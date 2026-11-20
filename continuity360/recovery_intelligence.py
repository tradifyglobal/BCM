"""IT Infrastructure Recovery Intelligence.

Builds an illustrative outage walkthrough from the inventory: which applications a
failed component takes down, the business processes and departments affected, the
plans and call trees that respond, and the recovery targets involved. This is a
simulation over recorded relationships, not a live infrastructure connection.
"""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from continuity360.schema import ROLES


def _authorize() -> None:
    if frappe.session.user == "Guest" or not set(ROLES).intersection(frappe.get_roles()):
        frappe.throw(_("A Continuity360 role is required."), frappe.PermissionError)


TARGET_DOCTYPES = {
    "Application": "C360 Application",
    "Server": "C360 Server",
    "Database": "C360 Database Instance",
}
TARGET_FIELDS = {
    "Application": "target_application",
    "Server": "target_server",
    "Database": "target_database",
}


def _affected_applications(target_type: str, target: str) -> tuple[list, list]:
    """Directly hit applications plus everything downstream through dependencies."""
    dependencies = frappe.get_list("C360 IT Dependency", page_length=0, fields=[
        "application", "dependency_type", "depends_on_application",
        "depends_on_server", "depends_on_database", "notes"])
    direct = set()
    if target_type == "Application":
        direct.add(target)
    databases = set()
    if target_type == "Server":
        databases = {row.name for row in frappe.get_list(
            "C360 Database Instance", filters={"server": target},
            fields=["name"], page_length=0)}
    if target_type == "Database":
        databases = {target}
    for row in dependencies:
        if target_type == "Server" and row.depends_on_server == target:
            direct.add(row.application)
        if row.depends_on_database in databases:
            direct.add(row.application)
    affected, queue = set(direct), list(direct)
    while queue:
        current = queue.pop()
        for row in dependencies:
            if row.depends_on_application == current and row.application not in affected:
                affected.add(row.application)
                queue.append(row.application)
    chain = [row for row in dependencies
             if row.application in affected or row.depends_on_application in affected
             or (target_type == "Server" and row.depends_on_server == target)
             or row.depends_on_database in databases]
    return sorted(affected), chain


@frappe.whitelist()
def simulate(target_type: str, target: str, save: int | str = 0) -> dict:
    _authorize()
    if target_type not in TARGET_DOCTYPES:
        frappe.throw(_("Choose an application, server or database to simulate."))
    component = frappe.get_doc(TARGET_DOCTYPES[target_type], target)
    component.check_permission("read")
    title_field = {"Application": "application_name", "Server": "server_name",
                   "Database": "database_name"}[target_type]
    component_title = component.get(title_field) or target

    affected_apps, chain = _affected_applications(target_type, target)
    applications = frappe.get_list(
        "C360 Application", filters={"name": ["in", affected_apps or [""]]},
        fields=["name", "application_name", "criticality", "hosting", "recovery_plan"],
        order_by="criticality desc", page_length=0)

    process_names = set()
    for application in applications:
        process_names.update(frappe.get_all(
            "C360 Application Process Link",
            filters={"parent": application.name, "parenttype": "C360 Application"},
            pluck="business_process"))
    processes = frappe.get_list(
        "C360 Business Process", filters={"name": ["in", sorted(process_names) or [""]]},
        fields=["name", "process_name", "department", "criticality",
                "rto_minutes", "rpo_minutes", "mtpd_minutes"],
        order_by="rto_minutes asc", page_length=0)
    departments = {row.department for row in processes if row.department}
    department_titles = {row.name: row.department_name for row in frappe.get_list(
        "C360 Department", fields=["name", "department_name"], page_length=0)}

    recovery_plans = frappe.get_list(
        "C360 Recovery Plan",
        filters={"business_process": ["in", [p.name for p in processes] or [""]]},
        fields=["name", "plan_title", "approval_status", "rto_minutes", "rpo_minutes",
                "business_process"], page_length=0)
    plan_links = {app.recovery_plan for app in applications if app.recovery_plan}
    if plan_links:
        existing = {plan.name for plan in recovery_plans}
        recovery_plans += frappe.get_list(
            "C360 Recovery Plan",
            filters={"name": ["in", sorted(plan_links - existing) or [""]]},
            fields=["name", "plan_title", "approval_status", "rto_minutes", "rpo_minutes",
                    "business_process"], page_length=0)

    covered = set(frappe.get_all(
        "C360 BCP Department Link",
        filters={"department": ["in", sorted(departments) or [""]],
                 "parenttype": "C360 Business Continuity Plan"}, pluck="parent"))
    bcps = frappe.get_list(
        "C360 Business Continuity Plan", filters={"name": ["in", sorted(covered) or [""]]},
        fields=["name", "plan_title", "approval_status", "plan_version"], page_length=0)

    call_trees = [tree for tree in frappe.get_list(
        "C360 Call Tree", filters={"status": "Active"},
        fields=["name", "tree_name", "business_continuity_plan", "department"],
        page_length=0)
        if tree.business_continuity_plan in {plan.name for plan in bcps}
        or tree.department in departments or (not tree.business_continuity_plan
                                              and not tree.department)]

    result = {
        "target": {"type": target_type, "name": target, "title": component_title},
        "simulated_on": str(now_datetime()),
        "illustrative": True,
        "affected_applications": applications,
        "dependency_chain": [{
            "application": row.application, "dependency_type": row.dependency_type,
            "depends_on": row.depends_on_application or row.depends_on_server
            or row.depends_on_database} for row in chain],
        "affected_processes": [dict(row, department_name=department_titles.get(
            row.department, row.department)) for row in processes],
        "affected_departments": sorted(department_titles.get(d, d) for d in departments),
        "recovery_plans": recovery_plans,
        "business_continuity_plans": bcps,
        "call_trees": call_trees,
    }
    if frappe.utils.cint(save):
        record = frappe.get_doc({
            "doctype": "C360 Outage Simulation", "company": component.company,
            "simulation_title": _("{0} outage simulation - {1}").format(
                component_title, now_datetime().strftime("%Y-%m-%d %H:%M")),
            "responsible_user": frappe.session.user,
            "target_type": target_type, TARGET_FIELDS[target_type]: target,
            "simulated_on": now_datetime(),
            "walkthrough": json.dumps(result, indent=1, default=str),
        })
        record.insert()
        frappe.db.commit()
        result["simulation_record"] = record.name
    return result


@frappe.whitelist()
def components() -> dict:
    """Selectable components for the Recovery Intelligence page."""
    _authorize()
    def rows(doctype, title):
        if not frappe.has_permission(doctype, "read"):
            return []
        return frappe.get_list(doctype, fields=["name", f"{title} as title"],
                               order_by=f"{title} asc", page_length=0)
    return {
        "Application": rows("C360 Application", "application_name"),
        "Server": rows("C360 Server", "server_name"),
        "Database": rows("C360 Database Instance", "database_name"),
    }
