frappe.pages["bcp-distribution"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("BCP Plan Distribution"),
        single_column: true,
    });
    const content = $('<div class="c360-dashboard"></div>').appendTo(page.main);
    const escape = frappe.utils.escape_html;
    const distribution = new URLSearchParams(window.location.search).get("distribution");

    function render(data) {
        const plan = data.plan || {};
        const details = JSON.stringify({
            approved_on: plan.approved_on,
            scope: plan.scope,
            activation_criteria: plan.activation_criteria,
            continuity_procedures: plan.continuity_procedures,
            communication_procedures: plan.communication_procedures,
            review_date: plan.review_date,
            linked_records: data.records,
        }, null, 2);
        const acknowledged = data.distribution.acknowledged_on;
        content.html(`
            <section class="c360-panel">
                <h3>${escape(plan.plan_title || __("Business continuity plan"))}</h3>
                <p>${escape(__("Version"))}: ${escape(plan.plan_version || __("Unnumbered legacy approval"))}
                    &middot; ${escape(__("Current status"))}: ${escape(data.current_status || __("Unavailable"))}</p>
                <p>${escape(__("Approved plan snapshot"))} &middot; ${escape(data.captured_on)}</p>
                <p>${escape(__("This is the approved version distributed to your account."))}</p>
                ${data.current_status !== "Approved"
                    ? `<p role="alert">${escape(__("HISTORICAL PLAN - not an active approved plan."))}</p>` : ""}
                <p>${escape(__("Downloaded copies are uncontrolled and cannot be revoked. Check the online plan before use."))}</p>
                <p>
                    <a class="btn btn-default" data-format="pdf">${escape(__("Download PDF"))}</a>
                    <a class="btn btn-default" data-format="docx">${escape(__("Download Word (DOCX)"))}</a>
                </p>
                <pre style="white-space:pre-wrap;max-height:60vh;overflow:auto">${escape(details)}</pre>
                ${acknowledged
                    ? `<p role="status">${escape(__("Acknowledged on"))} ${escape(acknowledged)}</p>`
                    : `<button class="btn btn-primary" type="button" data-action="acknowledge">
                        ${escape(__("I acknowledge that I have read this plan and understand my responsibilities."))}
                    </button>`}
            </section>`);
        content.find("[data-format]").each(function () {
            const args = new URLSearchParams({
                distribution_name: distribution,
                file_format: this.dataset.format,
            });
            this.href = `/api/method/continuity360.bcp_export.download_distribution?${args}`;
            this.target = "_blank";
            this.rel = "noopener";
        });
        content.find('[data-action="acknowledge"]').on("click", async () => {
            const { message } = await frappe.call({
                method: "continuity360.bcp_distribution.acknowledge_distribution",
                args: { distribution_name: distribution },
            });
            data.distribution.acknowledged_on = message.acknowledged_on;
            render(data);
        });
    }

    async function load() {
        if (!distribution) {
            content.html(`<p role="alert">${escape(__("This distribution link is incomplete."))}</p>`);
            return;
        }
        content.html(`<p role="status">${escape(__("Loading the approved plan..."))}</p>`);
        try {
            const { message } = await frappe.call({
                method: "continuity360.bcp_distribution.open_distribution",
                args: { distribution_name: distribution },
            });
            render(message);
        } catch (error) {
            content.html(`<div class="c360-panel" role="alert">${escape(__(
                "This plan distribution is unavailable to your account. Contact the plan owner or a BCM Administrator."
            ))}</div>`);
            console.error("Continuity360 BCP distribution failed", error);
        }
    }

    load();
};
