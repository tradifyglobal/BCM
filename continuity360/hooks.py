app_name = "continuity360"
app_title = "Continuity360"
app_publisher = "Continuity360"
app_description = "Business continuity management and recovery intelligence"
app_license = "Proprietary"
app_home = "/desk/continuity360"

# The version query forces browsers to refetch these unversioned assets after a release.
ASSET_VERSION = "20261120-2"
app_include_js = [
    f"/assets/continuity360/js/continuity360.js?v={ASSET_VERSION}",
    f"/assets/continuity360/js/bcp_plan.js?v={ASSET_VERSION}",
    f"/assets/continuity360/js/scale_picker.js?v={ASSET_VERSION}",
    f"/assets/continuity360/js/call_tree.js?v={ASSET_VERSION}",
]
app_include_css = [f"/assets/continuity360/css/continuity360.css?v={ASSET_VERSION}"]

after_install = "continuity360.install.after_install"
after_migrate = "continuity360.install.after_migrate"

scheduler_events = {"daily": ["continuity360.bcp_reminders.send_due_reminders"]}

doc_events = {
    "C360 Risk": {"validate": "continuity360.validation.validate_risk"},
    "C360 Risk Assessment": {"validate": "continuity360.validation.validate_assessment"},
    "C360 Business Process": {"validate": "continuity360.validation.validate_process"},
    "C360 Impact Assessment": {"validate": "continuity360.validation.validate_impact"},
    "C360 Risk Treatment": {"validate": "continuity360.validation.validate_treatment"},
    "C360 Recovery Plan": {
        "validate": "continuity360.validation.validate_plan",
        "before_submit": "continuity360.validation.approve_plan",
    },
    "C360 Business Continuity Plan": {
        "validate": "continuity360.validation.validate_bcp",
        "before_submit": "continuity360.validation.approve_bcp",
    },
    "C360 BCP Recovery Team": {"validate": "continuity360.validation.validate_bcp_team"},
    "C360 BCP Procedure": {"validate": "continuity360.validation.validate_bcp_procedure"},
    "C360 BC Exercise": {"validate": "continuity360.validation.validate_exercise"},
    "C360 Corrective Action": {"validate": "continuity360.validation.validate_corrective_action"},
    "C360 Call Tree": {"validate": "continuity360.validation.validate_call_tree"},
    "C360 Incident": {
        "validate": "continuity360.validation.validate_incident",
        "after_insert": "continuity360.validation.notify_incident",
        "before_insert": "continuity360.subscription.enforce_module",
    },
    "C360 Crisis Event": {
        "validate": "continuity360.validation.validate_crisis",
        "before_insert": "continuity360.subscription.enforce_module",
    },
    "C360 Communication Plan": {"before_insert": "continuity360.subscription.enforce_module"},
    "C360 Application": {
        "validate": "continuity360.validation.validate_application",
        "before_insert": "continuity360.subscription.enforce_module",
    },
    "C360 Server": {"before_insert": "continuity360.subscription.enforce_module"},
    "C360 Database Instance": {
        "validate": "continuity360.validation.validate_database_instance",
        "before_insert": "continuity360.subscription.enforce_module",
    },
    "C360 IT Dependency": {
        "validate": "continuity360.validation.validate_dependency",
        "before_insert": "continuity360.subscription.enforce_module",
    },
    "C360 Outage Simulation": {
        "validate": "continuity360.validation.validate_simulation",
        "before_insert": "continuity360.subscription.enforce_module",
    },
    "C360 Integration Connection": {
        "validate": "continuity360.integrations.validate_connection",
        "before_insert": "continuity360.subscription.enforce_module",
    },
    "C360 Branding": {"validate": "continuity360.subscription.validate_branding"},
    "User": {"validate": "continuity360.subscription.enforce_seats"},
    "C360 Department": {"validate": "continuity360.validation.validate_company_links"},
    "C360 Employee": {"validate": "continuity360.validation.validate_company_links"},
    "C360 Location": {"validate": "continuity360.validation.validate_company_links"},
}
