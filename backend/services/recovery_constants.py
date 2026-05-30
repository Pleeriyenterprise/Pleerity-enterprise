"""Canonical operational recovery types and safe action allow-list."""
from __future__ import annotations

from typing import Dict, FrozenSet, List

# Recovery categories (Phase 2A — guidance only)
RECOVERY_CONTRACTOR_NON_RESPONSE = "CONTRACTOR_NON_RESPONSE"
RECOVERY_QUOTE_NEGOTIATION_LOOP = "QUOTE_NEGOTIATION_LOOP"
RECOVERY_VISIT_RESCHEDULE_LOOP = "VISIT_RESCHEDULE_LOOP"
RECOVERY_EVIDENCE_REJECTION_LOOP = "EVIDENCE_REJECTION_LOOP"
RECOVERY_TENANT_ACTIVATION_STALL = "TENANT_ACTIVATION_STALL"
RECOVERY_CONTRACTOR_ACTIVATION_STALL = "CONTRACTOR_ACTIVATION_STALL"
RECOVERY_OVERDUE_REQUIREMENT_STALL = "OVERDUE_REQUIREMENT_STALL"
RECOVERY_WORK_ORDER_ABANDONMENT_RISK = "WORK_ORDER_ABANDONMENT_RISK"
RECOVERY_WAITING_ON_LANDLORD_APPROVAL = "WAITING_ON_LANDLORD_APPROVAL"
RECOVERY_WAITING_ON_CONTRACTOR_ACTION = "WAITING_ON_CONTRACTOR_ACTION"
RECOVERY_WAITING_ON_EVIDENCE_REVIEW = "WAITING_ON_EVIDENCE_REVIEW"
RECOVERY_WORKFLOW_STATE_DRIFT = "WORKFLOW_STATE_DRIFT"
RECOVERY_OPERATIONAL_DEAD_END = "OPERATIONAL_DEAD_END"

ALL_RECOVERY_TYPES: FrozenSet[str] = frozenset(
    {
        RECOVERY_CONTRACTOR_NON_RESPONSE,
        RECOVERY_QUOTE_NEGOTIATION_LOOP,
        RECOVERY_VISIT_RESCHEDULE_LOOP,
        RECOVERY_EVIDENCE_REJECTION_LOOP,
        RECOVERY_TENANT_ACTIVATION_STALL,
        RECOVERY_CONTRACTOR_ACTIVATION_STALL,
        RECOVERY_OVERDUE_REQUIREMENT_STALL,
        RECOVERY_WORK_ORDER_ABANDONMENT_RISK,
        RECOVERY_WAITING_ON_LANDLORD_APPROVAL,
        RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
        RECOVERY_WAITING_ON_EVIDENCE_REVIEW,
        RECOVERY_WORKFLOW_STATE_DRIFT,
        RECOVERY_OPERATIONAL_DEAD_END,
    }
)

CONFIDENCE_LOW = "LOW"
CONFIDENCE_MODERATE = "MODERATE"
CONFIDENCE_HIGH = "HIGH"

# Preparatory recovery actions only — never authority mutations
AUTHORITY_SAFE_RECOVERY_ACTIONS: FrozenSet[str] = frozenset(
    {
        "review_quote",
        "resend_invite",
        "review_contractor",
        "add_alternate_contractor",
        "upload_clearer_document",
        "review_rejected_evidence",
        "request_another_date",
        "open_requirement",
        "contact_support",
        "review_stalled_jobs",
        "confirm_proposed_visit",
        "submit_quote",
        "submit_revised_quote",
        "complete_portal_setup",
        "review_uploaded_evidence",
        "continue_requirement_resolution",
        "open_job",
        "propose_visit",
    }
)

FORBIDDEN_RECOVERY_ACTIONS: FrozenSet[str] = frozenset(
    {
        "approve_quote",
        "assign_contractor",
        "verify_evidence",
        "mark_compliant",
        "close_work_order",
        "confirm_visit_auto",
        "auto_escalate_authority",
    }
)

# Age thresholds (hours)
CONTRACTOR_NON_RESPONSE_HOURS = 24
ABANDONMENT_RISK_HOURS = 72
ABANDONMENT_MIN_NUDGES = 2
