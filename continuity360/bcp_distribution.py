from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import escape_html, now_datetime

from continuity360.bcp_snapshot import render_snapshot


@frappe.whitelist()
def get_distribution_audience(plan_name: str) -> list[dict]:
    plan = _get_publishable_plan(plan_name)
    return _eligible_recipients(plan)


@frappe.whitelist()
def distribute_approved_plan(plan_name: str, recipients) -> dict:
    plan = _get_publishable_plan(plan_name)
    if isinstance(recipients, str):
        recipients = frappe.parse_json(recipients)
    if not isinstance(recipients, list) or not recipients or any(
        not isinstance(user, str) or not user for user in recipients
    ):
        frappe.throw(_("Select at least one recipient."))
    if len(recipients) != len(set(recipients)):
        frappe.throw(_("A recipient can only be selected once."))

    audience = {item["user"]: item for item in _eligible_recipients(plan)}
    if any(user not in audience for user in recipients):
        frappe.throw(_("Recipients must be enabled internal stakeholders identified by this plan."),
                     frappe.PermissionError)

    snapshot = frappe.db.get_value(
        "C360 BCP Approval Snapshot", {"plan": plan.name}, "name"
    )
    if not snapshot:
        frappe.throw(_("The approved plan has no approval snapshot."))

    users = frappe.get_all(
        "User", filters={"name": ["in", recipients], "enabled": 1, "user_type": "System User"},
        fields=["name", "full_name", "email"],
    )
    users_by_name = {user.name: user for user in users}
    if set(users_by_name) != set(recipients):
        frappe.throw(_("Every recipient must be an enabled system user."))

    distribution = frappe.get_doc({
        "doctype": "C360 BCP Distribution",
        "plan": plan.name,
        "company": plan.company,
        "snapshot": snapshot,
        "distributed_by": frappe.session.user,
        "distributed_on": now_datetime(),
        "recipients": [
            {
                "recipient": user,
                "recipient_name": users_by_name[user].full_name or user,
                "reason": audience[user]["reason"],
            }
            for user in recipients
        ],
    }).insert(ignore_permissions=True)

    title = _("Approved business continuity plan")
    description = _("A plan for {0} is ready for review.").format(escape_html(plan.plan_title))
    for user in recipients:
        frappe.get_doc({
            "doctype": "Notification Log",
            "type": "C360 BCP Distribution",
            "for_user": user,
            "document_type": plan.doctype,
            "document_name": plan.name,
            "link": f"/desk/bcp-distribution?distribution={quote(distribution.name, safe='')}",
            "title": title,
            "description": description,
        }).insert(ignore_permissions=True)

    return {"distribution": distribution.name, "recipient_count": len(recipients)}


@frappe.whitelist()
def open_distribution(distribution_name: str) -> dict:
    distribution = frappe.get_doc("C360 BCP Distribution", distribution_name, for_update=True)
    recipient = _get_recipient(distribution)
    opened = now_datetime()
    recipient.first_opened_on = recipient.first_opened_on or opened
    recipient.last_opened_on = opened
    recipient.open_count = (recipient.open_count or 0) + 1
    distribution.save(ignore_permissions=True)

    snapshot = frappe.get_doc("C360 BCP Approval Snapshot", distribution.snapshot)
    content = render_snapshot(snapshot)
    content["current_status"] = frappe.db.get_value(
        "C360 Business Continuity Plan", distribution.plan, "approval_status"
    )
    content["distribution"] = {
        "name": distribution.name,
        "first_opened_on": recipient.first_opened_on,
        "last_opened_on": recipient.last_opened_on,
        "open_count": recipient.open_count,
        "acknowledged_on": recipient.acknowledged_on,
    }
    return content


@frappe.whitelist()
def acknowledge_distribution(distribution_name: str) -> dict:
    distribution = frappe.get_doc("C360 BCP Distribution", distribution_name, for_update=True)
    recipient = _get_recipient(distribution)
    if not recipient.first_opened_on:
        frappe.throw(_("Open the distributed plan before acknowledging it."))
    if not recipient.acknowledged_on:
        recipient.acknowledged_on = now_datetime()
        distribution.save(ignore_permissions=True)
    return {"acknowledged_on": recipient.acknowledged_on}


def _get_publishable_plan(plan_name: str):
    plan = frappe.get_doc("C360 Business Continuity Plan", plan_name)
    plan.check_permission("read")
    if plan.docstatus != 1 or plan.approval_status != "Approved":
        frappe.throw(_("Only approved business continuity plans can be distributed."))
    is_owner = frappe.session.user == plan.responsible_user
    is_bcm_admin = "BCM Administrator" in frappe.get_roles()
    if not (is_owner or is_bcm_admin):
        frappe.throw(_("Only the plan owner or a BCM Administrator may distribute this plan."),
                     frappe.PermissionError)
    return plan


def _eligible_recipients(plan) -> list[dict]:
    reasons: dict[str, list[str]] = {}

    def include(user: str | None, reason: str) -> None:
        if user:
            reasons.setdefault(user, [])
            if reason not in reasons[user]:
                reasons[user].append(reason)

    include(plan.responsible_user, _("Plan owner"))
    include(plan.owner, _("Plan author"))
    include(plan.manager_reviewer, _("Manager reviewer"))
    include(plan.bcm_reviewer, _("BCM reviewer"))
    include(plan.executive_approver, _("Executive approver"))

    department_names = {row.department for row in plan.business_units if row.department}
    process = None
    if plan.business_process:
        process = frappe.get_doc("C360 Business Process", plan.business_process)
        include(process.responsible_user, _("Business process owner"))
        if not department_names and process.department:
            department_names.add(process.department)

    employees = frappe.get_all(
        "C360 Employee",
        filters={"company": plan.company},
        fields=["user", "employee_name", "email", "department"],
    )
    users_by_email = {}
    users_in_company = set()
    for employee in employees:
        if employee.user:
            users_in_company.add(employee.user)
            if employee.email:
                users_by_email[employee.email.strip().lower()] = employee.user
            if employee.department in department_names:
                include(employee.user, _("Covered business unit: {0}").format(
                    employee.employee_name or employee.department
                ))

    for link in plan.teams:
        team = frappe.get_doc("C360 BCP Recovery Team", link.team)
        for member in team.members:
            email = frappe.db.get_value("C360 Emergency Contact", member.contact, "email")
            user = users_by_email.get((email or "").strip().lower())
            if user:
                include(user, _("Recovery team: {0}").format(team.team_name))

    for link in plan.procedures:
        procedure = frappe.get_doc("C360 BCP Procedure", link.procedure)
        for step in procedure.steps:
            if step.responsible_user in users_in_company:
                include(step.responsible_user, _("Continuity procedure: {0}").format(
                    procedure.procedure_name
                ))

    for link in plan.recovery_plans:
        recovery = frappe.get_doc("C360 Recovery Plan", link.recovery_plan)
        for user in [recovery.responsible_user, *(step.responsible_user for step in recovery.steps)]:
            if user in users_in_company:
                include(user, _("Related recovery plan: {0}").format(recovery.plan_title))

    if not reasons:
        return []
    users = frappe.get_all(
        "User",
        filters={
            "name": ["in", list(reasons)],
            "enabled": 1,
            "user_type": "System User",
        },
        fields=["name", "full_name", "email"],
        order_by="full_name asc",
    )
    return [
        {
            "user": user.name,
            "label": user.full_name or user.name,
            "email": user.email,
            "reason": "; ".join(reasons[user.name]),
        }
        for user in users
    ]


def _get_recipient(distribution):
    if frappe.session.user == "Guest":
        frappe.throw(_("Sign in with the account that received this distribution."),
                     frappe.PermissionError)
    for recipient in distribution.recipients:
        if recipient.recipient == frappe.session.user:
            return recipient
    frappe.throw(_("This distribution is not addressed to your account."),
                 frappe.PermissionError)
