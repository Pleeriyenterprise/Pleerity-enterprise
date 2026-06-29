"""Intelligence Service response envelopes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_intelligence_engine.constants import ENGINE_VERSION
from services.compliance_intelligence_engine.hashing import envelope_hash


def build_envelope(
    *,
    service: str,
    enabled: bool,
    insufficient_evidence: bool,
    reason: Optional[str] = None,
    artefact_id: Optional[str] = None,
    provenance_id: Optional[str] = None,
    artefact_type: Optional[str] = None,
    artefacts: Optional[List[Dict[str, Any]]] = None,
    tier1: Optional[Dict[str, Any]] = None,
    authoritative_references: Optional[Dict[str, Any]] = None,
    graph_service_response_hash: Optional[str] = None,
) -> Dict[str, Any]:
    refs = authoritative_references or {
        "artefact_ids": [],
        "provenance_ids": [],
        "decision_ids": [],
        "snapshot_ids": [],
    }
    if provenance_id and provenance_id not in refs.get("provenance_ids", []):
        refs.setdefault("provenance_ids", [])
        if provenance_id not in refs["provenance_ids"]:
            refs["provenance_ids"] = list(refs["provenance_ids"]) + [provenance_id]
    body: Dict[str, Any] = {
        "service": service,
        "enabled": enabled,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": insufficient_evidence,
        "reason": reason,
        "artefact_id": artefact_id,
        "provenance_id": provenance_id,
        "artefact_type": artefact_type,
        "artefacts": artefacts or [],
        "tier1": tier1,
        "authoritative_references": refs,
        "graph_service_response_hash": graph_service_response_hash,
        "tier2": None,
    }
    body["response_hash"] = envelope_hash({k: v for k, v in body.items() if k != "response_hash"})
    return body


def unavailable_envelope(service: str, *, artefact_type: Optional[str] = None) -> Dict[str, Any]:
    return build_envelope(
        service=service,
        enabled=False,
        insufficient_evidence=True,
        reason="COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED",
        artefact_type=artefact_type,
    )


def not_implemented_envelope(service: str, *, artefact_type: Optional[str] = None) -> Dict[str, Any]:
    return build_envelope(
        service=service,
        enabled=True,
        insufficient_evidence=True,
        reason="CIE_DOMAIN_ENGINE_NOT_IMPLEMENTED",
        artefact_type=artefact_type,
    )


def replay_not_implemented_envelope(
    *,
    replay_type: Optional[str] = None,
    provenance_id: Optional[str] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    return build_envelope(
        service="replay_intelligence",
        enabled=True,
        insufficient_evidence=True,
        reason="CIE_PROVENANCE_REPLAY_NOT_IMPLEMENTED",
        provenance_id=provenance_id,
        tier1={
            "replay_type": replay_type,
            "as_of": as_of,
            "requires_historical_inputs": True,
            "prohibits_current_state_substitution": True,
        },
    )


def compare_not_implemented_envelope(
    *,
    left_id: Optional[str] = None,
    right_id: Optional[str] = None,
) -> Dict[str, Any]:
    return build_envelope(
        service="compare_intelligence",
        enabled=True,
        insufficient_evidence=True,
        reason="CIE_PROVENANCE_COMPARE_NOT_IMPLEMENTED",
        artefact_id=right_id,
        tier1={
            "left_artefact_id": left_id,
            "right_artefact_id": right_id,
            "requires_provenance_references": True,
            "prohibits_current_state_substitution": True,
        },
    )
