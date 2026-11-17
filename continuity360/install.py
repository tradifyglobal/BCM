import frappe

from continuity360.schema import DOCTYPES, ROLES


def after_install() -> None:
    sync_metadata()


def after_migrate() -> None:
    sync_metadata()


def assert_installed() -> None:
    if "continuity360" not in frappe.get_installed_apps():
        frappe.throw("The existing site has no Continuity360 installation. Resolve the partial setup first.")


def sync_metadata() -> None:
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
                ignore_permissions=True
            )
    for name, definition in DOCTYPES.items():
        if frappe.db.exists("DocType", name):
            doc = frappe.get_doc("DocType", name)
            if doc.module != "Continuity360" or not doc.custom:
                frappe.throw(f"Cannot replace DocType {name}: it is not owned by Continuity360.")
            doc.update({key: value for key, value in definition.items() if key not in ("name", "doctype")})
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc(definition).insert(ignore_permissions=True)
    _workflow()
    for notification_type in ("C360 BCP Review", "C360 BCP Distribution"):
        if not frappe.db.exists("Notification Type", notification_type):
            frappe.get_doc({
                "doctype": "Notification Type", "type_name": notification_type, "enabled": 1,
            }).insert(ignore_permissions=True)
    frappe.clear_cache()


def _workflow() -> None:
    for state, style in (("Draft", "Primary"), ("In Review", "Warning"), ("Manager Review", "Warning"),
                         ("BCM Review", "Warning"), ("Executive Approval", "Warning"),
                         ("Approved", "Success"), ("Retired", "Inverse")):
        if not frappe.db.exists("Workflow State", state):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert()
    for action in ("Request Review", "Request Manager Review", "Request BCM Review",
                   "Request Executive Approval", "Return to Draft", "Approve", "Retire"):
        if not frappe.db.exists("Workflow Action Master", action):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert()
    _plan_workflow("C360 Recovery Plan")
    _bcp_workflow()


def _bcp_workflow() -> None:
    name = "C360 Business Continuity Plan Approval"
    if frappe.db.exists("Workflow", name):
        return
    frappe.get_doc({
        "doctype": "Workflow", "workflow_name": name,
        "document_type": "C360 Business Continuity Plan", "is_active": 1,
        "workflow_state_field": "approval_status",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": "BCP Author"},
            {"state": "Manager Review", "doc_status": "0", "allow_edit": "BCP Manager Reviewer"},
            {"state": "BCM Review", "doc_status": "0", "allow_edit": "BCM Administrator"},
            {"state": "Executive Approval", "doc_status": "0", "allow_edit": "BCP Executive Approver"},
            {"state": "Approved", "doc_status": "1", "allow_edit": "BCM Administrator"},
            {"state": "Retired", "doc_status": "2", "allow_edit": "BCM Administrator"},
        ],
        "transitions": [
            {"state": "Draft", "action": "Request Manager Review", "next_state": "Manager Review",
             "allowed": "BCP Author", "allow_self_approval": 1},
            {"state": "Manager Review", "action": "Request BCM Review", "next_state": "BCM Review",
             "allowed": "BCP Manager Reviewer", "allow_self_approval": 1},
            {"state": "BCM Review", "action": "Request Executive Approval", "next_state": "Executive Approval",
             "allowed": "BCM Administrator", "allow_self_approval": 1},
            {"state": "Executive Approval", "action": "Approve", "next_state": "Approved",
             "allowed": "BCP Executive Approver", "allow_self_approval": 0},
            {"state": "Manager Review", "action": "Return to Draft", "next_state": "Draft",
             "allowed": "BCP Manager Reviewer", "allow_self_approval": 1},
            {"state": "BCM Review", "action": "Return to Draft", "next_state": "Draft",
             "allowed": "BCM Administrator", "allow_self_approval": 1},
            {"state": "Executive Approval", "action": "Return to Draft", "next_state": "Draft",
             "allowed": "BCP Executive Approver", "allow_self_approval": 1},
            {"state": "Approved", "action": "Retire", "next_state": "Retired",
             "allowed": "BCM Administrator", "allow_self_approval": 1},
        ],
    }).insert(ignore_permissions=True)


def _plan_workflow(doctype: str) -> None:
    workflow_name = f"{doctype} Approval"
    if frappe.db.exists("Workflow", workflow_name):
        return
    frappe.get_doc({
        "doctype": "Workflow", "workflow_name": workflow_name,
        "document_type": doctype, "is_active": 1,
        "workflow_state_field": "approval_status",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": "IT Manager"},
            {"state": "In Review", "doc_status": "0", "allow_edit": "BCM Administrator"},
            {"state": "Approved", "doc_status": "1", "allow_edit": "BCM Administrator"},
            {"state": "Retired", "doc_status": "2", "allow_edit": "BCM Administrator"},
        ],
        "transitions": [
            {"state": "Draft", "action": "Request Review", "next_state": "In Review",
             "allowed": "IT Manager", "allow_self_approval": 1},
            {"state": "In Review", "action": "Return to Draft", "next_state": "Draft",
             "allowed": "BCM Administrator", "allow_self_approval": 1},
            {"state": "In Review", "action": "Approve", "next_state": "Approved",
             "allowed": "BCM Administrator", "allow_self_approval": 0},
            {"state": "Approved", "action": "Retire", "next_state": "Retired",
             "allowed": "BCM Administrator", "allow_self_approval": 1},
        ],
    }).insert(ignore_permissions=True)
