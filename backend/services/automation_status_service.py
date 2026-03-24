"""
Per-client automation heartbeat timestamps (additive; does not replace domain-derived freshness).
Written from workers when compliance recalc completes and when risk signals are regenerated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database

COLLECTION = "automation_status"


async def record_score_recalc(client_id: Optional[str]) -> None:
    if not client_id:
        return
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db[COLLECTION].update_one(
        {"client_id": client_id},
        {
            "$set": {"last_score_recalc_at": now, "updated_at": now},
            "$setOnInsert": {"client_id": client_id},
        },
        upsert=True,
    )


async def record_risk_refresh(client_id: Optional[str]) -> None:
    if not client_id:
        return
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db[COLLECTION].update_one(
        {"client_id": client_id},
        {
            "$set": {"last_risk_refresh_at": now, "updated_at": now},
            "$setOnInsert": {"client_id": client_id},
        },
        upsert=True,
    )


async def get_record(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    doc = await db[COLLECTION].find_one({"client_id": client_id}, {"_id": 0})
    return doc or {}
