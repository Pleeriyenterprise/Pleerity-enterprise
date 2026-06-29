"""P2 producers — tenant delivery proof and operational incident bridge."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_COMPLIANCE_ASSESSMENT
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def handle_tenant_delivery_proof(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    delivery_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="tenant_delivery_proof",
        client_id=client_id,
        entity_id=delivery_id,
        fact_signature=fact_hash({"status": payload.get("status"), "correlation_id": correlation_id}),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {"tenant_delivery_proof": payload},
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }
    result = await emit_producer_decision(
        decision_type=DECISION_COMPLIANCE_ASSESSMENT,
        decision_outcome=str(payload.get("status") or "RECORDED").upper(),
        summary=f"Tenant delivery proof recorded: {delivery_id}",
        source_collection="tenant_delivery_proofs",
        source_id=delivery_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "tenant_delivery_proof_service",
            "component": "record_delivery_proof",
            "actor_type": "system",
            "actor_id": "tenant_delivery",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "complete", "rule_certainty_score": 90},
        metadata={"mutation_kind": "tenant_delivery_proof", "producer": "p2"},
    )
    return result[0] if result else None


async def handle_operational_incident_bridge(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    incident_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="operational_incident_bridge",
        client_id=client_id,
        entity_id=incident_id,
        fact_signature=fact_hash({"incident_type": payload.get("incident_type"), "correlation_id": correlation_id}),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {"operational_incident": payload},
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }
    result = await emit_producer_decision(
        decision_type=DECISION_COMPLIANCE_ASSESSMENT,
        decision_outcome="INCIDENT_LINKED",
        summary=f"Operational incident bridge: {incident_id}",
        source_collection="operational_incidents",
        source_id=incident_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": payload.get("authority_service") or "operational_evidence",
            "component": "incident_compliance_bridge",
            "actor_type": "system",
            "actor_id": "oe_bridge",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "partial", "rule_certainty_score": 75},
        metadata={"mutation_kind": "operational_incident_bridge", "producer": "p2"},
    )
    return result[0] if result else None
