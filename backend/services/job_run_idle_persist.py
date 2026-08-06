"""
High-frequency schedule jobs: skip full job_runs + OEP on idle success ticks.

Root cause of ~1.9M staging job_runs: compliance_recalc_worker (15s),
risk_signal_regen_worker (30s), notification_retry_worker (1m), etc.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

COLLECTION_POLL_HEARTBEATS = "job_poll_heartbeats"

# Always skip job_runs for heartbeat — scheduler_heartbeat collection is authoritative for liveness.
ALWAYS_SKIP_JOB_RUN_PERSIST: Set[str] = {
    "scheduler_heartbeat",
}

# Skip persist when schedule run is idle success (no work performed).
IDLE_SKIP_JOB_RUN_PERSIST: Set[str] = {
    "compliance_recalc_worker",
    "risk_signal_regen_worker",
    "notification_retry_worker",
    "scheduled_admin_communications",
}


def idle_skip_enabled() -> bool:
    raw = (os.getenv("JOB_RUN_SKIP_IDLE_HIGH_FREQUENCY") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def is_idle_success_result(result: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("outcome_status") in ("failed", "degraded"):
        return False
    if result.get("error_code") or result.get("error_message"):
        # allow heartbeat-style messages without treating as failure
        if result.get("outcome_status") == "failed":
            return False
    om = result.get("outcome_metrics") or {}
    if om.get("outcome_kind") in ("WORK_PERFORMED",) and int(result.get("count") or 0) > 0:
        # heartbeat returns WORK_PERFORMED with count=1 — handled by ALWAYS_SKIP
        if int(om.get("attempted_count") or 0) > 0 and int(result.get("count") or 0) > 0:
            # risk/regen empty queue sets attempted_count 0
            pass
    count = result.get("count")
    if count is None:
        count = om.get("attempted_count")
    try:
        n = int(count if count is not None else 0)
    except (TypeError, ValueError):
        n = 0
    attempted = int(om.get("attempted_count") or 0)
    regenerated = int(om.get("regenerated_count") or 0)
    processed = int(om.get("processed") or om.get("processed_count") or 0)
    batch_size = int(om.get("batch_size") or 0)
    if result.get("idle") is True:
        return True
    if n == 0 and attempted == 0 and regenerated == 0 and processed == 0:
        return True
    if batch_size == 0 and n == 0 and attempted == 0:
        return True
    return False


def should_skip_full_persist(job_id: str, run_type: str, result: Dict[str, Any]) -> bool:
    if not idle_skip_enabled():
        return False
    if run_type != "schedule":
        return False
    if job_id in ALWAYS_SKIP_JOB_RUN_PERSIST:
        return True
    if job_id in IDLE_SKIP_JOB_RUN_PERSIST and is_idle_success_result(result):
        return True
    return False


async def touch_job_poll_heartbeat(
    job_id: str,
    *,
    result: Optional[Dict[str, Any]] = None,
    skipped_persist: bool = True,
) -> None:
    """Tiny upsert so System Health still sees recent ticks without job_runs growth."""
    try:
        from database import database

        db = database.get_db()
        if db is None:
            return
        now = datetime.now(timezone.utc).isoformat()
        payload: Dict[str, Any] = {
            "job_name": job_id,
            "last_tick_at": now,
            "updated_at": now,
            "skipped_persist": skipped_persist,
            "idle": True if result is None else is_idle_success_result(result),
        }
        if isinstance(result, dict):
            payload["last_message"] = (result.get("message") or "")[:240]
            payload["last_count"] = result.get("count")
        await db[COLLECTION_POLL_HEARTBEATS].update_one(
            {"_id": job_id},
            {"$set": payload, "$inc": {"tick_count": 1}},
            upsert=True,
        )
    except Exception as exc:
        logger.debug("job_poll_heartbeat touch skipped: %s", exc)
