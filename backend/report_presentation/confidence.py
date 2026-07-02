"""Confidence and assurance presentation."""

from __future__ import annotations

from typing import Any, Dict

from services.report_human_language_v1 import (
    human_assurance_tier_label,
    human_date_confidence_label,
    human_evidence_presence_label,
)


def present_confidence_block(row: Dict[str, Any]) -> Dict[str, str]:
    """Explain how confident the report is in an obligation conclusion."""
    assurance = human_assurance_tier_label(row)
    presence = human_evidence_presence_label(row)
    date_conf = human_date_confidence_label(row)
    lifecycle = str(row.get("client_lifecycle_state") or row.get("lifecycle_state") or "").upper()

    conclusion_confidence = "High"
    note = "Verified evidence supports this conclusion."
    if lifecycle == "PENDING_REVIEW" or "review" in assurance.lower():
        conclusion_confidence = "Moderate"
        note = "Evidence is on file but independent verification is still pending."
    elif lifecycle == "SATISFIED_UNVERIFIED" or "self" in assurance.lower():
        conclusion_confidence = "Moderate"
        note = "Information is self-declared or recorded on file — verification may still be required."
    elif presence in ("None", "Missing evidence") or lifecycle == "ACTION_REQUIRED":
        conclusion_confidence = "Low"
        note = "Supporting evidence is missing or incomplete for this obligation."
    elif date_conf == "Estimated":
        conclusion_confidence = "Moderate"
        note = "Dates are estimated — upload verified certificates to confirm."

    return {
        "assurance_label": assurance,
        "evidence_presence": presence,
        "date_confidence": date_conf,
        "conclusion_confidence": conclusion_confidence,
        "confidence_note": note,
    }
