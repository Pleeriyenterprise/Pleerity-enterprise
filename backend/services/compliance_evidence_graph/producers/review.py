"""P0 producer — evidence review transitions."""
from __future__ import annotations

from typing import Optional

from database import database

from services.compliance_evidence_graph.constants import DECISION_EVIDENCE_ACCEPTANCE, DECISION_EVIDENCE_REJECTION
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_p0_decision
from services.compliance_evidence_graph.producers.downstream import stamp_document
from services.compliance_evidence_graph.producers.registry import ProducerContext

_AUTHORITY = {
    "service": "evidence_review_audit",
    "component": "append_evidence_review_event",
    "actor_type": "admin",
}

_APPROVE_STATES = frozenset({"APPROVED", "VERIFIED", "ACCEPTED", "ACCEPTED_UNVERIFIED"})
_EXPIRED_STATES = frozenset({"EXPIRED", "MARK_EXPIRED"})
_SUPERSEDE_HINTS = frozenset({"SUPERSEDED", "SUPERSEDE"})
_EXTERNAL_VERIFY_HINTS = frozenset({"EXTERNALLY_VERIFIED", "EXTERNAL_VERIFICATION", "VERIFY_EXTERNAL"})


def _p1_transition_category(from_state: str, to_state: str) -> Optional[str]:
    """Map review transitions to P1 matrix rows when applicable."""
    fs = (from_state or "").upper()
    ts = (to_state or "").upper()
    if ts in _EXPIRED_STATES or "EXPIRED" in ts:
        return "P1-12"
    if ts in _SUPERSEDE_HINTS or "SUPERSEDE" in ts:
        return "P1-13"
    if ts in _EXTERNAL_VERIFY_HINTS or "EXTERNAL" in ts:
        return "P1-09"
    if ts in _APPROVE_STATES and fs not in _APPROVE_STATES:
        return "P1-08"
    return None


async def handle_evidence_review_transition(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    event_id = ctx.source_id
    document_id = payload.get("document_id")
    to_state = (payload.get("to_state") or "").upper()
    from_state = (payload.get("from_state") or "").upper()
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="evidence_review_transition",
        client_id=client_id,
        entity_id=event_id,
        fact_signature=f"{from_state}:{to_state}",
    )

    decision_type = DECISION_EVIDENCE_ACCEPTANCE if to_state in _APPROVE_STATES else DECISION_EVIDENCE_REJECTION
    human_status = "approved" if to_state in _APPROVE_STATES else ("rejected" if "REJECT" in to_state else "pending")

    snapshot_payload = {
        "human_approvals": [
            {
                "review_event_id": event_id,
                "actor_id": payload.get("reviewer_id"),
                "outcome": to_state.lower(),
                "from_state": from_state,
                "to_assurance_tier": payload.get("to_assurance_tier"),
            }
        ],
        "decision_reasoning_inputs": {
            "decision_reason": payload.get("decision_reason"),
            "validation_snapshot": payload.get("validation_snapshot"),
            "p1_transition_category": _p1_transition_category(from_state, to_state),
        },
    }

    result = await emit_p0_decision(
        decision_type=decision_type,
        decision_outcome=to_state,
        summary=f"Evidence review transition {from_state} → {to_state} for document {document_id}",
        source_collection="evidence_review_events",
        source_id=event_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        requirement_id=ctx.requirement_id or payload.get("requirement_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp or payload.get("created_at"),
        decision_authority={**_AUTHORITY, "actor_id": payload.get("reviewer_id") or "reviewer"},
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 95 if to_state in _APPROVE_STATES else 60,
            "human_verification_status": human_status,
            "rule_certainty_score": 100,
        },
        document_ids=[document_id] if document_id else None,
        metadata={"mutation_kind": "evidence_review_transition", "event_id": event_id},
    )
    if not result:
        return None

    decision_id, snapshot_id = result
    db = database.get_db()
    await stamp_document(
        db,
        "evidence_review_events",
        {"event_id": event_id},
        decision_id=decision_id,
        snapshot_id=snapshot_id,
        operational_correlation_id=correlation_id,
    )
    return decision_id
