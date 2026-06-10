"""
Requirements Report — operational obligation triage presentation layer.

Distinct from Compliance Summary (executive posture), Evidence Readiness (audit prep),
Monthly Digest (portfolio intelligence), and Audit Evidence Pack (immutable archive).

Transforms portal requirement rows into prioritised, scannable remediation surfaces.
Never exposes raw backend enums, workflow metadata, or registry dumps.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape as _xml_escape

from services.audience_governance_v1 import (
    AUDIENCE_LANDLORD_OPERATIONAL,
    interpret_requirement_for_audience,
)
from services.report_human_language_v1 import (
    human_compliance_status_label,
    human_evidence_presence_label,
    human_operational_renewal_date,
    human_requirements_evidence_posture,
    human_requirements_recommended_action,
    human_requirements_urgency_label,
)
from services.report_layout_governance import evidence_readiness_table_width, proportional_col_widths
from services.report_pdf_templates import _table_cell_para
from utils.expiry_utils import get_computed_status, get_effective_expiry_date

REQUIREMENTS_REPORT_TITLE = "Requirements Report"

# Presentation caps — cognitively manageable density
DETAIL_MAX_ROWS_PER_SECTION = 12
APPENDIX_MAX_ROWS_PER_PROPERTY = 12
PROPERTY_SUMMARY_MAX = 15
CLUSTER_SUMMARY_MIN_GROUP = 2

TRIAGE_IMMEDIATE = "immediate_attention"
TRIAGE_RENEWALS = "upcoming_renewals"
TRIAGE_EVIDENCE_REVIEW = "evidence_review_required"
TRIAGE_RECORDED = "recorded_not_verified"
TRIAGE_COMPLIANT = "fully_compliant"
TRIAGE_MONITORING = "monitoring_only"

TRIAGE_SECTION_ORDER: Tuple[str, ...] = (
    TRIAGE_IMMEDIATE,
    TRIAGE_RENEWALS,
    TRIAGE_EVIDENCE_REVIEW,
    TRIAGE_RECORDED,
    TRIAGE_COMPLIANT,
    TRIAGE_MONITORING,
)

TRIAGE_SECTION_TITLES: Dict[str, str] = {
    TRIAGE_IMMEDIATE: "Immediate attention",
    TRIAGE_RENEWALS: "Upcoming renewals",
    TRIAGE_EVIDENCE_REVIEW: "Evidence review required",
    TRIAGE_RECORDED: "Recorded but not independently verified",
    TRIAGE_COMPLIANT: "Fully compliant obligations",
    TRIAGE_MONITORING: "Monitoring only",
}

TRIAGE_SECTION_INTROS: Dict[str, str] = {
    TRIAGE_IMMEDIATE: (
        "Obligations needing prompt action — missing evidence, overdue items, or operational blockers. "
        "Address these first to reduce exposure."
    ),
    TRIAGE_RENEWALS: (
        "Renewals approaching within the configured window. Schedule evidence collection before expiry."
    ),
    TRIAGE_EVIDENCE_REVIEW: (
        "Evidence submitted and awaiting platform review. Not missing — decision pending."
    ),
    TRIAGE_RECORDED: (
        "Recorded on file without independent verification. Not failed — lower evidential confidence. "
        "Review may still be recommended before relying on these records externally."
    ),
    TRIAGE_COMPLIANT: (
        "Verified or accepted obligations at generation time. No immediate action unless renewal applies."
    ),
    TRIAGE_MONITORING: (
        "Satisfied obligations with no immediate action. Continue routine monitoring."
    ),
}

_CLUSTER_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Fire safety", ("gas", "fire", "smoke", "emergency lighting", "extinguisher", "alarm", "frs")),
    ("Licensing", ("licence", "license", "hmo", "selective", "registration")),
    ("Tenancy documentation", ("tenancy", "deposit", "right to rent", "rent", "contract", "how to rent")),
    ("Evidence verification", ("review", "verify", "upload", "document", "certificate", "epc", "eicr")),
    ("Onboarding", ("onboarding", "initial", "setup", "welcome")),
)

_FORBIDDEN_LEAK_TOKENS = frozenset(
    {
        "unknown_date",
        "workflow_class",
        "take_action",
        "property_id",
        "requirement_id",
        "semantic_state",
        "self_recorded",
        "satisfied_unverified",
        "action_required",
        "evidence_state",
        "client_lifecycle_state",
        "assurance_tier",
        "truth_presentation_stage",
    }
)

_LEAK_RE = re.compile(
    r"\b("
    r"UNKNOWN_DATE|SELF_RECORDED|SATISFIED_UNVERIFIED|WORKFLOW_CLASS|TAKE_ACTION|"
    r"EVIDENCE_STATE|CLIENT_LIFECYCLE|ASSURANCE_TIER|SEMANTIC_STATE|PLATFORM_REVIEW_PENDING"
    r")\b",
    re.I,
)


def assert_client_safe_text(text: str) -> None:
    """Raise if presentation text leaks backend vocabulary."""
    from services.report_human_language_v1 import contains_internal_language_leak
    from services.vocabulary_contract_v1 import assert_semantic_safe_text

    t = (text or "").strip()
    if not t:
        return
    if _LEAK_RE.search(t) or contains_internal_language_leak(t):
        raise ValueError(f"backend semantic leak in requirements presentation: {t[:80]!r}")
    assert_semantic_safe_text(t, context="requirements_operational", allow_stale=True)


def collect_all_client_text(model: Dict[str, Any]) -> List[str]:
    """Flatten model strings for leakage audits."""
    out: List[str] = []
    for sec in model.get("sections") or []:
        out.append(sec.get("title") or "")
        out.append(sec.get("intro") or "")
        for c in sec.get("cluster_summaries") or []:
            out.append(c)
        for r in sec.get("detail_rows") or []:
            for v in r.values():
                if isinstance(v, str):
                    out.append(v)
    for ps in model.get("property_summaries") or []:
        for v in ps.values():
            if isinstance(v, str):
                out.append(v)
    for r in model.get("appendix_rows") or []:
        for v in r.values():
            if isinstance(v, str):
                out.append(v)
    return [x for x in out if x]


def classify_issue_cluster(row: Dict[str, Any]) -> str:
    """Group obligations by operational theme for scanning."""
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("description", "requirement_type", "requirement_name", "category")
    ).lower()
    for label, keywords in _CLUSTER_RULES:
        if any(kw in blob for kw in keywords):
            return label
    return "General compliance"


def classify_operational_triage_bucket(
    row: Dict[str, Any],
    *,
    property_doc: Optional[dict],
    client_doc: dict,
    now: Optional[datetime] = None,
) -> str:
    """Assign one operational triage bucket per requirement row."""
    from services.audience_governance_v1 import (
        _is_awaiting_review_row,
        _is_recorded_not_verified_row,
        _is_true_unresolved_row,
        _is_verified_row,
        _satisfied,
    )

    cs = (get_computed_status(row, property_doc=property_doc, client_doc=client_doc) or "").upper()

    if _is_true_unresolved_row(row, property_doc=property_doc, client_doc=client_doc):
        return TRIAGE_IMMEDIATE
    if _is_awaiting_review_row(row):
        return TRIAGE_EVIDENCE_REVIEW
    if _is_recorded_not_verified_row(row):
        return TRIAGE_RECORDED
    if cs == "EXPIRING_SOON":
        return TRIAGE_RENEWALS
    if _is_verified_row(row) and _satisfied(row):
        return TRIAGE_COMPLIANT
    if _satisfied(row) and cs in ("COMPLIANT", "VALID", "NOT_REQUIRED"):
        return TRIAGE_MONITORING
    if cs in ("OVERDUE", "EXPIRED", "MISSING", "PENDING"):
        return TRIAGE_IMMEDIATE
    return TRIAGE_MONITORING


def _property_address(property_doc: Optional[dict], property_id: Optional[str]) -> str:
    if property_doc:
        parts = [property_doc.get("address_line_1"), property_doc.get("postcode")]
        addr = ", ".join(x for x in parts if x)
        if addr:
            return addr[:60]
    return str(property_id or "—")[:24]


def _obligation_label(row: Dict[str, Any]) -> str:
    return (row.get("description") or row.get("requirement_type") or "Obligation")[:72]


def _build_enriched_row(
    row: Dict[str, Any],
    *,
    property_doc: Optional[dict],
    client_doc: dict,
    now: datetime,
) -> Dict[str, Any]:
    interp = interpret_requirement_for_audience(
        row,
        AUDIENCE_LANDLORD_OPERATIONAL,
        property_doc=property_doc,
        client_doc=client_doc,
    )
    bucket = classify_operational_triage_bucket(
        row, property_doc=property_doc, client_doc=client_doc, now=now
    )
    cluster = classify_issue_cluster(row)
    cs = get_computed_status(row, property_doc=property_doc, client_doc=client_doc)
    posture = human_requirements_evidence_posture(row, interp)
    renewal = human_operational_renewal_date(row)
    action = human_requirements_recommended_action(row, interp, bucket=bucket)
    urgency = human_requirements_urgency_label(bucket, cs)

    detail = {
        "obligation": _obligation_label(row),
        "property": _property_address(property_doc, row.get("property_id")),
        "status": human_compliance_status_label(cs) if cs else interp.get("audience_status_label", "—"),
        "evidence_posture": posture,
        "renewal": renewal,
        "recommended_action": action,
        "urgency": urgency,
        "cluster": cluster,
        "triage_bucket": bucket,
        "property_id": row.get("property_id"),
        "requirement_id": row.get("requirement_id"),
    }
    from services.report_human_language_v1 import sanitize_customer_export_text

    for key in (
        "obligation",
        "property",
        "status",
        "evidence_posture",
        "renewal",
        "recommended_action",
        "urgency",
        "cluster",
    ):
        val = detail.get(key)
        if isinstance(val, str):
            detail[key] = sanitize_customer_export_text(val)
    return detail


def build_cluster_summaries(
    rows: List[Dict[str, Any]],
    *,
    bucket: str,
    min_group: int = CLUSTER_SUMMARY_MIN_GROUP,
) -> List[str]:
    """Grouped remediation lines — e.g. '3 fire safety obligations across 2 properties'."""
    by_cluster: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_cluster[r.get("cluster") or "General compliance"].append(r)

    summaries: List[str] = []
    action_verb = {
        TRIAGE_IMMEDIATE: "require immediate attention",
        TRIAGE_RENEWALS: "have renewals approaching",
        TRIAGE_EVIDENCE_REVIEW: "await evidence review",
        TRIAGE_RECORDED: "are recorded but not independently verified",
        TRIAGE_COMPLIANT: "are fully compliant",
        TRIAGE_MONITORING: "are stable for routine monitoring",
    }.get(bucket, "need review")

    for cluster, items in sorted(by_cluster.items(), key=lambda x: (-len(x[1]), x[0])):
        n = len(items)
        props = len({i.get("property") for i in items if i.get("property")})
        if n >= min_group or (bucket == TRIAGE_IMMEDIATE and n >= 1):
            prop_phrase = f" across {props} propert{'ies' if props != 1 else 'y'}" if props > 1 else ""
            summaries.append(f"{n} {cluster.lower()} obligation{'s' if n != 1 else ''}{prop_phrase} {action_verb}.")
        elif n == 1:
            item = items[0]
            summaries.append(
                f"{item.get('obligation', 'Obligation')[:50]} ({item.get('property', '—')[:30]}) — {action_verb}."
            )
    return summaries[:8]


def _property_priority_indicator(
    immediate: int,
    renewals: int,
    review: int,
    recorded: int,
) -> str:
    if immediate > 0:
        return "High priority"
    if review > 0 or renewals > 2:
        return "Elevated"
    if recorded > 3:
        return "Review suggested"
    return "Stable"


def build_property_summaries(
    enriched_rows: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    by_prop: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in enriched_rows:
        pid = r.get("property_id")
        if pid:
            by_prop[str(pid)].append(r)

    summaries: List[Dict[str, Any]] = []
    seen = set()
    for p in properties:
        pid = p.get("property_id")
        if not pid:
            continue
        seen.add(str(pid))
        rows = by_prop.get(str(pid), [])
        counts = {b: 0 for b in TRIAGE_SECTION_ORDER}
        for r in rows:
            counts[r.get("triage_bucket") or TRIAGE_MONITORING] += 1
        summaries.append(
            {
                "property": _property_address(p, pid),
                "priority": _property_priority_indicator(
                    counts[TRIAGE_IMMEDIATE],
                    counts[TRIAGE_RENEWALS],
                    counts[TRIAGE_EVIDENCE_REVIEW],
                    counts[TRIAGE_RECORDED],
                ),
                "immediate": counts[TRIAGE_IMMEDIATE],
                "renewals": counts[TRIAGE_RENEWALS],
                "evidence_review": counts[TRIAGE_EVIDENCE_REVIEW],
                "recorded_unverified": counts[TRIAGE_RECORDED],
                "compliant": counts[TRIAGE_COMPLIANT],
                "monitoring": counts[TRIAGE_MONITORING],
                "total": len(rows),
            }
        )

    for pid, rows in by_prop.items():
        if pid in seen:
            continue
        counts = {b: 0 for b in TRIAGE_SECTION_ORDER}
        for r in rows:
            counts[r.get("triage_bucket") or TRIAGE_MONITORING] += 1
        summaries.append(
            {
                "property": rows[0].get("property") if rows else pid,
                "priority": _property_priority_indicator(
                    counts[TRIAGE_IMMEDIATE],
                    counts[TRIAGE_RENEWALS],
                    counts[TRIAGE_EVIDENCE_REVIEW],
                    counts[TRIAGE_RECORDED],
                ),
                "immediate": counts[TRIAGE_IMMEDIATE],
                "renewals": counts[TRIAGE_RENEWALS],
                "evidence_review": counts[TRIAGE_EVIDENCE_REVIEW],
                "recorded_unverified": counts[TRIAGE_RECORDED],
                "compliant": counts[TRIAGE_COMPLIANT],
                "monitoring": counts[TRIAGE_MONITORING],
                "total": len(rows),
            }
        )
    return summaries[:PROPERTY_SUMMARY_MAX]


def build_requirements_operational_model(
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Full presentation model for PDF and CSV."""
    now = now or datetime.now(timezone.utc)
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    client = client_doc or {}

    enriched: List[Dict[str, Any]] = []
    for row in requirements:
        pd = pmap.get(row.get("property_id"))
        enriched.append(_build_enriched_row(row, property_doc=pd, client_doc=client, now=now))

    by_bucket: Dict[str, List[Dict[str, Any]]] = {b: [] for b in TRIAGE_SECTION_ORDER}
    for r in enriched:
        by_bucket[r.get("triage_bucket") or TRIAGE_MONITORING].append(r)

    triage_counts = {b: len(by_bucket[b]) for b in TRIAGE_SECTION_ORDER}
    sections: List[Dict[str, Any]] = []
    for bucket in TRIAGE_SECTION_ORDER:
        rows = by_bucket[bucket]
        if not rows and bucket not in (TRIAGE_IMMEDIATE, TRIAGE_RECORDED):
            continue
        sections.append(
            {
                "bucket": bucket,
                "title": TRIAGE_SECTION_TITLES[bucket],
                "intro": TRIAGE_SECTION_INTROS[bucket],
                "cluster_summaries": build_cluster_summaries(rows, bucket=bucket),
                "detail_rows": rows[:DETAIL_MAX_ROWS_PER_SECTION],
                "total": len(rows),
                "omitted": max(0, len(rows) - DETAIL_MAX_ROWS_PER_SECTION),
            }
        )

    # Property appendix — condensed rows for properties with most exposure
    prop_exposure = sorted(
        enriched,
        key=lambda r: (
            0 if r.get("triage_bucket") == TRIAGE_IMMEDIATE else 1,
            0 if r.get("triage_bucket") == TRIAGE_RENEWALS else 1,
            r.get("obligation") or "",
        ),
    )
    appendix_rows = [
        {
            "property": r["property"],
            "obligation": r["obligation"],
            "posture": r["evidence_posture"],
            "renewal": r["renewal"],
            "action": r["recommended_action"],
        }
        for r in prop_exposure[: APPENDIX_MAX_ROWS_PER_PROPERTY * PROPERTY_SUMMARY_MAX]
    ]

    return {
        "triage_counts": triage_counts,
        "sections": sections,
        "property_summaries": build_property_summaries(enriched, properties),
        "appendix_rows": appendix_rows,
        "enriched_rows": enriched,
        "total_requirements": len(requirements),
    }


def _scheduled_email_status_enum(row: Dict[str, Any]) -> str:
    """Map operational presentation row to legacy SCHEDULED_REPORT status bucket."""
    raw = str(row.get("status") or "").upper()
    if raw in ("OVERDUE", "EXPIRED", "EXPIRING_SOON", "PENDING", "COMPLIANT", "MISSING"):
        if raw == "EXPIRED":
            return "OVERDUE"
        if raw == "MISSING":
            return "PENDING"
        return raw
    bucket = row.get("triage_bucket") or ""
    low = str(row.get("status") or "").lower()
    if bucket == TRIAGE_IMMEDIATE or "overdue" in low or "expired" in low:
        return "OVERDUE"
    if bucket == TRIAGE_RECORDED:
        return "RECORDED_UNVERIFIED"
    if bucket == TRIAGE_RENEWALS:
        return "EXPIRING_SOON"
    if bucket in (TRIAGE_COMPLIANT, TRIAGE_MONITORING) or "compliant" in low:
        return "COMPLIANT"
    if bucket == TRIAGE_EVIDENCE_REVIEW:
        return "PENDING"
    if "renewal approaching" in low:
        return "EXPIRING_SOON"
    return "PENDING"


def build_requirements_scheduled_email_rows(
    enriched_rows: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Transitional rows for jobs.py → SCHEDULED_REPORT email digest.

    Customer CSV downloads use operational columns; scheduled emails still expect
    legacy keys (status, due_date, description) for aggregation — populated here
    from the operational model without re-exposing raw backend enums in CSV files.
    """
    out: List[Dict[str, str]] = []
    for r in enriched_rows:
        renewal = str(r.get("renewal") or "")
        due = renewal if renewal and renewal != "No verified renewal date recorded" else "N/A"
        out.append(
            {
                "property_address": str(r.get("property") or "—"),
                "description": str(r.get("obligation") or "Requirement"),
                "requirement_type": str(r.get("cluster") or "requirement"),
                "status": _scheduled_email_status_enum(r),
                "due_date": due,
                "obligation": str(r.get("obligation") or ""),
                "operational_status": str(r.get("status") or ""),
                "renewal_date": renewal,
                "urgency": str(r.get("urgency") or ""),
                "triage_category": TRIAGE_SECTION_TITLES.get(
                    str(r.get("triage_bucket") or ""), ""
                ),
                "recommended_action": str(r.get("recommended_action") or ""),
            }
        )
    return out


def build_requirements_operational_csv_rows(
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """Human-readable CSV rows with triage semantics."""
    model = build_requirements_operational_model(
        requirements=requirements,
        properties=properties,
        client_doc=client_doc,
        now=now,
    )
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    rows_out: List[Dict[str, str]] = []
    for r in model["enriched_rows"]:
        rows_out.append(
            {
                "property_address": r.get("property") or "—",
                "obligation": r.get("obligation") or "—",
                "triage_category": TRIAGE_SECTION_TITLES.get(r.get("triage_bucket") or "", "—"),
                "issue_cluster": r.get("cluster") or "—",
                "operational_status": r.get("status") or "—",
                "evidence_posture": r.get("evidence_posture") or "—",
                "renewal_date": r.get("renewal") or "—",
                "recommended_action": r.get("recommended_action") or "—",
                "urgency": r.get("urgency") or "—",
            }
        )
    return rows_out, model["triage_counts"], model["enriched_rows"]


CSV_FIELDNAMES = [
    "property_address",
    "obligation",
    "triage_category",
    "issue_cluster",
    "operational_status",
    "evidence_posture",
    "renewal_date",
    "recommended_action",
    "urgency",
]

# Raw fields that must never appear in customer CSV
CSV_FORBIDDEN_COLUMNS = frozenset(
    {
        "requirement_id",
        "property_id",
        "evidence_state",
        "client_lifecycle_state",
        "assurance_tier",
        "workflow_class",
        "jurisdiction_source",
        "status",
        "action_required",
        "review_state",
        "evidential_assurance",
        "audience_status",
        "frequency_days",
        "latest_doc_status",
    }
)


def _section_table(
    detail_rows: List[Dict[str, Any]],
    styles: Dict[str, Any],
    table_style: TableStyle,
) -> Table:
    table_width = evidence_readiness_table_width()
    col_widths = proportional_col_widths(
        table_width, [0.24, 0.20, 0.18, 0.16, 0.22]
    )
    data = [
        [
            _table_cell_para("Obligation", styles, bold=True),
            _table_cell_para("Property", styles, bold=True),
            _table_cell_para("Posture", styles, bold=True),
            _table_cell_para("Renewal", styles, bold=True),
            _table_cell_para("Action", styles, bold=True),
        ]
    ]
    for r in detail_rows:
        data.append(
            [
                _table_cell_para(r.get("obligation") or "—", styles),
                _table_cell_para(r.get("property") or "—", styles),
                _table_cell_para(r.get("evidence_posture") or "—", styles),
                _table_cell_para(r.get("renewal") or "—", styles),
                _table_cell_para(r.get("recommended_action") or "—", styles),
            ]
        )
    t = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    t.setStyle(table_style)
    return t


def append_requirements_operational_sections(
    elements: List[Any],
    *,
    model: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: TableStyle,
) -> None:
    """Render operational triage PDF body from presentation model."""
    counts = model.get("triage_counts") or {}
    elements.append(Paragraph("<b>Triage at a glance</b>", styles["heading"]))
    glance = (
        f"Immediate: <b>{counts.get(TRIAGE_IMMEDIATE, 0)}</b> &nbsp;|&nbsp; "
        f"Renewals: <b>{counts.get(TRIAGE_RENEWALS, 0)}</b> &nbsp;|&nbsp; "
        f"Evidence review: <b>{counts.get(TRIAGE_EVIDENCE_REVIEW, 0)}</b> &nbsp;|&nbsp; "
        f"Recorded (unverified): <b>{counts.get(TRIAGE_RECORDED, 0)}</b> &nbsp;|&nbsp; "
        f"Compliant: <b>{counts.get(TRIAGE_COMPLIANT, 0)}</b> &nbsp;|&nbsp; "
        f"Monitoring: <b>{counts.get(TRIAGE_MONITORING, 0)}</b>"
    )
    elements.append(Paragraph(glance, styles["body"]))
    elements.append(
        Paragraph(
            "Operational obligation management export — prioritised for remediation sequencing, not registry completeness.",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 14))

    for sec in model.get("sections") or []:
        title = sec.get("title") or ""
        intro = sec.get("intro") or ""
        total = int(sec.get("total") or 0)
        if total == 0 and sec.get("bucket") not in (TRIAGE_IMMEDIATE, TRIAGE_RECORDED):
            continue
        header_block: List[Any] = [
            Paragraph(_xml_escape(title), styles["heading"]),
            Paragraph(_xml_escape(intro), styles["small"]),
            Spacer(1, 6),
        ]
        body_block: List[Any] = []
        for line in sec.get("cluster_summaries") or []:
            body_block.append(Paragraph(f"• {_xml_escape(line)}", styles["body"]))
        if body_block:
            body_block.append(Spacer(1, 6))
        detail = sec.get("detail_rows") or []
        if detail:
            body_block.append(_section_table(detail, styles, table_style))
            omitted = int(sec.get("omitted") or 0)
            if omitted:
                body_block.append(
                    Paragraph(
                        f"<i>{omitted} additional obligation(s) in this category — see portal or CSV export.</i>",
                        styles["small"],
                    )
                )
            body_block.append(Spacer(1, 12))
        elif total == 0:
            body_block.append(Paragraph("None in export scope.", styles["body"]))
            body_block.append(Spacer(1, 12))
        else:
            body_block.append(Spacer(1, 12))
        elements.append(KeepTogether(header_block + body_block[:3]))
        for item in body_block[3:]:
            elements.append(item)

    props = model.get("property_summaries") or []
    if props:
        elements.append(Paragraph("Property operational summaries", styles["heading"]))
        elements.append(
            Paragraph(
                "Quick signal of operational load per property — not a full obligation matrix.",
                styles["small"],
            )
        )
        elements.append(Spacer(1, 8))
        table_width = evidence_readiness_table_width()
        prop_widths = proportional_col_widths(
            table_width, [0.28, 0.10, 0.10, 0.10, 0.10, 0.14, 0.08]
        )
        prop_data = [
            [
                _table_cell_para("Property", styles, bold=True),
                _table_cell_para("Priority", styles, bold=True),
                _table_cell_para("Immediate", styles, bold=True),
                _table_cell_para("Renewals", styles, bold=True),
                _table_cell_para("Review", styles, bold=True),
                _table_cell_para("Recorded", styles, bold=True),
                _table_cell_para("Total", styles, bold=True),
            ]
        ]
        for ps in props:
            prop_data.append(
                [
                    _table_cell_para(ps.get("property") or "—", styles),
                    _table_cell_para(ps.get("priority") or "—", styles),
                    _table_cell_para(str(ps.get("immediate") or 0), styles),
                    _table_cell_para(str(ps.get("renewals") or 0), styles),
                    _table_cell_para(str(ps.get("evidence_review") or 0), styles),
                    _table_cell_para(str(ps.get("recorded_unverified") or 0), styles),
                    _table_cell_para(str(ps.get("total") or 0), styles),
                ]
            )
        pt = Table(prop_data, colWidths=prop_widths, repeatRows=1, splitByRow=1)
        pt.setStyle(table_style)
        elements.append(pt)
        elements.append(Spacer(1, 14))

    appendix = model.get("appendix_rows") or []
    if appendix:
        elements.append(Paragraph("Condensed obligation reference", styles["subheading"]))
        elements.append(
            Paragraph(
                f"Sample of highest-exposure obligations ({min(len(appendix), APPENDIX_MAX_ROWS_PER_PROPERTY * 3)} shown).",
                styles["small"],
            )
        )
        elements.append(Spacer(1, 6))
        app_widths = proportional_col_widths(
            table_width, [0.20, 0.26, 0.18, 0.16, 0.20]
        )
        app_data = [
            [
                _table_cell_para("Property", styles, bold=True),
                _table_cell_para("Obligation", styles, bold=True),
                _table_cell_para("Posture", styles, bold=True),
                _table_cell_para("Renewal", styles, bold=True),
                _table_cell_para("Action", styles, bold=True),
            ]
        ]
        for r in appendix[: APPENDIX_MAX_ROWS_PER_PROPERTY * 3]:
            app_data.append(
                [
                    _table_cell_para(r.get("property") or "—", styles),
                    _table_cell_para(r.get("obligation") or "—", styles),
                    _table_cell_para(r.get("posture") or "—", styles),
                    _table_cell_para(r.get("renewal") or "—", styles),
                    _table_cell_para(r.get("action") or "—", styles),
                ]
            )
        at = Table(app_data, colWidths=app_widths, repeatRows=1, splitByRow=1)
        at.setStyle(table_style)
        elements.append(at)
