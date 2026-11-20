"""API integration framework: provider connections and inventory import.

Connections register AWS/Azure/Microsoft 365/monitoring accounts per tenant with an
encrypted credential slot. Inventory import maps a normalized JSON payload (for
example produced from ``aws ec2 describe-instances`` or ``az vm list``) onto the
infrastructure inventory, so the Recovery Intelligence graph reflects real estates
without a live connection. Live polling is roadmap work and will reuse the stored
credentials.
"""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from continuity360 import subscription

PROVIDER_PLATFORMS = {
    "AWS": {"server": "AWS EC2", "database": "AWS RDS"},
    "Azure": {"server": "Azure Virtual Machine", "database": "Azure Database"},
    "Microsoft 365": {"server": "Other Cloud", "database": "SaaS"},
    "Monitoring": {"server": "Other Cloud", "database": "Other"},
}
KINDS = ("server", "database", "application")


def validate_connection(doc, method=None) -> None:
    # Plan gating happens in subscription.enforce_module on insert.
    if not (doc.account_reference or "").strip():
        frappe.throw(_("Record the account or tenant reference for this connection."))


@frappe.whitelist()
def import_inventory(connection: str, payload: str) -> dict:
    """Upsert inventory records from a normalized JSON payload.

    Payload: list of {"kind": "server"|"database"|"application", "name": str,
    optional "environment", "engine", "operating_system", "criticality",
    "description"}.
    """
    if not subscription.entitled("integrations"):
        frappe.throw(_("API integrations are available on the Enterprise plan."),
                     frappe.PermissionError)
    record = frappe.get_doc("C360 Integration Connection", connection)
    record.check_permission("write")
    if not record.enabled:
        frappe.throw(_("Enable the connection before importing inventory."))
    try:
        rows = json.loads(payload)
        assert isinstance(rows, list)
    except (ValueError, AssertionError):
        frappe.throw(_("The payload must be a JSON list of inventory rows."))
    platforms = PROVIDER_PLATFORMS[record.provider]
    created, updated, skipped = [], [], []
    for row in rows:
        kind = (row.get("kind") or "").lower()
        name = (row.get("name") or "").strip()
        if kind not in KINDS or not name:
            skipped.append(row.get("name") or "?")
            continue
        note = _("Imported from {0} connection {1} on {2}.").format(
            record.provider, record.connection_name, now_datetime().strftime("%Y-%m-%d %H:%M"))
        if kind == "server":
            doctype, fields = "C360 Server", {
                "server_name": name,
                "environment": row.get("environment") or "Production",
                "platform": platforms["server"],
                "operating_system": row.get("operating_system"),
                "description": f"<p>{frappe.utils.escape_html(row.get('description') or note)}</p>",
            }
            match = {"server_name": name}
        elif kind == "database":
            doctype, fields = "C360 Database Instance", {
                "database_name": name,
                "engine": row.get("engine") or "Other",
                "platform": platforms["database"],
                "description": f"<p>{frappe.utils.escape_html(row.get('description') or note)}</p>",
            }
            match = {"database_name": name}
        else:
            doctype, fields = "C360 Application", {
                "application_name": name,
                "criticality": row.get("criticality") or "Medium",
                "hosting": "SaaS" if record.provider == "Microsoft 365" else record.provider,
                "description": f"<p>{frappe.utils.escape_html(row.get('description') or note)}</p>",
            }
            match = {"application_name": name}
        existing = frappe.db.get_value(doctype, {**match, "company": record.company})
        if existing:
            doc = frappe.get_doc(doctype, existing)
            doc.update({key: value for key, value in fields.items() if value})
            doc.save()
            updated.append(name)
        else:
            doc = frappe.get_doc({
                "doctype": doctype, "company": record.company,
                "responsible_user": record.owner
                if frappe.db.get_value("User", record.owner, "enabled")
                else frappe.session.user,
                **{key: value for key, value in fields.items() if value},
            })
            doc.insert()
            created.append(name)
    frappe.db.set_value("C360 Integration Connection", record.name,
                        "last_import", now_datetime())
    frappe.db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}
