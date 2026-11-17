frappe.pages["bcp-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: __("BCP Dashboard"), single_column: true });
    const content = $('<div class="c360-dashboard"></div>').appendTo(page.main);
    const escape = frappe.utils.escape_html;
    page.set_primary_action(__("Refresh"), load);

    async function load() {
        content.html(`<p role="status">${escape(__("Loading business continuity plans..."))}</p>`);
        try {
            const { message: data } = await frappe.call("continuity360.api.bcp_overview");
            const metrics = [
                ["Total plans", data.total],
                ["Reviews due in 30 days", data.due_for_review],
                ["Plans under approval", data.under_approval],
                ["Overdue reviews", data.overdue_review],
            ];
            const extras = [
                ["Plans tested (12 months)", data.tested_plans, "c360-bc-exercise"],
                ["Completed exercises (12 months)", data.exercises_completed, "c360-bc-exercise"],
                ["Open corrective actions", data.open_corrective_actions, "c360-corrective-action"],
            ];
            content.html(`
                <div class="c360-heading"><h3>${escape(__("Business continuity overview"))}</h3>
                    <span>${escape(__("Visible records"))} &middot; ${escape(data.as_of)}</span></div>
                <section class="c360-metrics">${metrics.map(([label, count]) => `
                    <a class="c360-metric" href="/desk/continuity360/c360-business-continuity-plan">
                        <span>${escape(__(label))}</span><strong>${Number(count)}</strong>
                        <small>${escape(__("View plans"))} &rarr;</small>
                    </a>`).join("")}</section>
                <section class="c360-panel">
                    <h3>${escape(__("Testing and corrective actions"))}</h3>
                    <section class="c360-metrics">${extras.map(([label, count, route]) => count === null ? `
                        <span class="c360-metric"><span>${escape(__(label))}</span>
                            <strong>&ndash;</strong><small>${escape(__("Not visible to your role"))}</small></span>` : `
                        <a class="c360-metric" href="/desk/continuity360/${route}">
                            <span>${escape(__(label))}</span><strong>${Number(count)}</strong>
                            <small>${escape(__("View records"))} &rarr;</small>
                        </a>`).join("")}</section>
                    <p>${escape(__("Expired plans are not tracked separately from overdue reviews yet."))}</p>
                </section>`);
        } catch (error) {
            content.html(`<div class="c360-panel" role="alert">${escape(__(
                "Unable to load the BCP overview. Check your permissions and connection, then select Refresh."
            ))}</div>`);
            console.error("Continuity360 BCP overview failed", error);
        }
    }
    wrapper.c360_bcp_load = load;
};

frappe.pages["bcp-dashboard"].on_page_show = function (wrapper) {
    wrapper.c360_bcp_load();
};
