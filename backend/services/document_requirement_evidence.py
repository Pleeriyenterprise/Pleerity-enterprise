"""
Requirement / document evidence helpers (Compliance Vault Pro).

Primary logic lives in ``services.evidence_document_match_engine``; this module keeps
a thin backward-compatible entry point for legacy callers.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.evidence_document_match_engine import evaluate_document_requirement_match
from services.evidence_document_taxonomy import MATCH_OUTCOME_MISMATCH_SUSPECTED


def detect_requirement_document_mismatch(
    requirement: Optional[Dict[str, Any]],
    extracted_data: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    """
    Returns (is_mismatch, short_reason).

    When extraction did not yield a usable document_type, may return (False, None) to limit false positives.
    """
    if not requirement or not isinstance(extracted_data, dict):
        return False, None
    ev = evaluate_document_requirement_match(
        requirement=requirement,
        filename="",
        user_declared_document_type=None,
        extracted_data=extracted_data,
        upload_route_context="legacy_detect_requirement_document_mismatch",
    )
    if ev.get("match_outcome") == MATCH_OUTCOME_MISMATCH_SUSPECTED:
        return True, (ev.get("mismatch_reason_text") or "Possible wrong document for this requirement.")[:500]
    return False, None
