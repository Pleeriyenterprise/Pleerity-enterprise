"""P2 producers — work orders, maintenance issues, SLA reminders."""
from __future__ import annotations

from typing import Optional

from services.compliance_evidence_graph.constants import (
    DECISION_COMPLIANCE_ASSESSMENT,
    DECISION_WORK_ORDER_CREATION,
)
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_producer_decision, fact_hash
from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs
from services.compliance_evidence_graph.producers.registry import ProducerContext


async def handle_work_order_lifecycle(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    wo_id = ctx.source_id
    lifecycle = (payload.get("lifecycle") or "created").lower()
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="work_order_lifecycle",
        client_id=client_id,
        entity_id=wo_id,
        fact_signature=fact_hash({"lifecycle": lifecycle, "status": payload.get("status"), "correlation_id": correlation_id}),
    )
    outcome = "COMPLETED" if lifecycle == "completed" else "CREATED"
    decision_type = DECISION_WORK_ORDER_CREATION if lifecycle == "created" else DECISION_COMPLIANCE_ASSESSMENT

    snapshot_payload = {
        "decision_reasoning_inputs": {"work_order_lifecycle": payload},
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }
    result = await emit_producer_decision(
        decision_type=decision_type,
        decision_outcome=outcome,
        summary=f"Work order {wo_id} {lifecycle}",
        source_collection="work_orders",
        source_id=wo_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "maintenance_service",
            "component": payload.get("authority_component") or "work_order_lifecycle",
            "actor_type": payload.get("actor_type") or "system",
            "actor_id": payload.get("actor_id") or "maintenance",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "complete", "rule_certainty_score": 90},
        metadata={"mutation_kind": "work_order_lifecycle", "producer": "p2", "lifecycle": lifecycle},
    )
    return result[0] if result else None


async def handle_maintenance_issue_lifecycle(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    issue_id = ctx.source_id
    lifecycle = (payload.get("lifecycle") or "created").lower()
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="maintenance_issue_lifecycle",
        client_id=client_id,
        entity_id=issue_id,
        fact_signature=fact_hash(
            {
                "lifecycle": lifecycle,
                "status": payload.get("status"),
                "previous_status": payload.get("previous_status"),
                "resolved_at": payload.get("resolved_at"),
                "correlation_id": correlation_id,
            }
        ),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {"maintenance_issue": payload},
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }
    result = await emit_producer_decision(
        decision_type=DECISION_COMPLIANCE_ASSESSMENT,
        decision_outcome=lifecycle.upper(),
        summary=f"Maintenance issue {issue_id} {lifecycle}",
        source_collection="maintenance_issues",
        source_id=issue_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "maintenance_issues_service",
            "component": payload.get("authority_component") or "issue_lifecycle",
            "actor_type": "system",
            "actor_id": "maintenance_issues",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "complete", "rule_certainty_score": 85},
        metadata={"mutation_kind": "maintenance_issue_lifecycle", "producer": "p2"},
    )
    return result[0] if result else None


async def handle_work_order_sla_reminder(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    wo_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="work_order_sla_reminder",
        client_id=client_id,
        entity_id=wo_id,
        fact_signature=fact_hash({"correlation_id": correlation_id, "reminder_type": payload.get("reminder_type")}),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {"work_order_sla_reminder": payload},
        "rule_lineage": build_rule_lineage_from_refs({"lineage_optional": True}),
    }
    result = await emit_producer_decision(
        decision_type=DECISION_WORK_ORDER_CREATION,
        decision_outcome="SLA_REMINDER",
        summary=f"Work order SLA reminder for {wo_id}",
        source_collection="work_orders",
        source_id=wo_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "job_runner",
            "component": "work_order_sla_reminder",
            "actor_type": "system",
            "actor_id": "wo_sla_job",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "complete", "rule_certainty_score": 85},
        metadata={"mutation_kind": "work_order_sla_reminder", "producer": "p2"},
    )
    return result[0] if result else None
