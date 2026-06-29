"""P2 producers — notification orchestrator and compliance alerts."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_RECOMMENDATION
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def _emit_notification(ctx: ProducerContext, *, mutation_kind: str, outcome: str, summary: str) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    entity_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind=mutation_kind,
        client_id=client_id,
        entity_id=entity_id,
        fact_signature=fact_hash(
            {
                "outcome": outcome,
                "template_key": payload.get("template_key"),
                "correlation_id": correlation_id,
            }
        ),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {mutation_kind: payload},
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }
    result = await emit_producer_decision(
        decision_type=DECISION_RECOMMENDATION,
        decision_outcome=outcome,
        summary=summary,
        source_collection=ctx.source_collection,
        source_id=entity_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": payload.get("authority_service") or "notification_orchestrator",
            "component": payload.get("authority_component") or mutation_kind,
            "actor_type": "system",
            "actor_id": "notification_orchestrator",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "complete", "rule_certainty_score": 85},
        metadata={"mutation_kind": mutation_kind, "producer": "p2"},
    )
    return result[0] if result else None


async def handle_notification_queued(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    return await _emit_notification(
        ctx,
        mutation_kind="notification_queued",
        outcome="QUEUED",
        summary=f"Notification queued: {payload.get('template_key', 'unknown')}",
    )


async def handle_notification_sent(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    return await _emit_notification(
        ctx,
        mutation_kind="notification_sent",
        outcome="SENT",
        summary=f"Notification sent: {payload.get('template_key', 'unknown')}",
    )


async def handle_compliance_status_alert(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    return await _emit_notification(
        ctx,
        mutation_kind="compliance_status_alert",
        outcome="ALERT_SENT",
        summary=f"Compliance status alert for client {ctx.client_id}",
    )
