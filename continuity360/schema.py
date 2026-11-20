"""Tenant-local DocType definitions installed through Frappe's metadata API."""

ADMIN = "BCM Administrator"
RISK = "Risk Manager"
IT = "IT Manager"
AUDITOR = "Auditor"
EMPLOYEE = "Employee"
BCP_AUTHOR = "BCP Author"
BCP_MANAGER = "BCP Manager Reviewer"
BCP_EXECUTIVE = "BCP Executive Approver"
ROLES = (ADMIN, RISK, IT, AUDITOR, EMPLOYEE, BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE)
DOCTYPES: dict[str, dict] = {}


def field(name: str, label: str, kind: str = "Data", **options) -> dict:
    return {"fieldname": name, "label": label, "fieldtype": kind, **options}


def link(name: str, label: str, target: str, **options) -> dict:
    return field(name, label, "Link", options=target, **options)


def choice(name: str, label: str, options: str, **settings) -> dict:
    return field(name, label, "Select", options=options, **settings)


def permissions(editors: tuple[str, ...], readers: tuple[str, ...]) -> list[dict]:
    # No record sharing or deletion: access comes from roles and optional Frappe User Permissions.
    result = []
    for role in dict.fromkeys((ADMIN, *editors, *readers)):
        writable = role in (ADMIN, *editors)
        result.append({
            "role": role, "read": 1, "write": int(writable), "create": int(writable),
            "report": 1, "export": int(role != EMPLOYEE), "print": 1,
            "email": 0, "share": 0, "delete": 0,
        })
    return result


def define(name: str, fields: list[dict], *, editors=(), readers=(AUDITOR,), **options) -> None:
    DOCTYPES[name] = {
        "doctype": "DocType", "name": name, "module": "Continuity360", "custom": 1,
        "engine": "InnoDB", "track_changes": 1,
        "autoname": f"C360-{name.removeprefix('C360 ').upper().replace(' ', '-') }-.#####",
        "fields": fields, "permissions": permissions(editors, readers), **options,
    }


company = lambda: link("company", "Company", "C360 Company", reqd=1, in_list_view=1)
owner = lambda: link("responsible_user", "Responsible person", "User", reqd=1)
description = lambda: field("description", "Description", "Text Editor")

define("C360 Company", [
    field("company_name", "Company name", reqd=1, in_list_view=1),
    field("industry", "Industry"),
    field("country", "Country"),
    field("website", "Website", options="URL"),
    description(),
], title_field="company_name",
    readers=(RISK, IT, AUDITOR, EMPLOYEE, BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE))

define("C360 Department", [
    field("department_name", "Department name", reqd=1, in_list_view=1), company(),
    owner(), description(),
], title_field="department_name",
    readers=(RISK, IT, AUDITOR, EMPLOYEE, BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE))

define("C360 Location", [
    field("location_name", "Location name", reqd=1, in_list_view=1), company(),
    field("address", "Address", "Small Text"),
    field("emergency_phone", "Emergency phone", options="Phone"),
], title_field="location_name", readers=(RISK, IT, AUDITOR))

define("C360 Employee", [
    field("employee_name", "Employee name", reqd=1, in_list_view=1), company(),
    link("department", "Department", "C360 Department"),
    link("location", "Location", "C360 Location"),
    link("user", "User account", "User"),
    field("email", "Work email", options="Email"),
    field("phone", "Work phone", options="Phone"),
], title_field="employee_name", readers=(IT, AUDITOR))

define("C360 Vendor", [
    field("vendor_name", "Vendor name", reqd=1, in_list_view=1), company(),
    field("service", "Provided service"), field("contact_email", "Contact email", options="Email"),
    field("contact_phone", "Contact phone", options="Phone"),
    choice("criticality", "Criticality", "Low\nMedium\nHigh\nCritical", default="Medium"),
], title_field="vendor_name", readers=(RISK, IT, AUDITOR))

define("C360 Business Process", [
    field("process_name", "Business process", reqd=1, in_list_view=1), company(),
    link("department", "Department", "C360 Department", reqd=1), owner(),
    choice("criticality", "Criticality", "Low\nMedium\nHigh\nCritical", default="Medium", in_list_view=1),
    description(),
    field("rto_minutes", "RTO (minutes)", "Int", reqd=1, default="60",
          description="Recovery Time Objective: how quickly this process must be restored after a disruption."),
    field("rpo_minutes", "RPO (minutes)", "Int", default="15",
          description="Recovery Point Objective: the maximum acceptable data loss, measured backwards in time."),
    field("mtpd_minutes", "MTPD (minutes)", "Int", reqd=1, default="240",
          description="Maximum Tolerable Period of Disruption: the longest outage the business can survive."),
    field("manual_workaround", "Manual workaround", "Text Editor"),
], title_field="process_name", editors=(RISK, IT), readers=(AUDITOR, BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE))

define("C360 Risk", [
    field("risk_title", "Risk title", reqd=1, in_list_view=1), company(),
    link("business_process", "Business process", "C360 Business Process"), owner(),
    choice("category", "Category", "Operational\nTechnology\nPeople\nSupplier\nEnvironmental\nRegulatory",
           default="Operational"),
    description(),
    field("likelihood", "Likelihood (1-5)", "Int", default="1", reqd=1),
    field("impact", "Impact (1-5)", "Int", default="1", reqd=1),
    field("score", "Inherent risk score", "Int", read_only=1, in_list_view=1),
    choice("rating", "Inherent risk rating", "Low\nMedium\nHigh\nCritical", read_only=1, in_list_view=1),
    choice("status", "Status", "Open\nTreating\nAccepted\nClosed", default="Open", in_list_view=1),
    field("acceptance_reason", "Acceptance / closure justification", "Small Text"),
], title_field="risk_title", editors=(RISK,))

define("C360 Risk Assessment", [
    company(),
    link("risk", "Risk", "C360 Risk", reqd=1, in_list_view=1),
    field("assessment_date", "Assessment date", "Date", reqd=1, default="Today"), owner(),
    field("residual_likelihood", "Residual likelihood (1-5)", "Int", reqd=1, default="1"),
    field("residual_impact", "Residual impact (1-5)", "Int", reqd=1, default="1"),
    field("residual_score", "Residual risk score", "Int", read_only=1, in_list_view=1),
    choice("residual_rating", "Residual rating", "Low\nMedium\nHigh\nCritical", read_only=1),
    field("rationale", "Assessment rationale", "Text Editor", reqd=1),
], editors=(RISK,))

define("C360 Risk Treatment", [
    company(),
    field("treatment_title", "Treatment title", reqd=1, in_list_view=1),
    link("risk", "Risk", "C360 Risk", reqd=1), owner(),
    choice("strategy", "Strategy", "Mitigate\nAvoid\nTransfer\nAccept", default="Mitigate"),
    field("actions", "Treatment actions", "Text Editor", reqd=1),
    field("start_date", "Start date", "Date", reqd=1, default="Today"),
    field("due_date", "Due date", "Date", reqd=1),
    choice("status", "Status", "Planned\nIn Progress\nCompleted", default="Planned", in_list_view=1),
    field("completion_evidence", "Completion evidence / reference", "Small Text"),
], title_field="treatment_title", editors=(RISK, IT))

define("C360 Impact Assessment", [
    company(),
    link("business_process", "Business process", "C360 Business Process", reqd=1, in_list_view=1),
    field("assessment_date", "Assessment date", "Date", reqd=1, default="Today"), owner(),
    field("financial_impact", "Financial impact (1-5)", "Int", reqd=1, default="1"),
    field("operational_impact", "Operational impact (1-5)", "Int", reqd=1, default="1"),
    field("reputational_impact", "Reputational impact (1-5)", "Int", reqd=1, default="1"),
    field("regulatory_impact", "Regulatory impact (1-5)", "Int", reqd=1, default="1"),
    field("overall_impact", "Highest impact", "Int", read_only=1, in_list_view=1),
    field("disruption_scenario", "Disruption scenario", "Small Text", reqd=1),
    field("impact_over_time", "Impact over time and rationale", "Text Editor", reqd=1),
], editors=(RISK, IT))

define("C360 Compliance Control", [
    field("control_title", "Control title", reqd=1, in_list_view=1), company(),
    field("framework", "Framework", reqd=1, in_list_view=1),
    field("control_reference", "Framework reference", reqd=1, in_list_view=1),
    owner(),
    choice("status", "Self-assessed status", "Not Assessed\nIn Progress\nImplemented\nNot Applicable",
           default="Not Assessed", in_list_view=1),
    description(),
    field("evidence_reference", "Evidence reference", "Small Text"),
    field("review_date", "Next review date", "Date"),
], title_field="control_title", editors=(RISK,), readers=(IT, AUDITOR))

define("C360 Recovery Strategy", [
    field("strategy_name", "Strategy name", reqd=1, in_list_view=1), company(),
    choice("strategy_type", "Strategy type",
           "Manual Workaround\nAlternate Site\nBackup Restore\nActive-Passive\nActive-Active",
           default="Manual Workaround"),
    description(),
], title_field="strategy_name", editors=(IT,))

define("C360 Recovery Step", [
    field("instruction", "Instruction", "Small Text", reqd=1, in_list_view=1),
    link("responsible_user", "Responsible person", "User", reqd=1, in_list_view=1),
    field("expected_minutes", "Expected duration (minutes)", "Int", reqd=1, default="5", in_list_view=1),
    field("validation", "Success / validation criteria", "Small Text", reqd=1),
], istable=1, permissions=[])

define("C360 Plan Contact", [
    field("contact_name", "Contact name", reqd=1, in_list_view=1),
    field("role", "Recovery responsibility", reqd=1, in_list_view=1),
    field("email", "Work email", options="Email", in_list_view=1),
    field("phone", "Work phone", options="Phone", in_list_view=1),
], istable=1, permissions=[])

define("C360 Recovery Plan", [
    field("plan_title", "Plan title", reqd=1, in_list_view=1), company(),
    link("business_process", "Business process", "C360 Business Process", reqd=1),
    owner(), link("strategy", "Recovery strategy", "C360 Recovery Strategy", reqd=1),
    choice("approval_status", "Approval status", "Draft\nIn Review\nApproved\nRetired",
           default="Draft", read_only=1, in_list_view=1, no_copy=1),
    field("scope", "Purpose and scope", "Text Editor", reqd=1),
    field("activation_criteria", "Activation criteria", "Small Text", reqd=1),
    field("rto_minutes", "RTO (minutes)", "Int", reqd=1, default="60",
          description="Recovery Time Objective: how quickly this service must be restored after a disruption."),
    field("rpo_minutes", "RPO (minutes)", "Int", default="15",
          description="Recovery Point Objective: the maximum acceptable data loss, measured backwards in time."),
    field("contacts", "Recovery team and emergency contacts", "Table", options="C360 Plan Contact"),
    field("steps", "Recovery procedure", "Table", options="C360 Recovery Step", reqd=1),
    field("review_date", "Next review date", "Date", reqd=1, in_list_view=1),
    field("change_reason", "Reason for this revision", "Small Text", reqd=1),
    link("approved_by", "Approved by", "User", read_only=1, no_copy=1),
    field("approved_on", "Approved on", "Datetime", read_only=1, no_copy=1),
    field("amended_from", "Amended from", "Link", options="C360 Recovery Plan",
          read_only=1, print_hide=1, no_copy=1),
], title_field="plan_title", editors=(IT,), is_submittable=1)

define("C360 BCP Recovery Link", [
    link("recovery_plan", "Recovery plan", "C360 Recovery Plan", reqd=1, in_list_view=1),
], istable=1, permissions=[])

define("C360 Continuity Strategy", [
    field("strategy_name", "Strategy name", reqd=1, in_list_view=1), company(), owner(),
    choice("strategy_type", "Strategy type",
           "Work From Home\nAlternative Site\nManual Processing\nThird Party Recovery\nOther",
           reqd=1),
    field("description", "Strategy description", "Text Editor", reqd=1),
], title_field="strategy_name", editors=(BCP_AUTHOR,), readers=(BCP_MANAGER, BCP_EXECUTIVE, IT, AUDITOR))

define("C360 Emergency Contact", [
    field("contact_name", "Contact name", reqd=1, in_list_view=1), company(),
    choice("contact_type", "Contact type",
           "Employee\nVendor\nEmergency Service\nCustomer\nRegulator\nOther", reqd=1, in_list_view=1),
    field("responsibility", "Role or responsibility"),
    field("email", "Email", options="Email"),
    field("phone", "Phone", options="Phone"),
], title_field="contact_name", editors=(BCP_AUTHOR,), readers=(BCP_MANAGER, BCP_EXECUTIVE, IT, AUDITOR))

define("C360 BCP Team Member", [
    link("contact", "Emergency contact", "C360 Emergency Contact", reqd=1, in_list_view=1),
    field("responsibility", "Team responsibility", reqd=1, in_list_view=1),
], istable=1, permissions=[])

define("C360 BCP Recovery Team", [
    field("team_name", "Team name", reqd=1, in_list_view=1), company(), owner(),
    description(),
    field("members", "Team members", "Table", options="C360 BCP Team Member"),
], title_field="team_name", editors=(BCP_AUTHOR,), readers=(BCP_MANAGER, BCP_EXECUTIVE, IT, AUDITOR))

define("C360 BCP Procedure Step", [
    field("instruction", "Instruction", "Small Text", reqd=1, in_list_view=1),
    link("responsible_user", "Responsible person", "User", reqd=1, in_list_view=1),
    field("completion_criteria", "Completion criteria", "Small Text"),
], istable=1, permissions=[])

define("C360 BCP Procedure", [
    field("procedure_name", "Procedure name", reqd=1, in_list_view=1), company(), owner(),
    field("trigger", "When to use this procedure", "Small Text", reqd=1),
    field("steps", "Ordered steps", "Table", options="C360 BCP Procedure Step", reqd=1),
], title_field="procedure_name", editors=(BCP_AUTHOR,), readers=(BCP_MANAGER, BCP_EXECUTIVE, IT, AUDITOR))

for child_name, fieldname, label, target in (
    ("C360 BCP Department Link", "department", "Business unit", "C360 Department"),
    ("C360 BCP Strategy Link", "strategy", "Continuity strategy", "C360 Continuity Strategy"),
    ("C360 BCP Team Link", "team", "Recovery team", "C360 BCP Recovery Team"),
    ("C360 BCP Procedure Link", "procedure", "Continuity procedure", "C360 BCP Procedure"),
):
    define(child_name, [link(fieldname, label, target, reqd=1, in_list_view=1)], istable=1, permissions=[])

define("C360 Business Continuity Plan", [
    field("plan_title", "Plan title", reqd=1, in_list_view=1), company(),
    field("plan_version", "Plan version", read_only=1, no_copy=1, in_list_view=1,
          description="Assigned by the server on first save; fixed thereafter."),
    choice("revision_type", "Revision type", "Minor\nMajor", default="Minor", no_copy=1,
           depends_on="eval:doc.amended_from",
           read_only_depends_on="eval:!doc.__islocal",
           description="Choose before saving an amendment: Minor 1.0 to 1.1; Major 1.1 to 2.0."),
    link("business_process", "Business process", "C360 Business Process"),
    owner(),
    link("manager_reviewer", "Manager reviewer", "User", reqd=1),
    link("bcm_reviewer", "BCM reviewer", "User", reqd=1),
    link("executive_approver", "Executive approver", "User", reqd=1),
    choice("approval_status", "Approval status",
           "Draft\nManager Review\nBCM Review\nExecutive Approval\nApproved\nRetired",
           default="Draft", read_only=1, in_list_view=1, no_copy=1),
    field("scope", "Purpose and scope", "Text Editor", reqd=1),
    field("activation_criteria", "Activation criteria", "Small Text", reqd=1),
    field("continuity_procedures", "Continuity procedures and workarounds", "Text Editor", reqd=1),
    field("communication_procedures", "Communication and escalation procedures", "Text Editor", reqd=1),
    field("contacts", "Continuity team and emergency contacts", "Table", options="C360 Plan Contact"),
    field("business_units", "Business units covered", "Table", options="C360 BCP Department Link"),
    field("strategies", "Continuity strategies", "Table", options="C360 BCP Strategy Link"),
    field("teams", "Recovery teams", "Table", options="C360 BCP Team Link"),
    field("procedures", "Detailed procedures", "Table", options="C360 BCP Procedure Link"),
    field("recovery_plans", "Related recovery plans", "Table", options="C360 BCP Recovery Link"),
    field("review_date", "Next review date", "Date", reqd=1, in_list_view=1),
    field("change_reason", "Reason for this revision", "Small Text", reqd=1),
    field("review_fingerprint", "Review fingerprint", read_only=1, hidden=1, no_copy=1),
    link("approved_by", "Approved by", "User", read_only=1, no_copy=1),
    field("approved_on", "Approved on", "Datetime", read_only=1, no_copy=1),
    field("amended_from", "Amended from", "Link", options="C360 Business Continuity Plan",
          read_only=1, print_hide=1, no_copy=1),
], title_field="plan_title", editors=(BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE),
    readers=(IT, AUDITOR), is_submittable=1)

define("C360 BCP Approval Snapshot", [
    link("plan", "Approved plan", "C360 Business Continuity Plan", reqd=1, unique=1),
    company(),
    field("captured_on", "Captured on", "Datetime", reqd=1),
    field("payload", "Approved content", "Long Text", reqd=1),
], permissions=[])

define("C360 BCP Distribution Recipient", [
    link("recipient", "Recipient", "User", reqd=1, in_list_view=1),
    field("recipient_name", "Name at distribution", reqd=1),
    # Small Text: combined eligibility reasons can exceed a Data field's 140 characters.
    field("reason", "Why this person receives the plan", "Small Text", reqd=1),
    field("first_opened_on", "First opened on", "Datetime", read_only=1),
    field("last_opened_on", "Last opened on", "Datetime", read_only=1),
    field("open_count", "Open count", "Int", default="0", read_only=1),
    field("acknowledged_on", "Acknowledged on", "Datetime", read_only=1),
], istable=1, permissions=[])

define("C360 BCP Distribution", [
    link("plan", "Approved plan", "C360 Business Continuity Plan", reqd=1),
    company(),
    link("snapshot", "Approval snapshot", "C360 BCP Approval Snapshot", reqd=1),
    link("distributed_by", "Distributed by", "User", reqd=1),
    field("distributed_on", "Distributed on", "Datetime", reqd=1),
    field("recipients", "Recipients", "Table", options="C360 BCP Distribution Recipient", reqd=1),
], permissions=[])

define("C360 BCP Review Reminder", [
    link("plan", "Plan", "C360 Business Continuity Plan", reqd=1),
    company(),
    link("recipient", "Plan owner", "User", reqd=1),
    field("review_date", "Review date", "Date", reqd=1),
    field("slot", "Reminder interval", reqd=1),
    field("event_key", "Event key", reqd=1, unique=1),
    link("notification", "Notification", "Notification Log", reqd=1),
], permissions=[])

# System-managed issue log: gives every generated PDF report a version number and history.
define("C360 Report Issue", [
    field("report", "Report", reqd=1, in_list_view=1),
    field("report_title", "Report title", reqd=1),
    link("department", "Department scope", "C360 Department"),
    field("version", "Issue version", "Int", reqd=1, in_list_view=1),
    link("generated_by", "Prepared by", "User", reqd=1),
    field("generated_on", "Generated on", "Datetime", reqd=1),
], permissions=[])

define("C360 Exercise Objective", [
    field("objective", "Objective", "Small Text", reqd=1, in_list_view=1),
    choice("outcome", "Outcome", "Not Assessed\nMet\nPartially Met\nNot Met",
           default="Not Assessed", reqd=1, in_list_view=1),
    field("notes", "Notes", "Small Text"),
], istable=1, permissions=[])

define("C360 Exercise Participant", [
    link("participant", "Participant", "User", reqd=1, in_list_view=1),
    field("exercise_role", "Role in exercise", reqd=1, in_list_view=1),
    field("attended", "Attended", "Check", default="1", in_list_view=1),
], istable=1, permissions=[])

define("C360 BC Exercise", [
    field("exercise_name", "Exercise name", reqd=1, in_list_view=1), company(),
    choice("exercise_type", "Exercise type",
           "Tabletop Exercise\nWalkthrough\nSimulation\nDR Drill\nFull Interruption Test",
           reqd=1, in_list_view=1),
    owner(),
    link("business_continuity_plan", "Business continuity plan", "C360 Business Continuity Plan"),
    link("recovery_plan", "Recovery plan", "C360 Recovery Plan"),
    choice("status", "Status", "Planned\nIn Progress\nCompleted\nCancelled",
           default="Planned", reqd=1, in_list_view=1),
    field("scheduled_date", "Scheduled date", "Date", reqd=1, in_list_view=1),
    field("actual_date", "Conducted on", "Date"),
    field("scenario", "Scenario", "Text Editor", reqd=1,
          description="The disruption this exercise simulates; no live systems are affected."),
    field("objectives", "Objectives", "Table", options="C360 Exercise Objective", reqd=1),
    field("participants", "Participants", "Table", options="C360 Exercise Participant"),
    choice("result", "Overall result",
           "\nEffective\nEffective With Observations\nNeeds Improvement\nIneffective",
           in_list_view=1),
    field("achieved_rto_minutes", "Achieved recovery time (minutes)", "Int",
          description="Measured time to recover during the exercise, where applicable."),
    field("summary", "Results summary", "Text Editor"),
    field("lessons_learned", "Lessons learned", "Text Editor"),
], title_field="exercise_name", editors=(RISK, IT, BCP_AUTHOR),
    readers=(AUDITOR, BCP_MANAGER, BCP_EXECUTIVE))

define("C360 Call Tree Member", [
    link("contact", "Contact", "C360 Emergency Contact", reqd=1, in_list_view=1),
    link("called_by", "Called by", "C360 Emergency Contact", in_list_view=1,
         description="Leave empty for the person who starts the cascade."),
    field("tree_role", "Role in the cascade", in_list_view=1),
], istable=1, permissions=[])

define("C360 Call Tree", [
    field("tree_name", "Call tree name", reqd=1, in_list_view=1), company(), owner(),
    link("business_continuity_plan", "Business continuity plan", "C360 Business Continuity Plan"),
    link("department", "Department", "C360 Department"),
    choice("status", "Status", "Draft\nActive\nRetired", default="Draft", reqd=1, in_list_view=1,
           description="Only Active call trees are printed in reports. Activation requires a "
                       "complete cascade: one or more initiators and every member reachable."),
    field("activation_criteria", "When to activate", "Small Text", reqd=1),
    field("instructions", "Caller instructions", "Small Text",
          description="What each caller must tell the people they phone."),
    field("members", "Cascade members", "Table", options="C360 Call Tree Member", reqd=1),
], title_field="tree_name", editors=(BCP_AUTHOR, IT),
    readers=(BCP_MANAGER, BCP_EXECUTIVE, AUDITOR))

define("C360 Corrective Action", [
    field("action_title", "Action title", reqd=1, in_list_view=1), company(),
    link("exercise", "Exercise", "C360 BC Exercise", reqd=1, in_list_view=1),
    owner(),
    choice("priority", "Priority", "Low\nMedium\nHigh\nCritical",
           default="Medium", reqd=1, in_list_view=1),
    choice("status", "Status", "Open\nIn Progress\nCompleted\nCancelled",
           default="Open", reqd=1, in_list_view=1),
    field("description", "What must change", "Text Editor", reqd=1),
    field("due_date", "Due date", "Date", reqd=1, in_list_view=1),
    field("completed_on", "Completed on", "Date", read_only=1, no_copy=1),
    field("completion_evidence", "Completion evidence", "Small Text"),
], title_field="action_title", editors=(RISK, IT, BCP_AUTHOR),
    readers=(AUDITOR, BCP_MANAGER, BCP_EXECUTIVE))

# ---------------------------------------------------------------- Phase 2: incidents

define("C360 Incident Timeline Entry", [
    field("entry_time", "Time", "Datetime", reqd=1, in_list_view=1),
    choice("entry_type", "Entry type",
           "Detection\nEscalation\nAction\nCommunication\nStatus Change\nResolution",
           reqd=1, in_list_view=1),
    field("details", "Details", "Small Text", reqd=1, in_list_view=1),
    link("recorded_by", "Recorded by", "User", reqd=1),
], istable=1, permissions=[])

define("C360 Incident Escalation", [
    field("sequence", "Escalation level", "Int", reqd=1, in_list_view=1),
    link("escalate_to", "Escalate to", "User", reqd=1, in_list_view=1),
    field("criteria", "Escalation criteria", "Small Text", reqd=1, in_list_view=1),
], istable=1, permissions=[])

define("C360 Incident", [
    field("incident_title", "Incident title", reqd=1, in_list_view=1), company(),
    choice("incident_type", "Incident type",
           "IT Outage\nCyber Security\nFacility\nSupplier\nPeople\nData Loss\nOther",
           reqd=1, in_list_view=1),
    choice("severity", "Severity", "Low\nMedium\nHigh\nCritical", reqd=1, in_list_view=1),
    choice("status", "Status", "Open\nInvestigating\nMitigated\nResolved\nClosed",
           default="Open", reqd=1, in_list_view=1),
    owner(),
    link("reported_by", "Reported by", "User", reqd=1),
    field("detected_on", "Detected on", "Datetime", reqd=1),
    field("resolved_on", "Resolved on", "Datetime"),
    field("description", "What happened", "Text Editor", reqd=1),
    link("business_process", "Affected business process", "C360 Business Process"),
    link("risk", "Related risk", "C360 Risk"),
    link("recovery_plan", "Activated recovery plan", "C360 Recovery Plan"),
    link("business_continuity_plan", "Activated business continuity plan",
         "C360 Business Continuity Plan"),
    link("call_tree", "Call tree used", "C360 Call Tree"),
    field("escalations", "Escalation chain", "Table", options="C360 Incident Escalation"),
    field("timeline", "Timeline", "Table", options="C360 Incident Timeline Entry"),
    field("impact_summary", "Impact summary", "Small Text"),
    field("root_cause", "Root cause", "Small Text"),
    field("resolution_summary", "Resolution summary", "Small Text"),
], title_field="incident_title", editors=(IT, RISK),
    readers=(AUDITOR, BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE))

# ------------------------------------------------------------------ Phase 2: crisis

define("C360 Crisis Log Entry", [
    field("logged_on", "Time", "Datetime", reqd=1, in_list_view=1),
    choice("entry_type", "Entry type", "Decision\nAction\nSituation Update\nCommunication",
           reqd=1, in_list_view=1),
    field("details", "Details", "Small Text", reqd=1, in_list_view=1),
    link("recorded_by", "Recorded by", "User", reqd=1),
], istable=1, permissions=[])

define("C360 Crisis Communication", [
    choice("audience", "Audience", "Employees\nCustomers\nRegulators\nSuppliers\nMedia\nExecutives",
           reqd=1, in_list_view=1),
    choice("channel", "Channel", "Email\nPhone\nSMS\nStatus Page\nPress Release\nBriefing",
           reqd=1, in_list_view=1),
    link("responsible", "Responsible", "User", reqd=1, in_list_view=1),
    field("message_summary", "Message summary", "Small Text", reqd=1),
    field("sent_on", "Sent on", "Datetime"),
], istable=1, permissions=[])

define("C360 Crisis BCP Link", [
    link("business_continuity_plan", "Business continuity plan",
         "C360 Business Continuity Plan", reqd=1, in_list_view=1),
], istable=1, permissions=[])

define("C360 Crisis Recovery Link", [
    link("recovery_plan", "Recovery plan", "C360 Recovery Plan", reqd=1, in_list_view=1),
], istable=1, permissions=[])

define("C360 Communication Plan", [
    field("plan_name", "Plan name", reqd=1, in_list_view=1), company(), owner(),
    choice("audience", "Audience", "Employees\nCustomers\nRegulators\nSuppliers\nMedia\nExecutives",
           reqd=1, in_list_view=1),
    choice("channel", "Primary channel", "Email\nPhone\nSMS\nStatus Page\nPress Release\nBriefing",
           reqd=1, in_list_view=1),
    field("trigger", "When to use", "Small Text", reqd=1),
    field("message_template", "Message template", "Text Editor", reqd=1),
    link("approver", "Message approver", "User"),
], title_field="plan_name", editors=(RISK,),
    readers=(IT, AUDITOR, BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE))

define("C360 Crisis Event", [
    field("crisis_title", "Crisis title", reqd=1, in_list_view=1), company(),
    choice("level", "Crisis level",
           "Level 1 - Site\nLevel 2 - Significant\nLevel 3 - Organisation-wide",
           reqd=1, in_list_view=1),
    choice("status", "Status", "Declared\nManaging\nStood Down\nClosed",
           default="Declared", reqd=1, in_list_view=1),
    link("crisis_commander", "Crisis commander", "User", reqd=1),
    link("deputy_commander", "Deputy commander", "User"),
    link("incident", "Triggering incident", "C360 Incident"),
    link("call_tree", "Call tree activated", "C360 Call Tree"),
    field("declared_on", "Declared on", "Datetime", reqd=1),
    field("stood_down_on", "Stood down on", "Datetime"),
    field("situation_summary", "Situation summary", "Text Editor", reqd=1),
    field("activated_bcps", "Activated business continuity plans", "Table",
          options="C360 Crisis BCP Link"),
    field("activated_recovery_plans", "Activated recovery plans", "Table",
          options="C360 Crisis Recovery Link"),
    field("log", "Decision and action log", "Table", options="C360 Crisis Log Entry"),
    field("communications", "Communications issued", "Table",
          options="C360 Crisis Communication"),
    field("outcome_summary", "Outcome summary", "Small Text"),
], title_field="crisis_title", editors=(RISK,),
    readers=(IT, AUDITOR, BCP_AUTHOR, BCP_MANAGER, BCP_EXECUTIVE))

# ---------------------------------------------------- Phase 2: infrastructure inventory

define("C360 Application Process Link", [
    link("business_process", "Business process", "C360 Business Process",
         reqd=1, in_list_view=1),
], istable=1, permissions=[])

define("C360 Application", [
    field("application_name", "Application name", reqd=1, in_list_view=1), company(), owner(),
    choice("criticality", "Criticality", "Low\nMedium\nHigh\nCritical", reqd=1, in_list_view=1),
    choice("hosting", "Hosting model", "On-Premises\nAWS\nAzure\nGoogle Cloud\nSaaS\nHybrid",
           reqd=1, in_list_view=1),
    link("vendor", "Vendor", "C360 Vendor"),
    link("recovery_plan", "Recovery plan", "C360 Recovery Plan"),
    field("supported_processes", "Business processes supported", "Table",
          options="C360 Application Process Link"),
    description(),
], title_field="application_name", editors=(IT,), readers=(RISK, AUDITOR))

define("C360 Server", [
    field("server_name", "Server name", reqd=1, in_list_view=1), company(), owner(),
    choice("environment", "Environment", "Production\nStaging\nDevelopment\nDisaster Recovery",
           reqd=1, in_list_view=1),
    choice("platform", "Platform",
           "AWS EC2\nAzure Virtual Machine\nAzure Kubernetes Service\n"
           "On-Premises Virtual Machine\nOn-Premises Physical\nOther Cloud",
           reqd=1, in_list_view=1),
    link("location", "Location", "C360 Location"),
    field("operating_system", "Operating system"),
    description(),
], title_field="server_name", editors=(IT,), readers=(RISK, AUDITOR))

define("C360 Database Instance", [
    field("database_name", "Database name", reqd=1, in_list_view=1), company(), owner(),
    choice("engine", "Engine", "MariaDB\nMySQL\nPostgreSQL\nSQL Server\nOracle\nMongoDB\nOther",
           reqd=1, in_list_view=1),
    choice("platform", "Platform", "AWS RDS\nAzure SQL\nAzure Database\nSelf-Managed\nSaaS\nOther",
           reqd=1, in_list_view=1),
    link("server", "Hosted on server", "C360 Server"),
    description(),
], title_field="database_name", editors=(IT,), readers=(RISK, AUDITOR))

define("C360 IT Dependency", [
    field("dependency_title", "Dependency", reqd=1, in_list_view=1), company(),
    link("application", "Dependent application", "C360 Application", reqd=1, in_list_view=1),
    choice("dependency_type", "Dependency type",
           "Runs On\nStores Data In\nIntegrates With\nSupplied By", reqd=1, in_list_view=1),
    link("depends_on_application", "Depends on application", "C360 Application"),
    link("depends_on_server", "Depends on server", "C360 Server"),
    link("depends_on_database", "Depends on database", "C360 Database Instance"),
    field("notes", "Notes", "Small Text"),
], title_field="dependency_title", editors=(IT,), readers=(RISK, AUDITOR))

# ----------------------------------------------- Phase 2: recovery intelligence records

define("C360 Outage Simulation", [
    field("simulation_title", "Simulation title", reqd=1, in_list_view=1), company(), owner(),
    choice("target_type", "Component type", "Application\nServer\nDatabase",
           reqd=1, in_list_view=1),
    link("target_application", "Application", "C360 Application"),
    link("target_server", "Server", "C360 Server"),
    link("target_database", "Database", "C360 Database Instance"),
    field("simulated_on", "Simulated on", "Datetime", reqd=1),
    field("walkthrough", "Walkthrough result", "Long Text", read_only=1,
          description="Illustrative workflow captured at simulation time; "
                      "not a live infrastructure connection."),
    field("notes", "Notes", "Small Text"),
], title_field="simulation_title", editors=(IT, RISK), readers=(AUDITOR,))

# ------------------------------------------------------- Phase 3: commercial SaaS layer

# Operator-managed: tenant roles may read their plan but never change it.
# Operators set plans with bench execute continuity360.subscription.set_plan.
define("C360 Subscription", [
    choice("plan", "Subscription plan", "Starter\nProfessional\nEnterprise",
           default="Enterprise", reqd=1,
           description="Managed centrally by the Continuity360 operator."),
    field("licensed_users", "Licensed users", "Int", default="25", reqd=1,
          description="Maximum enabled system users (excluding Administrator and Guest)."),
    field("valid_until", "Valid until", "Date",
          description="After this date the tenant falls back to Starter entitlements."),
    field("customer_reference", "Customer reference"),
], issingle=1, permissions=[
    {"role": ADMIN, "read": 1, "write": 0, "create": 0, "print": 1, "email": 0,
     "share": 0, "delete": 0},
    {"role": AUDITOR, "read": 1, "write": 0, "create": 0, "print": 1, "email": 0,
     "share": 0, "delete": 0},
])

define("C360 Branding", [
    field("display_name", "Display name",
          description="Shown in navigation and report branding instead of the company name."),
    field("primary_color", "Primary colour",
          description="Hex colour such as #0f6a53; themes navigation and report accents."),
    field("report_footer", "Report footer line",
          description="Printed in the attribution footer of every PDF report."),
    field("logo", "Logo", "Attach Image"),
], issingle=1, editors=(), readers=(RISK, IT, AUDITOR, EMPLOYEE, BCP_AUTHOR,
                                    BCP_MANAGER, BCP_EXECUTIVE))

define("C360 Integration Connection", [
    field("connection_name", "Connection name", reqd=1, in_list_view=1), company(),
    choice("provider", "Provider", "AWS\nAzure\nMicrosoft 365\nMonitoring",
           reqd=1, in_list_view=1),
    field("account_reference", "Account / tenant reference", reqd=1,
          description="AWS account id, Azure tenant id or equivalent. Never a secret."),
    field("credential", "API credential", "Password",
          description="Stored encrypted. Used by future live polling; manual inventory "
                      "import does not require it."),
    field("enabled", "Enabled", "Check", default="1", in_list_view=1),
    field("last_import", "Last inventory import", "Datetime", read_only=1, no_copy=1),
    field("notes", "Notes", "Small Text"),
], title_field="connection_name", editors=(IT,), readers=(AUDITOR,))

# Plan readers do not receive employee/contact-directory access independently.
for plan_type, editor in (("C360 Recovery Plan", IT), ("C360 Business Continuity Plan", BCP_AUTHOR)):
    for permission in DOCTYPES[plan_type]["permissions"]:
        if permission["role"] == ADMIN:
            permission.update(submit=1, cancel=1, amend=1)
        elif permission["role"] == editor:
            permission["amend"] = 1
        elif plan_type == "C360 Business Continuity Plan" and permission["role"] in (BCP_MANAGER, BCP_EXECUTIVE):
            permission["create"] = 0
            if permission["role"] == BCP_EXECUTIVE:
                permission["submit"] = 1
