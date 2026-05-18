"""
Scheduled pilot lifecycle reconciliation — expiry transitions (idempotent, audited).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from database import database
from models.pilot_lifecycle import PilotStatus
from services.pilot_lifecycle_service import reconcile_pilot_operational_state, sync_expired_if_due

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (
    PilotStatus.ACTIVE.value,
    PilotStatus.EXTENDED.value,
)


async def reconcile_pilot_lifecycle_batch(*, limit: int = 500) -> Dict[str, Any]:
    """
    Scan pilot accounts past effective expiry and transition to expired (platform governance).

    Idempotent per client/date via pilot_lifecycle_service idempotency keys.
    Stripe subscription state is not mutated here — Stripe remains billing authority.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    cursor = (
        db.clients.find(
            {"pilot_status": {"$in": list(_ACTIVE_STATUSES)}},
            {"_id": 0, "client_id": 1, "pilot_status": 1, "pilot_expires_at": 1, "pilot_extended_until": 1},
        )
        .limit(limit)
    )

    scanned = 0
    expired = 0
    reconciled = 0
    anomalies_detected = 0
    errors: List[str] = []

    async for doc in cursor:
        scanned += 1
        cid = doc.get("client_id")
        if not cid:
            continue
        try:
            if await sync_expired_if_due(cid):
                expired += 1
                logger.info("pilot_lifecycle_reconcile: marked expired client_id=%s", cid)
            rec = await reconcile_pilot_operational_state(cid)
            reconciled += 1
            anomalies_detected += len(rec.get("operational_sync", {}).get("anomaly_ids") or [])
            if rec.get("inconsistencies"):
                logger.warning(
                    "pilot_lifecycle_reconcile inconsistencies client_id=%s: %s",
                    cid,
                    rec["inconsistencies"],
                )
        except Exception as ex:
            msg = f"{cid}:{ex}"
            errors.append(msg)
            logger.exception("pilot_lifecycle_reconcile failed client_id=%s", cid)

    # Also reconcile non-active pilot accounts with open operational state (sample)
    other_cursor = (
        db.clients.find(
            {
                "pilot_status": {"$exists": True, "$nin": list(_ACTIVE_STATUSES)},
                "pilot_operational_updated_at": {"$exists": False},
            },
            {"_id": 0, "client_id": 1},
        )
        .limit(min(100, limit))
    )
    async for doc in other_cursor:
        cid = doc.get("client_id")
        if not cid:
            continue
        try:
            await reconcile_pilot_operational_state(cid)
            reconciled += 1
        except Exception:
            pass

    result = {
        "scanned": scanned,
        "expired_transitions": expired,
        "operational_reconciled": reconciled,
        "anomalies_detected": anomalies_detected,
        "errors": errors,
        "completed_at": now.isoformat(),
    }
    logger.info("pilot_lifecycle_reconcile batch complete: %s", result)
    return result
