import frappe


def get_context(context):
    context.no_cache = 1
    if frappe.session.user != "Guest":
        frappe.local.flags.redirect_location = "/desk/continuity360"
        raise frappe.Redirect
    redirect_to = frappe.local.request.args.get("redirect-to") or "/desk/continuity360"
    # Only same-site destinations; never an absolute URL from the query string.
    if not redirect_to.startswith("/") or redirect_to.startswith("//"):
        redirect_to = "/desk/continuity360"
    context.redirect_to = redirect_to
    return context
