"""
Bounded idempotency for client maintenance issue → work order conversion (F2 / G9 remediation).

Same actor + issue + client within a short window returns the existing work order with
idempotent_replay=True — no second visible operational debt row.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from services import maintenance_service

logger = logging.getLogger(__name__)

DEDUPE_COLLECTION = "maintenance_wo_from_issue_dedupe"
IDEMPOTENCY_WINDOW_SECONDS = 90
_INFLIGHT_POLL_ATTEMPTS = 25
_INFLIGHT_POLL_INTERVAL_S = 0.12

_indexes_ensured = False


def build_wo_from_issue_fingerprint(
    *,
    client_id: str,
    property_id: str,
    issue_id: str,
    actor_id: Optional[str],
) -> str:
    actor = (actor_id or "").strip()
    raw = f"{client_id}\x1f{property_id}\x1f{issue_id}\x1f{actor}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def ensure_wo_from_issue_dedupe_indexes(db) -> None:
    global _indexes_ensured
    if _indexes_ensured:
        return
    coll = db[DEDUPE_COLLECTION]
    try:
        await coll.create_index("fingerprint", unique=True)
        await coll.create_index("expires_at", expireAfterSeconds=0)
    except Exception as exc:
        logger.debug("wo from issue dedupe index ensure skip: %s", exc)
    _indexes_ensured = True


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _row_within_window(row: Dict[str, Any], now: datetime) -> bool:
    created = _parse_ts(row.get("created_at"))
    if created is None:
        return False
    return (now - created) <= timedelta(seconds=IDEMPOTENCY_WINDOW_SECONDS)


async def find_existing_work_order_for_issue(issue_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """Return the latest non-cancelled work order already linked to this issue."""
    from database import database

    db = database.get_db()
    row = await db.work_orders.find_one(
        {
            "issue_id": issue_id,
            "client_id": client_id,
            "status": {"$nin": ["CANCELLED", "cancelled"]},
        },
        {"_id": 0, "work_order_id": 1},
        sort=[("created_at", -1)],
    )
    if not row or not row.get("work_order_id"):
        return None
    doc = await maintenance_service.get_work_order(str(row["work_order_id"]))
    if not doc:
        return None
    doc = dict(doc)
    doc["idempotent_replay"] = True
    return doc


async def _load_wo_for_replay(work_order_id: str) -> Optional[Dict[str, Any]]:
    doc = await maintenance_service.get_work_order(work_order_id)
    if not doc:
        return None
    doc = dict(doc)
    doc["idempotent_replay"] = True
    return doc


async def wo_from_issue_begin(
    db,
    *,
    fingerprint: str,
    client_id: str,
    property_id: str,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Returns (mode, work_order_doc):
      - ("create", None) — caller should create a new work order
      - ("replay", doc) — return existing work order (idempotent)
      - ("in_progress", None) — parallel create still running; caller should 409
    """
    await ensure_wo_from_issue_dedupe_indexes(db)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=IDEMPOTENCY_WINDOW_SECONDS)

    for attempt in range(2):
        try:
            await db[DEDUPE_COLLECTION].insert_one(
                {
                    "fingerprint": fingerprint,
                    "client_id": client_id,
                    "property_id": property_id,
                    "work_order_id": None,
                    "created_at": now.isoformat(),
                    "expires_at": expires_at,
                }
            )
            return "create", None
        except DuplicateKeyError:
            row = await db[DEDUPE_COLLECTION].find_one({"fingerprint": fingerprint})
            if not row:
                continue
            if not _row_within_window(row, now):
                await db[DEDUPE_COLLECTION].delete_one({"fingerprint": fingerprint})
                if attempt == 0:
                    continue
                return "create", None
            wo_id = row.get("work_order_id")
            if wo_id:
                replay = await _load_wo_for_replay(str(wo_id))
                if replay:
                    return "replay", replay
            for _ in range(_INFLIGHT_POLL_ATTEMPTS):
                await asyncio.sleep(_INFLIGHT_POLL_INTERVAL_S)
                row = await db[DEDUPE_COLLECTION].find_one({"fingerprint": fingerprint})
                if row and row.get("work_order_id"):
                    replay = await _load_wo_for_replay(str(row["work_order_id"]))
                    if replay:
                        return "replay", replay
            return "in_progress", None
    return "in_progress", None


async def wo_from_issue_complete(db, *, fingerprint: str, work_order_id: str) -> None:
    await db[DEDUPE_COLLECTION].update_one(
        {"fingerprint": fingerprint},
        {"$set": {"work_order_id": work_order_id}},
    )


async def wo_from_issue_abort(db, *, fingerprint: str) -> None:
    """Remove in-flight dedupe slot so a failed create can be retried honestly."""
    await db[DEDUPE_COLLECTION].delete_one({"fingerprint": fingerprint, "work_order_id": None})
