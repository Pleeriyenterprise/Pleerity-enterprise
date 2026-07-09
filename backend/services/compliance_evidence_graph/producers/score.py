"""P0 producer — compliance score recalc and score ledger writes."""
from __future__ import annotations

from typing import Optional

from database import database

from services.compliance_evidence_graph.constants import DECISION_COMPLIANCE_SCORE_CHANGE
from services.compliance_evidence_graph.producers._base import build_dedupe_key
from services.compliance_evidence_graph.producers._emit import emit_p0_decision, fact_hash
from services.compliance_evidence_graph.producers.downstream import stamp_document
from services.compliance_evidence_graph.producers.registry import ProducerContext

_AUTHORITY = {
    "service": "compliance_scoring_service",
    "component": "recalculate_and_persist",
    "actor_type": "system",
}


async def handle_compliance_score_recalc(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    property_id = ctx.property_id or ctx.source_id
    correlation_id = ctx.correlation_id
    previous_score = payload.get("previous_score")
    new_score = payload.get("new_score")
    reason = payload.get("reason", "")

    sig = fact_hash(
        {
            "previous_score": previous_score,
            "new_score": new_score,
            "reason": reason,
            "correlation_id": correlation_id,
        }
    )
    dedupe_key = build_dedupe_key(
        mutation_kind="compliance_score_recalc",
        client_id=client_id,
        entity_id=property_id,
        fact_signature=sig,
    )

    outcome = "SCORE_CHANGED" if previous_score != new_score else "SCORE_UNCHANGED"
    snapshot_payload = {
        "compliance_score": {
            "property_id": property_id,
            "score_before": previous_score,
            "score_after": new_score,
            "delta": payload.get("delta"),
            "reason": reason,
        },
        "decision_reasoning_inputs": {
            "changed_requirements": payload.get("changed_requirements") or [],
            "trigger_reason": reason,
        },
    }

    result = await emit_p0_decision(
        decision_type=DECISION_COMPLIANCE_SCORE_CHANGE,
        decision_outcome=outcome,
        summary=f"Compliance score recalculated for property {property_id}: {previous_score} → {new_score}",
        source_collection="properties",
        source_id=property_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={**_AUTHORITY, "actor_id": payload.get("actor_id") or "compliance_recalc"},
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 100,
            "rule_certainty_score": 100,
            "decision_stability": "stable",
        },
        metadata={"mutation_kind": "compliance_score_recalc", "reason": reason},
    )
    if not result:
        return None

    decision_id, snapshot_id = result
    db = database.get_db()

    hist_at = payload.get("history_created_at")
    if hist_at:
        await stamp_document(
            db,
            "property_compliance_score_history",
            {"property_id": property_id, "client_id": client_id, "created_at": hist_at},
            decision_id=decision_id,
            snapshot_id=snapshot_id,
            operational_correlation_id=correlation_id,
        )

    log_at = payload.get("score_change_log_created_at")
    if log_at:
        await stamp_document(
            db,
            "score_change_log",
            {"property_id": property_id, "client_id": client_id, "created_at": log_at},
            decision_id=decision_id,
            snapshot_id=snapshot_id,
            operational_correlation_id=correlation_id,
        )

    return decision_id


async def handle_score_ledger_write(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    property_id = ctx.property_id or payload.get("property_id")
    ledger_id = ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="score_ledger_write",
        client_id=client_id,
        entity_id=ledger_id,
        fact_signature=fact_hash(
            {
                "before_score": payload.get("before_score"),
                "after_score": payload.get("after_score"),
                "trigger_type": payload.get("trigger_type"),
                "correlation_id": correlation_id,
            }
        ),
    )

    before_score = payload.get("before_score")
    after_score = payload.get("after_score")
    snapshot_payload = {
        "compliance_score": {
            "property_id": property_id,
            "score_before": before_score,
            "score_after": after_score,
            "delta": payload.get("delta"),
        },
        "decision_reasoning_inputs": {
            "trigger_type": payload.get("trigger_type"),
            "trigger_label": payload.get("trigger_label"),
            "ledger_id": ledger_id,
        },
    }

    result = await emit_p0_decision(
        decision_type=DECISION_COMPLIANCE_SCORE_CHANGE,
        decision_outcome="LEDGER_RECORDED",
        summary=f"Score ledger entry recorded for property {property_id}",
        source_collection="score_ledger_events",
        source_id=ledger_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        requirement_id=ctx.requirement_id or payload.get("requirement_id"),
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp or payload.get("created_at"),
        decision_authority={
            "service": "score_ledger_service",
            "component": "log_score_change",
            "actor_type": "system",
            "actor_id": payload.get("actor_id") or "score_ledger",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 100,
            "rule_certainty_score": 100,
        },
        document_ids=[payload["document_id"]] if payload.get("document_id") else None,
        metadata={"mutation_kind": "score_ledger_write", "ledger_id": ledger_id},
    )
    if not result:
        return None

    decision_id, snapshot_id = result
    db = database.get_db()
    await stamp_document(
        db,
        "score_ledger_events",
        {"_id": payload.get("ledger_object_id")},
        decision_id=decision_id,
        snapshot_id=snapshot_id,
        operational_correlation_id=correlation_id,
    )
    return decision_id


async def handle_admin_score_repair(ctx: ProducerContext) -> Optional[str]:
    """P1 — admin validate-compliance-score fix=true repair path."""
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    property_id = ctx.property_id or ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")
    previous_score = payload.get("previous_score")
    new_score = payload.get("new_score")

    dedupe_key = build_dedupe_key(
        mutation_kind="admin_score_repair",
        client_id=client_id,
        entity_id=property_id,
        fact_signature=fact_hash(
            {
                "previous_score": previous_score,
                "new_score": new_score,
                "correlation_id": correlation_id,
            }
        ),
    )

    snapshot_payload = {
        "compliance_score": {
            "property_id": property_id,
            "score_before": previous_score,
            "score_after": new_score,
            "repair_reason": payload.get("reason"),
        },
        "decision_reasoning_inputs": {
            "admin_validator_repair": True,
            "breakdown_diffs": payload.get("breakdown_diffs"),
        },
        "rule_lineage": {"lineage_complete": False, "lineage_incomplete": True, "lineage_incomplete_reason": "score_repair"},
    }

    result = await emit_p0_decision(
        decision_type=DECISION_COMPLIANCE_SCORE_CHANGE,
        decision_outcome="ADMIN_REPAIR",
        summary=f"Admin compliance score repair for property {property_id}: {previous_score} → {new_score}",
        source_collection="properties",
        source_id=property_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "routes.admin",
            "component": "validate_compliance_score",
            "actor_type": "admin",
            "actor_id": payload.get("actor_id") or "admin_validator",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 100,
            "human_verification_status": "approved",
            "rule_certainty_score": 100,
        },
        metadata={"mutation_kind": "admin_score_repair", "producer": "p1"},
    )
    return result[0] if result else None


async def handle_report_generation(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    report_artifact_id = payload.get("report_artifact_id") or ctx.source_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")
    generated_at = payload.get("generated_at") or ctx.mutation_timestamp

    dedupe_key = build_dedupe_key(
        mutation_kind="report_generation",
        client_id=client_id,
        entity_id=report_artifact_id,
        fact_signature=fact_hash(
            {
                "report_type": payload.get("report_type"),
                "generated_at": generated_at,
                "report_artifact_id": report_artifact_id,
            }
        ),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {
            "report_generation": {
                "report_artifact_id": report_artifact_id,
                "report_type": payload.get("report_type"),
                "client_id": client_id,
                "property_id": payload.get("property_id"),
                "portfolio_scope": payload.get("portfolio_scope"),
                "generated_at": generated_at,
                "delivery_context": payload.get("delivery_context"),
                "schedule_id": payload.get("schedule_id"),
                "filename": payload.get("filename"),
            }
        },
        "rule_lineage": {"lineage_complete": False, "lineage_incomplete": True, "lineage_optional": True},
    }
    result = await emit_p0_decision(
        decision_type=DECISION_COMPLIANCE_SCORE_CHANGE,
        decision_outcome="REPORT_GENERATED",
        summary=f"Compliance report generated: {payload.get('report_type', report_artifact_id)}",
        source_collection=ctx.source_collection,
        source_id=report_artifact_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=ctx.property_id or payload.get("property_id"),
        correlation_id=correlation_id,
        mutation_timestamp=generated_at or ctx.mutation_timestamp,
        decision_authority={
            "service": payload.get("authority_service") or "jobs",
            "component": payload.get("authority_component") or "ScheduledReportJob.process_scheduled_reports",
            "actor_type": "system",
            "actor_id": "report_generator",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={
            "evidence_completeness": "complete",
            "evidence_confidence_score": 95,
            "rule_certainty_score": 90,
            "decision_stability": "stable",
        },
        metadata={
            "mutation_kind": "report_generation",
            "producer": "p2",
            "report_artifact_id": report_artifact_id,
        },
    )
    return result[0] if result else None


async def handle_portfolio_recalc(ctx: ProducerContext) -> Optional[str]:
    payload = ctx.authoritative_payload or {}
    client_id = ctx.client_id
    correlation_id = ctx.correlation_id or payload.get("correlation_id")

    dedupe_key = build_dedupe_key(
        mutation_kind="portfolio_recalc",
        client_id=client_id,
        entity_id=client_id,
        fact_signature=fact_hash(
            {
                "properties_processed": payload.get("properties_processed"),
                "correlation_id": correlation_id,
            }
        ),
    )
    snapshot_payload = {
        "decision_reasoning_inputs": {"portfolio_recalc": payload},
        "rule_lineage": {"lineage_complete": False, "lineage_incomplete": True, "lineage_optional": True},
    }
    result = await emit_p0_decision(
        decision_type=DECISION_COMPLIANCE_SCORE_CHANGE,
        decision_outcome="PORTFOLIO_RECALC",
        summary=f"Portfolio compliance recalc for client {client_id}",
        source_collection="clients",
        source_id=client_id,
        dedupe_key=dedupe_key,
        client_id=client_id,
        correlation_id=correlation_id,
        mutation_timestamp=ctx.mutation_timestamp,
        decision_authority={
            "service": "compliance_scoring_service",
            "component": "portfolio_recalc",
            "actor_type": "system",
            "actor_id": "portfolio_recalc",
        },
        snapshot_payload=snapshot_payload,
        quality_inputs={"evidence_completeness": "complete", "rule_certainty_score": 95},
        metadata={"mutation_kind": "portfolio_recalc", "producer": "p2"},
    )
    return result[0] if result else None
