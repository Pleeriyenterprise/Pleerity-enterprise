"""
Idempotent reconciliation: enqueue compliance recalculation for properties whose persisted
scores are missing or explicitly pending, so existing tenants converge without one-off scripts.

Uses compliance_recalc_queue only — worker runs compliance_scoring_service.recalculate_and_persist.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from database import database
from services.compliance_recalc_queue import (
    ACTOR_SYSTEM,
    TRIGGER_RECONCILIATION_BATCH,
    enqueue_compliance_recalc,
)

logger = logging.getLogger(__name__)


async def enqueue_reconciliation_for_properties(
    *,
    client_id: Optional[str] = None,
    include_missing_score: bool = True,
    include_pending_flag: bool = True,
    max_properties: int = 2000,
) -> Dict[str, Any]:
    """
    Scan properties (optionally scoped to one client) and enqueue recalc for rows that need repair.

    Idempotent: each enqueue uses a stable correlation_id per property for this batch type.
    """
    db = database.get_db()
    filt: Dict[str, Any] = {}
    if client_id:
        filt["client_id"] = client_id

    or_clauses: List[Dict[str, Any]] = []
    if include_missing_score:
        or_clauses.append({"compliance_score": None})
    if include_pending_flag:
        or_clauses.append({"compliance_score_pending": True})

    if not or_clauses:
        return {"enqueued": 0, "skipped": 0, "property_ids": []}

    filt["$or"] = or_clauses

    cursor = db.properties.find(
        filt,
        {"_id": 0, "property_id": 1, "client_id": 1},
    ).limit(max_properties)

    enqueued = 0
    skipped = 0
    ids: List[str] = []
    async for row in cursor:
        pid = str(row.get("property_id") or "").strip()
        cid = str(row.get("client_id") or "").strip()
        if not pid or not cid:
            skipped += 1
            continue
        corr = f"{TRIGGER_RECONCILIATION_BATCH}:{pid}"
        ok = await enqueue_compliance_recalc(
            property_id=pid,
            client_id=cid,
            trigger_reason=TRIGGER_RECONCILIATION_BATCH,
            actor_type=ACTOR_SYSTEM,
            actor_id=None,
            correlation_id=corr,
        )
        if ok:
            enqueued += 1
            ids.append(pid)
        else:
            skipped += 1

    logger.info(
        "compliance_score reconciliation batch client_id=%s enqueued=%s skipped=%s",
        client_id or "ALL",
        enqueued,
        skipped,
    )
    return {
        "enqueued": enqueued,
        "skipped": skipped,
        "property_ids": ids[:500],
        "truncated_ids": len(ids) > 500,
    }
