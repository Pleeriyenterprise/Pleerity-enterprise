from __future__ import annotations

from typing import Any, Dict, Optional

# Additive semantic states (internal vocabulary)
UPLOADED_UNCONFIRMED = "UPLOADED_UNCONFIRMED"
VERIFICATION_PENDING = "VERIFICATION_PENDING"
DECLARATION_RECORDED = "DECLARATION_RECORDED"
REGISTRATION_RECORDED = "REGISTRATION_RECORDED"
TENANT_DELIVERY_RECORDED = "TENANT_DELIVERY_RECORDED"
PARTIALLY_COMPLETE = "PARTIALLY_COMPLETE"
COMPLETENESS_PENDING = "COMPLETENESS_PENDING"
FOLLOWUP_REQUIRED = "FOLLOWUP_REQUIRED"
OPERATIONALLY_OPEN = "OPERATIONALLY_OPEN"
ASSESSMENT_RECORDED = "ASSESSMENT_RECORDED"
ASSESSMENT_FOLLOWUP_REQUIRED = "ASSESSMENT_FOLLOWUP_REQUIRED"
EXPIRY_REVIEW_REQUIRED = "EXPIRY_REVIEW_REQUIRED"
VERIFIED_CURRENT = "VERIFIED_CURRENT"
VERIFIED_EXPIRED = "VERIFIED_EXPIRED"
MISSING = "MISSING"
REJECTED = "REJECTED"
NOT_REQUIRED = "NOT_REQUIRED"


def derive_semantic_state(
    *,
    authority_state: Optional[str],
    state_reason: Optional[str],
    workflow_class: Optional[str] = None,
    evidence_completeness: Optional[Dict[str, Any]] = None,
) -> str:
    st = str(authority_state or "").strip().upper()
    reason = str(state_reason or "").strip().lower()
    wf = str(workflow_class or "").strip().upper()

    reason_map = {
        "operational_followup_required_condition_standard": OPERATIONALLY_OPEN,
        "multi_evidence_components_incomplete": PARTIALLY_COMPLETE,
        "guided_declaration_not_independently_verified": DECLARATION_RECORDED,
        "registration_tracking_regulator_confirmation_not_verified": REGISTRATION_RECORDED,
        "tenant_delivery_tenant_confirmation_not_verified": TENANT_DELIVERY_RECORDED,
        "external_assessment_remediation_or_followup_unresolved": ASSESSMENT_FOLLOWUP_REQUIRED,
        "document_upload_missing_required_expiry_semantics": EXPIRY_REVIEW_REQUIRED,
        "verified_non_document_evidence": ASSESSMENT_RECORDED if wf == "EXTERNAL_ASSESSMENT_EVIDENCE" else VERIFIED_CURRENT,
    }
    if reason in reason_map:
        return reason_map[reason]

    if st == "VERIFIED_CURRENT":
        return VERIFIED_CURRENT
    if st == "VERIFIED_EXPIRED":
        return VERIFIED_EXPIRED
    if st == "MISSING":
        return MISSING
    if st == "REJECTED":
        return REJECTED
    if st in ("EXTRACTION_COMPLETE_PENDING_CONFIRMATION", "PENDING_ADMIN_REVIEW"):
        return VERIFICATION_PENDING
    if st == "UPLOADED_UNCONFIRMED":
        comp = evidence_completeness if isinstance(evidence_completeness, dict) else {}
        if comp and comp.get("evaluated") is True and comp.get("is_complete") is False:
            return PARTIALLY_COMPLETE
        return UPLOADED_UNCONFIRMED
    if st == "NOT_REQUIRED":
        return NOT_REQUIRED
    return COMPLETENESS_PENDING


def semantic_state_to_legacy_status(semantic_state: Optional[str]) -> str:
    st = str(semantic_state or "").strip().upper()
    if st in (VERIFIED_CURRENT, ASSESSMENT_RECORDED):
        return "COMPLIANT"
    if st == VERIFIED_EXPIRED:
        return "OVERDUE"
    if st == NOT_REQUIRED:
        return "NOT_REQUIRED"
    return "PENDING"


def semantic_state_to_legacy_evidence_state(semantic_state: Optional[str]) -> str:
    st = str(semantic_state or "").strip().upper()
    if st in (VERIFIED_CURRENT, ASSESSMENT_RECORDED):
        return "VERIFIED_CURRENT"
    if st == VERIFIED_EXPIRED:
        return "VERIFIED_EXPIRED"
    if st == MISSING:
        return "MISSING"
    if st == REJECTED:
        return "REJECTED"
    if st == NOT_REQUIRED:
        return "NOT_REQUIRED"
    return "UPLOADED_UNCONFIRMED"


def semantic_state_to_scoring_projection(semantic_state: Optional[str]) -> Dict[str, str]:
    """
    Compatibility mapping only (no scoring redesign).
    """
    return {
        "legacy_status": semantic_state_to_legacy_status(semantic_state),
        "legacy_evidence_state": semantic_state_to_legacy_evidence_state(semantic_state),
    }
