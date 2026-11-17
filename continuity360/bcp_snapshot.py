import hashlib
import json

import frappe
from frappe import _


def linked_records(plan) -> list:
    links = set()
    if plan.business_process:
        links.add(("C360 Business Process", plan.business_process))
    for table, fieldname, doctype in (
        ("business_units", "department", "C360 Department"),
        ("strategies", "strategy", "C360 Continuity Strategy"),
        ("teams", "team", "C360 BCP Recovery Team"),
        ("procedures", "procedure", "C360 BCP Procedure"),
        ("recovery_plans", "recovery_plan", "C360 Recovery Plan"),
    ):
        links.update((doctype, row.get(fieldname)) for row in plan.get(table))

    records = []
    contacts = set()
    for doctype, name in sorted(links):
        record = frappe.get_doc(doctype, name, for_update=True)
        if record.company != plan.company:
            frappe.throw(_("Linked records must belong to the same company."))
        records.append({"doctype": doctype, "name": name, "content": record.as_dict()})
        if doctype == "C360 BCP Recovery Team":
            contacts.update(row.contact for row in record.members)

    for name in sorted(contacts):
        contact = frappe.get_doc("C360 Emergency Contact", name, for_update=True)
        if contact.company != plan.company:
            frappe.throw(_("Linked records must belong to the same company."))
        records.append({"doctype": contact.doctype, "name": name, "content": contact.as_dict()})

    return records


def fingerprint(records: list) -> str:
    return hashlib.sha256(frappe.as_json(records, indent=None).encode("utf-8")).hexdigest()


def capture(plan) -> None:
    records = linked_records(plan)
    if not plan.review_fingerprint or fingerprint(records) != plan.review_fingerprint:
        frappe.throw(_("Linked content changed during review. Return the plan to draft and review it again."))
    frappe.get_doc({
        "doctype": "C360 BCP Approval Snapshot",
        "plan": plan.name,
        "company": plan.company,
        "captured_on": plan.approved_on,
        "payload": frappe.as_json({"plan": plan.as_dict(), "records": records}),
    }).insert(ignore_permissions=True)


@frappe.whitelist()
def get_approved_snapshot(plan_name: str) -> dict:
    plan = frappe.get_doc("C360 Business Continuity Plan", plan_name)
    plan.check_permission("read")
    if plan.docstatus not in (1, 2):
        frappe.throw(_("An approved snapshot is only available for approved or retired plans."))
    snapshot = frappe.db.get_value(
        "C360 BCP Approval Snapshot", {"plan": plan.name}, ["captured_on", "payload"], as_dict=True
    )
    if not snapshot:
        frappe.throw(_("No approved snapshot exists for this plan."))
    return render_snapshot(snapshot)


def render_snapshot(snapshot) -> dict:
    data = json.loads(snapshot.payload)
    records = []
    for record in data["records"]:
        doctype, name = record["doctype"], record["name"]
        if frappe.db.exists(doctype, name) and frappe.has_permission(doctype, "read", doc=name):
            content = frappe.get_doc(record["content"]).copy_with_fieldlevel_read_permissions().as_dict()
            records.append({"doctype": doctype, "name": name, "content": content})
        else:
            records.append({"doctype": doctype, "restricted": True})
    approved_plan = frappe.get_doc(data["plan"]).copy_with_fieldlevel_read_permissions().as_dict()
    return {"captured_on": snapshot.captured_on, "plan": approved_plan, "records": records}
