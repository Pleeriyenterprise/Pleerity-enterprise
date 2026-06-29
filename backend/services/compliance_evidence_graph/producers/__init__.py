"""Compliance Evidence Graph — mutation producers (Phase 2)."""
from services.compliance_evidence_graph.producers.bootstrap import (
    ensure_p0_producers_initialized,
    ensure_p1_producers_initialized,
    ensure_p2_producers_initialized,
    ensure_producers_initialized,
)
from services.compliance_evidence_graph.producers.hooks import (
    dispatch_p0_producer,
    dispatch_p1_producer,
    dispatch_p2_producer,
    dispatch_producer,
)
from services.compliance_evidence_graph.producers.registry import (
    ProducerContext,
    emit_for_mutation,
    list_producer_registry,
    register_producer_metadata,
)

__all__ = [
    "ProducerContext",
    "dispatch_p0_producer",
    "dispatch_p1_producer",
    "dispatch_producer",
    "emit_for_mutation",
    "ensure_p0_producers_initialized",
    "ensure_p1_producers_initialized",
    "ensure_p2_producers_initialized",
    "ensure_producers_initialized",
    "list_producer_registry",
    "register_producer_metadata",
]
