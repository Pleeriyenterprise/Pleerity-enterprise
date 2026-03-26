"""
Enterprise branded invoice/receipt PDF (ReportLab, sync).
Used for orders (non-CVP) and subscription checkout (CVP). Single visual template.

Line items:
  Prefer ``line_items`` (list of dicts: description, quantity, unit_pence, line_total_pence).
  Legacy single-field keys (line_description, line_quantity, …) are still supported.

Table headers use a dedicated white/bold Paragraph style; TableStyle TEXTCOLOR does not
override colors inside Paragraph flowables (using the default navy ``body`` style made
headers invisible on the navy row).
"""
from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from utils.branding import COMPANY_NAME, SUPPORT_EMAIL, TAGLINE, get_branding_logo_path, get_branding_website_url

NAVY = colors.HexColor("#0B1D3A")
TEAL = colors.HexColor("#00B8A9")
WHITE = colors.white
GREY_TEXT = colors.HexColor("#64748b")
LIGHT_BG = colors.HexColor("#f8fafc")
LOGO_TARGET_WIDTH_MM = 28
LOGO_MAX_HEIGHT_MM = 16

# Canonical site for PDF header (spec); avoid localhost from get_branding_website_url in dev if needed
CANONICAL_WEBSITE = "https://pleerityenterprise.co.uk"


def _description_to_paragraph_html(text: str) -> str:
    """One escaped paragraph; newlines become <br/>."""
    raw = (text or "").strip() or "—"
    return "<br/>".join(xml_escape(line) for line in raw.split("\n"))


def _normalize_line_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = data.get("line_items")
    if isinstance(raw, list) and raw:
        out: List[Dict[str, Any]] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            qty = int(row.get("quantity") or row.get("line_quantity") or 1)
            unit = int(row.get("unit_pence") or row.get("line_unit_pence") or 0)
            lt = row.get("line_total_pence")
            if lt is None:
                lt = unit * max(qty, 1)
            else:
                lt = int(lt)
            out.append(
                {
                    "description": str(row.get("description") or row.get("line_description") or "Service"),
                    "quantity": max(qty, 1),
                    "unit_pence": unit,
                    "line_total_pence": lt,
                }
            )
        return out if out else _legacy_single_line_item(data)

    return _legacy_single_line_item(data)


def _legacy_single_line_item(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    qty = int(data.get("line_quantity") or 1)
    unit_p = int(data.get("line_unit_pence") or 0)
    line_total_p = int(data.get("line_total_pence") or unit_p * max(qty, 1))
    return [
        {
            "description": str(data.get("line_description") or "Service"),
            "quantity": max(qty, 1),
            "unit_pence": unit_p,
            "line_total_pence": line_total_p,
        }
    ]


def _sum_line_totals(items: List[Dict[str, Any]]) -> int:
    return sum(int(x.get("line_total_pence") or 0) for x in items)


def build_branded_invoice_pdf_bytes(data: Dict[str, Any]) -> bytes:
    """
    Build PDF from a normalized invoice dict.

    Required keys (legacy):
      document_title, invoice_number, order_reference, date_issued (str)
      customer_name, customer_email
      subtotal_pence, total_pence, currency (str, e.g. gbp)
      payment_status, payment_method (str)

    Line items (preferred):
      line_items: list of { description, quantity, unit_pence, line_total_pence }

    Or single-line legacy:
      line_description, line_quantity (int), line_unit_pence, line_total_pence

    Optional:
      vat_pence (int, default 0)

    When ``line_items`` is supplied, ``subtotal_pence`` defaults to the sum of line totals
    if omitted or None (caller should align VAT/total with Stripe/order totals).
    """
    doc_title = str(data.get("document_title") or "RECEIPT").upper()
    if doc_title not in ("RECEIPT", "INVOICE"):
        doc_title = "RECEIPT"

    invoice_number = xml_escape(str(data.get("invoice_number") or "—"))
    order_reference = xml_escape(str(data.get("order_reference") or "—"))
    date_issued = xml_escape(str(data.get("date_issued") or "—"))
    customer_name = xml_escape(str(data.get("customer_name") or ""))
    customer_email = xml_escape(str(data.get("customer_email") or ""))

    line_items = _normalize_line_items(data)
    sum_lines = _sum_line_totals(line_items)

    vat_p = int(data.get("vat_pence") or 0)
    total_p = int(data.get("total_pence") if data.get("total_pence") is not None else sum_lines + vat_p)

    if data.get("line_items") is not None and isinstance(data.get("line_items"), list):
        subtotal_p = int(data["subtotal_pence"]) if data.get("subtotal_pence") is not None else sum_lines
    else:
        line_total_p = int(data.get("line_total_pence") or sum_lines)
        subtotal_p = int(data.get("subtotal_pence") if data.get("subtotal_pence") is not None else line_total_p)

    if sum_lines and subtotal_p != sum_lines and data.get("line_items"):
        subtotal_p = sum_lines

    currency = str(data.get("currency") or "gbp").lower()
    payment_status = xml_escape(str(data.get("payment_status") or "PAID"))
    payment_method = xml_escape(str(data.get("payment_method") or "Card (Stripe)"))

    website = get_branding_website_url()
    if "localhost" in (website or "").lower():
        website = CANONICAL_WEBSITE

    def money(pence: int) -> str:
        cur = currency.upper()
        sym = "£" if cur in ("GBP", "GB") else f"{cur} "
        return f"{sym}{pence / 100:.2f}"

    styles = getSampleStyleSheet()
    body = ParagraphStyle("InvBody", parent=styles["Normal"], fontSize=10, leading=14, textColor=NAVY)
    body_small = ParagraphStyle("InvSmall", parent=styles["Normal"], fontSize=9, leading=12, textColor=GREY_TEXT)
    white_header = ParagraphStyle(
        "InvWhite",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=WHITE,
    )
    # Header row in service table: must be white on navy (Paragraph ignores Table TEXTCOLOR).
    table_header_white = ParagraphStyle(
        "InvTableHdr",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=WHITE,
        fontName="Helvetica-Bold",
    )
    title_big = ParagraphStyle(
        "InvDocTitle",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=TEAL,
        fontName="Helvetica-Bold",
        spaceAfter=8,
    )
    section = ParagraphStyle(
        "InvSec",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=6,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )

    header_html = (
        f"<b><font size='12' color='white'>{xml_escape(COMPANY_NAME)}</font></b><br/>"
        f"<font color='white'>Email: {xml_escape(SUPPORT_EMAIL)}</font><br/>"
        f"<font color='white'>Website: {xml_escape(website)}</font><br/>"
        f"<font color='white'>{xml_escape(TAGLINE)}</font>"
    )
    header_para = Paragraph(header_html, white_header)

    logo_path = get_branding_logo_path()
    logo_flowable: Optional[Image] = None
    if logo_path and os.path.isfile(logo_path):
        try:
            logo_flowable = Image(logo_path)
            iw = float(getattr(logo_flowable, "imageWidth", 0) or 0)
            ih = float(getattr(logo_flowable, "imageHeight", 0) or 0)
            if iw > 0 and ih > 0:
                target_w = LOGO_TARGET_WIDTH_MM * mm
                target_h = (target_w * ih) / iw
                max_h = LOGO_MAX_HEIGHT_MM * mm
                if target_h > max_h:
                    scale = max_h / target_h
                    target_w = target_w * scale
                    target_h = max_h
                logo_flowable.drawWidth = target_w
                logo_flowable.drawHeight = target_h
            else:
                logo_flowable = Image(logo_path, width=LOGO_TARGET_WIDTH_MM * mm)
        except Exception:
            logo_flowable = None

    if logo_flowable is not None:
        header_inner = Table(
            [[logo_flowable, header_para]],
            colWidths=[32 * mm, 142 * mm],
        )
        header_inner.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        header_table = Table([[header_inner]], colWidths=[174 * mm])
    else:
        header_table = Table([[header_para]], colWidths=[174 * mm])

    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("BOX", (0, 0), (-1, -1), 0, NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    story = [header_table, Spacer(1, 14), Paragraph(doc_title, title_big)]

    meta_rows = [
        [Paragraph("<b>Invoice Number</b>", body), Paragraph(invoice_number, body)],
        [Paragraph("<b>Order Reference</b>", body), Paragraph(order_reference, body)],
        [Paragraph("<b>Date Issued</b>", body), Paragraph(date_issued, body)],
    ]
    meta_t = Table(meta_rows, colWidths=[48 * mm, 126 * mm])
    meta_t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    story.append(meta_t)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Billed To", section))
    billed_html = f"{customer_name}<br/><font color='#64748b'>{customer_email}</font>"
    story.append(Paragraph(billed_html, body))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Service Details", section))
    line_header = [
        Paragraph("Description", table_header_white),
        Paragraph("Qty", table_header_white),
        Paragraph("Unit Price", table_header_white),
        Paragraph("Total", table_header_white),
    ]
    line_rows: List[List[Paragraph]] = [line_header]
    for item in line_items:
        desc_html = _description_to_paragraph_html(item["description"])
        line_rows.append(
            [
                Paragraph(desc_html, body),
                Paragraph(str(item["quantity"]), body),
                Paragraph(money(int(item["unit_pence"])), body),
                Paragraph(money(int(item["line_total_pence"])), body),
            ]
        )

    line_t = Table(line_rows, colWidths=[78 * mm, 18 * mm, 38 * mm, 40 * mm])
    line_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(line_t)
    story.append(Spacer(1, 12))

    summary_rows = [
        [Paragraph("<b>Subtotal</b>", body), Paragraph(money(subtotal_p), body)],
    ]
    if vat_p > 0:
        summary_rows.append([Paragraph("<b>VAT</b>", body), Paragraph(money(vat_p), body)])
    summary_rows.append([Paragraph("<b>Total Paid</b>", body), Paragraph(money(total_p), body)])

    sum_t = Table(summary_rows, colWidths=[120 * mm, 54 * mm])
    sum_t.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEABOVE", (0, -1), (-1, -1), 1, TEAL),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    story.append(sum_t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Payment Status", section))
    story.append(Paragraph(f"<b>{payment_status}</b>", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Payment Method", section))
    story.append(Paragraph(payment_method, body))
    story.append(Spacer(1, 20))

    footer_lines = (
        f"<b>{xml_escape(COMPANY_NAME)}</b><br/>"
        f"{xml_escape(TAGLINE)}<br/>"
        f"Support: {xml_escape(SUPPORT_EMAIL)} | Website: {xml_escape(website)}<br/>"
        "This document serves as confirmation of payment."
    )
    story.append(Paragraph(footer_lines, body_small))

    doc.build(story)
    return buffer.getvalue()
