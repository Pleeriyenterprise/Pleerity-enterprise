"""
Monthly Operations Intelligence Digest PDF (ReportLab).

Executive operational briefing — distinct from Evidence Readiness, Requirements
Reports, and Audit Evidence Packs.
"""
from __future__ import annotations

import html
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.monthly_digest_operational_intelligence import build_digest_intelligence
from services.report_branding_layout import ACCESSIBILITY_ENHANCED_NOTICE, append_report_cover_block
from services.report_layout_governance import (
    GovernancePdfContext,
    governance_footer_bottom_margin,
    make_page_callbacks,
    proportional_col_widths,
)
from services.reporting_semantics_v1 import (
    EXPORT_DETERMINISM_POINT_IN_TIME,
    EXPORT_GRADE_DEFINITIONS,
    GRADE_EXECUTIVE,
    REPORTING_SEMANTICS_VERSION,
)
from utils.storage_paths import resolve_data_dir

logger = logging.getLogger(__name__)

_DIGEST_FROZEN_NOTE = (
    "This report is a point-in-time operational intelligence snapshot. "
    "Figures reflect data held at generation; re-download of a stored artifact returns the same bytes."
)


def _hex_color(raw: Optional[str], fallback: str = "#0B1D3A") -> colors.Color:
    s = (raw or fallback).strip()
    if s.startswith("#") and len(s) in (4, 7):
        try:
            return colors.HexColor(s)
        except Exception:
            pass
    return colors.HexColor(fallback if fallback.startswith("#") else "#" + fallback)


def _digest_table_cell(text: str, style: ParagraphStyle, *, bold: bool = False) -> Paragraph:
    raw = html.escape(str(text if text is not None else "—"))
    if bold:
        return Paragraph(f"<b>{raw}</b>", style)
    return Paragraph(raw, style)


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def _priority_section(
    body: List[Any],
    title: str,
    items: List[Dict[str, str]],
    styles: Any,
    h3: ParagraphStyle,
) -> None:
    if not items:
        return
    body.append(Paragraph(f"<b>{html.escape(title)}</b>", h3))
    for item in items:
        prop = html.escape(item.get("property") or "Portfolio")
        issue = html.escape(item.get("issue") or "")
        action = html.escape(item.get("action") or "")
        urgency = html.escape(item.get("urgency") or "")
        block = (
            f"<b>{prop}</b> — {issue}<br/>"
            f"<font size=8>Recommended: {action} &nbsp;|&nbsp; Urgency: {urgency}</font>"
        )
        body.append(Paragraph(block, styles["Normal"]))
        body.append(Spacer(1, 0.12 * cm))


def build_monthly_digest_pdf_bytes(model: Dict[str, Any], *, brand: Any) -> bytes:
    """Build Monthly Operations Intelligence Digest PDF from assembly model."""
    from datetime import datetime, timezone

    intelligence = build_digest_intelligence(model)
    now = datetime.now(timezone.utc)
    grade_def = EXPORT_GRADE_DEFINITIONS.get(GRADE_EXECUTIVE) or {}
    gov_ctx = GovernancePdfContext(
        export_grade=GRADE_EXECUTIVE,
        export_grade_label=grade_def.get("label") or GRADE_EXECUTIVE,
        generated_at=now,
        determinism=EXPORT_DETERMINISM_POINT_IN_TIME,
        jurisdiction_summary=str(model.get("digest_jurisdiction_framing") or "")[:90],
        company_name=str(getattr(brand, "company_name", None) or ""),
        semantics_version=REPORTING_SEMANTICS_VERSION,
        report_scope="portfolio",
    )
    on_first, on_later = make_page_callbacks(gov_ctx, footer_mode="compact")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=governance_footer_bottom_margin(),
        title="Monthly Operations Intelligence Digest",
    )
    styles = getSampleStyleSheet()
    primary = _hex_color(getattr(brand, "primary_color", None))
    digest_styles = {
        "title": ParagraphStyle(
            name="DigestTitle",
            parent=styles["Heading1"],
            textColor=primary,
            spaceAfter=10,
            fontSize=18,
        ),
        "subtitle": ParagraphStyle(name="DigestSub", parent=styles["Normal"], fontSize=10),
        "heading": ParagraphStyle(name="H2", parent=styles["Heading2"], textColor=primary, spaceBefore=12, spaceAfter=8),
        "body": styles["Normal"],
        "small": ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#64748b")),
    }
    h2 = digest_styles["heading"]
    h3 = ParagraphStyle(name="H3", parent=styles["Heading3"], spaceBefore=8, spaceAfter=6)
    small = digest_styles["small"]
    interpret_style = ParagraphStyle(
        name="DigestInterpret",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=4,
        spaceAfter=10,
        leading=14,
    )
    table_cell_style = styles["Normal"]

    branding_dict: Dict[str, Any] = {}
    if hasattr(brand, "to_report_dict") and callable(getattr(brand, "to_report_dict")):
        try:
            raw_bd = brand.to_report_dict()
            if isinstance(raw_bd, dict):
                branding_dict = raw_bd
        except Exception:
            branding_dict = {}
    if not branding_dict:
        branding_dict = {
            "company_name": getattr(brand, "company_name", None) or "",
            "brand_company_name": getattr(brand, "company_name", None) or "",
            "logo_path": getattr(brand, "logo_path", None),
            "branding_source": getattr(brand, "source", None) or "pleerity",
            "primary_color": getattr(brand, "primary_color", None),
            "secondary_color": getattr(brand, "secondary_color", None),
            "tagline": getattr(brand, "tagline", None),
        }

    body: List[Any] = []
    report_period = str(model.get("reporting_month_label") or "Monthly report")
    crn = model.get("customer_reference")
    account = str(model.get("account_name") or model.get("client_name") or "")
    report_class = intelligence.get("report_class") or "Monthly Operations Intelligence Digest"

    append_report_cover_block(
        body,
        report_title=report_class,
        branding=branding_dict,
        gov_ctx=gov_ctx,
        styles=digest_styles,
        account_line=f"<b>Account:</b> {html.escape(account)}"
        + (f" &nbsp;|&nbsp; <b>CRN:</b> {html.escape(str(crn))}" if crn else ""),
        scope_line=f"<b>Reporting period:</b> {html.escape(report_period)} &nbsp;|&nbsp; "
        f"<b>Properties:</b> {int(model.get('properties_count') or 0)}",
        extra_metadata_lines=[
            f"<b>Generated:</b> {html.escape(str(model.get('generated_at_display') or model.get('data_as_of') or ''))}",
            f"<b>Report class:</b> {html.escape(report_class)}",
        ],
    )
    body.append(Paragraph(html.escape(_DIGEST_FROZEN_NOTE), small))
    body.append(Spacer(1, 0.2 * cm))

    from services.report_interpretation_v1 import append_how_to_read_pdf_section

    append_how_to_read_pdf_section(body, report_class="monthly_digest", styles=digest_styles)

    if model.get("digest_truncated") and model.get("digest_truncation_display_lines"):
        warn_style = ParagraphStyle(
            name="DigestTruncWarn",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#b45309"),
            spaceBefore=6,
            spaceAfter=6,
        )
        body.append(
            Paragraph(
                "<b>Data scope notice:</b> " + html.escape(" ".join(model["digest_truncation_display_lines"])),
                warn_style,
            )
        )
    if model.get("digest_score_scope_note"):
        body.append(Paragraph(html.escape(str(model["digest_score_scope_note"])), small))
    if model.get("digest_jurisdiction_framing"):
        body.append(
            Paragraph(
                "<b>Jurisdiction context:</b> " + html.escape(str(model["digest_jurisdiction_framing"])),
                small,
            )
        )
    if model.get("digest_jurisdiction_fallback_disclaimer"):
        body.append(
            Paragraph(
                "<b>Default jurisdiction:</b> " + html.escape(str(model["digest_jurisdiction_fallback_disclaimer"])),
                small,
            )
        )
    dhl = model.get("digest_hiua_line")
    dhfn = model.get("digest_hiua_report_framing_notice")
    if dhl or dhfn:
        body.append(Paragraph("<b>Operational follow-up (applicability)</b>", h3))
        if dhl:
            body.append(Paragraph("<b>Summary:</b> " + html.escape(str(dhl)), small))
        if dhfn:
            body.append(Paragraph(html.escape(str(dhfn)), small))

    body.append(PageBreak())

    # B — Executive snapshot
    body.append(Paragraph("Executive snapshot", h2))
    snap_line = (model.get("digest_snapshot_framing_line") or "").strip()
    if snap_line:
        body.append(Paragraph(html.escape(snap_line), small))
    body.append(Paragraph(html.escape(intelligence.get("executive_interpretation") or ""), interpret_style))

    trends = intelligence.get("trend_indicators") or {}
    stability = intelligence.get("portfolio_stability") or {}
    _lc_headline = model.get("last_calculated_at") or model.get("portfolio_last_calculated_at")
    exec_rows = [
        ["Metric", "Value"],
        [
            "Compliance score (0–100)",
            html.escape(
                str(
                    model.get("compliance_score_display")
                    if model.get("compliance_score_display") is not None
                    else (model.get("compliance_score") if model.get("compliance_score") is not None else "N/A")
                )
            ),
        ],
        ["Portfolio trajectory", html.escape(str(stability.get("trajectory") or "—"))],
        ["Score trend (vs prior month)", html.escape(str(trends.get("score_trend") or "—"))],
        ["Risk level", html.escape(str(model.get("risk_level") or "—"))],
        ["Overdue obligations", str(int(model.get("overdue") or 0))],
        ["Missing evidence", str(int(model.get("missing_evidence_count") or 0))],
        ["Expiring soon", str(int(model.get("expiring_soon") or 0))],
        ["Evidence uploads (period)", str(int(model.get("documents_uploaded_period") or 0))],
        ["Upload activity trend", html.escape(str(trends.get("upload_activity") or "—"))],
        ["Resolved items (period)", html.escape(str(trends.get("resolved_items") or "—"))],
        ["New risk items (period)", html.escape(str(trends.get("new_risk_items") or "—"))],
        [
            "Last calculated",
            html.escape(str(_lc_headline) if _lc_headline not in (None, "") else "—"),
        ],
    ]
    _ssm_pdf = (model.get("score_status_message") or "").strip()
    if _ssm_pdf:
        exec_rows.append(["Headline note", html.escape(_ssm_pdf)])
    t_exec = Table([[Paragraph(cell, styles["Normal"]) for cell in row] for row in exec_rows], colWidths=[9 * cm, 7 * cm])
    t_exec.setStyle(_table_style())
    body.append(t_exec)
    body.append(Spacer(1, 0.35 * cm))

    # C — What changed this month
    body.append(Paragraph("What changed this month", h2))
    for line in intelligence.get("what_changed") or []:
        body.append(Paragraph(html.escape(line), styles["Normal"]))
    body.append(Spacer(1, 0.25 * cm))

    # D — Priority actions for next 30 days
    if model.get("include_recommendations", True) or model.get("include_action_items", True):
        body.append(Paragraph("Priority actions — next 30 days", h2))
        priorities = intelligence.get("priority_actions") or {}
        _priority_section(body, "Immediate attention", priorities.get("immediate") or [], styles, h3)
        _priority_section(body, "Upcoming actions", priorities.get("upcoming") or [], styles, h3)
        _priority_section(body, "Monitoring only", priorities.get("monitoring") or [], styles, h3)
        body.append(Spacer(1, 0.2 * cm))

    body.append(PageBreak())

    # E — Portfolio risk highlights
    body.append(Paragraph("Portfolio risk highlights", h2))
    highlights = intelligence.get("risk_highlights") or []
    if highlights:
        for hl in highlights:
            body.append(Paragraph(f"• {html.escape(hl)}", styles["Normal"]))
    else:
        body.append(Paragraph("No elevated operational risks beyond routine monitoring.", styles["Normal"]))
    body.append(Spacer(1, 0.3 * cm))

    # F — Property movement summary
    if model.get("include_property_breakdown", True):
        body.append(Paragraph("Property movement summary", h2))
        movement = intelligence.get("property_movement") or []
        if not movement:
            body.append(Paragraph("No properties in scope.", styles["Normal"]))
        else:
            mov_widths = proportional_col_widths(doc.width, [0.28, 0.12, 0.12, 0.14, 0.34])
            mov_rows = [
                [
                    _digest_table_cell("Property", table_cell_style, bold=True),
                    _digest_table_cell("Prior score", table_cell_style, bold=True),
                    _digest_table_cell("Current", table_cell_style, bold=True),
                    _digest_table_cell("Direction", table_cell_style, bold=True),
                    _digest_table_cell("Key change", table_cell_style, bold=True),
                ]
            ]
            for row in movement:
                mov_rows.append(
                    [
                        _digest_table_cell(row.get("property") or "—", table_cell_style),
                        _digest_table_cell(row.get("previous_score") or "—", table_cell_style),
                        _digest_table_cell(row.get("current_score") or "—", table_cell_style),
                        _digest_table_cell(row.get("direction") or "—", table_cell_style),
                        _digest_table_cell(row.get("key_change") or "—", table_cell_style),
                    ]
                )
            mt = Table(mov_rows, repeatRows=1, colWidths=mov_widths, splitByRow=1)
            mt.setStyle(_table_style())
            body.append(mt)
        body.append(Spacer(1, 0.3 * cm))

    # G — Evidence activity summary
    if model.get("include_recent_documents", True):
        body.append(Paragraph("Evidence activity summary", h2))
        for line in (intelligence.get("evidence_activity") or {}).get("lines") or []:
            body.append(Paragraph(f"• {html.escape(line)}", styles["Normal"]))
        body.append(Spacer(1, 0.3 * cm))

    # H — Optional condensed appendix (high-risk only)
    appendix = intelligence.get("condensed_appendix") or []
    if appendix:
        body.append(Paragraph("High-priority obligations (condensed)", h2))
        body.append(
            Paragraph(
                "Selected high-risk items only. Full requirement detail is available in the portal and dedicated reports.",
                small,
            )
        )
        app_widths = proportional_col_widths(doc.width, [0.24, 0.36, 0.20, 0.20])
        app_rows = [
            [
                _digest_table_cell("Property", table_cell_style, bold=True),
                _digest_table_cell("Obligation", table_cell_style, bold=True),
                _digest_table_cell("Status", table_cell_style, bold=True),
                _digest_table_cell("Evidence", table_cell_style, bold=True),
            ]
        ]
        for row in appendix:
            app_rows.append(
                [
                    _digest_table_cell(row.get("property") or "—", table_cell_style),
                    _digest_table_cell(row.get("obligation") or "—", table_cell_style),
                    _digest_table_cell(row.get("status") or "—", table_cell_style),
                    _digest_table_cell(row.get("evidence") or "—", table_cell_style),
                ]
            )
        at = Table(app_rows, repeatRows=1, colWidths=app_widths, splitByRow=1)
        at.setStyle(_table_style())
        body.append(at)

    body.append(PageBreak())

    body.append(Paragraph("Method and limitations", h2))
    body.append(
        Paragraph(
            "This digest is an operational intelligence briefing — not legal advice, not an audit evidence pack, "
            "and not a complete requirement register. Figures reflect tracked obligations and evidence states "
            "held in Compliance Vault Pro at generation time.",
            styles["Normal"],
        )
    )
    body.append(
        Paragraph(
            "<b>Estimated vs verified dates:</b> Estimated dates are derived from renewal rules until verified "
            "evidence is on file. Uploading and verifying evidence improves accuracy.",
            small,
        )
    )
    body.append(Spacer(1, 0.3 * cm))
    foot = [f"Generated {html.escape(str(model.get('generated_at_display') or ''))}."]
    if model.get("customer_reference"):
        foot.append(f"Client reference: {html.escape(str(model.get('customer_reference')))}.")
    if getattr(brand, "include_pleerity_attribution", True) and getattr(brand, "powered_by_text", None):
        foot.append(html.escape(str(brand.powered_by_text)))
    body.append(Paragraph("<br/>".join(foot), small))
    body.append(Paragraph(html.escape(ACCESSIBILITY_ENHANCED_NOTICE), small))

    doc.build(body, onFirstPage=on_first, onLaterPages=on_later)
    out = buffer.getvalue()
    buffer.close()
    return out


def write_monthly_digest_pdf_to_storage(client_id: str, report_month_key: str, pdf_bytes: bytes) -> str:
    """Persist PDF under DATA_DIR/monthly_digest_pdfs/{client_id}/{report_month_key}.pdf."""
    data_dir = resolve_data_dir()
    rel = Path("monthly_digest_pdfs") / client_id / f"{report_month_key}.pdf"
    dest = Path(data_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(pdf_bytes)
    return str(rel).replace("\\", "/")
