"""Intelligence replay stub — historical reconstruction deferred to CIE-2+."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_intelligence_engine.config import intelligence_engine_enabled
from services.compliance_intelligence_engine.constants import ENGINE_VERSION
from services.compliance_intelligence_engine.envelopes import attach_response_hash, empty_authoritative_references


def replay_not_implemented_envelope(
    *,
    service: str = "replay_intelligence",
    replay_type: Optional[str] = None,
    provenance_id: Optional[str] = None,
    as_of: Optional[str] = None,
    reason: str = "CIE_PROVENANCE_REPLAY_NOT_IMPLEMENTED",
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    if enabled is None:
        enabled = intelligence_engine_enabled()
    refs = empty_authoritative_references()
    if provenance_id:
        refs["provenance_ids"] = [provenance_id]
    body: Dict[str, Any] = {
        "service": service,
        "enabled": enabled,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": True,
        "reason": reason,
        "replay_type": replay_type,
        "provenance_id": provenance_id,
        "as_of": as_of,
        "requires_historical_inputs": True,
        "prohibits_current_state_substitution": True,
        "artefact_id": None,
        "artefact_type": None,
        "artefacts": [],
        "tier1": {
            "replay_type": replay_type,
            "as_of": as_of,
            "requires_historical_inputs": True,
            "prohibits_current_state_substitution": True,
        },
        "authoritative_references": refs,
        "graph_service_response_hash": None,
        "tier2": None,
    }
    return attach_response_hash(body)


async def dispatch_replay(
    *,
    replay_type: str,
    provenance_id: Optional[str] = None,
    as_of: Optional[str] = None,
    artefact_type: Optional[str] = None,
    engine_version: Optional[str] = None,
    client_id: Optional[str] = None,
    persist_result: bool = False,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return replay_not_implemented_envelope(
            replay_type=replay_type,
            provenance_id=provenance_id,
            as_of=as_of,
            reason="COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED",
            enabled=False,
        )
    if not as_of and replay_type == "point_in_time":
        return replay_not_implemented_envelope(
            replay_type=replay_type,
            provenance_id=provenance_id,
            as_of=as_of,
            reason="CIE_REPLAY_AS_OF_REQUIRED",
            enabled=True,
        )
    if not provenance_id and replay_type == "exact":
        return replay_not_implemented_envelope(
            replay_type=replay_type,
            provenance_id=provenance_id,
            as_of=as_of,
            reason="CIE_REPLAY_PROVENANCE_ID_REQUIRED",
            enabled=True,
        )
    return replay_not_implemented_envelope(
        replay_type=replay_type, provenance_id=provenance_id, as_of=as_of, enabled=True
    )
