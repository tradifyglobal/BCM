/* global frappe, __, $ */
(() => {
    const groups = [
        { label: "Overview", items: [["Dashboard", null, "continuity360"]] },
        { label: "Organisation", items: [
            ["Companies", "C360 Company"], ["Departments", "C360 Department"],
            ["Department View", "C360 Department", "department-view"],
            ["Locations", "C360 Location"], ["Employees", "C360 Employee"], ["Vendors", "C360 Vendor"],
        ] },
        { label: "Risk Management", items: [
            ["Risk Register", "C360 Risk"], ["Risk Assessments", "C360 Risk Assessment"],
            ["Risk Treatments", "C360 Risk Treatment"],
        ] },
        { label: "Business Impact Analysis", items: [
            ["Business Processes", "C360 Business Process"], ["Impact Assessments", "C360 Impact Assessment"],
        ] },
        { label: "Business Continuity Planning", items: [
            ["BCP Dashboard", "C360 Business Continuity Plan", "bcp-dashboard"],
            ["Business Continuity Plans", "C360 Business Continuity Plan"],
            ["Continuity Strategies", "C360 Continuity Strategy"],
            ["Recovery Teams", "C360 BCP Recovery Team"],
            ["Emergency Contacts", "C360 Emergency Contact"],
            ["Call Trees", "C360 Call Tree"],
            ["Continuity Procedures", "C360 BCP Procedure"],
        ] },
        { label: "Disaster Recovery", items: [
            ["Recovery Strategies", "C360 Recovery Strategy"], ["Recovery Plans", "C360 Recovery Plan"],
        ] },
        { label: "Testing & Exercises", items: [
            ["Exercises", "C360 BC Exercise"], ["Corrective Actions", "C360 Corrective Action"],
        ] },
        { label: "Incident & Crisis", items: [
            ["Incidents", "C360 Incident"], ["Crisis Events", "C360 Crisis Event"],
            ["Communication Plans", "C360 Communication Plan"],
        ] },
        { label: "Infrastructure", items: [
            ["Applications", "C360 Application"], ["Servers", "C360 Server"],
            ["Databases", "C360 Database Instance"], ["Dependencies", "C360 IT Dependency"],
            ["Recovery Intelligence", null, "recovery-intelligence"],
            ["Outage Simulations", "C360 Outage Simulation"],
        ] },
        { label: "Compliance", items: [["Control Register", "C360 Compliance Control"]] },
        { label: "Reports", items: [
            ["Report Centre", null, "report-centre"],
            ["Management Overview", null, "continuity360"],
        ] },
    ];
    const roles = ["BCM Administrator", "Risk Manager", "IT Manager", "Auditor", "Employee",
        "BCP Author", "BCP Manager Reviewer", "BCP Executive Approver"];
    const escape = (value) => frappe.utils.escape_html(__(value));
    const href = ([, doctype, page]) => page
        ? `/desk/${page}` : `/desk/continuity360/${doctype.toLowerCase().replaceAll(" ", "-")}`;

    $(document).on("app_ready", () => {
        if (!roles.some((role) => frappe.user.has_role(role))) return;
        const readable = frappe.boot.user.can_read || [];
        const visible = groups.map((group) => ({
            ...group, items: group.items.filter((item) => !item[1] || readable.includes(item[1])),
        })).filter((group) => group.items.length);
        const key = `continuity360.navigation.${frappe.session.user}`;
        const saved = window.localStorage.getItem(key);
        let mode = ["combined", "top", "sidebar"].includes(saved) ? saved : "combined";
        const link = (item) => `<a href="${href(item)}">${escape(item[0])}</a>`;
        const shell = document.createElement("div");
        shell.id = "c360-shell";
        shell.innerHTML = `
            <div class="c360-topbar">
                <a class="c360-brand" href="/desk/continuity360"><span class="c360-mark">C</span>Continuity<span>360</span></a>
                <nav aria-label="${escape("Continuity360 modules")}" class="c360-topnav">
                    ${visible.map((group, i) => `<div class="c360-dropdown">
                        <button type="button" aria-expanded="false" aria-controls="c360-menu-${i}">
                            ${escape(group.label)} <span aria-hidden="true">&#8964;</span></button>
                        <div id="c360-menu-${i}" class="c360-menu" hidden>${group.items.map(link).join("")}</div>
                    </div>`).join("")}
                </nav>
                <label class="c360-mode"><span class="sr-only">${escape("Navigation layout")}</span>
                    <select aria-label="${escape("Navigation layout")}">
                        <option value="combined">${escape("Top + sidebar")}</option>
                        <option value="top">${escape("Top navigation")}</option>
                        <option value="sidebar">${escape("Sidebar navigation")}</option>
                    </select>
                </label>
                <button type="button" class="c360-tool" data-c360-action="search">${escape("Search")}</button>
                <button type="button" class="c360-tool" data-c360-action="notification">${escape("Notifications")}</button>
            </div>
            <aside class="c360-sidebar" aria-label="${escape("Continuity360 sidebar")}">
                <div class="c360-sidebar-title">${escape("YOUR WORKSPACE")}</div>
                ${visible.map((group) => `<section><h2>${escape(group.label)}</h2>
                    ${group.items.map(link).join("")}</section>`).join("")}
                <div class="c360-sidebar-foot">${escape("Phase 2")}<br>${escape("Operational resilience")}</div>
            </aside>`;
        document.body.appendChild(shell);
        const topbar = shell.querySelector(".c360-topbar");
        const updateTopbarHeight = () => {
            document.body.style.setProperty("--c360-current-top", `${topbar.getBoundingClientRect().height}px`);
        };
        new ResizeObserver(updateTopbarHeight).observe(topbar);
        updateTopbarHeight();
        const nativeUserMenu = document.querySelector(".body-sidebar .dropdown-navbar-user");
        if (nativeUserMenu) {
            shell.querySelector(".c360-topbar").appendChild(nativeUserMenu);
            document.body.classList.add("c360-native-sidebar-replaced");
        }
        shell.querySelector('[data-c360-action="search"]').addEventListener("click", () => {
            document.querySelector('.body-sidebar [item-name="Search"] .item-anchor')?.click();
        });
        shell.querySelector('[data-c360-action="notification"]').addEventListener("click", () => {
            const panel = frappe.ui.sidebar_panels.get("notifications");
            if (panel) {
                panel.opts.trigger_selector = '.sidebar-notification, [data-c360-action="notification"]';
                panel.toggle();
            } else {
                console.error("Continuity360: notification panel is unavailable.");
            }
        });
        document.body.classList.add("c360-shell-active");
        const select = shell.querySelector("select");
        function applyMode() {
            document.body.dataset.c360Nav = mode;
            select.value = mode;
            shell.querySelectorAll(".c360-menu").forEach((menu) => { menu.hidden = true; });
            shell.querySelectorAll("[aria-expanded]").forEach((button) => button.setAttribute("aria-expanded", "false"));
        }
        select.addEventListener("change", () => {
            mode = select.value;
            window.localStorage.setItem(key, mode);
            applyMode();
        });
        shell.querySelectorAll(".c360-dropdown").forEach((dropdown) => {
            const button = dropdown.querySelector("button");
            const menu = dropdown.querySelector(".c360-menu");
            const close = () => { menu.hidden = true; button.setAttribute("aria-expanded", "false"); };
            const open = () => {
                shell.querySelectorAll(".c360-menu").forEach((other) => { other.hidden = true; });
                shell.querySelectorAll("[aria-expanded]").forEach((other) => other.setAttribute("aria-expanded", "false"));
                menu.hidden = false;
                button.setAttribute("aria-expanded", "true");
            };
            button.addEventListener("click", () => menu.hidden ? open() : close());
            dropdown.addEventListener("mouseleave", () => {
                if (!dropdown.contains(document.activeElement)) close();
            });
            dropdown.addEventListener("focusout", (event) => {
                if (!dropdown.contains(event.relatedTarget)) close();
            });
            dropdown.addEventListener("keydown", (event) => {
                if (event.key === "Escape") { close(); button.focus(); }
            });
            menu.addEventListener("click", close);
        });
        function highlight() {
            shell.querySelectorAll(".c360-sidebar a[href], .c360-menu a[href], .c360-brand[href]").forEach((anchor) => {
                const active = window.location.pathname === new URL(anchor.href).pathname;
                anchor.classList.toggle("c360-active", active);
                if (active) anchor.setAttribute("aria-current", "page");
                else anchor.removeAttribute("aria-current");
            });
        }
        frappe.router.on("change", highlight);
        applyMode();
        highlight();
    });
})();
