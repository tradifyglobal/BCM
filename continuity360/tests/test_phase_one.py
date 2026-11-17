"""Run with Bench on a disposable test site, never on a customer site."""

import unittest
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import frappe
from frappe.model.workflow import apply_workflow

from continuity360.api import bcp_overview, overview
from continuity360.bcp_distribution import (
    acknowledge_distribution,
    distribute_approved_plan,
    get_distribution_audience,
    open_distribution,
)
from continuity360.bcp_reminders import send_due_reminders
from continuity360.bcp_snapshot import get_approved_snapshot
from continuity360.bcp_export import download_approved_plan, download_distribution


class TestPhaseOne(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.tag = uuid4().hex[:12]
        self.company = self.make("C360 Company", company_name=f"Test {self.tag}")
        self.department = self.make(
            "C360 Department", department_name="Operations", company=self.company.name,
            responsible_user="Administrator",
        )
        self.process = self.make(
            "C360 Business Process", process_name="Payroll", company=self.company.name,
            department=self.department.name, responsible_user="Administrator",
            rto_minutes=60, rpo_minutes=15, mtpd_minutes=240,
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        frappe.clear_cache()

    def make(self, doctype, **values):
        return frappe.get_doc({"doctype": doctype, **values}).insert()

    def user(self, label, role):
        email = f"c360-{label}-{self.tag}@example.invalid"
        self.make(
            "User", email=email, first_name=label, enabled=1, send_welcome_email=0,
            user_type="System User", roles=[{"role": role}],
        )
        return email

    def test_risk_scores_persist_and_cross_company_links_fail(self):
        risk = self.make(
            "C360 Risk", risk_title="Power loss", company=self.company.name,
            business_process=self.process.name, responsible_user="Administrator", likelihood=4, impact=5,
        )
        risk.reload()
        self.assertEqual((risk.score, risk.rating), (20, "Critical"))
        other = self.make("C360 Company", company_name="Other company")
        risk.company = other.name
        with self.assertRaises(frappe.ValidationError):
            risk.save()

    def test_employee_cannot_read_or_change_risks_and_guest_cannot_report(self):
        employee = self.user("employee", "Employee")
        frappe.set_user(employee)
        self.assertFalse(frappe.has_permission("C360 Risk", "read"))
        self.assertFalse(frappe.has_permission("C360 Risk", "write"))
        data = overview()
        risk_metric = next(item for item in data["metrics"] if item["doctype"] == "C360 Risk")
        self.assertIsNone(risk_metric["value"])
        self.assertIsNone(data["risk_distribution"])
        self.assertIsNone(data["process_distribution"])
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            overview()

    def test_approval_is_independent_and_submitted_plans_are_immutable(self):
        author = self.user("author", "IT Manager")
        approver = self.user("approver", "BCM Administrator")
        # An author with both roles must still not be able to self-approve.
        frappe.get_doc("User", author).add_roles("BCM Administrator")
        strategy = self.make(
            "C360 Recovery Strategy", strategy_name="Manual recovery", company=self.company.name,
        )
        frappe.set_user(author)
        plan = self.make(
            "C360 Recovery Plan", plan_title="Payroll recovery", company=self.company.name,
            business_process=self.process.name, responsible_user=author, strategy=strategy.name,
            scope="Restore payroll", activation_criteria="Payroll unavailable", rto_minutes=60,
            rpo_minutes=15, review_date=frappe.utils.add_days(frappe.utils.nowdate(), 30),
            change_reason="Initial controlled plan",
            steps=[{"instruction": "Restore and validate", "responsible_user": author,
                    "expected_minutes": 30, "validation": "Business owner accepts output"}],
        )
        plan.steps[0].instruction = "Restore and independently validate"
        with self.assertRaises(frappe.ValidationError):
            plan.save()
        plan.reload()
        plan.steps[0].instruction = "Restore and independently validate"
        plan.change_reason = "Clarified validation responsibility"
        plan.save()
        plan = apply_workflow(plan, "Request Review")
        with self.assertRaises(frappe.ValidationError):
            apply_workflow(plan, "Approve")
        frappe.set_user(approver)
        plan.reload()
        plan = apply_workflow(plan, "Approve")
        plan.reload()
        self.assertEqual(plan.docstatus, 1)
        self.assertEqual(plan.approved_by, approver)
        plan.scope = "Unauthorized post-approval edit"
        with self.assertRaises(frappe.ValidationError):
            plan.save()

    def test_dashboard_honours_company_user_permissions(self):
        other = self.make("C360 Company", company_name="Restricted company")
        other_department = self.make(
            "C360 Department", department_name="Restricted operations", company=other.name,
            responsible_user="Administrator",
        )
        self.make(
            "C360 Business Process", process_name="Restricted process", company=other.name,
            department=other_department.name, responsible_user="Administrator",
            criticality="Critical", rto_minutes=60, rpo_minutes=15, mtpd_minutes=240,
        )
        for company in (self.company.name, other.name):
            self.make(
                "C360 Risk", risk_title="Restricted risk", company=company,
                responsible_user="Administrator", likelihood=2, impact=3,
            )
        reader = self.user("risk-reader", "Risk Manager")
        self.make(
            "User Permission", user=reader, allow="C360 Company", for_value=self.company.name,
            apply_to_all_doctypes=1,
        )
        frappe.set_user(reader)
        data = overview()
        metric = next(item for item in data["metrics"] if item["label"] == "Open risks")
        self.assertEqual(metric["value"], 1)
        self.assertEqual(len(data["risks"]), 1)
        self.assertEqual({row.rating: row.total for row in data["risk_distribution"]}, {"Medium": 1})
        self.assertEqual(
            {row.criticality: row.total for row in data["process_distribution"]}, {"Medium": 1}
        )

    def test_business_continuity_plan_links_and_independent_approval(self):
        author = self.user("bcp-author", "BCP Author")
        manager = self.user("bcp-manager", "BCP Manager Reviewer")
        other_manager = self.user("bcp-other-manager", "BCP Manager Reviewer")
        bcm = self.user("bcp-bcm", "BCM Administrator")
        executive = self.user("bcp-executive", "BCP Executive Approver")
        frappe.get_doc("User", author).add_roles("IT Manager")
        strategy = self.make(
            "C360 Recovery Strategy", strategy_name="Manual recovery", company=self.company.name,
        )
        recovery = self.make(
            "C360 Recovery Plan", plan_title="Recovery", company=self.company.name,
            business_process=self.process.name, responsible_user=author, strategy=strategy.name,
            scope="Recover the process", activation_criteria="Unavailable", rto_minutes=60,
            rpo_minutes=15, review_date=frappe.utils.add_days(frappe.utils.nowdate(), 30),
            change_reason="Initial plan",
            steps=[{"instruction": "Restore", "responsible_user": author,
                    "expected_minutes": 30, "validation": "Confirm service"}],
        )
        contact = self.make(
            "C360 Emergency Contact", contact_name="Operations lead", contact_type="Employee",
            company=self.company.name, phone="555-0101",
        )
        team = self.make(
            "C360 BCP Recovery Team", team_name="Operations", company=self.company.name,
            responsible_user=author, members=[{"contact": contact.name, "responsibility": "Coordinate"}],
        )
        strategy = self.make(
            "C360 Continuity Strategy", strategy_name="Manual processing", company=self.company.name,
            responsible_user=author, strategy_type="Manual Processing", description="Use paper forms",
        )
        procedure = self.make(
            "C360 BCP Procedure", procedure_name="Manual payroll", company=self.company.name,
            responsible_user=author, trigger="System unavailable",
            steps=[{"instruction": "Start manual processing", "responsible_user": author}],
        )
        frappe.set_user(author)
        plan = self.make(
            "C360 Business Continuity Plan", plan_title="Continuity", company=self.company.name,
            business_process=self.process.name, responsible_user=author, scope="Continue operations",
            activation_criteria="Process unavailable", continuity_procedures="Use manual process",
            communication_procedures="Notify process owner",
            manager_reviewer=manager, bcm_reviewer=bcm, executive_approver=executive,
            business_units=[{"department": self.department.name}],
            strategies=[{"strategy": strategy.name}], teams=[{"team": team.name}],
            procedures=[{"procedure": procedure.name}],
            recovery_plans=[{"recovery_plan": recovery.name}],
            review_date=frappe.utils.add_days(frappe.utils.nowdate(), 730), change_reason="Initial plan",
        )
        plan.reload()
        self.assertEqual(plan.recovery_plans[0].recovery_plan, recovery.name)
        self.assertEqual(plan.business_units[0].department, self.department.name)
        self.assertEqual(plan.procedures[0].procedure, procedure.name)
        plan.append("recovery_plans", {"recovery_plan": recovery.name})
        plan.change_reason = "Duplicate link"
        with self.assertRaises(frappe.ValidationError):
            plan.save()
        plan.reload()
        plan.scope = "Changed without revision reason"
        with self.assertRaises(frappe.ValidationError):
            plan.save()
        plan.reload()
        plan.executive_approver = author
        plan.change_reason = "Invalid reviewer"
        with self.assertRaises(frappe.ValidationError):
            plan.save()
        plan.reload()
        plan = apply_workflow(plan, "Request Manager Review")
        self.assertEqual(bcp_overview()["under_approval"], 1)
        frappe.set_user(other_manager)
        with self.assertRaises(frappe.PermissionError):
            apply_workflow(plan, "Request BCM Review")
        frappe.set_user(manager)
        plan.reload()
        plan = apply_workflow(plan, "Request BCM Review")
        frappe.set_user(bcm)
        plan.reload()
        plan = apply_workflow(plan, "Request Executive Approval")
        frappe.set_user(executive)
        plan.reload()
        with self.assertRaises(frappe.ValidationError):
            apply_workflow(plan, "Approve")
        self.assertFalse(frappe.db.exists("C360 BCP Approval Snapshot", {"plan": plan.name}))
        plan.reload()
        plan = apply_workflow(plan, "Return to Draft")
        frappe.set_user(author)
        plan.reload()
        plan.review_date = frappe.utils.add_days(frappe.utils.nowdate(), 30)
        plan.change_reason = "Set annual review date"
        plan.save()
        plan = apply_workflow(plan, "Request Manager Review")
        contact.reload()
        contact.phone = "555-0105"
        contact.save()
        frappe.set_user(manager)
        plan.reload()
        plan = apply_workflow(plan, "Request BCM Review")
        frappe.set_user(bcm)
        plan.reload()
        plan = apply_workflow(plan, "Request Executive Approval")
        frappe.set_user(executive)
        plan.reload()
        with self.assertRaises(frappe.ValidationError):
            apply_workflow(plan, "Approve")
        self.assertFalse(frappe.db.exists("C360 BCP Approval Snapshot", {"plan": plan.name}))
        plan.reload()
        plan = apply_workflow(plan, "Return to Draft")
        frappe.set_user(author)
        plan.reload()
        plan = apply_workflow(plan, "Request Manager Review")
        frappe.set_user(manager)
        plan.reload()
        plan = apply_workflow(plan, "Request BCM Review")
        frappe.set_user(bcm)
        plan.reload()
        plan = apply_workflow(plan, "Request Executive Approval")
        frappe.set_user(executive)
        plan.reload()
        plan = apply_workflow(plan, "Approve")
        plan.reload()
        self.assertEqual(plan.plan_version, "1.0")
        self.assertEqual((plan.docstatus, plan.approved_by), (1, executive))
        summary = bcp_overview()
        self.assertEqual((summary["total"], summary["due_for_review"], summary["under_approval"]), (1, 1, 0))
        self.assertFalse(frappe.has_permission("C360 BCP Approval Snapshot", "read"))
        snapshot_name = frappe.db.get_value("C360 BCP Approval Snapshot", {"plan": plan.name}, "name")
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("C360 BCP Approval Snapshot", snapshot_name).check_permission("read")
        executive_snapshot = get_approved_snapshot(plan.name)
        self.assertIn({"doctype": "C360 Recovery Plan", "restricted": True}, executive_snapshot["records"])
        frappe.set_user(author)
        strategy.reload()
        strategy.description = "Updated after approval"
        strategy.save()
        contact.reload()
        contact.phone = "555-0102"
        contact.save()
        snapshot = get_approved_snapshot(plan.name)
        saved = {record.get("name"): record["content"] for record in snapshot["records"]
                 if not record.get("restricted")}
        self.assertEqual(saved[strategy.name]["description"], "Use paper forms")
        self.assertEqual(saved[contact.name]["phone"], "555-0105")
        self.assertEqual(frappe.get_doc("C360 Emergency Contact", contact.name).phone, "555-0102")
        self.assertIn(recovery.name, saved)
        download_approved_plan(plan.name, "docx")
        with ZipFile(BytesIO(frappe.local.response.filecontent)) as archive:
            self.assertIsNone(archive.testzip())
            text = "".join(ET.fromstring(archive.read("word/document.xml")).itertext())
            self.assertIn("Version: 1.0", text)
            self.assertIn("Use paper forms", text)
            self.assertIn("555-0105", text)
            self.assertNotIn("555-0102", text)
            self.assertIn("Uncontrolled downloaded copy", text)
        with self.assertRaises(frappe.ValidationError):
            download_approved_plan(plan.name, "html")
        frappe.set_user("Administrator")
        employee = self.user("bcp-snapshot-employee", "Employee")
        frappe.set_user(employee)
        with self.assertRaises(frappe.PermissionError):
            get_approved_snapshot(plan.name)
        with self.assertRaises(frappe.PermissionError):
            download_approved_plan(plan.name, "docx")
        frappe.set_user("Administrator")
        staff = self.user("bcp-covered-staff", "Employee")
        self.make(
            "C360 Employee", employee_name="Covered staff", company=self.company.name,
            department=self.department.name, user=staff, email=staff,
        )
        frappe.set_user(author)
        audience = get_distribution_audience(plan.name)
        eligible_users = {item["user"] for item in audience}
        self.assertIn(staff, eligible_users)
        self.assertNotIn(employee, eligible_users)
        with self.assertRaises(frappe.PermissionError):
            distribute_approved_plan(plan.name, [employee])
        frappe.set_user(manager)
        with self.assertRaises(frappe.PermissionError):
            distribute_approved_plan(plan.name, [staff])
        frappe.set_user(author)
        with patch("frappe.desk.doctype.notification_log.notification_log.send_notification_email"):
            distribution = distribute_approved_plan(plan.name, [staff])["distribution"]
        frappe.set_user(employee)
        with self.assertRaises(frappe.PermissionError):
            open_distribution(distribution)
        with self.assertRaises(frappe.PermissionError):
            download_distribution(distribution, "docx")
        frappe.set_user(staff)
        delivered = open_distribution(distribution)
        self.assertEqual(delivered["plan"]["name"], plan.name)
        self.assertEqual(delivered["distribution"]["open_count"], 1)
        self.assertTrue(any(record.get("restricted") for record in delivered["records"]))
        download_distribution(distribution, "docx")
        with ZipFile(BytesIO(frappe.local.response.filecontent)) as archive:
            text = "".join(ET.fromstring(archive.read("word/document.xml")).itertext())
            self.assertIn("Version: 1.0", text)
            self.assertIn("Restricted linked record", text)
            self.assertNotIn("555-0105", text)
        download_distribution(distribution, "pdf")
        from pypdf import PdfReader

        pdf = PdfReader(BytesIO(frappe.local.response.filecontent))
        pdf_text = "\n".join(page.extract_text() for page in pdf.pages)
        self.assertIn("Continuity", pdf_text)
        self.assertIn("1.0", pdf_text)
        self.assertNotIn("555-0105", pdf_text)
        self.assertEqual(open_distribution(distribution)["distribution"]["open_count"], 2)
        self.assertTrue(acknowledge_distribution(distribution)["acknowledged_on"])
        self.assertTrue(acknowledge_distribution(distribution)["acknowledged_on"])
        self.assertEqual(
            frappe.db.get_value(
                "C360 BCP Distribution Recipient",
                {"parent": distribution, "recipient": staff},
                "open_count",
            ),
            2,
        )
        self.assertTrue(
            frappe.db.get_value(
                "C360 BCP Distribution Recipient",
                {"parent": distribution, "recipient": staff},
                "acknowledged_on",
            )
        )
        frappe.set_user("Administrator")
        with patch("frappe.desk.doctype.notification_log.notification_log.send_notification_email") as send_email:
            for offset in (0, 23, 29, 31, 38):
                result = send_due_reminders(frappe.utils.add_days(frappe.utils.nowdate(), offset))
                self.assertEqual((result["created"], result["failed"]), (1, 0))
                self.assertEqual(send_due_reminders(frappe.utils.add_days(frappe.utils.nowdate(), offset))["created"], 0)
            self.assertEqual(send_email.call_count, 5)
        reminders = frappe.get_all(
            "C360 BCP Review Reminder", filters={"plan": plan.name}, fields=["slot", "recipient"]
        )
        self.assertEqual(
            {row.slot for row in reminders},
            {"before-30", "before-7", "before-1", "overdue-1", "overdue-2"},
        )
        self.assertEqual({row.recipient for row in reminders}, {author})
        self.assertEqual(
            frappe.db.count("Notification Log", {
                "type": "C360 BCP Review",
                "document_type": plan.doctype,
                "document_name": plan.name,
            }),
            5,
        )
        from frappe.desk.doctype.notification_settings.notification_settings import create_notification_settings

        create_notification_settings(author)
        settings = frappe.get_doc("Notification Settings", author)
        settings.set("email_notification_types", [])
        settings.save(ignore_permissions=True)
        frappe.clear_document_cache("Notification Settings", author)
        with patch("frappe.desk.doctype.notification_log.notification_log.send_notification_email") as send_email:
            result = send_due_reminders(frappe.utils.add_days(frappe.utils.nowdate(), 45))
        self.assertEqual((result["created"], result["failed"]), (1, 0))
        send_email.assert_not_called()
        settings.reload()
        settings.enabled = 0
        settings.save(ignore_permissions=True)
        result = send_due_reminders(frappe.utils.add_days(frappe.utils.nowdate(), 52))
        self.assertEqual((result["created"], result["failed"]), (0, 0))
        settings.enabled = 1
        settings.save(ignore_permissions=True)
        frappe.get_doc("User", author).remove_roles("BCP Author", "IT Manager")
        with patch("continuity360.bcp_reminders.frappe.log_error") as log_error:
            result = send_due_reminders(frappe.utils.add_days(frappe.utils.nowdate(), 52))
        self.assertEqual((result["created"], result["failed"]), (0, 1))
        log_error.assert_called_once()
        self.assertEqual(frappe.db.count("C360 BCP Review Reminder", {"plan": plan.name}), 6)
        frappe.set_user(executive)
        plan.scope = "Unauthorized edit"
        with self.assertRaises(frappe.ValidationError):
            plan.save()

    def test_bcp_amendments_numbering_and_immutable_version_lineage(self):
        author = self.user("version-author", "BCP Author")
        manager = self.user("version-manager", "BCP Manager Reviewer")
        bcm = self.user("version-bcm", "BCM Administrator")
        executive = self.user("version-executive", "BCP Executive Approver")

        def draft(**changes):
            return self.make(
                "C360 Business Continuity Plan", **{
                    "plan_title": "Versioned plan", "company": self.company.name,
                    "responsible_user": author, "manager_reviewer": manager,
                    "bcm_reviewer": bcm, "executive_approver": executive,
                    "scope": "<p>Continue <strong>operations</strong> &amp; payroll</p>",
                    "activation_criteria": "Office unavailable",
                    "continuity_procedures": "Use manual processing",
                    "communication_procedures": "Notify the owner",
                    "review_date": frappe.utils.add_days(frappe.utils.nowdate(), 30),
                    "change_reason": "Document revision", **changes,
                },
            )

        def approve_and_retire(plan):
            for user, action in (
                (author, "Request Manager Review"), (manager, "Request BCM Review"),
                (bcm, "Request Executive Approval"), (executive, "Approve"), (bcm, "Retire"),
            ):
                frappe.set_user(user)
                plan.reload()
                plan = apply_workflow(plan, action)
            frappe.set_user(author)
            return plan

        frappe.set_user(author)
        plan = draft(plan_version="99.0")
        self.assertEqual(frappe.db.get_value(plan.doctype, plan.name, "plan_version"), "1.0")
        for fieldname, value in (("plan_version", "9.0"), ("revision_type", "Major"),
                                 ("amended_from", "fake-plan")):
            plan.reload()
            plan.set(fieldname, value)
            plan.change_reason = "Attempt to change version"
            with self.assertRaises(frappe.ValidationError):
                plan.save()
        plan.reload()
        with self.assertRaises(frappe.ValidationError):
            download_approved_plan(plan.name, "docx")
        with self.assertRaises(frappe.ValidationError):
            draft(amended_from=plan.name)
        plan = approve_and_retire(plan)
        download_approved_plan(plan.name, "docx")
        with ZipFile(BytesIO(frappe.local.response.filecontent)) as archive:
            text = "".join(ET.fromstring(archive.read("word/document.xml")).itertext())
            self.assertIn("HISTORICAL PLAN", text)
            self.assertIn("operations", text)
            self.assertNotIn("<strong>", text)
        minor = draft(amended_from=plan.name, revision_type="Minor")
        self.assertEqual(minor.plan_version, "1.1")
        with self.assertRaises(frappe.ValidationError):
            draft(amended_from=plan.name)
        minor = approve_and_retire(minor)
        major = draft(amended_from=minor.name, revision_type="Major")
        self.assertEqual(major.plan_version, "2.0")
        self.assertEqual(get_approved_snapshot(plan.name)["plan"]["plan_version"], "1.0")
        self.assertEqual(get_approved_snapshot(minor.name)["plan"]["plan_version"], "1.1")
        self.assertFalse(frappe.db.exists("C360 BCP Approval Snapshot", {"plan": major.name}))
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            download_approved_plan(plan.name, "docx")

    def test_business_continuity_plan_rejects_cross_company_recovery_links(self):
        other = self.make("C360 Company", company_name="Other company")
        manager = self.user("bcp-link-manager", "BCP Manager Reviewer")
        bcm = self.user("bcp-link-bcm", "BCM Administrator")
        executive = self.user("bcp-link-executive", "BCP Executive Approver")
        strategy = self.make("C360 Recovery Strategy", strategy_name="Recovery", company=self.company.name)
        recovery = self.make(
            "C360 Recovery Plan", plan_title="Recovery", company=self.company.name,
            business_process=self.process.name, responsible_user="Administrator", strategy=strategy.name,
            scope="Recover", activation_criteria="Unavailable", rto_minutes=60, rpo_minutes=15,
            review_date=frappe.utils.add_days(frappe.utils.nowdate(), 30), change_reason="Initial plan",
            steps=[{"instruction": "Restore", "responsible_user": "Administrator",
                    "expected_minutes": 30, "validation": "Confirm"}],
        )
        with self.assertRaises(frappe.ValidationError):
            self.make(
                "C360 Business Continuity Plan", plan_title="Continuity", company=other.name,
                responsible_user="Administrator", scope="Continue", activation_criteria="Unavailable",
                continuity_procedures="Manual process", communication_procedures="Notify owner",
                manager_reviewer=manager, bcm_reviewer=bcm, executive_approver=executive,
                recovery_plans=[{"recovery_plan": recovery.name}],
                review_date=frappe.utils.add_days(frappe.utils.nowdate(), 30), change_reason="Initial plan",
            )
        contact = self.make(
            "C360 Emergency Contact", contact_name="Other contact", company=other.name,
            contact_type="Vendor",
        )
        with self.assertRaises(frappe.ValidationError):
            self.make(
                "C360 BCP Recovery Team", team_name="Operations", company=self.company.name,
                responsible_user="Administrator",
                members=[{"contact": contact.name, "responsibility": "Support"}],
            )
        author = self.user("bcp-restricted-author", "BCP Author")
        frappe.set_user(author)
        values = {
            "plan_title": "Restricted continuity", "company": self.company.name,
            "responsible_user": author, "scope": "Continue", "activation_criteria": "Unavailable",
            "continuity_procedures": "Manual process", "communication_procedures": "Notify owner",
            "manager_reviewer": manager, "bcm_reviewer": bcm, "executive_approver": executive,
            "review_date": frappe.utils.add_days(frappe.utils.nowdate(), 30), "change_reason": "Initial plan",
        }
        with self.assertRaises(frappe.PermissionError):
            self.make("C360 Business Continuity Plan", **values,
                      recovery_plans=[{"recovery_plan": recovery.name}])
        plan = self.make("C360 Business Continuity Plan", **values, owner=manager)
        self.assertEqual(plan.owner, author)

    def test_bcp_dashboard_respects_company_and_role_permissions(self):
        manager = self.user("bcp-dashboard-manager", "BCP Manager Reviewer")
        bcm = self.user("bcp-dashboard-bcm", "BCM Administrator")
        executive = self.user("bcp-dashboard-executive", "BCP Executive Approver")
        other = self.make("C360 Company", company_name="Other company")
        for company in (self.company.name, other.name):
            self.make(
                "C360 Business Continuity Plan", plan_title="Continuity", company=company,
                responsible_user="Administrator", manager_reviewer=manager, bcm_reviewer=bcm,
                executive_approver=executive, scope="Continue", activation_criteria="Unavailable",
                continuity_procedures="Manual process", communication_procedures="Notify owner",
                review_date=frappe.utils.add_days(frappe.utils.nowdate(), 30), change_reason="Initial plan",
            )
        self.make(
            "User Permission", user=manager, allow="C360 Company", for_value=self.company.name,
            apply_to_all_doctypes=1,
        )
        frappe.set_user(manager)
        self.assertEqual(bcp_overview()["total"], 1)
        frappe.set_user("Administrator")
        employee = self.user("bcp-dashboard-employee", "Employee")
        frappe.set_user(employee)
        with self.assertRaises(frappe.PermissionError):
            bcp_overview()

    def test_dashboard_charts_count_all_records_not_just_top_six(self):
        for index in range(7):
            self.make(
                "C360 Risk", risk_title=f"Risk {index}", company=self.company.name,
                responsible_user="Administrator", likelihood=2, impact=3,
            )
            self.make(
                "C360 Business Process", process_name=f"Process {index}", company=self.company.name,
                department=self.department.name, responsible_user="Administrator",
                criticality="High", rto_minutes=60, rpo_minutes=15, mtpd_minutes=240,
            )
        self.make(
            "C360 Risk", risk_title="Closed risk", company=self.company.name,
            responsible_user="Administrator", likelihood=2, impact=3,
            status="Closed", acceptance_reason="Closed after review",
        )
        data = overview()
        self.assertEqual(len(data["risks"]), 6)
        self.assertEqual({row.rating: row.total for row in data["risk_distribution"]}, {"Medium": 7})
        self.assertEqual(
            {row.criticality: row.total for row in data["process_distribution"]}, {"High": 7, "Medium": 1}
        )

    def test_compliance_controls_respect_roles_and_company_permissions(self):
        other = self.make("C360 Company", company_name="Other company")
        for company in (self.company.name, other.name):
            self.make(
                "C360 Compliance Control", control_title="Recovery review", company=company,
                framework="Customer framework", control_reference="TEST-1",
                responsible_user="Administrator", evidence_reference="Internal review record",
            )
        auditor = self.user("auditor", "Auditor")
        self.make(
            "User Permission", user=auditor, allow="C360 Company", for_value=self.company.name,
            apply_to_all_doctypes=1,
        )
        frappe.set_user(auditor)
        controls = frappe.get_list("C360 Compliance Control", fields=["name", "company"])
        self.assertEqual([control.company for control in controls], [self.company.name])
        self.assertTrue(frappe.has_permission("C360 Compliance Control", "read"))
        self.assertFalse(frappe.has_permission("C360 Compliance Control", "write"))
        frappe.set_user("Administrator")
        employee = self.user("employee-control", "Employee")
        frappe.set_user(employee)
        self.assertFalse(frappe.has_permission("C360 Compliance Control", "read"))
