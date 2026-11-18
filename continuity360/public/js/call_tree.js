/* Live cascade preview on the Call Tree form. */
(() => {
    "use strict";

    async function render(frm) {
        if (!frm.fields_dict || frm.doc.doctype !== "C360 Call Tree") return;
        let wrapper = frm.$wrapper.find(".c360-call-tree-preview");
        if (!wrapper.length) {
            wrapper = $('<div class="c360-call-tree-preview form-dashboard-section"></div>')
                .prependTo(frm.$wrapper.find(".form-page").first());
        }
        const members = (frm.doc.members || []).filter((row) => row.contact);
        if (!members.length) {
            wrapper.html(`<p class="text-muted">${frappe.utils.escape_html(
                __("Add cascade members to preview the call tree."))}</p>`);
            return;
        }
        const names = {};
        (await frappe.db.get_list("C360 Emergency Contact",
            {fields: ["name", "contact_name", "phone"], limit: 0})
        ).forEach((row) => { names[row.name] = row; });
        const children = {};
        const contacts = new Set(members.map((row) => row.contact));
        const roots = [];
        members.forEach((row) => {
            if (row.called_by && contacts.has(row.called_by) && row.called_by !== row.contact) {
                (children[row.called_by] = children[row.called_by] || []).push(row);
            } else {
                roots.push(row);
            }
        });
        const esc = frappe.utils.escape_html;
        const seen = new Set();
        function branch(row, level) {
            if (seen.has(row.contact)) return "";
            seen.add(row.contact);
            const meta = names[row.contact] || {};
            const label = esc(meta.contact_name || row.contact);
            const phone = meta.phone ? ` <span class="text-muted">${esc(meta.phone)}</span>` : "";
            const role = row.tree_role ? ` <span class="text-muted">&middot; ${esc(row.tree_role)}</span>` : "";
            const marker = level ? "&#8627; " : "&#9742; ";
            let html = `<div style="margin-left:${level * 26}px;padding:2px 0">${marker}<b>${label}</b>${role}${phone}</div>`;
            (children[row.contact] || []).forEach((next) => { html += branch(next, level + 1); });
            return html;
        }
        let html = `<h5 style="margin:4px 0 8px">${esc(__("Cascade preview"))}</h5>`;
        roots.forEach((row) => { html += branch(row, 0); });
        const overloaded = Object.entries(children).filter(([, rows]) => rows.length > 7);
        if (overloaded.length) {
            html += `<p class="text-warning" style="margin-top:8px">&#9888; ${esc(__(
                "Span of control:"))} ${overloaded.map(([caller, rows]) =>
                `${esc((names[caller] || {}).contact_name || caller)} ${esc(__("calls"))} ${rows.length}`)
                .join(", ")} — ${esc(__("good practice is three to seven per caller."))}</p>`;
        }
        const unreachable = members.filter((row) => !seen.has(row.contact));
        if (unreachable.length) {
            html += `<p class="text-danger" style="margin-top:8px">${esc(__(
                "Not reachable from an initiator:"))} ${unreachable.map((row) =>
                esc((names[row.contact] || {}).contact_name || row.contact)).join(", ")}</p>`;
        }
        wrapper.html(html);
    }

    frappe.ui.form.on("C360 Call Tree", {
        refresh: render,
        members_add: render,
        members_remove: render,
    });
    frappe.ui.form.on("C360 Call Tree Member", {
        contact: (frm) => render(frm),
        called_by: (frm) => render(frm),
        tree_role: (frm) => render(frm),
    });
})();
