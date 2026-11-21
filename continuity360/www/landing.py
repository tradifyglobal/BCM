import frappe


def get_context(context):
    # Signed-in users go straight to the workspace instead of the marketing page.
    if frappe.session.user != "Guest":
        frappe.local.flags.redirect_location = "/desk/continuity360"
        raise frappe.Redirect
    context.no_cache = 1
    return context
