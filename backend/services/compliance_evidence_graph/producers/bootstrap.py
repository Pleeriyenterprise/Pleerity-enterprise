"""Register Phase 2B P0 producer handlers."""
from __future__ import annotations

from services.compliance_evidence_graph.producers import authority_sync, outcome, review, score
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

_INITIALIZED = False


def initialize_p0_producers() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    for mutation_kind, handler in _P0_HANDLERS.items():
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
                    implementation_stage="2B",
                    status="implemented",
                    emit_implemented=True,
                )
            )
    _INITIALIZED = True


def ensure_p0_producers_initialized() -> None:
    initialize_p0_producers()
