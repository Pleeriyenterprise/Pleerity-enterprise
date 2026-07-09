"""Shared CIE response envelope helpers — deterministic response_hash on all entry points."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_intelligence_engine.constants import ENGINE_VERSION
from services.compliance_intelligence_engine.hashing import envelope_hash


def empty_authoritative_references() -> Dict[str, Any]:
    return {
        "artefact_ids": [],
        "provenance_ids": [],
        "decision_ids": [],
        "snapshot_ids": [],
    }


def attach_response_hash(body: Dict[str, Any]) -> Dict[str, Any]:
    """Add sha256 response_hash; body must not already contain response_hash."""
    out = dict(body)
    if "response_hash" in out:
        raise ValueError("response_hash_must_not_be_pre_set")
    out["response_hash"] = envelope_hash({k: v for k, v in out.items() if k != "response_hash"})
    return out


def build_stub_envelope(
    *,
    service: str,
    enabled: bool,
    insufficient_evidence: bool,
    reason: str,
    artefact_type: Optional[str] = None,
    provenance_id: Optional[str] = None,
    tier1: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    refs = empty_authoritative_references()
    if provenance_id:
        refs["provenance_ids"] = [provenance_id]
    body: Dict[str, Any] = {
        "service": service,
        "enabled": enabled,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": insufficient_evidence,
        "reason": reason,
        "artefact_id": None,
        "provenance_id": provenance_id,
        "artefact_type": artefact_type,
        "artefacts": [],
        "tier1": tier1,
        "authoritative_references": refs,
        "graph_service_response_hash": None,
        "tier2": None,
    }
    if extra:
        body.update(extra)
    return attach_response_hash(body)
