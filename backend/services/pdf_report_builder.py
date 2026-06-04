"""
Deterministic PDF report builder (sync).
Evidence Readiness report from pre-loaded report_data. No AI; template-only.
Evidence Readiness PDFs label export time and persisted score metadata (no live-portal truth claims).
Footer: "This report does not constitute legal advice."
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as _xml_escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
from utils.branding import COMPANY_NAME, TAGLINE, get_branding_website_url, SUPPORT_EMAIL
from presentation.jurisdiction_reporting import (
    jurisdiction_default_fallback_report_disclaimer,
    portfolio_jurisdiction_summary_sentence,
)
from utils.expiry_utils import get_computed_status, get_effective_expiry_date
from services.scoring_semantics_v1 import (
    aggregate_persisted_portfolio_headline,
    headline_score_display_for_export,
    resolve_property_score_status,
)
from services.report_branding_layout import append_report_cover_block
from services.report_layout_governance import (
    GovernancePdfContext,
    append_governance_matrix_for_properties,
    append_unresolved_obligations_section,
    export_disclosure_paragraphs,
    make_page_callbacks,
    matrix_continuation_stats,
    matrix_continuation_disclosure_paragraph,
    governance_chip_line,
    MATRIX_MAX_ROWS_PER_PROPERTY,
)
from services.reporting_semantics_v1 import (
    EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
    EXPORT_DETERMINISM_LIVE_REGENERATED,
    EXPORT_DETERMINISM_POINT_IN_TIME,
    EXPORT_GRADE_DEFINITIONS,
    GRADE_CLIENT_PRESENTATION,
    GRADE_EXECUTIVE,
    REPORTING_SEMANTICS_VERSION,
)
from services.scoring_explanation_copy import (
    SCORE_AREA_DESCRIPTIONS,
    SCORE_AREA_LABELS,
    SCORE_COMPONENTS_FALLBACK,
    SCORE_COMPONENTS_SECTION_INTRO,
    SCORE_COMPONENTS_SECTION_TITLE,
    SCORE_DEFINITIONS_EXPIRING,
    SCORE_DEFINITIONS_OVERDUE,
    SCORE_DEFINITIONS_UPDATES,
    SCORE_DEFINITIONS_VALID,
    SCORE_FRAMEWORK_DISCLAIMER,
    SCORE_PDF_METHODOLOGY_SUMMARY,
    SCORE_SCOPE_EXCLUDED,
    SCORE_SCOPE_INCLUDED,
    score_change_narrative,
)

PDF_FOOTER_DISCLAIMER = "This report does not constitute legal advice."


def _portfolio_has_v2_bucket_breakdown(bucket_breakdown: Any) -> bool:
    """True when compliance-score payload includes full v2 bucket breakdown (mirrors client portal)."""
    if not isinstance(bucket_breakdown, dict):
        return False
    keys = (
        "legal_core",
        "documentation_completeness",
        "operational_responsiveness",
        "recency_maintenance_confidence",
    )
    for k in keys:
        b = bucket_breakdown.get(k)
        if not isinstance(b, dict) or b.get("percent") is None:
            return False
        try:
            float(b["percent"])
        except (TypeError, ValueError):
            return False
    return True


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


def _row_computed_status(
    req: dict, properties: List[dict], client_doc: Optional[dict]
) -> str:
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    pd = pmap.get(req.get("property_id"))
    return (
        get_computed_status(req, property_doc=pd, client_doc=client_doc or {}) or ""
    ).upper()


def _derive_counts_and_risk(
    properties: List[dict], requirements: List[dict], now: datetime, client_doc: Optional[dict] = None
) -> dict:
    def st(r: dict) -> str:
        return _row_computed_status(r, properties, client_doc)

    valid = sum(1 for r in requirements if st(r) in ("COMPLIANT", "VALID", "NOT_REQUIRED"))
    expiring = sum(1 for r in requirements if st(r) == "EXPIRING_SOON")
    overdue = sum(1 for r in requirements if st(r) in ("OVERDUE", "EXPIRED"))
    missing = sum(1 for r in requirements if st(r) in ("PENDING", "MISSING", "UNKNOWN_DATE"))
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


def _evidence_readiness_snapshot_timestamp_display(now: datetime) -> str:
    """UTC label for snapshot framing (aligned with cover ``Generated`` line)."""
    return now.strftime("%d %B %Y at %H:%M UTC")


def _evidence_readiness_last_calc_display(raw: Any) -> str:
    """Human-readable persisted score batch time for Evidence Readiness PDF."""
    if raw is None or raw == "":
        return "—"
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo is not None else raw.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
    s = str(raw).strip()
    if not s:
        return "—"
    s_iso = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s_iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
    except Exception:
        if len(s) >= 19 and "T" in s[:19]:
            return s[:19].replace("T", " ")
        return s[:32] if len(s) > 32 else s


def _evidence_readiness_headline_score_from_agg(agg: dict) -> str:
    """SCORING_SEMANTICS_V1: never show ``N/A/100``; only append ``/100`` for authoritative numeric headlines."""
    disp = headline_score_display_for_export(agg.get("portfolio_score"), agg.get("score_status"))
    return f"{disp}/100" if disp.isdigit() else disp


def _evidence_readiness_headline_score_frag(
    properties: List[dict], now: datetime, agg: Optional[dict] = None
) -> str:
    """Portfolio headline display; pass ``agg`` to avoid a second aggregate pass."""
    agg = agg if agg is not None else aggregate_persisted_portfolio_headline(properties, now=now)
    return _evidence_readiness_headline_score_from_agg(agg)


def _evidence_readiness_exec_aggregate_meta_html(agg: dict) -> str:
    """HTML lines for executive summary: score status, last portfolio calculation, optional headline note."""
    st = agg.get("score_status")
    st_s = _xml_escape(str(st)) if st is not None and str(st) != "" else "—"
    last = _evidence_readiness_last_calc_display(agg.get("portfolio_last_calculated_at"))
    lines = [
        f"<b>Score status:</b> {st_s} &nbsp;|&nbsp; <b>Last score calculation:</b> {_xml_escape(last)}",
    ]
    ssm = (agg.get("score_status_message") or "").strip()
    if ssm:
        lines.append(f"<b>Headline note:</b> {_xml_escape(ssm)}")
    return "<br/>".join(lines)


def _evidence_readiness_property_score_cell_html(p: dict, *, now: datetime) -> str:
    """Score column HTML: headline plus score status and optional last calculation / property message."""
    st = resolve_property_score_status(p, now=now)
    disp = headline_score_display_for_export(p.get("compliance_score"), st)
    primary = f"{disp}/100" if disp.isdigit() else disp
    meta: List[str] = [f"Score status: {_xml_escape(str(st))}"]
    lcat = p.get("compliance_last_calculated_at")
    if lcat is not None and str(lcat).strip():
        meta.append(f"Last calculated: {_xml_escape(_evidence_readiness_last_calc_display(lcat))}")
    pssm = (p.get("score_status_message") or "").strip()
    if pssm:
        meta.append(_xml_escape(pssm[:200] + ("…" if len(pssm) > 200 else "")))
    return _xml_escape(primary) + '<br/><font size="8">' + " · ".join(meta) + "</font>"


def _parse_governance_datetime(raw: Any) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _governance_ctx(
    *,
    report_data: dict,
    client: dict,
    properties: List[dict],
    now: datetime,
    company_name: str,
    crn: str,
    export_grade: str = GRADE_CLIENT_PRESENTATION,
    determinism: str = EXPORT_DETERMINISM_LIVE_REGENERATED,
    report_scope: str = "",
) -> GovernancePdfContext:
    lineage = report_data.get("artifact_lineage") or {}
    if lineage.get("export_grade"):
        export_grade = lineage["export_grade"]
    if lineage.get("determinism"):
        determinism = lineage["determinism"]
    grade_def = EXPORT_GRADE_DEFINITIONS.get(export_grade) or {}
    gen_at = _parse_governance_datetime(lineage.get("original_generated_at")) or now
    return GovernancePdfContext(
        export_grade=export_grade,
        export_grade_label=lineage.get("export_grade_label") or grade_def.get("label") or export_grade,
        generated_at=gen_at,
        determinism=determinism,
        jurisdiction_summary=(lineage.get("jurisdiction_scope") or portfolio_jurisdiction_summary_sentence(client, properties))[:90],
        original_generated_at=_parse_governance_datetime(lineage.get("original_generated_at") or report_data.get("original_generated_at")),
        regenerated_at=_parse_governance_datetime(report_data.get("regenerated_at")),
        company_name=company_name,
        crn=crn,
        artifact_id=str(lineage.get("artifact_id") or ""),
        semantics_version=str(lineage.get("semantics_version") or REPORTING_SEMANTICS_VERSION),
        immutable_status=str(lineage.get("immutable_status") or ("frozen" if determinism == EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT else "")),
        report_scope=str(lineage.get("report_scope") or report_scope),
        source_snapshot_hash=str(lineage.get("source_snapshot_hash") or ""),
    )


def _top_risk_drivers(
    requirements: List[dict],
    properties: List[dict],
    client_doc: Optional[dict],
    limit: int = 10,
) -> List[dict]:
    """Requirements that are overdue, expired, or expiring soon."""
    out = []
    for r in requirements:
        s = _row_computed_status(r, properties, client_doc)
        if s in ("OVERDUE", "EXPIRED", "EXPIRING_SOON"):
            out.append({
                "requirement_type": r.get("requirement_type") or r.get("description") or "—",
                "status": _status_label(s),
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
    derived = _derive_counts_and_risk(properties, requirements, now, client_doc=client)
    top_risks = _top_risk_drivers(requirements, properties, client, limit=10)
    headline_agg = aggregate_persisted_portfolio_headline(properties, now=now)
    gov_ctx = _governance_ctx(
        report_data=report_data,
        client=client,
        properties=properties,
        now=now,
        company_name=company_name,
        crn=crn,
        report_scope="portfolio",
    )
    on_first, on_later = make_page_callbacks(gov_ctx)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=62,
    )
    elements = []
    append_report_cover_block(
        elements,
        report_title="Evidence Readiness Report",
        branding=branding,
        gov_ctx=gov_ctx,
        styles=styles,
        account_line=f"<b>Account:</b> {_xml_escape(company_name)} &nbsp;|&nbsp; <b>CRN:</b> {_xml_escape(crn)}",
        scope_line="<b>Scope:</b> portfolio",
    )
    elements.append(PageBreak())

    # Executive summary
    elements.append(Paragraph("Executive Summary", styles["heading"]))
    snap_ts = _evidence_readiness_snapshot_timestamp_display(now)
    elements.append(Paragraph(f"<b>Snapshot generated at</b> {_xml_escape(snap_ts)}", styles["body"]))
    if not gov_ctx.is_immutable_artifact:
        if gov_ctx.regenerated_at and gov_ctx.original_generated_at:
            elements.append(
                Paragraph(
                    f"<b>Regenerated (UTC):</b> {_xml_escape(_evidence_readiness_snapshot_timestamp_display(gov_ctx.regenerated_at))} "
                    f"(original run: {_xml_escape(_evidence_readiness_snapshot_timestamp_display(gov_ctx.original_generated_at))})",
                    styles["body"],
                )
            )
        elements.append(Paragraph(
            "LIVE EXPORT: reflects portfolio state at generation time and may differ from future downloads.",
            styles["small"],
        ))
    elements.append(Spacer(1, 8))
    score_frag = _evidence_readiness_headline_score_frag(properties, now, headline_agg)
    summary_text = f"""
    <b>Score:</b> {score_frag} &nbsp;|&nbsp;
    <b>Risk level:</b> {derived['risk_level']}
    <br/>{_evidence_readiness_exec_aggregate_meta_html(headline_agg)}
    <br/><br/>
    <b>Counts:</b> {len(properties)} propert(ies); {len(requirements)} requirements.
    Evidence in place: <b>{derived['valid_count']}</b> &nbsp;|&nbsp;
    Expiring soon: <b>{derived['expiring_count']}</b> &nbsp;|&nbsp;
    Expired/overdue: <b>{derived['overdue_count']}</b> &nbsp;|&nbsp;
    Missing evidence: <b>{derived['missing_count']}</b>
    """
    elements.append(Paragraph(summary_text, styles["body"]))
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Jurisdiction scope", styles["heading"]))
    elements.append(Paragraph(portfolio_jurisdiction_summary_sentence(client, properties), styles["body"]))
    elements.append(Spacer(1, 12))
    jn = report_data.get("jurisdiction_compliance_notice") or {}
    if jn.get("active"):
        elements.append(
            Paragraph(
                "<b>Default jurisdiction notice:</b> " + jurisdiction_default_fallback_report_disclaimer(),
                styles["body"],
            )
        )
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

    append_unresolved_obligations_section(
        elements,
        requirements=requirements,
        properties=properties,
        client_doc=client,
        styles=styles,
        table_style=table_style,
        heading_style=styles["heading"],
    )

    # Portfolio breakdown
    elements.append(Paragraph("Portfolio breakdown", styles["heading"]))
    prop_data = [["Address", "Score", "Risk level", "Last updated"]]
    for p in properties[:50]:
        addr = p.get("address_line_1") or p.get("nickname") or p.get("property_id", "")
        score_cell = Paragraph(_evidence_readiness_property_score_cell_html(p, now=now), styles["body"])
        risk = p.get("risk_level") or "—"
        updated = p.get("compliance_last_calculated_at") or "—"
        if isinstance(updated, str) and len(updated) > 16:
            updated = updated[:10]
        prop_data.append([addr[:50], score_cell, risk, updated])
    if len(prop_data) > 1:
        t = Table(prop_data, colWidths=[185, 100, 85, 80])
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
            due = get_effective_expiry_date(r)
            due_for_days = due if due is not None else r.get("due_date")
            if due and hasattr(due, "isoformat"):
                due_str = due.date().isoformat() if hasattr(due, "date") else due.isoformat()[:10]
            elif isinstance(r.get("due_date"), str) and r.get("due_date"):
                due_str = str(r.get("due_date"))[:10]
            else:
                due_str = "—"
            days = _days_to_expiry(due_for_days, now)
            days_str = str(days) if days is not None else "—"
            cs = get_computed_status(r, property_doc=p, client_doc=client)
            rows.append([
                (r.get("description") or r.get("requirement_type") or "—")[:35],
                _status_label(cs),
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
    elements.append(Paragraph(SCORE_PDF_METHODOLOGY_SUMMARY, styles["body"]))
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
    gen_by = branding.get("pdf_footer_generated_by") or ("Generated by " + COMPANY_NAME)
    contact_line = branding.get("pdf_footer_contact_line") or (
        f"{get_branding_website_url()} | {SUPPORT_EMAIL}"
    )
    elements.append(Paragraph(gen_by, styles["footer"]))
    elements.append(Paragraph(contact_line, styles["footer"]))

    doc.build(elements, onFirstPage=on_first, onLaterPages=on_later)
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
    Sections: cover, portfolio snapshot, what score means, area breakdown,
    top drivers, property breakdown, appendix (full drivers). Footer: disclaimer + Pleerity line.

    Headline timing: **Snapshot as of** uses the same persisted-batch timestamps as the cover
    (`last_calculated_at` / `portfolio_last_calculated_at` / `score_last_calculated_at`), then PDF
    generation time if none are set. Driver rows reflect requirement state at PDF generation time.
    """
    company_name = client_doc.get("company_name") or client_doc.get("full_name") or "Client"
    crn = client_doc.get("customer_reference") or client_id
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%d %B %Y at %H:%M UTC")

    raw_as_of = (
        score_payload.get("last_calculated_at")
        or score_payload.get("portfolio_last_calculated_at")
        or score_payload.get("score_last_calculated_at")
    )

    def _score_report_as_of_display(raw: Any) -> str:
        """Human-readable as-of for headline (persisted batch time); falls back to PDF generation time."""
        if raw is None or raw == "":
            return now_str
        if isinstance(raw, datetime):
            dt = raw if raw.tzinfo is not None else raw.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
        s = str(raw).strip()
        if not s:
            return now_str
        s_iso = s.replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(s_iso)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
        except Exception:
            if len(s) >= 19 and "T" in s[:19]:
                return s[:19].replace("T", " ")
            return s

    data_as_of_display = _score_report_as_of_display(raw_as_of)

    branding = branding or {
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "company_name": company_name,
    }
    styles, table_style = _build_styles_and_table_style(branding)
    props_for_j = score_payload.get("property_breakdown") or []
    gov_ctx = _governance_ctx(
        report_data={},
        client=client_doc,
        properties=props_for_j if isinstance(props_for_j, list) else [],
        now=now,
        company_name=company_name,
        crn=crn,
        export_grade=GRADE_EXECUTIVE,
        determinism=EXPORT_DETERMINISM_LIVE_REGENERATED,
    )
    on_first, on_later = make_page_callbacks(gov_ctx)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=62,
    )
    elements = []

    branding = branding or {
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "company_name": company_name,
    }
    append_report_cover_block(
        elements,
        report_title="Compliance Score Summary (Informational)",
        branding=branding,
        gov_ctx=gov_ctx,
        styles=styles,
        account_line=f"<b>Account:</b> {_xml_escape(company_name)} &nbsp;|&nbsp; <b>CRN:</b> {_xml_escape(crn)}",
        scope_line=f"<b>Data as of:</b> {_xml_escape(data_as_of_display)}",
        extra_metadata_lines=[
            "Informational tracking indicator only. Not legal advice.",
        ],
    )
    elements.append(PageBreak())

    # —— 2. Portfolio snapshot ——
    elements.append(Paragraph("Portfolio snapshot", styles["heading"]))
    elements.append(
        Paragraph(
            f"<b>Snapshot as of</b> {_xml_escape(data_as_of_display)}",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 8))
    score = score_payload.get("score")
    score_status = score_payload.get("score_status")
    score_display = headline_score_display_for_export(score, score_status)
    grade = score_payload.get("grade") or "—"
    stats = score_payload.get("stats") or {}
    valid = stats.get("compliant", 0)
    expiring = stats.get("expiring_soon", 0)
    overdue = stats.get("overdue", 0)
    props_count = score_payload.get("properties_count", 0)
    completeness = score_payload.get("data_completeness_percent")
    completeness_str = f"{completeness}%" if completeness is not None else "—"
    cov = score_payload.get("score_coverage") or {}
    cov_note = ""
    if isinstance(cov, dict) and int(cov.get("properties_missing_score") or 0) > 0:
        cov_note = (
            f"<br/><b>Coverage:</b> score averages {int(cov.get('properties_with_score') or 0)} of "
            f"{int(cov.get('properties_total') or 0)} properties with persisted scores."
        )
    ssm = (score_payload.get("score_status_message") or "").strip()
    headline_note = ""
    if ssm:
        headline_note = f"<br/><b>Headline note:</b> {_xml_escape(ssm)}"
    snapshot_text = f"""
    <b>Overall score (headline):</b> {score_display}{'/100' if score_display.isdigit() else ''} &nbsp;|&nbsp; <b>Grade:</b> {grade}
    <br/><b>Score status:</b> {score_status or '—'} &nbsp;|&nbsp; <b>Authority:</b> {score_payload.get('score_authority') or '—'}
    {cov_note}{headline_note}
    <br/><br/>
    <b>Valid:</b> {valid} &nbsp;|&nbsp; <b>Expiring soon:</b> {expiring} &nbsp;|&nbsp; <b>Overdue:</b> {overdue}
    <br/>
    <b>Properties monitored:</b> {props_count} &nbsp;|&nbsp; <b>Data completeness:</b> {completeness_str}
    """
    elements.append(Paragraph(snapshot_text, styles["body"]))
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Jurisdiction scope", styles["heading"]))
    elements.append(Paragraph(
        portfolio_jurisdiction_summary_sentence(client_doc, score_payload.get("property_breakdown") or []),
        styles["body"],
    ))
    jn_score = score_payload.get("jurisdiction_compliance_notice") or {}
    if jn_score.get("active"):
        elements.append(Spacer(1, 10))
        elements.append(
            Paragraph(
                "<b>Default jurisdiction notice:</b> " + jurisdiction_default_fallback_report_disclaimer(),
                styles["small"],
            )
        )
    elements.append(Spacer(1, 24))

    # —— 3. What the score means ——
    elements.append(Paragraph("What the score means", styles["heading"]))
    elements.append(Paragraph(f"<b>Scope (included):</b> {SCORE_SCOPE_INCLUDED}", styles["body"]))
    elements.append(Paragraph(f"<b>Excluded:</b> {SCORE_SCOPE_EXCLUDED}", styles["body"]))
    elements.append(
        Paragraph(
            f"<b>Definitions:</b> Valid = {SCORE_DEFINITIONS_VALID} "
            f"Expiring soon = {SCORE_DEFINITIONS_EXPIRING} "
            f"Overdue = {SCORE_DEFINITIONS_OVERDUE} "
            f"Missing evidence = no accepted upload on file.",
            styles["body"],
        )
    )
    elements.append(Paragraph(f"<b>Updates:</b> {SCORE_DEFINITIONS_UPDATES}", styles["body"]))
    elements.append(Paragraph(SCORE_FRAMEWORK_DISCLAIMER, styles["small"]))
    elements.append(Spacer(1, 24))

    # —— 4. Score components (area breakdown when available) ——
    elements.append(Paragraph(SCORE_COMPONENTS_SECTION_TITLE, styles["heading"]))
    bb = score_payload.get("bucket_breakdown") or {}
    if _portfolio_has_v2_bucket_breakdown(bb):
        elements.append(Paragraph(SCORE_COMPONENTS_SECTION_INTRO, styles["small"]))
        elements.append(Spacer(1, 8))
        area_rows = [["Area", "How you're doing (%)"]]
        for key in (
            "legal_core",
            "documentation_completeness",
            "operational_responsiveness",
            "recency_maintenance_confidence",
        ):
            label = SCORE_AREA_LABELS.get(key, key)
            pct = bb.get(key, {}).get("percent")
            try:
                pct_str = f"{round(float(pct))}%" if pct is not None else "—"
            except (TypeError, ValueError):
                pct_str = "—"
            area_rows.append([label, pct_str])
        wt = Table(area_rows, colWidths=[260, 120])
        wt.setStyle(table_style)
        elements.append(wt)
        elements.append(Spacer(1, 8))
        for key in (
            "legal_core",
            "documentation_completeness",
            "operational_responsiveness",
            "recency_maintenance_confidence",
        ):
            desc = SCORE_AREA_DESCRIPTIONS.get(key)
            if desc:
                elements.append(
                    Paragraph(
                        f"<b>{SCORE_AREA_LABELS.get(key, key)}:</b> {desc}",
                        styles["small"],
                    )
                )
    else:
        elements.append(Paragraph(SCORE_COMPONENTS_FALLBACK, styles["body"]))
    elements.append(Spacer(1, 24))

    # —— 5. Top drivers ——
    drivers = score_payload.get("drivers") or []
    top_drivers = drivers[:10]
    elements.append(Paragraph("Top drivers (what is affecting your score)", styles["heading"]))
    if not top_drivers:
        elements.append(
            Paragraph(
                "No issues detected from the requirement data used when this PDF was generated.",
                styles["body"],
            )
        )
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
                headline_score_display_for_export(p.get("score"), p.get("score_status")),
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
    footer_co = branding.get("company_name") or company_name or COMPANY_NAME
    elements.append(Paragraph(f"{footer_co} – {TAGLINE}", styles["footer"]))
    elements.append(Paragraph(f"CRN: {crn} &nbsp;|&nbsp; Generated: {now_str}", styles["footer"]))
    elements.append(Paragraph("Informational indicator based on portal records. Not legal advice.", styles["footer"]))

    doc.build(elements, onFirstPage=on_first, onLaterPages=on_later)
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
    derived = _derive_counts_and_risk(properties, requirements, now, client_doc=client)
    top_risks = _top_risk_drivers(requirements, properties, client, limit=10)
    prop = properties[0] if properties else {}
    headline_agg = aggregate_persisted_portfolio_headline(properties, now=now)
    gov_ctx = _governance_ctx(
        report_data=report_data,
        client=client,
        properties=properties,
        now=now,
        company_name=company_name,
        crn=crn,
        report_scope=f"property:{property_id}",
    )
    on_first, on_later = make_page_callbacks(gov_ctx)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=62,
    )
    elements = []

    scope_line = f"<b>Scope:</b> property (Property: {_xml_escape(property_id)})"
    append_report_cover_block(
        elements,
        report_title="Evidence Readiness Report",
        branding=branding,
        gov_ctx=gov_ctx,
        styles=styles,
        account_line=f"<b>Account:</b> {_xml_escape(company_name)} &nbsp;|&nbsp; <b>CRN:</b> {_xml_escape(crn)}",
        scope_line=scope_line,
    )
    elements.append(PageBreak())

    # Executive summary
    elements.append(Paragraph("Executive Summary", styles["heading"]))
    snap_ts = _evidence_readiness_snapshot_timestamp_display(now)
    elements.append(Paragraph(f"<b>Snapshot generated at</b> {_xml_escape(snap_ts)}", styles["body"]))
    if not gov_ctx.is_immutable_artifact:
        if gov_ctx.regenerated_at and gov_ctx.original_generated_at:
            elements.append(
                Paragraph(
                    f"<b>Regenerated (UTC):</b> {_xml_escape(_evidence_readiness_snapshot_timestamp_display(gov_ctx.regenerated_at))} "
                    f"(original run: {_xml_escape(_evidence_readiness_snapshot_timestamp_display(gov_ctx.original_generated_at))})",
                    styles["body"],
                )
            )
        elements.append(Paragraph(
            "LIVE EXPORT: reflects portfolio state at generation time and may differ from future downloads.",
            styles["small"],
        ))
    elements.append(Spacer(1, 8))
    score_line = (
        f"<b>Score:</b> {_evidence_readiness_headline_score_frag(properties, now, headline_agg)} &nbsp;|&nbsp; "
        f"<b>Risk level:</b> {derived['risk_level']}"
    )
    score_line += "<br/>" + _evidence_readiness_exec_aggregate_meta_html(headline_agg)
    prop_score_msg = (prop.get("score_status_message") or "").strip()
    agg_score_msg = (headline_agg.get("score_status_message") or "").strip()
    if prop_score_msg and prop_score_msg != agg_score_msg:
        score_line += f"<br/><b>Headline note:</b> {_xml_escape(prop_score_msg)}"
    if score_delta is not None or score_change_summary:
        change_text = score_change_summary or score_change_narrative(score_delta)
        score_line += f"<br/><b>Score change:</b> {_xml_escape(change_text)}"
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
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Jurisdiction scope", styles["heading"]))
    elements.append(Paragraph(portfolio_jurisdiction_summary_sentence(client, properties), styles["body"]))
    elements.append(Spacer(1, 12))
    jn_prop = report_data.get("jurisdiction_compliance_notice") or {}
    if jn_prop.get("active"):
        elements.append(
            Paragraph(
                "<b>Default jurisdiction notice:</b> " + jurisdiction_default_fallback_report_disclaimer(),
                styles["body"],
            )
        )
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
        due = get_effective_expiry_date(r)
        due_for_days = due if due is not None else r.get("due_date")
        if due and hasattr(due, "isoformat"):
            due_str = due.date().isoformat() if hasattr(due, "date") else due.isoformat()[:10]
        elif isinstance(r.get("due_date"), str) and r.get("due_date"):
            due_str = str(r.get("due_date"))[:10]
        else:
            due_str = "—"
        days = _days_to_expiry(due_for_days, now)
        days_str = str(days) if days is not None else "—"
        cs = get_computed_status(r, property_doc=prop, client_doc=client)
        rows.append([
            (r.get("description") or r.get("requirement_type") or "—")[:40],
            _status_label(cs),
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
        "Scores are evidence-based; status (Evidence in place, Expiring soon, Expired/overdue, Missing evidence) maps to a factor. "
        "Expiring-soon uses the jurisdiction- and requirement-aware rule window used in scoring. Risk level is derived from score. "
        "This is not a legal compliance opinion.",
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
    gen_by = branding.get("pdf_footer_generated_by") or ("Generated by " + COMPANY_NAME)
    contact_line = branding.get("pdf_footer_contact_line") or (
        f"{get_branding_website_url()} | {SUPPORT_EMAIL}"
    )
    elements.append(Paragraph(gen_by, styles["footer"]))
    elements.append(Paragraph(contact_line, styles["footer"]))

    doc.build(elements, onFirstPage=on_first, onLaterPages=on_later)
    buffer.seek(0)
    return buffer.getvalue()


def build_requirements_report_pdf(client_id: str, report_data: dict) -> bytes:
    """Server-side requirements PDF with governance columns and unresolved section."""
    client = report_data.get("client") or {}
    company_name = client.get("company_name") or client.get("full_name") or "Client"
    crn = client.get("customer_reference") or client_id
    properties = report_data.get("properties") or []
    requirements = report_data.get("requirements") or []
    now_iso = report_data.get("now_iso")
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(timezone.utc)
    branding = report_data.get("branding") or {
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "company_name": company_name,
    }
    styles, table_style = _build_styles_and_table_style(branding)
    gov_ctx = _governance_ctx(
        report_data=report_data,
        client=client,
        properties=properties,
        now=now,
        company_name=company_name,
        crn=crn,
        determinism=EXPORT_DETERMINISM_POINT_IN_TIME,
    )
    on_first, on_later = make_page_callbacks(gov_ctx)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=62,
    )
    elements = []
    elements.append(Spacer(1, 60))
    elements.append(Paragraph("Requirements Report", styles["title"]))
    elements.append(Paragraph(
        f"{company_name}<br/>CRN: {crn}<br/>Generated: {now.strftime('%d %B %Y at %H:%M UTC')}<br/>"
        f"Export grade: {_xml_escape(gov_ctx.export_grade_label)}",
        styles["subtitle"],
    ))
    elements.extend(export_disclosure_paragraphs(gov_ctx, styles))
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(f"<b>Requirements in scope:</b> {len(requirements)}", styles["body"]))
    elements.append(Spacer(1, 12))

    append_unresolved_obligations_section(
        elements,
        requirements=requirements,
        properties=properties,
        client_doc=client,
        styles=styles,
        table_style=table_style,
        heading_style=styles["heading"],
    )

    if properties:
        append_governance_matrix_for_properties(
            elements,
            properties=properties,
            requirements=requirements,
            client_doc=client,
            styles=styles,
            table_style=table_style,
            heading_style=styles["heading"],
            body_style=styles["body"],
            now=now,
            status_label_fn=_status_label,
        )
    else:
        elements.append(Paragraph("Requirement detail", styles["heading"]))
        elements.append(matrix_continuation_disclosure_paragraph(
            matrix_continuation_stats([], requirements), styles
        ))
        rows = [["Requirement", "Status", "Governance", "Due", "Days"]]
        for r in requirements[:MATRIX_MAX_ROWS_PER_PROPERTY]:
            due = get_effective_expiry_date(r)
            due_str = "—"
            if due and hasattr(due, "date"):
                due_str = due.date().isoformat()
            elif isinstance(r.get("due_date"), str):
                due_str = str(r.get("due_date"))[:10]
            cs = get_computed_status(r, property_doc=None, client_doc=client)
            rows.append([
                (r.get("description") or r.get("requirement_type") or "—")[:35],
                _status_label(cs),
                governance_chip_line(r)[:42],
                due_str,
                "—",
            ])
        if len(rows) > 1:
            tb = Table(rows, colWidths=[150, 90, 130, 65, 45], repeatRows=1)
            tb.setStyle(table_style)
            elements.append(tb)
        omitted = max(0, len(requirements) - MATRIX_MAX_ROWS_PER_PROPERTY)
        if omitted:
            elements.append(
                Paragraph(
                    f"<b>Continuation:</b> {omitted} additional obligations omitted from summary matrix.",
                    styles["small"],
                )
            )

    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray, spaceAfter=12))
    elements.append(Paragraph(PDF_FOOTER_DISCLAIMER, styles["footer"]))
    doc.build(elements, onFirstPage=on_first, onLaterPages=on_later)
    buffer.seek(0)
    return buffer.getvalue()
