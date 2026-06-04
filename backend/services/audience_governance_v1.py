"""
AUDIENCE-GOVERNANCE-CONVERGENCE-01 — audience-aware interpretation of the same requirement truth.

Does not alter satisfaction truth, scoring formulas, or assurance tiers.
Maps authoritative fields to audience-appropriate labels, buckets, and disclosures.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.report_human_language_v1 import (
    human_assurance_tier_label,
    human_evidence_presence_label,
    human_lifecycle_label,
    human_review_state_label,
)

AUDIENCE_GOVERNANCE_VERSION = "v1"

# --- Audiences ---
AUDIENCE_LANDLORD_OPERATIONAL = "LANDLORD_OPERATIONAL"
AUDIENCE_REGULATOR_EVIDENTIAL = "REGULATOR_EVIDENTIAL"
AUDIENCE_INSURER_LENDER_REVIEW = "INSURER_LENDER_REVIEW"
AUDIENCE_INTERNAL_SUPPORT = "INTERNAL_SUPPORT"
AUDIENCE_IMMUTABLE_AUDIT_ARTIFACT = "IMMUTABLE_AUDIT_ARTIFACT"

ALL_AUDIENCES = frozenset(
    {
        AUDIENCE_LANDLORD_OPERATIONAL,
        AUDIENCE_REGULATOR_EVIDENTIAL,
        AUDIENCE_INSURER_LENDER_REVIEW,
        AUDIENCE_INTERNAL_SUPPORT,
        AUDIENCE_IMMUTABLE_AUDIT_ARTIFACT,
    }
)

# --- Export PDF section buckets (regulator / immutable lens) ---
EXPORT_SECTION_UNRESOLVED = "unresolved_obligations"
EXPORT_SECTION_RECORDED_NOT_VERIFIED = "recorded_not_verified"
EXPORT_SECTION_AWAITING_REVIEW = "awaiting_review"
EXPORT_SECTION_VERIFIED = "verified_accepted"
EXPORT_SECTION_NONE = "none"

# --- Disclosure / unresolved taxonomy ---
UNRESOLVED_BUCKET_NONE = "none"
UNRESOLVED_BUCKET_ACTION_REQUIRED = "action_required"
UNRESOLVED_BUCKET_REVIEW_PENDING = "review_pending"
UNRESOLVED_BUCKET_RECORDED_NOT_VERIFIED = "recorded_not_verified"
UNRESOLVED_BUCKET_MISSING_EVIDENCE = "missing_evidence"

DISCLOSURE_NONE = "none"
DISCLOSURE_RECORDED_NOT_VERIFIED = "recorded_not_verified"
DISCLOSURE_PENDING_REVIEW = "pending_review"
DISCLOSURE_ASSURANCE_LIMITATION = "assurance_limitation"
DISCLOSURE_OPERATIONAL_COMPLETE = "operational_complete"

ACTION_VISIBILITY_NONE = "none"
ACTION_VISIBILITY_OPTIONAL = "optional"
ACTION_VISIBILITY_REQUIRED = "required"

AUDIENCE_EXPORT_PREAMBLE = (
    "This report separates operational completion from evidential assurance. "
    "Some obligations may be recorded on file without independent verification. "
    "Those items are not shown as missing, but they are disclosed separately for review purposes."
)

AUDIENCE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    AUDIENCE_LANDLORD_OPERATIONAL: {
        "label": "Landlord operational view",
        "purpose": "Day-to-day action management; reduce false panic; show next steps only.",
        "strictness": "calm",
        "provisional_action_suppressing": True,
        "show_assurance_limitation_inline": "when_useful",
    },
    AUDIENCE_REGULATOR_EVIDENTIAL: {
        "label": "Regulator evidential view",
        "purpose": "Conservative evidence interpretation; assurance limitations disclosed.",
        "strictness": "conservative",
        "provisional_action_suppressing": False,
        "show_assurance_limitation_inline": "always",
    },
    AUDIENCE_INSURER_LENDER_REVIEW: {
        "label": "Insurer / lender review",
        "purpose": "Risk and assurance visibility; unresolved exposure clarity.",
        "strictness": "conservative",
        "provisional_action_suppressing": False,
        "show_assurance_limitation_inline": "always",
    },
    AUDIENCE_INTERNAL_SUPPORT: {
        "label": "Internal support",
        "purpose": "Support and admin diagnostics with readable detail.",
        "strictness": "diagnostic",
        "provisional_action_suppressing": True,
        "show_assurance_limitation_inline": "always",
    },
    AUDIENCE_IMMUTABLE_AUDIT_ARTIFACT: {
        "label": "Immutable audit artifact",
        "purpose": "Frozen point-in-time record for historical defensibility.",
        "strictness": "conservative",
        "provisional_action_suppressing": False,
        "show_assurance_limitation_inline": "always",
    },
}


def _life(row: Dict[str, Any]) -> str:
    return str(row.get("client_lifecycle_state") or row.get("lifecycle_state") or "").strip().upper()


def _tier(row: Dict[str, Any]) -> str:
    return str(row.get("assurance_tier") or "").strip().upper()


def _truth(row: Dict[str, Any]) -> str:
    return str(row.get("truth_presentation_stage") or "").lower()


def _satisfied(row: Dict[str, Any]) -> bool:
    if row.get("requirement_satisfied") is True:
        return True
    if row.get("requirement_satisfied") is False:
        return False
    from services.requirement_satisfaction_service import is_requirement_satisfied

    return is_requirement_satisfied(row)


def _attention_eligible(row: Dict[str, Any]) -> bool:
    if row.get("requirement_attention_eligible") is True:
        return True
    if row.get("requirement_attention_eligible") is False:
        return False
    from services.requirement_attention_eligibility_service import is_requirement_attention_eligible

    return bool(is_requirement_attention_eligible(row)[0])


def _attention_reason(row: Dict[str, Any]) -> str:
    r = row.get("requirement_attention_reason")
    if r:
        return str(r).strip().lower()
    from services.requirement_attention_eligibility_service import is_requirement_attention_eligible

    _, reason, _ = is_requirement_attention_eligible(row)
    return str(reason or "").strip().lower()


def _is_verified_row(row: Dict[str, Any]) -> bool:
    life = _life(row)
    if life == "VERIFIED":
        return True
    if _truth(row) == "verified":
        return True
    tier = _tier(row)
    if tier in ("VERIFIED_DOCUMENT", "VERIFIED", "PLATFORM_VERIFIED"):
        return True
    return False


def _is_recorded_not_verified_row(row: Dict[str, Any]) -> bool:
    if _is_verified_row(row):
        return False
    if not _satisfied(row):
        return False
    life = _life(row)
    tier = _tier(row)
    if life == "SATISFIED_UNVERIFIED" or tier == "SELF_RECORDED":
        return True
    if _truth(row) in ("declaration_recorded", "assessment_recorded", "evidence_recorded", "recorded_on_file"):
        return True
    return False


def _is_awaiting_review_row(row: Dict[str, Any]) -> bool:
    life = _life(row)
    if life == "PENDING_REVIEW":
        return True
    if _truth(row) in ("platform_verification_pending", "org_verification_pending"):
        return True
    if _attention_reason(row) in ("platform_verification_pending", "review_pending"):
        return True
    return False


def _is_true_unresolved_row(
    row: Dict[str, Any],
    *,
    property_doc: Optional[dict],
    client_doc: dict,
) -> bool:
    """Action-required obligations — not self-recorded satisfaction exposure."""
    from utils.expiry_utils import get_computed_status

    life = _life(row)
    if life in ("NOT_APPLICABLE", "VERIFIED"):
        return False
    if _is_recorded_not_verified_row(row) and not _attention_eligible(row):
        return False
    if _is_awaiting_review_row(row) and not _attention_eligible(row):
        return False

    if _attention_eligible(row):
        reason = _attention_reason(row)
        if reason in (
            "followup_required",
            "follow_up_required",
            "operational_incomplete",
            "expired",
            "renewal_due",
            "action_required",
            "collect_evidence",
            "rejected",
            "escalation_review",
        ):
            return True
        if reason in ("platform_verification_pending", "review_pending"):
            return False

    if life == "ACTION_REQUIRED":
        return True
    cs = (get_computed_status(row, property_doc=property_doc, client_doc=client_doc) or "").upper()
    if cs in ("OVERDUE", "EXPIRED", "MISSING"):
        return True
    if cs in ("PENDING",):
        from services.requirement_satisfaction_service import row_counts_as_missing_evidence

        return row_counts_as_missing_evidence(row)
    if cs == "EXPIRING_SOON" and _attention_eligible(row):
        return True
    return False


def classify_export_section_bucket(
    row: Dict[str, Any],
    *,
    property_doc: Optional[dict] = None,
    client_doc: Optional[dict] = None,
    audience: str = AUDIENCE_REGULATOR_EVIDENTIAL,
) -> str:
    """Which governed PDF export section should include this row (regulator/immutable lens)."""
    life = _life(row)
    if life in ("NOT_APPLICABLE", "NOT_REQUIRED"):
        return EXPORT_SECTION_NONE

    if _is_true_unresolved_row(row, property_doc=property_doc, client_doc=client_doc or {}):
        return EXPORT_SECTION_UNRESOLVED
    if _is_awaiting_review_row(row):
        return EXPORT_SECTION_AWAITING_REVIEW
    if _is_verified_row(row) and _satisfied(row):
        return EXPORT_SECTION_VERIFIED
    if _is_recorded_not_verified_row(row):
        return EXPORT_SECTION_RECORDED_NOT_VERIFIED
    return EXPORT_SECTION_NONE


def interpret_requirement_for_audience(
    row: Dict[str, Any],
    audience: str,
    *,
    property_doc: Optional[dict] = None,
    client_doc: Optional[dict] = None,
) -> Dict[str, Any]:
    """Governed presentation fields for one requirement row."""
    aud = audience if audience in ALL_AUDIENCES else AUDIENCE_LANDLORD_OPERATIONAL
    life = _life(row)
    tier = _tier(row)
    satisfied = _satisfied(row)
    attention = _attention_eligible(row)
    reason = _attention_reason(row)
    verified = _is_verified_row(row)
    recorded_nv = _is_recorded_not_verified_row(row)
    awaiting = _is_awaiting_review_row(row)
    unresolved = _is_true_unresolved_row(row, property_doc=property_doc, client_doc=client_doc or {})

    # Defaults
    status_label = human_lifecycle_label(row)
    status_description = ""
    action_visibility = ACTION_VISIBILITY_NONE
    unresolved_bucket = UNRESOLVED_BUCKET_NONE
    disclosure_bucket = DISCLOSURE_NONE
    score_explanation_bucket = "standard"
    regulator_note = ""
    landlord_next_action = ""
    evidence_sufficiency = "unknown"

    if aud == AUDIENCE_LANDLORD_OPERATIONAL:
        if verified and satisfied:
            status_label = "Verified"
            status_description = "Evidence verified — no immediate action required."
            evidence_sufficiency = "verified"
            disclosure_bucket = DISCLOSURE_OPERATIONAL_COMPLETE
        elif recorded_nv and satisfied and not attention:
            status_label = "Recorded on file"
            status_description = "Recorded on file — no immediate action required unless renewal or follow-up applies."
            evidence_sufficiency = "recorded_not_verified"
            disclosure_bucket = DISCLOSURE_ASSURANCE_LIMITATION
        elif awaiting:
            status_label = "Awaiting review"
            status_description = "Submitted — awaiting platform review. No upload action unless rejected."
            action_visibility = ACTION_VISIBILITY_OPTIONAL
            unresolved_bucket = UNRESOLVED_BUCKET_REVIEW_PENDING
            disclosure_bucket = DISCLOSURE_PENDING_REVIEW
        elif unresolved or attention:
            status_label = "Action required" if life == "ACTION_REQUIRED" else status_label
            status_description = "This obligation needs your attention."
            action_visibility = ACTION_VISIBILITY_REQUIRED
            unresolved_bucket = (
                UNRESOLVED_BUCKET_MISSING_EVIDENCE
                if reason in ("collect_evidence", "missing", "legacy_missing")
                else UNRESOLVED_BUCKET_ACTION_REQUIRED
            )
        elif satisfied:
            status_label = "Recorded on file"
            status_description = "No immediate action required."
            evidence_sufficiency = "recorded"
        landlord_next_action = (
            "No immediate action required"
            if action_visibility == ACTION_VISIBILITY_NONE and satisfied
            else "Review requirement details in the portal"
        )
        score_explanation_bucket = (
            "assurance_fraction"
            if recorded_nv
            else "verified" if verified else "standard"
        )

    elif aud in (AUDIENCE_REGULATOR_EVIDENTIAL, AUDIENCE_INSURER_LENDER_REVIEW, AUDIENCE_IMMUTABLE_AUDIT_ARTIFACT):
        if verified and satisfied:
            status_label = "Verified / accepted evidence"
            status_description = "Platform-accepted evidence on file at generation time."
            evidence_sufficiency = "verified"
            disclosure_bucket = DISCLOSURE_OPERATIONAL_COMPLETE
            regulator_note = "Accepted for scoring where policy applies."
        elif recorded_nv:
            status_label = "Recorded, not independently verified"
            status_description = (
                "Self-recorded or declaration-based satisfaction — not external statutory verification."
            )
            evidence_sufficiency = "recorded_not_verified"
            unresolved_bucket = UNRESOLVED_BUCKET_RECORDED_NOT_VERIFIED
            disclosure_bucket = DISCLOSURE_RECORDED_NOT_VERIFIED
            regulator_note = "Disclosed separately from missing evidence; assurance limitation applies."
        elif awaiting:
            status_label = "Review pending"
            status_description = "Evidence submitted — decision pending."
            unresolved_bucket = UNRESOLVED_BUCKET_REVIEW_PENDING
            disclosure_bucket = DISCLOSURE_PENDING_REVIEW
            regulator_note = "Not equivalent to verified acceptance."
        elif unresolved:
            status_label = "Unresolved — action or evidence required"
            status_description = "Missing, expired, rejected, or follow-up not completed."
            unresolved_bucket = UNRESOLVED_BUCKET_ACTION_REQUIRED
            disclosure_bucket = DISCLOSURE_ASSURANCE_LIMITATION
        if aud == AUDIENCE_IMMUTABLE_AUDIT_ARTIFACT and recorded_nv:
            status_label = "Recorded at generation time"
            regulator_note = "Self-recorded assurance; not independent verification."

    elif aud == AUDIENCE_INTERNAL_SUPPORT:
        status_label = human_lifecycle_label(row) or life or "—"
        status_description = (
            f"satisfied={satisfied} attention={attention} reason={reason or '—'} "
            f"tier={tier or '—'} export_bucket={classify_export_section_bucket(row, property_doc=property_doc, client_doc=client_doc)}"
        )
        evidence_sufficiency = "diagnostic"

    export_section = classify_export_section_bucket(
        row, property_doc=property_doc, client_doc=client_doc, audience=AUDIENCE_REGULATOR_EVIDENTIAL
    )

    return {
        "audience": aud,
        "audience_status_label": status_label,
        "audience_status_description": status_description,
        "action_visibility": action_visibility,
        "unresolved_bucket": unresolved_bucket,
        "disclosure_bucket": disclosure_bucket,
        "score_explanation_bucket": score_explanation_bucket,
        "regulator_note": regulator_note,
        "landlord_next_action": landlord_next_action,
        "evidence_sufficiency_label": evidence_sufficiency,
        "export_section_bucket": export_section,
        "operational_status": _operational_status_csv(row),
        "evidential_assurance": _evidential_assurance_csv(row),
        "action_required": "yes" if action_visibility == ACTION_VISIBILITY_REQUIRED else "no",
        "review_state": human_review_state_label(row),
    }


def _operational_status_csv(row: Dict[str, Any]) -> str:
    if _is_true_unresolved_row(row, property_doc=None, client_doc={}):
        return "action_required"
    if _is_awaiting_review_row(row):
        return "awaiting_review"
    if _is_verified_row(row) and _satisfied(row):
        return "verified"
    if _is_recorded_not_verified_row(row):
        return "recorded_on_file"
    return "in_progress"


def _evidential_assurance_csv(row: Dict[str, Any]) -> str:
    if _is_verified_row(row):
        return "verified"
    if _is_recorded_not_verified_row(row):
        return "recorded_not_independently_verified"
    if _is_awaiting_review_row(row):
        return "awaiting_review"
    if _is_true_unresolved_row(row, property_doc=None, client_doc={}):
        return "missing_or_blocked"
    return "unknown"


def audience_export_preamble_paragraph(audience: str = AUDIENCE_REGULATOR_EVIDENTIAL) -> str:
    if audience in (AUDIENCE_REGULATOR_EVIDENTIAL, AUDIENCE_INSURER_LENDER_REVIEW, AUDIENCE_IMMUTABLE_AUDIT_ARTIFACT):
        return AUDIENCE_EXPORT_PREAMBLE
    return ""


def score_explanation_audience_lines(audience: str = AUDIENCE_REGULATOR_EVIDENTIAL) -> List[str]:
    if audience == AUDIENCE_LANDLORD_OPERATIONAL:
        return [
            "Items recorded on file do not always need immediate action.",
            "The score may be lower where evidence is self-recorded or awaiting review — that does not always mean upload is required now.",
        ]
    return [
        "Items recorded on file are not the same as independently verified evidence.",
        "The score reflects assurance level as well as task completion.",
    ]


def audience_model_export() -> Dict[str, Any]:
    return {
        "version": AUDIENCE_GOVERNANCE_VERSION,
        "audiences": AUDIENCE_DEFINITIONS,
        "export_sections": [
            EXPORT_SECTION_UNRESOLVED,
            EXPORT_SECTION_RECORDED_NOT_VERIFIED,
            EXPORT_SECTION_AWAITING_REVIEW,
            EXPORT_SECTION_VERIFIED,
        ],
    }
