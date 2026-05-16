"""
Canonical derived operational document state for client/admin presentation.

Additive projection only — does not replace persisted evidence or extraction fields.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state

MATCH_CONFIRMED = "MATCH_CONFIRMED"


class DocumentOperationalState(str, Enum):
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"
    EVIDENCE_ACCEPTED_ON_FILE = "EVIDENCE_ACCEPTED_ON_FILE"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    EVIDENCE_SUPERSEDED = "EVIDENCE_SUPERSEDED"
    ADMIN_REVIEW_PENDING = "ADMIN_REVIEW_PENDING"
    MATCH_RESOLVED_VERIFICATION_PENDING = "MATCH_RESOLVED_VERIFICATION_PENDING"
    EXTRACTION_CONFIRMATION_PENDING = "EXTRACTION_CONFIRMATION_PENDING"
    EXTRACTION_IN_PROGRESS = "EXTRACTION_IN_PROGRESS"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    UPLOADED_AWAITING_REVIEW = "UPLOADED_AWAITING_REVIEW"


OPERATIONAL_LABELS: Dict[str, str] = {
    DocumentOperationalState.EVIDENCE_REJECTED.value: "Rejected",
    DocumentOperationalState.EXTERNALLY_VERIFIED.value: "Externally verified",
    DocumentOperationalState.EVIDENCE_ACCEPTED_ON_FILE.value: "Accepted on file (not externally verified)",
    DocumentOperationalState.EVIDENCE_VERIFIED.value: "Verified",
    DocumentOperationalState.EVIDENCE_EXPIRED.value: "Expired",
    DocumentOperationalState.EVIDENCE_SUPERSEDED.value: "Superseded",
    DocumentOperationalState.ADMIN_REVIEW_PENDING.value: "Awaiting admin review",
    DocumentOperationalState.MATCH_RESOLVED_VERIFICATION_PENDING.value: "Requirement linked — verification still pending",
    DocumentOperationalState.EXTRACTION_CONFIRMATION_PENDING.value: "AI data needs review",
    DocumentOperationalState.EXTRACTION_IN_PROGRESS.value: "Extraction in progress",
    DocumentOperationalState.EXTRACTION_FAILED.value: "Extraction failed",
    DocumentOperationalState.UPLOADED_AWAITING_REVIEW.value: "Uploaded — awaiting review",
}


def is_admin_evidence_accepted(doc: Dict[str, Any]) -> bool:
    review = effective_evidence_review_state(doc)
    if review in ("REJECTED", "EXPIRED", "SUPERSEDED"):
        return False
    if review in ("ACCEPTED_UNVERIFIED", "VERIFIED"):
        return True
    tier = effective_assurance_tier(doc)
    if tier in ("EXTERNALLY_VERIFIED", "HUMAN_ACCEPTED"):
        return True
    return str(doc.get("status") or "").upper() == "VERIFIED"


def is_admin_evidence_rejected(doc: Dict[str, Any]) -> bool:
    review = effective_evidence_review_state(doc)
    if review == "REJECTED":
        return True
    tier = effective_assurance_tier(doc)
    if tier == "REJECTED":
        return True
    return str(doc.get("status") or "").upper() == "REJECTED"


def has_extraction_confirmation_superseded(doc: Dict[str, Any]) -> bool:
    if doc.get("extraction_confirmation_superseded") is True:
        return True
    ai = doc.get("ai_extraction")
    if isinstance(ai, dict) and ai.get("superseded_by_admin_decision"):
        return True
    return False


def infer_supersession_decision(doc: Dict[str, Any]) -> Optional[str]:
    """Return accepted | rejected when evidence review outcome supersedes extraction confirmation."""
    if is_admin_evidence_rejected(doc):
        return "rejected"
    if is_admin_evidence_accepted(doc):
        return "accepted"
    return None


def is_extraction_confirmation_unresolved(doc: Dict[str, Any]) -> bool:
    """True when extraction fields still imply a pending apply/confirm step."""
    if has_extraction_confirmation_superseded(doc):
        return False
    rs = str((doc.get("ai_extraction") or {}).get("review_status") or "").lower()
    if rs in ("approved", "rejected"):
        return False
    extraction_status = str(doc.get("extraction_status") or "").upper()
    if extraction_status in ("CONFIRMED", "REJECTED"):
        return False
    if extraction_status in ("EXTRACTED", "NEEDS_REVIEW"):
        return True
    review_status = str((doc.get("ai_extraction") or {}).get("review_status") or "").upper()
    if not review_status or review_status in ("PENDING", "AWAITING_USER_CONFIRM"):
        ai = doc.get("ai_extraction") if isinstance(doc.get("ai_extraction"), dict) else {}
        has_ai_data = ai.get("status") == "completed" and ai.get("data")
        return bool(has_ai_data or doc.get("extraction_id"))
    return False


def is_match_resolved_pending_verification(doc: Dict[str, Any]) -> bool:
    """Match/link resolved administratively but evidence not yet verified/accepted."""
    if is_admin_evidence_accepted(doc) or is_admin_evidence_rejected(doc):
        return False
    if doc.get("requirement_evidence_mismatch") is True:
        return False
    if not doc.get("requirement_id"):
        return False
    match_outcome = str(doc.get("reviewed_match_outcome") or doc.get("match_outcome") or "").upper()
    return match_outcome == MATCH_CONFIRMED


def document_needs_extraction_reconciliation(doc: Dict[str, Any]) -> bool:
    """True when a persisted supersession/reconciliation patch should be applied."""
    decision = infer_supersession_decision(doc)
    if not decision:
        return False
    if is_extraction_confirmation_unresolved(doc):
        return True
    if not has_extraction_confirmation_superseded(doc):
        return True
    return not _extraction_fields_aligned(doc, decision)


def _extraction_fields_aligned(doc: Dict[str, Any], decision: str) -> bool:
    expected_status = "CONFIRMED" if decision == "accepted" else "REJECTED"
    expected_review = "approved" if decision == "accepted" else "rejected"
    if str(doc.get("extraction_status") or "").upper() != expected_status:
        return False
    ai = doc.get("ai_extraction") if isinstance(doc.get("ai_extraction"), dict) else {}
    if str(ai.get("review_status") or "").lower() != expected_review:
        return False
    return has_extraction_confirmation_superseded(doc)


def derive_document_operational_state(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive operational presentation fields (not persisted by default).
    Returns document_operational_state, document_operational_label, document_operational_reason_codes.
    """
    reason_codes: List[str] = []
    review = effective_evidence_review_state(doc)
    tier = effective_assurance_tier(doc)

    if is_admin_evidence_rejected(doc):
        reason_codes.append("EVIDENCE_DECISION_REJECTED")
        state = DocumentOperationalState.EVIDENCE_REJECTED
    elif tier == "EXTERNALLY_VERIFIED":
        reason_codes.append("EXTERNAL_VERIFICATION")
        state = DocumentOperationalState.EXTERNALLY_VERIFIED
    elif review == "VERIFIED":
        reason_codes.append("EVIDENCE_VERIFIED")
        state = DocumentOperationalState.EVIDENCE_VERIFIED
    elif review == "ACCEPTED_UNVERIFIED" or is_admin_evidence_accepted(doc):
        reason_codes.append("EVIDENCE_ACCEPTED_ON_FILE")
        state = DocumentOperationalState.EVIDENCE_ACCEPTED_ON_FILE
    elif review == "EXPIRED":
        reason_codes.append("EVIDENCE_EXPIRED")
        state = DocumentOperationalState.EVIDENCE_EXPIRED
    elif review == "SUPERSEDED":
        reason_codes.append("EVIDENCE_SUPERSEDED")
        state = DocumentOperationalState.EVIDENCE_SUPERSEDED
    elif review in ("UNDER_REVIEW", "NEEDS_INFORMATION"):
        reason_codes.append("ADMIN_REVIEW_OPEN")
        state = DocumentOperationalState.ADMIN_REVIEW_PENDING
    elif is_match_resolved_pending_verification(doc):
        reason_codes.append("MATCH_RESOLVED_NOT_VERIFIED")
        state = DocumentOperationalState.MATCH_RESOLVED_VERIFICATION_PENDING
    elif is_extraction_confirmation_unresolved(doc) and not is_admin_evidence_accepted(doc):
        reason_codes.append("EXTRACTION_AWAITING_CONFIRMATION")
        state = DocumentOperationalState.EXTRACTION_CONFIRMATION_PENDING
    elif str(doc.get("extraction_status") or "").upper() == "FAILED" or (
        isinstance(doc.get("ai_extraction"), dict) and doc["ai_extraction"].get("status") == "failed"
    ):
        reason_codes.append("EXTRACTION_FAILED")
        state = DocumentOperationalState.EXTRACTION_FAILED
    elif str(doc.get("extraction_status") or "").upper() == "PENDING" or (
        isinstance(doc.get("ai_extraction"), dict) and doc["ai_extraction"].get("status") == "pending"
    ):
        reason_codes.append("EXTRACTION_RUNNING")
        state = DocumentOperationalState.EXTRACTION_IN_PROGRESS
    else:
        reason_codes.append("UPLOADED")
        state = DocumentOperationalState.UPLOADED_AWAITING_REVIEW

    if has_extraction_confirmation_superseded(doc):
        reason_codes.append("EXTRACTION_CONFIRMATION_SUPERSEDED")
    if doc.get("requirement_evidence_mismatch") is True:
        reason_codes.append("REQUIREMENT_EVIDENCE_MISMATCH")
    if doc.get("extraction_reconciliation_at"):
        reason_codes.append("EXTRACTION_RECONCILED")

    label = OPERATIONAL_LABELS.get(state.value, state.value.replace("_", " ").title())
    return {
        "document_operational_state": state.value,
        "document_operational_label": label,
        "document_operational_reason_codes": reason_codes,
    }


def attach_document_operational_projection(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate doc in place with derived operational fields; return doc."""
    projection = derive_document_operational_state(doc)
    doc.update(projection)
    return doc


def operational_extraction_review_pending(doc: Dict[str, Any]) -> bool:
    """Whether client should prompt for extraction apply/confirm (canonical)."""
    op = derive_document_operational_state(doc)
    return op["document_operational_state"] == DocumentOperationalState.EXTRACTION_CONFIRMATION_PENDING.value


def operational_show_review_and_apply(doc: Dict[str, Any]) -> bool:
    if operational_extraction_review_pending(doc):
        return True
    has_queue = str(doc.get("extraction_status") or "").upper() in ("EXTRACTED", "NEEDS_REVIEW")
    has_ai = isinstance(doc.get("ai_extraction"), dict) and bool(doc.get("ai_extraction", {}).get("data"))
    return bool(has_queue or has_ai) and operational_extraction_review_pending(doc)
