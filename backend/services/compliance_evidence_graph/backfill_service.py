"""
Bounded historical backfill for Compliance Evidence Graph decisions.

Append-only, idempotent, observer-only. Never overwrites existing graph records.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database

logger = logging.getLogger(__name__)

DEFAULT_MAX_DECISIONS = 500


async def run_bounded_backfill(
    *,
    client_id: Optional[str] = None,
    max_decisions: int = DEFAULT_MAX_DECISIONS,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Reconstruct graph decisions from authoritative score history rows.

    Uses existing P0 score recalc producer semantics with ``backfill=True`` quality labels.
    Idempotent via producer dedupe keys on historical fact signatures.
    """
    from services.compliance_evidence_graph.config import graph_producers_enabled
    from services.compliance_evidence_graph.producers.registry import ProducerContext

    if not graph_producers_enabled():
        return {"ok": False, "reason": "producers_disabled", "backfilled": 0}

    db = database.get_db()
    q: Dict[str, Any] = {}
    if client_id:
        q["client_id"] = str(client_id).strip()

    cursor = db.property_compliance_score_history.find(q, {"_id": 0}).sort("created_at", -1).limit(max(1, max_decisions))
    rows = await cursor.to_list(max_decisions)

    backfilled = 0
    skipped = 0
    errors: List[str] = []

    for row in rows:
        cid = str(row.get("client_id") or "").strip()
        pid = str(row.get("property_id") or "").strip()
        if not cid or not pid:
            skipped += 1
            continue
        hist_at = row.get("created_at")
        dedupe_entity = f"{pid}:{hist_at}"
        if dry_run:
            backfilled += 1
            continue
        try:
            from services.compliance_evidence_graph.producers.bootstrap import ensure_producers_initialized

            ensure_producers_initialized()
            from services.compliance_evidence_graph.producers.hooks import dispatch_p0_producer

            dec = await dispatch_p0_producer(
                ProducerContext(
                    mutation_kind="compliance_score_recalc",
                    client_id=cid,
                    source_collection="property_compliance_score_history",
                    source_id=dedupe_entity,
                    property_id=pid,
                    correlation_id=f"BACKFILL:{dedupe_entity}",
                    mutation_timestamp=str(hist_at) if hist_at else None,
                    authoritative_payload={
                        "previous_score": row.get("previous_score"),
                        "new_score": row.get("new_score"),
                        "reason": row.get("reason") or "BACKFILL",
                        "backfill": True,
                    },
                    operational_context={"backfill": True},
                )
            )
            if dec:
                backfilled += 1
            else:
                skipped += 1
        except Exception as exc:
            errors.append(f"{dedupe_entity}:{exc}")
            logger.debug("backfill row skipped %s: %s", dedupe_entity, exc)

    return {
        "ok": True,
        "dry_run": dry_run,
        "candidates": len(rows),
        "backfilled": backfilled,
        "skipped": skipped,
        "errors": errors[:20],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
