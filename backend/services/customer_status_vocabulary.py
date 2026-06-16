"""
Customer-facing obligation status vocabulary — mirror of docs/governance/CUSTOMER_STATUS_VOCABULARY.json.

PR-1A: Import-only constants. No runtime wiring. No projector usage.
Authority: docs/governance/REVIEW_POLICY_VOCABULARY.md (human), CUSTOMER_STATUS_VOCABULARY.json (machine).
"""
from __future__ import annotations

from typing import Final, Tuple

VOCABULARY_VERSION: Final[str] = "1.0.0"
VOCABULARY_EFFECTIVE_DATE: Final[str] = "2026-06-02"

# Primary status keys (machine enum)
ACTION_REQUIRED: Final[str] = "action_required"
SUBMITTED: Final[str] = "submitted"
UPLOADED: Final[str] = "uploaded"
UNDER_REVIEW: Final[str] = "under_review"
RECORDED: Final[str] = "recorded"
SATISFIED: Final[str] = "satisfied"
VERIFIED: Final[str] = "verified"
REJECTED: Final[str] = "rejected"
FOLLOWUP_REQUIRED: Final[str] = "followup_required"
ADDITIONAL_ACTION_REQUIRED: Final[str] = "additional_action_required"
EXPIRY_DATE_NEEDED: Final[str] = "expiry_date_needed"
ESCALATION_REQUIRED: Final[str] = "escalation_required"
ESCALATION_RESOLVED: Final[str] = "escalation_resolved"

CUSTOMER_STATUS_KEYS: Final[Tuple[str, ...]] = (
    ACTION_REQUIRED,
    SUBMITTED,
    UPLOADED,
    UNDER_REVIEW,
    RECORDED,
    SATISFIED,
    VERIFIED,
    REJECTED,
    FOLLOWUP_REQUIRED,
    ADDITIONAL_ACTION_REQUIRED,
    EXPIRY_DATE_NEEDED,
    ESCALATION_REQUIRED,
    ESCALATION_RESOLVED,
)

CUSTOMER_STATUS_LABEL_BY_KEY: Final[dict[str, str]] = {
    ACTION_REQUIRED: "Action required",
    SUBMITTED: "Submitted",
    UPLOADED: "Uploaded",
    UNDER_REVIEW: "Under review",
    RECORDED: "Recorded on file",
    SATISFIED: "Satisfied",
    VERIFIED: "Verified",
    REJECTED: "Rejected",
    FOLLOWUP_REQUIRED: "Follow-up required",
    ADDITIONAL_ACTION_REQUIRED: "Additional action required",
    EXPIRY_DATE_NEEDED: "Expiry date needed",
    ESCALATION_REQUIRED: "Escalation required",
    ESCALATION_RESOLVED: "Issue resolved",
}

CANONICAL_OBLIGATION_STATUS_LADDER: Final[Tuple[str, ...]] = CUSTOMER_STATUS_KEYS

CLASS_A_LIFECYCLE_STATES: Final[Tuple[str, ...]] = (
    ACTION_REQUIRED,
    SUBMITTED,
    RECORDED,
    SATISFIED,
)

CLASS_B_LIFECYCLE_STATES: Final[Tuple[str, ...]] = (
    ACTION_REQUIRED,
    UPLOADED,
    UNDER_REVIEW,
    VERIFIED,
    REJECTED,
)

CLASS_C_LIFECYCLE_STATES: Final[Tuple[str, ...]] = (
    ESCALATION_REQUIRED,
    ESCALATION_RESOLVED,
)

CLASS_A_FORBIDDEN_PRIMARY_BADGES: Final[Tuple[str, ...]] = (
    UPLOADED,
    UNDER_REVIEW,
    VERIFIED,
    REJECTED,
)

CLASS_B_FORBIDDEN_PRIMARY_BADGES: Final[Tuple[str, ...]] = (
    SUBMITTED,
    RECORDED,
    SATISFIED,
)

OVERLAY_PRECEDENCE: Final[Tuple[str, ...]] = (
    ESCALATION_REQUIRED,
    REJECTED,
    UNDER_REVIEW,
    EXPIRY_DATE_NEEDED,
    FOLLOWUP_REQUIRED,
    ADDITIONAL_ACTION_REQUIRED,
    "base_path_state",
)

RETIRED_REVIEW_PHRASES: Final[Tuple[str, ...]] = (
    "Review pending",
    "Pending review",
    "Platform review required",
    "Awaiting platform review",
    "Escalated for platform review",
    "Platform verification pending",
    "Awaiting review",
    "Evidence review pending",
    "Evidence submitted and awaiting review",
    "Verification required",
    "Awaiting approval",
    "Submission is awaiting review — not yet verified",
    "Awaiting review — submission not yet verified",
    "Submission on file — awaiting review",
    "Your submission is waiting for review",
    "no upload needed while review is in progress",
    "PLATFORM_REVIEWED assurance title: Awaiting platform review",
    "pending_review document visibility bucket label",
    "PENDING_REVIEW in reportHumanLanguage",
)

PRESENTATION_STAGE_TO_STATUS_KEY: Final[dict[str, str]] = {
    "declaration_recorded": RECORDED,
    "assessment_recorded": RECORDED,
    "platform_verification_pending": UNDER_REVIEW,
    "escalation_review": ESCALATION_REQUIRED,
    "followup_required": FOLLOWUP_REQUIRED,
    "operational_incomplete": ADDITIONAL_ACTION_REQUIRED,
    "expiry_confirmation_required": EXPIRY_DATE_NEEDED,
    "verified": VERIFIED,
    "collect_evidence": ACTION_REQUIRED,
    "action_required": ACTION_REQUIRED,
}

REVIEW_POLICY_MODEL: Final[str] = "Model A — single human review workflow + exception escalation"

GATE_EMIT_UNDER_REVIEW: Final[str] = (
    "obligation_class=B AND document.status=UPLOADED AND in_pending_verification_queue"
)
GATE_EMIT_RECORDED: Final[str] = (
    "obligation_class=A AND has_persisted_submission AND NOT escalation_required"
)
GATE_EMIT_ESCALATION_REQUIRED: Final[str] = (
    "exception_trigger_active AND admin_resolution_path_exists"
)

IMPLEMENTATION_SEQUENCE_RULE: Final[str] = "No S2 before S1 completion"
