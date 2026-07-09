"""P1 producers — applicability operator, materialization, registry publish."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import DECISION_REQUIREMENT_APPLICABILITY
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs, lineage_refs_from_requirement
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def _emit_applicability_decision(
    ctx: ProducerContext,
    *,
    mutation_kind: str,
    decision_outcome: str,
    summary: str,
    lineage_refs: dict,
    snapshot_extra: dict,
    quality_inputs: dict,
) -> Optional[str]:
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
                "outcome": decision_outcome,
                "correlation_id": correlation_id,
                **snapshot_extra,
            }
        ),
    )

    snapshot_payload = {
        "decision_reasoning_inputs": snapshot_extra,
        "rule_lineage": build_rule_lineage_from_refs(lineage_refs),
    }

    result = await emit_producer_decision(
        decision_type=DECISION_REQUIREMENT_APPLICABILITY,
        decision_outcome=decision_outcome,
        summary=summary,
        source_collection=ctx.source_collection,
        source_id=entity_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        requirement_id=ctx.requirement_id or payload.get("requirement_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": payload.get("authority_service") or "applicability",
            "component": payload.get("authority_component") or mutation_kind,
            "actor_type": payload.get("actor_type") or "system",
            "actor_id": payload.get("actor_id") or mutation_kind,
        },
        snapshot_payload=snapshot_payload,
        quality_inputs=quality_inputs,
        metadata={"mutation_kind": mutation_kind, "producer": "p1"},
    )
    return result[0] if result else None


async def handle_applicability_operator(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    command = (payload.get("command") or "").upper()
    return await _emit_applicability_decision(
        ctx,
        mutation_kind="applicability_operator",
        decision_outcome=command or "OPERATOR_COMMAND",
        summary=f"Applicability operator command {command} on requirement {ctx.requirement_id or ctx.source_id}",
        lineage_refs=lineage_refs_from_requirement(payload.get("requirement")),
        snapshot_extra={
            "operator_command": command,
            "pipeline_applicability_state": payload.get("pipeline_applicability_state"),
            "effective_applicability_state": payload.get("effective_applicability_state"),
            "resolution_reason_code": payload.get("resolution_reason_code"),
        },
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 100,
            "human_verification_status": "approved",
            "rule_certainty_score": 100,
            "jurisdiction_certainty_score": 95,
        },
    )


async def handle_requirement_materialization(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    trigger = payload.get("trigger") or "materialization"
    return await _emit_applicability_decision(
        ctx,
        mutation_kind="requirement_materialization",
        decision_outcome="MATERIALIZED",
        summary=f"Requirements materialized for property {ctx.property_id or ctx.source_id} ({trigger})",
        lineage_refs={
            "registry_publish_version": payload.get("registry_publish_version"),
            "jurisdiction": payload.get("jurisdiction"),
            "lineage_optional": True,
        },
        snapshot_extra={
            "trigger": trigger,
            "planned_types": payload.get("planned_types") or [],
            "upsert_passes": payload.get("upsert_passes"),
            "reconciled_obsolete": payload.get("reconciled_obsolete"),
        },
        quality_inputs={
            "evidence_completeness": "complete",
            "rule_certainty_score": 100,
            "jurisdiction_certainty_score": 90,
        },
    )


async def handle_property_jurisdiction_materialization(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    return await _emit_applicability_decision(
        ctx,
        mutation_kind="property_jurisdiction_materialization",
        decision_outcome="JURISDICTION_MATERIALIZED",
        summary=f"Property jurisdiction change materialized for {ctx.property_id or ctx.source_id}",
        lineage_refs={
            "jurisdiction": payload.get("jurisdiction"),
            "lineage_optional": True,
        },
        snapshot_extra={
            "previous_jurisdiction": payload.get("previous_jurisdiction"),
            "new_jurisdiction": payload.get("new_jurisdiction"),
            "applicability_fields_changed": payload.get("applicability_fields_changed"),
        },
        quality_inputs={
            "evidence_completeness": "complete",
            "rule_certainty_score": 95,
            "jurisdiction_certainty_score": 100,
        },
    )


async def handle_registry_publish(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    version = payload.get("published_version")
    return await _emit_applicability_decision(
        ctx,
        mutation_kind="registry_publish",
        decision_outcome="PUBLISHED",
        summary=f"Compliance registry published version {version}",
        lineage_refs={
            "policy_registry_version": version,
            "registry_publish_version": version,
            "lineage_optional": True,
        },
        snapshot_extra={
            "published_version": version,
            "entry_count": payload.get("entry_count"),
            "keys_updated": payload.get("keys_updated_this_publish") or [],
            "queue_id": payload.get("queue_id"),
        },
        quality_inputs={
            "evidence_completeness": "complete",
            "rule_certainty_score": 100,
        },
    )
