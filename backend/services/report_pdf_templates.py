"""
Enterprise formal report PDF templates — regulator-ready presentation layer.

Reusable cover, evidence matrix, executive summary, audit trail, and governance sections.
Preserves deterministic snapshot semantics and restrained enterprise styling.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape as _xml_escape

from services.report_branding_layout import append_report_cover_block
from services.report_layout_governance import (
    GovernancePdfContext,
    export_disclosure_paragraphs,
    formal_report_table_width,
    governance_footer_bottom_margin,
    make_page_callbacks,
    proportional_col_widths,
    utc_display,
)
from utils.expiry_utils import get_computed_status, get_effective_expiry_date

BRAND_MIDNIGHT = "#0B1D3A"
BRAND_TEAL = "#00B8A9"
PLEERITY_OPERATOR = "Pleerity Enterprise Ltd"
PLEERITY_WEBSITE = "pleerityenterprise.co.uk"
PLEERITY_SUPPORT = "info@pleerityenterprise.co.uk"

FROZEN_SNAPSHOT_WORDING = (
    "This report is a frozen deterministic snapshot generated from system records "
    "available as at the generation timestamp boundary."
)

INTENDED_USE: Dict[str, str] = {
    "audit_evidence_pack": (
        "Intended for evidentiary review, dispute support, council, insurer, solicitor, "
        "lender, tribunal, and internal governance. Not tenant email delivery."
    ),
    "compliance_summary": (
        "Intended for client-facing portfolio or property compliance overview and "
        "professional third-party review where a summary posture is required."
    ),
    "evidence_readiness": (
        "Intended for identifying evidence gaps, expiry risk, delivery proof exposure, "
        "and action priorities ahead of audit or regulatory review."
    ),
    "audit_trail": (
        "Intended as a readable chronological record of system events supporting "
        "evidentiary review and governance audit."
    ),
}

LEGAL_LIMITATION = (
    "This report does not constitute legal advice. Evidence and compliance conclusions "
    "remain subject to independent verification of source documents, issuing authorities, "
    "and applicable external registries."
)

ACTION_PRIORITIES = ("Critical", "High", "Medium", "Informational")


@dataclass
class FormalReportSpec:
    report_title: str
    report_classification: str
    report_kind: str
    branding: Dict[str, Any]
    gov_ctx: GovernancePdfContext
    generated_at_iso: str
    jurisdiction: str = ""
    scope_line: str = ""
    account_line: str = ""
    export_id: str = ""
    export_generation_id: str = ""
    extra_cover_lines: List[str] = field(default_factory=list)
    include_matrix: bool = True
    include_executive_summary: bool = True
    include_readiness_indicators: bool = True
    include_action_priorities: bool = True
    include_exception_summaries: bool = True
    include_audit_trail: bool = False
    include_intended_use: bool = True
    include_scope_limitations: bool = True


def _hex_color(hex_str: str) -> colors.Color:
    h = (hex_str or BRAND_MIDNIGHT).lstrip("#")
    return colors.HexColor(f"#{h}")


def create_enterprise_styles(branding: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    branding = branding or {}
    primary = branding.get("primary_color") or BRAND_MIDNIGHT
    accent = branding.get("accent_color") or BRAND_TEAL
    base = getSampleStyleSheet()
    c_primary = _hex_color(primary)
    c_accent = _hex_color(accent)
    return {
        "title": ParagraphStyle(
            "EntTitle",
            parent=base["Title"],
            fontSize=20,
            textColor=c_primary,
            spaceAfter=10,
            leading=24,
        ),
        "heading": ParagraphStyle(
            "EntHeading",
            parent=base["Heading2"],
            fontSize=13,
            textColor=c_primary,
            spaceBefore=14,
            spaceAfter=8,
            leading=16,
        ),
        "subheading": ParagraphStyle(
            "EntSub",
            parent=base["Heading3"],
            fontSize=11,
            textColor=c_accent,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "EntBody",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "EntSmall",
            parent=base["BodyText"],
            fontSize=8,
            leading=11,
            textColor=colors.grey,
        ),
        "table_cell": ParagraphStyle(
            "EntTableCell",
            parent=base["BodyText"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            wordWrap="normal",
            splitLongWords=False,
        ),
        "table_header_cell": ParagraphStyle(
            "EntTableHeaderCell",
            parent=base["BodyText"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        ),
        "table_header_bg": c_primary,
        "table_accent": c_accent,
    }


def _table_cell_para(text: Any, styles: Dict[str, Any], *, bold: bool = False) -> Paragraph:
    raw = _xml_escape(str(text if text is not None else "\u2014"))
    if bold:
        header_style = styles.get("table_header_cell")
        if header_style is None:
            parent = styles.get("table_cell") or styles.get("body") or styles.get("small")
            header_style = ParagraphStyle(
                "EntTableHeaderCellDynamic",
                parent=parent,
                fontSize=getattr(parent, "fontSize", 8),
                leading=getattr(parent, "leading", 10),
                textColor=colors.white,
                fontName="Helvetica-Bold",
            )
        return Paragraph(raw, header_style)
    cell_style = styles.get("table_cell") or styles.get("body") or styles.get("small")
    return Paragraph(raw, cell_style)


def _obligation_cell_para(
    obligation: str,
    category: str,
    styles: Dict[str, Any],
) -> Paragraph:
    """Obligation label only — internal category codes are not shown to customers."""
    del category
    cell_style = styles.get("table_cell") or styles["body"]
    return Paragraph(_xml_escape(obligation or "\u2014"), cell_style)


def _stacked_cell_para(primary: str, secondary: str, styles: Dict[str, Any]) -> Paragraph:
    cell_style = styles.get("table_cell") or styles["body"]
    main = _xml_escape(primary or "\u2014")
    sub = (secondary or "").strip()
    if sub and sub not in ("\u2014", primary):
        return Paragraph(
            f"{main}<br/><font size=\"7\" color=\"#64748b\">{_xml_escape(sub)}</font>",
            cell_style,
        )
    return Paragraph(main, cell_style)


def create_enterprise_table_style(styles: Dict[str, Any]) -> TableStyle:
    bg = styles.get("table_header_bg") or _hex_color(BRAND_MIDNIGHT)
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.Color(0.82, 0.82, 0.82)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.98, 0.99)]),
        ]
    )


def _days_to_expiry(due: Any, now: datetime) -> Optional[int]:
    if due is None:
        return None
    try:
        if isinstance(due, datetime):
            d = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
        else:
            raw = str(due).strip().replace("Z", "+00:00")
            if not raw:
                return None
            d = datetime.fromisoformat(raw)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
        n = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return (d.astimezone(timezone.utc) - n.astimezone(timezone.utc)).days
    except Exception:
        return None


def _risk_level_for_row(row: Dict[str, Any], *, property_doc: Optional[dict], client_doc: dict) -> str:
    cs = (get_computed_status(row, property_doc=property_doc, client_doc=client_doc) or "").upper()
    if cs in ("OVERDUE", "EXPIRED", "NON_COMPLIANT", "FAILED"):
        return "High" if not row.get("mandatory") else "Critical"
    if cs in ("MISSING", "PENDING", "ACTION_REQUIRED"):
        return "Critical" if row.get("mandatory") else "High"
    if cs == "EXPIRING_SOON":
        return "Medium"
    if cs in ("COMPLIANT", "VALID", "SATISFIED"):
        return "Low"
    return "Medium"


def _action_priority_for_row(row: Dict[str, Any], *, property_doc: Optional[dict], client_doc: dict) -> str:
    cs = (get_computed_status(row, property_doc=property_doc, client_doc=client_doc) or "").upper()
    if cs in ("OVERDUE", "EXPIRED", "NON_COMPLIANT", "FAILED") and row.get("mandatory"):
        return "Critical"
    if cs in ("OVERDUE", "EXPIRED", "MISSING", "ACTION_REQUIRED"):
        return "High"
    if cs in ("PENDING", "EXPIRING_SOON") or str(row.get("client_lifecycle_state") or "").upper() == "PENDING_REVIEW":
        return "Medium"
    return "Informational"


def _evidence_present(row: Dict[str, Any]) -> str:
    if row.get("evidence_doc_id") or row.get("document_id"):
        return "Yes"
    es = str(row.get("evidence_state") or "").strip().upper()
    if es in ("VERIFIED", "UPLOADED_UNVERIFIED"):
        return "Yes"
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    if str(ea.get("state") or "").upper() in ("VERIFIED_CURRENT", "VERIFIED"):
        return "Yes"
    return "No"


def _delivery_proof_label(req_id: str, delivery_by_req: Dict[str, bool]) -> str:
    if not req_id:
        return "N/A"
    if delivery_by_req.get(req_id):
        return "Yes"
    return "No"


def _evidence_file_ref(row: Dict[str, Any], docs_by_req: Dict[str, List[Dict[str, Any]]]) -> str:
    rid = str(row.get("requirement_id") or "")
    docs = docs_by_req.get(rid) or []
    if not docs:
        return "—"
    names = [str(d.get("file_name") or d.get("document_id") or "")[:24] for d in docs[:2]]
    return "; ".join(n for n in names if n) or "—"


def _last_updated(row: Dict[str, Any]) -> str:
    for key in ("updated_at", "evidence_authority_synced_at", "last_status_change_at", "modified_at"):
        val = row.get(key)
        if val:
            return utc_display(val)[:18]
    return "—"


def _action_required_label(row: Dict[str, Any], *, property_doc: Optional[dict], client_doc: dict) -> str:
    pri = _action_priority_for_row(row, property_doc=property_doc, client_doc=client_doc)
    if pri in ("Critical", "High"):
        return "Yes"
    if pri == "Medium":
        return "Review"
    return "No"


def build_matrix_rows(
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    docs_by_req: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    delivery_by_req: Optional[Dict[str, bool]] = None,
    now: Optional[datetime] = None,
    property_filter_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    now = now or datetime.now(timezone.utc)
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    docs_by_req = docs_by_req or {}
    delivery_by_req = delivery_by_req or {}
    rows: List[Dict[str, str]] = []
    for r in requirements:
        pid = r.get("property_id")
        if property_filter_id and pid != property_filter_id:
            continue
        pd = pmap.get(pid)
        eff = get_effective_expiry_date(r)
        due_str = "—"
        if eff and hasattr(eff, "date"):
            due_str = eff.date().isoformat()
        elif r.get("due_date"):
            due_str = str(r.get("due_date"))[:10]
        days = _days_to_expiry(eff or r.get("due_date"), now)
        cs = get_computed_status(r, property_doc=pd, client_doc=client_doc)
        rid = str(r.get("requirement_id") or "")
        rows.append(
            {
                "obligation": (r.get("description") or r.get("requirement_type") or "\u2014"),
                "category": (r.get("requirement_type") or r.get("requirement_code") or "\u2014")[:32],
                "status": str(cs or r.get("status") or "\u2014"),
                "evidence_present": _evidence_present(r),
                "evidence_ref": _evidence_file_ref(r, docs_by_req)[:36],
                "delivery_proof": _delivery_proof_label(rid, delivery_by_req),
                "expiry": due_str,
                "days_to_expiry": str(days) if days is not None else "—",
                "risk_level": _risk_level_for_row(r, property_doc=pd, client_doc=client_doc),
                "action_required": _action_required_label(r, property_doc=pd, client_doc=client_doc),
                "last_updated": _last_updated(r),
                "priority": _action_priority_for_row(r, property_doc=pd, client_doc=client_doc),
            }
        )
    return rows


def compute_readiness_indicators(
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    deliveries: Optional[List[Dict[str, Any]]] = None,
    docs_by_req: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    deliveries = deliveries or []
    docs_by_req = docs_by_req or {}
    total = len(requirements)
    with_evidence = sum(1 for r in requirements if _evidence_present(r) == "Yes")
    delivery_req_ids = {
        str(d.get("requirement_id") or "")
        for d in deliveries
        if d.get("requirement_id")
    }
    with_delivery = sum(
        1 for r in requirements if str(r.get("requirement_id") or "") in delivery_req_ids
    )
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    unresolved = 0
    for r in requirements:
        pd = pmap.get(r.get("property_id"))
        if _action_priority_for_row(r, property_doc=pd, client_doc=client_doc) in ("Critical", "High"):
            unresolved += 1
    evidence_pct = round((with_evidence / total) * 100) if total else 100
    delivery_pct = round((with_delivery / total) * 100) if total and delivery_req_ids else None
    if total and not delivery_req_ids:
        delivery_note = "No delivery proof records in scope."
        delivery_pct = None
    else:
        delivery_note = f"{with_delivery} of {total} obligations have linked delivery proof."
    if unresolved == 0 and evidence_pct >= 90:
        readiness = "Audit-ready"
        confidence = "High"
    elif unresolved <= max(2, total // 10):
        readiness = "Substantially ready — limited exceptions"
        confidence = "Medium"
    else:
        readiness = "Not audit-ready — material gaps remain"
        confidence = "Low"
    exposure = unresolved
    return {
        "total_obligations": total,
        "evidence_completeness_pct": evidence_pct,
        "evidence_completeness_note": f"{with_evidence} of {total} obligations have evidence on file.",
        "delivery_proof_completeness_pct": delivery_pct,
        "delivery_proof_note": delivery_note,
        "audit_readiness": readiness,
        "audit_confidence": confidence,
        "unresolved_evidence_exposure": exposure,
    }


def classify_exceptions(
    *,
    requirements: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
    docs_by_req: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    deliveries: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, List[str]]:
    now = now or datetime.now(timezone.utc)
    docs_by_req = docs_by_req or {}
    deliveries = deliveries or []
    delivery_req_ids = {str(d.get("requirement_id") or "") for d in deliveries if d.get("requirement_id")}
    pmap = {p.get("property_id"): p for p in properties if p.get("property_id")}
    out: Dict[str, List[str]] = {
        "missing_evidence": [],
        "unverifiable_evidence": [],
        "expired_evidence": [],
        "conflicting_records": [],
        "missing_delivery_proof": [],
        "unresolved_obligations": [],
    }
    for r in requirements:
        label = (r.get("description") or r.get("requirement_type") or r.get("requirement_id") or "—")[:48]
        pd = pmap.get(r.get("property_id"))
        cs = (get_computed_status(r, property_doc=pd, client_doc=client_doc) or "").upper()
        rid = str(r.get("requirement_id") or "")
        if _evidence_present(r) == "No" and cs in ("MISSING", "PENDING", "OVERDUE", "EXPIRED"):
            out["missing_evidence"].append(label)
        if str(r.get("assurance_tier") or "").upper() in ("SELF_RECORDED",) or str(
            r.get("client_lifecycle_state") or ""
        ).upper() == "SATISFIED_UNVERIFIED":
            out["unverifiable_evidence"].append(label)
        if cs in ("OVERDUE", "EXPIRED"):
            out["expired_evidence"].append(label)
        if cs in ("OVERDUE", "EXPIRED", "MISSING", "ACTION_REQUIRED", "NON_COMPLIANT"):
            out["unresolved_obligations"].append(label)
        if rid and delivery_req_ids and rid not in delivery_req_ids and r.get("requires_tenant_delivery"):
            out["missing_delivery_proof"].append(label)
    for labels in out.values():
        del labels[25:]
    return out


def group_by_action_priority(matrix_rows: List[Dict[str, str]]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {k: [] for k in ACTION_PRIORITIES}
    for row in matrix_rows:
        pri = row.get("priority") or "Informational"
        if pri not in groups:
            pri = "Informational"
        if len(groups[pri]) < 20:
            groups[pri].append(row.get("obligation") or "—")
    return groups


def append_section_block(
    elements: List[Any],
    *,
    title: str,
    intro: str,
    styles: Dict[str, Any],
    body_items: Optional[List[Any]] = None,
) -> None:
    """Section with KeepTogether header to reduce orphan headings."""
    header = [
        Paragraph(_xml_escape(title), styles["heading"]),
        Paragraph(intro, styles["small"]),
        Spacer(1, 6),
    ]
    elements.append(KeepTogether(header))
    for item in body_items or []:
        elements.append(item)


def append_frozen_snapshot_notice(elements: List[Any], *, generated_at_iso: str, styles: Dict[str, Any]) -> None:
    """No-op — frozen snapshot wording is rendered in the canvas footer band."""
    del elements, generated_at_iso, styles


def append_intended_use_section(elements: List[Any], *, report_kind: str, styles: Dict[str, Any]) -> None:
    use = INTENDED_USE.get(report_kind, INTENDED_USE["compliance_summary"])
    append_section_block(
        elements,
        title="Intended use",
        intro=use,
        styles=styles,
        body_items=[
            Paragraph(_xml_escape(LEGAL_LIMITATION), styles["small"]),
            Spacer(1, 10),
        ],
    )


def append_readiness_indicators_section(
    elements: List[Any],
    *,
    indicators: Dict[str, Any],
    styles: Dict[str, Any],
    table_style: TableStyle,
    table_width: Optional[float] = None,
) -> None:
    width = table_width or formal_report_table_width()
    col_widths = proportional_col_widths(width, [0.30, 0.18, 0.52])
    delivery_val = (
        f"{indicators['delivery_proof_completeness_pct']}%"
        if indicators.get("delivery_proof_completeness_pct") is not None
        else "N/A"
    )
    confidence = indicators.get("audit_confidence", "—")
    data = [
        [
            _table_cell_para("Indicator", styles, bold=True),
            _table_cell_para("Value", styles, bold=True),
            _table_cell_para("Interpretation", styles, bold=True),
        ],
        [
            _table_cell_para("Evidence completeness", styles),
            _table_cell_para(f"{indicators.get('evidence_completeness_pct', 0)}%", styles),
            _table_cell_para(indicators.get("evidence_completeness_note", ""), styles),
        ],
        [
            _table_cell_para("Delivery proof completeness", styles),
            _table_cell_para(delivery_val, styles),
            _table_cell_para(indicators.get("delivery_proof_note", ""), styles),
        ],
        [
            _table_cell_para("Audit readiness", styles),
            _table_cell_para(indicators.get("audit_readiness", "—"), styles),
            _table_cell_para(f"Confidence level: {confidence}", styles),
        ],
        [
            _table_cell_para("Unresolved evidence exposure", styles),
            _table_cell_para(str(indicators.get("unresolved_evidence_exposure", 0)), styles),
            _table_cell_para(
                "Obligations requiring critical or high-priority action.",
                styles,
            ),
        ],
    ]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(table_style)
    append_section_block(
        elements,
        title="Evidence sufficiency and audit readiness",
        intro=(
            "Indicators summarise whether evidence and delivery proof are sufficient for "
            "independent review at the generation boundary."
        ),
        styles=styles,
        body_items=[t, Spacer(1, 8)],
    )


def append_executive_summary_section(
    elements: List[Any],
    *,
    posture_lines: List[str],
    metrics: List[Tuple[str, str]],
    interpretation: List[str],
    styles: Dict[str, Any],
    table_style: TableStyle,
) -> None:
    metric_rows = [["Metric", "Value"]] + [[a, b] for a, b in metrics]
    mt = Table(metric_rows, colWidths=[90 * mm, 55 * mm], repeatRows=1)
    mt.setStyle(table_style)
    body_items: List[Any] = []
    for line in posture_lines:
        body_items.append(Paragraph(line, styles["body"]))
    body_items.append(Spacer(1, 6))
    body_items.append(mt)
    body_items.append(Spacer(1, 6))
    for line in interpretation:
        body_items.append(Paragraph(line, styles["small"]))
    body_items.append(Spacer(1, 10))
    append_section_block(
        elements,
        title="Executive summary",
        intro="Overall compliance posture and action posture at generation time.",
        styles=styles,
        body_items=body_items,
    )


def append_central_evidence_matrix(
    elements: List[Any],
    *,
    matrix_rows: List[Dict[str, str]],
    styles: Dict[str, Any],
    table_style: TableStyle,
    max_rows: int = 40,
    table_width: Optional[float] = None,
) -> None:
    shown = matrix_rows[:max_rows]
    width = table_width or formal_report_table_width()
    col_widths = proportional_col_widths(
        width,
        [0.28, 0.11, 0.13, 0.09, 0.13, 0.10, 0.16],
    )
    header = [
        _table_cell_para("Obligation", styles, bold=True),
        _table_cell_para("Status", styles, bold=True),
        _table_cell_para("Evidence", styles, bold=True),
        _table_cell_para("Delivery", styles, bold=True),
        _table_cell_para("Expiry / Risk", styles, bold=True),
        _table_cell_para("Action", styles, bold=True),
        _table_cell_para("Updated", styles, bold=True),
    ]
    data: List[List[Any]] = [header]
    for row in shown:
        expiry = row.get("expiry", "—")
        risk = row.get("risk_level", "—")
        days = row.get("days_to_expiry", "—")
        expiry_risk = expiry
        if risk and risk != "—":
            expiry_risk = f"{expiry} / {risk}"
        if days and days != "—":
            expiry_risk = f"{expiry_risk} ({days}d)"
        data.append(
            [
                _obligation_cell_para(
                    row.get("obligation", "—"),
                    row.get("category", "—"),
                    styles,
                ),
                _table_cell_para(_human_status_label(row.get("status", "\u2014")), styles),
                _stacked_cell_para(
                    row.get("evidence_present", "—"),
                    row.get("evidence_ref", "—"),
                    styles,
                ),
                _table_cell_para(row.get("delivery_proof", "—"), styles),
                _table_cell_para(expiry_risk, styles),
                _table_cell_para(row.get("action_required", "—"), styles),
                _table_cell_para(row.get("last_updated", "—"), styles),
            ]
        )
    t = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    t.setStyle(table_style)
    omitted = max(0, len(matrix_rows) - len(shown))
    intro = (
        "Central evidence matrix mapping each obligation to status, evidence files, "
        "delivery proof, expiry, and risk. Compliance conclusions must be read against this matrix."
    )
    if omitted:
        intro += f" Showing {len(shown)} of {len(matrix_rows)} obligations."
    append_section_block(
        elements,
        title="Evidence matrix",
        intro=intro,
        styles=styles,
        body_items=[
            t,
            Paragraph(
                "Evidence remains subject to independent verification of source documents and issuing authorities.",
                styles["small"],
            ),
            Spacer(1, 10),
        ],
    )


def append_action_priority_section(
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
        body.append(Paragraph(f"<b>{_xml_escape(pri)}</b>", styles.get("subheading") or styles["heading"]))
        for item in items[:12]:
            body.append(Paragraph(f"• {_xml_escape(item)}", styles["body"]))
        body.append(Spacer(1, 4))
    if not body:
        body.append(Paragraph("No action-priority groupings in export scope.", styles["body"]))
    append_section_block(
        elements,
        title="Action priority groupings",
        intro="Obligations grouped by operational priority for review sequencing.",
        styles=styles,
        body_items=body + [Spacer(1, 8)],
    )


def append_exception_summaries_section(
    elements: List[Any],
    *,
    exceptions: Dict[str, List[str]],
    styles: Dict[str, Any],
    table_style: TableStyle,
    table_width: Optional[float] = None,
) -> None:
    labels = {
        "missing_evidence": "Missing evidence",
        "unverifiable_evidence": "Unverifiable evidence",
        "expired_evidence": "Expired evidence",
        "conflicting_records": "Conflicting records",
        "missing_delivery_proof": "Missing delivery proof",
        "unresolved_obligations": "Unresolved obligations",
    }
    width = table_width or formal_report_table_width()
    col_widths = proportional_col_widths(width, [0.34, 0.12, 0.54])
    data: List[List[Any]] = [
        [
            _table_cell_para("Exception type", styles, bold=True),
            _table_cell_para("Count", styles, bold=True),
            _table_cell_para("Examples", styles, bold=True),
        ]
    ]
    for key, title in labels.items():
        items = exceptions.get(key) or []
        sample = "; ".join(items[:3]) if items else "None in scope"
        data.append(
            [
                _table_cell_para(title, styles),
                _table_cell_para(str(len(items)), styles),
                _table_cell_para(sample, styles),
            ]
        )
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(table_style)
    append_section_block(
        elements,
        title="Evidence exception summary",
        intro="Summarised exceptions affecting evidential confidence within export scope.",
        styles=styles,
        body_items=[t, Spacer(1, 10)],
    )


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


def _human_status_label(status: Any) -> str:
    from services.report_human_language_v1 import human_compliance_status_label

    raw = str(status or "").strip()
    if not raw:
        return "\u2014"
    return human_compliance_status_label(raw) or raw


def _compact_audit_timestamp(value: Any) -> str:
    s = str(value or "\u2014").strip().replace("Z", "+00:00")
    if "T" in s:
        s = s.replace("T", " ", 1)
    s = s.replace("+00:00", " UTC")
    return s


def _humanize_audit_event(action: Any) -> str:
    from services.report_evidence_readiness_operational import humanize_audit_event_action

    return humanize_audit_event_action(action)


def _is_internal_reference_token(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    if len(v) >= 32 and "-" in v:
        return True
    if v.startswith(("rs_", "req_", "doc_", "prop_")):
        return True
    return bool(re.fullmatch(r"[a-z0-9_]{3,}", v))


def _audit_trail_summary_cell(ev: Dict[str, Any], styles: Dict[str, Any]) -> Paragraph:
    md = ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}
    action = ev.get("action") or ev.get("event_type")
    summary = str(md.get("summary") or _humanize_audit_event(action) or "—")
    subject = str(ev.get("resource_id") or md.get("requirement_id") or "").strip()
    ref = str(md.get("document_id") or md.get("evidence_record_id") or "").strip()
    parts = [summary]
    if subject and subject not in summary and not _is_internal_reference_token(subject):
        parts.append(f"Subject: {subject}")
    elif ref and not _is_internal_reference_token(ref):
        parts.append(f"Reference: {ref[:24]}")
    return _table_cell_para(" · ".join(parts), styles)


def append_audit_trail_narrative(
    elements: List[Any],
    *,
    events: List[Dict[str, Any]],
    styles: Dict[str, Any],
    table_style: TableStyle,
    max_rows: int = 60,
    table_width: Optional[float] = None,
) -> None:
    shown = events[:max_rows]
    width = table_width or formal_report_table_width()
    col_widths = proportional_col_widths(width, [0.18, 0.22, 0.14, 0.46])
    data: List[List[Any]] = [
        [
            _table_cell_para("Timestamp (UTC)", styles, bold=True),
            _table_cell_para("Event", styles, bold=True),
            _table_cell_para("Actor", styles, bold=True),
            _table_cell_para("Summary", styles, bold=True),
        ]
    ]
    for ev in shown:
        action = ev.get("action") or ev.get("event_type")
        data.append(
            [
                _table_cell_para(_compact_audit_timestamp(ev.get("timestamp")), styles),
                _table_cell_para(_humanize_audit_event(action), styles),
                _table_cell_para(
                    _human_actor_role(ev.get("actor_role") or ev.get("actor")),
                    styles,
                ),
                _audit_trail_summary_cell(ev, styles),
            ]
        )
    t = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    t.setStyle(table_style)
    omitted = max(0, len(events) - len(shown))
    intro = "Chronological audit trail from system records at generation time."
    if omitted:
        intro += f" Showing {len(shown)} of {len(events)} events."
    append_section_block(
        elements,
        title="Audit trail",
        intro=intro,
        styles=styles,
        body_items=[t, Spacer(1, 10)],
    )


def append_scope_limitations_section(
    elements: List[Any],
    *,
    lines: List[str],
    styles: Dict[str, Any],
) -> None:
    bullets = [Paragraph(f"• {_xml_escape(ln)}", styles["body"]) for ln in lines]
    header = [
        Paragraph(_xml_escape("Scope and limitations"), styles["heading"]),
        Paragraph(
            "Records included, excluded, and verification boundaries for this export.",
            styles["small"],
        ),
        Spacer(1, 6),
    ]
    elements.append(KeepTogether(header + bullets + [Spacer(1, 10)]))


def build_formal_report_pdf(
    spec: FormalReportSpec,
    *,
    posture_lines: Optional[List[str]] = None,
    metrics: Optional[List[Tuple[str, str]]] = None,
    interpretation: Optional[List[str]] = None,
    matrix_rows: Optional[List[Dict[str, str]]] = None,
    readiness: Optional[Dict[str, Any]] = None,
    exceptions: Optional[Dict[str, List[str]]] = None,
    action_groups: Optional[Dict[str, List[str]]] = None,
    audit_events: Optional[List[Dict[str, Any]]] = None,
    scope_lines: Optional[List[str]] = None,
) -> bytes:
    styles = create_enterprise_styles(spec.branding)
    table_style = create_enterprise_table_style(styles)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=governance_footer_bottom_margin(),
        pageCompression=0,
    )
    table_width = doc.width
    operator_line = (
        f"{spec.branding.get('pdf_footer_generated_by') or f'Generated by {PLEERITY_OPERATOR}'} · "
        f"{spec.branding.get('pdf_footer_contact_line') or PLEERITY_WEBSITE}"
    )
    on_first, on_later = make_page_callbacks(spec.gov_ctx, operator_line=operator_line)
    elements: List[Any] = []

    cover_extra = list(spec.extra_cover_lines)
    if spec.export_id:
        cover_extra.append(f"<b>Export ID:</b> {_xml_escape(spec.export_id)}")
    if spec.export_generation_id:
        cover_extra.append(f"<b>Export generation ID:</b> {_xml_escape(spec.export_generation_id)}")
    cover_extra.append(
        f"<b>Prepared by:</b> {_xml_escape(spec.branding.get('brand_company_name') or PLEERITY_OPERATOR)}"
    )
    cover_extra.append(
        f"<b>Contact:</b> {_xml_escape(PLEERITY_SUPPORT)} &nbsp;|&nbsp; {_xml_escape(PLEERITY_WEBSITE)}"
    )
    cover_extra.append(
        "<b>Confidentiality:</b> For authorised review only. System provenance metadata is retained "
        "in governance files regardless of white-label presentation."
    )

    append_report_cover_block(
        elements,
        report_title=spec.report_title,
        branding=spec.branding,
        gov_ctx=spec.gov_ctx,
        styles=styles,
        account_line=spec.account_line,
        scope_line=spec.scope_line or f"<b>Classification:</b> {_xml_escape(spec.report_classification)}",
        extra_metadata_lines=cover_extra,
    )
    elements.extend(export_disclosure_paragraphs(spec.gov_ctx, styles))
    if spec.jurisdiction:
        elements.append(Paragraph(f"<b>Jurisdiction:</b> {_xml_escape(spec.jurisdiction)}", styles["body"]))
    elements.append(Spacer(1, 8))

    if spec.include_intended_use:
        append_intended_use_section(elements, report_kind=spec.report_kind, styles=styles)

    if spec.include_executive_summary and metrics:
        append_executive_summary_section(
            elements,
            posture_lines=posture_lines or [],
            metrics=metrics,
            interpretation=interpretation or [],
            styles=styles,
            table_style=table_style,
        )

    if spec.include_readiness_indicators and readiness:
        append_readiness_indicators_section(
            elements,
            indicators=readiness,
            styles=styles,
            table_style=table_style,
            table_width=table_width,
        )

    if spec.include_matrix and matrix_rows:
        append_central_evidence_matrix(
            elements,
            matrix_rows=matrix_rows,
            styles=styles,
            table_style=table_style,
            table_width=table_width,
        )

    if spec.include_action_priorities and action_groups:
        append_action_priority_section(elements, groups=action_groups, styles=styles)

    if spec.include_exception_summaries and exceptions:
        append_exception_summaries_section(
            elements,
            exceptions=exceptions,
            styles=styles,
            table_style=table_style,
            table_width=table_width,
        )

    if spec.include_audit_trail and audit_events:
        append_audit_trail_narrative(
            elements,
            events=audit_events,
            styles=styles,
            table_style=table_style,
            table_width=table_width,
        )

    if spec.include_scope_limitations and scope_lines:
        append_scope_limitations_section(elements, lines=scope_lines, styles=styles)

    doc.build(elements, onFirstPage=on_first, onLaterPages=on_later)
    return buf.getvalue()


def docs_by_requirement(docs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        rid = str(d.get("requirement_id") or "")
        if rid:
            out.setdefault(rid, []).append(d)
    return out


def delivery_proof_by_requirement(deliveries: List[Dict[str, Any]]) -> Dict[str, bool]:
    out: Dict[str, bool] = {}
    for d in deliveries:
        rid = str(d.get("requirement_id") or "")
        if rid:
            out[rid] = True
    return out
