"""
Adapter between Evidence Review V2 fields and legacy scoring that counted DocumentStatus.VERIFIED only.

When FEATURE_EVIDENCE_REVIEW_V2 is disabled, behaviour matches legacy (status VERIFIED counts).

When enabled, positive compliance credit requires acceptable evidence_review_state / assurance_tier.
"""

from __future__ import annotations

from typing import Any, Dict

from models.evidence_review import AssuranceTier, EvidenceReviewState
from services.evidence_review_config import is_feature_evidence_review_v2
from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state


def evidence_review_contributes_positive_credit(doc: Dict[str, Any]) -> bool:
    """Whether this document should count toward verified-document coverage metrics."""
    if not is_feature_evidence_review_v2():
        return (doc.get("status") or "").upper() == "VERIFIED"

    if (doc.get("status") or "").upper() != "VERIFIED":
        return False

    rs = effective_evidence_review_state(doc)
    if rs in (
        EvidenceReviewState.REJECTED.value,
        EvidenceReviewState.EXPIRED.value,
        EvidenceReviewState.NEEDS_INFORMATION.value,
        EvidenceReviewState.UPLOADED.value,
        EvidenceReviewState.UNDER_REVIEW.value,
        EvidenceReviewState.SUPERSEDED.value,
    ):
        return False

    if rs in (EvidenceReviewState.ACCEPTED_UNVERIFIED.value, EvidenceReviewState.VERIFIED.value):
        return True

    return False


def assurance_bucket_for_report(doc: Dict[str, Any]) -> str:
    """Stable bucket labels for dashboards / APIs — not a score redesign."""
    tier = effective_assurance_tier(doc)
    rs = effective_evidence_review_state(doc)

    if tier == AssuranceTier.EXTERNALLY_VERIFIED.value or rs == EvidenceReviewState.VERIFIED.value:
        return "externally_verified"
    if tier == AssuranceTier.HUMAN_ACCEPTED.value or rs == EvidenceReviewState.ACCEPTED_UNVERIFIED.value:
        return "human_accepted"
    if tier == AssuranceTier.USER_UPLOADED.value or rs == EvidenceReviewState.UPLOADED.value:
        return "uploaded_only"
    if tier == AssuranceTier.REJECTED.value or rs == EvidenceReviewState.REJECTED.value:
        return "rejected"
    if tier == AssuranceTier.SYSTEM_EXPIRED.value or rs == EvidenceReviewState.EXPIRED.value:
        return "expired"
    return "unknown"
