"""P0 producer — requirement evidence authority sync."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import (
    DECISION_COMPLIANCE_ASSESSMENT,
    DECISION_EVIDENCE_ACCEPTANCE,
    DECISION_EVIDENCE_REJECTION,
)
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_p0_decision, fact_hash
from services.compliance_evidence_graph.producers.registry import ProducerContext

_AUTHORITY = {
    "service": "requirement_evidence_authority",
    "component": "sync_requirement_evidence_authority",
    "actor_type": "system",
}

_ACCEPT_STATES = frozenset({"VALID", "COMPLIANT", "SATISFIED", "VERIFIED"})
_REJECT_STATES = frozenset({"REJECTED", "EXPIRED", "MISSING", "INVALID"})


def _resolve_decision_type(semantic_state: str) -> str:
    st = (semantic_state or "").upper()
    if st in _REJECT_STATES:
        return DECISION_EVIDENCE_REJECTION
    if st in _ACCEPT_STATES:
        return DECISION_EVIDENCE_ACCEPTANCE
    return DECISION_COMPLIANCE_ASSESSMENT


async def handle_evidence_authority_sync(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    requirement_id = ctx.requirement_id or ctx.source_id
    property_id = ctx.property_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    semantic_state = (payload.get("semantic_state") or payload.get("state") or "UNKNOWN").upper()
    authority_version = payload.get("authority_version") or payload.get("version") or 0

    sig = fact_hash(
        {
            "semantic_state": semantic_state,
            "authority_version": authority_version,
            "correlation_id": correlation_id,
            "transition_id": payload.get("transition_id"),
        }
    )
    dedupe_key = build_dedupe_key(
        mutation_kind="evidence_authority_sync",
        client_id=client_id,
        entity_id=requirement_id,
        fact_signature=sig,
    )

    decision_type = _resolve_decision_type(semantic_state)
    missing = payload.get("missing_dependencies") or []
    conflicts = payload.get("conflicts") or []

    snapshot_payload = {
        "decision_reasoning_inputs": {
            "authority_sync_outcome": {
                "semantic_state": semantic_state,
                "state_reason": payload.get("state_reason"),
                "effective_expiry": payload.get("effective_expiry"),
                "authority_version": authority_version,
            },
            "missing_dependencies": missing,
        },
        "evidence_version": {
            "document_versions": payload.get("document_versions") or [],
        },
    }

    completeness = "complete" if not missing else "partial"
    result = await emit_p0_decision(
        decision_type=decision_type,
        decision_outcome=semantic_state,
        summary=f"Evidence authority sync for requirement {requirement_id}: {semantic_state}",
        source_collection="requirements",
        source_id=requirement_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={**_AUTHORITY, "actor_id": payload.get("transition_origin") or "authority_sync"},
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": completeness,
            "evidence_confidence_score": 100 if semantic_state in _ACCEPT_STATES else 70,
            "human_verification_status": payload.get("human_verification_status") or "unknown",
            "missing_required_evidence": missing,
            "conflicting_evidence": conflicts,
            "rule_certainty_score": 100,
        },
        document_ids=payload.get("document_ids"),
        metadata={"mutation_kind": "evidence_authority_sync", "transition_id": payload.get("transition_id")},
    )
    if not result:
        return None
    return result[0]
