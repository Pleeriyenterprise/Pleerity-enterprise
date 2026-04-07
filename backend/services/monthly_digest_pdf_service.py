"""
Branded monthly compliance PDF (audit layer). ReportLab; uses resolve_branding for letterhead.
Structured sections complement the action email — not a duplicate layout.
"""
from __future__ import annotations

import html
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.monthly_digest_limits import DIGEST_PDF_MAX_REQUIREMENT_ROWS

logger = logging.getLogger(__name__)


def _hex_color(raw: Optional[str], fallback: str = "#0B1D3A") -> colors.Color:
    s = (raw or fallback).strip()
    if s.startswith("#") and len(s) in (4, 7):
        try:
            return colors.HexColor(s)
        except Exception:
            pass
    return colors.HexColor(fallback if fallback.startswith("#") else "#" + fallback)


def build_monthly_digest_pdf_bytes(model: Dict[str, Any], *, brand: Any) -> bytes:
    """
    Full audit PDF from digest assembly model.
    ``brand`` is ResolvedBrandingProfile from branding_resolver_service.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Monthly Compliance Summary",
    )
    styles = getSampleStyleSheet()
    primary = _hex_color(getattr(brand, "primary_color", None))
    title_style = ParagraphStyle(
        name="DigestTitle",
        parent=styles["Heading1"],
        textColor=primary,
        spaceAfter=10,
        fontSize=18,
    )
    h2 = ParagraphStyle(name="H2", parent=styles["Heading2"], textColor=primary, spaceBefore=12, spaceAfter=8)
    h3 = ParagraphStyle(name="H3", parent=styles["Heading3"], spaceBefore=8, spaceAfter=6)
    small = ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#64748b"))

    body: List[Any] = []
    company = html.escape(str(getattr(brand, "company_name", None) or "Pleerity Enterprise Ltd"))
    tag = html.escape(str(getattr(brand, "tagline", None) or "AI-Driven Solutions & Compliance"))
    logo_path = getattr(brand, "logo_path", None)
    if logo_path and Path(str(logo_path)).is_file():
        try:
            img = Image(str(logo_path), width=3.2 * cm, height=1.2 * cm)
            body.append(img)
            body.append(Spacer(1, 0.2 * cm))
        except Exception as e:
            logger.debug("digest PDF logo skip: %s", e)

    report_title = html.escape(str(model.get("reporting_month_label") or "Monthly report"))
    body.append(Paragraph(f"<b>{company}</b><br/><i>{tag}</i>", styles["Normal"]))
    body.append(Spacer(1, 0.3 * cm))
    body.append(Paragraph("Monthly Compliance Summary (audit report)", title_style))
    body.append(Paragraph(f"<b>Reporting period:</b> {html.escape(report_title)}", styles["Normal"]))
    body.append(
        Paragraph(
            f"<b>Generated:</b> {html.escape(str(model.get('generated_at_display') or model.get('data_as_of') or ''))}",
            styles["Normal"],
        )
    )
    body.append(
        Paragraph(
            f"<b>Account:</b> {html.escape(str(model.get('account_name') or model.get('client_name') or ''))}"
            + (
                f" &nbsp;|&nbsp; <b>CRN:</b> {html.escape(str(model.get('customer_reference')))}"
                if model.get("customer_reference")
                else ""
            ),
            styles["Normal"],
        )
    )
    body.append(
        Paragraph(
            f"<b>Properties in scope:</b> {int(model.get('properties_count') or 0)}",
            styles["Normal"],
        )
    )
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
        info_style = ParagraphStyle(
            name="DigestScopeInfo",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#1e40af"),
            spaceBefore=4,
            spaceAfter=6,
        )
        body.append(Paragraph(html.escape(str(model["digest_score_scope_note"])), info_style))
    if model.get("digest_jurisdiction_framing"):
        jur_style = ParagraphStyle(
            name="DigestJurisdiction",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=6,
            spaceAfter=6,
        )
        body.append(
            Paragraph(
                "<b>Jurisdiction context:</b> " + html.escape(str(model["digest_jurisdiction_framing"])),
                jur_style,
            )
        )
    if model.get("digest_jurisdiction_fallback_disclaimer"):
        fb_style = ParagraphStyle(
            name="DigestJurFallback",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#92400e"),
            spaceBefore=8,
            spaceAfter=6,
        )
        body.append(
            Paragraph(
                "<b>Default jurisdiction:</b> " + html.escape(str(model["digest_jurisdiction_fallback_disclaimer"])),
                fb_style,
            )
        )
    body.append(PageBreak())

    # Section 2 — Executive summary
    body.append(Paragraph("2. Executive summary", h2))
    exec_rows = [
        ["Metric", "Value"],
        ["Compliance score (0–100)", str(int(model.get("compliance_score") or 0))],
        ["Risk level", html.escape(str(model.get("risk_level") or "—"))],
        ["Total tracked requirements", str(int(model.get("total_requirements") or 0))],
        ["Valid (compliant)", str(int(model.get("valid_count") or model.get("compliant") or 0))],
        ["Expiring soon", str(int(model.get("expiring_soon") or 0))],
        ["Overdue", str(int(model.get("overdue") or 0))],
        ["Missing evidence", str(int(model.get("missing_evidence_count") or 0))],
        ["Open compliance jobs", str(int(model.get("open_compliance_jobs") or 0))],
        ["Open maintenance jobs", str(int(model.get("open_maintenance_jobs") or 0))],
    ]
    t_exec = Table([[Paragraph(cell, styles["Normal"]) for cell in row] for row in exec_rows], colWidths=[9 * cm, 7 * cm])
    t_exec.setStyle(
        TableStyle(
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
    )
    body.append(t_exec)
    body.append(Spacer(1, 0.4 * cm))

    # Section 3 — What changed
    body.append(Paragraph("3. What changed since your last report", h2))
    d = model.get("deltas") or {}
    if not d.get("has_prior_snapshot"):
        body.append(
            Paragraph(
                "This is your first stored monthly compliance report for this account. "
                "Future reports will compare score, overdue items, and document activity against this baseline.",
                styles["Normal"],
            )
        )
    else:
        lines: List[str] = []
        sd = d.get("score_delta")
        if sd is not None:
            try:
                sdi = int(sd)
                lines.append(f"Compliance score movement: {sdi:+d} point(s) since the last report.")
            except (TypeError, ValueError):
                lines.append(f"Compliance score movement: {sd}")
        if d.get("newly_overdue_labels"):
            lines.append("Newly overdue: " + "; ".join(html.escape(x) for x in d["newly_overdue_labels"][:6]))
        if d.get("resolved_improved_labels"):
            lines.append("Resolved or improved: " + "; ".join(html.escape(x) for x in d["resolved_improved_labels"][:6]))
        if d.get("newly_expiring_labels"):
            lines.append("Newly expiring soon: " + "; ".join(html.escape(x) for x in d["newly_expiring_labels"][:6]))
        doc_delta = d.get("documents_uploaded_delta_vs_prev_period")
        if doc_delta is not None:
            try:
                ddi = int(doc_delta)
                lines.append(f"Document uploads vs prior reporting period: {ddi:+d}.")
            except (TypeError, ValueError):
                lines.append(f"Document uploads vs prior reporting period: {doc_delta}.")
        elif model.get("include_recent_documents", True):
            lines.append(f"Documents uploaded in this reporting period: {int(model.get('documents_uploaded_period') or 0)}")
        nmd = d.get("newly_missing_evidence_delta")
        if nmd is not None and nmd != 0:
            try:
                nmdi = int(nmd)
                lines.append(f"Missing evidence items vs last report: {nmdi:+d}.")
            except (TypeError, ValueError):
                lines.append(f"Missing evidence items vs last report: {nmd}.")
        if model.get("digest_period_activity_included") and model.get("include_audit_summary"):
            pal = model.get("digest_period_activity_lines") or []
            if pal:
                lines.append("Operational activity (period): " + "; ".join(html.escape(str(x)) for x in pal[:4]))
        if not lines:
            lines.append("No material score or status movements were detected against your previous report snapshot.")
        for line in lines:
            body.append(Paragraph(line, styles["Normal"]))
    body.append(Spacer(1, 0.3 * cm))

    show_property_breakdown = model.get("include_property_breakdown", True)
    # Section 4 — Property summary (optional per notification preference)
    if show_property_breakdown:
        body.append(Paragraph("4. Property summary", h2))
        prop_rows: List[List[str]] = [
            ["Property", "Score", "Risk", "Overdue", "Expiring", "Missing ev.", "Open jobs"]
        ]
        for pr in model.get("property_rows_pdf") or []:
            prop_rows.append(
                [
                    html.escape(str(pr.get("name") or "—"))[:45],
                    str(pr.get("score") if pr.get("score") is not None else "—"),
                    html.escape(str(pr.get("risk_level") or "—"))[:14],
                    str(int(pr.get("overdue_count") or 0)),
                    str(int(pr.get("expiring_soon_count") or 0)),
                    str(int(pr.get("missing_evidence_count") or 0)),
                    str(int(pr.get("open_jobs_count") or 0)),
                ]
            )
        if len(prop_rows) == 1:
            body.append(Paragraph("No properties in scope.", styles["Normal"]))
        else:
            pt = Table(prop_rows, repeatRows=1, colWidths=[3.8 * cm, 1.2 * cm, 2 * cm, 1.2 * cm, 1.2 * cm, 1.3 * cm, 1.3 * cm])
            pt.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            body.append(pt)
    body.append(PageBreak())

    s_req, s_risk, s_method, s_foot = (5, 6, 7, 8) if show_property_breakdown else (4, 5, 6, 7)

    # Requirements (paragraph list to avoid clipped wide tables)
    body.append(Paragraph(f"{s_req}. Requirement breakdown", h2))
    body.append(
        Paragraph(
            "Each row reflects live requirement state, evidence, and effective dates as held in Compliance Vault Pro.",
            small,
        )
    )
    reqs = model.get("requirement_rows_pdf") or []
    if not reqs:
        body.append(Paragraph("No applicable requirements to list.", styles["Normal"]))
    else:
        cap = DIGEST_PDF_MAX_REQUIREMENT_ROWS
        for i, rr in enumerate(reqs[:cap]):
            prop = html.escape(str(rr.get("property_name") or ""))
            name = html.escape(str(rr.get("requirement_name") or ""))
            st = html.escape(str(rr.get("state") or ""))
            ev = html.escape(str(rr.get("evidence_state") or ""))
            du = html.escape(str(rr.get("date_used") or "—"))
            dk = "verified" if rr.get("date_kind") == "verified" else "estimated"
            dv = rr.get("days_value")
            dd = rr.get("days_direction")
            day_part = ""
            if dv is not None and dd == "remaining":
                day_part = f", {int(dv)} day(s) remaining"
            elif dv is not None and dd == "overdue":
                day_part = f", {int(dv)} day(s) overdue"
            na = html.escape(str(rr.get("next_action") or ""))
            block = (
                f"<b>{name}</b> — {prop}<br/>"
                f"<font size=8>State: {st} | Evidence: {ev} | Date used: {du} ({dk}){day_part}<br/>"
                f"Recommended next action: {na}</font>"
            )
            body.append(Paragraph(block, styles["Normal"]))
            if i < min(len(reqs), cap) - 1:
                body.append(Spacer(1, 0.15 * cm))
        if len(reqs) > cap:
            body.append(
                Paragraph(
                    f"<i>… plus {len(reqs) - cap} further requirements (view full detail in the portal).</i>",
                    small,
                )
            )

    body.append(PageBreak())

    body.append(Paragraph(f"{s_risk}. Risk and operational guidance", h2))
    body.append(Paragraph("<b>Top risk drivers</b>", h3))
    drivers = model.get("top_risk_drivers") or []
    if drivers:
        for dr in drivers[:8]:
            body.append(Paragraph(f"• {html.escape(str(dr))}", styles["Normal"]))
    else:
        body.append(Paragraph("No additional risk drivers beyond your summary scores.", styles["Normal"]))
    body.append(Paragraph("<b>Recommended priorities</b>", h3))
    acts = model.get("top_next_actions") or []
    if acts:
        for ac in acts[:8]:
            body.append(Paragraph(f"• {html.escape(str(ac))}", styles["Normal"]))
    else:
        body.append(
            Paragraph(
                "Keep monitoring expiries in the calendar, maintain verified evidence, and clear overdue items first.",
                styles["Normal"],
            )
        )

    body.append(Paragraph(f"{s_method}. Method and limitations", h2))
    body.append(
        Paragraph(
            "<b>Estimated vs verified dates:</b> Dates marked as estimated are derived from renewal rules or extracted data "
            "until you confirm a date or supply verified evidence. Verified dates come from confirmed expiry data or "
            "verified documents. Uploading and verifying evidence improves accuracy across your portfolio.",
            styles["Normal"],
        )
    )
    body.append(
        Paragraph(
            "<b>Scope:</b> This report is generated from tracked requirements, evidence states, and dates recorded in "
            "Compliance Vault Pro. It is operational and informational — not legal advice. Seek professional counsel where needed.",
            styles["Normal"],
        )
    )

    body.append(Paragraph(f"{s_foot}. Footer", h2))
    body.append(Spacer(1, 0.2 * cm))
    foot = [
        f"Generated {html.escape(str(model.get('generated_at_display') or ''))}.",
    ]
    if model.get("customer_reference"):
        foot.append(f"Client reference: {html.escape(str(model.get('customer_reference')))}.")
    if getattr(brand, "include_pleerity_attribution", True) and getattr(brand, "powered_by_text", None):
        foot.append(html.escape(str(brand.powered_by_text)))
    body.append(Paragraph("<br/>".join(foot), small))

    doc.build(body)
    out = buffer.getvalue()
    buffer.close()
    return out


def write_monthly_digest_pdf_to_storage(client_id: str, report_month_key: str, pdf_bytes: bytes) -> str:
    """
    Persist PDF under DATA_DIR/monthly_digest_pdfs/{client_id}/{report_month_key}.pdf.
    Returns relative path from DATA_DIR for storage in digest_logs.
    """
    data_dir = os.getenv("DATA_DIR", "/tmp")
    rel = Path("monthly_digest_pdfs") / client_id / f"{report_month_key}.pdf"
    dest = Path(data_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(pdf_bytes)
    return str(rel).replace("\\", "/")
