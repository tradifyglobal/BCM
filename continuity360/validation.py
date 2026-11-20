import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, now_datetime

from continuity360 import rules


def _apply(rule, *args):
    try:
        return rule(*args)
    except ValueError as exc:
        frappe.throw(_(str(exc)), frappe.ValidationError)


def _same_company(doc, fieldname: str, target: str) -> None:
    if doc.get(fieldname) and doc.get("company"):
        linked_company = frappe.db.get_value(target, doc.get(fieldname), "company")
        if linked_company != doc.company:
            frappe.throw(_("Linked records must belong to the same company."))


def _child_content(doc, fieldname: str, child_type: str) -> list:
    fields = [f.fieldname for f in frappe.get_meta(child_type).fields
              if f.fieldname and f.fieldtype not in ("Section Break", "Column Break", "Tab Break")]
    return [(row.name, tuple(row.get(name) for name in fields)) for row in doc.get(fieldname)]


def validate_company_links(doc, method=None) -> None:
    _same_company(doc, "department", "C360 Department")
    _same_company(doc, "location", "C360 Location")


def validate_risk(doc, method=None) -> None:
    doc.score, doc.rating = _apply(rules.risk_score, doc.likelihood, doc.impact)
    _same_company(doc, "business_process", "C360 Business Process")
    if doc.status in ("Accepted", "Closed") and not (doc.acceptance_reason or "").strip():
        frappe.throw(_("A justification is required to accept or close a risk."))


def validate_assessment(doc, method=None) -> None:
    _same_company(doc, "risk", "C360 Risk")
    doc.residual_score, doc.residual_rating = _apply(
        rules.risk_score, doc.residual_likelihood, doc.residual_impact
    )


def validate_process(doc, method=None) -> None:
    validate_company_links(doc)
    _apply(rules.recovery_objectives, doc.rto_minutes, doc.rpo_minutes, doc.mtpd_minutes)


def validate_impact(doc, method=None) -> None:
    _same_company(doc, "business_process", "C360 Business Process")
    impacts = []
    for name in ("financial_impact", "operational_impact", "reputational_impact", "regulatory_impact"):
        score, _rating = _apply(rules.risk_score, doc.get(name), 1)
        impacts.append(score)
    doc.overall_impact = max(impacts)


def validate_treatment(doc, method=None) -> None:
    _same_company(doc, "risk", "C360 Risk")
    if doc.start_date and doc.due_date:
        _apply(rules.date_order, getdate(doc.start_date), getdate(doc.due_date), "Due date")
    if doc.status == "Completed" and not (doc.completion_evidence or "").strip():
        frappe.throw(_("Record completion evidence before completing a treatment."))


def validate_plan(doc, method=None) -> None:
    _same_company(doc, "business_process", "C360 Business Process")
    _same_company(doc, "strategy", "C360 Recovery Strategy")
    process = frappe.get_doc("C360 Business Process", doc.business_process)
    _apply(rules.recovery_objectives, doc.rto_minutes, doc.rpo_minutes, process.mtpd_minutes)
    if doc.rto_minutes > process.rto_minutes or doc.rpo_minutes > process.rpo_minutes:
        frappe.throw(_("Plan recovery targets must not exceed the business process RTO and RPO."))
    if not doc.steps:
        frappe.throw(_("Add at least one recovery step."))
    duration = sum(_apply(rules.number, step.expected_minutes, "Step duration") for step in doc.steps)
    if duration > doc.rto_minutes:
        frappe.throw(_("The total planned step duration must not exceed the plan RTO."))
    _validate_controlled_plan(doc, _("recovery plan"))


def validate_bcp(doc, method=None) -> None:
    previous = doc.get_doc_before_save()
    _validate_bcp_version(doc, previous)
    if not previous and doc.owner != frappe.session.user:
        frappe.throw(_("The plan author must be the user creating the plan."), frappe.PermissionError)
    if previous and doc.owner != previous.owner:
        frappe.throw(_("The plan author cannot be changed."), frappe.PermissionError)
    _same_company(doc, "business_process", "C360 Business Process")
    for table, fieldname, target in (
        ("business_units", "department", "C360 Department"),
        ("strategies", "strategy", "C360 Continuity Strategy"),
        ("teams", "team", "C360 BCP Recovery Team"),
        ("procedures", "procedure", "C360 BCP Procedure"),
        ("recovery_plans", "recovery_plan", "C360 Recovery Plan"),
    ):
        _validate_company_rows(doc, table, fieldname, target)
    reviewers = (doc.manager_reviewer, doc.bcm_reviewer, doc.executive_approver)
    if all(reviewers) and len({doc.owner, *reviewers}) != 4:
        frappe.throw(_("The author and all three reviewers must be different people."))
    if previous:
        if previous.approval_status == "Draft" and frappe.session.user != doc.owner:
            frappe.throw(_("Only the plan author may change or submit a draft."), frappe.PermissionError)
        if previous.approval_status in ("Manager Review", "BCM Review", "Executive Approval"):
            actor = {
                "Manager Review": doc.manager_reviewer,
                "BCM Review": doc.bcm_reviewer,
                "Executive Approval": doc.executive_approver,
            }[previous.approval_status]
            if frappe.session.user != actor:
                frappe.throw(_("Only the assigned reviewer may act at this stage."), frappe.PermissionError)
            for f in doc.meta.fields:
                if f.fieldname in ("approval_status", "approved_by", "approved_on", "review_fingerprint") or f.fieldtype in (
                    "Section Break", "Column Break", "Tab Break"
                ):
                    continue
                changed = (_child_content(doc, f.fieldname, f.options)
                           != _child_content(previous, f.fieldname, f.options)
                           if f.fieldtype == "Table" else doc.has_value_changed(f.fieldname))
                if changed:
                    frappe.throw(_("Return the plan to draft before changing {0}.").format(_(f.label)))
            if doc.review_fingerprint != previous.review_fingerprint:
                frappe.throw(_("The review fingerprint cannot be changed."), frappe.PermissionError)
    if doc.approval_status == "Draft":
        doc.review_fingerprint = None
    elif previous and previous.approval_status == "Draft" and doc.approval_status == "Manager Review":
        from continuity360.bcp_snapshot import fingerprint, linked_records

        doc.review_fingerprint = fingerprint(linked_records(doc))
    if not previous or previous.approval_status == "Draft":
        for user, role in (
            (doc.manager_reviewer, "BCP Manager Reviewer"),
            (doc.bcm_reviewer, "BCM Administrator"),
            (doc.executive_approver, "BCP Executive Approver"),
        ):
            if user and (not frappe.db.get_value("User", user, "enabled") or role not in frappe.get_roles(user)):
                frappe.throw(_("Each assigned reviewer must be enabled and have the required BCP role."))
    _validate_controlled_plan(doc, _("business continuity plan"))


def _validate_bcp_version(doc, previous) -> None:
    if previous:
        for fieldname in ("plan_version", "revision_type", "amended_from"):
            if doc.get(fieldname) != previous.get(fieldname):
                frappe.throw(_("Version details cannot be changed after the first save."))
        return
    if not doc.amended_from:
        doc.plan_version = "1.0"
        doc.revision_type = "Minor"
        return
    source = frappe.get_doc(doc.doctype, doc.amended_from, for_update=True)
    source.check_permission("read")
    source.check_permission("amend")
    if source.docstatus != 2 or source.company != doc.company:
        frappe.throw(_("Amend a retired plan belonging to the same company."))
    if frappe.db.exists(doc.doctype, {"amended_from": source.name}):
        frappe.throw(_("This plan already has an amendment. Continue with that revision instead."))
    # Legacy plans retain their original unnumbered snapshots; their amendment baseline is 1.0.
    doc.plan_version = _apply(rules.next_bcp_version, source.plan_version or "1.0", doc.revision_type)


def _validate_company_rows(doc, table: str, fieldname: str, target: str) -> None:
    previous = doc.get_doc_before_save()
    existing = {row.get(fieldname) for row in previous.get(table)} if previous else set()
    seen = set()
    for row in doc.get(table):
        name = row.get(fieldname)
        if name in seen:
            frappe.throw(_("The same record cannot be linked more than once."))
        seen.add(name)
        if frappe.db.get_value(target, name, "company") != doc.company:
            frappe.throw(_("Linked records must belong to the same company."))
        if name not in existing and not frappe.has_permission(target, "read", doc=name):
            frappe.throw(_("You do not have permission to link this record."), frappe.PermissionError)


def validate_bcp_team(doc, method=None) -> None:
    _validate_company_rows(doc, "members", "contact", "C360 Emergency Contact")


def validate_bcp_procedure(doc, method=None) -> None:
    if not doc.steps:
        frappe.throw(_("Add at least one continuity procedure step."))


def validate_exercise(doc, method=None) -> None:
    _same_company(doc, "business_continuity_plan", "C360 Business Continuity Plan")
    _same_company(doc, "recovery_plan", "C360 Recovery Plan")
    if not doc.get("objectives"):
        frappe.throw(_("Add at least one exercise objective."))
    if doc.achieved_rto_minutes not in (None, ""):
        _apply(rules.number, doc.achieved_rto_minutes, "Achieved recovery time")
    _apply(rules.exercise_completion, doc.status, doc.actual_date, doc.result, doc.summary,
           [row.outcome for row in doc.objectives])


def validate_corrective_action(doc, method=None) -> None:
    _same_company(doc, "exercise", "C360 BC Exercise")
    if doc.status == "Completed":
        if not (doc.completion_evidence or "").strip():
            frappe.throw(_("Record completion evidence before completing a corrective action."))
        doc.completed_on = doc.completed_on or getdate()
    else:
        doc.completed_on = None


def validate_call_tree(doc, method=None) -> None:
    _same_company(doc, "business_continuity_plan", "C360 Business Continuity Plan")
    _same_company(doc, "department", "C360 Department")
    _validate_company_rows(doc, "members", "contact", "C360 Emergency Contact")
    pairs = [(row.contact, row.called_by or None) for row in doc.members]
    _apply(rules.call_tree_structure, pairs, doc.status == "Active")
    # Span of control is good practice (3-7 calls per person), so warn without blocking.
    for caller, count in rules.call_tree_span(pairs):
        display = frappe.db.get_value("C360 Emergency Contact", caller, "contact_name") or caller
        frappe.msgprint(
            _("{0} calls {1} people; good practice is three to seven per caller. "
              "Consider a department-level call tree.").format(display, count),
            indicator="orange", alert=True)


def validate_incident(doc, method=None) -> None:
    for fieldname, target in (
        ("business_process", "C360 Business Process"),
        ("risk", "C360 Risk"),
        ("recovery_plan", "C360 Recovery Plan"),
        ("business_continuity_plan", "C360 Business Continuity Plan"),
        ("call_tree", "C360 Call Tree"),
    ):
        _same_company(doc, fieldname, target)
    _apply(rules.incident_lifecycle, doc.status, doc.detected_on, doc.resolved_on,
           doc.resolution_summary)
    levels = [row.sequence for row in doc.escalations]
    if len(set(levels)) != len(levels):
        frappe.throw(_("Escalation levels must be unique."))
    previous = doc.get_doc_before_save()
    if previous and previous.status != doc.status:
        doc.append("timeline", {
            "entry_time": now_datetime(), "entry_type": "Status Change",
            "details": _("Status changed from {0} to {1}.").format(previous.status, doc.status),
            "recorded_by": frappe.session.user,
        })


def notify_incident(doc, method=None) -> None:
    """High and critical incidents alert the incident manager and the escalation chain."""
    if doc.severity not in ("High", "Critical"):
        return
    recipients = {doc.responsible_user} | {row.escalate_to for row in doc.escalations}
    recipients.discard(frappe.session.user)
    for user in sorted(recipients):
        if not frappe.db.get_value("User", user, "enabled"):
            continue
        frappe.get_doc({
            "doctype": "Notification Log", "type": "Alert", "for_user": user,
            "document_type": doc.doctype, "document_name": doc.name,
            "subject": _("{0} incident: {1}").format(doc.severity, doc.incident_title),
            "email_content": _("A {0} severity incident was recorded: {1}. "
                               "You are named on its response or escalation chain.").format(
                                   doc.severity, doc.incident_title),
        }).insert(ignore_permissions=True)


def validate_crisis(doc, method=None) -> None:
    _same_company(doc, "incident", "C360 Incident")
    _same_company(doc, "call_tree", "C360 Call Tree")
    _validate_company_rows(doc, "activated_bcps", "business_continuity_plan",
                           "C360 Business Continuity Plan")
    _validate_company_rows(doc, "activated_recovery_plans", "recovery_plan",
                           "C360 Recovery Plan")
    if doc.deputy_commander and doc.deputy_commander == doc.crisis_commander:
        frappe.throw(_("The deputy commander must be a different person from the commander."))
    for user in (doc.crisis_commander, doc.deputy_commander):
        if user and not frappe.db.get_value("User", user, "enabled"):
            frappe.throw(_("Crisis commanders must be enabled users."))
    _apply(rules.crisis_closure, doc.status, doc.declared_on, doc.stood_down_on,
           doc.outcome_summary)
    previous = doc.get_doc_before_save()
    if previous and previous.status != doc.status:
        doc.append("log", {
            "logged_on": now_datetime(), "entry_type": "Situation Update",
            "details": _("Status changed from {0} to {1}.").format(previous.status, doc.status),
            "recorded_by": frappe.session.user,
        })


def validate_application(doc, method=None) -> None:
    _same_company(doc, "vendor", "C360 Vendor")
    _same_company(doc, "recovery_plan", "C360 Recovery Plan")
    _validate_company_rows(doc, "supported_processes", "business_process",
                           "C360 Business Process")


def validate_database_instance(doc, method=None) -> None:
    _same_company(doc, "server", "C360 Server")


def validate_dependency(doc, method=None) -> None:
    _apply(rules.dependency_target, doc.application, doc.depends_on_application,
           doc.depends_on_server, doc.depends_on_database)
    for fieldname, target in (
        ("application", "C360 Application"),
        ("depends_on_application", "C360 Application"),
        ("depends_on_server", "C360 Server"),
        ("depends_on_database", "C360 Database Instance"),
    ):
        _same_company(doc, fieldname, target)


def validate_simulation(doc, method=None) -> None:
    targets = {"Application": doc.target_application, "Server": doc.target_server,
               "Database": doc.target_database}
    if not targets.get(doc.target_type):
        frappe.throw(_("Select the {0} this simulation targets.").format(_(doc.target_type)))
    if sum(1 for value in targets.values() if value) != 1:
        frappe.throw(_("Select exactly one target component."))
    for fieldname, target in (
        ("target_application", "C360 Application"),
        ("target_server", "C360 Server"),
        ("target_database", "C360 Database Instance"),
    ):
        _same_company(doc, fieldname, target)


def _validate_controlled_plan(doc, label) -> None:
    if doc.is_new() and (doc.approval_status != "Draft" or doc.docstatus != 0):
        frappe.throw(_("New plans must begin as drafts."))
    if doc.docstatus == 0:
        doc.approved_by = None
        doc.approved_on = None
    previous = doc.get_doc_before_save()
    if previous and doc.docstatus == 0 and doc.has_value_changed("change_reason") is False:
        changed_fields = [
            f for f in doc.meta.fields
            if f.fieldname not in ("approval_status", "approved_by", "approved_on", "change_reason", "review_fingerprint")
            and f.fieldtype not in ("Section Break", "Column Break", "Tab Break")
        ]
        if any(
            not doc.is_child_table_same(f.fieldname) if f.fieldtype == "Table"
            else doc.has_value_changed(f.fieldname)
            for f in changed_fields
        ):
            frappe.throw(_("Update the revision reason when changing a {0}.").format(label))


def approve_plan(doc, method=None) -> None:
    _approve_controlled_plan(doc, _("recovery plan"))


def approve_bcp(doc, method=None) -> None:
    previous = doc.get_doc_before_save()
    if not previous or previous.approval_status != "Executive Approval":
        frappe.throw(_("A business continuity plan must complete all review stages before approval."))
    if frappe.session.user != doc.executive_approver or "BCP Executive Approver" not in frappe.get_roles():
        frappe.throw(_("Only the assigned executive approver may approve this plan."), frappe.PermissionError)
    today = getdate()
    if getdate(doc.review_date) < today or getdate(doc.review_date) > getdate(add_to_date(today, years=1)):
        frappe.throw(_("The review date must be between today and one year from approval."))
    doc.approved_by = frappe.session.user
    doc.approved_on = now_datetime()
    from continuity360.bcp_snapshot import capture

    capture(doc)


def _approve_controlled_plan(doc, label) -> None:
    previous = doc.get_doc_before_save()
    if not previous or previous.approval_status != "In Review":
        frappe.throw(_("A {0} must be in review before approval.").format(label))
    if "BCM Administrator" not in frappe.get_roles():
        frappe.throw(_("Only a BCM Administrator may approve a {0}.").format(label), frappe.PermissionError)
    if frappe.session.user == doc.owner:
        frappe.throw(_("The plan author cannot approve their own plan."))
    if getdate(doc.review_date) < getdate():
        frappe.throw(_("Set a current or future review date before approval."))
    doc.approved_by = frappe.session.user
    doc.approved_on = now_datetime()
