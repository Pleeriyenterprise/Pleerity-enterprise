"""Phase 2B P0 producer dispatch helpers."""
from __future__ import annotations

import logging
from typing import Optional

from services.compliance_evidence_graph.config import graph_producers_enabled
from services.compliance_evidence_graph.producers.bootstrap import ensure_p0_producers_initialized
from services.compliance_evidence_graph.producers.registry import ProducerContext, emit_for_mutation

logger = logging.getLogger(__name__)


async def dispatch_p0_producer(ctx: ProducerContext) -> Optional[str]:
    """Non-blocking P0 producer dispatch — never raises."""
    if not graph_producers_enabled():
        return None
    try:
        ensure_p0_producers_initialized()
        return await emit_for_mutation(mutation_kind=ctx.mutation_kind, context=ctx)
    except Exception as exc:
        logger.warning("ceg P0 dispatch failed: %s — %s", ctx.mutation_kind, exc)
        return None
