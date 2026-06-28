"""P1 producers — risk signal generation and regen worker."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_RISK_ASSESSMENT
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def handle_risk_signal_generation(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    property_id = ctx.property_id or ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")
    generated = int(payload.get("generated") or 0)

    dedupe_key = build_dedupe_key(
        mutation_kind="risk_signal_generation",
        client_id=client_id,
        entity_id=property_id,
        fact_signature=fact_hash(
            {
                "generated": generated,
                "merged_in_place": payload.get("merged_in_place"),
                "previous_active_removed": payload.get("previous_active_removed"),
                "correlation_id": correlation_id,
            }
        ),
    )

    signal_summaries = []
    for s in (payload.get("signals") or [])[:25]:
        if isinstance(s, dict):
            signal_summaries.append(
                {
                    "signal_id": s.get("signal_id"),
                    "risk_type": s.get("risk_type"),
                    "risk_level": s.get("risk_level"),
                }
            )

    snapshot_payload = {
        "decision_reasoning_inputs": {
            "risk_generation": {
                "generated": generated,
                "merged_in_place": payload.get("merged_in_place"),
                "previous_active_removed": payload.get("previous_active_removed"),
                "signal_summaries": signal_summaries,
            }
        },
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }

    result = await emit_producer_decision(
        decision_type=DECISION_RISK_ASSESSMENT,
        decision_outcome="SIGNALS_GENERATED",
        summary=f"Risk signals generated for property {property_id}: {generated} signal(s)",
        source_collection="risk_signals",
        source_id=property_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "risk_signal_service",
            "component": "generate_risk_signals_for_property",
            "actor_type": "system",
            "actor_id": "risk_signal_generator",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete" if generated else "partial",
            "evidence_confidence_score": 85,
            "rule_certainty_score": 90,
            "decision_stability": "stable",
        },
        metadata={"mutation_kind": "risk_signal_generation", "producer": "p1"},
    )
    return result[0] if result else None


async def handle_risk_signal_regen_worker(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    property_id = ctx.property_id or ctx.source_id
    queue_item_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="risk_signal_regen_worker",
        client_id=client_id,
        entity_id=queue_item_id,
        fact_signature=fact_hash(
            {
                "generated": payload.get("generated"),
                "correlation_id": correlation_id,
            }
        ),
    )

    snapshot_payload = {
        "decision_reasoning_inputs": {
            "risk_regen_worker": {
                "queue_item_id": queue_item_id,
                "generated": payload.get("generated"),
                "previous_active_removed": payload.get("previous_active_removed"),
                "trigger_reasons": payload.get("trigger_reasons") or [],
            }
        },
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }

    result = await emit_producer_decision(
        decision_type=DECISION_RISK_ASSESSMENT,
        decision_outcome="REGEN_COMPLETED",
        summary=f"Risk signal regen worker completed for property {property_id}",
        source_collection="risk_signal_regen_queue",
        source_id=queue_item_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "risk_signal_regen_queue",
            "component": "run_risk_signal_regen_worker",
            "actor_type": "system",
            "actor_id": "risk_regen_worker",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 90,
            "rule_certainty_score": 90,
        },
        metadata={"mutation_kind": "risk_signal_regen_worker", "producer": "p1"},
    )
    return result[0] if result else None
