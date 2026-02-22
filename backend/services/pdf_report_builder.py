"""
Deterministic PDF report builder (sync).
Evidence Readiness report from pre-loaded report_data. No AI; template-only.
Footer: "This report does not constitute legal advice."
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io

PDF_FOOTER_DISCLAIMER = "This report does not constitute legal advice."


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = (hex_color or "#0B1D3A").lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _parse_date(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _days_to_expiry(due_date: Any, now: datetime) -> Optional[int]:
    d = _parse_date(due_date)
    if d is None:
        return None
    # Normalize to date for day count
    if d.tzinfo:
        d = d.astimezone(now.tzinfo)
    n = now.replace(tzinfo=None) if now.tzinfo else now
    delta = (d.replace(tzinfo=None) if d.tzinfo else d) - n
    return delta.days


def _status_label(s: Optional[str]) -> str:
    if not s:
        return "Missing evidence"
    u = (s or "").upper()
    if u in ("COMPLIANT", "VALID"):
        return "Evidence in place"
    if u == "EXPIRING_SOON":
        return "Expiring soon"
    if u in ("OVERDUE", "EXPIRED"):
        return "Expired / overdue"
    if u in ("PENDING", "MISSING"):
        return "Missing evidence"
    return (s or "—")[:20]


def _build_styles_and_table_style(branding: dict) -> tuple:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("T", parent=base["Title"], fontSize=24, spaceAfter=12, alignment=TA_LEFT),
        "subtitle": ParagraphStyle("S", parent=base["Normal"], fontSize=12, spaceAfter=20),
        "heading": ParagraphStyle("H", parent=base["Heading2"], fontSize=14, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("B", parent=base["Normal"], fontSize=10),
        "small": ParagraphStyle("Sm", parent=base["Normal"], fontSize=8),
        "footer": ParagraphStyle("F", parent=base["Normal"], fontSize=8, alignment=TA_CENTER),
    }
    primary_rgb = _hex_to_rgb(branding.get("primary_color", "#0B1D3A"))
    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*primary_rgb)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])
    return styles, table_style


def _derive_counts_and_risk(properties: List[dict], requirements: List[dict], now: datetime) -> dict:
    valid = sum(1 for r in requirements if (r.get("status") or "").upper() in ("COMPLIANT", "VALID"))
    expiring = sum(1 for r in requirements if (r.get("status") or "").upper() == "EXPIRING_SOON")
    overdue = sum(1 for r in requirements if (r.get("status") or "").upper() in ("OVERDUE", "EXPIRED"))
    missing = sum(1 for r in requirements if (r.get("status") or "").upper() in ("PENDING", "MISSING"))
    scores = [p.get("compliance_score") for p in properties if p.get("compliance_score") is not None]
    portfolio_score = round(sum(scores) / len(scores)) if scores else None
    risk_levels = [p.get("risk_level") for p in properties if p.get("risk_level")]
    risk_level = risk_levels[0] if len(risk_levels) == 1 else (risk_levels[0] if risk_levels else "N/A")
    return {
        "valid_count": valid,
        "expiring_count": expiring,
        "overdue_count": overdue,
        "missing_count": missing,
        "portfolio_score": portfolio_score,
        "risk_level": risk_level,
    }


def _top_risk_drivers(requirements: List[dict], limit: int = 10) -> List[dict]:
    """Requirements that are overdue, expired, or expiring soon."""
    out = []
    for r in requirements:
        s = (r.get("status") or "").upper()
        if s in ("OVERDUE", "EXPIRED", "EXPIRING_SOON"):
            out.append({
                "requirement_type": r.get("requirement_type") or r.get("description") or "—",
                "status": _status_label(r.get("status")),
                "property_id": r.get("property_id"),
            })
    return out[:limit]


def build_portfolio_report(client_id: str, report_data: dict) -> bytes:
    """
    Build Evidence Readiness PDF for full portfolio. Sync; deterministic.
    report_data: client, properties, requirements, audit_logs, now_iso, branding (optional).
    """
    client = report_data.get("client") or {}
    company_name = client.get("company_name") or client.get("full_name") or "Client"
    crn = client.get("customer_reference") or client_id
    properties = report_data.get("properties") or []
    requirements = report_data.get("requirements") or []
    audit_logs = report_data.get("audit_logs") or []
    now_iso = report_data.get("now_iso")
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(timezone.utc)
    branding = report_data.get("branding") or {
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "company_name": company_name,
    }

    styles, table_style = _build_styles_and_table_style(branding)
    derived = _derive_counts_and_risk(properties, requirements, now)
    top_risks = _top_risk_drivers(requirements)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50,
    )
    elements = []

    # Cover
    elements.append(Spacer(1, 80))
    elements.append(Paragraph("Evidence Readiness Report", styles["title"]))
    elements.append(Paragraph(
        f"{company_name}<br/>CRN: {crn}<br/>Scope: portfolio<br/>Generated: {now.strftime('%d %B %Y at %H:%M UTC')}",
        styles["subtitle"],
    ))
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.Color(*_hex_to_rgb(branding.get("secondary_color", "#00B8A9"))), spaceAfter=20))
    elements.append(PageBreak())

    # Executive summary
    elements.append(Paragraph("Executive Summary", styles["heading"]))
    summary_text = f"""
    <b>Score:</b> {derived['portfolio_score'] if derived['portfolio_score'] is not None else 'N/A'}/100 &nbsp;|&nbsp;
    <b>Risk level:</b> {derived['risk_level']}
    <br/><br/>
    <b>Counts:</b> {len(properties)} propert(ies); {len(requirements)} requirements.
    Evidence in place: <b>{derived['valid_count']}</b> &nbsp;|&nbsp;
    Expiring soon: <b>{derived['expiring_count']}</b> &nbsp;|&nbsp;
    Expired/overdue: <b>{derived['overdue_count']}</b> &nbsp;|&nbsp;
    Missing evidence: <b>{derived['missing_count']}</b>
    """
    elements.append(Paragraph(summary_text, styles["body"]))
    elements.append(Spacer(1, 20))

    # Top risk drivers (if any)
    if top_risks:
        elements.append(Paragraph("Top risk drivers", styles["heading"]))
        risk_rows = [["Requirement type", "Status", "Property"]]
        for r in top_risks:
            risk_rows.append([(r["requirement_type"] or "—")[:40], r["status"], (r.get("property_id") or "—")[:20]])
        rt = Table(risk_rows, colWidths=[220, 120, 100])
        rt.setStyle(table_style)
        elements.append(rt)
        elements.append(Spacer(1, 20))

    # Portfolio breakdown
    elements.append(Paragraph("Portfolio breakdown", styles["heading"]))
    prop_data = [["Address", "Score", "Risk level", "Last updated"]]
    for p in properties[:50]:
        addr = p.get("address_line_1") or p.get("nickname") or p.get("property_id", "")
        score = p.get("compliance_score")
        risk = p.get("risk_level") or "—"
        updated = p.get("compliance_last_calculated_at") or "—"
        if isinstance(updated, str) and len(updated) > 16:
            updated = updated[:10]
        prop_data.append([addr[:50], str(score) if score is not None else "—", risk, updated])
    if len(prop_data) > 1:
        t = Table(prop_data, colWidths=[200, 50, 90, 80])
        t.setStyle(table_style)
        elements.append(t)
    else:
        elements.append(Paragraph("No properties in scope.", styles["body"]))
    elements.append(Spacer(1, 20))

    # Property detail – requirement matrix
    elements.append(Paragraph("Property detail – requirement matrix", styles["heading"]))
    reqs_by_prop: Dict[str, List[Dict]] = {}
    for r in requirements:
        reqs_by_prop.setdefault(r["property_id"], []).append(r)
    for p in properties[:20]:
        elements.append(Paragraph(f"<b>{p.get('address_line_1') or p.get('property_id')}</b>", styles["body"]))
        rows = [["Requirement", "Status", "Due date", "Days to expiry"]]
        for r in reqs_by_prop.get(p["property_id"], [])[:30]:
            due = r.get("due_date")
            due_str = due.isoformat()[:10] if hasattr(due, "isoformat") else str(due)[:10] if due else "—"
            days = _days_to_expiry(due, now)
            days_str = str(days) if days is not None else "—"
            rows.append([
                (r.get("description") or r.get("requirement_type") or "—")[:35],
                _status_label(r.get("status")),
                due_str,
                days_str,
            ])
        if len(rows) > 1:
            tb = Table(rows, colWidths=[180, 100, 80, 70])
            tb.setStyle(table_style)
            elements.append(tb)
        elements.append(Spacer(1, 12))
    elements.append(Spacer(1, 12))

    # Methodology
    elements.append(Paragraph("Scoring methodology summary", styles["heading"]))
    elements.append(Paragraph(
        "Scores are evidence-based: each applicable requirement contributes a weight; status (Evidence in place, Expiring soon, Expired/overdue, Missing evidence) maps to a factor. "
        "Risk level is derived from overall score and critical requirement status. This is not a legal compliance opinion.",
        styles["body"],
    ))
    elements.append(Spacer(1, 20))

    # Audit snapshot
    elements.append(Paragraph("Audit activity snapshot (last 30 days)", styles["heading"]))
    audit_data = [["Time", "Action", "Resource", "Details"]]
    for log in audit_logs[:50]:
        ts = log.get("timestamp") or "—"
        if isinstance(ts, str) and len(ts) > 19:
            ts = ts[:19].replace("T", " ")
        action = (log.get("action") or "—")[:30]
        res = f"{log.get('resource_type') or '-'}/{log.get('resource_id') or '-'}"[:25]
        meta = str((log.get("metadata") or {}).get("reason", ""))[:30]
        audit_data.append([ts, action, res, meta])
    if len(audit_data) > 1:
        at = Table(audit_data, colWidths=[90, 100, 100, 120])
        at.setStyle(table_style)
        elements.append(at)
    else:
        elements.append(Paragraph("No audit activity in the last 30 days.", styles["body"]))
    elements.append(Spacer(1, 24))

    # Footer disclaimer
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray, spaceAfter=12))
    elements.append(Paragraph(PDF_FOOTER_DISCLAIMER, styles["footer"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Generated by Pleerity Enterprise", styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def build_property_report(client_id: str, property_id: str, report_data: dict) -> bytes:
    """
    Build Evidence Readiness PDF for a single property. Sync; deterministic.
    report_data: client, properties (single), requirements, audit_logs, now_iso, branding (optional),
    optional score_delta, score_change_summary.
    """
    client = report_data.get("client") or {}
    company_name = client.get("company_name") or client.get("full_name") or "Client"
    crn = client.get("customer_reference") or client_id
    properties = report_data.get("properties") or []
    requirements = report_data.get("requirements") or []
    audit_logs = report_data.get("audit_logs") or []
    now_iso = report_data.get("now_iso")
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(timezone.utc)
    branding = report_data.get("branding") or {
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "company_name": company_name,
    }
    score_delta = report_data.get("score_delta")
    score_change_summary = report_data.get("score_change_summary")

    styles, table_style = _build_styles_and_table_style(branding)
    derived = _derive_counts_and_risk(properties, requirements, now)
    top_risks = _top_risk_drivers(requirements)
    prop = properties[0] if properties else {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50,
    )
    elements = []

    # Cover
    elements.append(Spacer(1, 80))
    elements.append(Paragraph("Evidence Readiness Report", styles["title"]))
    scope_line = f"Scope: property (Property: {property_id})"
    elements.append(Paragraph(
        f"{company_name}<br/>CRN: {crn}<br/>{scope_line}<br/>Generated: {now.strftime('%d %B %Y at %H:%M UTC')}",
        styles["subtitle"],
    ))
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.Color(*_hex_to_rgb(branding.get("secondary_color", "#00B8A9"))), spaceAfter=20))
    elements.append(PageBreak())

    # Executive summary
    elements.append(Paragraph("Executive Summary", styles["heading"]))
    score_line = f"<b>Score:</b> {derived['portfolio_score'] if derived['portfolio_score'] is not None else 'N/A'}/100 &nbsp;|&nbsp; <b>Risk level:</b> {derived['risk_level']}"
    if score_delta is not None or score_change_summary:
        score_line += "<br/><b>Score change:</b> " + (score_change_summary or (f"Delta {score_delta:+d}" if score_delta is not None else "—"))
    summary_text = f"""
    {score_line}
    <br/><br/>
    <b>Counts:</b> 1 property; {len(requirements)} requirements.
    Evidence in place: <b>{derived['valid_count']}</b> &nbsp;|&nbsp;
    Expiring soon: <b>{derived['expiring_count']}</b> &nbsp;|&nbsp;
    Expired/overdue: <b>{derived['overdue_count']}</b> &nbsp;|&nbsp;
    Missing evidence: <b>{derived['missing_count']}</b>
    """
    elements.append(Paragraph(summary_text, styles["body"]))
    elements.append(Spacer(1, 20))

    if top_risks:
        elements.append(Paragraph("Top risk drivers", styles["heading"]))
        risk_rows = [["Requirement type", "Status"]]
        for r in top_risks:
            risk_rows.append([(r["requirement_type"] or "—")[:50], r["status"]])
        rt = Table(risk_rows, colWidths=[300, 150])
        rt.setStyle(table_style)
        elements.append(rt)
        elements.append(Spacer(1, 20))

    # Property requirement matrix with days_to_expiry
    elements.append(Paragraph("Requirement matrix", styles["heading"]))
    rows = [["Requirement", "Status", "Due date", "Days to expiry"]]
    for r in requirements[:50]:
        due = r.get("due_date")
        due_str = due.isoformat()[:10] if hasattr(due, "isoformat") else str(due)[:10] if due else "—"
        days = _days_to_expiry(due, now)
        days_str = str(days) if days is not None else "—"
        rows.append([
            (r.get("description") or r.get("requirement_type") or "—")[:40],
            _status_label(r.get("status")),
            due_str,
            days_str,
        ])
    if len(rows) > 1:
        tb = Table(rows, colWidths=[220, 120, 90, 80])
        tb.setStyle(table_style)
        elements.append(tb)
    else:
        elements.append(Paragraph("No requirements for this property.", styles["body"]))
    elements.append(Spacer(1, 20))

    # Methodology
    elements.append(Paragraph("Scoring methodology summary", styles["heading"]))
    elements.append(Paragraph(
        "Scores are evidence-based; status (Evidence in place, Expiring soon, Expired/overdue, Missing evidence) maps to a factor. Risk level is derived from score. This is not a legal compliance opinion.",
        styles["body"],
    ))
    elements.append(Spacer(1, 20))

    # Audit snapshot
    elements.append(Paragraph("Audit activity snapshot (last 30 days)", styles["heading"]))
    audit_data = [["Time", "Action", "Resource", "Details"]]
    for log in audit_logs[:30]:
        ts = log.get("timestamp") or "—"
        if isinstance(ts, str) and len(ts) > 19:
            ts = ts[:19].replace("T", " ")
        action = (log.get("action") or "—")[:30]
        res = f"{log.get('resource_type') or '-'}/{log.get('resource_id') or '-'}"[:25]
        meta = str((log.get("metadata") or {}).get("reason", ""))[:30]
        audit_data.append([ts, action, res, meta])
    if len(audit_data) > 1:
        at = Table(audit_data, colWidths=[90, 100, 100, 120])
        at.setStyle(table_style)
        elements.append(at)
    else:
        elements.append(Paragraph("No audit activity in the last 30 days.", styles["body"]))
    elements.append(Spacer(1, 24))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray, spaceAfter=12))
    elements.append(Paragraph(PDF_FOOTER_DISCLAIMER, styles["footer"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Generated by Pleerity Enterprise", styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
