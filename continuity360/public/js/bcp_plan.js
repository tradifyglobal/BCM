$(document).on("app_ready", () => {
    frappe.require("form.bundle.js", () => {
        function addSnapshotButton(frm) {
            const permissions = frappe.perm.get_perm(frm.doctype)[0];
            if (!frm.is_new() && frm.doc.docstatus === 2 && permissions.amend && permissions.create) {
                frm.add_custom_button(__("Create amendment"), () => frm.amend_doc());
            }
            if (!frm.is_new() && [1, 2].includes(frm.doc.docstatus)) {
                for (const [label, format] of [[__("PDF"), "pdf"], [__("Word (DOCX)"), "docx"]]) {
                    frm.add_custom_button(label, () => {
                        const args = new URLSearchParams({plan_name: frm.doc.name, file_format: format});
                        window.open(`/api/method/continuity360.bcp_export.download_approved_plan?${args}`, "_blank", "noopener");
                    }, __("Download approved plan"));
                }
                frm.add_custom_button(__("View approved snapshot"), async () => {
                    const { message } = await frappe.call({
                        method: "continuity360.bcp_snapshot.get_approved_snapshot",
                        args: { plan_name: frm.doc.name },
                    });
                    const content = frappe.utils.escape_html(JSON.stringify(message, null, 2));
                    frappe.msgprint({
                        title: __("Approved snapshot"),
                        message: `<p>${frappe.utils.escape_html(__(
                            "This is the approval-time snapshot. Open linked contacts to see their current details."
                        ))}</p><pre style="white-space:pre-wrap;max-height:60vh;overflow:auto">${content}</pre>`,
                        wide: true,
                    });
                });
            }
        }
        async function addDistributionButton(frm) {
            if (frm.is_new() || frm.doc.docstatus !== 1 || frm.doc.approval_status !== "Approved") return;
            frm.add_custom_button(__("Distribute approved plan"), async () => {
                const { message: audience } = await frappe.call({
                    method: "continuity360.bcp_distribution.get_distribution_audience",
                    args: { plan_name: frm.doc.name },
                });
                if (!audience.length) {
                    frappe.msgprint(__("No enabled internal stakeholders are linked to this plan."));
                    return;
                }
                const escape = frappe.utils.escape_html;
                let dialog;
                dialog = new frappe.ui.Dialog({
                    title: __("Distribute approved plan"),
                    fields: [{
                        fieldname: "recipients",
                        fieldtype: "MultiCheck",
                        label: __("Recipients identified from this plan"),
                        options: audience.map((person) => ({
                            label: `${escape(person.label)} (${escape(person.email || person.user)}) — ${escape(person.reason)}`,
                            value: person.user,
                        })),
                    }],
                    primary_action_label: __("Send securely"),
                    primary_action: async (values) => {
                        const selected = Array.isArray(values.recipients)
                            ? values.recipients
                            : (values.recipients ? [values.recipients] : []);
                        if (!selected.length) {
                            frappe.msgprint(__("Select at least one recipient."));
                            return;
                        }
                        const { message: result } = await frappe.call({
                            method: "continuity360.bcp_distribution.distribute_approved_plan",
                            args: { plan_name: frm.doc.name, recipients: selected },
                        });
                        dialog.hide();
                        frappe.show_alert({
                            message: __("Distributed to {0} recipients.", [result.recipient_count]),
                            indicator: "green",
                        });
                    },
                });
                dialog.show();
            });
        }
        frappe.ui.form.on("C360 Business Continuity Plan", {
            refresh(frm) {
                addSnapshotButton(frm);
                addDistributionButton(frm);
            },
        });
        if (window.cur_frm && window.cur_frm.doctype === "C360 Business Continuity Plan") {
            addSnapshotButton(window.cur_frm);
            addDistributionButton(window.cur_frm);
        }
    });
});
