"""Approval-snapshot downloads; never render user-supplied HTML or fetch embedded resources."""

import re
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils import escape_html, now_datetime

from continuity360.bcp_snapshot import get_approved_snapshot, render_snapshot


@frappe.whitelist()
def download_approved_plan(plan_name: str, file_format: str = "pdf") -> None:
    plan = frappe.get_doc("C360 Business Continuity Plan", plan_name)
    plan.check_permission("read")
    plan.check_permission("print")
    _download(get_approved_snapshot(plan_name), plan.approval_status, file_format)


@frappe.whitelist()
def download_distribution(distribution_name: str, file_format: str = "pdf") -> None:
    from continuity360.bcp_distribution import _get_recipient

    distribution = frappe.get_doc("C360 BCP Distribution", distribution_name)
    _get_recipient(distribution)
    snapshot = frappe.get_doc("C360 BCP Approval Snapshot", distribution.snapshot)
    status = frappe.db.get_value("C360 Business Continuity Plan", distribution.plan, "approval_status")
    _download(render_snapshot(snapshot), status, file_format)


def _download(snapshot: dict, status: str, file_format: str) -> None:
    if file_format not in ("pdf", "docx"):
        frappe.throw(_("Choose PDF or Word (DOCX)."))
    sections = _sections(snapshot, status)
    if file_format == "pdf":
        from frappe.utils.pdf import get_pdf

        body = "".join(
            f"<h2>{escape_html(heading)}</h2>"
            + "".join(f"<p>{escape_html(line)}</p>" for line in lines)
            for heading, lines in sections
        )
        content = get_pdf(
            "<html><head><meta charset='utf-8'><style>"
            "body{font-family:sans-serif;color:#142d46;font-size:11pt}"
            "h2{color:#1454a0;page-break-after:avoid}"
            "p{white-space:pre-wrap;overflow-wrap:break-word}</style></head>"
            f"<body>{body}</body></html>"
        )
        content_type = "application/pdf"
    else:
        content = _docx(sections)
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    plan = snapshot["plan"]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", str(plan["name"]))
    version = re.sub(r"[^A-Za-z0-9._-]", "-", str(plan.get("plan_version") or "legacy"))
    frappe.local.response.filename = f"{name}-v{version}.{file_format}"
    frappe.local.response.filecontent = content
    frappe.local.response.content_type = content_type
    frappe.local.response.display_content_as = "attachment"
    frappe.local.response.type = "download"


def _sections(snapshot: dict, status: str) -> list[tuple[str, list[str]]]:
    plan = snapshot["plan"]
    sections = [
        ("Continuity360 - " + _("Business continuity plan"), [
            str(plan.get("plan_title") or plan["name"]),
            _("Plan: {0}").format(plan["name"]),
            _("Version: {0}").format(plan.get("plan_version") or _("Unnumbered legacy approval")),
            _("Approved snapshot captured: {0}").format(snapshot["captured_on"]),
            _("Current plan status: {0}").format(_(status or "Unavailable")),
            _("Downloaded by: {0} at {1}").format(frappe.session.user, now_datetime()),
            _("Uncontrolled downloaded copy. Check the online plan before use. "
              "Downloaded copies cannot be revoked and may become outdated."),
            _("Content reflects your current access permissions. Restricted linked records are omitted. "
              "Rich text is exported as plain text; embedded images and attachments are not included."),
        ]),
    ]
    if status != "Approved":
        sections[0][1].append(_("HISTORICAL PLAN - not an active approved plan."))
    sections.append((_("Approved plan details"), _record_lines(plan)))
    for record in snapshot["records"]:
        if record.get("restricted"):
            sections.append((_(record["doctype"]), [_("Restricted linked record - content omitted.")]))
        else:
            sections.append((
                f"{_(record['doctype'])}: {record['name']}",
                _record_lines(record["content"]),
            ))
    return sections


def _record_lines(record: dict) -> list[str]:
    lines = []
    for field in frappe.get_meta(record["doctype"]).fields:
        value = record.get(field.fieldname)
        if field.hidden or value in (None, "", []) or field.fieldtype in (
            "Section Break", "Column Break", "Tab Break", "HTML", "Button",
        ):
            continue
        if field.fieldtype == "Table":
            lines.append(_(field.label))
            for index, row in enumerate(value, 1):
                lines.append(f"{index}. " + "; ".join(_record_lines(row)))
        else:
            text = (BeautifulSoup(str(value), "html.parser").get_text("\n", strip=True)
                    if field.fieldtype == "Text Editor" else str(value))
            lines.append(f"{_(field.label)}: {text}")
    return lines


def _docx(sections: list[tuple[str, list[str]]]) -> bytes:
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ET.register_namespace("w", namespace)
    document = ET.Element(f"{{{namespace}}}document")
    body = ET.SubElement(document, f"{{{namespace}}}body")
    for heading, lines in sections:
        for index, text in enumerate([heading, *lines]):
            paragraph = ET.SubElement(body, f"{{{namespace}}}p")
            run = ET.SubElement(paragraph, f"{{{namespace}}}r")
            if index == 0:
                properties = ET.SubElement(run, f"{{{namespace}}}rPr")
                ET.SubElement(properties, f"{{{namespace}}}b")
            for line_index, line in enumerate(str(text).splitlines() or [""]):
                if line_index:
                    ET.SubElement(run, f"{{{namespace}}}br")
                node = ET.SubElement(run, f"{{{namespace}}}t", {
                    "{http://www.w3.org/XML/1998/namespace}space": "preserve",
                })
                node.text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", line)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        ))
        archive.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>'
        ))
        archive.writestr("word/document.xml", ET.tostring(document, encoding="utf-8", xml_declaration=True))
    return output.getvalue()
