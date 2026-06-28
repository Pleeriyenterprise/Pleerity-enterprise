"""P1 producers — CER writes and supporting document linkage."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_EVIDENCE_ACCEPTANCE
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs, lineage_refs_from_requirement
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def handle_cer_linkage(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    cer_id = ctx.source_id
    client_id = ctx.client_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")
    evidence_mode = payload.get("evidence_mode") or "UNKNOWN"

    dedupe_key = build_dedupe_key(
        mutation_kind="cer_linkage",
        client_id=client_id,
        entity_id=cer_id,
        fact_signature=fact_hash(
            {
                "evidence_mode": evidence_mode,
                "verification_status": payload.get("verification_status"),
                "correlation_id": correlation_id,
            }
        ),
    )

    snapshot_payload = {
        "decision_reasoning_inputs": {
            "cer_linkage": {
                "evidence_record_id": cer_id,
                "evidence_mode": evidence_mode,
                "verification_status": payload.get("verification_status"),
                "created_via": payload.get("created_via"),
                "linked_document_ids": payload.get("linked_document_ids") or [],
            }
        },
        "rule_lineage": build_rule_lineage_from_refs(lineage_refs_from_requirement(payload.get("requirement"))),
    }

    result = await emit_producer_decision(
        decision_type=DECISION_EVIDENCE_ACCEPTANCE,
        decision_outcome="CER_LINKED",
        summary=f"Compliance evidence record {cer_id} linked ({evidence_mode})",
        source_collection="compliance_evidence_records",
        source_id=cer_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        requirement_id=ctx.requirement_id or payload.get("requirement_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "compliance_evidence_record_service",
            "component": payload.get("authority_component") or "cer_write",
            "actor_type": payload.get("actor_type") or "user",
            "actor_id": payload.get("actor_id") or "cer_service",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": payload.get("evidence_confidence_score") or 85,
            "human_verification_status": payload.get("verification_status") or "unknown",
            "rule_certainty_score": 95,
        },
        document_ids=payload.get("linked_document_ids"),
        metadata={"mutation_kind": "cer_linkage", "producer": "p1"},
    )
    return result[0] if result else None


async def handle_supporting_document_linkage(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    document_id = ctx.source_id
    client_id = ctx.client_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="supporting_document_linkage",
        client_id=client_id,
        entity_id=document_id,
        fact_signature=fact_hash(
            {
                "requirement_id": ctx.requirement_id or payload.get("requirement_id"),
                "supporting_only": payload.get("supporting_only"),
                "correlation_id": correlation_id,
            }
        ),
    )

    snapshot_payload = {
        "decision_reasoning_inputs": {
            "supporting_linkage": {
                "document_id": document_id,
                "requirement_id": ctx.requirement_id or payload.get("requirement_id"),
                "supporting_only": payload.get("supporting_only"),
                "reason": payload.get("reason"),
            }
        },
        "rule_lineage": build_rule_lineage_from_refs(lineage_refs_from_requirement(payload.get("requirement"))),
    }

    result = await emit_producer_decision(
        decision_type=DECISION_EVIDENCE_ACCEPTANCE,
        decision_outcome="SUPPORTING_LINKED",
        summary=f"Supporting document {document_id} linked to requirement",
        source_collection="documents",
        source_id=document_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        requirement_id=ctx.requirement_id or payload.get("requirement_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "routes.documents",
            "component": "reconcile_document_linkage",
            "actor_type": "user",
            "actor_id": payload.get("actor_id") or "client",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "partial",
            "evidence_confidence_score": 70,
            "human_verification_status": "approved",
            "rule_certainty_score": 90,
        },
        document_ids=[document_id],
        metadata={"mutation_kind": "supporting_document_linkage", "producer": "p1"},
    )
    return result[0] if result else None
