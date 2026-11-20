import frappe
from frappe import _
from frappe.utils import add_days, escape_html, nowdate

from continuity360.schema import ROLES

METRICS = (
    ("Companies", "C360 Company", {}),
    ("Business processes", "C360 Business Process", {}),
    ("Open risks", "C360 Risk", {"status": ["in", ["Open", "Treating"]]}),
    ("Approved plans", "C360 Recovery Plan", {"docstatus": 1}),
    ("Open incidents", "C360 Incident", {"status": ["in", ["Open", "Investigating", "Mitigated"]]}),
    ("Active crises", "C360 Crisis Event", {"status": ["in", ["Declared", "Managing"]]}),
    ("Overdue treatments", "C360 Risk Treatment", {"status": ["!=", "Completed"], "due_date": ["<", "Today"]}),
    ("Plans needing review", "C360 Recovery Plan", {"docstatus": 1, "review_date": ["<", "Today"]}),
)


def _authorize() -> None:
    if frappe.session.user == "Guest" or not set(ROLES).intersection(frappe.get_roles()):
        frappe.throw(_("A Continuity360 role is required."), frappe.PermissionError)


def _count(doctype: str, filters: dict) -> int | None:
    if not frappe.has_permission(doctype, "read"):
        return None
    filters = {key: [v if v != "Today" else nowdate() for v in value] if isinstance(value, list) else value
               for key, value in filters.items()}
    rows = frappe.get_list(doctype, filters=filters, fields=[{"COUNT": "name", "as": "total"}])
    return int(rows[0].total) if rows else 0


@frappe.whitelist()
def overview() -> dict:
    _authorize()
    metrics = [{"label": label, "doctype": doctype, "value": _count(doctype, filters)}
               for label, doctype, filters in METRICS]
    risks, processes, heatmap = [], [], []
    risk_distribution, process_distribution = None, None
    if frappe.has_permission("C360 Risk", "read"):
        risks = frappe.get_list(
            "C360 Risk", fields=["name", "risk_title", "score", "rating", "status"],
            filters={"status": ["in", ["Open", "Treating"]]}, order_by="score desc, modified desc",
            page_length=6,
        )
        heatmap = frappe.get_list(
            "C360 Risk", fields=["likelihood", "impact", {"COUNT": "name", "as": "total"}],
            filters={"status": ["in", ["Open", "Treating"]]}, group_by="likelihood, impact", page_length=25,
        )
        risk_distribution = frappe.get_list(
            "C360 Risk", fields=["rating", {"COUNT": "name", "as": "total"}],
            filters={"status": ["in", ["Open", "Treating"]]}, group_by="rating", page_length=10,
        )
    if frappe.has_permission("C360 Business Process", "read"):
        processes = frappe.get_list(
            "C360 Business Process", fields=["name", "process_name", "criticality", "rto_minutes", "rpo_minutes"],
            order_by="rto_minutes asc, modified desc", page_length=6,
        )
        process_distribution = frappe.get_list(
            "C360 Business Process", fields=["criticality", {"COUNT": "name", "as": "total"}],
            group_by="criticality", page_length=10,
        )
    return {"metrics": metrics, "risks": risks, "processes": processes, "heatmap": heatmap,
            "risk_distribution": risk_distribution, "process_distribution": process_distribution,
            "as_of": nowdate(), "phase": "Phase 1", "simulation_only": True}


@frappe.whitelist()
def bcp_overview() -> dict:
    _authorize()
    doctype = "C360 Business Continuity Plan"
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(_("Your role cannot view business continuity plans."), frappe.PermissionError)
    today = nowdate()
    tested_plans = None
    if frappe.has_permission("C360 BC Exercise", "read"):
        tested_plans = len({row.business_continuity_plan for row in frappe.get_list(
            "C360 BC Exercise",
            filters={"status": "Completed", "actual_date": [">=", add_days(today, -365)],
                     "business_continuity_plan": ["is", "set"]},
            fields=["business_continuity_plan"], page_length=0)})
    return {
        "total": _count(doctype, {}),
        "due_for_review": _count(doctype, {
            "docstatus": 1, "review_date": ["between", [today, add_days(today, 30)]],
        }),
        "under_approval": _count(doctype, {
            "approval_status": ["in", ["Manager Review", "BCM Review", "Executive Approval"]],
        }),
        "overdue_review": _count(doctype, {"docstatus": 1, "review_date": ["<", today]}),
        "tested_plans": tested_plans,
        "exercises_completed": _count("C360 BC Exercise", {
            "status": "Completed", "actual_date": [">=", add_days(today, -365)],
        }),
        "open_corrective_actions": _count("C360 Corrective Action", {
            "status": ["in", ["Open", "In Progress"]],
        }),
        "as_of": today,
    }


@frappe.whitelist()
def department_view(department: str) -> dict:
    _authorize()
    record = frappe.get_doc("C360 Department", department)
    record.check_permission("read")

    def rows(doctype, filters, fields, order_by="modified desc"):
        if not frappe.has_permission(doctype, "read"):
            return None
        return frappe.get_list(doctype, filters=filters, fields=fields,
                               order_by=order_by, page_length=0)

    processes = rows(
        "C360 Business Process", {"department": department},
        ["name", "process_name", "criticality", "rto_minutes", "rpo_minutes", "mtpd_minutes"],
        order_by="rto_minutes asc",
    )
    process_names = [row.name for row in processes or []]
    risks = rows(
        "C360 Risk", {"business_process": ["in", process_names]},
        ["name", "risk_title", "score", "rating", "status"],
        order_by="score desc",
    ) if process_names else ([] if frappe.has_permission("C360 Risk", "read") else None)
    risk_names = [row.name for row in risks or []]

    def linked(doctype, fieldname, names, fields, order_by="modified desc"):
        if not frappe.has_permission(doctype, "read"):
            return None
        if not names:
            return []
        return frappe.get_list(doctype, filters={fieldname: ["in", names]},
                               fields=fields, order_by=order_by, page_length=0)

    bcps = None
    if frappe.has_permission("C360 Business Continuity Plan", "read"):
        bcps = frappe.get_list(
            "C360 Business Continuity Plan",
            filters=[["C360 BCP Department Link", "department", "=", department]],
            fields=["name", "plan_title", "plan_version", "approval_status", "review_date"],
            order_by="modified desc", page_length=0,
        )
    return {
        "department": {
            "name": record.name,
            "department_name": record.department_name,
            "responsible_user": record.responsible_user,
        },
        "processes": processes,
        "impact_assessments": linked(
            "C360 Impact Assessment", "business_process", process_names,
            ["name", "business_process", "overall_impact", "assessment_date"],
        ),
        "risks": risks,
        "risk_assessments": linked(
            "C360 Risk Assessment", "risk", risk_names,
            ["name", "risk", "residual_score", "residual_rating", "assessment_date"],
        ),
        "treatments": linked(
            "C360 Risk Treatment", "risk", risk_names,
            ["name", "treatment_title", "status", "due_date"],
        ),
        "recovery_plans": linked(
            "C360 Recovery Plan", "business_process", process_names,
            ["name", "plan_title", "approval_status", "rto_minutes", "review_date"],
        ),
        "bcps": bcps,
        "employees": rows(
            "C360 Employee", {"department": department},
            ["name", "employee_name", "email", "phone"], order_by="employee_name asc",
        ),
        "as_of": nowdate(),
    }


@frappe.whitelist()
def download_report() -> None:
    data = overview()
    if not set(("BCM Administrator", "Risk Manager", "IT Manager", "Auditor")).intersection(
        frappe.get_roles()
    ):
        frappe.throw(_("Your role cannot export management reports."), frappe.PermissionError)
    from frappe.utils.pdf import get_pdf

    metrics = "".join(
        f"<tr><td>{escape_html(item['label'])}</td><td>{item['value']}</td></tr>"
        for item in data["metrics"] if item["value"] is not None
    )
    risks = "".join(
        f"<tr><td>{escape_html(row.risk_title)}</td><td>{row.score}</td>"
        f"<td>{escape_html(row.rating)}</td></tr>" for row in data["risks"]
    )
    html = (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:sans-serif;color:#142d46;padding:32px}"
        "table{width:100%;border-collapse:collapse;margin:20px 0}"
        "td,th{text-align:left;padding:10px;border-bottom:1px solid #dce3eb}</style></head><body>"
        f"<h1>Continuity360</h1><h2>Management overview</h2><p>As of {data['as_of']}</p>"
        f"<table><tr><th>Measure</th><th>Count</th></tr>{metrics}</table>"
        f"<h2>Highest-scoring open risks (up to 6)</h2><table>"
        f"<tr><th>Risk</th><th>Score</th><th>Rating</th></tr>{risks}</table>"
        "<p>This report reflects records visible to its requesting user. "
        "It is not a certification of compliance or a live infrastructure health assessment.</p></body></html>"
    )
    frappe.local.response.filename = f"continuity360-management-{data['as_of']}.pdf"
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "pdf"
