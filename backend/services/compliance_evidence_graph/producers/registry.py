"""
Producer registry — metadata catalogue and dispatch contract.

Phase 2A: registry and dispatch exist; live emit is disabled until producer modules
implement handlers in 2B+.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from services.compliance_evidence_graph.config import graph_producers_enabled

logger = logging.getLogger(__name__)

VALIDATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class ProducerContext:
    """Post-authoritative-write context passed to producers (Phase 2B+)."""

    mutation_kind: str
    client_id: str
    source_collection: str
    source_id: str
    property_id: Optional[str] = None
    requirement_id: Optional[str] = None
    correlation_id: Optional[str] = None
    mutation_timestamp: Optional[str] = None
    authoritative_payload: Dict[str, Any] = field(default_factory=dict)
    operational_context: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProducerRegistryEntry:
    mutation_kind: str
    priority: str  # P0 | P1 | P2
    producer_module: str
    description: str
    stream_e_ref: Optional[str] = None
    implementation_stage: str = "2B"
    status: str = "planned"
    emit_implemented: bool = False


ProducerHandler = Callable[[ProducerContext], Any]

_REGISTRY: Dict[str, ProducerRegistryEntry] = {}
_HANDLERS: Dict[str, ProducerHandler] = {}


def _seed_registry() -> None:
    if _REGISTRY:
        return
    entries = [
        ("evidence_authority_sync", "P0", "authority_sync.py", "Evidence authority sync", "9"),
        ("compliance_score_recalc", "P0", "score.py", "Compliance score recalc", None),
        ("score_ledger_write", "P0", "score.py", "Score ledger write", None),
        ("evidence_review_transition", "P0", "review.py", "Evidence review transition", "6-8"),
        ("outcome_engine_event", "P0", "outcome.py", "Outcome engine event", "Appendix"),
        ("applicability_operator", "P1", "applicability.py", "Applicability operator", "12"),
        ("property_jurisdiction_materialization", "P1", "applicability.py", "Property jurisdiction materialization", "11"),
        ("requirement_materialization", "P1", "applicability.py", "Requirement materialization", "11"),
        ("registry_publish", "P1", "applicability.py", "Registry publish", None),
        ("risk_signal_generation", "P1", "risk.py", "Risk signal generation", None),
        ("risk_signal_regen_worker", "P1", "risk.py", "Risk regen worker", None),
        ("document_extraction_apply", "P1", "document.py", "Document extraction apply", None),
        ("document_extraction_reject", "P1", "document.py", "Document extraction reject", None),
        ("cer_linkage", "P1", "evidence.py", "CER linkage", None),
        ("supporting_document_linkage", "P1", "evidence.py", "Supporting document linkage", None),
        ("admin_score_repair", "P1", "score.py", "Admin score repair", "19"),
        ("daily_reminder", "P2", "reminder.py", "Daily reminder", None),
        ("notification_sent", "P2", "notification.py", "Notification sent", None),
        ("work_order_lifecycle", "P2", "work_order.py", "Work order lifecycle", "17"),
        ("report_generation", "P2", "score.py", "Report generation", None),
        ("knowledge_reference", "P2", "knowledge.py", "Knowledge reference attach", None),
    ]
    stage_map = {"P0": "2B", "P1": "2C", "P2": "2D"}
    for kind, priority, module, desc, ref in entries:
        _REGISTRY[kind] = ProducerRegistryEntry(
            mutation_kind=kind,
            priority=priority,
            producer_module=module,
            description=desc,
            stream_e_ref=ref,
            implementation_stage=stage_map[priority],
            status="planned",
            emit_implemented=False,
        )


def register_producer_metadata(entry: ProducerRegistryEntry) -> None:
    _seed_registry()
    _REGISTRY[entry.mutation_kind] = entry


def register_producer_handler(mutation_kind: str, handler: ProducerHandler) -> None:
    """Register emit handler — only used when emit_implemented=True (Phase 2B+)."""
    _seed_registry()
    _HANDLERS[mutation_kind] = handler


def list_producer_registry() -> List[Dict[str, Any]]:
    _seed_registry()
    return [
        {
            "mutation_kind": e.mutation_kind,
            "priority": e.priority,
            "producer_module": e.producer_module,
            "description": e.description,
            "stream_e_ref": e.stream_e_ref,
            "implementation_stage": e.implementation_stage,
            "status": e.status,
            "emit_implemented": e.emit_implemented,
            "live_emit_active": e.emit_implemented and graph_producers_enabled(),
        }
        for e in sorted(_REGISTRY.values(), key=lambda x: (x.priority, x.mutation_kind))
    ]


def get_registry_entry(mutation_kind: str) -> Optional[ProducerRegistryEntry]:
    _seed_registry()
    return _REGISTRY.get(mutation_kind)


async def emit_for_mutation(*, mutation_kind: str, context: ProducerContext) -> Optional[str]:
    """
    Dispatch contract for mutation-site instrumentation.

    Phase 2A: returns None always — no live graph decisions emitted.
    Phase 2B+: dispatches to registered handler when emit_implemented=True.
    """
    if not graph_producers_enabled():
        logger.debug("ceg producer dispatch skipped: producers disabled (mode)")
        return None

    entry = get_registry_entry(mutation_kind)
    if not entry:
        logger.warning("ceg producer dispatch: unknown mutation_kind=%s", mutation_kind)
        return None

    if not entry.emit_implemented:
        logger.debug(
            "ceg producer dispatch deferred: %s (stage %s)",
            mutation_kind,
            entry.implementation_stage,
        )
        return None

    handler = _HANDLERS.get(mutation_kind)
    if not handler:
        logger.warning("ceg producer handler missing for implemented kind=%s", mutation_kind)
        return None

    try:
        result = handler(context)
        if hasattr(result, "__await__"):
            return await result
        return result
    except Exception as exc:
        logger.warning("ceg producer dispatch failed: %s — %s", mutation_kind, exc)
        return None
