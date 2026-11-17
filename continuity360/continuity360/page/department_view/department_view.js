frappe.pages["department-view"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Department View"), single_column: true });
    const content = $('<div class="c360-dashboard"></div>').appendTo(page.main);
    const escape = frappe.utils.escape_html;
    const listRoute = (doctype) => "/desk/" + frappe.router.slug(doctype);
    const formRoute = (doctype, name) => listRoute(doctype) + "/" + encodeURIComponent(name);

    function link(doctype, name, label) {
        return `<a href="${formRoute(doctype, name)}">${escape(label || name)}</a>`;
    }

    function minutes(value) {
        if (value == null || value === "") return "";
        const amount = Number(value);
        if (amount === 0) return escape(__("None"));
        if (amount % 1440 === 0) return escape(__("{0}d", [amount / 1440]));
        if (amount % 60 === 0) return escape(__("{0}h", [amount / 60]));
        return escape(__("{0} min", [amount]));
    }

    const SECTIONS = [
        {key: "processes", title: __("Business processes (BIA)"), doctype: "C360 Business Process",
         filter: (dept) => `?department=${encodeURIComponent(dept)}`,
         columns: [[__("Process"), (r) => link("C360 Business Process", r.name, r.process_name)],
                   [__("Criticality"), (r) => escape(r.criticality || "")],
                   [__("RTO"), (r) => minutes(r.rto_minutes)],
                   [__("RPO"), (r) => minutes(r.rpo_minutes)],
                   [__("MTPD"), (r) => minutes(r.mtpd_minutes)]]},
        {key: "impact_assessments", title: __("Impact assessments"), doctype: "C360 Impact Assessment",
         columns: [[__("Assessment"), (r) => link("C360 Impact Assessment", r.name, r.name)],
                   [__("Process"), (r) => escape(r.business_process)],
                   [__("Highest impact"), (r) => escape(String(r.overall_impact))],
                   [__("Date"), (r) => escape(r.assessment_date || "")]]},
        {key: "risks", title: __("Risks"), doctype: "C360 Risk",
         columns: [[__("Risk"), (r) => link("C360 Risk", r.name, r.risk_title)],
                   [__("Score"), (r) => escape(String(r.score))],
                   [__("Rating"), (r) => escape(r.rating || "")],
                   [__("Status"), (r) => escape(r.status || "")]]},
        {key: "risk_assessments", title: __("Risk assessments (residual)"), doctype: "C360 Risk Assessment",
         columns: [[__("Assessment"), (r) => link("C360 Risk Assessment", r.name, r.name)],
                   [__("Risk"), (r) => escape(r.risk)],
                   [__("Residual score"), (r) => escape(String(r.residual_score))],
                   [__("Residual rating"), (r) => escape(r.residual_rating || "")]]},
        {key: "treatments", title: __("Risk treatments"), doctype: "C360 Risk Treatment",
         columns: [[__("Treatment"), (r) => link("C360 Risk Treatment", r.name, r.treatment_title)],
                   [__("Status"), (r) => escape(r.status || "")],
                   [__("Due"), (r) => escape(r.due_date || "")]]},
        {key: "bcps", title: __("Business continuity plans (BCP)"), doctype: "C360 Business Continuity Plan",
         columns: [[__("Plan"), (r) => link("C360 Business Continuity Plan", r.name, r.plan_title)],
                   [__("Version"), (r) => escape(r.plan_version || "")],
                   [__("Status"), (r) => escape(r.approval_status || "")],
                   [__("Next review"), (r) => escape(r.review_date || "")]]},
        {key: "recovery_plans", title: __("Disaster recovery plans"), doctype: "C360 Recovery Plan",
         columns: [[__("Plan"), (r) => link("C360 Recovery Plan", r.name, r.plan_title)],
                   [__("Status"), (r) => escape(r.approval_status || "")],
                   [__("RTO"), (r) => minutes(r.rto_minutes)],
                   [__("Next review"), (r) => escape(r.review_date || "")]]},
        {key: "employees", title: __("Employees"), doctype: "C360 Employee",
         filter: (dept) => `?department=${encodeURIComponent(dept)}`,
         columns: [[__("Employee"), (r) => link("C360 Employee", r.name, r.employee_name)],
                   [__("Email"), (r) => escape(r.email || "")],
                   [__("Phone"), (r) => escape(r.phone || "")]]},
    ];

    function renderSection(section, rows, department) {
        const more = section.filter
            ? `<a href="${listRoute(section.doctype)}${section.filter(department)}">${escape(__("Open list"))} &rarr;</a>`
            : "";
        let body;
        if (rows === null || rows === undefined) {
            body = `<p>${escape(__("Your role cannot view these records."))}</p>`;
        } else if (!rows.length) {
            body = `<p>${escape(__("No records for this department yet."))}</p>`;
        } else {
            body = `<table class="c360-table"><thead><tr>
                ${section.columns.map(([label]) => `<th>${escape(label)}</th>`).join("")}
                </tr></thead><tbody>
                ${rows.map((row) => `<tr>${section.columns.map(([, cell]) =>
                    `<td>${cell(row)}</td>`).join("")}</tr>`).join("")}
                </tbody></table>`;
        }
        return `<section class="c360-panel c360-dept-panel">
            <div class="c360-dept-panel-head"><h3>${escape(section.title)}
            <span class="c360-dept-count">${rows ? rows.length : ""}</span></h3>${more}</div>
            ${body}</section>`;
    }

    async function show(department) {
        if (!department) {
            content.html(`<section class="c360-panel"><p>${escape(
                __("Choose a department above to see everything recorded for it."))}</p></section>`);
            return;
        }
        content.html(`<p role="status">${escape(__("Loading department records..."))}</p>`);
        try {
            const { message: data } = await frappe.call({
                method: "continuity360.api.department_view", args: { department },
            });
            const owner = data.department.responsible_user;
            content.html(`
                <div class="c360-heading">
                    <h3>${escape(data.department.department_name)}</h3>
                    <span>${owner ? escape(__("Responsible: {0}", [owner])) + " &middot; " : ""}${escape(data.as_of)}</span>
                </div>
                ${SECTIONS.map((section) => renderSection(section, data[section.key], department)).join("")}`);
        } catch (error) {
            content.html(`<div class="c360-panel" role="alert">${escape(__(
                "Unable to load this department. Check your permissions and connection."))}</div>`);
            console.error("Continuity360 department view failed", error);
        }
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
        const selector = page.add_field({
            fieldname: "department", fieldtype: "Select", label: __("Department"),
            options: [{label: __("Select a department..."), value: ""},
                      ...departments.map((d) => ({label: d.department_name, value: d.name}))],
            change() { show(selector.get_value()); },
        });
        const preset = frappe.utils.get_url_arg("department");
        if (preset && departments.some((d) => d.name === preset)) {
            selector.set_value(preset);
            show(preset);
        } else if (departments.length === 1) {
            selector.set_value(departments[0].name);
            show(departments[0].name);
        } else {
            show("");
        }
    }

    load();
};
