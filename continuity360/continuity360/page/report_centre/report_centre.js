frappe.pages["report-centre"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Report Centre"), single_column: true });
    const content = $('<div class="c360-dashboard"></div>').appendTo(page.main);
    const escape = frappe.utils.escape_html;
    let selector;

    const REPORTS = [
        {method: "full_report", featured: true,
         title: __("Complete BCM Report"),
         description: __("One combined document: BIA, risk assessment, BCP, disaster recovery "
            + "and compliance chapters with page numbers throughout.")},
        {method: "bia_report", title: __("Business Impact Analysis (BIA) Report"),
         description: __("Processes with criticality, RTO/RPO/MTPD, workarounds and full impact assessments.")},
        {method: "risk_report", title: __("Risk Assessment Report"),
         description: __("Risk register with inherent and residual scoring, rationale and all treatments.")},
        {method: "bcp_report", title: __("Business Continuity Plan (BCP) Report"),
         description: __("Every plan with scope, strategies, teams, procedures, approvals and acknowledgements.")},
        {method: "dr_report", title: __("Disaster Recovery (DR) Report"),
         description: __("Recovery plans with targets, contacts and step-by-step procedures.")},
        {method: "testing_report", title: __("Testing and Exercise Report"),
         description: __("Exercises with scenarios, objectives, participants, results, "
            + "lessons learned and corrective actions.")},
        {method: "incident_report", title: __("Incident and Crisis Report"),
         description: __("Incidents with severity, escalation chains and timelines, plus "
            + "crisis events with decision logs and communications.")},
        {method: "infrastructure_report", title: __("Infrastructure Report"),
         description: __("Applications, servers, databases, dependency map and illustrative "
            + "outage simulations.")},
        {method: "compliance_report", title: __("Compliance Control Report"),
         description: __("Controls by framework with status, owners, evidence and review dates. "
            + "Controls are organisation-wide regardless of the selected department.")},
    ];

    function render() {
        content.html(`
            <div class="c360-heading"><h3>${escape(__("Detailed PDF reports"))}</h3>
                <span>${escape(__("The department selected above applies to every report. "
                    + "Each report includes only records visible to you."))}</span></div>
            <div class="c360-report-grid">${REPORTS.map((report) => `
                <section class="c360-panel c360-report-card${report.featured ? " c360-report-featured" : ""}">
                    <h3>${escape(report.title)}</h3>
                    <p>${escape(report.description)}</p>
                    <button class="btn ${report.featured ? "btn-primary" : "btn-default"} btn-sm"
                        data-method="${escape(report.method)}">
                        ${escape(__("Download PDF"))}
                    </button>
                </section>`).join("")}</div>`);
        content.find("button[data-method]").on("click", function () {
            const args = new URLSearchParams();
            const department = selector && selector.get_value();
            if (department) args.set("department", department);
            const query = args.toString();
            window.open(
                `/api/method/continuity360.reports.${this.dataset.method}${query ? "?" + query : ""}`,
                "_blank", "noopener");
        });
    }

    async function load() {
        let departments = [];
        try {
            departments = await frappe.db.get_list("C360 Department", {
                fields: ["name", "department_name"], order_by: "department_name asc", limit: 0,
            });
        } catch (error) {
            console.error("Continuity360 department list failed", error);
        }
        selector = page.add_field({
            fieldname: "department", fieldtype: "Select", label: __("Department"),
            options: [{label: __("All departments"), value: ""},
                      ...departments.map((d) => ({label: d.department_name, value: d.name}))],
        });
        render();
    }

    load();
};
