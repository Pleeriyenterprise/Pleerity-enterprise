"""
Map legacy DocumentStatus → (evidence_review_state, assurance_tier) when new fields absent.
Does not reinterpret legacy VERIFIED as external verification.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from models import DocumentStatus
from models.evidence_review import AssuranceTier, EvidenceReviewState
from services.evidence_review_config import is_feature_evidence_review_v2


def legacy_status_to_review_and_tier(document_status: Optional[str]) -> Tuple[str, str]:
    u = (document_status or "").strip().upper()
    if u in ("PENDING", "UPLOADED", ""):
        return EvidenceReviewState.UPLOADED.value, AssuranceTier.USER_UPLOADED.value
    if u == DocumentStatus.VERIFIED.value:
        return EvidenceReviewState.ACCEPTED_UNVERIFIED.value, AssuranceTier.HUMAN_ACCEPTED.value
    if u == DocumentStatus.REJECTED.value:
        return EvidenceReviewState.REJECTED.value, AssuranceTier.REJECTED.value
    if u == DocumentStatus.EXPIRED.value:
        return EvidenceReviewState.EXPIRED.value, AssuranceTier.SYSTEM_EXPIRED.value
    return EvidenceReviewState.UPLOADED.value, AssuranceTier.USER_UPLOADED.value


def effective_evidence_review_state(doc: Dict[str, Any]) -> str:
    existing = doc.get("evidence_review_state")
    if existing and str(existing).strip():
        return str(existing).strip().upper()
    return legacy_status_to_review_and_tier((doc.get("status") or None))[0]


def effective_assurance_tier(doc: Dict[str, Any]) -> str:
    existing = doc.get("assurance_tier")
    if existing and str(existing).strip():
        return str(existing).strip().upper()
    return legacy_status_to_review_and_tier((doc.get("status") or None))[1]


def apply_v2_defaults_to_new_upload(doc: Dict[str, Any]) -> None:
    """Best-effort defaults on insert when Evidence Review V2 is enabled (additive)."""
    if not is_feature_evidence_review_v2():
        return
    doc.setdefault("evidence_review_state", EvidenceReviewState.UPLOADED.value)
    doc.setdefault("assurance_tier", AssuranceTier.USER_UPLOADED.value)
    doc.setdefault("review_required", True)


def backfill_review_fields_dict(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Persisted patch to add missing review fields derived from legacy status (idempotent)."""
    st, tier = legacy_status_to_review_and_tier((doc.get("status") or None))
    out: Dict[str, Any] = {}
    if not doc.get("evidence_review_state"):
        out["evidence_review_state"] = st
    if not doc.get("assurance_tier"):
        out["assurance_tier"] = tier
    if doc.get("review_required") is None and (doc.get("status") or "").upper() in (
        "PENDING",
        "UPLOADED",
        "",
    ):
        out["review_required"] = True
    return out
