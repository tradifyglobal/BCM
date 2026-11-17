frappe.pages["continuity360"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper, title: __("Continuity360"), single_column: true,
    });
    page.set_primary_action(__("Refresh"), () => load());
    page.set_secondary_action(__("Download PDF"), () => {
        window.open("/api/method/continuity360.api.download_report", "_blank", "noopener");
    });
    const content = $('<div class="c360-dashboard"></div>').appendTo(page.main);
    const escape = frappe.utils.escape_html;
    const route = (doctype, name) => {
        const slug = doctype.toLowerCase().replaceAll(" ", "-");
        return `/desk/continuity360/${slug}/${encodeURIComponent(name)}`;
    };
    const empty = (message) => `<p class="c360-empty">${escape(__(message))}</p>`;
    const table = (heads, rows) => `<div class="c360-table-wrap"><table class="c360-table"><thead><tr>
        ${heads.map((h) => `<th scope="col">${escape(__(h))}</th>`).join("")}
        </tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
    const chart = (rows, key, message) => {
        if (!rows.length) return empty(message);
        const order = ["Critical", "High", "Medium", "Low"];
        const sorted = [...rows].sort((a, b) => {
            const position = (value) => order.includes(value) ? order.indexOf(value) : order.length;
            return position(a[key]) - position(b[key]);
        });
        const max = Math.max(...sorted.map((row) => Number(row.total)), 1);
        return `<ul class="c360-chart">${sorted.map((row) => {
            const label = row[key] || "Unspecified";
            const count = Number(row.total);
            return `<li class="c360-chart-row">
                <span class="c360-chart-label">${escape(__(label))}</span>
                <span class="c360-chart-track" aria-hidden="true"><span class="c360-chart-bar"
                    style="width:${count / max * 100}%"></span></span>
                <strong>${count}</strong>
            </li>`;
        }).join("")}</ul>`;
    };

    async function load() {
        content.html(`<p role="status">${escape(__("Loading your continuity overview..."))}</p>`);
        try {
            const { message: data } = await frappe.call("continuity360.api.overview");
            const cards = data.metrics.filter((m) => m.value !== null).map((m) => `
                <a class="c360-metric" href="/desk/continuity360/${m.doctype.toLowerCase().replaceAll(" ", "-")}">
                    <span>${escape(__(m.label))}</span><strong>${Number(m.value)}</strong>
                    <small>${escape(__("View records"))} &rarr;</small>
                </a>`).join("");
            const riskRows = data.risks.map((r) => `<tr><td><a href="${route("C360 Risk", r.name)}">
                ${escape(r.risk_title)}</a></td><td>${Number(r.score)}</td>
                <td><span class="c360-rating c360-${r.rating.toLowerCase()}">${escape(__(r.rating))}</span></td></tr>`);
            const processRows = data.processes.map((p) => `<tr><td><a href="${route("C360 Business Process", p.name)}">
                ${escape(p.process_name)}</a></td><td>${Number(p.rto_minutes)} min</td>
                <td>${Number(p.rpo_minutes)} min</td></tr>`);
            const charts = [];
            if (data.risk_distribution !== null) {
                charts.push(`<section class="c360-panel c360-chart-panel">
                    <h3>${escape(__("Open risks by rating"))}</h3>
                    <p class="c360-muted">${escape(__("Open and treating risks visible to you"))}</p>
                    ${chart(data.risk_distribution, "rating", "No open risks to chart yet.")}
                </section>`);
            }
            if (data.process_distribution !== null) {
                charts.push(`<section class="c360-panel c360-chart-panel">
                    <h3>${escape(__("Processes by criticality"))}</h3>
                    <p class="c360-muted">${escape(__("Business processes visible to you"))}</p>
                    ${chart(data.process_distribution, "criticality", "No business processes to chart yet.")}
                </section>`);
            }
            const cells = [];
            for (let likelihood = 5; likelihood >= 1; likelihood--) {
                for (let impact = 1; impact <= 5; impact++) {
                    const count = data.heatmap.find((c) => c.likelihood === likelihood && c.impact === impact);
                    const score = likelihood * impact;
                    const rating = score >= 20 ? "critical" : score >= 12 ? "high" : score >= 6 ? "medium" : "low";
                    cells.push(`<div class="c360-heat-cell c360-${rating}"
                        aria-label="${escape(__("Likelihood"))} ${likelihood}, ${escape(__("Impact"))} ${impact}: ${Number(count?.total || 0)}">
                        ${Number(count?.total || 0)}</div>`);
                }
            }
            content.html(`
                <section class="c360-hero">
                    <div><span class="c360-eyebrow">${escape(__("BUSINESS CONTINUITY WORKSPACE"))}</span>
                    <h2>${escape(__("Plan confidently. Build resilience."))}</h2>
                    <p>${escape(__("Connect your people, risks and critical processes with approved recovery plans."))}</p>
                    <a class="c360-hero-link" href="/desk/continuity360/c360-recovery-plan">${escape(__("Explore recovery plans"))} &rarr;</a></div>
                    <div class="c360-orbit" aria-hidden="true"><span>360</span></div>
                </section>
                <div class="c360-heading"><h3>${escape(__("Your resilience overview"))}</h3>
                    <span>${escape(__("Live tenant records"))} &middot; ${escape(data.as_of)}</span></div>
                <section class="c360-metrics">${cards}</section>
                ${charts.length ? `<div class="c360-panels c360-charts">${charts.join("")}</div>` : ""}
                <div class="c360-panels">
                    <section class="c360-panel"><div class="c360-heading"><h3>${escape(__("Priority risks"))}</h3>
                        <a href="/desk/continuity360/c360-risk">${escape(__("Risk register"))} &rarr;</a></div>
                        ${riskRows.length ? table(["Risk", "Score", "Rating"], riskRows) : empty("No open risks visible. Start with your risk register.")}</section>
                    <section class="c360-panel"><div class="c360-heading"><h3>${escape(__("Critical processes"))}</h3>
                        <a href="/desk/continuity360/c360-business-process">${escape(__("Business impact"))} &rarr;</a></div>
                        ${processRows.length ? table(["Business process", "RTO", "RPO"], processRows) : empty("No processes visible. Define your business recovery priorities.")}</section>
                </div>
                <div class="c360-panels">
                    ${data.risk_distribution !== null ? `<section class="c360-panel"><h3>${escape(__("Risk exposure"))}</h3>
                        <p class="c360-muted">${escape(__("Open risks by likelihood (5 to 1) and impact (1 to 5)"))}</p>
                        <div class="c360-heatmap">${cells.join("")}</div>
                        <p class="c360-muted">${escape(__("Low 1-5 / Medium 6-11 / High 12-19 / Critical 20-25"))}</p></section>` : ""}
                    <section class="c360-panel c360-next"><span class="c360-eyebrow">${escape(__("ON THE ROADMAP"))}</span>
                        <h3>${escape(__("From business impact to recovery intelligence"))}</h3>
                        <p>${escape(__("Business service → Process → Application → Infrastructure → Recovery"))}</p>
                        <p>${escape(__("Infrastructure discovery, incident simulations and cloud connectors arrive in later phases. No live infrastructure is connected."))}</p>
                        <span class="c360-phase">${escape(__("Phase 1 · BCM foundation"))}</span></section>
                </div>`);
        } catch (error) {
            content.html(`<div class="c360-panel" role="alert">${escape(__(
                "Unable to load the overview. Check your permissions and connection, then select Refresh."
            ))}</div>`);
            console.error("Continuity360 overview failed", error);
        }
    }
    wrapper.c360_load = load;
};

frappe.pages["continuity360"].on_page_show = function (wrapper) {
    wrapper.c360_load();
};
