"""
Global attention eligibility for Today / Command Centre / unified tasks.

Queue and score surfaces must not show action-required tasks when authoritative
requirement truth says the obligation is satisfied, unless a current valid reason
(expiry, rejection, follow-up, pending review, etc.) applies.

Authoritative inputs: evidence_authority, semantic_state, governance truth,
truth_presentation_stage, lifecycle_state, expiry/renewal, follow-up state.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any, Dict, Optional, Tuple

from services.compliance_expiry_policy import resolve_expiring_soon_days_for_requirement
from services.requirement_evidence_authority import (
    AUTHORITY_VERSION,
    EA_NOT_REQUIRED,
    EA_PENDING_ADMIN_REVIEW,
    EA_REJECTED,
    EA_VERIFIED_CURRENT,
    EA_VERIFIED_EXPIRED,
    authority_state,
)

# Truth presentation stages that mean no landlord action is required now.
SATISFIED_TRUTH_STAGES = frozenset(
    {
        "verified",
        "declaration_recorded",
        "evidence_recorded",
        "assessment_recorded",
        "recorded_on_file",
    }
)

# Stages that always warrant attention when present.
ATTENTION_TRUTH_STAGES = frozenset(
    {
        "action_required",
        "operational_incomplete",
        "followup_required",
        "platform_verification_pending",
        "escalation_review",
        "collect_evidence",
    }
)

# Operational deficiencies that warrant property-level "Attention needed" (AMBER).
OPERATIONAL_PROPERTY_ATTENTION_REASONS = frozenset(
    {
        "action_required",
        "collect_evidence",
        "additional_action_required",
        "renewal_due",
        "follow_up_required",
        "followup_required",
        "operational_incomplete",
        "legacy_overdue",
        "legacy_expired",
        "legacy_expiring_soon",
        "legacy_missing",
        "legacy_incomplete",
        "legacy_awaiting_user_confirm",
    }
)

# Inbox/today operational urgency — excludes assurance-only review when obligation is met.
OPERATIONAL_INBOX_ATTENTION_REASONS = frozenset(OPERATIONAL_PROPERTY_ATTENTION_REASONS) | frozenset(
    {"rejected", "expired", "escalation_review"}
)

SATISFIED_SEMANTIC_STATES = frozenset(
    {
        "DECLARATION_RECORDED",
        "VERIFIED",
        "COMPLETE",
        "SATISFIED",
        "EVIDENCE_ACCEPTED",
    }
)

SUPPRESSION_SATISFIED_VERIFIED = "satisfied_verified"
SUPPRESSION_EVIDENCE_ACCEPTED = "evidence_accepted"
SUPPRESSION_DECLARATION_RECORDED = "declaration_recorded"
SUPPRESSION_NOT_APPLICABLE = "not_applicable"
SUPPRESSION_NO_CURRENT_ACTION = "no_current_action"
SUPPRESSION_TAKE_ACTION_SUPPRESSED = "take_action_suppressed"


def _parse_due_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def _authority_synced(requirement: Dict[str, Any]) -> bool:
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    return bool(requirement.get("evidence_authority_synced_at")) and int(ea.get("version") or 0) >= AUTHORITY_VERSION


def _expiring_within_window(
    requirement: Dict[str, Any],
    *,
    now: datetime,
    expiring_window_days: Optional[int],
    allow_legacy_due_date: bool = True,
) -> bool:
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    eff = ea.get("effective_expiry_date")
    if eff is None and not allow_legacy_due_date:
        return False
    eff = eff or requirement.get("due_date") or requirement.get("expiry_date")
    dt = _parse_due_date(eff)
    if dt is None:
        return False
    window = int(expiring_window_days if expiring_window_days is not None else resolve_expiring_soon_days_for_requirement(requirement))
    days = (dt - now.date()).days
    return 0 <= days <= window


def _is_expired(requirement: Dict[str, Any], *, now: datetime) -> bool:
    """
    True when an authoritative expiry demands attention.

    Legacy `status=OVERDUE` and system-estimated `due_date` alone must not
    override non-document assessment-on-file truth (see legacy_due_date_blocks).
    """
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    st = str(authority_state(requirement) or ea.get("state") or "").upper()
    if st == EA_VERIFIED_EXPIRED:
        return True

    eff_auth = ea.get("effective_expiry_date")
    if eff_auth:
        dt_auth = _parse_due_date(eff_auth)
        if dt_auth is not None and dt_auth < now.date():
            return True

    from services.requirement_satisfaction_service import legacy_due_date_blocks_renewal_attention

    if not legacy_due_date_blocks_renewal_attention(requirement):
        truth_stage = str(requirement.get("truth_presentation_stage") or "").lower()
        if truth_stage in SATISFIED_TRUTH_STAGES:
            return False
        sem = str(requirement.get("semantic_state") or "").upper()
        if sem in SATISFIED_SEMANTIC_STATES:
            return False
        return False

    status = str(requirement.get("status") or "").upper()
    if status in ("OVERDUE", "EXPIRED"):
        return True
    eff = requirement.get("due_date") or requirement.get("expiry_date")
    dt = _parse_due_date(eff)
    if dt is not None and dt < now.date():
        return True
    return False


def derive_attention_reason(
    requirement: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    expiring_window_days: Optional[int] = None,
) -> Optional[str]:
    """Return a non-empty attention reason when action is legitimately required."""
    row = dict(requirement or {})
    ref = now or datetime.now(timezone.utc)
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    ea_st = str(authority_state(row) or ea.get("state") or "").upper()
    truth_stage = str(row.get("truth_presentation_stage") or "").lower()

    if ea_st == EA_REJECTED:
        return "rejected"
    from services.supporting_evidence_linkage import (
        requirement_structured_satisfaction_suppresses_document_escalation,
    )

    if truth_stage == "escalation_review" or str(row.get("review_owner") or "") == "platform_admin_escalation":
        if requirement_structured_satisfaction_suppresses_document_escalation(row):
            return None
        return "escalation_review"
    if truth_stage == "platform_verification_pending":
        if str(row.get("client_lifecycle_state") or "").upper() in ("VERIFIED", "SATISFIED_UNVERIFIED"):
            return None
        return truth_stage
    if truth_stage == "org_verification_pending":
        return "declaration_recorded"
    if _is_expired(row, now=ref):
        return "expired"
    from services.requirement_satisfaction_service import legacy_due_date_blocks_renewal_attention

    allow_legacy_due = legacy_due_date_blocks_renewal_attention(row)
    if _expiring_within_window(row, now=ref, expiring_window_days=expiring_window_days, allow_legacy_due_date=allow_legacy_due):
        return "renewal_due"
    if truth_stage in ("followup_required", "operational_incomplete"):
        return truth_stage
    if truth_stage == "action_required" or truth_stage == "collect_evidence":
        return truth_stage
    if ea_st in (EA_PENDING_ADMIN_REVIEW, "UPLOADED_UNCONFIRMED", "EXTRACTION_PENDING_CONFIRMATION"):
        if truth_stage in SATISFIED_TRUTH_STAGES:
            return None
        sem_early = str(row.get("semantic_state") or "").upper()
        if sem_early in SATISFIED_SEMANTIC_STATES:
            return None
        return "platform_verification_pending"
    sem = str(row.get("semantic_state") or "").upper()
    if sem in ("COMPLETENESS_PENDING", "FOLLOWUP_REQUIRED", "FOLLOW_UP_REQUIRED"):
        return "follow_up_required"
    ndvs = str(ea.get("non_document_verification_status") or "").upper()
    if ndvs == "PENDING_REVIEW" and str(row.get("review_owner") or "") == "platform_admin":
        return "review_pending"
    window = int(
        expiring_window_days
        if expiring_window_days is not None
        else resolve_expiring_soon_days_for_requirement(row)
    )
    for key in ("follow_up_date", "next_review_date"):
        dt = _parse_due_date(row.get(key))
        if dt is None:
            continue
        days = (dt - ref.date()).days
        if days <= window:
            return "follow_up_required"
    comp = row.get("evidence_completeness") if isinstance(row.get("evidence_completeness"), dict) else {}
    try:
        if int(comp.get("required_missing_count") or 0) > 0:
            return "additional_action_required"
    except Exception:
        pass
    return None


def explain_suppression_reason(requirement: Dict[str, Any]) -> Optional[str]:
    """Human-readable suppression label for diagnostics."""
    eligible, _, suppression = is_requirement_attention_eligible(requirement)
    if eligible or not suppression:
        return None
    return suppression


def suppress_satisfied_requirement(requirement: Dict[str, Any]) -> bool:
    """True when a satisfied requirement should be suppressed from attention surfaces."""
    eligible, _, suppression = is_requirement_attention_eligible(requirement)
    return not eligible and bool(suppression)


def is_requirement_attention_eligible(
    requirement: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    expiring_window_days: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Returns (eligible, attention_reason, suppression_reason).

    suppression_reason is set when eligible is False due to satisfied / N/A truth.
    """
    row = dict(requirement or {})
    ref = now or datetime.now(timezone.utc)

    if row.get("client_surface_visible") is False:
        return False, None, SUPPRESSION_NOT_APPLICABLE

    ta = row.get("take_action") if isinstance(row.get("take_action"), dict) else {}
    if ta.get("suppressed"):
        return False, None, SUPPRESSION_TAKE_ACTION_SUPPRESSED

    lifecycle = str(row.get("client_lifecycle_state") or "").upper()
    status = str(row.get("status") or "").upper()
    if lifecycle in ("NOT_REQUIRED", "NOT_APPLICABLE", "CLOSED") or status in ("NOT_REQUIRED", "NOT_APPLICABLE"):
        return False, None, SUPPRESSION_NOT_APPLICABLE

    attention_reason = derive_attention_reason(
        row,
        now=ref,
        expiring_window_days=expiring_window_days,
    )
    if attention_reason:
        return True, attention_reason, None

    truth_stage = str(row.get("truth_presentation_stage") or "").lower()
    if truth_stage in SATISFIED_TRUTH_STAGES:
        if truth_stage == "declaration_recorded":
            return False, None, SUPPRESSION_DECLARATION_RECORDED
        if truth_stage == "verified":
            return False, None, SUPPRESSION_SATISFIED_VERIFIED
        return False, None, SUPPRESSION_EVIDENCE_ACCEPTED

    ea_st = str(authority_state(row) or "").upper()
    if _authority_synced(row):
        if ea_st in (EA_VERIFIED_CURRENT, EA_NOT_REQUIRED):
            return False, None, SUPPRESSION_SATISFIED_VERIFIED

    sem = str(row.get("semantic_state") or "").upper()
    if sem in SATISFIED_SEMANTIC_STATES and truth_stage not in ATTENTION_TRUTH_STAGES:
        return False, None, SUPPRESSION_EVIDENCE_ACCEPTED

    if lifecycle in ("VERIFIED", "SATISFIED", "COMPLIANT") and not attention_reason:
        return False, None, SUPPRESSION_SATISFIED_VERIFIED

    if truth_stage in ATTENTION_TRUTH_STAGES:
        return True, truth_stage, None

    # Unsynced legacy bridge: only when no authoritative satisfied truth above.
    if not _authority_synced(row):
        if row.get("requirement_satisfied") is True:
            return False, None, SUPPRESSION_NO_CURRENT_ACTION
        if truth_stage in SATISFIED_TRUTH_STAGES:
            return False, None, SUPPRESSION_EVIDENCE_ACCEPTED
        if sem in SATISFIED_SEMANTIC_STATES:
            return False, None, SUPPRESSION_EVIDENCE_ACCEPTED
        if status in ("OVERDUE", "EXPIRED", "EXPIRING_SOON", "PENDING", "MISSING", "INCOMPLETE", "AWAITING_USER_CONFIRM"):
            return True, f"legacy_{status.lower()}", None
        if status in ("VALID", "COMPLIANT", "VERIFIED", "RESOLVED"):
            return False, None, SUPPRESSION_SATISFIED_VERIFIED

    return False, None, SUPPRESSION_NO_CURRENT_ACTION


def validate_attention_against_authority(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnostic payload comparing attention eligibility to authority snapshot."""
    eligible, attention_reason, suppression_reason = is_requirement_attention_eligible(requirement)
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    return {
        "eligible": eligible,
        "attention_reason": attention_reason,
        "suppression_reason": suppression_reason,
        "truth_presentation_stage": requirement.get("truth_presentation_stage"),
        "semantic_state": requirement.get("semantic_state"),
        "authority_state": authority_state(requirement),
        "authority_synced": _authority_synced(requirement),
        "legacy_status": requirement.get("status"),
        "take_action_suppressed": bool(
            isinstance(requirement.get("take_action"), dict) and requirement.get("take_action", {}).get("suppressed")
        ),
        "effective_expiry_date": ea.get("effective_expiry_date"),
    }
