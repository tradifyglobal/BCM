"""Public demo-request endpoint for the marketing landing page.

Sends the request through the site's configured outgoing email account. The
recipient defaults to the site config key ``demo_request_recipient``.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, validate_email_address

DEFAULT_RECIPIENT = "zubair@geeksontap.ca"


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=3600)
def submit(email: str, message: str = "") -> dict:
    email = (email or "").strip()
    validate_email_address(email, throw=True)
    message = (message or "").strip()
    if not message:
        frappe.throw(_("Tell us briefly what you would like to see in the demo."))
    if len(message) > 2000:
        frappe.throw(_("Please keep the message under 2000 characters."))
    recipient = frappe.conf.demo_request_recipient or DEFAULT_RECIPIENT
    body = (
        "<h3>Continuity360 demo request</h3>"
        f"<p><b>From:</b> {escape_html(email)}</p>"
        "<p><b>Message:</b></p>"
        f"<p>{escape_html(message).replace(chr(10), '<br>')}</p>"
        "<p style='color:#5c6f84'>Submitted through the public landing page. "
        "Reply directly to reach the requester.</p>"
    )
    frappe.sendmail(
        recipients=[recipient],
        subject=_("Continuity360 demo request from {0}").format(email),
        message=body,
        reply_to=email,
    )
    return {"ok": True}
