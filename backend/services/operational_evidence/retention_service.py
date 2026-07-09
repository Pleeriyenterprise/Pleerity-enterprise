"""
Operational Evidence Platform — retention tiering (append-only).

Marks events older than the warm threshold as warm tier. Does not delete or mutate
runtime evidence fields beyond retention metadata.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from database import database

from services.operational_evidence.constants import (
    ARCHIVED_RETENTION_TIERS,
    COLLECTION_EVENTS,
    RETENTION_TIER_HOT,
    RETENTION_TIER_WARM,
    RETENTION_WARM_AFTER_DAYS,
)

logger = logging.getLogger(__name__)


async def apply_warm_retention_tier(
    *,
    warm_after_days: int = RETENTION_WARM_AFTER_DAYS,
    batch_limit: int = 2000,
) -> Dict[str, Any]:
    """Move hot-tier events older than warm_after_days to warm tier (bounded batch)."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=max(1, min(warm_after_days, 365)))).isoformat()
    now_iso = now.isoformat()

    filt = {
        "occurred_at": {"$lt": cutoff},
        "$or": [
            {"retention.tier": {"$exists": False}},
            {"retention.tier": RETENTION_TIER_HOT},
        ],
    }
    candidates = await db[COLLECTION_EVENTS].count_documents(filt)
    ids = (
        await db[COLLECTION_EVENTS]
        .find(filt, {"_id": 1})
        .sort("occurred_at", 1)
        .limit(batch_limit)
        .to_list(batch_limit)
    )
    if not ids:
        return {
            "warm_after_days": warm_after_days,
            "cutoff": cutoff,
            "candidates": candidates,
            "modified": 0,
        }

    result = await db[COLLECTION_EVENTS].update_many(
        {"_id": {"$in": [d["_id"] for d in ids]}},
        {
            "$set": {
                "retention.tier": RETENTION_TIER_WARM,
                "retention.archived_at": now_iso,
                "retention.warm_after_days": warm_after_days,
            }
        },
    )
    logger.info(
        "operational_evidence retention: warm tier applied modified=%s candidates=%s",
        result.modified_count,
        candidates,
    )
    return {
        "warm_after_days": warm_after_days,
        "cutoff": cutoff,
        "candidates": candidates,
        "modified": result.modified_count,
        "batch_limit": batch_limit,
    }


async def get_retention_stats() -> Dict[str, Any]:
    db = database.get_db()
    pipeline = [
        {
            "$group": {
                "_id": {"$ifNull": ["$retention.tier", RETENTION_TIER_HOT]},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
    ]
    rows = await db[COLLECTION_EVENTS].aggregate(pipeline).to_list(10)
    by_tier = {str(r["_id"]): r["count"] for r in rows}
    archived = sum(by_tier.get(t, 0) for t in ARCHIVED_RETENTION_TIERS)
    total = sum(by_tier.values())
    return {
        "total_events": total,
        "archived_count": archived,
        "hot_count": by_tier.get(RETENTION_TIER_HOT, 0) + by_tier.get("null", 0),
        "warm_count": by_tier.get(RETENTION_TIER_WARM, 0),
        "cold_count": by_tier.get("cold", 0),
        "by_tier": by_tier,
        "warm_after_days": RETENTION_WARM_AFTER_DAYS,
    }
