"""
REPORTING-ENTERPRISE-PRESENTATION-PHASE-02 — shared ReportLab presentation governance.

Reusable footer, matrix governance columns, unresolved obligations, and portfolio truncation disclosure.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from xml.sax.saxutils import escape as _xml_escape

from services.report_human_language_v1 import (
    IMMUTABLE_SECTION_TITLE,
    LIVE_EXPORT_SECTION_TITLE,
    human_export_footer_grade,
    human_governance_chip_line,
)
from services.reporting_semantics_v1 import (
    EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
    EXPORT_DETERMINISM_LIVE_REGENERATED,
    GRADE_CLIENT_PRESENTATION,
    IMMUTABLE_ARTIFACT_DISCLOSURE,
    LIVE_REGENERATED_DISCLOSURE,
    REPORTING_SEMANTICS_VERSION,
)
from utils.expiry_utils import get_computed_status, get_effective_expiry_date

MATRIX_MAX_PROPERTIES_DISPLAY = 15
MATRIX_MAX_ROWS_PER_PROPERTY = 25
UNRESOLVED_SECTION_MAX_ROWS = 45

PDF_LEGAL_FOOTER = "This report does not constitute legal advice."

# Table header row contrast (accessibility-enhanced, print-safe monochrome)
TABLE_HEADER_BG = colors.Color(0.12, 0.15, 0.22)
TABLE_HEADER_FG = colors.white
TABLE_ROW_ALT = colors.Color(0.97, 0.97, 0.97)
TABLE_GRID = colors.Color(0.72, 0.72, 0.72)


@dataclass(frozen=True)
class GovernancePdfContext:
    export_grade: str
    export_grade_label: str
    generated_at: datetime
    determinism: str
    jurisdiction_summary: str = ""
    original_generated_at: Optional[datetime] = None
    regenerated_at: Optional[datetime] = None
    company_name: str = ""
    crn: str = ""
    artifact_id: str = ""
    semantics_version: str = REPORTING_SEMANTICS_VERSION
    immutable_status: str = ""
    report_scope: str = ""
    source_snapshot_hash: str = ""

    @property
    def is_immutable_artifact(self) -> bool:
        return self.determinism == EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT or bool(self.artifact_id)

    @property
    def is_live_regenerated(self) -> bool:
        if self.is_immutable_artifact:
            return False
        return self.regenerated_at is not None or self.determinism == EXPORT_DETERMINISM_LIVE_REGENERATED


def utc_display(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
    s = str(value).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
    except Exception:
        return s[:32] if len(s) > 32 else s


def date_confidence_label(row: Dict[str, Any]) -> str:
    dc = str(row.get("date_confidence") or "").strip().upper()
    if dc in ("CONFIRMED", "VERIFIED", "USER_CONFIRMED"):
        return "CONF"
    if dc in ("ESTIMATED", "SYSTEM_ESTIMATED", "PROVISIONAL"):
        return "EST"
    if row.get("date_source") == "SYSTEM_ESTIMATED":
        return "EST"
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    if ea.get("effective_expiry_is_estimated"):
        return "EST"
    if not row.get("confirmed_expiry_date") and (row.get("due_date") or row.get("extracted_expiry_date")):
        return "EST"
    if dc:
        return dc[:8]
    return "UNK"


def assurance_tier_chip(row: Dict[str, Any]) -> str:
    """Customer-facing assurance column (compact label)."""
    from services.report_human_language_v1 import human_assurance_tier_label

    label = human_assurance_tier_label(row)
    return label[:24] if label and label != "—" else "—"


def lifecycle_chip(row: Dict[str, Any]) -> str:
    """Customer-facing lifecycle column (compact label)."""
    from services.report_human_language_v1 import human_lifecycle_label

    label = human_lifecycle_label(row)
    return label[:20] if label and label != "—" else "—"


def review_state_label(row: Dict[str, Any]) -> str:
    life = str(row.get("client_lifecycle_state") or "").strip().upper()
    if life == "PENDING_REVIEW":
        return "Platform review"
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    ndv = str(ea.get("non_document_verification_status") or "").strip().upper()
    if ndv == "PENDING_ADMIN_REVIEW":
        return "Platform review"
    return "—"


def evidence_presence_label(row: Dict[str, Any]) -> str:
    if row.get("evidence_doc_id") or row.get("document_id"):
        return "Linked"
    es = str(row.get("evidence_state") or "").strip().upper()
    if es in ("VERIFIED", "UPLOADED_UNVERIFIED"):
        return "On file"
    if es in ("MISSING", ""):
        return "None"
    return es[:8] if es else "—"


def governance_chip_line(row: Dict[str, Any]) -> str:
    """Single concise governance column for matrix tables."""
    return human_governance_chip_line(row)


def _unresolved_reason(row: Dict[str, Any], *, property_doc: Optional[dict], client_doc: dict) -> str:
    life = str(row.get("client_lifecycle_state") or "").strip().upper()
    if life == "PENDING_REVIEW":
        return "Awaiting platform review"
    if life == "ACTION_REQUIRED":
        return "Action required"
    cs = (get_computed_status(row, property_doc=property_doc, client_doc=client_doc) or "").upper()
    if cs in ("OVERDUE", "EXPIRED"):
        return "Overdue or expired"
    if cs in ("MISSING", "PENDING"):
        from services.requirement_satisfaction_service import row_counts_as_missing_evidence

        if row_counts_as_missing_evidence(row):
            return "Missing required evidence"
        return "Pending confirmation"
    if cs == "EXPIRING_SOON":
        return "Expiring soon — renewal attention"
    tier = str(row.get("assurance_tier") or "").strip().upper()
    if life == "SATISFIED_UNVERIFIED" or tier == "SELF_RECORDED":
        return "Self-recorded — not platform-verified"
    return "Unresolved in export scope"


def is_unresolved_row(row: Dict[str, Any], *, property_doc: Optional[dict], client_doc: dict) -> bool:
    """True only for action-required export bucket — not self-recorded satisfaction exposure."""
    from services.audience_governance_v1 import (
        AUDIENCE_REGULATOR_EVIDENTIAL,
        EXPORT_SECTION_UNRESOLVED,
        classify_export_section_bucket,
    )

    return (
        classify_export_section_bucket(
            row,
            property_doc=property_doc,
            client_doc=client_doc,
            audience=AUDIENCE_REGULATOR_EVIDENTIAL,
        )
        == EXPORT_SECTION_UNRESOLVED
    )


def _collect_obligations_for_export_bucket(
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Optional[Dict[str, Any]],
    *,
    bucket: str,
    limit: int = UNRESOLVED_SECTION_MAX_ROWS,
) -> Tuple[List[Dict[str, Any]], int]:
    from services.audience_governance_v1 import AUDIENCE_REGULATOR_EVIDENTIAL, classify_export_section_bucket

    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    client = client_doc or {}
    out: List[Dict[str, Any]] = []
    total = 0
    for r in requirements:
        pid = r.get("property_id")
        pd = pmap.get(pid)
        if (
            classify_export_section_bucket(
                r, property_doc=pd, client_doc=client, audience=AUDIENCE_REGULATOR_EVIDENTIAL
            )
            != bucket
        ):
            continue
        total += 1
        if len(out) >= limit:
            continue
        eff = get_effective_expiry_date(r)
        due_s = eff.date().isoformat() if eff and hasattr(eff, "date") else (str(r.get("due_date") or "")[:10] or "—")
        addr = ""
        if pd:
            addr = ", ".join(x for x in [pd.get("address_line_1"), pd.get("postcode")] if x)[:60]
        interp = None
        try:
            from services.audience_governance_v1 import interpret_requirement_for_audience

            interp = interpret_requirement_for_audience(
                r, AUDIENCE_REGULATOR_EVIDENTIAL, property_doc=pd, client_doc=client
            )
        except Exception:
            interp = {}
        out.append(
            {
                "requirement": (r.get("description") or r.get("requirement_type") or "—")[:50],
                "property": addr or str(pid or "—")[:20],
                "reason": (interp or {}).get("audience_status_description", _unresolved_reason(r, property_doc=pd, client_doc=client))[:60],
                "assurance": assurance_tier_chip(r),
                "evidence": evidence_presence_label(r),
                "review": review_state_label(r),
                "expiry_risk": due_s,
                "status_label": (interp or {}).get("audience_status_label", "")[:40],
            }
        )
    return out, total


def collect_unresolved_obligations(
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Optional[Dict[str, Any]],
    *,
    limit: int = UNRESOLVED_SECTION_MAX_ROWS,
) -> Tuple[List[Dict[str, Any]], int]:
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    client = client_doc or {}
    out: List[Dict[str, Any]] = []
    total = 0
    for r in requirements:
        pid = r.get("property_id")
        pd = pmap.get(pid)
        if not is_unresolved_row(r, property_doc=pd, client_doc=client):
            continue
        total += 1
        if len(out) >= limit:
            continue
        eff = get_effective_expiry_date(r)
        due_s = eff.date().isoformat() if eff and hasattr(eff, "date") else (str(r.get("due_date") or "")[:10] or "—")
        addr = ""
        if pd:
            addr = ", ".join(x for x in [pd.get("address_line_1"), pd.get("postcode")] if x)[:60]
        out.append(
            {
                "requirement": (r.get("description") or r.get("requirement_type") or "—")[:50],
                "property": addr or str(pid or "—")[:20],
                "reason": _unresolved_reason(r, property_doc=pd, client_doc=client)[:40],
                "assurance": assurance_tier_chip(r),
                "evidence": evidence_presence_label(r),
                "review": review_state_label(r),
                "expiry_risk": due_s,
            }
        )
    return out, total


def export_disclosure_paragraphs(ctx: GovernancePdfContext, styles: Dict[str, Any]) -> List[Any]:
    """Cover/body governance block: export grade, determinism, timestamps."""
    from reportlab.platypus import Paragraph, Spacer

    elements: List[Any] = []
    elements.append(
        Paragraph(
            f"<b>Export grade:</b> {_xml_escape(ctx.export_grade_label or ctx.export_grade)}",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 6))
    if ctx.is_immutable_artifact:
        elements.append(
            Paragraph(
                "<b>IMMUTABLE GOVERNANCE ARTIFACT</b><br/>" + _xml_escape(IMMUTABLE_ARTIFACT_DISCLOSURE),
                styles["body"],
            )
        )
        meta_parts = [
            f"<b>Artifact ID:</b> {_xml_escape(ctx.artifact_id or '—')}",
            f"<b>Semantics:</b> {_xml_escape(ctx.semantics_version)}",
            f"<b>Scope:</b> {_xml_escape(ctx.report_scope or '—')}",
        ]
        if ctx.source_snapshot_hash:
            meta_parts.append(f"<b>Snapshot hash:</b> {_xml_escape(ctx.source_snapshot_hash[:16])}…")
        elements.append(Paragraph(" &nbsp;|&nbsp; ".join(meta_parts), styles["small"]))
        elements.append(
            Paragraph(
                f"<b>Generated (UTC):</b> {_xml_escape(utc_display(ctx.generated_at))} &nbsp;|&nbsp; "
                f"<b>Status:</b> {_xml_escape(ctx.immutable_status or 'frozen')}",
                styles["small"],
            )
        )
    elif ctx.is_live_regenerated:
        elements.append(
            Paragraph(
                "<b>LIVE-GENERATED EXPORT — READ BEFORE RELYING ON THIS FILE</b><br/>"
                + _xml_escape(LIVE_REGENERATED_DISCLOSURE),
                styles["body"],
            )
        )
        elements.append(
            Paragraph(
                "This document reflects portfolio state at generation time and may differ from future downloads "
                "or from the live client portal.",
                styles["small"],
            )
        )
        if ctx.original_generated_at:
            elements.append(
                Paragraph(
                    f"<b>Originally recorded:</b> {_xml_escape(utc_display(ctx.original_generated_at))} &nbsp;|&nbsp; "
                    f"<b>Regenerated:</b> {_xml_escape(utc_display(ctx.regenerated_at or ctx.generated_at))}",
                    styles["small"],
                )
            )
        else:
            elements.append(
                Paragraph(
                    f"<b>Generated (UTC):</b> {_xml_escape(utc_display(ctx.generated_at))}",
                    styles["small"],
                )
            )
    else:
        elements.append(
            Paragraph(
                "Point-in-time export. Data reflects portal records at generation; may differ after later changes.",
                styles["small"],
            )
        )
        elements.append(
            Paragraph(
                f"<b>Generated (UTC):</b> {_xml_escape(utc_display(ctx.generated_at))}",
                styles["small"],
            )
        )
    elements.append(Spacer(1, 10))
    return elements


def live_regenerated_disclosure_paragraphs(ctx: GovernancePdfContext, styles: Dict[str, Any]) -> List[Any]:
    """Alias for evidence readiness paths."""
    return export_disclosure_paragraphs(ctx, styles)


def make_page_callbacks(ctx: GovernancePdfContext) -> Tuple[Callable, Callable]:
    """ReportLab onFirstPage / onLaterPages with page numbers and governance footer."""

    def _draw(canvas, _doc):
        canvas.saveState()
        width, height = A4
        footer_y = 12 * mm
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        page_num = canvas.getPageNumber()
        left = f"Grade: {ctx.export_grade} | {PDF_LEGAL_FOOTER[:48]}…"
        if ctx.jurisdiction_summary:
            left = f"{left} | {ctx.jurisdiction_summary[:40]}"
        canvas.drawString(15 * mm, footer_y + 4 * mm, left[:95])
        canvas.drawRightString(
            width - 15 * mm,
            footer_y + 4 * mm,
            f"Page {page_num} | Generated {utc_display(ctx.generated_at)[:16]}",
        )
        canvas.drawCentredString(
            width / 2,
            footer_y,
            LIVE_REGENERATED_DISCLOSURE[:120],
        )
        canvas.restoreState()

    return _draw, _draw


def matrix_continuation_stats(
    properties: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
) -> Dict[str, int]:
    reqs_by_prop: Dict[str, List[Dict[str, Any]]] = {}
    for r in requirements:
        reqs_by_prop.setdefault(str(r.get("property_id") or ""), []).append(r)
    props_shown = min(len(properties), MATRIX_MAX_PROPERTIES_DISPLAY)
    omitted_props = max(0, len(properties) - MATRIX_MAX_PROPERTIES_DISPLAY)
    omitted_req_rows = 0
    for i, p in enumerate(properties):
        pid = str(p.get("property_id") or "")
        n = len(reqs_by_prop.get(pid, []))
        if i >= MATRIX_MAX_PROPERTIES_DISPLAY:
            omitted_req_rows += n
        else:
            omitted_req_rows += max(0, n - MATRIX_MAX_ROWS_PER_PROPERTY)
    return {
        "properties_total": len(properties),
        "properties_shown": props_shown,
        "properties_omitted": omitted_props,
        "requirement_rows_omitted": omitted_req_rows,
    }


def _append_obligation_table_section(
    elements: List[Any],
    *,
    title: str,
    intro: str,
    rows: List[Dict[str, Any]],
    total: int,
    styles: Dict[str, Any],
    table_style: Any,
    heading_style: Any,
    empty_message: str,
) -> None:
    from reportlab.platypus import Paragraph, Spacer, Table

    elements.append(Paragraph(title, heading_style))
    elements.append(Paragraph(intro, styles["small"]))
    elements.append(Spacer(1, 8))
    if not rows:
        elements.append(Paragraph(empty_message, styles["body"]))
        elements.append(Spacer(1, 16))
        return
    table_data = [["Requirement", "Property", "Status", "Assurance", "Evidence", "Review", "Expiry"]]
    for row in rows:
        table_data.append(
            [
                row["requirement"],
                row["property"],
                row.get("status_label") or row["reason"][:40],
                row["assurance"],
                row["evidence"],
                row["review"],
                row["expiry_risk"],
            ]
        )
    if total > len(rows):
        table_data.append([f"… {total - len(rows)} more", "—", "See portal", "—", "—", "—", "—"])
    t = Table(table_data, colWidths=[90, 68, 82, 45, 40, 52, 48], repeatRows=1)
    t.setStyle(table_style)
    elements.append(t)
    if total > len(rows):
        elements.append(
            Paragraph(
                f"<i>Table continues: {total - len(rows)} additional rows in portal.</i>",
                styles["small"],
            )
        )
    elements.append(Spacer(1, 16))


def append_audience_governed_obligation_sections(
    elements: List[Any],
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: Any,
    heading_style: Any,
    audience: str = "REGULATOR_EVIDENTIAL",
) -> None:
    """Governed export sections: unresolved vs recorded-not-verified vs awaiting review vs verified."""
    from reportlab.platypus import Paragraph, Spacer

    from services.audience_governance_v1 import (
        AUDIENCE_REGULATOR_EVIDENTIAL,
        EXPORT_SECTION_AWAITING_REVIEW,
        EXPORT_SECTION_RECORDED_NOT_VERIFIED,
        EXPORT_SECTION_UNRESOLVED,
        EXPORT_SECTION_VERIFIED,
        audience_export_preamble_paragraph,
    )

    preamble = audience_export_preamble_paragraph(audience)
    if preamble:
        elements.append(Paragraph(_xml_escape(preamble), styles["small"]))
        elements.append(Spacer(1, 12))

    un_rows, un_total = _collect_obligations_for_export_bucket(
        requirements, properties, client_doc, bucket=EXPORT_SECTION_UNRESOLVED
    )
    _append_obligation_table_section(
        elements,
        title="Unresolved obligations",
        intro=(
            f"Action, missing evidence, expiry, or follow-up blockers ({len(un_rows)} of {un_total} shown). "
            "These items may require landlord action."
        ),
        rows=un_rows,
        total=un_total,
        styles=styles,
        table_style=table_style,
        heading_style=heading_style,
        empty_message="No unresolved action-required obligations in export scope.",
    )

    rec_rows, rec_total = _collect_obligations_for_export_bucket(
        requirements, properties, client_doc, bucket=EXPORT_SECTION_RECORDED_NOT_VERIFIED
    )
    _append_obligation_table_section(
        elements,
        title="Recorded but not independently verified",
        intro=(
            f"Self-recorded or declaration-based satisfaction ({len(rec_rows)} of {rec_total} shown). "
            "Not missing — disclosed for evidential review. Not equivalent to external verification."
        ),
        rows=rec_rows,
        total=rec_total,
        styles=styles,
        table_style=table_style,
        heading_style=heading_style,
        empty_message="No recorded-not-verified obligations in export scope.",
    )

    rev_rows, rev_total = _collect_obligations_for_export_bucket(
        requirements, properties, client_doc, bucket=EXPORT_SECTION_AWAITING_REVIEW
    )
    _append_obligation_table_section(
        elements,
        title="Awaiting review",
        intro=(
            f"Evidence submitted — platform review pending ({len(rev_rows)} of {rev_total} shown). "
            "Not treated as missing evidence."
        ),
        rows=rev_rows,
        total=rev_total,
        styles=styles,
        table_style=table_style,
        heading_style=heading_style,
        empty_message="No obligations awaiting review in export scope.",
    )

    ver_rows, ver_total = _collect_obligations_for_export_bucket(
        requirements, properties, client_doc, bucket=EXPORT_SECTION_VERIFIED, limit=25
    )
    if ver_total > 0:
        _append_obligation_table_section(
            elements,
            title="Verified / accepted evidence (summary)",
            intro=(
                f"Platform-accepted evidence at generation time ({len(ver_rows)} of {ver_total} shown). "
                "Sample only — see requirement matrix for full detail."
            ),
            rows=ver_rows,
            total=ver_total,
            styles=styles,
            table_style=table_style,
            heading_style=heading_style,
            empty_message="",
        )


def append_unresolved_obligations_section(
    elements: List[Any],
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: Any,
    heading_style: Any,
) -> None:
    """Backward-compatible entry — routes to audience-governed multi-section layout."""
    from services.audience_governance_v1 import AUDIENCE_REGULATOR_EVIDENTIAL

    append_audience_governed_obligation_sections(
        elements,
        requirements=requirements,
        properties=properties,
        client_doc=client_doc,
        styles=styles,
        table_style=table_style,
        heading_style=heading_style,
        audience=AUDIENCE_REGULATOR_EVIDENTIAL,
    )


def append_governance_matrix_for_properties(
    elements: List[Any],
    *,
    properties: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: Any,
    heading_style: Any,
    body_style: Any,
    now: datetime,
    status_label_fn: Callable[[Optional[str]], str],
) -> None:
    from reportlab.platypus import Paragraph, Spacer, Table

    stats = matrix_continuation_stats(properties, requirements)
    elements.append(Paragraph("Property detail – requirement matrix", heading_style))
    elements.append(matrix_continuation_disclosure_paragraph(stats, styles))
    elements.append(Spacer(1, 10))

    reqs_by_prop: Dict[str, List[Dict[str, Any]]] = {}
    for r in requirements:
        reqs_by_prop.setdefault(r.get("property_id"), []).append(r)
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}

    appendix_index: List[List[str]] = [["Property", "Rows in matrix", "Rows omitted"]]

    for pi, p in enumerate(properties[: MATRIX_MAX_PROPERTIES_DISPLAY]):
        pid = p.get("property_id")
        prop_reqs = reqs_by_prop.get(pid, [])
        shown = prop_reqs[:MATRIX_MAX_ROWS_PER_PROPERTY]
        omitted = max(0, len(prop_reqs) - len(shown))
        appendix_index.append(
            [
                (p.get("address_line_1") or pid or "—")[:40],
                str(len(shown)),
                str(omitted),
            ]
        )
        label = p.get("address_line_1") or pid
        cont = f" (continued — {omitted} obligations omitted from summary matrix)" if omitted else ""
        elements.append(Paragraph(f"<b>{_xml_escape(str(label))}</b>{_xml_escape(cont)}", body_style))
        rows = [["Requirement", "Status", "Governance", "Due", "Days"]]
        for r in shown:
            eff = get_effective_expiry_date(r)
            due_for_days = eff if eff is not None else r.get("due_date")
            if eff and hasattr(eff, "isoformat"):
                due_str = eff.date().isoformat() if hasattr(eff, "date") else eff.isoformat()[:10]
            elif isinstance(r.get("due_date"), str) and r.get("due_date"):
                due_str = str(r.get("due_date"))[:10]
            else:
                due_str = "—"
            days = None
            if due_for_days:
                try:
                    d = due_for_days if isinstance(due_for_days, datetime) else datetime.fromisoformat(
                        str(due_for_days).replace("Z", "+00:00")
                    )
                    if d.tzinfo is None:
                        d = d.replace(tzinfo=timezone.utc)
                    days = (d - now).days
                except Exception:
                    days = None
            days_str = str(days) if days is not None else "—"
            cs = get_computed_status(r, property_doc=pmap.get(pid), client_doc=client_doc)
            rows.append(
                [
                    (r.get("description") or r.get("requirement_type") or "—")[:28],
                    status_label_fn(cs),
                    governance_chip_line(r)[:42],
                    due_str,
                    days_str,
                ]
            )
        if len(rows) > 1:
            tb = Table(rows, colWidths=[115, 75, 130, 65, 45])
            tb.setStyle(table_style)
            elements.append(tb)
        elements.append(Spacer(1, 10))

    if stats["properties_omitted"] > 0 or stats["requirement_rows_omitted"] > 0:
        elements.append(Paragraph("Matrix appendix index", heading_style))
        for p in properties[MATRIX_MAX_PROPERTIES_DISPLAY : MATRIX_MAX_PROPERTIES_DISPLAY + 20]:
            pid = p.get("property_id")
            n = len(reqs_by_prop.get(pid, []))
            appendix_index.append([(p.get("address_line_1") or pid or "—")[:40], "0", str(n)])
        if len(appendix_index) > 1:
            idx = Table(appendix_index, colWidths=[200, 80, 80], repeatRows=1)
            idx.setStyle(table_style)
            elements.append(idx)
        elements.append(Spacer(1, 12))


def matrix_continuation_disclosure_paragraph(stats: Dict[str, int], styles: Dict[str, Any]) -> Any:
    from reportlab.platypus import Paragraph

    if stats["properties_omitted"] == 0 and stats["requirement_rows_omitted"] == 0:
        return Paragraph(
            "Summary matrix includes all in-scope obligations in this export (within per-property row limits).",
            styles["small"],
        )
    return Paragraph(
        f"<b>Matrix continuation notice:</b> Showing {stats['properties_shown']} of {stats['properties_total']} properties "
        f"(max {MATRIX_MAX_ROWS_PER_PROPERTY} obligations per property in the summary matrix). "
        f"Additional obligations omitted from summary matrix: <b>{stats['requirement_rows_omitted']}</b> "
        f"(see Unresolved obligations section and full portal export). "
        f"Properties omitted from matrix: <b>{stats['properties_omitted']}</b>.",
        styles["body"],
    )
