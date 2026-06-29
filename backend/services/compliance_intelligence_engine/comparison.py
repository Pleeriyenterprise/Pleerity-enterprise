"""Intelligence comparison stub — deterministic diff deferred to CIE-2+."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_intelligence_engine.config import intelligence_engine_enabled
from services.compliance_intelligence_engine.constants import ENGINE_VERSION
from services.compliance_intelligence_engine.envelopes import attach_response_hash


def compare_not_implemented_envelope(
    *,
    service: str = "compare_intelligence",
    left_id: Optional[str] = None,
    right_id: Optional[str] = None,
    left_provenance_id: Optional[str] = None,
    right_provenance_id: Optional[str] = None,
    reason: str = "CIE_PROVENANCE_COMPARE_NOT_IMPLEMENTED",
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    if enabled is None:
        enabled = intelligence_engine_enabled()
    prov_ids = [p for p in (left_provenance_id, right_provenance_id) if p]
    artefact_ids = [a for a in (left_id, right_id) if a]
    body: Dict[str, Any] = {
        "service": service,
        "enabled": enabled,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": True,
        "reason": reason,
        "left_artefact_id": left_id,
        "right_artefact_id": right_id,
        "left_provenance_id": left_provenance_id,
        "right_provenance_id": right_provenance_id,
        "requires_provenance_references": True,
        "prohibits_current_state_substitution": True,
        "diff": None,
        "artefact_id": right_id,
        "provenance_id": right_provenance_id,
        "artefact_type": None,
        "artefacts": [],
        "tier1": {
            "left_artefact_id": left_id,
            "right_artefact_id": right_id,
            "requires_provenance_references": True,
            "prohibits_current_state_substitution": True,
        },
        "authoritative_references": {
            "provenance_ids": prov_ids,
            "artefact_ids": artefact_ids,
            "decision_ids": [],
            "snapshot_ids": [],
        },
        "graph_service_response_hash": None,
        "tier2": None,
    }
    return attach_response_hash(body)


async def dispatch_compare(
    *,
    left_id: str,
    right_id: str,
    compare_mode: str = "full",
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return compare_not_implemented_envelope(
            left_id=left_id, right_id=right_id, reason="COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED", enabled=False
        )
    if not left_id or not right_id:
        return compare_not_implemented_envelope(
            left_id=left_id, right_id=right_id, reason="CIE_COMPARE_ARTEFACT_IDS_REQUIRED", enabled=True
        )
    return compare_not_implemented_envelope(left_id=left_id, right_id=right_id, enabled=True)
