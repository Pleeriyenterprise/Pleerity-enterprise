"""P1 producers — AI extraction apply/reject."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_EVIDENCE_ACCEPTANCE, DECISION_EVIDENCE_REJECTION
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs, lineage_refs_from_requirement
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def handle_document_extraction_apply(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    document_id = ctx.source_id
    client_id = ctx.client_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")
    ai_confidence = payload.get("confidence_score") or payload.get("ai_confidence")

    dedupe_key = build_dedupe_key(
        mutation_kind="document_extraction_apply",
        client_id=client_id,
        entity_id=document_id,
        fact_signature=fact_hash(
            {
                "requirement_id": ctx.requirement_id or payload.get("requirement_id"),
                "user_confirmed": payload.get("user_confirmed"),
                "correlation_id": correlation_id,
            }
        ),
    )

    snapshot_payload = {
        "decision_reasoning_inputs": {
            "extraction_apply": {
                "document_id": document_id,
                "changes_made": payload.get("changes_made") or [],
                "user_confirmed": payload.get("user_confirmed"),
                "expiry_date_set": payload.get("expiry_date_set"),
            }
        },
        "rule_lineage": build_rule_lineage_from_refs(lineage_refs_from_requirement(payload.get("requirement"))),
    }

    result = await emit_producer_decision(
        decision_type=DECISION_EVIDENCE_ACCEPTANCE,
        decision_outcome="EXTRACTION_APPLIED",
        summary=f"AI extraction applied for document {document_id}",
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
            "component": "apply_ai_extraction",
            "actor_type": "user",
            "actor_id": payload.get("actor_id") or "client",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "ai_extraction_confidence_score": int(ai_confidence) if ai_confidence is not None else None,
            "human_verification_status": "approved" if payload.get("user_confirmed") else "partial",
            "rule_certainty_score": 95,
        },
        document_ids=[document_id],
        metadata={"mutation_kind": "document_extraction_apply", "producer": "p1"},
    )
    return result[0] if result else None


async def handle_document_extraction_reject(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    document_id = ctx.source_id
    client_id = ctx.client_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="document_extraction_reject",
        client_id=client_id,
        entity_id=document_id,
        fact_signature=fact_hash({"reason": payload.get("reason"), "correlation_id": correlation_id}),
    )

    snapshot_payload = {
        "decision_reasoning_inputs": {
            "extraction_reject": {
                "document_id": document_id,
                "reason": payload.get("reason"),
            }
        },
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }

    result = await emit_producer_decision(
        decision_type=DECISION_EVIDENCE_REJECTION,
        decision_outcome="EXTRACTION_REJECTED",
        summary=f"AI extraction rejected for document {document_id}",
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
            "component": "reject_ai_extraction",
            "actor_type": "user",
            "actor_id": payload.get("actor_id") or "client",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "partial",
            "human_verification_status": "rejected",
            "rule_certainty_score": 90,
        },
        document_ids=[document_id],
        metadata={"mutation_kind": "document_extraction_reject", "producer": "p1"},
    )
    return result[0] if result else None
