"""
Bounded idempotency for client maintenance issue create (F1 / G9 remediation).

Same actor + property + normalized payload within a short window returns the existing issue
with idempotent_replay=True — no second operational debt row.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from services import maintenance_issues_service

logger = logging.getLogger(__name__)

DEDUPE_COLLECTION = "maintenance_issue_create_dedupe"
# Bounded window for accidental double-submit / rapid duplicate POST (not a global dedupe framework).
IDEMPOTENCY_WINDOW_SECONDS = 90
_INFLIGHT_POLL_ATTEMPTS = 25
_INFLIGHT_POLL_INTERVAL_S = 0.12

_indexes_ensured = False


def normalize_issue_create_fields(description: str, category: Optional[str]) -> Tuple[str, str]:
    desc_norm = " ".join((description or "").strip().lower().split())
    cat_norm = (category or "general").strip().lower() or "general"
    return desc_norm, cat_norm


def build_issue_create_fingerprint(
    *,
    client_id: str,
    property_id: str,
    actor_id: Optional[str],
    description: str,
    category: Optional[str],
) -> str:
    desc_norm, cat_norm = normalize_issue_create_fields(description, category)
    actor = (actor_id or "").strip()
    raw = f"{client_id}\x1f{property_id}\x1f{actor}\x1f{cat_norm}\x1f{desc_norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def ensure_issue_create_dedupe_indexes(db) -> None:
    global _indexes_ensured
    if _indexes_ensured:
        return
    coll = db[DEDUPE_COLLECTION]
    try:
        await coll.create_index("fingerprint", unique=True)
        await coll.create_index("expires_at", expireAfterSeconds=0)
    except Exception as exc:
        logger.debug("issue create dedupe index ensure skip: %s", exc)
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


async def _load_issue_for_replay(issue_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    doc = await maintenance_issues_service.get_issue(issue_id, client_id=client_id)
    if not doc:
        return None
    doc = dict(doc)
    doc["idempotent_replay"] = True
    return doc


async def issue_create_begin(
    db,
    *,
    fingerprint: str,
    client_id: str,
    property_id: str,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Returns (mode, issue_doc):
      - ("create", None) — caller should create a new issue
      - ("replay", doc) — return existing issue (idempotent)
      - ("in_progress", None) — parallel create still running; caller should 409
    """
    await ensure_issue_create_dedupe_indexes(db)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=IDEMPOTENCY_WINDOW_SECONDS)

    for attempt in range(2):
        try:
            await db[DEDUPE_COLLECTION].insert_one(
                {
                    "fingerprint": fingerprint,
                    "client_id": client_id,
                    "property_id": property_id,
                    "issue_id": None,
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
            issue_id = row.get("issue_id")
            if issue_id:
                replay = await _load_issue_for_replay(str(issue_id), client_id)
                if replay:
                    return "replay", replay
            # In-flight: another request is creating
            for _ in range(_INFLIGHT_POLL_ATTEMPTS):
                await asyncio.sleep(_INFLIGHT_POLL_INTERVAL_S)
                row = await db[DEDUPE_COLLECTION].find_one({"fingerprint": fingerprint})
                if row and row.get("issue_id"):
                    replay = await _load_issue_for_replay(str(row["issue_id"]), client_id)
                    if replay:
                        return "replay", replay
            return "in_progress", None
    return "in_progress", None


async def issue_create_complete(db, *, fingerprint: str, issue_id: str) -> None:
    await db[DEDUPE_COLLECTION].update_one(
        {"fingerprint": fingerprint},
        {"$set": {"issue_id": issue_id}},
    )


async def issue_create_abort(db, *, fingerprint: str) -> None:
    """Remove in-flight dedupe slot so a failed create can be retried honestly."""
    await db[DEDUPE_COLLECTION].delete_one({"fingerprint": fingerprint, "issue_id": None})
