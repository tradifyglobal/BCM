import hashlib
from urllib.parse import quote

import frappe
from frappe import _
from frappe.desk.doctype.notification_settings.notification_settings import is_notifications_enabled
from frappe.utils import add_days, escape_html, getdate, nowdate

from continuity360.rules import review_reminder_slot


def send_due_reminders(today=None) -> dict:
    today = getdate(today or nowdate())
    names = frappe.get_all(
        "C360 Business Continuity Plan",
        filters={"docstatus": 1, "review_date": ["<=", add_days(today, 30)]},
        pluck="name",
        order_by="name",
    )
    result = {"created": 0, "skipped": 0, "failed": 0}
    for name in names:
        frappe.db.savepoint("bcp_reminder")
        try:
            result["created" if _send_reminder(name, today) else "skipped"] += 1
        except Exception:
            frappe.db.rollback(save_point="bcp_reminder")
            frappe.log_error(
                title=_("BCP review reminder failed"),
                message=f"Plan: {name}\n{frappe.get_traceback()}",
            )
            result["failed"] += 1
    return result


def _send_reminder(name: str, today) -> bool:
    plan = frappe.get_doc("C360 Business Continuity Plan", name, for_update=True)
    if plan.docstatus != 1:
        return False
    slot = review_reminder_slot(getdate(plan.review_date), today)
    if not slot:
        return False
    recipient = plan.responsible_user
    if not frappe.db.get_value("User", recipient, "enabled"):
        frappe.throw(_("The BCP plan owner is disabled or missing."))
    if not frappe.has_permission(plan.doctype, "read", doc=plan, user=recipient):
        frappe.throw(_("The BCP plan owner cannot read the plan."), frappe.PermissionError)
    if not is_notifications_enabled(recipient):
        return False

    key = hashlib.sha256(
        "\0".join((plan.name, recipient, str(plan.review_date), slot)).encode("utf-8")
    ).hexdigest()
    if frappe.db.exists("C360 BCP Review Reminder", {"event_key": key}):
        return False

    title = _("Business continuity plan review")
    message = _("Review {0} by {1}.").format(escape_html(plan.plan_title), escape_html(str(plan.review_date)))
    notification = frappe.get_doc({
        "doctype": "Notification Log",
        "type": "C360 BCP Review",
        "for_user": recipient,
        "document_type": plan.doctype,
        "document_name": plan.name,
        "link": f"/desk/continuity360/c360-business-continuity-plan/{quote(plan.name, safe='')}",
        "title": title,
        "description": message,
    }).insert(ignore_permissions=True)
    frappe.get_doc({
        "doctype": "C360 BCP Review Reminder",
        "plan": plan.name,
        "company": plan.company,
        "recipient": recipient,
        "review_date": plan.review_date,
        "slot": slot,
        "event_key": key,
        "notification": notification.name,
    }).insert(ignore_permissions=True)
    return True
