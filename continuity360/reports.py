"""Detailed PDF reports. Content is permission-filtered for the requesting user."""

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils import escape_html, get_datetime, now_datetime, nowdate

REPORT_ROLES = ("BCM Administrator", "Risk Manager", "IT Manager", "Auditor",
                "BCP Author", "BCP Manager Reviewer", "BCP Executive Approver")
STYLE = """
body{font-family:'Segoe UI',Arial,'Helvetica Neue','DejaVu Sans',sans-serif;color:#1d2d3e;font-size:9.5pt;line-height:1.45}
h1{font-size:20pt;color:#102d70;margin:0 0 2px}
h2{font-size:13pt;color:#1454a0;margin:22px 0 8px;border-bottom:2px solid #dce5f2;padding-bottom:4px;page-break-after:avoid}
h3{font-size:10.5pt;color:#102d70;margin:16px 0 6px;page-break-after:avoid;
   background:#f1f6fd;border-left:4px solid #245cd1;padding:5px 8px;border-radius:0 4px 4px 0}
.chapter{page-break-before:always}
.chapter-title{font-size:16pt;color:#102d70;margin:6px 0 12px;border-bottom:3px solid #245cd1;padding-bottom:6px}
table{width:100%;border-collapse:collapse;margin:8px 0 14px;table-layout:fixed;font-size:8.5pt}
th{text-align:left;font-size:7.5pt;text-transform:uppercase;letter-spacing:.4px;color:#fff;
   background:#1b3a6b;padding:6px;word-wrap:break-word}
td{padding:6px;border-bottom:1px solid #e3e9f2;vertical-align:top;word-wrap:break-word;overflow-wrap:break-word}
tr:nth-child(even) td{background:#f6f9fd}
.badge{display:inline-block;padding:1.5px 8px;border-radius:9px;font-size:7.5pt;font-weight:bold;white-space:nowrap}
.meta{color:#5c6f84;font-size:9pt;margin:2px 0 14px}
.note{color:#5c6f84;font-size:8pt;margin-top:18px;border-top:1px solid #dce5f2;padding-top:8px}
.kv{margin:4px 0 9px;overflow-wrap:break-word}
.kv b{color:#1454a0}
.detail{page-break-inside:avoid;margin-bottom:6px}
.scope-note{color:#5c6f84;font-style:italic}
.cover{page-break-after:always;padding-top:40px}
.cover-band{height:14px;background:#102d70;margin-bottom:4px}
.cover-band2{height:5px;background:#2f80e6;margin-bottom:46px}
.cover-brand{font-size:30pt;font-weight:bold;color:#102d70;margin-bottom:4px}
.cover-title{font-size:19pt;color:#2f5fb0;font-weight:normal;margin:0 0 24px}
.cover-scope{display:inline-block;background:#eef4fd;border:1px solid #c9dcf7;color:#1b3a6b;
   border-radius:7px;padding:9px 16px;font-size:11pt;font-weight:bold;margin-bottom:32px}
.cover-meta{width:70%;table-layout:auto;font-size:9.5pt}
.cover-meta td{border-bottom:1px solid #dce5f2;padding:8px 6px}
.cover-meta td:first-child{color:#5c6f84;text-transform:uppercase;font-size:7.5pt;letter-spacing:.6px;width:170px}
.cover-history-title{margin-top:24px;color:#5c6f84;text-transform:uppercase;font-size:7.5pt;
   letter-spacing:.6px}
.toc{page-break-after:always;padding-top:30px}
.toc-title{font-size:15pt;color:#102d70;border-bottom:3px solid #245cd1;padding-bottom:6px;margin-bottom:16px}
.toc-item{font-size:11pt;color:#1d2d3e;font-weight:bold;margin:12px 0 4px;
   border-bottom:1px dotted #b9c6d8;padding-bottom:5px}
.toc-item span{display:inline-block;min-width:26px;color:#2f80e6}
.toc-sub{font-size:9.5pt;color:#44566b;margin:3px 0 3px 30px;border-bottom:1px dotted #e0e7f0;padding-bottom:3px}
"""

GRADIENT = ("#2f9e44", "#86b81b", "#f3c300", "#f08c00", "#d9342b")
RATING_COLORS = {"Low": ("#2f9e44", "#fff"), "Medium": ("#f3c300", "#4a3b00"),
                 "High": ("#f08c00", "#fff"), "Critical": ("#d9342b", "#fff")}
STATUS_COLORS = {
    "Open": ("#d9342b", "#fff"), "Treating": ("#f08c00", "#fff"),
    "Accepted": ("#6c7a89", "#fff"), "Closed": ("#2f9e44", "#fff"),
    "Planned": ("#4a6fa5", "#fff"), "In Progress": ("#f08c00", "#fff"),
    "Completed": ("#2f9e44", "#fff"),
    "Draft": ("#6c7a89", "#fff"), "In Review": ("#f3c300", "#4a3b00"),
    "Manager Review": ("#f3c300", "#4a3b00"), "BCM Review": ("#f3c300", "#4a3b00"),
    "Executive Approval": ("#f08c00", "#fff"), "Approved": ("#2f9e44", "#fff"),
    "Retired": ("#6c7a89", "#fff"),
    "Implemented": ("#2f9e44", "#fff"), "Not Assessed": ("#6c7a89", "#fff"),
    "Not Applicable": ("#9aa7b5", "#fff"),
    "Cancelled": ("#9aa7b5", "#fff"),
    "Effective": ("#2f9e44", "#fff"),
    "Effective With Observations": ("#f3c300", "#4a3b00"),
    "Needs Improvement": ("#f08c00", "#fff"), "Ineffective": ("#d9342b", "#fff"),
    "Met": ("#2f9e44", "#fff"), "Partially Met": ("#f3c300", "#4a3b00"),
    "Not Met": ("#d9342b", "#fff"),
}


class _Raw(str):
    """Pre-rendered, already-escaped table cell content."""


def _badge(label, background: str, color: str = "#fff") -> _Raw:
    return _Raw(f"<span class='badge' style='background:{background};color:{color}'>"
                f"{escape_html(str(label))}</span>")


def _rating_badge(rating):
    if not rating:
        return ""
    background, color = RATING_COLORS.get(rating, ("#6c7a89", "#fff"))
    return _badge(rating, background, color)


def _status_badge(status):
    if not status:
        return ""
    background, color = STATUS_COLORS.get(status, ("#6c7a89", "#fff"))
    return _badge(status, background, color)


def _level_badge(value):
    if value in (None, ""):
        return ""
    level = max(1, min(5, int(value)))
    background = GRADIENT[level - 1]
    color = "#4a3b00" if level == 3 else "#fff"
    return _badge(value, background, color)


def _score_badge(score, rating):
    if score in (None, ""):
        return ""
    background, color = RATING_COLORS.get(rating, ("#6c7a89", "#fff"))
    return _badge(score, background, color)


def _target_badge(minutes):
    """Duration chips match the form pickers: short targets green, long targets red."""
    if minutes in (None, ""):
        return ""
    amount = int(minutes)
    if amount <= 60:
        background, color = GRADIENT[0], "#fff"
    elif amount <= 240:
        background, color = GRADIENT[1], "#fff"
    elif amount <= 480:
        background, color = GRADIENT[2], "#4a3b00"
    elif amount <= 1440:
        background, color = GRADIENT[3], "#fff"
    else:
        background, color = GRADIENT[4], "#fff"
    return _badge(_minutes(amount), background, color)


def _authorize() -> None:
    if frappe.session.user == "Guest" or not set(REPORT_ROLES).intersection(frappe.get_roles()):
        frappe.throw(_("Your role cannot export reports."), frappe.PermissionError)


def _scope(department: str | None) -> str:
    if not department:
        return _("All departments")
    record = frappe.get_doc("C360 Department", department)
    record.check_permission("read")
    return record.department_name or department


def _brand() -> str:
    """The customer's company name brands the report; one visible company is the tenant norm."""
    companies = _rows("C360 Company", fields=["company_name"]) or []
    if len(companies) == 1 and companies[0].company_name:
        return companies[0].company_name
    return "Continuity360"


def _rows(doctype, **kwargs):
    if not frappe.has_permission(doctype, "read"):
        return None
    return frappe.get_list(doctype, page_length=0, **kwargs)


def _docs(doctype, filters=None, order_by="modified desc"):
    rows = _rows(doctype, filters=filters, fields=["name"], order_by=order_by)
    if rows is None:
        return None
    return [frappe.get_doc(doctype, row.name) for row in rows]


def _department_processes(department: str | None):
    """Process names limiting a department-scoped report; None means unscoped."""
    if not department:
        return None
    rows = _rows("C360 Business Process", filters={"department": department}, fields=["name"])
    if rows is None:
        frappe.throw(_("Department filtering requires access to business processes."),
                     frappe.PermissionError)
    return [row.name for row in rows]


def _text(value) -> str:
    return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)


def _user(account) -> str:
    """Display name for a user account; falls back to the account id."""
    if not account:
        return ""
    names = getattr(frappe.local, "_c360_user_names", None)
    if names is None:
        names = {row.name: (row.full_name or row.name)
                 for row in frappe.get_all("User", fields=["name", "full_name"])}
        frappe.local._c360_user_names = names
    return names.get(account, account)


def _when(value) -> str:
    if not value:
        return ""
    return get_datetime(value).strftime("%d %B %Y, %H:%M")


def _record_issue(slug: str, title: str, department: str | None):
    """Log this generation and return the issue version plus recent history."""
    history = frappe.get_all(
        "C360 Report Issue",
        filters={"report": slug, "department": department or ("is", "not set")},
        fields=["version", "generated_by", "generated_on"],
        order_by="version desc", limit_page_length=5)
    version = (history[0].version + 1) if history else 1
    frappe.get_doc({
        "doctype": "C360 Report Issue", "report": slug, "report_title": title,
        "department": department, "version": version,
        "generated_by": frappe.session.user, "generated_on": now_datetime(),
    }).insert(ignore_permissions=True)
    # Report downloads are GET requests, which Frappe does not auto-commit.
    frappe.db.commit()
    return version, history


def _minutes(value) -> str:
    if value in (None, ""):
        return ""
    amount = int(value)
    if amount == 0:
        return _("None (zero data loss)")
    if amount % 1440 == 0:
        return _("{0} day(s)").format(amount // 1440)
    if amount % 60 == 0:
        return _("{0} hour(s)").format(amount // 60)
    return _("{0} minute(s)").format(amount)


def _titles(doctype, title_field):
    rows = _rows(doctype, fields=["name", title_field]) or []
    return {row.name: row.get(title_field) or row.name for row in rows}


def _table(headers, rows) -> str:
    if not rows:
        return "<p>" + escape_html(_("No records visible to you.")) + "</p>"
    head = "".join(f"<th>{escape_html(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{cell if isinstance(cell, _Raw) else escape_html(str(cell if cell is not None else ''))}</td>"
            for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def _kv(pairs) -> str:
    return "".join(
        f"<div class='kv'><b>{escape_html(label)}:</b> {escape_html(str(value))}</div>"
        for label, value in pairs if value not in (None, "")
    )


def _serve(slug: str, title: str, scope: str, body: str, contents=(),
           department: str | None = None) -> None:
    from frappe.utils.pdf import get_pdf

    brand = _brand()
    version, history = _record_issue(slug, title, department)
    toc = ""
    if contents:
        entries = ""
        for number, (label, subsections) in enumerate(contents, 1):
            entries += (f"<div class='toc-item'><span>{number}.</span>"
                        f"{escape_html(label)}</div>")
            for subsection in subsections:
                entries += f"<div class='toc-sub'>{escape_html(subsection)}</div>"
        toc = (f"<div class='toc'><div class='toc-title'>{escape_html(_('Table of Contents'))}</div>"
               f"{entries}</div>")
    preparer = f"{_user(frappe.session.user)} ({frappe.session.user})"
    history_rows = [[_("Version {0}").format(version), _when(now_datetime()),
                     _user(frappe.session.user), _Raw("<b>" + escape_html(_("This issue")) + "</b>")]]
    history_rows += [[_("Version {0}").format(row.version), _when(row.generated_on),
                      _user(row.generated_by), ""] for row in history]
    cover = (
        "<div class='cover'>"
        "<div class='cover-band'></div><div class='cover-band2'></div>"
        f"<div class='cover-brand'>{escape_html(brand)}</div>"
        f"<h1 class='cover-title'>{escape_html(title)}</h1><br>"
        f"<span class='cover-scope'>{escape_html(_('Scope: {0}').format(scope))}</span>"
        "<table class='cover-meta'>"
        f"<tr><td>{escape_html(_('Document version'))}</td>"
        f"<td>{escape_html(_('Version {0}').format(version))}</td></tr>"
        f"<tr><td>{escape_html(_('Prepared for'))}</td><td>{escape_html(brand)}</td></tr>"
        f"<tr><td>{escape_html(_('Prepared by'))}</td><td>{escape_html(preparer)}</td></tr>"
        f"<tr><td>{escape_html(_('Generated on'))}</td><td>{escape_html(_when(now_datetime()))}</td></tr>"
        f"<tr><td>{escape_html(_('Classification'))}</td>"
        f"<td>{escape_html(_('Internal - uncontrolled when printed or downloaded'))}</td></tr>"
        f"<tr><td>{escape_html(_('Produced by'))}</td><td>Continuity360</td></tr>"
        "</table>"
        f"<div class='cover-history-title'>{escape_html(_('Document history'))}</div>"
        + _table([_("Version"), _("Issued on"), _("Prepared by"), ""], history_rows)
        + "</div>"
    )
    html = (
        "<html><head><meta charset='utf-8'><style>" + STYLE + "</style></head><body>"
        + cover + toc + body +
        "<p class='note'>" + escape_html(_(
            "Generated by Continuity360 for {0}. This report reflects records visible to the "
            "requesting user at generation time. It is an uncontrolled copy, not a certification "
            "of compliance.").format(brand)) + "</p></body></html>"
    )
    options = {
        "header-left": f"{brand} - {title}",
        "header-right": _("Department: {0}").format(scope),
        "header-font-size": "7",
        "header-spacing": "4",
        "footer-left": _("{0} | Version {1}").format(nowdate(), version),
        "footer-right": _("Page [page] of [topage]"),
        "footer-font-size": "7",
        "footer-spacing": "4",
        "margin-top": "20mm",
        "margin-bottom": "18mm",
        "margin-left": "12mm",
        "margin-right": "12mm",
    }
    frappe.local.response.filename = f"continuity360-{slug}-{nowdate()}.pdf"
    frappe.local.response.filecontent = get_pdf(html, options=options)
    frappe.local.response.type = "pdf"


def _bia_body(department: str | None) -> str:
    departments = _titles("C360 Department", "department_name")
    filters = {"department": department} if department else {}
    processes = _docs("C360 Business Process", filters=filters, order_by="rto_minutes asc")
    if processes is None:
        frappe.throw(_("Your role cannot view business processes."), frappe.PermissionError)
    counts: dict[str, int] = {}
    for process in processes:
        counts[process.criticality] = counts.get(process.criticality, 0) + 1
    body = "<h2>" + escape_html(_("Summary")) + "</h2>" + _table(
        [_("Criticality"), _("Processes")],
        [[_rating_badge(criticality), total] for criticality, total in sorted(counts.items())])
    body += "<h2>" + escape_html(_("Business processes and recovery targets")) + "</h2>" + _table(
        [_("Process"), _("Department"), _("Criticality"), _("RTO"), _("RPO"), _("MTPD"), _("Owner")],
        [[p.process_name, departments.get(p.department, p.department), _rating_badge(p.criticality),
          _target_badge(p.rto_minutes), _target_badge(p.rpo_minutes), _target_badge(p.mtpd_minutes),
          _user(p.responsible_user)] for p in processes])
    assessments = _rows("C360 Impact Assessment", filters={
        "business_process": ["in", [p.name for p in processes] or [""]],
    }, fields=["business_process", "assessment_date", "financial_impact", "operational_impact",
               "reputational_impact", "regulatory_impact", "overall_impact",
               "disruption_scenario", "impact_over_time"], order_by="assessment_date desc")
    by_process: dict[str, list] = {}
    for row in assessments or []:
        by_process.setdefault(row.business_process, []).append(row)
    body += "<h2>" + escape_html(_("Process details and impact analysis")) + "</h2>"
    for process in processes:
        body += f"<div class='detail'><h3>{escape_html(process.process_name)}</h3>"
        body += _kv([
            (_("Department"), departments.get(process.department, process.department)),
            (_("Process owner"), _user(process.responsible_user)),
            (_("Entered by"), _user(process.owner)),
            (_("Last updated by"), _("{0} on {1}").format(_user(process.modified_by),
                                                          _when(process.modified))),
            (_("Description"), _text(process.description)),
            (_("Manual workaround"), _text(process.manual_workaround)),
        ])
        rows = by_process.get(process.name, [])
        if rows:
            body += _table(
                [_("Date"), _("Financial"), _("Operational"), _("Reputational"),
                 _("Regulatory"), _("Highest"), _("Disruption scenario"), _("Impact over time")],
                [[r.assessment_date, _level_badge(r.financial_impact), _level_badge(r.operational_impact),
                  _level_badge(r.reputational_impact), _level_badge(r.regulatory_impact),
                  _level_badge(r.overall_impact),
                  _text(r.disruption_scenario), _text(r.impact_over_time)] for r in rows])
        elif assessments is None:
            body += "<p>" + escape_html(_("Impact assessments are not visible to your role.")) + "</p>"
        else:
            body += "<p>" + escape_html(_("No impact assessment recorded yet.")) + "</p>"
        body += "</div>"
    return body


def _risk_body(department: str | None) -> str:
    processes = _titles("C360 Business Process", "process_name")
    scope_processes = _department_processes(department)
    filters = {"business_process": ["in", scope_processes or [""]]} if department else {}
    risks = _docs("C360 Risk", filters=filters, order_by="score desc")
    if risks is None:
        frappe.throw(_("Your role cannot view risks."), frappe.PermissionError)
    body = ""
    if department:
        body += "<p>" + escape_html(_(
            "Scoped to risks linked to this department's business processes; "
            "risks without a linked process are excluded.")) + "</p>"
    ratings: dict[tuple, int] = {}
    for risk in risks:
        key = (risk.rating, risk.status)
        ratings[key] = ratings.get(key, 0) + 1
    body += "<h2>" + escape_html(_("Summary by rating and status")) + "</h2>" + _table(
        [_("Rating"), _("Status"), _("Risks")],
        [[_rating_badge(rating), _status_badge(status), total]
         for (rating, status), total in sorted(ratings.items())])
    body += "<h2>" + escape_html(_("Risk register")) + "</h2>" + _table(
        [_("Risk"), _("Category"), _("Process"), _("Likelihood"), _("Impact"),
         _("Score"), _("Rating"), _("Status"), _("Owner")],
        [[r.risk_title, r.category, processes.get(r.business_process, r.business_process or ""),
          _level_badge(r.likelihood), _level_badge(r.impact), _score_badge(r.score, r.rating),
          _rating_badge(r.rating), _status_badge(r.status), _user(r.responsible_user)] for r in risks])
    names = [r.name for r in risks] or [""]
    assessments = _rows("C360 Risk Assessment", filters={"risk": ["in", names]},
                        fields=["risk", "assessment_date", "residual_likelihood", "residual_impact",
                                "residual_score", "residual_rating", "rationale"])
    treatments = _rows("C360 Risk Treatment", filters={"risk": ["in", names]},
                       fields=["risk", "treatment_title", "strategy", "status", "start_date",
                               "due_date", "actions", "completion_evidence"])
    assessed = {row.risk: row for row in assessments or []}
    treated: dict[str, list] = {}
    for row in treatments or []:
        treated.setdefault(row.risk, []).append(row)
    body += "<h2>" + escape_html(_("Risk details, residual assessments and treatments")) + "</h2>"
    for risk in risks:
        body += f"<div class='detail'><h3>{escape_html(risk.risk_title)}</h3>"
        body += _kv([
            (_("Description"), _text(risk.description)),
            (_("Risk owner"), _user(risk.responsible_user)),
            (_("Entered by"), _user(risk.owner)),
            (_("Last updated by"), _("{0} on {1}").format(_user(risk.modified_by),
                                                          _when(risk.modified))),
            (_("Inherent"), _("Likelihood {0} x Impact {1} = {2} ({3})").format(
                risk.likelihood, risk.impact, risk.score, risk.rating)),
            (_("Status"), risk.status),
            (_("Acceptance / closure justification"), _text(risk.acceptance_reason)),
        ])
        residual = assessed.get(risk.name)
        if residual:
            body += _kv([(_("Residual assessment ({0})").format(residual.assessment_date),
                          _("Likelihood {0} x Impact {1} = {2} ({3}). {4}").format(
                              residual.residual_likelihood, residual.residual_impact,
                              residual.residual_score, residual.residual_rating,
                              _text(residual.rationale)))])
        rows = treated.get(risk.name, [])
        if rows:
            body += _table(
                [_("Treatment"), _("Strategy"), _("Status"), _("Start"), _("Due"),
                 _("Actions"), _("Completion evidence")],
                [[t.treatment_title, t.strategy, _status_badge(t.status), t.start_date, t.due_date,
                  _text(t.actions), _text(t.completion_evidence)] for t in rows])
        body += "</div>"
    return body


def _bcp_body(department: str | None) -> str:
    departments = _titles("C360 Department", "department_name")
    team_names = _titles("C360 BCP Recovery Team", "team_name")
    strategy_names = _titles("C360 Continuity Strategy", "strategy_name")
    procedure_names = _titles("C360 BCP Procedure", "procedure_name")
    recovery_names = _titles("C360 Recovery Plan", "plan_title")
    filters = ([["C360 BCP Department Link", "department", "=", department]]
               if department else None)
    plans = _docs("C360 Business Continuity Plan", filters=filters, order_by="plan_title asc")
    if plans is None:
        frappe.throw(_("Your role cannot view business continuity plans."), frappe.PermissionError)
    body = ""
    if department:
        body += "<p>" + escape_html(_(
            "Scoped to plans whose covered business units include this department.")) + "</p>"
    body += "<h2>" + escape_html(_("Plan register")) + "</h2>" + _table(
        [_("Plan"), _("Version"), _("Status"), _("Owner"), _("Next review"), _("Approved by")],
        [[p.plan_title, p.plan_version, _status_badge(p.approval_status), _user(p.responsible_user),
          p.review_date, _user(p.approved_by)] for p in plans])
    body += "<h2>" + escape_html(_("Document control and approvals")) + "</h2>" + _table(
        [_("Plan"), _("Version"), _("Prepared by"), _("Manager reviewer"), _("BCM reviewer"),
         _("Executive approver"), _("Approved by"), _("Approved on")],
        [[p.plan_title, p.plan_version, _user(p.responsible_user), _user(p.manager_reviewer),
          _user(p.bcm_reviewer), _user(p.executive_approver), _user(p.approved_by),
          _when(p.approved_on)] for p in plans])
    include_distributions = frappe.has_permission("C360 BCP Distribution", "read")
    body += "<h2>" + escape_html(_("Plan details")) + "</h2>"
    for plan in plans:
        body += (f"<div class='detail'><h3>{escape_html(plan.plan_title)} "
                 f"(v{escape_html(plan.plan_version or _('unnumbered'))} - "
                 f"{escape_html(plan.approval_status)})</h3>")
        body += _kv([
            (_("Purpose and scope"), _text(plan.scope)),
            (_("Activation criteria"), _text(plan.activation_criteria)),
            (_("Continuity procedures"), _text(plan.continuity_procedures)),
            (_("Communication procedures"), _text(plan.communication_procedures)),
            (_("Business units covered"), ", ".join(
                departments.get(row.department, row.department) for row in plan.business_units)),
            (_("Continuity strategies"), ", ".join(
                strategy_names.get(row.strategy, row.strategy) for row in plan.strategies)),
            (_("Recovery teams"), ", ".join(
                team_names.get(row.team, row.team) for row in plan.teams)),
            (_("Detailed procedures"), ", ".join(
                procedure_names.get(row.procedure, row.procedure) for row in plan.procedures)),
            (_("Linked recovery plans"), ", ".join(
                recovery_names.get(row.recovery_plan, row.recovery_plan)
                for row in plan.recovery_plans)),
            (_("Prepared by"), _user(plan.responsible_user)),
            (_("Reviewers"), _("Manager {0}; BCM {1}; Executive {2}").format(
                _user(plan.manager_reviewer), _user(plan.bcm_reviewer),
                _user(plan.executive_approver))),
            (_("Approved"), _("{0} on {1}").format(_user(plan.approved_by),
                                                   _when(plan.approved_on))
             if plan.approved_by else ""),
            (_("Next review"), plan.review_date),
        ])
        if plan.contacts:
            body += _table([_("Contact"), _("Responsibility"), _("Email"), _("Phone")],
                           [[c.contact_name, c.role, c.email, c.phone] for c in plan.contacts])
        if include_distributions:
            plan_distributions = set(frappe.get_all(
                "C360 BCP Distribution", filters={"plan": plan.name}, pluck="name"))
            recipients = [r for r in frappe.get_all(
                "C360 BCP Distribution Recipient",
                filters={"parenttype": "C360 BCP Distribution"},
                fields=["parent", "recipient_name", "recipient", "first_opened_on",
                        "open_count", "acknowledged_on"]) if r.parent in plan_distributions]
            if recipients:
                body += "<h3>" + escape_html(_("Distribution and acknowledgement")) + "</h3>"
                body += _table(
                    [_("Recipient"), _("Account"), _("First opened"), _("Opens"), _("Acknowledged")],
                    [[r.recipient_name, r.recipient, r.first_opened_on or _("Never"),
                      r.open_count,
                      _badge(r.acknowledged_on, "#2f9e44") if r.acknowledged_on
                      else _badge(_("Not acknowledged"), "#d9342b")] for r in recipients])
        body += "</div>"
    return body


def _dr_body(department: str | None) -> str:
    processes = _titles("C360 Business Process", "process_name")
    strategies = _titles("C360 Recovery Strategy", "strategy_name")
    scope_processes = _department_processes(department)
    filters = {"business_process": ["in", scope_processes or [""]]} if department else None
    plans = _docs("C360 Recovery Plan", filters=filters, order_by="plan_title asc")
    if plans is None:
        frappe.throw(_("Your role cannot view recovery plans."), frappe.PermissionError)
    body = ""
    if department:
        body += "<p>" + escape_html(_(
            "Scoped to recovery plans for this department's business processes.")) + "</p>"
    body += "<h2>" + escape_html(_("Recovery plan register")) + "</h2>" + _table(
        [_("Plan"), _("Business process"), _("Strategy"), _("Status"), _("RTO"), _("RPO"),
         _("Next review")],
        [[p.plan_title, processes.get(p.business_process, p.business_process),
          strategies.get(p.strategy, p.strategy), _status_badge(p.approval_status),
          _target_badge(p.rto_minutes), _target_badge(p.rpo_minutes), p.review_date] for p in plans])
    body += "<h2>" + escape_html(_("Document control and approvals")) + "</h2>" + _table(
        [_("Plan"), _("Prepared by"), _("Status"), _("Approved by"), _("Approved on"),
         _("Last updated")],
        [[p.plan_title, _user(p.responsible_user), _status_badge(p.approval_status),
          _user(p.approved_by), _when(p.approved_on), _when(p.modified)] for p in plans])
    body += "<h2>" + escape_html(_("Recovery procedures")) + "</h2>"
    for plan in plans:
        body += (f"<div class='detail'><h3>{escape_html(plan.plan_title)} "
                 f"({escape_html(plan.approval_status)})</h3>")
        body += _kv([
            (_("Purpose and scope"), _text(plan.scope)),
            (_("Activation criteria"), _text(plan.activation_criteria)),
            (_("Targets"), _("RTO {0}; RPO {1}").format(
                _minutes(plan.rto_minutes), _minutes(plan.rpo_minutes))),
            (_("Prepared by"), _user(plan.responsible_user)),
            (_("Approved"), _("{0} on {1}").format(_user(plan.approved_by),
                                                   _when(plan.approved_on))
             if plan.approved_by else ""),
        ])
        if plan.contacts:
            body += _table([_("Contact"), _("Responsibility"), _("Email"), _("Phone")],
                           [[c.contact_name, c.role, c.email, c.phone] for c in plan.contacts])
        body += _table(
            [_("Step"), _("Instruction"), _("Responsible"), _("Expected minutes"),
             _("Validation criteria")],
            [[index, _text(step.instruction), _user(step.responsible_user), step.expected_minutes,
              _text(step.validation)] for index, step in enumerate(plan.steps, 1)])
        body += "</div>"
    return body


def _testing_body(department: str | None) -> str:
    exercises = _docs("C360 BC Exercise", order_by="scheduled_date desc")
    if exercises is None:
        frappe.throw(_("Your role cannot view exercises."), frappe.PermissionError)
    bcp_titles = _titles("C360 Business Continuity Plan", "plan_title")
    recovery_titles = _titles("C360 Recovery Plan", "plan_title")
    body = ""
    if department:
        scope_processes = _department_processes(department)
        recovery_rows = _rows("C360 Recovery Plan", fields=["name"], filters={
            "business_process": ["in", scope_processes or [""]]}) or []
        scoped_recovery = {row.name for row in recovery_rows}
        scoped_bcps = set(frappe.get_all(
            "C360 BCP Department Link", pluck="parent",
            filters={"department": department, "parenttype": "C360 Business Continuity Plan"}))
        exercises = [e for e in exercises if e.business_continuity_plan in scoped_bcps
                     or e.recovery_plan in scoped_recovery]
        body += "<p>" + escape_html(_(
            "Scoped to exercises whose plan covers this department or recovers one of its "
            "business processes; exercises without a linked plan are excluded.")) + "</p>"
    counts: dict[tuple, int] = {}
    for exercise in exercises:
        key = (exercise.exercise_type, exercise.status)
        counts[key] = counts.get(key, 0) + 1
    body += "<h2>" + escape_html(_("Exercise summary")) + "</h2>" + _table(
        [_("Exercise type"), _("Status"), _("Exercises")],
        [[kind, _status_badge(status), total] for (kind, status), total in sorted(counts.items())])
    body += "<h2>" + escape_html(_("Exercise register")) + "</h2>" + _table(
        [_("Exercise"), _("Type"), _("Status"), _("Scheduled"), _("Conducted"), _("Result"),
         _("Facilitator")],
        [[e.exercise_name, e.exercise_type, _status_badge(e.status), e.scheduled_date,
          e.actual_date or "", _status_badge(e.result), _user(e.responsible_user)]
         for e in exercises])
    actions = _rows("C360 Corrective Action", filters={
        "exercise": ["in", [e.name for e in exercises] or [""]],
    }, fields=["exercise", "action_title", "priority", "status", "responsible_user", "due_date",
               "completed_on", "completion_evidence", "description"], order_by="due_date asc")
    by_exercise: dict[str, list] = {}
    for row in actions or []:
        by_exercise.setdefault(row.exercise, []).append(row)
    body += "<h2>" + escape_html(_("Exercise details and outcomes")) + "</h2>"
    for exercise in exercises:
        body += f"<div class='detail'><h3>{escape_html(exercise.exercise_name)}</h3>"
        body += _kv([
            (_("Type"), exercise.exercise_type),
            (_("Status"), exercise.status),
            (_("Scenario"), _text(exercise.scenario)),
            (_("Business continuity plan"), bcp_titles.get(
                exercise.business_continuity_plan, exercise.business_continuity_plan or "")),
            (_("Recovery plan"), recovery_titles.get(
                exercise.recovery_plan, exercise.recovery_plan or "")),
            (_("Facilitator"), _user(exercise.responsible_user)),
            (_("Conducted on"), exercise.actual_date),
            (_("Achieved recovery time"), _minutes(exercise.achieved_rto_minutes)),
            (_("Results summary"), _text(exercise.summary)),
            (_("Lessons learned"), _text(exercise.lessons_learned)),
            (_("Entered by"), _user(exercise.owner)),
            (_("Last updated by"), _("{0} on {1}").format(_user(exercise.modified_by),
                                                          _when(exercise.modified))),
        ])
        if exercise.objectives:
            body += _table([_("Objective"), _("Outcome"), _("Notes")],
                           [[_text(o.objective), _status_badge(o.outcome), _text(o.notes)]
                            for o in exercise.objectives])
        if exercise.participants:
            body += _table([_("Participant"), _("Role in exercise"), _("Attended")],
                           [[_user(p.participant), p.exercise_role,
                             _badge(_("Yes"), "#2f9e44") if p.attended
                             else _badge(_("No"), "#d9342b")] for p in exercise.participants])
        rows = by_exercise.get(exercise.name, [])
        if rows:
            body += "<h3>" + escape_html(_("Corrective actions")) + "</h3>"
            body += _table(
                [_("Action"), _("Priority"), _("Status"), _("Owner"), _("Due"), _("Completed"),
                 _("What must change"), _("Completion evidence")],
                [[a.action_title, _rating_badge(a.priority), _status_badge(a.status),
                  _user(a.responsible_user), a.due_date, a.completed_on or "",
                  _text(a.description), _text(a.completion_evidence)] for a in rows])
        elif actions is None:
            body += "<p>" + escape_html(_("Corrective actions are not visible to your role.")) + "</p>"
        body += "</div>"
    if not exercises:
        body += "<p>" + escape_html(_("No exercises recorded in this scope yet.")) + "</p>"
    return body


def _compliance_body(department: str | None) -> str:
    controls = _docs("C360 Compliance Control", order_by="framework asc, control_reference asc")
    if controls is None:
        frappe.throw(_("Your role cannot view compliance controls."), frappe.PermissionError)
    body = ""
    if department:
        body += "<p>" + escape_html(_(
            "Compliance controls are organisation-wide; the department selection does not "
            "restrict this section.")) + "</p>"
    counts: dict[str, int] = {}
    for control in controls:
        counts[control.status] = counts.get(control.status, 0) + 1
    body += "<h2>" + escape_html(_("Self-assessed status summary")) + "</h2>" + _table(
        [_("Status"), _("Controls")],
        [[_status_badge(status), total] for status, total in sorted(counts.items())])
    frameworks: dict[str, list] = {}
    for control in controls:
        frameworks.setdefault(control.framework, []).append(control)
    for framework, rows in frameworks.items():
        body += f"<h2>{escape_html(framework)}</h2>" + _table(
            [_("Reference"), _("Control"), _("Status"), _("Owner"), _("Evidence"),
             _("Next review"), _("Description")],
            [[c.control_reference, c.control_title, _status_badge(c.status), _user(c.responsible_user),
              _text(c.evidence_reference), c.review_date, _text(c.description)] for c in rows])
    body += "<p>" + escape_html(_(
        "Framework references and status are entered and self-assessed by the organisation; "
        "no standards content is supplied by Continuity360.")) + "</p>"
    return body


BIA_CONTENTS = (
    (_("Summary"), ()),
    (_("Business processes and recovery targets"), ()),
    (_("Process details and impact analysis"), ()),
)
RISK_CONTENTS = (
    (_("Summary by rating and status"), ()),
    (_("Risk register"), ()),
    (_("Risk details, residual assessments and treatments"), ()),
)
BCP_CONTENTS = (
    (_("Plan register"), ()),
    (_("Document control and approvals"), ()),
    (_("Plan details"), (_("Scope, strategies, teams and procedures"),
                         _("Distribution and acknowledgement"))),
)
DR_CONTENTS = (
    (_("Recovery plan register"), ()),
    (_("Document control and approvals"), ()),
    (_("Recovery procedures"), (_("Contacts and step-by-step instructions"),)),
)
TESTING_CONTENTS = (
    (_("Exercise summary"), ()),
    (_("Exercise register"), ()),
    (_("Exercise details and outcomes"), (_("Objectives, participants and corrective actions"),)),
)
COMPLIANCE_CONTENTS = (
    (_("Self-assessed status summary"), ()),
    (_("Controls by framework"), ()),
)


@frappe.whitelist()
def bia_report(department: str | None = None) -> None:
    _authorize()
    scope = _scope(department)
    _serve("bia-report", _("Business Impact Analysis Report"), scope, _bia_body(department),
           BIA_CONTENTS, department)


@frappe.whitelist()
def risk_report(department: str | None = None) -> None:
    _authorize()
    scope = _scope(department)
    _serve("risk-report", _("Risk Assessment Report"), scope, _risk_body(department),
           RISK_CONTENTS, department)


@frappe.whitelist()
def bcp_report(department: str | None = None) -> None:
    _authorize()
    scope = _scope(department)
    _serve("bcp-report", _("Business Continuity Plan Report"), scope, _bcp_body(department),
           BCP_CONTENTS, department)


@frappe.whitelist()
def dr_report(department: str | None = None) -> None:
    _authorize()
    scope = _scope(department)
    _serve("dr-report", _("Disaster Recovery Report"), scope, _dr_body(department), DR_CONTENTS,
           department)


@frappe.whitelist()
def testing_report(department: str | None = None) -> None:
    _authorize()
    scope = _scope(department)
    _serve("testing-report", _("Testing and Exercise Report"), scope, _testing_body(department),
           TESTING_CONTENTS, department)


@frappe.whitelist()
def compliance_report(department: str | None = None) -> None:
    _authorize()
    scope = _scope(department)
    _serve("compliance-report", _("Compliance Control Report"), scope,
           _compliance_body(department), COMPLIANCE_CONTENTS, department)


@frappe.whitelist()
def full_report(department: str | None = None) -> None:
    _authorize()
    scope = _scope(department)
    chapters = (
        (_("Business Impact Analysis"), _bia_body, BIA_CONTENTS),
        (_("Risk Assessment"), _risk_body, RISK_CONTENTS),
        (_("Business Continuity Plans"), _bcp_body, BCP_CONTENTS),
        (_("Disaster Recovery"), _dr_body, DR_CONTENTS),
        (_("Testing and Exercises"), _testing_body, TESTING_CONTENTS),
        (_("Compliance Controls"), _compliance_body, COMPLIANCE_CONTENTS),
    )
    body = ""
    contents = []
    for index, (label, build, chapter_contents) in enumerate(chapters):
        contents.append((label, tuple(entry for entry, _subs in chapter_contents)))
        try:
            chapter = build(department)
        except frappe.PermissionError:
            chapter = "<p>" + escape_html(_("This section is not visible to your role.")) + "</p>"
        wrapper = " class='chapter'" if index else ""
        body += (f"<div{wrapper}><h1 class='chapter-title'>{index + 1}. {escape_html(label)}</h1>"
                 f"{chapter}</div>")
    _serve("bcm-report", _("Business Continuity Management Report"), scope, body, contents,
           department)
