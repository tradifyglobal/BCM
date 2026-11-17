$(document).on("app_ready", () => {
    frappe.require("form.bundle.js", () => {
        const GRADIENT = ["#2f9e44", "#86b81b", "#f3c300", "#f08c00", "#d9342b"];
        const LIKELIHOOD = [__("Rare"), __("Unlikely"), __("Possible"), __("Likely"), __("Almost certain")];
        const IMPACT = [__("Minimal"), __("Minor"), __("Moderate"), __("Major"), __("Severe")];

        function levelCells(labels) {
            return [1, 2, 3, 4, 5].map((value, index) => ({
                value, text: String(value), color: GRADIENT[index], hint: labels[index],
            }));
        }

        function minutesText(minutes) {
            if (minutes === 0) return __("None");
            if (minutes % 10080 === 0) return __("{0}w", [minutes / 10080]);
            if (minutes % 1440 === 0) return __("{0}d", [minutes / 1440]);
            if (minutes % 60 === 0) return __("{0}h", [minutes / 60]);
            return __("{0}m", [minutes]);
        }

        function durationCells(values) {
            const last = values.length - 1;
            return values.map((value, index) => ({
                value, text: minutesText(value),
                color: GRADIENT[Math.round((index / last) * (GRADIENT.length - 1))],
                hint: __("{0} minutes", [value]),
            }));
        }

        const TARGETS = [15, 30, 60, 120, 240, 480, 1440, 2880, 4320, 10080];
        const SCALES = {
            "C360 Risk": {likelihood: levelCells(LIKELIHOOD), impact: levelCells(IMPACT)},
            "C360 Risk Assessment": {
                residual_likelihood: levelCells(LIKELIHOOD),
                residual_impact: levelCells(IMPACT),
            },
            "C360 Impact Assessment": {
                financial_impact: levelCells(IMPACT),
                operational_impact: levelCells(IMPACT),
                reputational_impact: levelCells(IMPACT),
                regulatory_impact: levelCells(IMPACT),
            },
            "C360 Business Process": {
                rto_minutes: durationCells(TARGETS),
                rpo_minutes: durationCells([0, ...TARGETS.slice(0, 9)]),
                mtpd_minutes: durationCells([60, 240, 480, 1440, 2880, 4320, 10080, 20160, 43200]),
            },
            "C360 Recovery Plan": {
                rto_minutes: durationCells(TARGETS),
                rpo_minutes: durationCells([0, ...TARGETS.slice(0, 9)]),
            },
        };

        function attach(frm, fieldname, cells) {
            const field = frm.fields_dict[fieldname];
            if (!field || !field.$wrapper) return;
            field.$wrapper.find(".c360-scale").remove();
            const locked = frm.doc.docstatus !== 0 || field.df.read_only || field.disp_status === "Read";
            const scale = $('<div class="c360-scale" role="group"></div>')
                .attr("aria-label", __("Select {0}", [__(field.df.label)]));
            for (const cell of cells) {
                const selected = frm.doc[fieldname] != null && Number(frm.doc[fieldname]) === cell.value;
                const button = $('<button type="button" class="c360-scale-cell"></button>')
                    .text(cell.text)
                    .attr("title", cell.hint)
                    .attr("aria-pressed", selected ? "true" : "false")
                    .toggleClass("c360-scale-selected", selected)
                    .prop("disabled", locked)
                    .css("--c360-cell", cell.color);
                if (!locked) {
                    button.on("click", () => frm.set_value(fieldname, cell.value));
                }
                scale.append(button);
            }
            field.$wrapper.append(scale);
        }

        const MATRIX = {
            "C360 Risk": {likelihood: "likelihood", impact: "impact"},
            "C360 Risk Assessment": {likelihood: "residual_likelihood", impact: "residual_impact"},
        };
        const RATINGS = [
            [20, "#d9342b", __("Critical 20-25")],
            [12, "#f08c00", __("High 12-19")],
            [6, "#f3c300", __("Medium 6-11")],
            [1, "#2f9e44", __("Low 1-5")],
        ];

        function ratingColor(score) {
            return RATINGS.find(([minimum]) => score >= minimum)[1];
        }

        function attachMatrix(frm, fields) {
            const anchor = frm.fields_dict[fields.impact];
            if (!anchor || !anchor.$wrapper) return;
            anchor.$wrapper.find(".c360-matrix-wrap").remove();
            const locked = frm.doc.docstatus !== 0 || anchor.df.read_only || anchor.disp_status === "Read";
            const likelihood = Number(frm.doc[fields.likelihood]);
            const impact = Number(frm.doc[fields.impact]);
            const wrap = $('<div class="c360-matrix-wrap"></div>');
            wrap.append($('<div class="c360-matrix-title"></div>').text(
                __("Or pick likelihood and impact together on the matrix")));
            const grid = $('<div class="c360-matrix" role="group"></div>')
                .attr("aria-label", __("Risk matrix: rows likelihood 5 to 1, columns impact 1 to 5"));
            grid.append('<span></span>');
            grid.append($('<span class="c360-matrix-xlabel"></span>').text(__("Impact")));
            grid.append('<span></span>');
            for (let column = 1; column <= 5; column++) {
                grid.append($('<span class="c360-matrix-axis"></span>').text(String(column)));
            }
            for (let row = 5; row >= 1; row--) {
                grid.append($('<span class="c360-matrix-axis"></span>').text(String(row)));
                for (let column = 1; column <= 5; column++) {
                    const score = row * column;
                    const selected = likelihood === row && impact === column;
                    const cell = $('<button type="button" class="c360-matrix-cell"></button>')
                        .text(score)
                        .attr("title", __("Likelihood {0} x Impact {1} = {2}", [row, column, score]))
                        .attr("aria-pressed", selected ? "true" : "false")
                        .toggleClass("c360-matrix-selected", selected)
                        .prop("disabled", locked)
                        .css("--c360-cell", ratingColor(score));
                    if (!locked) {
                        cell.on("click", async () => {
                            await frm.set_value(fields.likelihood, row);
                            await frm.set_value(fields.impact, column);
                        });
                    }
                    grid.append(cell);
                }
            }
            const frame = $('<div class="c360-matrix-frame"></div>');
            frame.append($('<div class="c360-matrix-ylabel"></div>').text(__("Likelihood")));
            frame.append(grid);
            wrap.append(frame);
            const legend = $('<div class="c360-matrix-legend"></div>');
            for (const [, color, label] of [...RATINGS].reverse()) {
                legend.append($("<span></span>").text(label).css("--c360-cell", color));
            }
            wrap.append(legend);
            anchor.$wrapper.append(wrap);
        }

        for (const [doctype, fields] of Object.entries(SCALES)) {
            const matrix = MATRIX[doctype];
            const render = (frm) => {
                for (const [fieldname, cells] of Object.entries(fields)) attach(frm, fieldname, cells);
                if (matrix) attachMatrix(frm, matrix);
            };
            const handlers = {refresh: render};
            for (const [fieldname, cells] of Object.entries(fields)) {
                handlers[fieldname] = (frm) => {
                    attach(frm, fieldname, cells);
                    if (matrix && (fieldname === matrix.likelihood || fieldname === matrix.impact)) {
                        attachMatrix(frm, matrix);
                    }
                };
            }
            frappe.ui.form.on(doctype, handlers);
            if (window.cur_frm && window.cur_frm.doctype === doctype) {
                render(window.cur_frm);
            }
        }
    });
});
