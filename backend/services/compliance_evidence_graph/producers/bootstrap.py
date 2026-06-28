"""Register Phase 2B P0 and Phase 2C P1 producer handlers."""

from __future__ import annotations



from services.compliance_evidence_graph.producers import (

    applicability,

    authority_sync,

    document,

    evidence,

    outcome,

    review,

    risk,

    score,

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



_P0_INITIALIZED = False

_P1_INITIALIZED = False





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





def ensure_p0_producers_initialized() -> None:

    initialize_p0_producers()





def ensure_p1_producers_initialized() -> None:

    initialize_p1_producers()





def ensure_producers_initialized() -> None:

    initialize_p0_producers()

    initialize_p1_producers()


