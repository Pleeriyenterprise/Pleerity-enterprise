"""P0 producer — compliance outcome engine events."""
from __future__ import annotations

from typing import Optional

from database import database

from services.compliance_evidence_graph.constants import DECISION_COMPLIANCE_ASSESSMENT
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_p0_decision
from services.compliance_evidence_graph.producers.downstream import stamp_document
from services.compliance_evidence_graph.producers.registry import ProducerContext

_AUTHORITY = {
    "service": "compliance_outcome_engine",
    "component": "apply_action_outcome",
    "actor_type": "system",
}


async def handle_outcome_engine_event(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    property_id = ctx.property_id or payload.get("property_id")
    dedupe_key_src = payload.get("dedupe_key") or ctx.source_id
    event_type = (payload.get("event_type") or "").lower()
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="outcome_engine_event",
        client_id=client_id,
        entity_id=dedupe_key_src,
        fact_signature=event_type,
    )

    score_change = payload.get("score_change", 0)
    outcome_label = "IMPROVED" if score_change > 0 else ("DECLINED" if score_change < 0 else "UNCHANGED")

    snapshot_payload = {
        "compliance_score": {
            "property_id": property_id,
            "score_before": payload.get("previous_score"),
            "score_after": payload.get("new_score"),
        },
        "decision_reasoning_inputs": {
            "outcome_event_type": event_type,
            "requirement_type": payload.get("requirement_type"),
            "risk_change": payload.get("risk_change"),
            "status_change": payload.get("status_change"),
            "message": payload.get("message"),
        },
    }

    result = await emit_p0_decision(
        decision_type=DECISION_COMPLIANCE_ASSESSMENT,
        decision_outcome=outcome_label,
        summary=f"Action outcome applied: {event_type} → {payload.get('message', outcome_label)}",
        source_collection="compliance_activity_log",
        source_id=dedupe_key_src,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp or payload.get("created_at"),
        decision_authority={
            **_AUTHORITY,
            "actor_id": payload.get("actor_id") or event_type,
            "actor_type": payload.get("actor_role") or "system",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 100,
            "rule_certainty_score": 100,
            "decision_stability": "stable",
        },
        metadata={"mutation_kind": "outcome_engine_event", "event_type": event_type},
    )
    if not result:
        return None

    decision_id, snapshot_id = result
    db = database.get_db()
    await stamp_document(
        db,
        "compliance_activity_log",
        {"dedupe_key": dedupe_key_src, "client_id": client_id},
        decision_id=decision_id,
        snapshot_id=snapshot_id,
        operational_correlation_id=correlation_id,
    )
    return decision_id
