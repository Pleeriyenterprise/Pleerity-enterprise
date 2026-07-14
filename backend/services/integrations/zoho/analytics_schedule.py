"""Staging Analytics schedule helpers — run lock and schedule metadata."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pymongo.errors import DuplicateKeyError

from database import database
from services.integrations.zoho.config import (
    zoho_analytics_schedule_registration_allowed,
    zoho_analytics_sync_enabled,
    zoho_integration_enabled,
    zoho_kill_switch_active,
)
from services.integrations.zoho.types import (
    ANALYTICS_EXPORT_JOB_ID,
    ANALYTICS_EXPORT_LOCK_ID,
    ANALYTICS_EXPORT_SCHEDULE_CADENCE,
    ZOHO_ANALYTICS_EXPORT_LOCKS_COLLECTION,
)

logger = logging.getLogger(__name__)

# Long enough for one export + soft retries buffer; short enough to heal after crash.
DEFAULT_LOCK_TTL_SECONDS = 45 * 60


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        t = value
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc)
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        t = datetime.fromisoformat(s)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc)
    except ValueError:
        return None


def next_daily_run_utc(hour: int = 2, minute: int = 15, *, now: Optional[datetime] = None) -> datetime:
    """Next occurrence of daily HH:MM UTC at or after ``now``."""
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    else:
        clock = clock.astimezone(timezone.utc)
    candidate = clock.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= clock:
        candidate = candidate + timedelta(days=1)
    return candidate


def new_lock_owner() -> str:
    return f"analytics-export-{uuid.uuid4().hex[:16]}"


async def acquire_analytics_export_lock(
    owner: str,
    *,
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
) -> bool:
    """
    Database-backed mutual exclusion for Analytics export.

    Complements APScheduler max_instances=1 (process-local) for multi-instance /
    memory-jobstore fallback safety.
    """
    db = database.get_db()
    if db is None:
        logger.warning("analytics export lock: database unavailable")
        return False
    coll = db[ZOHO_ANALYTICS_EXPORT_LOCKS_COLLECTION]
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
    doc = {
        "_id": ANALYTICS_EXPORT_LOCK_ID,
        "owner": owner,
        "acquired_at": now_iso,
        "expires_at": expires_at,
        "job_id": ANALYTICS_EXPORT_JOB_ID,
    }
    try:
        await coll.insert_one(doc)
        return True
    except DuplicateKeyError:
        existing = await coll.find_one({"_id": ANALYTICS_EXPORT_LOCK_ID})
        if not existing:
            return False
        exp = _parse_iso(existing.get("expires_at"))
        if exp is not None and exp <= now:
            result = await coll.find_one_and_update(
                {
                    "_id": ANALYTICS_EXPORT_LOCK_ID,
                    "expires_at": existing.get("expires_at"),
                },
                {
                    "$set": {
                        "owner": owner,
                        "acquired_at": now_iso,
                        "expires_at": expires_at,
                        "job_id": ANALYTICS_EXPORT_JOB_ID,
                    }
                },
            )
            return result is not None
        return False
    except Exception:
        logger.exception("analytics export lock acquire failed")
        return False


async def release_analytics_export_lock(owner: str) -> None:
    db = database.get_db()
    if db is None:
        return
    try:
        await db[ZOHO_ANALYTICS_EXPORT_LOCKS_COLLECTION].delete_one(
            {"_id": ANALYTICS_EXPORT_LOCK_ID, "owner": owner}
        )
    except Exception:
        logger.exception("analytics export lock release failed owner=%s", owner)


async def analytics_export_run_lock_status() -> Dict[str, Any]:
    db = database.get_db()
    if db is None:
        return {"held": False, "status": "unavailable", "owner": None, "expires_at": None}
    try:
        existing = await db[ZOHO_ANALYTICS_EXPORT_LOCKS_COLLECTION].find_one(
            {"_id": ANALYTICS_EXPORT_LOCK_ID},
            {"_id": 0, "owner": 1, "acquired_at": 1, "expires_at": 1},
        )
    except Exception:
        return {"held": False, "status": "error", "owner": None, "expires_at": None}
    if not existing:
        return {"held": False, "status": "free", "owner": None, "expires_at": None}
    now = datetime.now(timezone.utc)
    exp = _parse_iso(existing.get("expires_at"))
    if exp is not None and exp <= now:
        return {
            "held": False,
            "status": "expired",
            "owner": existing.get("owner"),
            "acquired_at": existing.get("acquired_at"),
            "expires_at": existing.get("expires_at"),
        }
    return {
        "held": True,
        "status": "held",
        "owner": existing.get("owner"),
        "acquired_at": existing.get("acquired_at"),
        "expires_at": existing.get("expires_at"),
    }


def scheduler_job_next_run_iso() -> Optional[str]:
    """Read next_run_time from in-process APScheduler, if registered."""
    try:
        from server import scheduler

        job = scheduler.get_job(ANALYTICS_EXPORT_JOB_ID)
        if not job:
            return None
        nrt = getattr(job, "next_run_time", None)
        if not nrt:
            return None
        if getattr(nrt, "tzinfo", None) is None:
            nrt = nrt.replace(tzinfo=timezone.utc)
        return nrt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def schedule_enabled_state() -> Dict[str, Any]:
    """Whether the staging daily schedule is intended to run and why."""
    registered_env_ok = zoho_analytics_schedule_registration_allowed()
    kill = zoho_kill_switch_active()
    master = zoho_integration_enabled()
    analytics = zoho_analytics_sync_enabled()
    operationally_armed = registered_env_ok and master and analytics and not kill
    reason = "armed"
    if not registered_env_ok:
        reason = "environment_not_staging"
    elif kill:
        reason = "kill_switch_active"
    elif not master:
        reason = "zoho_integration_disabled"
    elif not analytics:
        reason = "analytics_sync_disabled"
    return {
        "schedule_registration_allowed": registered_env_ok,
        "schedule_armed": operationally_armed,
        "cadence": ANALYTICS_EXPORT_SCHEDULE_CADENCE if registered_env_ok else None,
        "reason": reason,
        "job_id": ANALYTICS_EXPORT_JOB_ID,
    }
