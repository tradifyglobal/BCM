"""Commercial subscription layer: plans, entitlements, seats and white labelling.

The C360 Subscription single is operator-managed. Tenants read their plan through
``status``; operators set it with::

    bench --site <site> execute continuity360.subscription.set_plan \
        --args '["Professional", 10, "2027-12-31"]'

Sites without a configured plan run with Enterprise development defaults; the
provisioning tooling sets a real plan at tenant creation.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from continuity360 import rules
from continuity360.schema import ROLES

MODULE_LABELS = {
    "foundation": "BCM foundation",
    "incident_crisis": "Incident & Crisis Management",
    "infrastructure": "Infrastructure & Recovery Intelligence",
    "white_label": "White labelling",
    "integrations": "API integrations",
}
GATED_DOCTYPES = {
    "C360 Incident": "incident_crisis",
    "C360 Crisis Event": "incident_crisis",
    "C360 Communication Plan": "incident_crisis",
    "C360 Application": "infrastructure",
    "C360 Server": "infrastructure",
    "C360 Database Instance": "infrastructure",
    "C360 IT Dependency": "infrastructure",
    "C360 Outage Simulation": "infrastructure",
    "C360 Integration Connection": "integrations",
}
# Sites without an operator-configured plan (development) run fully featured.
DEVELOPMENT_DEFAULTS = {"plan": "Enterprise", "licensed_users": 25, "valid_until": None}


def _subscription() -> dict:
    record = frappe.get_single("C360 Subscription")
    if not record.plan:
        return dict(DEVELOPMENT_DEFAULTS)
    return {"plan": record.plan, "licensed_users": record.licensed_users or 1,
            "valid_until": record.valid_until}


def effective() -> dict:
    subscription = _subscription()
    valid_until = subscription["valid_until"]
    plan, modules, expired = rules.plan_entitlements(
        subscription["plan"], getdate(valid_until) if valid_until else None,
        getdate(nowdate()))
    return {"plan": subscription["plan"], "effective_plan": plan, "modules": modules,
            "expired": expired, "valid_until": str(valid_until or ""),
            "licensed_users": subscription["licensed_users"]}


def entitled(module: str) -> bool:
    return module in effective()["modules"]


def _used_seats() -> int:
    return frappe.db.count("User", {
        "enabled": 1, "user_type": "System User",
        "name": ["not in", ["Administrator", "Guest"]],
    })


def enforce_module(doc, method=None) -> None:
    """before_insert hook for plan-gated DocTypes."""
    state = effective()
    module = GATED_DOCTYPES[doc.doctype]
    if module not in state["modules"]:
        reason = (_("The subscription expired on {0} and currently provides Starter "
                    "entitlements.").format(state["valid_until"])
                  if state["expired"] else
                  _("The {0} plan does not include {1}.").format(
                      _(state["plan"]), _(MODULE_LABELS[module])))
        frappe.throw(reason + " " + _("Contact your Continuity360 operator to upgrade."),
                     frappe.PermissionError)


def enforce_seats(doc, method=None) -> None:
    """User validate hook: enabling a system user must stay within licensed seats."""
    if doc.name in ("Administrator", "Guest") or doc.user_type != "System User" \
            or not doc.enabled:
        return
    previous = doc.get_doc_before_save()
    if previous and previous.enabled and previous.user_type == "System User":
        return  # already counted
    used = _used_seats() + (0 if previous and previous.enabled else 1)
    try:
        rules.seat_limit(effective()["licensed_users"], used)
    except ValueError as exc:
        frappe.throw(_(str(exc)), frappe.ValidationError)


def validate_branding(doc, method=None) -> None:
    if not entitled("white_label"):
        frappe.throw(_("White labelling is available on the Enterprise plan. "
                       "Contact your Continuity360 operator to upgrade."),
                     frappe.PermissionError)
    try:
        doc.primary_color = rules.brand_color(doc.primary_color)
    except ValueError as exc:
        frappe.throw(_(str(exc)), frappe.ValidationError)


def branding() -> dict:
    """Applied branding; empty when the plan does not include white labelling."""
    if not entitled("white_label"):
        return {}
    record = frappe.get_single("C360 Branding")
    return {key: value for key, value in (
        ("display_name", (record.display_name or "").strip()),
        ("primary_color", record.primary_color),
        ("report_footer", (record.report_footer or "").strip()),
    ) if value}


@frappe.whitelist()
def status() -> dict:
    if frappe.session.user == "Guest" or not set(ROLES).intersection(frappe.get_roles()):
        frappe.throw(_("A Continuity360 role is required."), frappe.PermissionError)
    state = effective()
    state.update({
        "module_labels": {module: _(MODULE_LABELS[module]) for module in state["modules"]},
        "used_seats": _used_seats(),
        "branding": branding(),
    })
    return state


def set_plan(plan: str, licensed_users: int = 10, valid_until: str | None = None,
             customer_reference: str | None = None) -> dict:
    """Operator entry point (bench execute); not exposed over HTTP."""
    rules.plan_entitlements(plan, None, getdate(nowdate()))  # validates the plan name
    record = frappe.get_single("C360 Subscription")
    record.plan = plan
    record.licensed_users = int(licensed_users)
    record.valid_until = valid_until
    if customer_reference is not None:
        record.customer_reference = customer_reference
    record.save(ignore_permissions=True)
    frappe.db.commit()
    return effective()
