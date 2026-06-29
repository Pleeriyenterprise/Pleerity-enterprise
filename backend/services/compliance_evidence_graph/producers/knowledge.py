"""P2 producer — knowledge centre reference attach."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_REGULATORY_INTERPRETATION
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def handle_knowledge_reference(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    ref_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="knowledge_reference",
        client_id=client_id,
        entity_id=ref_id,
        fact_signature=fact_hash(
            {
                "article_id": payload.get("article_id"),
                "requirement_id": ctx.requirement_id or payload.get("requirement_id"),
                "correlation_id": correlation_id,
            }
        ),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {"knowledge_reference": payload},
        "rule_lineage": build_rule_lineage_from_refs(
            {
                "lineage_node_ids": [payload["article_id"]] if payload.get("article_id") else [],
                "lineage_optional": True,
            }
        ),
    }
    result = await emit_producer_decision(
        decision_type=DECISION_REGULATORY_INTERPRETATION,
        decision_outcome="KNOWLEDGE_ATTACHED",
        summary=f"Knowledge reference attached: {payload.get('article_id', ref_id)}",
        source_collection=ctx.source_collection,
        source_id=ref_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id,
        requirement_id=ctx.requirement_id or payload.get("requirement_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": payload.get("authority_service") or "knowledge",
            "component": "knowledge_reference_attach",
            "actor_type": "system",
            "actor_id": "knowledge_link",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "partial", "rule_certainty_score": 80},
        metadata={"mutation_kind": "knowledge_reference", "producer": "p2"},
    )
    return result[0] if result else None
