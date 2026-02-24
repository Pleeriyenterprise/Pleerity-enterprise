"""
Generate the UK Landlord Compliance Master Checklist (2026 Edition) PDF for the lead magnet.
Static 8-page PDF: Cover, How to Use, Core Safety Certificates, Licensing, Tenancy checklist,
Portfolio Overview, Manual vs Digital comparison, Disclaimer & Support.
Output: frontend/public/compliance-checklist-2026.pdf
Run from repo root: python backend/scripts/generate_compliance_checklist_pdf.py
"""
from __future__ import annotations

import os
import sys
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Brand
TEAL_HEX = "#00B8A9"
DISCLAIMER = (
    "This document provides general information only and does not constitute legal advice. "
    "Requirements may vary by property type and local authority."
)
FOOTER_LINES = [
    "Compliance Vault Pro",
    "AI-Driven Compliance Tracking",
    "pleerityenterprise.co.uk",
]


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _footer_canvas(canvas, doc):
    """Draw brand footer on every page."""
    canvas.saveState()
    width = doc.pagesize[0]
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    y = 36
    for line in reversed(FOOTER_LINES):
        canvas.drawCentredString(width / 2, y, line)
        y += 10
    canvas.restoreState()


def _build_styles():
    base = getSampleStyleSheet()
    teal_rgb = _hex_to_rgb(TEAL_HEX)
    return {
        "logo": ParagraphStyle(
            "Logo",
            parent=base["Normal"],
            fontSize=14,
            textColor=colors.HexColor(TEAL_HEX),
            spaceAfter=6,
            alignment=TA_LEFT,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontSize=22,
            spaceAfter=12,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=11,
            spaceAfter=24,
            alignment=TA_CENTER,
        ),
        "heading": ParagraphStyle(
            "Heading",
            parent=base["Heading2"],
            fontSize=14,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=10,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontSize=9,
            spaceAfter=4,
        ),
        "notice": ParagraphStyle(
            "Notice",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#555555"),
            alignment=TA_CENTER,
            spaceBefore=30,
        ),
    }


def _table_style_header_teal():
    teal_rgb = _hex_to_rgb(TEAL_HEX)
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*teal_rgb)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def build_pdf() -> bytes:
    """Build the 8-page checklist PDF. Returns PDF bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=56,
    )
    styles = _build_styles()
    table_style = _table_style_header_teal()
    elements = []

    # ----- PAGE 1: Cover -----
    elements.append(Spacer(1, 50))
    elements.append(Paragraph("Compliance Vault Pro", styles["logo"]))
    elements.append(Spacer(1, 60))
    elements.append(Paragraph("UK Landlord Compliance Master Checklist", styles["title"]))
    elements.append(Paragraph("2026 Edition", styles["title"]))
    elements.append(Paragraph(
        "A structured framework for managing UK rental compliance documentation",
        styles["subtitle"],
    ))
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=colors.HexColor(TEAL_HEX),
        spaceAfter=24,
    ))
    elements.append(Paragraph(DISCLAIMER, styles["notice"]))
    elements.append(PageBreak())

    # ----- PAGE 2: How to Use -----
    elements.append(Paragraph("How to Use This Compliance Checklist", styles["heading"]))
    elements.append(Paragraph(
        "• Review each requirement per property<br/>"
        "• Record confirmed expiry dates<br/>"
        "• Set reminder dates 30–60 days before expiry<br/>"
        "• Review your portfolio monthly",
        styles["body"],
    ))
    elements.append(Spacer(1, 20))
    # Box: Recommended Review Cycle
    box_data = [[
        Paragraph(
            "<b>Recommended Review Cycle:</b><br/>"
            "☐ Monthly &nbsp;&nbsp; ☐ Quarterly",
            styles["body"],
        )
    ]]
    box_table = Table(box_data, colWidths=[doc.width])
    box_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(TEAL_HEX)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.Color(0.97, 1, 1)),
        ("PADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(box_table)
    elements.append(PageBreak())

    # ----- PAGE 3: Core Safety Certificates -----
    elements.append(Paragraph("Core Safety Certificates", styles["heading"]))
    core_data = [
        ["Requirement", "Applies?", "Confirmed Expiry Date", "Reminder Set", "Notes"],
        ["Gas Safety Record (CP12)", "", "", "", ""],
        ["Electrical Installation Condition Report (EICR)", "", "", "", ""],
        ["Energy Performance Certificate (EPC)", "", "", "", ""],
        ["Smoke Alarm Test Record", "", "", "", ""],
        ["Carbon Monoxide Alarm Check", "", "", "", ""],
    ]
    core_table = Table(core_data, colWidths=[100, 45, 70, 55, 90])
    core_table.setStyle(table_style)
    elements.append(core_table)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(
        "<i>Tracking Note:</i> Renewal cycles vary depending on property and circumstances.",
        styles["small"],
    ))
    elements.append(PageBreak())

    # ----- PAGE 4: Licensing -----
    elements.append(Paragraph("Licensing & Local Authority Requirements", styles["heading"]))
    lic_data = [
        ["Licence Type", "Required?", "Expiry Date", "Renewal Reminder", "Notes"],
        ["HMO Licence", "", "", "", ""],
        ["Selective Licence", "", "", "", ""],
        ["Additional Licensing (if applicable)", "", "", "", ""],
    ]
    lic_table = Table(lic_data, colWidths=[120, 55, 70, 70, 95])
    lic_table.setStyle(table_style)
    elements.append(lic_table)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(
        "Licensing requirements depend on property type and local authority.",
        styles["small"],
    ))
    elements.append(PageBreak())

    # ----- PAGE 5: Tenancy & Record Keeping -----
    elements.append(Paragraph("Tenancy & Record Keeping", styles["heading"]))
    elements.append(Paragraph(
        "☐ Tenancy Agreement Signed<br/>"
        "☐ Deposit Protection Certificate Issued<br/>"
        "☐ Prescribed Information Served<br/>"
        "☐ Right-to-Rent Checks Completed<br/>"
        "☐ Inventory / Check-In Report<br/>"
        "☐ How to Rent Guide Provided",
        styles["body"],
    ))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Notes:", styles["body"]))
    elements.append(Spacer(1, 80))
    elements.append(PageBreak())

    # ----- PAGE 6: Portfolio Compliance Overview -----
    elements.append(Paragraph("Portfolio Compliance Overview", styles["heading"]))
    port_data = [
        ["Property", "Gas", "EICR", "EPC", "Licence", "Next Expiry", "Risk Indicator"],
        ["", "", "", "", "", "", ""],
        ["", "", "", "", "", "", ""],
        ["", "", "", "", "", "", ""],
        ["", "", "", "", "", "", ""],
    ]
    port_table = Table(port_data, colWidths=[70, 35, 35, 35, 45, 55, 65])
    port_table.setStyle(table_style)
    elements.append(port_table)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(
        "<b>Risk Indicator:</b> Green = All valid &nbsp;|&nbsp; "
        "Amber = Expiry within 60 days &nbsp;|&nbsp; Red = Expired or missing evidence",
        styles["small"],
    ))
    elements.append(PageBreak())

    # ----- PAGE 7: Manual vs Digital -----
    elements.append(Paragraph("Structured Tracking vs Manual Tracking", styles["heading"]))
    comp_data = [
        ["Manual Tracking", "Structured Digital Tracking"],
        ["Spreadsheets", "Centralised dashboard"],
        ["Email reminders", "Automated notifications"],
        ["No portfolio visibility", "Property-level overview"],
        ["Higher oversight risk", "Expiry alerts"],
    ]
    comp_table = Table(comp_data, colWidths=[doc.width / 2] * 2)
    comp_table.setStyle(table_style)
    elements.append(comp_table)
    elements.append(Spacer(1, 28))
    elements.append(Paragraph(
        "If you prefer automated expiry reminders and structured portfolio tracking, "
        "explore <b>Compliance Vault Pro</b>.",
        styles["body"],
    ))
    elements.append(PageBreak())

    # ----- PAGE 8: Disclaimer & Support -----
    elements.append(Paragraph("Disclaimer & Support", styles["heading"]))
    elements.append(Paragraph(DISCLAIMER, styles["body"]))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Support:", styles["body"]))
    elements.append(Paragraph("info@pleerityenterprise.co.uk", styles["body"]))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(
        "Your Compliance Vault Pro reference number: ___________",
        styles["body"],
    ))

    doc.build(elements, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)
    buffer.seek(0)
    return buffer.getvalue()


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(script_dir)
    repo_root = os.path.dirname(backend_dir)
    output_path = os.path.join(repo_root, "frontend", "public", "compliance-checklist-2026.pdf")

    out_dir = os.path.dirname(output_path)
    if not os.path.isdir(out_dir):
        print(f"Error: Directory does not exist: {out_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        pdf_bytes = build_pdf()
    except Exception as e:
        print(f"Error generating PDF: {e}", file=sys.stderr)
        sys.exit(1)

    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"Written: {output_path} ({len(pdf_bytes)} bytes)")


if __name__ == "__main__":
    main()
