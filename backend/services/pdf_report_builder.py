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


def build_score_explanation_report(
    client_id: str,
    score_payload: dict,
    client_doc: dict,
    branding: dict,
) -> bytes:
    """
    Build Compliance Score Summary (Informational) PDF. Audit-style, branded.
    Sections: cover, portfolio snapshot, what score means, weighting model,
    top drivers, property breakdown, appendix (full drivers). Footer: disclaimer + Pleerity line.
    """
    company_name = client_doc.get("company_name") or client_doc.get("full_name") or "Client"
    crn = client_doc.get("customer_reference") or client_id
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%d %B %Y at %H:%M UTC")
    data_as_of = score_payload.get("score_last_calculated_at") or now.isoformat()
    if isinstance(data_as_of, str) and len(data_as_of) > 19:
        data_as_of = data_as_of[:19].replace("T", " ")

    branding = branding or {
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "company_name": company_name,
    }
    styles, table_style = _build_styles_and_table_style(branding)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50,
    )
    elements = []

    # —— 1. Cover ——
    elements.append(Spacer(1, 60))
    elements.append(Paragraph("Compliance Score Summary (Informational)", styles["title"]))
    elements.append(Paragraph(
        f"{company_name}<br/>CRN: {crn}<br/>Generated: {now_str}<br/>Data as of: {data_as_of}",
        styles["subtitle"],
    ))
    elements.append(Paragraph(
        "Informational tracking indicator only. Not legal advice. Status based on portal records; may apply depending on your situation.",
        styles["small"],
    ))
    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.Color(*_hex_to_rgb(branding.get("secondary_color", "#00B8A9"))), spaceAfter=20))
    elements.append(PageBreak())

    # —— 2. Portfolio snapshot ——
    elements.append(Paragraph("Portfolio snapshot", styles["heading"]))
    score = score_payload.get("score")
    grade = score_payload.get("grade") or "—"
    stats = score_payload.get("stats") or {}
    valid = stats.get("compliant", 0)
    expiring = stats.get("expiring_soon", 0)
    overdue = stats.get("overdue", 0)
    props_count = score_payload.get("properties_count", 0)
    completeness = score_payload.get("data_completeness_percent")
    completeness_str = f"{completeness}%" if completeness is not None else "—"
    model_ver = score_payload.get("score_model_version") or "—"
    snapshot_text = f"""
    <b>Overall score:</b> {score if score is not None else '—'}/100 &nbsp;|&nbsp; <b>Grade:</b> {grade}
    <br/><br/>
    <b>Valid:</b> {valid} &nbsp;|&nbsp; <b>Expiring soon:</b> {expiring} &nbsp;|&nbsp; <b>Overdue:</b> {overdue}
    <br/>
    <b>Properties monitored:</b> {props_count} &nbsp;|&nbsp; <b>Data completeness:</b> {completeness_str} &nbsp;|&nbsp; <b>Model:</b> CVP Score v{model_ver}
    """
    elements.append(Paragraph(snapshot_text, styles["body"]))
    elements.append(Spacer(1, 24))

    # —— 3. What the score means ——
    elements.append(Paragraph("What the score means", styles["heading"]))
    elements.append(Paragraph(
        "<b>Scope (included):</b> Applicable tracked items for each property (e.g. Gas Safety, EICR, EPC, Licence if configured).",
        styles["body"],
    ))
    elements.append(Paragraph(
        "<b>Excluded:</b> Council-specific rules unless configured; optional uploads not tracked; evidence not uploaded/confirmed.",
        styles["body"],
    ))
    elements.append(Paragraph(
        "<b>Definitions:</b> Valid = current and in date; Expiring soon = due within the configured window; Overdue = due date passed; Missing evidence = no upload; Not applicable = excluded from score.",
        styles["body"],
    ))
    elements.append(Paragraph(
        "<b>Updates:</b> Score recalculates automatically when documents, dates, applicability, or status changes.",
        styles["body"],
    ))
    elements.append(Spacer(1, 24))

    # —— 4. Weighting model ——
    elements.append(Paragraph("Weighting model", styles["heading"]))
    weights = score_payload.get("weights") or {}
    breakdown = score_payload.get("breakdown") or {}
    components = score_payload.get("components") or {}
    weight_rows = [["Component", "Weight", "Your score (%)"]]
    comp_map = {"status": "status", "expiry": "timeline", "documents": "documents", "overdue_penalty": "urgency"}
    break_map = {"status": "status_score", "expiry": "expiry_score", "documents": "document_score", "overdue_penalty": "overdue_penalty_score"}
    for key, label in [("status", "Status"), ("expiry", "Timeline"), ("documents", "Documents"), ("overdue_penalty", "Urgency impact")]:
        w = weights.get(key, "—")
        comp = components.get(comp_map[key])
        sc = comp.get("score") if isinstance(comp, dict) else breakdown.get(break_map[key])
        weight_rows.append([label, str(w), str(round(sc)) if sc is not None else "—"])
    if len(weight_rows) > 1:
        wt = Table(weight_rows, colWidths=[180, 80, 100])
        wt.setStyle(table_style)
        elements.append(wt)
    elements.append(Spacer(1, 24))

    # —— 5. Top drivers ——
    drivers = score_payload.get("drivers") or []
    top_drivers = drivers[:10]
    elements.append(Paragraph("Top drivers (what is affecting your score)", styles["heading"]))
    if not top_drivers:
        elements.append(Paragraph("No issues detected based on current portal records.", styles["body"]))
    else:
        driver_rows = [["Property", "Requirement", "Status", "Date used", "Evidence", "Next step"]]
        for d in top_drivers:
            next_step = "—"
            acts = d.get("actions") or []
            if "UPLOAD" in acts:
                next_step = "Upload document"
            elif "CONFIRM" in acts:
                next_step = "Confirm details"
            elif "VIEW" in acts:
                next_step = "View requirement"
            date_used = d.get("date_used")
            if date_used and isinstance(date_used, str):
                date_used = date_used[:10] if len(date_used) >= 10 else date_used
            driver_rows.append([
                (d.get("property_name") or d.get("property_id") or "—")[:25],
                (d.get("requirement_name") or "—")[:30],
                (d.get("status") or "—"),
                str(date_used) if date_used else "—",
                "Yes" if d.get("evidence_uploaded") else "No",
                next_step,
            ])
        dt = Table(driver_rows, colWidths=[100, 120, 70, 75, 50, 95])
        dt.setStyle(table_style)
        elements.append(dt)
    elements.append(Spacer(1, 24))

    # —— 6. Property breakdown ——
    elements.append(Paragraph("Property breakdown", styles["heading"]))
    prop_breakdown = score_payload.get("property_breakdown") or []
    if not prop_breakdown:
        elements.append(Paragraph("No property data in scope.", styles["body"]))
    else:
        prop_rows = [["Property", "Score", "Valid", "Expiring", "Overdue"]]
        for p in prop_breakdown[:30]:
            prop_rows.append([
                (p.get("name") or p.get("property_id") or "—")[:40],
                str(p.get("score")) if p.get("score") is not None else "—",
                str(p.get("valid", 0)),
                str(p.get("expiring", 0)),
                str(p.get("overdue", 0)),
            ])
        pt = Table(prop_rows, colWidths=[200, 50, 50, 60, 60])
        pt.setStyle(table_style)
        elements.append(pt)
    elements.append(Spacer(1, 24))

    # —— 7. Appendix: full driver table (optional) ——
    if drivers and len(drivers) > 10:
        elements.append(Paragraph("Appendix: full driver list", styles["heading"]))
        full_rows = [["Property", "Requirement", "Status", "Date used", "Evidence"]]
        for d in drivers:
            date_used = d.get("date_used")
            if date_used and isinstance(date_used, str):
                date_used = date_used[:10] if len(date_used) >= 10 else date_used
            full_rows.append([
                (d.get("property_name") or d.get("property_id") or "—")[:30],
                (d.get("requirement_name") or "—")[:35],
                (d.get("status") or "—")[:15],
                str(date_used) if date_used else "—",
                "Y" if d.get("evidence_uploaded") else "N",
            ])
        ft = Table(full_rows, colWidths=[120, 130, 70, 75, 45])
        ft.setStyle(table_style)
        elements.append(ft)
    elements.append(Spacer(1, 20))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray, spaceAfter=12))
    elements.append(Paragraph("Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance", styles["footer"]))
    elements.append(Paragraph(f"CRN: {crn} &nbsp;|&nbsp; Generated: {now_str}", styles["footer"]))
    elements.append(Paragraph("Informational indicator based on portal records. Not legal advice.", styles["footer"]))

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
