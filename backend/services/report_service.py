"""
Evidence Readiness PDF report service.
Enterprise-grade report with cover, executive summary, portfolio breakdown,
property requirement matrix, methodology, audit snapshot, and disclaimer.
Data loading is async; PDF build is delegated to pdf_report_builder (sync).
"""
from database import database
from datetime import datetime, timezone, timedelta
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
import logging

logger = logging.getLogger(__name__)

EVIDENCE_READINESS_DISCLAIMER = (
    "This report reflects document status recorded within the platform and does not constitute legal advice."
)


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = (hex_color or "#0B1D3A").lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))


async def generate_evidence_readiness_pdf(
    client_id: str,
    scope: str,
    property_id: Optional[str] = None,
) -> io.BytesIO:
    """
    Generate Evidence Readiness PDF.
    scope: "portfolio" | "property". If property, property_id must be set.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)

    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "company_name": 1, "full_name": 1, "customer_reference": 1},
    )
    company_name = (client or {}).get("company_name") or (client or {}).get("full_name") or "Client"
    crn = (client or {}).get("customer_reference") or client_id

    query = {"client_id": client_id}
    if scope == "property" and property_id:
        query["property_id"] = property_id
    properties = await db.properties.find(query, {"_id": 0}).to_list(500)
    if scope == "property" and property_id and not properties:
        raise ValueError("Property not found")

    property_ids = [p["property_id"] for p in properties]
    requirements = await db.requirements.find(
        {"client_id": client_id, "property_id": {"$in": property_ids}},
        {"_id": 0, "property_id": 1, "requirement_type": 1, "status": 1, "due_date": 1, "description": 1},
    ).to_list(5000)

    cutoff = (now - timedelta(days=30)).isoformat()
    audit_logs = await db.audit_logs.find(
        {"client_id": client_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0, "action": 1, "resource_type": 1, "resource_id": 1, "timestamp": 1, "metadata": 1},
    ).sort("timestamp", -1).to_list(500)

    # Reuse branding if available
    try:
        from services.professional_reports import professional_report_generator
        branding = await professional_report_generator.get_branding(client_id)
        styles = professional_report_generator.create_styles(branding)
        table_style = professional_report_generator.create_table_style(branding)
    except Exception:
        branding = {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9", "company_name": company_name}
        base = getSampleStyleSheet()
        styles = {
            "title": ParagraphStyle("T", parent=base["Title"], fontSize=24, spaceAfter=12, alignment=TA_LEFT),
            "subtitle": ParagraphStyle("S", parent=base["Normal"], fontSize=12, spaceAfter=20),
            "heading": ParagraphStyle("H", parent=base["Heading2"], fontSize=14, spaceBefore=12, spaceAfter=6),
            "body": ParagraphStyle("B", parent=base["Normal"], fontSize=10),
            "small": ParagraphStyle("Sm", parent=base["Normal"], fontSize=8),
            "footer": ParagraphStyle("F", parent=base["Normal"], fontSize=8, alignment=TA_CENTER),
        }
        primary_rgb = _hex_to_rgb(branding["primary_color"])
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

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )
    elements = []

    # —— Cover ——
    elements.append(Spacer(1, 80))
    elements.append(Paragraph("Evidence Readiness Report", styles["title"]))
    elements.append(Paragraph(
        f"{company_name}<br/>CRN: {crn}<br/>Scope: {scope}" + (f" (Property: {property_id})" if property_id else " (Portfolio)") + f"<br/>Generated: {now.strftime('%d %B %Y at %H:%M UTC')}",
        styles["subtitle"],
    ))
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.Color(*_hex_to_rgb(branding.get("secondary_color", "#00B8A9"))), spaceAfter=20))
    elements.append(PageBreak())

    # —— Executive summary ——
    scores = [p.get("compliance_score") for p in properties if p.get("compliance_score") is not None]
    portfolio_score = round(sum(scores) / len(scores)) if scores else None
    risk_levels = [p.get("risk_level") for p in properties if p.get("risk_level")]
    overdue_count = sum(1 for r in requirements if (r.get("status") or "").upper() in ("OVERDUE", "EXPIRED"))
    expiring_count = sum(1 for r in requirements if (r.get("status") or "").upper() == "EXPIRING_SOON")
    missing_count = sum(1 for r in requirements if (r.get("status") or "").upper() in ("PENDING", "MISSING"))
    valid_count = sum(1 for r in requirements if (r.get("status") or "").upper() in ("COMPLIANT", "VALID"))

    elements.append(Paragraph("Executive Summary", styles["heading"]))
    summary_text = f"""
    <b>Score:</b> {portfolio_score if portfolio_score is not None else 'N/A'}/100 &nbsp;|&nbsp;
    <b>Risk level:</b> {risk_levels[0] if len(risk_levels) == 1 else (risk_levels[0] if risk_levels else 'N/A')}
    <br/><br/>
    <b>Counts:</b> {len(properties)} propert(ies); {len(requirements)} requirements.
    Valid/evidence in place: <b>{valid_count}</b> &nbsp;|&nbsp;
    Expiring soon: <b>{expiring_count}</b> &nbsp;|&nbsp;
    Overdue: <b>{overdue_count}</b> &nbsp;|&nbsp;
    Missing/pending evidence: <b>{missing_count}</b>
    """
    elements.append(Paragraph(summary_text, styles["body"]))
    elements.append(Spacer(1, 20))

    # —— Portfolio breakdown table ——
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

    # —— Property detail with requirement matrix ——
    elements.append(Paragraph("Property detail – requirement matrix", styles["heading"]))
    reqs_by_prop: Dict[str, List[Dict]] = {}
    for r in requirements:
        reqs_by_prop.setdefault(r["property_id"], []).append(r)
    for p in properties[:20]:
        elements.append(Paragraph(f"<b>{p.get('address_line_1') or p.get('property_id')}</b>", styles["body"]))
        rows = [["Requirement", "Status", "Due date"]]
        for r in reqs_by_prop.get(p["property_id"], [])[:30]:
            due = r.get("due_date")
            due_str = due.isoformat()[:10] if hasattr(due, "isoformat") else str(due)[:10] if due else "—"
            rows.append([
                (r.get("description") or r.get("requirement_type") or "—")[:40],
                (r.get("status") or "PENDING")[:20],
                due_str,
            ])
        if len(rows) > 1:
            tb = Table(rows, colWidths=[220, 100, 90])
            tb.setStyle(table_style)
            elements.append(tb)
        elements.append(Spacer(1, 12))
    elements.append(Spacer(1, 12))

    # —— Scoring methodology summary ——
    elements.append(Paragraph("Scoring methodology summary", styles["heading"]))
    elements.append(Paragraph(
        "Scores are evidence-based: each applicable requirement contributes a weight; status (Valid, Expiring soon, Needs review, Expired, Missing evidence) maps to a factor. "
        "Weights are renormalized to 100 across applicable requirements. Risk level is derived from critical requirement status and overall score. "
        "This is not a legal compliance opinion.",
        styles["body"],
    ))
    elements.append(Spacer(1, 20))

    # —— Audit activity snapshot (last 30 days) ——
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

    # —— Disclaimer ——
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray, spaceAfter=12))
    elements.append(Paragraph(EVIDENCE_READINESS_DISCLAIMER, styles["footer"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Generated by Pleerity Enterprise", styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


async def load_evidence_readiness_data(
    client_id: str,
    scope: str,
    property_id: Optional[str] = None,
) -> dict:
    """
    Load all data needed for Evidence Readiness PDF (portfolio or property).
    Used by route to pass report_data to pdf_report_builder. Returns dict with
    client, properties, requirements, audit_logs, now_iso, branding; for property
    scope also score_delta, score_change_summary from latest score_change_log.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    query = {"client_id": client_id}
    if scope == "property" and property_id:
        query["property_id"] = property_id
    properties = await db.properties.find(query, {"_id": 0}).to_list(500)
    if scope == "property" and property_id and not properties:
        raise ValueError("Property not found")

    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "company_name": 1, "full_name": 1, "customer_reference": 1},
    )
    company_name = (client or {}).get("company_name") or (client or {}).get("full_name") or "Client"
    property_ids = [p["property_id"] for p in properties]
    requirements = await db.requirements.find(
        {"client_id": client_id, "property_id": {"$in": property_ids}},
        {"_id": 0, "property_id": 1, "requirement_type": 1, "status": 1, "due_date": 1, "description": 1},
    ).to_list(5000)
    cutoff = (now - timedelta(days=30)).isoformat()
    audit_logs = await db.audit_logs.find(
        {"client_id": client_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0, "action": 1, "resource_type": 1, "resource_id": 1, "timestamp": 1, "metadata": 1},
    ).sort("timestamp", -1).to_list(500)

    branding = {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9", "company_name": company_name}
    try:
        from services.professional_reports import professional_report_generator
        branding = await professional_report_generator.get_branding(client_id)
    except Exception:
        pass

    report_data = {
        "client": client or {},
        "properties": properties,
        "requirements": requirements,
        "audit_logs": audit_logs,
        "now_iso": now.isoformat(),
        "branding": branding,
    }

    if scope == "property" and property_id:
        latest_log = await db.score_change_log.find_one(
            {"client_id": client_id, "property_id": property_id},
            sort=[("created_at", -1)],
            projection={"previous_score": 1, "new_score": 1, "delta": 1, "reason": 1},
        )
        if latest_log:
            report_data["score_delta"] = latest_log.get("delta")
            reason = latest_log.get("reason") or ""
            d = latest_log.get("delta")
            if d is not None:
                report_data["score_change_summary"] = f"Delta {d:+d}. {reason}"[:80]
            else:
                report_data["score_change_summary"] = reason[:80] if reason else None

    return report_data
