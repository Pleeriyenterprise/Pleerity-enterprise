"""
Compliance Summary Report — executive posture presentation layer.

Professional portfolio compliance overview for landlords, insurers, lenders,
solicitors, and senior portfolio managers. Distinct from Requirements triage,
Evidence Readiness remediation, Monthly Digest intelligence, and Audit Pack archives.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape as _xml_escape

from services.report_human_language_v1 import (
    human_compliance_status_label,
    human_operational_renewal_date,
)
from services.report_layout_governance import formal_report_table_width, proportional_col_widths
from services.report_pdf_templates import (
    _human_status_label,
    _table_cell_para,
    append_section_block,
)
from utils.expiry_utils import get_computed_status

COMPLIANCE_SUMMARY_REPORT_TITLE = "Compliance Summary Report"
CSV_FORMAT_VERSION = "compliance_summary_executive_v1"

CONDENSED_MATRIX_MAX = 12
PROPERTY_POSTURE_MAX = 20
RECOMMENDATION_MAX = 6

# Executive wording — must not mirror Requirements Report triage labels
_FORBIDDEN_TRIAGE_PHRASES = frozenset(
    {
        "immediate attention",
        "triage at a glance",
        "operational triage",
        "upcoming renewals",
        "evidence review required",
        "monitoring only",
    }
)

_LEAK_RE = re.compile(
    r"\b(UNKNOWN_DATE|SELF_RECORDED|SATISFIED_UNVERIFIED|workflow_class|evidence_state)\b",
    re.I,
)

_EXPOSURE_THEMES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Fire safety", ("gas", "fire", "smoke", "emergency lighting", "alarm")),
    ("Licensing", ("licence", "license", "hmo", "selective", "registration")),
    ("Tenancy documentation", ("tenancy", "deposit", "right to rent", "contract")),
    ("Evidence verification", ("review", "verify", "upload", "certificate", "epc", "eicr")),
    ("Onboarding", ("onboarding", "initial", "setup")),
    ("Renewal scheduling", ("renewal", "expir")),
)

_STATUS_HUMAN = {
    "GREEN": "Favourable posture",
    "AMBER": "Attention advised",
    "RED": "Elevated attention",
    "UNKNOWN": "Status under review",
}


def portfolio_material_exposure(
    *,
    overdue: int,
    missing_evidence: int,
    counts: Dict[str, int],
    readiness: Dict[str, Any],
    risk_concentration: List[Dict[str, Any]],
) -> bool:
    """True when export-scope metrics show overdue, missing evidence, or elevated exposure."""
    pending = int(counts.get("pending") or 0)
    if int(overdue or 0) + int(missing_evidence or 0) + pending > 0:
        return True
    if int(readiness.get("unresolved_evidence_exposure") or 0) > 0:
        return True
    if any(int(c.get("unresolved") or 0) > 0 for c in risk_concentration):
        return True
    return False


def human_property_dashboard_status(
    raw: Optional[str],
    *,
    stats: Optional[Dict[str, Any]] = None,
) -> str:
    """Dashboard posture label — scoped to property stats, not a legal compliance determination."""
    stats = stats or {}
    overdue = int(stats.get("overdue") or 0)
    missing = int(stats.get("missing_evidence") or 0)
    expiring = int(stats.get("expiring_soon") or 0)
    if overdue > 0:
        return "Elevated attention" if overdue >= 2 else "Attention advised"
    if missing > 0:
        return "Attention advised"
    if expiring > 0:
        return "Attention advised"
    key = str(raw or "UNKNOWN").strip().upper()
    return _STATUS_HUMAN.get(key, "Status under review")


def _property_readiness_label(*, overdue: int, missing: int) -> str:
    """Property-scoped readiness — not derived from portfolio-level confidence."""
    unresolved = overdue + missing
    if unresolved == 0:
        return "Strong"
    if unresolved <= 2:
        return "Adequate with review"
    return "Review recommended"


def assert_executive_safe_text(text: str) -> None:
    t = (text or "").strip()
    if not t:
        return
    if _LEAK_RE.search(t):
        raise ValueError(f"backend leak in compliance summary: {t[:80]!r}")
    low = t.lower()
    for phrase in _FORBIDDEN_TRIAGE_PHRASES:
        if phrase in low:
            raise ValueError(f"requirements triage leak in compliance summary: {phrase!r}")
    from services.vocabulary_contract_v1 import assert_semantic_safe_text

    assert_semantic_safe_text(t, context="compliance_summary_executive", allow_stale=True)


def classify_exposure_theme(row: Dict[str, Any]) -> str:
    blob = " ".join(
        str(row.get(k) or "") for k in ("description", "requirement_type", "category", "obligation")
    ).lower()
    for label, keywords in _EXPOSURE_THEMES:
        if any(kw in blob for kw in keywords):
            return label
    return "General compliance"


def humanize_matrix_row(row: Dict[str, str]) -> Dict[str, str]:
    out = dict(row)
    st = str(row.get("status") or "")
    if st and st.upper() not in ("—", "N/A"):
        out["status"] = human_compliance_status_label(st.upper()) or st
    expiry_display = row.get("expiry_display")
    if expiry_display and expiry_display not in ("—", ""):
        out["expiry"] = expiry_display
    elif row.get("expiry") not in (None, "—", ""):
        out["expiry"] = human_operational_renewal_date({"due_date": row.get("expiry")})
    else:
        out["expiry"] = "—"
    for v in out.values():
        if isinstance(v, str):
            assert_executive_safe_text(v)
    return out


def _matrix_priority_score(row: Dict[str, str]) -> int:
    risk = str(row.get("risk_level") or "")
    action = str(row.get("action_required") or "")
    pri = str(row.get("priority") or "")
    score = 0
    if risk == "Critical":
        score += 100
    elif risk == "High":
        score += 80
    elif pri in ("Critical", "High"):
        score += 70
    if action == "Yes":
        score += 50
    elif action == "Review":
        score += 30
    st = str(row.get("status") or "").lower()
    if "overdue" in st or "expired" in st:
        score += 40
    if "renewal" in st or "expiring" in st:
        score += 25
    return score


def select_condensed_matrix_rows(matrix_rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], int]:
    """Highest-value obligations for executive evidence summary — not full registry dump."""
    ranked = sorted(matrix_rows, key=_matrix_priority_score, reverse=True)
    high_value = [r for r in ranked if _matrix_priority_score(r) >= 25]
    if not high_value:
        high_value = ranked[:CONDENSED_MATRIX_MAX]
    shown = high_value[:CONDENSED_MATRIX_MAX]
    omitted = max(0, len(matrix_rows) - len(shown))
    return [humanize_matrix_row(r) for r in shown], omitted


def build_portfolio_risk_concentration(
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: dict,
) -> List[Dict[str, Any]]:
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    by_theme: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "properties": set(), "unresolved": 0})
    for r in requirements:
        theme = classify_exposure_theme(r)
        pd = pmap.get(r.get("property_id"))
        cs = (get_computed_status(r, property_doc=pd, client_doc=client_doc) or "").upper()
        by_theme[theme]["count"] += 1
        if r.get("property_id"):
            by_theme[theme]["properties"].add(str(r.get("property_id")))
        if cs in ("OVERDUE", "EXPIRED", "MISSING", "PENDING", "ACTION_REQUIRED"):
            by_theme[theme]["unresolved"] += 1
    out = []
    for theme, data in sorted(by_theme.items(), key=lambda x: (-x[1]["unresolved"], -x[1]["count"], x[0])):
        n = data["count"]
        props = len(data["properties"])
        unresolved = data["unresolved"]
        if unresolved:
            line = (
                f"{theme}: {unresolved} unresolved obligation{'s' if unresolved != 1 else ''} "
                f"across {props} propert{'ies' if props != 1 else 'y'}."
            )
        elif n:
            line = (
                f"{theme}: {n} obligation{'s' if n != 1 else ''} in scope — "
                "no overdue or missing-evidence items in this theme at the report date."
            )
        else:
            continue
        assert_executive_safe_text(line)
        out.append({"theme": theme, "count": n, "properties": props, "unresolved": unresolved, "summary": line})
    return out[:8]


def build_executive_interpretation(
    *,
    counts: Dict[str, int],
    readiness: Dict[str, Any],
    risk_concentration: List[Dict[str, Any]],
    overdue: int,
    missing_evidence: int,
    expiring: int,
    completion_pct: int,
    total_reqs: int,
) -> List[str]:
    lines: List[str] = []
    material = portfolio_material_exposure(
        overdue=overdue,
        missing_evidence=missing_evidence,
        counts=counts,
        readiness=readiness,
        risk_concentration=risk_concentration,
    )
    if total_reqs > 0:
        lines.append(
            f"In this report, {completion_pct}% of {total_reqs} obligations show operationally "
            "compliant status at the report date — distinct from the CVP headline score above and "
            "not a legal compliance determination."
        )
    top = [r for r in risk_concentration if r.get("unresolved", 0) > 0]
    if top:
        themes = ", ".join(r["theme"].lower() for r in top[:3])
        lines.append(
            f"Most unresolved exposure is concentrated in {themes}."
        )
    conf = str(readiness.get("audit_confidence") or "")
    if conf == "High" and material:
        lines.append(
            "Portfolio audit readiness is broadly sound, though exposure in this report still warrants "
            "professional review of detail sections."
        )
    elif conf == "High":
        lines.append(
            "Portfolio audit readiness remains substantially strong at the report date."
        )
    elif conf == "Medium":
        lines.append(
            "Portfolio audit readiness is broadly sound with limited exceptions requiring professional review."
        )
    elif conf == "Low":
        lines.append(
            "Portfolio audit readiness shows material gaps that may affect third-party review confidence."
        )
    if overdue > missing_evidence and overdue > 0:
        lines.append("Operational exposure is currently driven more by overdue renewals than missing evidence.")
    elif missing_evidence > overdue and missing_evidence > 0:
        lines.append("Operational exposure is currently driven more by evidence confidence gaps than calendar overdue items.")
    elif expiring > 0 and overdue == 0:
        lines.append("Near-term attention is primarily renewal scheduling rather than overdue failure.")
    if not lines:
        if material:
            lines.append(
                "Operational exposure remains in this report — review detail sections for overdue items, "
                "evidence gaps, and renewal scheduling before relying on headline posture alone."
            )
        else:
            lines.append(
                "No material compliance posture concerns were detected in this report at the report date."
            )
    for ln in lines:
        assert_executive_safe_text(ln)
    return lines[:4]


def build_grouped_executive_recommendations(
    risk_concentration: List[Dict[str, Any]],
    *,
    expiring: int,
    missing_evidence: int,
) -> List[str]:
    recs: List[str] = []
    for item in risk_concentration:
        if item.get("unresolved", 0) <= 0:
            continue
        theme = item["theme"]
        props = item.get("properties", 0)
        n = item.get("unresolved", 0)
        if props > 1:
            recs.append(
                f"Prioritise {theme.lower()} across {props} properties ({n} unresolved items in scope)."
            )
        else:
            recs.append(f"Address {theme.lower()} exposure ({n} item{'s' if n != 1 else ''} in scope).")
        if len(recs) >= RECOMMENDATION_MAX:
            break
    if expiring > 0 and len(recs) < RECOMMENDATION_MAX:
        recs.append(f"Schedule renewal evidence for {expiring} obligation{'s' if expiring != 1 else ''} approaching expiry.")
    if missing_evidence > 0 and len(recs) < RECOMMENDATION_MAX:
        recs.append(
            f"Strengthen evidence on file for {missing_evidence} obligation{'s' if missing_evidence != 1 else ''} "
            "where confirmation or upload is still required."
        )
    for r in recs:
        assert_executive_safe_text(r)
    return recs[:RECOMMENDATION_MAX]


def build_property_posture_rows(
    *,
    properties: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
    client_doc: dict,
    readiness: Dict[str, Any],
) -> List[Dict[str, str]]:
    from services.requirement_client_runtime_surface import compute_client_portal_requirement_stats

    pmap_reqs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in requirements:
        pid = r.get("property_id")
        if pid:
            pmap_reqs[str(pid)].append(r)

    rows: List[Dict[str, str]] = []
    for prop in properties[:PROPERTY_POSTURE_MAX]:
        pid = str(prop.get("property_id") or "")
        prop_reqs = pmap_reqs.get(pid, [])
        stats = compute_client_portal_requirement_stats(prop_reqs) if prop_reqs else {}
        themes: Dict[str, int] = defaultdict(int)
        for r in prop_reqs:
            pd = prop
            cs = (get_computed_status(r, property_doc=pd, client_doc=client_doc) or "").upper()
            if cs in ("OVERDUE", "EXPIRED", "MISSING", "PENDING"):
                themes[classify_exposure_theme(r)] += 1
        key_theme = max(themes.items(), key=lambda x: x[1])[0] if themes else "Routine monitoring"
        if stats.get("overdue", 0):
            concern = f"{stats.get('overdue', 0)} overdue; {key_theme.lower()}"
        elif stats.get("expiring_soon", 0):
            concern = f"{stats.get('expiring_soon', 0)} renewal{'s' if stats.get('expiring_soon', 0) != 1 else ''} approaching"
        elif stats.get("missing_evidence", 0):
            concern = f"Evidence confidence — {key_theme.lower()}"
        else:
            concern = "Routine monitoring in scope"

        overdue_n = int(stats.get("overdue", 0) or 0)
        missing_n = int(stats.get("missing_evidence", 0) or 0)
        unresolved = overdue_n + missing_n
        readiness_label = _property_readiness_label(overdue=overdue_n, missing=missing_n)

        addr = ", ".join(x for x in [prop.get("address_line_1"), prop.get("postcode")] if x)[:48]
        row = {
            "property_id": pid,
            "property": addr or pid[:20],
            "status": human_property_dashboard_status(prop.get("compliance_status"), stats=stats),
            "key_concern": concern[:42],
            "readiness": readiness_label,
            "unresolved_count": str(unresolved),
            "expiring_count": str(stats.get("expiring_soon", 0)),
        }
        for v in row.values():
            assert_executive_safe_text(v)
        rows.append(row)
    return rows


def enrich_readiness_narrative(readiness: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(readiness)
    notes: List[str] = []
    pct = int(readiness.get("evidence_completeness_pct") or 0)
    if pct >= 90:
        notes.append("Evidence on file is broadly complete; gaps are limited and identifiable.")
    elif pct >= 70:
        notes.append("Evidence completeness is moderate — targeted strengthening may improve review confidence.")
    else:
        notes.append("Evidence completeness is limited — professional review may require additional documentation.")
    exp = int(readiness.get("unresolved_evidence_exposure") or 0)
    if exp == 0:
        notes.append(
            "No elevated-priority evidence exposure identified in readiness scoring at the report date."
        )
    else:
        notes.append(
            f"{exp} obligation{'s' if exp != 1 else ''} carry elevated evidence or renewal exposure."
        )
    out["executive_notes"] = notes
    return out


def build_compliance_summary_executive_model(
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    matrix_rows: List[Dict[str, str]],
    readiness: Dict[str, Any],
    counts: Dict[str, int],
    total_props: int,
    green: int,
    amber: int,
    red: int,
) -> Dict[str, Any]:
    client = client_doc or {}
    enriched_readiness = enrich_readiness_narrative(readiness)
    risk_concentration = build_portfolio_risk_concentration(requirements, properties, client)
    overdue = int(counts.get("overdue") or 0)
    missing = int(counts.get("missing_evidence") or 0)
    expiring = int(counts.get("expiring_soon") or 0)
    compliant = int(counts.get("compliant") or 0)
    total_reqs = int(counts.get("total_requirements") or 0)
    completion_pct = round((compliant / total_reqs * 100) if total_reqs else 0)
    interpretation = build_executive_interpretation(
        counts=counts,
        readiness=enriched_readiness,
        risk_concentration=risk_concentration,
        overdue=overdue,
        missing_evidence=missing,
        expiring=expiring,
        completion_pct=completion_pct,
        total_reqs=total_reqs,
    )
    recommendations = build_grouped_executive_recommendations(
        risk_concentration, expiring=expiring, missing_evidence=missing
    )
    property_rows = build_property_posture_rows(
        properties=properties,
        requirements=requirements,
        client_doc=client,
        readiness=enriched_readiness,
    )
    condensed, matrix_omitted = select_condensed_matrix_rows(matrix_rows)

    model = {
        "interpretation": interpretation,
        "readiness": enriched_readiness,
        "risk_concentration": risk_concentration,
        "recommendations": recommendations,
        "property_posture": property_rows,
        "condensed_matrix": condensed,
        "matrix_omitted": matrix_omitted,
        "matrix_total": len(matrix_rows),
        "portfolio_metrics": {
            "properties": total_props,
            "on_track": green,
            "attention": amber,
            "elevated": red,
            "obligations_in_scope": total_reqs,
            "completion_rate_pct": completion_pct,
            "overdue": overdue,
            "expiring": expiring,
            "missing_evidence": missing,
        },
    }
    if counts.get("lifecycle_kpi_breakdown"):
        model["lifecycle_kpi_breakdown"] = counts["lifecycle_kpi_breakdown"]
        model["lifecycle_kpi_effective_mode"] = counts.get("lifecycle_kpi_effective_mode")
    return model


def append_lifecycle_kpi_breakdown_report_section(
    elements: List[Any],
    *,
    model: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: TableStyle,
) -> None:
    """Supplemental lifecycle attention breakdown (P5-S6) — presentation only."""
    from services.lifecycle_kpi_gates import (
        lifecycle_kpi_breakdown_report_entries,
        lifecycle_kpi_report_framing_note,
    )

    breakdown = model.get("lifecycle_kpi_breakdown")
    entries = lifecycle_kpi_breakdown_report_entries(breakdown)
    if not entries:
        return
    mode = model.get("lifecycle_kpi_effective_mode")
    framing = lifecycle_kpi_report_framing_note(mode)
    table_width = formal_report_table_width()
    col_widths = proportional_col_widths(table_width, [0.55, 0.45])
    rows = [
        [
            _table_cell_para("Lifecycle attention category", styles, bold=True),
            _table_cell_para("Count", styles, bold=True),
        ]
    ]
    for label, count in entries:
        rows.append(
            [
                _table_cell_para(label, styles),
                _table_cell_para(str(count), styles),
            ]
        )
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(table_style)
    intro = (
        framing
        or "Lifecycle categorisation by attention kind (supplemental to headline KPI totals)."
    )
    append_section_block(
        elements,
        title="Lifecycle attention breakdown",
        intro=intro,
        styles=styles,
        body_items=[tbl, Spacer(1, 10)],
    )


def append_compliance_summary_executive_sections(
    elements: List[Any],
    *,
    model: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: TableStyle,
) -> None:
    from services.report_interpretation_v1 import append_how_to_read_pdf_section, audit_readiness_scope_note

    append_how_to_read_pdf_section(elements, report_class="compliance_summary", styles=styles)

    append_lifecycle_kpi_breakdown_report_section(
        elements,
        model=model,
        styles=styles,
        table_style=table_style,
    )

    metrics = model.get("portfolio_metrics") or {}
    interp = model.get("interpretation") or []
    append_section_block(
        elements,
        title="Portfolio posture interpretation",
        intro="Executive synthesis of compliance posture at the report date — not a legal determination.",
        styles=styles,
        body_items=[Paragraph(f"• {_xml_escape(line)}", styles["body"]) for line in interp]
        + [Spacer(1, 10)],
    )

    readiness = model.get("readiness") or {}
    table_width = formal_report_table_width()
    rd_widths = proportional_col_widths(table_width, [0.30, 0.18, 0.52])
    rd = [
        [
            _table_cell_para("Indicator", styles, bold=True),
            _table_cell_para("Value", styles, bold=True),
            _table_cell_para("Professional interpretation", styles, bold=True),
        ],
        [
            _table_cell_para("Evidence completeness", styles),
            _table_cell_para(f"{readiness.get('evidence_completeness_pct', 0)}%", styles),
            _table_cell_para(readiness.get("evidence_completeness_note", ""), styles),
        ],
        [
            _table_cell_para("Audit readiness posture", styles),
            _table_cell_para(readiness.get("audit_readiness", "—"), styles),
            _table_cell_para(
                f"{audit_readiness_scope_note(readiness.get('audit_readiness'))} "
                f"Confidence level: {readiness.get('audit_confidence', '—')}".strip(),
                styles,
            ),
        ],
        [
            _table_cell_para("Priority exposure", styles),
            _table_cell_para(str(readiness.get("unresolved_evidence_exposure", 0)), styles),
            _table_cell_para("Elevated-priority obligations at the report date.", styles),
        ],
    ]
    rt = Table(rd, colWidths=rd_widths, repeatRows=1)
    rt.setStyle(table_style)
    notes = readiness.get("executive_notes") or []
    body: List[Any] = [rt, Spacer(1, 6)]
    for n in notes:
        body.append(Paragraph(_xml_escape(n), styles["small"]))
    body.append(Spacer(1, 10))
    append_section_block(
        elements,
        title="Audit readiness and evidence confidence",
        intro="Readiness reflects evidence sufficiency — missing items are not automatically treated as non-compliance.",
        styles=styles,
        body_items=body,
    )

    concentration = model.get("risk_concentration") or []
    if concentration:
        append_section_block(
            elements,
            title="Where portfolio exposure is concentrated",
            intro="Operational themes with the greatest concentration of obligations or unresolved exposure.",
            styles=styles,
            body_items=[
                Paragraph(f"• {_xml_escape(c.get('summary', ''))}", styles["body"]) for c in concentration
            ]
            + [Spacer(1, 10)],
        )

    props = model.get("property_posture") or []
    if props:
        pt_widths = proportional_col_widths(table_width, [0.28, 0.16, 0.34, 0.22])
        pdata = [
            [
                _table_cell_para("Property", styles, bold=True),
                _table_cell_para("Status", styles, bold=True),
                _table_cell_para("Key concern", styles, bold=True),
                _table_cell_para("Readiness", styles, bold=True),
            ]
        ]
        for p in props:
            pdata.append(
                [
                    _table_cell_para(p["property"], styles),
                    _table_cell_para(p["status"], styles),
                    _table_cell_para(p["key_concern"], styles),
                    _table_cell_para(p["readiness"], styles),
                ]
            )
        pt = Table(pdata, colWidths=pt_widths, repeatRows=1, splitByRow=1)
        pt.setStyle(table_style)
        append_section_block(
            elements,
            title="Property posture overview",
            intro="Compact operational posture per property — not a full obligation matrix.",
            styles=styles,
            body_items=[pt, Spacer(1, 10)],
        )

    recs = model.get("recommendations") or []
    if recs:
        append_section_block(
            elements,
            title="Recommended priorities",
            intro="Portfolio-level guidance for professional review — grouped by operational theme.",
            styles=styles,
            body_items=[Paragraph(f"• {_xml_escape(r)}", styles["body"]) for r in recs] + [Spacer(1, 10)],
        )

    condensed = model.get("condensed_matrix") or []
    omitted = int(model.get("matrix_omitted") or 0)
    if condensed:
        mt_widths = proportional_col_widths(
            table_width,
            [0.30, 0.14, 0.12, 0.16, 0.12, 0.16],
        )
        mdata = [
            [
                _table_cell_para("Obligation", styles, bold=True),
                _table_cell_para("Status", styles, bold=True),
                _table_cell_para("Evidence", styles, bold=True),
                _table_cell_para("Expiry", styles, bold=True),
                _table_cell_para("Risk", styles, bold=True),
                _table_cell_para("Action", styles, bold=True),
            ]
        ]
        for raw in condensed:
            r = humanize_matrix_row(raw)
            mdata.append(
                [
                    _table_cell_para(r.get("obligation") or "—", styles),
                    _table_cell_para(_human_status_label(r.get("status")), styles),
                    _table_cell_para(r.get("evidence_present") or "—", styles),
                    _table_cell_para(r.get("expiry") or "—", styles),
                    _table_cell_para(r.get("risk_level") or "—", styles),
                    _table_cell_para(r.get("action_required") or "—", styles),
                ]
            )
        mt = Table(mdata, colWidths=mt_widths, repeatRows=1, splitByRow=1)
        mt.setStyle(table_style)
        intro = (
            f"Summary of highest-value obligations ({len(condensed)} shown). "
            "Full obligation detail remains available in the portal."
        )
        if omitted:
            intro += f" {omitted} additional obligations omitted from this summary."
        items: List[Any] = [
            mt,
            Paragraph(
                "Recorded items are not automatically equivalent to independent verification.",
                styles["small"],
            ),
            Spacer(1, 10),
        ]
        append_section_block(
            elements,
            title="Evidence summary",
            intro=intro,
            styles=styles,
            body_items=items,
        )


CSV_PROPERTY_FIELDS = [
    "property",
    "posture",
    "primary_risk_area",
    "readiness",
    "unresolved_count",
    "expiring_count",
    "evidence_confidence",
    "next_action",
]


def build_compliance_summary_executive_csv_rows(
    *,
    properties: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    readiness: Dict[str, Any],
) -> List[Dict[str, str]]:
    posture_rows = build_property_posture_rows(
        properties=properties,
        requirements=requirements,
        client_doc=client_doc,
        readiness=readiness,
    )
    pmap_reqs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in requirements:
        pid = r.get("property_id")
        if pid:
            pmap_reqs[str(pid)].append(r)

    out: List[Dict[str, str]] = []
    for pr in posture_rows:
        pid = str(pr.get("property_id") or "")
        prop_reqs = pmap_reqs.get(pid, [])
        themes = [classify_exposure_theme(r) for r in prop_reqs]
        primary = max(set(themes), key=themes.count) if themes else "General compliance"
        conf = (
            "Strong"
            if pr["readiness"] == "Strong"
            else "Review suggested"
            if "Review" in pr["readiness"]
            else "Adequate"
        )
        action = (
            pr["key_concern"]
            if pr["key_concern"] != "Routine monitoring in scope"
            else "Continue routine monitoring"
        )
        row = {
            "property": pr["property"],
            "posture": pr["status"],
            "primary_risk_area": primary,
            "readiness": pr["readiness"],
            "unresolved_count": pr["unresolved_count"],
            "expiring_count": pr["expiring_count"],
            "evidence_confidence": conf,
            "next_action": action[:64],
        }
        from services.report_human_language_v1 import sanitize_customer_export_text

        for key, val in list(row.items()):
            if isinstance(val, str):
                row[key] = sanitize_customer_export_text(val)
        out.append(row)
    return out


def collect_all_executive_text(model: Dict[str, Any]) -> List[str]:
    texts: List[str] = list(model.get("interpretation") or [])
    texts.extend(model.get("recommendations") or [])
    for c in model.get("risk_concentration") or []:
        texts.append(c.get("summary") or "")
    for p in model.get("property_posture") or []:
        texts.extend(p.values())
    for m in model.get("condensed_matrix") or []:
        texts.extend(m.values())
    rd = model.get("readiness") or {}
    texts.extend(rd.get("executive_notes") or [])
    return [t for t in texts if t]
