"""First-run settings for the localhost-only development site."""

import frappe


def initialize() -> None:
    if frappe.local.site != "continuity360.localhost":
        frappe.throw("Development setup is restricted to the local Continuity360 development site.")
    if "erpnext" in frappe.get_installed_apps():
        frappe.throw("Development setup does not support sites with ERPNext installed.")
    if frappe.is_setup_complete():
        # Already configured; a production host_name (public demo) is fine here.
        return
    if frappe.conf.host_name != "http://localhost:18080":
        frappe.throw("First-run development setup only runs with the local development host_name.")

    from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

    # Development defaults only; administrators can change these in System Settings.
    result = setup_complete({
        "language": "English",
        "country": "Canada",
        "timezone": "UTC",
        "currency": "CAD",
        "enable_telemetry": 0,
    })
    if result.get("status") != "ok":
        frappe.throw("Frappe development setup did not complete successfully.")
