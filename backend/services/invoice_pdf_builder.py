"""
Enterprise branded invoice/receipt PDF (ReportLab, sync).
Used for orders (non-CVP) and subscription checkout (CVP). Single visual template.
"""
from __future__ import annotations

import io
from typing import Any, Dict
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from utils.branding import COMPANY_NAME, SUPPORT_EMAIL, TAGLINE, get_branding_website_url

NAVY = colors.HexColor("#0B1D3A")
TEAL = colors.HexColor("#00B8A9")
WHITE = colors.white
GREY_TEXT = colors.HexColor("#64748b")
LIGHT_BG = colors.HexColor("#f8fafc")

# Canonical site for PDF header (spec); avoid localhost from get_branding_website_url in dev if needed
CANONICAL_WEBSITE = "https://pleerityenterprise.co.uk"


def build_branded_invoice_pdf_bytes(data: Dict[str, Any]) -> bytes:
    """
    Build PDF from a normalized invoice dict.

    Required keys:
      document_title: "RECEIPT" | "INVOICE"
      invoice_number, order_reference, date_issued (str)
      customer_name, customer_email
      line_description, line_quantity (int), line_unit_pence, line_total_pence
      subtotal_pence, total_pence, currency (str, e.g. gbp)
      payment_status, payment_method (str)
    Optional:
      vat_pence (int, default 0)
    """
    doc_title = str(data.get("document_title") or "RECEIPT").upper()
    if doc_title not in ("RECEIPT", "INVOICE"):
        doc_title = "RECEIPT"

    invoice_number = xml_escape(str(data.get("invoice_number") or "—"))
    order_reference = xml_escape(str(data.get("order_reference") or "—"))
    date_issued = xml_escape(str(data.get("date_issued") or "—"))
    customer_name = xml_escape(str(data.get("customer_name") or ""))
    customer_email = xml_escape(str(data.get("customer_email") or ""))
    line_desc = xml_escape(str(data.get("line_description") or "Service"))
    qty = int(data.get("line_quantity") or 1)
    unit_p = int(data.get("line_unit_pence") or 0)
    line_total_p = int(data.get("line_total_pence") or unit_p * qty)
    subtotal_p = int(data.get("subtotal_pence") if data.get("subtotal_pence") is not None else line_total_p)
    vat_p = int(data.get("vat_pence") or 0)
    total_p = int(data.get("total_pence") or subtotal_p + vat_p)
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
    title_big = ParagraphStyle(
        "InvDocTitle",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=TEAL,
        fontName="Helvetica-Bold",
        spaceAfter=8,
    )
    section = ParagraphStyle("InvSec", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", textColor=NAVY, spaceBefore=10, spaceAfter=6)

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
        Paragraph("<b>Description</b>", body),
        Paragraph("<b>Qty</b>", body),
        Paragraph("<b>Unit Price</b>", body),
        Paragraph("<b>Total</b>", body),
    ]
    line_row = [
        Paragraph(line_desc, body),
        Paragraph(str(qty), body),
        Paragraph(money(unit_p), body),
        Paragraph(money(line_total_p), body),
    ]
    line_t = Table([line_header, line_row], colWidths=[78 * mm, 18 * mm, 38 * mm, 40 * mm])
    line_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
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
        "Thank you for your business.<br/>"
        "This document serves as confirmation of payment.<br/><br/>"
        f"<font color='#64748b'>Support: {xml_escape(SUPPORT_EMAIL)}</font>"
    )
    story.append(Paragraph(footer_lines, body_small))

    doc.build(story)
    return buffer.getvalue()
