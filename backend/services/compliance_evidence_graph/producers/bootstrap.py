"""Register Phase 2B P0, Phase 2C P1, and Phase 2D P2 producer handlers."""
from __future__ import annotations

from services.compliance_evidence_graph.producers import (
    applicability,
    authority_sync,
    document,
    evidence,
    knowledge,
    notification,
    operational_bridge,
    outcome,
    reminder,
    review,
    risk,
    score,
    work_order,
)
from services.compliance_evidence_graph.producers.registry import (
    ProducerRegistryEntry,
    get_registry_entry,
    register_producer_handler,
    register_producer_metadata,
)

_P0_HANDLERS = {
    "evidence_authority_sync": authority_sync.handle_evidence_authority_sync,
    "compliance_score_recalc": score.handle_compliance_score_recalc,
    "score_ledger_write": score.handle_score_ledger_write,
    "evidence_review_transition": review.handle_evidence_review_transition,
    "outcome_engine_event": outcome.handle_outcome_engine_event,
}

_P1_HANDLERS = {
    "applicability_operator": applicability.handle_applicability_operator,
    "property_jurisdiction_materialization": applicability.handle_property_jurisdiction_materialization,
    "requirement_materialization": applicability.handle_requirement_materialization,
    "registry_publish": applicability.handle_registry_publish,
    "risk_signal_generation": risk.handle_risk_signal_generation,
    "risk_signal_regen_worker": risk.handle_risk_signal_regen_worker,
    "document_extraction_apply": document.handle_document_extraction_apply,
    "document_extraction_reject": document.handle_document_extraction_reject,
    "cer_linkage": evidence.handle_cer_linkage,
    "supporting_document_linkage": evidence.handle_supporting_document_linkage,
    "admin_score_repair": score.handle_admin_score_repair,
}

_P2_HANDLERS = {
    "daily_reminder": reminder.handle_daily_reminder,
    "reminder_cancelled": reminder.handle_reminder_cancelled,
    "monthly_digest": reminder.handle_monthly_digest,
    "notification_queued": notification.handle_notification_queued,
    "notification_sent": notification.handle_notification_sent,
    "compliance_status_alert": notification.handle_compliance_status_alert,
    "work_order_lifecycle": work_order.handle_work_order_lifecycle,
    "maintenance_issue_lifecycle": work_order.handle_maintenance_issue_lifecycle,
    "work_order_sla_reminder": work_order.handle_work_order_sla_reminder,
    "report_generation": score.handle_report_generation,
    "portfolio_recalc": score.handle_portfolio_recalc,
    "knowledge_reference": knowledge.handle_knowledge_reference,
    "tenant_delivery_proof": operational_bridge.handle_tenant_delivery_proof,
    "operational_incident_bridge": operational_bridge.handle_operational_incident_bridge,
}

_P0_INITIALIZED = False
_P1_INITIALIZED = False
_P2_INITIALIZED = False


def _register_handlers(handlers: dict, *, stage: str) -> None:
    for mutation_kind, handler in handlers.items():
        register_producer_handler(mutation_kind, handler)
        entry = get_registry_entry(mutation_kind)
        if entry:
            register_producer_metadata(
                ProducerRegistryEntry(
                    mutation_kind=entry.mutation_kind,
                    priority=entry.priority,
                    producer_module=entry.producer_module,
                    description=entry.description,
                    stream_e_ref=entry.stream_e_ref,
                    implementation_stage=stage,
                    status="implemented",
                    emit_implemented=True,
                )
            )


def initialize_p0_producers() -> None:
    global _P0_INITIALIZED
    if _P0_INITIALIZED:
        return
    _register_handlers(_P0_HANDLERS, stage="2B")
    _P0_INITIALIZED = True


def initialize_p1_producers() -> None:
    global _P1_INITIALIZED
    if _P1_INITIALIZED:
        return
    _register_handlers(_P1_HANDLERS, stage="2C")
    _P1_INITIALIZED = True


def initialize_p2_producers() -> None:
    global _P2_INITIALIZED
    if _P2_INITIALIZED:
        return
    _register_handlers(_P2_HANDLERS, stage="2D")
    _P2_INITIALIZED = True


def ensure_p0_producers_initialized() -> None:
    initialize_p0_producers()


def ensure_p1_producers_initialized() -> None:
    initialize_p1_producers()


def ensure_p2_producers_initialized() -> None:
    initialize_p2_producers()


def ensure_producers_initialized() -> None:
    initialize_p0_producers()
    initialize_p1_producers()
    initialize_p2_producers()
