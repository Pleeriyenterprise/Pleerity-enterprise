"""P2 producers — reminders and digests."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_REMINDER_GENERATION
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def _emit_reminder(ctx: ProducerContext, *, mutation_kind: str, outcome: str, summary: str) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    entity_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind=mutation_kind,
        client_id=client_id,
        entity_id=entity_id,
        fact_signature=fact_hash({"outcome": outcome, "count": payload.get("count"), "correlation_id": correlation_id}),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {mutation_kind: payload},
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }
    result = await emit_producer_decision(
        decision_type=DECISION_REMINDER_GENERATION,
        decision_outcome=outcome,
        summary=summary,
        source_collection=ctx.source_collection,
        source_id=entity_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": payload.get("authority_service") or "jobs",
            "component": payload.get("authority_component") or mutation_kind,
            "actor_type": "system",
            "actor_id": "reminder_job",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "complete", "rule_certainty_score": 90},
        metadata={"mutation_kind": mutation_kind, "producer": "p2"},
    )
    return result[0] if result else None


async def handle_daily_reminder(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    count = int(payload.get("success_count") or payload.get("count") or 0)
    return await _emit_reminder(
        ctx,
        mutation_kind="daily_reminder",
        outcome="DAILY_SENT",
        summary=f"Daily compliance reminders dispatched ({count} success)",
    )


async def handle_reminder_cancelled(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    return await _emit_reminder(
        ctx,
        mutation_kind="reminder_cancelled",
        outcome="CANCELLED",
        summary=f"Reminder cancelled: {payload.get('reason', 'user_action')}",
    )


async def handle_monthly_digest(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    count = int(payload.get("digest_count") or payload.get("count") or 0)
    return await _emit_reminder(
        ctx,
        mutation_kind="monthly_digest",
        outcome="DIGEST_SENT",
        summary=f"Monthly compliance digest sent ({count} client(s))",
    )
