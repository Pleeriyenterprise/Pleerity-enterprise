"""CEG producer dispatch helpers (P0 + P1)."""
from __future__ import annotations

import logging
from typing import Optional

from services.compliance_evidence_graph.config import graph_producers_enabled
from services.compliance_evidence_graph.producers.bootstrap import ensure_producers_initialized
from services.compliance_evidence_graph.producers.registry import ProducerContext, emit_for_mutation

logger = logging.getLogger(__name__)


async def dispatch_producer(ctx: ProducerContext) -> Optional[str]:
    """Non-blocking producer dispatch — never raises."""
    if not graph_producers_enabled():
        return None
    try:
        ensure_producers_initialized()
        return await emit_for_mutation(mutation_kind=ctx.mutation_kind, context=ctx)
    except Exception as exc:
        logger.warning("ceg producer dispatch failed: %s — %s", ctx.mutation_kind, exc)
        return None


async def dispatch_p0_producer(ctx: ProducerContext) -> Optional[str]:
    """Backward-compatible alias for P0 instrumentation sites."""
    return await dispatch_producer(ctx)


async def dispatch_p1_producer(ctx: ProducerContext) -> Optional[str]:
    """P1 instrumentation sites (same dispatch path as P0)."""
    return await dispatch_producer(ctx)
