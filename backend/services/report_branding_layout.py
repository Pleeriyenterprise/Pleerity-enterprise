"""
REPORTING-PRESENTATION-USABILITY-PHASE-04 — reusable ReportLab cover, branding, accessibility.

White-label aware: uses branding_resolver ``to_report_dict()`` (logo_path, company_name, source).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Image, Paragraph, Spacer

from services.report_layout_governance import GovernancePdfContext, export_disclosure_paragraphs
from xml.sax.saxutils import escape as _xml_escape

ACCESSIBILITY_ENHANCED_NOTICE = (
    "Accessibility-enhanced PDF: logical section headings, improved table contrast, and selectable text. "
    "Not PDF/UA certified."
)

LOGO_MAX_WIDTH = 42 * mm
LOGO_MAX_HEIGHT = 16 * mm


def _logo_flowable(branding: Dict[str, Any]) -> Optional[Image]:
    path = (branding.get("logo_path") or "").strip()
    if not path or not Path(path).is_file():
        return None
    try:
        return Image(path, width=LOGO_MAX_WIDTH, height=LOGO_MAX_HEIGHT, kind="proportional")
    except Exception:
        return None


def append_report_cover_block(
    elements: List[Any],
    *,
    report_title: str,
    branding: Dict[str, Any],
    gov_ctx: GovernancePdfContext,
    styles: Dict[str, Any],
    account_line: str = "",
    scope_line: str = "",
    extra_metadata_lines: Optional[List[str]] = None,
) -> None:
    """Branded cover: logo, title, metadata strip, governance identity (disclosures preserved)."""
    logo = _logo_flowable(branding)
    if logo:
        elements.append(logo)
        elements.append(Spacer(1, 8))

    brand_name = (branding.get("brand_company_name") or branding.get("company_name") or "").strip()
    wl = branding.get("branding_source") == "client_white_label"
    if brand_name:
        sub = f"<b>{_xml_escape(brand_name)}</b>"
        if wl and branding.get("report_header_text"):
            sub += f"<br/>{_xml_escape(str(branding['report_header_text'])[:120])}"
        elif not wl:
            tag = (branding.get("tagline") or "").strip()
            if tag:
                sub += f"<br/><font size=\"9\">{_xml_escape(tag[:80])}</font>"
        elements.append(Paragraph(sub, styles.get("subtitle") or styles["body"]))
        elements.append(Spacer(1, 10))

    elements.append(Paragraph(_xml_escape(report_title), styles["title"]))
    meta_lines: List[str] = []
    if account_line:
        meta_lines.append(account_line)
    if scope_line:
        meta_lines.append(scope_line)
    meta_lines.append(
        f"<b>Export grade:</b> {_xml_escape(gov_ctx.export_grade_label or gov_ctx.export_grade)}"
    )
    if gov_ctx.artifact_id:
        meta_lines.append(f"<b>Artifact ID:</b> {_xml_escape(gov_ctx.artifact_id)}")
    meta_lines.append(f"<b>Generated (UTC):</b> {_xml_escape(gov_ctx.generated_at.strftime('%d %B %Y at %H:%M UTC'))}")
    for line in extra_metadata_lines or []:
        meta_lines.append(line)
    elements.append(Paragraph("<br/>".join(meta_lines), styles.get("subtitle") or styles["body"]))
    elements.append(Spacer(1, 6))
    elements.extend(export_disclosure_paragraphs(gov_ctx, styles))
    elements.append(Paragraph(f"<font size=\"8\">{_xml_escape(ACCESSIBILITY_ENHANCED_NOTICE)}</font>", styles["small"]))
    elements.append(Spacer(1, 12))
    elements.append(
        HRFlowable(
            width="100%",
            thickness=1,
            color=colors.Color(0.75, 0.75, 0.75),
            spaceAfter=14,
        )
    )


def append_section_divider(
    elements: List[Any],
    section_label: str,
    styles: Dict[str, Any],
    *,
    level: int = 2,
) -> None:
    """Consistent section break with visible heading hierarchy."""
    style = styles["heading"] if level <= 2 else styles.get("body", styles["heading"])
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(_xml_escape(section_label), style))
    elements.append(Spacer(1, 4))


def append_readability_property_banner(
    elements: List[Any],
    property_label: str,
    styles: Dict[str, Any],
) -> None:
    """Repeat property identity before matrix blocks on long reports."""
    elements.append(
        Paragraph(
            f"<b>Property:</b> {_xml_escape(property_label)}",
            styles.get("small") or styles["body"],
        )
    )
    elements.append(Spacer(1, 4))
