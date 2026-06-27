"""
Consumer-facing presentation helpers for Compliance Timeline (Phase 2).

Reads timeline fields from enriched requirements. Does not recalculate timeline logic —
delegates to ``build_compliance_timeline`` only when timeline fields are absent.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.requirement_truth import (
    DATE_SOURCE_SYSTEM_ESTIMATED,
    EVIDENCE_AWAITING_USER_CONFIRM,
    EVIDENCE_MISMATCH_FLAGGED,
)


def ensure_compliance_timeline_on_requirement(
    requirement: Dict[str, Any],
    *,
    compliance_evidence_records: Optional[list] = None,
) -> Dict[str, Any]:
    """Return requirement with timeline projection attached (non-mutating copy)."""
    if requirement.get("compliance_timeline") and requirement.get("timeline_primary_date_label"):
        return requirement
    from services.compliance_timeline import build_compliance_timeline

    try:
        timeline = build_compliance_timeline(
            requirement,
            compliance_evidence_records=compliance_evidence_records,
        )
    except Exception:
        # Consumer fallback only — timeline calculator unchanged; sparse rows may lack lifecycle context.
        return dict(requirement)
    out = dict(requirement)
    out["compliance_timeline"] = timeline
    out["timeline_primary_date"] = timeline.get("primary_date")
    out["timeline_primary_date_label"] = timeline.get("primary_date_label")
    out["timeline_primary_date_confidence"] = timeline.get("primary_date_confidence")
    out["timeline_primary_date_source"] = timeline.get("primary_date_source")
    out["timeline_primary_date_concept"] = timeline.get("primary_date_concept")
    return out


def timeline_sort_date_iso(requirement: Dict[str, Any]) -> Optional[str]:
    """ISO date for sorting/urgency — prefers effective attention anchor when present."""
    tl = requirement.get("compliance_timeline") if isinstance(requirement.get("compliance_timeline"), dict) else {}
    attention = tl.get("effective_attention_date") or requirement.get("timeline_primary_date")
    if attention:
        return str(attention)[:10]
    return None


def timeline_customer_helper_text(
    requirement: Dict[str, Any],
    date_source: str,
    evidence_state: str,
) -> Optional[str]:
    """Helper text aligned with timeline confidence — not duplicate date wording."""
    if evidence_state == EVIDENCE_MISMATCH_FLAGGED:
        return (
            "The uploaded file does not look like the expected certificate type for this requirement. "
            "Upload the correct evidence or correct the extracted type and apply."
        )
    if evidence_state == EVIDENCE_AWAITING_USER_CONFIRM:
        return (
            "Confirm extracted details in Documents before your compliance score treats "
            "this certificate as final evidence."
        )
    tl = requirement.get("compliance_timeline") if isinstance(requirement.get("compliance_timeline"), dict) else {}
    if tl.get("is_estimated") or requirement.get("timeline_primary_date_confidence") == "ESTIMATED":
        return "Estimated from standard compliance cycles and your property setup. Upload your certificate to confirm this date."
    conf = (requirement.get("timeline_primary_date_confidence") or "").upper()
    if conf == "PARTIALLY_CONFIRMED" and evidence_state != "VERIFIED":
        return (
            "You entered this date or it came from an uploaded file — upload and verify "
            "your certificate to confirm it."
        )
    if date_source == DATE_SOURCE_SYSTEM_ESTIMATED:
        return "Estimated from standard compliance cycles and your property setup."
    return None


def timeline_customer_date_label(requirement: Dict[str, Any]) -> Optional[str]:
    """Authoritative customer-facing date label from timeline projection."""
    label = requirement.get("timeline_primary_date_label")
    if label:
        return str(label)
    tl = requirement.get("compliance_timeline") if isinstance(requirement.get("compliance_timeline"), dict) else {}
    if tl.get("primary_date_label"):
        return str(tl["primary_date_label"])
    return None


def timeline_report_date_display(requirement: Dict[str, Any]) -> str:
    """Report/export cell — timeline label preferred, ISO date fallback, never raw due_date heuristics."""
    label = timeline_customer_date_label(requirement)
    if label and label.strip().lower() != "no date on file":
        return label
    iso = requirement.get("timeline_primary_date")
    if iso:
        return str(iso)[:10]
    return "No date on file"


def timeline_report_date_kind(requirement: Dict[str, Any]) -> str:
    tl = requirement.get("compliance_timeline") if isinstance(requirement.get("compliance_timeline"), dict) else {}
    if tl.get("is_verified"):
        return "verified"
    if tl.get("is_estimated") or requirement.get("timeline_primary_date_confidence") == "ESTIMATED":
        return "estimated"
    conf = (requirement.get("timeline_primary_date_confidence") or "").upper()
    if conf == "VERIFIED":
        return "verified"
    if conf in ("PARTIALLY_CONFIRMED", "UNKNOWN", ""):
        return "partial" if requirement.get("timeline_primary_date") else "unknown"
    return "partial"


def build_date_presentation_from_timeline(
    requirement: Dict[str, Any],
    date_source: str,
    evidence_state: str,
) -> Tuple[str, Optional[str]]:
    """
    Phase 2: customer date presentation sourced from Compliance Timeline.
    Preserves evidence-workflow labels for mismatch / awaiting confirm only.
    """
    from services.requirement_truth import _format_gb_date, _parse_due_date_value

    if evidence_state == EVIDENCE_MISMATCH_FLAGGED:
        due_raw = requirement.get("timeline_primary_date") or requirement.get("due_date")
        d = _parse_due_date_value(due_raw)
        formatted = _format_gb_date(d) if d else None
        return (
            f"Review required — date on file: {formatted}" if formatted else "Review required — possible wrong document for this requirement",
            timeline_customer_helper_text(requirement, date_source, evidence_state),
        )
    if evidence_state == EVIDENCE_AWAITING_USER_CONFIRM:
        extracted = _parse_due_date_value(requirement.get("extracted_expiry_date"))
        formatted = _format_gb_date(extracted) if extracted else None
        if formatted:
            return (
                f"Extracted date (not yet applied): {formatted}",
                timeline_customer_helper_text(requirement, date_source, evidence_state),
            )
        return (
            "Awaiting your confirmation",
            timeline_customer_helper_text(requirement, date_source, evidence_state),
        )

    label = timeline_customer_date_label(requirement)
    if label:
        return label, timeline_customer_helper_text(requirement, date_source, evidence_state)

    return (
        "No due date on file yet",
        "Upload your certificate or enter a date to track this item.",
    )
