frappe.pages["recovery-intelligence"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper, title: __("Recovery Intelligence"), single_column: true,
    });
    const esc = frappe.utils.escape_html;
    const content = $('<div class="c360-dashboard"></div>').appendTo(page.main);
    const typeField = page.add_field({
        fieldname: "component_type", label: __("Component type"), fieldtype: "Select",
        options: ["Application", "Server", "Database"].join("\n"), default: "Application",
        change: loadComponents,
    });
    const componentField = page.add_field({
        fieldname: "component", label: __("Component"), fieldtype: "Select", options: "",
    });
    page.set_primary_action(__("Simulate outage"), run);
    let catalogue = null;

    async function loadComponents() {
        if (!catalogue) {
            catalogue = (await frappe.call("continuity360.recovery_intelligence.components")).message;
        }
        const rows = catalogue[typeField.get_value()] || [];
        componentField.df.options = rows.map((row) => row.name).join("\n");
        componentField.refresh();
        if (rows.length) componentField.set_value(rows[0].name);
        const labels = {};
        rows.forEach((row) => { labels[row.name] = row.title; });
        componentField.$input.find("option").each(function () {
            if (labels[this.value]) this.textContent = labels[this.value];
        });
    }

    function badge(text) {
        return `<span class="indicator-pill orange">${esc(text)}</span>`;
    }

    function listOrNone(items, render) {
        if (!items || !items.length) {
            return `<p class="text-muted">${esc(__("None recorded."))}</p>`;
        }
        return `<ul>${items.map(render).join("")}</ul>`;
    }

    function docLink(doctype, name, label) {
        const route = doctype.toLowerCase().replace(/ /g, "-");
        return `<a href="/desk/${route}/${encodeURIComponent(name)}">${esc(label || name)}</a>`;
    }

    async function run() {
        const target = componentField.get_value();
        if (!target) {
            frappe.msgprint(__("Add infrastructure components first."));
            return;
        }
        content.html(`<p role="status">${esc(__("Simulating outage..."))}</p>`);
        const { message: data } = await frappe.call("continuity360.recovery_intelligence.simulate", {
            target_type: typeField.get_value(), target, save: 1,
        });
        const minutes = (value) => value == null ? "" : ` (RTO ${value}m)`;
        const steps = [
            [__("1. Incident detected"), `<p>${esc(__("Simulated outage of"))} <b>${esc(data.target.title)}</b>
                (${esc(data.target.type)}). ${badge(__("Illustrative workflow - no live infrastructure connection"))}</p>`],
            [__("2. Business impact analysis"), `
                <h5>${esc(__("Affected applications"))}</h5>
                ${listOrNone(data.affected_applications, (a) =>
                    `<li>${docLink("C360 Application", a.name, a.application_name)} — ${esc(a.criticality)} / ${esc(a.hosting)}</li>`)}
                <h5>${esc(__("Affected business processes"))}</h5>
                ${listOrNone(data.affected_processes, (p) =>
                    `<li>${docLink("C360 Business Process", p.name, p.process_name)} — ${esc(p.department_name || "")},
                     ${esc(p.criticality)}${minutes(p.rto_minutes)}</li>`)}
                <p><b>${esc(__("Departments impacted"))}:</b> ${esc((data.affected_departments || []).join(", ") || __("None recorded."))}</p>`],
            [__("3. Recovery plan activated"), `
                <h5>${esc(__("Business continuity plans"))}</h5>
                ${listOrNone(data.business_continuity_plans, (p) =>
                    `<li>${docLink("C360 Business Continuity Plan", p.name, p.plan_title)} — v${esc(p.plan_version || "")} ${esc(p.approval_status)}</li>`)}
                <h5>${esc(__("Call trees to activate"))}</h5>
                ${listOrNone(data.call_trees, (t) => `<li>${docLink("C360 Call Tree", t.name, t.tree_name)}</li>`)}`],
            [__("4. Recovery procedure"), `
                <h5>${esc(__("Approved recovery runbooks and targets"))}</h5>
                ${listOrNone(data.recovery_plans, (p) =>
                    `<li>${docLink("C360 Recovery Plan", p.name, p.plan_title)} — ${esc(p.approval_status)},
                     RTO ${Number(p.rto_minutes)}m / RPO ${Number(p.rpo_minutes)}m</li>`)}`],
            [__("5. Recovery validation"), `<p>${esc(__(
                "Record service restoration and data validation as an incident with a resolution summary, then validate against the recovery targets above."))}</p>`],
            [__("6. Post-incident report"), `<p>${esc(__(
                "This walkthrough was saved as"))} ${data.simulation_record
                    ? docLink("C360 Outage Simulation", data.simulation_record, data.simulation_record)
                    : esc(__("an unsaved simulation"))}.
                ${esc(__("Use the incident timeline and testing module to capture actions and lessons learned."))}</p>`],
        ];
        content.html(steps.map(([title, body]) => `
            <section class="c360-panel" style="margin-bottom:12px">
                <h3>${esc(title)}</h3>${body}
            </section>`).join(""));
    }

    loadComponents();
    content.html(`<div class="c360-panel"><p>${esc(__(
        "Pick a component and select Simulate outage to walk through detection, impact, plan activation, recovery and reporting. Simulations are illustrative and are stored as Outage Simulation records."))}</p></div>`);
};
