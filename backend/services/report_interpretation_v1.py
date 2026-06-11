"""
S2-B Lite — report-facing interpretability copy (pre-launch).

Composes vocabulary_contract_v1 boundary notes into concise, report-class-specific
guidance. Does not alter scoring, posture logic, or export contracts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.vocabulary_contract_v1 import (
    metric_boundary_note,
    posture_boundary_note,
    readiness_boundary_note,
    semantic_scope_note,
)

REPORT_INTERPRETATION_VERSION = "v1"

_REPORT_CLASS_ALIASES = {
    "compliance_summary": "compliance_summary",
    "requirements": "requirements",
    "evidence_readiness": "evidence_readiness",
    "monthly_digest": "monthly_digest",
    "scheduled_compliance_summary": "scheduled_compliance_summary",
    "scheduled_requirements": "scheduled_requirements",
}

# Landlord-readable how-to-read lines (semantically aligned with vocabulary contract).
_CVP_HOW_TO_READ = (
    "The CVP headline score is your portfolio score from the last calculation. "
    "It is not a legal compliance rating and may differ from how many obligations are satisfied."
)
_COMPLETION_HOW_TO_READ = (
    "The satisfaction rate counts obligations marked satisfied in this report. "
    "It is separate from the CVP score and is not a legal compliance rating."
)
_VERIFICATION_HOW_TO_READ = (
    "Uploaded or recorded items are not the same as independently verified evidence unless stated."
)


def _norm_report_class(report_class: str) -> str:
    return _REPORT_CLASS_ALIASES.get(
        str(report_class or "").strip().lower().replace("-", "_"),
        "compliance_summary",
    )


def metric_interpretation_line(metric_id: str) -> str:
    """One-line interpretation for a headline metric."""
    lines = {
        "cvp": metric_boundary_note("cvp"),
        "completion_pct": metric_boundary_note("completion_pct"),
        "compliance_rate": metric_boundary_note("compliance_rate"),
        "evidence_confidence": semantic_scope_note(kind="evidence_confidence"),
        "audit_readiness": readiness_boundary_note(),
        "operational_posture": posture_boundary_note(),
        "operational_exposure": (
            "Operational exposure counts overdue items, missing evidence, and pending review "
            "in this report — not court or financial risk."
        ),
        "property_readiness": (
            "Property readiness reflects local overdue and missing-evidence items — "
            "not portfolio audit-ready status or the CVP headline score."
        ),
        "verification_maturity": semantic_scope_note(kind="verification"),
    }
    return lines.get(metric_id, semantic_scope_note())


def audit_readiness_scope_note(readiness_label: Optional[str] = None) -> str:
    """Bounded note when audit-ready language appears."""
    label = str(readiness_label or "").strip()
    if "audit-ready" in label.lower() and "not audit-ready" not in label.lower():
        return (
            "Audit-ready means evidence is largely complete with few critical gaps. "
            "It does not mean an external auditor or council has approved your portfolio."
        )
    if "substantially ready" in label.lower():
        return "Limited exceptions remain; address priority items before external review."
    if "not audit-ready" in label.lower():
        return "Material gaps remain before external review at the report date."
    return readiness_boundary_note()


def how_to_read_paragraphs(report_class: str) -> List[str]:
    """Concise interpretability bullets for PDF/report bodies."""
    key = _norm_report_class(report_class)
    if key == "compliance_summary":
        return [
            "This report brings together portfolio status, your CVP headline score, and readiness at the report date.",
            _CVP_HOW_TO_READ,
            _COMPLETION_HOW_TO_READ,
            "Posture and property readiness are dashboard indicators — not legal compliance ratings.",
            report_relationship_note("compliance_summary"),
        ]
    if key == "requirements":
        return [
            "This report prioritises what needs action — overdue items, renewals, evidence review, and recorded items.",
            _VERIFICATION_HOW_TO_READ,
            report_relationship_note("requirements"),
        ]
    if key == "evidence_readiness":
        return [
            "This report shows how ready your evidence is for audit review and where gaps remain.",
            audit_readiness_scope_note("Audit-ready"),
            "Evidence completeness shows files on file — not the same as verified compliance.",
            report_relationship_note("evidence_readiness"),
        ]
    if key == "monthly_digest":
        return digest_directional_caveat_lines(has_prior_snapshot=True) + [
            report_relationship_note("monthly_digest"),
        ]
    if key == "scheduled_compliance_summary":
        return [
            "This email is a brief snapshot — not a full export.",
            "Open the portal for live status and full detail.",
        ]
    if key == "scheduled_requirements":
        return [
            "This email summarises triage counts — open the Requirements Report or portal for full detail.",
            "Verified or accepted items are listed separately from recorded (unverified) items.",
        ]
    return [semantic_scope_note()]


def how_to_read_csv_lines(report_class: str) -> List[str]:
    """CSV comment rows (# prefix) for interpretability."""
    lines = ["# === HOW TO READ THIS REPORT ==="]
    for para in how_to_read_paragraphs(report_class):
        lines.append(f"# {para}")
    lines.append("#")
    return lines


def how_to_read_email_html_bullets(report_class: str) -> List[str]:
    """Short bullets for scheduled/digest email panels (max 2 — reduce cognitive load)."""
    key = _norm_report_class(report_class)
    if key == "monthly_digest":
        return [
            "Month-on-month changes are directional only — check operational reports for overdue items and gaps.",
            "Digest summaries do not replace the Requirements Report or Audit Evidence Pack.",
        ]
    return how_to_read_paragraphs(report_class)[:2]


def digest_directional_caveat_lines(*, has_prior_snapshot: bool) -> List[str]:
    """Monthly digest movement interpretation boundaries."""
    lines = [
        "Month-on-month changes are directional indicators only — not a full obligation list.",
        "A stable or improving trend does not remove overdue items or missing evidence in operational reports.",
    ]
    if not has_prior_snapshot:
        lines.insert(
            0,
            "First digest for this portfolio: baseline snapshot only; later digests will show month-on-month movement.",
        )
    return lines


def report_relationship_note(report_class: str) -> str:
    """Lightweight human-readable report relationship guidance (not authority routing)."""
    key = _norm_report_class(report_class)
    notes = {
        "compliance_summary": (
            "Portfolio overview here differs from item-by-item detail in the Requirements Report "
            "and from the Audit Evidence Pack export."
        ),
        "requirements": (
            "Use this report for day-to-day actions. Compliance Summary shows portfolio overview; "
            "Audit Evidence Pack holds your formal evidence export."
        ),
        "evidence_readiness": (
            "Remediation focus here differs from the Compliance Summary portfolio overview and from "
            "the point-in-time Audit Evidence Pack."
        ),
        "monthly_digest": (
            "Digest summaries show month-on-month movement — they do not replace the Requirements Report "
            "or Audit Evidence Pack."
        ),
    }
    return notes.get(key, semantic_scope_note())


def scheduled_summary_has_material_exposure(
    summary: Optional[Dict[str, Any]],
    properties: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """True when scheduled compliance snapshot still has operational follow-up in scope."""
    summary = summary or {}
    rb = summary.get("requirements_breakdown") or {}
    overdue = int(rb.get("overdue") or 0)
    pending = int(rb.get("pending") or 0)
    if overdue + pending > 0:
        return True
    for prop in properties or []:
        st = str(prop.get("compliance_status") or "").upper()
        if st in ("RED", "AMBER"):
            return True
    return False


def scheduled_all_clear_panel_html() -> str:
    return (
        "<p style=\"margin:0;\">No properties are flagged red or amber in this run's dashboard indicators. "
        "Keep evidence current in the portal — operational reports may still list renewals or recorded items.</p>"
    )


def scheduled_exposure_panel_html() -> str:
    return (
        "<p style=\"margin:0;\">Some items still need follow-up — overdue obligations, missing evidence, "
        "or amber/red property indicators. Check the portal or Requirements Report for details.</p>"
    )


def append_how_to_read_pdf_section(
    elements: List[Any],
    *,
    report_class: str,
    styles: Dict[str, Any],
) -> None:
    """Add a concise 'How to read this report' block to PDF bodies."""
    from reportlab.platypus import Paragraph, Spacer

    from services.report_pdf_templates import _xml_escape, append_section_block

    paras = how_to_read_paragraphs(report_class)
    body_items = [Paragraph(f"• {_xml_escape(p)}", styles["body"]) for p in paras] + [Spacer(1, 10)]
    append_section_block(
        elements,
        title="How to read this report",
        intro="What this report shows at the report date — and what it does not decide.",
        styles=styles,
        body_items=body_items,
    )


def scheduled_how_to_read_html_panel(report_type_raw: str) -> str:
    """Lightweight interpretability panel for scheduled report emails."""
    key = _norm_report_class(
        "scheduled_compliance_summary"
        if _normalize_scheduled_report_type(report_type_raw) == "compliance_summary"
        else "scheduled_requirements"
    )
    bullets = how_to_read_email_html_bullets(key)
    items = "".join(f"<li>{b}</li>" for b in bullets)
    preamble = ""
    if key == "scheduled_compliance_summary":
        preamble = (
            "<p style=\"margin:0 0 8px 0;\">Green, amber, and red are <strong>dashboard indicators</strong> "
            "from tracked requirements and evidence — not a legal compliance rating. "
            "Figures can change when data updates or scoring recalculates.</p>"
        )
    return f"{preamble}<ul style=\"margin:8px 0 0 0;padding-left:20px;\">{items}</ul>"


def _normalize_scheduled_report_type(report_type: str) -> str:
    raw = str(report_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in ("compliance_summary", "compliance_summary_report", "compliance_status_summary"):
        return "compliance_summary"
    if raw in ("requirements", "requirements_report"):
        return "requirements"
    return raw
