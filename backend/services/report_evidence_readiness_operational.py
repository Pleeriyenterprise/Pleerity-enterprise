"""
Operational Audit Readiness presentation layer for Evidence Readiness PDFs.

Distinct from governed Audit Evidence Pack (evidentiary archive). Focuses on
remediation, triage, and audit-preparation workflows — not tribunal bundles.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape as _xml_escape

from services.report_human_language_v1 import human_compliance_status_label
from services.report_layout_governance import proportional_col_widths
from services.report_pdf_templates import (
    ACTION_PRIORITIES,
    build_matrix_rows,
    compute_readiness_indicators,
    _obligation_cell_para,
    _table_cell_para,
)

# pdf_report_builder uses 50pt side margins.
OPERATIONAL_REPORT_TABLE_WIDTH = A4[0] - 100

# --- Audit event humanisation (presentation only; raw codes retained in metadata) ---

_AUDIT_EVENT_OVERRIDES: Dict[str, str] = {
    "COMPLIANCE_RECALC_SLA_BREACH": "Compliance recalculation exceeded SLA threshold",
    "RISK_SIGNAL_REGEN_COMPLETED": "Risk assessment regeneration completed",
    "RISK_SIGNAL_REGEN_STARTED": "Risk assessment regeneration started",
    "COMPLIANCE_SCORE_RECALCULATED": "Compliance score recalculated",
    "DOCUMENT_UPLOADED": "Compliance document uploaded",
    "DOCUMENT_VERIFIED": "Compliance document verified",
    "EVIDENCE_REVIEW_COMPLETED": "Evidence review completed",
    "TENANT_DELIVERY_PROOF_RECORDED": "Tenant delivery proof recorded",
    "REQUIREMENT_STATUS_CHANGED": "Obligation status updated",
    "AUDIT_PACK_GENERATED": "Audit evidence pack generated",
    "REPORT_GENERATED": "Report export generated",
}

_LOW_VALUE_EVENT_PREFIXES = (
    "COMPLIANCE_RECALC_SLA_BREACH",
    "HEARTBEAT",
    "PING",
    "CACHE_",
)

_EVENT_FAMILY_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Evidence lifecycle", ("DOCUMENT", "EVIDENCE", "UPLOAD", "VERIFY", "INTAKE")),
    ("Compliance scoring", ("COMPLIANCE", "SCORE", "RECALC", "SLA", "CALC")),
    ("User and admin actions", ("ROLE_", "ADMIN", "USER", "IMPERSON", "LOGIN")),
    ("Risk assessment", ("RISK", "SIGNAL")),
    ("Delivery proof", ("DELIVERY", "TENANT", "PROOF")),
    ("Reporting and exports", ("REPORT", "EXPORT", "AUDIT_PACK")),
)

_PRIORITY_SEVERITY_BG = {
    "Critical": colors.Color(0.98, 0.92, 0.92),
    "High": colors.Color(0.99, 0.96, 0.88),
    "Medium": colors.Color(0.95, 0.97, 0.99),
    "Informational": colors.Color(0.97, 0.97, 0.97),
}

COMPACT_FOOTER_SNAPSHOT = "Frozen snapshot export · generation boundary applies"
COMPACT_FOOTER_LIVE = "Point-in-time export · may differ on re-download"


def humanize_audit_event_action(action: Optional[str]) -> str:
    """Convert telemetry-style audit codes to operator-readable labels."""
    raw = (action or "").strip()
    if not raw:
        return "System event"
    if raw in _AUDIT_EVENT_OVERRIDES:
        return _AUDIT_EVENT_OVERRIDES[raw]
    if raw.upper() in _AUDIT_EVENT_OVERRIDES:
        return _AUDIT_EVENT_OVERRIDES[raw.upper()]
    # Title-case token stream: FOO_BAR_BAZ → Foo bar baz
    words = re.sub(r"[_\-]+", " ", raw).strip().lower()
    if not words:
        return raw[:48]
    titled = words.title() if len(words) <= 48 else words[:48].title()
    return titled[:72]


def _event_family(action: Optional[str]) -> str:
    upper = (action or "").upper()
    for family, prefixes in _EVENT_FAMILY_RULES:
        if any(upper.startswith(p) or p in upper for p in prefixes):
            return family
    return "Other system activity"


def _is_low_value_telemetry(action: Optional[str]) -> bool:
    upper = (action or "").upper()
    return any(upper.startswith(p) for p in _LOW_VALUE_EVENT_PREFIXES)


def group_audit_events_for_operational_report(
    events: List[Dict[str, Any]],
    *,
    max_per_family: int = 12,
    collapse_repetitive: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group audit events by operational family; collapse repetitive low-value telemetry.
    Each returned event dict includes human_label and optional similar_count.
    """
    by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ev in events:
        action = ev.get("action") or ev.get("event_type")
        if collapse_repetitive and _is_low_value_telemetry(action):
            continue
        family = _event_family(action)
        md = ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}
        human = humanize_audit_event_action(action)
        summary = str(md.get("summary") or human)[:80]
        by_family[family].append(
            {
                "timestamp": ev.get("timestamp"),
                "action_raw": action,
                "human_label": human,
                "summary": summary,
                "actor_role": ev.get("actor_role") or ev.get("actor") or "system",
                "resource_id": ev.get("resource_id") or md.get("requirement_id"),
            }
        )

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for family, items in by_family.items():
        if collapse_repetitive:
            seen: Dict[str, int] = defaultdict(int)
            collapsed: List[Dict[str, Any]] = []
            for item in items:
                key = item["human_label"]
                seen[key] += 1
                if seen[key] == 1:
                    collapsed.append(dict(item))
                elif seen[key] == 2:
                    collapsed[-1]["similar_count"] = 2
                else:
                    collapsed[-1]["similar_count"] = seen[key]
            items = collapsed
        grouped[family] = items[:max_per_family]
    return grouped


def enrich_readiness_interpretation(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """Add calm operational interpretation lines to readiness indicators."""
    out = dict(indicators)
    total = int(out.get("total_obligations") or 0)
    pct = out.get("evidence_completeness_pct")
    with_ev = 0
    if total and pct is not None:
        with_ev = round((pct / 100) * total)
    remaining = max(0, total - with_ev)
    lines = [
        out.get("evidence_completeness_note") or "",
        (
            f"{remaining} obligation(s) may still require upload, onboarding, or verification before audit review."
            if remaining
            else "All in-scope obligations currently have evidence on file at the generation boundary."
        ),
    ]
    readiness = out.get("audit_readiness") or ""
    if "Not audit-ready" in readiness:
        lines.append(
            "Focus remediation on critical and high-priority items below before external audit or council review."
        )
    elif "Substantially ready" in readiness:
        lines.append("Limited exceptions remain; address priority items to improve audit confidence.")
    else:
        lines.append("Maintain renewal dates and monitor expiring obligations to preserve readiness.")
    del_pct = out.get("delivery_proof_completeness_pct")
    if del_pct is not None and del_pct < 100:
        lines.append(out.get("delivery_proof_note") or "")
    out["interpretation_lines"] = [ln for ln in lines if ln]
    return out


def build_recommended_remediation_actions(
    matrix_rows: List[Dict[str, str]],
    *,
    now: Optional[datetime] = None,
    max_per_priority: int = 8,
) -> Dict[str, List[str]]:
    """Generate Priority 1–3 operational remediation guidance (non-legal)."""
    now = now or datetime.now(timezone.utc)
    p1: List[str] = []
    p2: List[str] = []
    p3: List[str] = []

    def _expiry_phrase(row: Dict[str, str]) -> str:
        exp = row.get("expiry") or ""
        if exp and exp != "—":
            return f" before {exp}"
        days = row.get("days_to_expiry")
        if days and days not in ("-", "") and str(days).lstrip("-").isdigit():
            d = int(days)
            if d >= 0:
                return f" within {d} day(s)"
        return ""

    for row in matrix_rows:
        name = (row.get("obligation") or "Obligation").strip()
        pri = row.get("priority") or "Informational"
        risk = row.get("risk_level") or ""
        status = (row.get("status") or "").upper()
        evidence = row.get("evidence_present") or "No"
        delivery = row.get("delivery_proof") or ""
        action = row.get("action_required") or "No"
        urgent = pri in ("Critical", "High") or risk in ("Critical", "High")

        if urgent or (action == "Yes" and evidence == "No"):
            if evidence == "No":
                p1.append(f"Upload {name} evidence{ _expiry_phrase(row)}.")
            elif status in ("OVERDUE", "EXPIRED"):
                p1.append(f"Resolve overdue {name} — renew or replace evidence{ _expiry_phrase(row)}.")
            elif delivery == "No" and action in ("Yes", "Review"):
                p1.append(f"Add delivery proof or tenant confirmation for {name}.")
            else:
                p1.append(f"Review {name} — priority attention at generation boundary.")
        elif pri == "Medium" or status in ("EXPIRING_SOON", "PENDING", "MISSING"):
            if status in ("EXPIRING_SOON", "OVERDUE", "EXPIRED"):
                p2.append(f"Review {name} before renewal breach{ _expiry_phrase(row)}.")
            elif evidence == "No":
                p2.append(f"Upload missing evidence for {name}.")
            elif action == "Review":
                p2.append(f"Confirm {name} details and supporting documents.")
        elif action in ("Review", "Yes"):
            p3.append(f"Schedule review of {name}{ _expiry_phrase(row)}.")

    return {
        "Priority 1": p1[:max_per_priority],
        "Priority 2": p2[:max_per_priority],
        "Priority 3": p3[:max_per_priority],
    }


def _human_status(status_raw: str) -> str:
    return human_compliance_status_label(status_raw) or status_raw or "—"


def _human_actor_role(role: Any) -> str:
    raw = str(role or "system").strip()
    upper = raw.upper()
    if upper in ("ROLE_CLIENT", "CLIENT"):
        return "Client"
    if upper in ("SYSTEM", "ROLE_SYSTEM"):
        return "System"
    if upper.startswith("ROLE_"):
        return raw[5:].replace("_", " ").title()
    return raw.replace("_", " ").title() if raw else "System"


def build_operational_matrix_rows(
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    docs_by_req: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    delivery_by_req: Optional[Dict[str, bool]] = None,
    now: Optional[datetime] = None,
    property_filter_id: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Build core 6-column operational rows plus secondary metadata appendix rows.
    """
    full = build_matrix_rows(
        requirements=requirements,
        properties=properties,
        client_doc=client_doc,
        docs_by_req=docs_by_req,
        delivery_by_req=delivery_by_req,
        now=now,
        property_filter_id=property_filter_id,
    )
    core: List[Dict[str, str]] = []
    appendix: List[Dict[str, str]] = []
    for row in full:
        core.append(
            {
                "obligation": row.get("obligation") or "—",
                "status": _human_status(row.get("status") or ""),
                "evidence": row.get("evidence_present") or "—",
                "expiry": row.get("expiry") or "—",
                "risk": row.get("risk_level") or "—",
                "action_required": row.get("action_required") or "—",
                "priority": row.get("priority") or "Informational",
            }
        )
        appendix.append(
            {
                "obligation": row.get("obligation") or "—",
                "category": row.get("category") or "—",
                "file_ref": row.get("evidence_ref") or "—",
                "delivery": row.get("delivery_proof") or "—",
                "updated": row.get("last_updated") or "—",
            }
        )
    return core, appendix


def create_operational_table_style(header_bg: Any = None, *, font_size: int = 9) -> TableStyle:
    bg = header_bg or colors.Color(0.12, 0.15, 0.22)
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.Color(0.82, 0.82, 0.82)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.98, 0.985, 0.99)]),
        ]
    )


def _risk_row_style(table: Table, row_idx: int, risk: str) -> None:
    bg = _PRIORITY_SEVERITY_BG.get(risk)
    if bg and row_idx > 0:
        table.setStyle(TableStyle([("BACKGROUND", (0, row_idx), (-1, row_idx), bg)]))


def append_operational_readiness_section(
    elements: List[Any],
    *,
    indicators: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: TableStyle,
) -> None:
    enriched = enrich_readiness_interpretation(indicators)
    ent_styles = styles if styles.get("table_cell") else {**styles, "table_cell": styles.get("body")}
    col_widths = proportional_col_widths(OPERATIONAL_REPORT_TABLE_WIDTH, [0.30, 0.18, 0.52])
    delivery_val = (
        f"{enriched['delivery_proof_completeness_pct']}%"
        if enriched.get("delivery_proof_completeness_pct") is not None
        else "N/A"
    )
    data = [
        [
            _table_cell_para("Indicator", ent_styles, bold=True),
            _table_cell_para("Value", ent_styles, bold=True),
            _table_cell_para("Operational interpretation", ent_styles, bold=True),
        ],
        [
            _table_cell_para("Evidence completeness", ent_styles),
            _table_cell_para(f"{enriched.get('evidence_completeness_pct', 0)}%", ent_styles),
            _table_cell_para(enriched.get("evidence_completeness_note", ""), ent_styles),
        ],
        [
            _table_cell_para("Delivery proof coverage", ent_styles),
            _table_cell_para(delivery_val, ent_styles),
            _table_cell_para(enriched.get("delivery_proof_note", ""), ent_styles),
        ],
        [
            _table_cell_para("Audit readiness posture", ent_styles),
            _table_cell_para(enriched.get("audit_readiness", "—"), ent_styles),
            _table_cell_para(
                f"Confidence level: {enriched.get('audit_confidence', '—')}",
                ent_styles,
            ),
        ],
        [
            _table_cell_para("Priority exposure", ent_styles),
            _table_cell_para(str(enriched.get("unresolved_evidence_exposure", 0)), ent_styles),
            _table_cell_para(
                "Obligations flagged critical or high for remediation sequencing.",
                ent_styles,
            ),
        ],
    ]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(table_style)
    body: List[Any] = [t, Spacer(1, 6)]
    for line in enriched.get("interpretation_lines") or []:
        body.append(Paragraph(_xml_escape(line), styles["body"]))
    body.append(Spacer(1, 10))
    header = [
        Paragraph("<b>Audit readiness indicators</b>", styles["heading"]),
        Paragraph(
            "Operational view of evidence sufficiency and preparation status at the generation boundary.",
            styles["small"],
        ),
        Spacer(1, 6),
    ]
    elements.append(KeepTogether(header))
    for item in body:
        elements.append(item)


def append_recommended_remediation_section(
    elements: List[Any],
    *,
    actions: Dict[str, List[str]],
    styles: Dict[str, Any],
) -> None:
    body: List[Any] = []
    any_action = False
    for label in ("Priority 1", "Priority 2", "Priority 3"):
        items = actions.get(label) or []
        if not items:
            continue
        any_action = True
        pri_key = label.replace("Priority ", "")
        tbl_data = [[Paragraph(f"<b>{_xml_escape(label)}</b>", styles["body"])]]
        for item in items:
            tbl_data.append([Paragraph(f"• {_xml_escape(item)}", styles["body"])])
        band = Table(tbl_data, colWidths=[170 * mm])
        band.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _PRIORITY_SEVERITY_BG.get(pri_key, colors.white)),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        body.append(band)
        body.append(Spacer(1, 4))
    if not any_action:
        body.append(
            Paragraph(
                "No immediate remediation sequence indicated from export-scope metrics.",
                styles["body"],
            )
        )
    header = [
        Paragraph("<b>Recommended remediation actions</b>", styles["heading"]),
        Paragraph(
            "Prioritised operational steps for audit preparation. Not legal advice — verify requirements independently.",
            styles["small"],
        ),
        Spacer(1, 6),
    ]
    elements.append(KeepTogether(header))
    for item in body:
        elements.append(item)
    elements.append(Spacer(1, 8))


def append_operational_evidence_matrix(
    elements: List[Any],
    *,
    core_rows: List[Dict[str, str]],
    appendix_rows: List[Dict[str, str]],
    styles: Dict[str, Any],
    table_style: TableStyle,
    max_rows: int = 35,
) -> None:
    shown = core_rows[:max_rows]
    ent_styles = styles if styles.get("table_cell") else {**styles, "table_cell": styles.get("body")}
    col_widths = proportional_col_widths(
        OPERATIONAL_REPORT_TABLE_WIDTH,
        [0.28, 0.18, 0.10, 0.14, 0.10, 0.20],
    )
    header = [
        _table_cell_para("Obligation", ent_styles, bold=True),
        _table_cell_para("Status", ent_styles, bold=True),
        _table_cell_para("Evidence", ent_styles, bold=True),
        _table_cell_para("Expiry", ent_styles, bold=True),
        _table_cell_para("Risk", ent_styles, bold=True),
        _table_cell_para("Action required", ent_styles, bold=True),
    ]
    data: List[List[Any]] = [header]
    for row in shown:
        data.append(
            [
                _obligation_cell_para(
                    row.get("obligation") or "—",
                    row.get("category") or "",
                    ent_styles,
                ),
                _table_cell_para(row.get("status") or "—", ent_styles),
                _table_cell_para(row.get("evidence") or "—", ent_styles),
                _table_cell_para(row.get("expiry") or "—", ent_styles),
                _table_cell_para(row.get("risk") or "—", ent_styles),
                _table_cell_para(row.get("action_required") or "—", ent_styles),
            ]
        )
    t = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    t.setStyle(table_style)
    for i, row in enumerate(shown, start=1):
        _risk_row_style(t, i, row.get("risk") or "")
    omitted = max(0, len(core_rows) - len(shown))
    intro = (
        "Core obligation view for rapid triage — status, evidence, expiry, and required action. "
        "Detailed references appear in the metadata appendix when present."
    )
    if omitted:
        intro += f" Showing {len(shown)} of {len(core_rows)} obligations."
    header_block = [
        Paragraph("<b>Operational evidence matrix</b>", styles["heading"]),
        Paragraph(intro, styles["small"]),
        Spacer(1, 6),
    ]
    elements.append(KeepTogether(header_block))
    elements.append(t)
    elements.append(Spacer(1, 8))

    if appendix_rows and shown:
        app_shown = appendix_rows[: len(shown)]
        app_header = [
            _table_cell_para("Obligation", ent_styles, bold=True),
            _table_cell_para("Category", ent_styles, bold=True),
            _table_cell_para("File ref", ent_styles, bold=True),
            _table_cell_para("Delivery", ent_styles, bold=True),
            _table_cell_para("Updated", ent_styles, bold=True),
        ]
        app_data: List[List[Any]] = [app_header]
        for row in app_shown:
            app_data.append(
                [
                    _table_cell_para(row.get("obligation") or "—", ent_styles),
                    _table_cell_para(row.get("category") or "—", ent_styles),
                    _table_cell_para(row.get("file_ref") or "—", ent_styles),
                    _table_cell_para(row.get("delivery") or "—", ent_styles),
                    _table_cell_para(row.get("updated") or "—", ent_styles),
                ]
            )
        app_col = proportional_col_widths(
            OPERATIONAL_REPORT_TABLE_WIDTH,
            [0.30, 0.16, 0.22, 0.14, 0.18],
        )
        app_t = Table(app_data, colWidths=app_col, repeatRows=1, splitByRow=1)
        app_t.setStyle(table_style)
        elements.append(
            KeepTogether(
                [
                    Paragraph("<b>Reference metadata appendix</b>", styles.get("subheading") or styles["heading"]),
                    Paragraph("Secondary fields for audit preparation cross-check.", styles["small"]),
                    Spacer(1, 4),
                ]
            )
        )
        elements.append(app_t)
    elements.append(Spacer(1, 10))


def append_operational_action_priorities(
    elements: List[Any],
    *,
    groups: Dict[str, List[str]],
    styles: Dict[str, Any],
) -> None:
    body: List[Any] = []
    for pri in ACTION_PRIORITIES:
        items = groups.get(pri) or []
        if not items:
            continue
        rows = [[Paragraph(f"<b>{_xml_escape(pri)}</b>", styles["body"])]]
        for item in items[:10]:
            rows.append([Paragraph(f"• {_xml_escape(item)}", styles["body"])])
        band = Table(rows, colWidths=[170 * mm])
        band.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _PRIORITY_SEVERITY_BG.get(pri, colors.white)),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        body.append(band)
        body.append(Spacer(1, 6))
    if not body:
        body.append(Paragraph("No priority groupings in export scope.", styles["body"]))
    header = [
        Paragraph("<b>Action priority summary</b>", styles["heading"]),
        Paragraph("Grouped obligations by urgency for internal review sequencing.", styles["small"]),
        Spacer(1, 6),
    ]
    elements.append(KeepTogether(header))
    for item in body:
        elements.append(item)
    elements.append(Spacer(1, 8))


def append_operational_audit_trail(
    elements: List[Any],
    *,
    grouped_events: Dict[str, List[Dict[str, Any]]],
    styles: Dict[str, Any],
    table_style: TableStyle,
) -> None:
    if not grouped_events:
        return
    header = [
        Paragraph("<b>Operational activity chronology</b>", styles["heading"]),
        Paragraph(
            "Grouped system activity for audit preparation. Raw event codes are normalised for readability.",
            styles["small"],
        ),
        Spacer(1, 6),
    ]
    elements.append(KeepTogether(header))
    for family, items in grouped_events.items():
        if not items:
            continue
        elements.append(Paragraph(f"<b>{_xml_escape(family)}</b>", styles.get("subheading") or styles["heading"]))
        ent_styles = styles if styles.get("table_cell") else {**styles, "table_cell": styles.get("body")}
        col_widths = proportional_col_widths(
            OPERATIONAL_REPORT_TABLE_WIDTH,
            [0.18, 0.22, 0.14, 0.46],
        )
        data = [
            [
                _table_cell_para("When (UTC)", ent_styles, bold=True),
                _table_cell_para("Activity", ent_styles, bold=True),
                _table_cell_para("Actor", ent_styles, bold=True),
                _table_cell_para("Summary", ent_styles, bold=True),
            ]
        ]
        for ev in items:
            label = ev.get("human_label") or "—"
            similar = ev.get("similar_count")
            if similar and similar > 1:
                label = f"{label} (+{similar - 1} similar)"
            data.append(
                [
                    _table_cell_para(
                        str(ev.get("timestamp") or "\u2014")
                        .replace("T", " ", 1)
                        .replace("+00:00", " UTC")
                        .replace("Z", " UTC"),
                        ent_styles,
                    ),
                    _table_cell_para(label, ent_styles),
                    _table_cell_para(_human_actor_role(ev.get("actor_role")), ent_styles),
                    _table_cell_para(str(ev.get("summary") or "—"), ent_styles),
                ]
            )
        ft = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
        ft.setStyle(table_style)
        elements.append(ft)
        elements.append(Spacer(1, 8))


def append_operational_governance_once(
    elements: List[Any],
    *,
    generated_at_iso: str,
    styles: Dict[str, Any],
) -> None:
    """Brief cover triage note — determinism footer is canvas-only."""
    del generated_at_iso
    elements.append(
        Paragraph(
            "Operational audit-readiness export for triage and remediation sequencing. "
            "Generation boundary and determinism notices appear in the page footer.",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 10))


def append_evidence_readiness_operational_sections(
    elements: List[Any],
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client: dict,
    now: datetime,
    styles: Dict[str, Any],
    property_filter_id: Optional[str] = None,
    audit_logs: Optional[List[dict]] = None,
    header_bg: Any = None,
) -> None:
    """Orchestrate operational audit-readiness sections for Evidence Readiness PDFs."""
    from services.report_pdf_templates import (
        append_exception_summaries_section,
        append_intended_use_section,
        classify_exceptions,
        create_enterprise_styles,
        create_enterprise_table_style,
        group_by_action_priority,
    )

    ent_styles = create_enterprise_styles({})
    table_style = create_operational_table_style(ent_styles.get("table_header_bg"))
    ent_style = create_enterprise_table_style(ent_styles)

    append_operational_governance_once(elements, generated_at_iso=now.isoformat(), styles=styles)
    append_intended_use_section(elements, report_kind="evidence_readiness", styles=styles)

    readiness = compute_readiness_indicators(
        requirements=requirements,
        properties=properties,
        client_doc=client,
        now=now,
    )
    append_operational_readiness_section(
        elements, indicators=readiness, styles=styles, table_style=ent_style
    )

    core_rows, appendix_rows = build_operational_matrix_rows(
        requirements=requirements,
        properties=properties,
        client_doc=client,
        now=now,
        property_filter_id=property_filter_id,
    )
    full_matrix = build_matrix_rows(
        requirements=requirements,
        properties=properties,
        client_doc=client,
        now=now,
        property_filter_id=property_filter_id,
    )
    remediation = build_recommended_remediation_actions(full_matrix, now=now)
    append_recommended_remediation_section(elements, actions=remediation, styles=styles)

    append_operational_evidence_matrix(
        elements,
        core_rows=core_rows,
        appendix_rows=appendix_rows,
        styles=styles,
        table_style=table_style,
    )

    exceptions = classify_exceptions(
        requirements=requirements,
        properties=properties,
        client_doc=client,
        now=now,
    )
    append_exception_summaries_section(
        elements, exceptions=exceptions, styles=styles, table_style=ent_style
    )

    append_operational_action_priorities(
        elements,
        groups=group_by_action_priority(full_matrix),
        styles=styles,
    )

    if audit_logs:
        grouped = group_audit_events_for_operational_report(
            [
                {
                    "timestamp": log.get("timestamp"),
                    "action": log.get("action"),
                    "actor_role": log.get("actor_role"),
                    "resource_id": log.get("resource_id"),
                    "metadata": log.get("metadata") if isinstance(log.get("metadata"), dict) else {},
                }
                for log in audit_logs
            ]
        )
        append_operational_audit_trail(
            elements, grouped_events=grouped, styles=styles, table_style=table_style
        )
