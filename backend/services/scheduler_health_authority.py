"""
Single authority for scheduler heartbeat freshness.

Used by /api/health, observability health-summary, and Control Centre so statuses agree.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Align with job_schedule_registry.HEARTBEAT_STALE_SECONDS (2-minute cadence → 5 min stale)
DEFAULT_STALE_SECONDS = 300

SCHEDULER_HEALTH_HEALTHY = "healthy"
SCHEDULER_HEALTH_DEGRADED = "degraded"
SCHEDULER_HEALTH_UNHEALTHY = "unhealthy"
SCHEDULER_HEALTH_UNKNOWN = "unknown"
SCHEDULER_HEALTH_DISABLED = "disabled_by_design"


@dataclass
class SchedulerHealthSnapshot:
    status: str
    stale: bool
    last_heartbeat_at: Optional[str]
    age_seconds: Optional[float]
    stale_after_seconds: int
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "stale": self.stale,
            "last_heartbeat_at": self.last_heartbeat_at,
            "age_seconds": self.age_seconds,
            "stale_after_seconds": self.stale_after_seconds,
            "reason": self.reason,
        }


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def evaluate_scheduler_heartbeat(
    *,
    last_heartbeat_at: Optional[str],
    now: Optional[datetime] = None,
    stale_after_seconds: int = DEFAULT_STALE_SECONDS,
    scheduler_disabled: bool = False,
) -> SchedulerHealthSnapshot:
    if scheduler_disabled:
        return SchedulerHealthSnapshot(
            status=SCHEDULER_HEALTH_DISABLED,
            stale=False,
            last_heartbeat_at=last_heartbeat_at,
            age_seconds=None,
            stale_after_seconds=stale_after_seconds,
            reason="scheduler_disabled_by_design",
        )
    if not last_heartbeat_at:
        return SchedulerHealthSnapshot(
            status=SCHEDULER_HEALTH_UNKNOWN,
            stale=True,
            last_heartbeat_at=None,
            age_seconds=None,
            stale_after_seconds=stale_after_seconds,
            reason="heartbeat_missing",
        )
    now = now or datetime.now(timezone.utc)
    parsed = _parse_iso(last_heartbeat_at)
    if not parsed:
        return SchedulerHealthSnapshot(
            status=SCHEDULER_HEALTH_UNKNOWN,
            stale=True,
            last_heartbeat_at=last_heartbeat_at,
            age_seconds=None,
            stale_after_seconds=stale_after_seconds,
            reason="heartbeat_unparseable",
        )
    age = (now - parsed).total_seconds()
    if age > stale_after_seconds:
        return SchedulerHealthSnapshot(
            status=SCHEDULER_HEALTH_UNHEALTHY,
            stale=True,
            last_heartbeat_at=last_heartbeat_at,
            age_seconds=age,
            stale_after_seconds=stale_after_seconds,
            reason="heartbeat_stale",
        )
    return SchedulerHealthSnapshot(
        status=SCHEDULER_HEALTH_HEALTHY,
        stale=False,
        last_heartbeat_at=last_heartbeat_at,
        age_seconds=age,
        stale_after_seconds=stale_after_seconds,
        reason="heartbeat_fresh",
    )


async def load_scheduler_health_snapshot() -> SchedulerHealthSnapshot:
    """Read scheduler_heartbeat from the active DB and evaluate freshness."""
    try:
        from database import database
        from services.job_schedule_registry import HEARTBEAT_STALE_SECONDS

        db = database.get_db()
        if db is None:
            return evaluate_scheduler_heartbeat(
                last_heartbeat_at=None,
                stale_after_seconds=HEARTBEAT_STALE_SECONDS,
            )
        doc = await db.scheduler_heartbeat.find_one(
            {"_id": "default"},
            {"_id": 0, "last_heartbeat_at": 1},
        )
        return evaluate_scheduler_heartbeat(
            last_heartbeat_at=(doc or {}).get("last_heartbeat_at"),
            stale_after_seconds=HEARTBEAT_STALE_SECONDS,
        )
    except Exception as exc:
        logger.warning("scheduler health load failed: %s", exc)
        return evaluate_scheduler_heartbeat(last_heartbeat_at=None)


def map_platform_status(scheduler: SchedulerHealthSnapshot, *, startup_degraded: bool = False) -> str:
    """
    Map scheduler + startup into platform status values for /api/health.
    Process may still be up (HTTP 200) while status is unhealthy/degraded.
    """
    if startup_degraded and scheduler.status == SCHEDULER_HEALTH_HEALTHY:
        return "degraded"
    if scheduler.status in (SCHEDULER_HEALTH_UNHEALTHY, SCHEDULER_HEALTH_UNKNOWN):
        return "unhealthy"
    if scheduler.status == SCHEDULER_HEALTH_DEGRADED:
        return "degraded"
    if scheduler.status == SCHEDULER_HEALTH_DISABLED:
        return "degraded"
    return "healthy"
