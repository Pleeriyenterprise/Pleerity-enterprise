"""Zoho integration operational health — feeds System Health and Control Centre."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.integrations.zoho.circuit_breaker import zoho_circuit_breaker
from services.integrations.zoho.config import (
    INTEGRATION_FLAG_CHECKERS,
    analytics_target_config_snapshot,
    crm_target_config_snapshot,
    zoho_credentials_configured,
    zoho_integration_enabled,
    zoho_kill_switch_active,
    zoho_refresh_token,
    zoho_shared_oauth_client_configured,
)
from services.integrations.zoho.metrics.analytics_export import (
    TIMESTAMP_STORAGE_NOTE,
    resolve_daily_reporting_period,
)
from services.integrations.zoho.analytics_schedule import (
    analytics_export_run_lock_status,
    next_daily_run_utc,
    schedule_enabled_state,
    scheduler_job_next_run_iso,
)
from services.integrations.zoho.credential_resolver import resolve_oauth_credentials
from services.integrations.zoho.oauth import zoho_oauth_manager
from services.integrations.zoho.oauth_credential_registry import (
    NON_OAUTH_INTEGRATIONS,
    OAUTH_INTEGRATION_REGISTRY,
    registry_snapshot,
)
from services.integrations.zoho.types import (
    ANALYTICS_EXPORT_JOB_ID,
    ANALYTICS_EXPORT_SCHEDULE_CADENCE,
    ZOHO_SYNC_DEAD_LETTER_COLLECTION,
    ZOHO_SYNC_QUEUE_COLLECTION,
    ZOHO_SYNC_RUNS_COLLECTION,
    SyncSkipReason,
    SyncStatus,
)
from services.integrations.zoho.version import version_metadata_snapshot

ACCESS_TOKEN_BUFFER_SECONDS = 300
DEAD_LETTER_DEGRADED_THRESHOLD = 50
QUEUE_LAG_DEGRADED_THRESHOLD = 100
QUEUE_LAG_HOURS = 1
ANALYTICS_NO_SUCCESS_INCIDENT_HOURS = 48
ANALYTICS_CONSECUTIVE_WARNING = 1
ANALYTICS_CONSECUTIVE_DEGRADED = 2
ANALYTICS_CONSECUTIVE_INCIDENT = 3


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _oauth_status_label(
    *,
    credentials_configured: bool,
    token_cached: bool,
    token_valid: bool,
    auth_failure_count: int,
) -> str:
    if not credentials_configured:
        return "not_configured"
    if auth_failure_count > 0 and not token_valid:
        return "authentication_failed"
    if token_cached and token_valid:
        return "healthy"
    if token_cached:
        return "cached_expired"
    return "awaiting_refresh"


async def _oauth_health_for_integration(integration: str) -> Dict[str, Any]:
    if integration in NON_OAUTH_INTEGRATIONS:
        return {
            "integration": integration,
            "credentials_configured": False,
            "refresh_token_configured": False,
            "refresh_token_source": "not_applicable",
            "access_token_cached": False,
            "last_successful_refresh": None,
            "token_expiry": None,
            "expires_in_seconds": None,
            "expected_scope": None,
            "oauth_status": "not_applicable",
            "authentication_failures": 0,
            "last_validation_time": None,
            "using_legacy_fallback": False,
            "requires_oauth": False,
        }

    resolved = resolve_oauth_credentials(integration)
    if not resolved:
        return {
            "integration": integration,
            "credentials_configured": False,
            "refresh_token_configured": False,
            "refresh_token_source": "none",
            "access_token_cached": False,
            "last_successful_refresh": None,
            "token_expiry": None,
            "expires_in_seconds": None,
            "expected_scope": None,
            "oauth_status": "unknown_integration",
            "authentication_failures": 0,
            "last_validation_time": None,
            "using_legacy_fallback": False,
            "requires_oauth": True,
        }

    metadata = await zoho_oauth_manager.get_token_metadata(integration)
    expires_at = float(metadata.get("expires_at") or 0)
    now = time.time()
    expires_in = max(0, int(expires_at - now)) if expires_at else None
    token_cached = bool(metadata.get("expires_at"))
    token_valid = expires_at > (now + ACCESS_TOKEN_BUFFER_SECONDS) if expires_at else False
    auth_failures = int(metadata.get("auth_failure_count") or 0)
    token_expiry_iso = (
        datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat() if expires_at else None
    )

    return {
        "integration": integration,
        "credentials_configured": resolved.credentials_configured,
        "refresh_token_configured": resolved.refresh_token_configured,
        "refresh_token_source": resolved.refresh_token_source.value,
        "access_token_cached": token_cached,
        "last_successful_refresh": metadata.get("last_successful_refresh_at"),
        "token_expiry": token_expiry_iso,
        "expires_in_seconds": expires_in,
        "expected_scope": resolved.expected_scope,
        "oauth_status": _oauth_status_label(
            credentials_configured=resolved.credentials_configured,
            token_cached=token_cached,
            token_valid=token_valid,
            auth_failure_count=auth_failures,
        ),
        "authentication_failures": auth_failures,
        "last_validation_time": metadata.get("last_validation_at"),
        "using_legacy_fallback": resolved.using_legacy_fallback,
        "requires_oauth": True,
    }


async def _oauth_health() -> Dict[str, Any]:
    by_integration = {
        name: await _oauth_health_for_integration(name)
        for name in list(OAUTH_INTEGRATION_REGISTRY.keys()) + list(NON_OAUTH_INTEGRATIONS)
    }

    any_valid = any(
        row.get("oauth_status") == "healthy" for row in by_integration.values()
    )
    any_cached = any(row.get("access_token_cached") for row in by_integration.values())

    # Aggregate fields preserved for existing observability consumers.
    return {
        "configured": zoho_credentials_configured(),
        "shared_client_configured": zoho_shared_oauth_client_configured(),
        "legacy_refresh_token_configured": bool(zoho_refresh_token()),
        "token_cached": any_cached,
        "token_valid": any_valid,
        "expires_in_seconds": _min_expires_in(by_integration),
        "by_integration": by_integration,
        "credential_registry": registry_snapshot(),
    }


def _min_expires_in(by_integration: Dict[str, Dict[str, Any]]) -> Optional[int]:
    values = [
        int(row["expires_in_seconds"])
        for row in by_integration.values()
        if row.get("expires_in_seconds") is not None
    ]
    return min(values) if values else None


async def _integration_sync_summary(integration: str, since_iso: str) -> Dict[str, Any]:
    db = database.get_db()
    filt = {"integration": integration}
    last_success = await db[ZOHO_SYNC_RUNS_COLLECTION].find_one(
        {**filt, "status": SyncStatus.SUCCESS.value},
        {"_id": 0, "completed_at": 1, "sync_id": 1, "operation": 1, "result_summary": 1},
        sort=[("completed_at", -1)],
    )
    last_failure = await db[ZOHO_SYNC_RUNS_COLLECTION].find_one(
        {**filt, "status": {"$in": [SyncStatus.FAILED.value, SyncStatus.DEAD_LETTER.value]}},
        {"_id": 0, "completed_at": 1, "sync_id": 1, "operation": 1, "error": 1, "message": 1},
        sort=[("completed_at", -1)],
    )
    failure_count_24h = await db[ZOHO_SYNC_RUNS_COLLECTION].count_documents(
        {
            **filt,
            "status": {"$in": [SyncStatus.FAILED.value, SyncStatus.DEAD_LETTER.value]},
            "completed_at": {"$gte": since_iso},
        }
    )
    last_was_failure = bool(last_failure) and (
        not last_success
        or str(last_failure.get("completed_at") or "")
        >= str(last_success.get("completed_at") or "")
    )
    # Proxy streak: open failure window while last outcome is a failure.
    consecutive_failures = int(failure_count_24h) if last_was_failure else 0

    last_duration_seconds = None
    if last_success and last_success.get("sync_id"):
        full = await db[ZOHO_SYNC_RUNS_COLLECTION].find_one(
            {"sync_id": last_success["sync_id"]},
            {"_id": 0, "created_at": 1, "completed_at": 1},
        )
        if full and full.get("created_at") and full.get("completed_at"):
            try:
                start = datetime.fromisoformat(str(full["created_at"]))
                end = datetime.fromisoformat(str(full["completed_at"]))
                last_duration_seconds = max(0, int((end - start).total_seconds()))
            except ValueError:
                last_duration_seconds = None

    cb_open = zoho_circuit_breaker.is_open(integration)
    enabled = bool(INTEGRATION_FLAG_CHECKERS.get(integration) and INTEGRATION_FLAG_CHECKERS[integration]())
    return {
        "enabled": enabled,
        "last_success_at": (last_success or {}).get("completed_at"),
        "last_success_sync_id": (last_success or {}).get("sync_id"),
        "last_success_period_start": ((last_success or {}).get("result_summary") or {}).get(
            "period_start"
        ),
        "last_success_period_end": ((last_success or {}).get("result_summary") or {}).get(
            "period_end"
        ),
        "last_failure_at": (last_failure or {}).get("completed_at"),
        "last_failure_sync_id": (last_failure or {}).get("sync_id"),
        "last_failure_error": (last_failure or {}).get("error")
        or (last_failure or {}).get("message"),
        "failure_count_24h": failure_count_24h,
        "consecutive_failures": consecutive_failures,
        "last_success_duration_seconds": last_duration_seconds,
        "circuit_breaker": "open" if cb_open else "closed",
    }


async def _queue_stats(now: datetime) -> Dict[str, Any]:
    db = database.get_db()
    pending = await db[ZOHO_SYNC_QUEUE_COLLECTION].count_documents({"status": "pending"})
    processing = await db[ZOHO_SYNC_QUEUE_COLLECTION].count_documents({"status": "processing"})
    oldest = await db[ZOHO_SYNC_QUEUE_COLLECTION].find_one(
        {"status": "pending"},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", 1)],
    )
    oldest_at = (oldest or {}).get("created_at")
    oldest_age_seconds: Optional[int] = None
    if oldest_at:
        parsed = _parse_iso(oldest_at)
        if parsed:
            oldest_age_seconds = int((now - parsed.astimezone(timezone.utc)).total_seconds())
    return {
        "pending": pending,
        "processing": processing,
        "oldest_pending_at": oldest_at,
        "oldest_pending_age_seconds": oldest_age_seconds,
    }


async def _dead_letter_stats() -> Dict[str, Any]:
    db = database.get_db()
    unresolved = await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].count_documents({"resolved": False})
    oldest = await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].find_one(
        {"resolved": False},
        {"_id": 0, "created_at": 1, "dead_letter_id": 1},
        sort=[("created_at", 1)],
    )
    return {
        "unresolved": unresolved,
        "oldest_unresolved_at": (oldest or {}).get("created_at"),
        "oldest_unresolved_id": (oldest or {}).get("dead_letter_id"),
    }


async def _webhook_stats_24h(since_iso: str) -> Dict[str, Any]:
    db = database.get_db()
    accepted = 0
    rejected = 0
    auth_failed = 0
    try:
        cursor = db.audit_logs.find(
            {
                "metadata.action_type": "ZOHO_WEBHOOK",
                "created_at": {"$gte": since_iso},
            },
            {"_id": 0, "metadata": 1},
        ).limit(5000)
        async for row in cursor:
            status = str((row.get("metadata") or {}).get("status") or "").lower()
            if status in ("success", "accepted"):
                accepted += 1
            elif status == "rejected":
                rejected += 1
            elif status in ("auth_failed", "unauthorized"):
                auth_failed += 1
    except Exception:
        pass
    return {
        "accepted": accepted,
        "rejected": rejected,
        "auth_failed": auth_failed,
    }


async def _analytics_consecutive_failures() -> int:
    """Count trailing failed/dead_letter analytics export runs until a success/skip."""
    db = database.get_db()
    try:
        cursor = (
            db[ZOHO_SYNC_RUNS_COLLECTION]
            .find(
                {"integration": "analytics", "operation": "export_aggregates"},
                {"_id": 0, "status": 1},
            )
            .sort("completed_at", -1)
            .limit(20)
        )
        streak = 0
        async for row in cursor:
            status = str(row.get("status") or "")
            if status in (SyncStatus.FAILED.value, SyncStatus.DEAD_LETTER.value):
                streak += 1
                continue
            break
        return streak
    except Exception:
        return 0


async def _analytics_schedule_job_run_markers() -> Dict[str, Any]:
    """Last scheduled attempt / success / failure from job_runs."""
    db = database.get_db()
    out: Dict[str, Any] = {
        "last_scheduled_attempt_at": None,
        "last_scheduled_success_at": None,
        "last_scheduled_failure_at": None,
    }
    try:
        from services.job_run_service import (
            COLLECTION as JOB_RUNS_COLLECTION,
            STATUS_FAILED,
            STATUS_SUCCESS,
            STATUS_DEGRADED,
        )

        last_any = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": ANALYTICS_EXPORT_JOB_ID},
            {"_id": 0, "started_at": 1, "finished_at": 1, "status": 1},
            sort=[("started_at", -1)],
        )
        if last_any:
            out["last_scheduled_attempt_at"] = last_any.get("finished_at") or last_any.get(
                "started_at"
            )
        last_ok = await db[JOB_RUNS_COLLECTION].find_one(
            {
                "job_name": ANALYTICS_EXPORT_JOB_ID,
                "status": {"$in": [STATUS_SUCCESS, STATUS_DEGRADED]},
            },
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        if last_ok:
            out["last_scheduled_success_at"] = last_ok.get("finished_at")
        last_fail = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": ANALYTICS_EXPORT_JOB_ID, "status": STATUS_FAILED},
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        if last_fail:
            out["last_scheduled_failure_at"] = last_fail.get("finished_at")
    except Exception:
        pass
    return out


async def _analytics_duplicate_skip_count() -> int:
    db = database.get_db()
    try:
        return int(
            await db[ZOHO_SYNC_RUNS_COLLECTION].count_documents(
                {
                    "integration": "analytics",
                    "operation": "export_aggregates",
                    "status": SyncStatus.SKIPPED.value,
                    "message": {"$regex": SyncSkipReason.DUPLICATE_PERIOD.value},
                }
            )
        )
    except Exception:
        return 0


async def _analytics_dead_letter_count() -> int:
    db = database.get_db()
    try:
        return int(
            await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].count_documents(
                {"integration": "analytics", "resolved": False}
            )
        )
    except Exception:
        return 0


def _analytics_incident_policy(
    *,
    kill_switch: bool,
    schedule_state: Dict[str, Any],
    consecutive_failures: int,
    last_success_at: Optional[str],
    now: datetime,
) -> Dict[str, Any]:
    """
    Incident policy for scheduled Analytics operation:
    - kill switch / disabled flags: expected disabled (not an incident)
    - 1 consecutive failure: warning
    - 2 consecutive: degraded
    - 3 consecutive OR no success within 48h while schedule armed: actionable incident
    """
    if kill_switch or schedule_state.get("reason") in (
        "kill_switch_active",
        "zoho_integration_disabled",
        "analytics_sync_disabled",
        "environment_not_staging",
    ):
        if kill_switch or schedule_state.get("reason") == "kill_switch_active":
            return {
                "level": "disabled_expected",
                "reason": "kill_switch_active",
                "actionable_incident": False,
            }
        if not schedule_state.get("schedule_registration_allowed"):
            return {
                "level": "disabled_expected",
                "reason": "schedule_not_registered_non_staging",
                "actionable_incident": False,
            }
        return {
            "level": "disabled_expected",
            "reason": schedule_state.get("reason") or "disabled",
            "actionable_incident": False,
        }

    hours_since_success: Optional[float] = None
    if last_success_at:
        parsed = _parse_iso(last_success_at)
        if parsed:
            hours_since_success = (now - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0

    armed = bool(schedule_state.get("schedule_armed"))
    no_success_48h = (
        armed
        and (
            hours_since_success is None
            or hours_since_success >= ANALYTICS_NO_SUCCESS_INCIDENT_HOURS
        )
    )
    # Fresh schedule with no prior success yet: do not open 48h incident until armed long enough
    # and at least one attempt window has elapsed — operators still see consecutive-failure rules.
    if consecutive_failures >= ANALYTICS_CONSECUTIVE_INCIDENT or (
        no_success_48h and hours_since_success is not None
    ):
        return {
            "level": "incident",
            "reason": (
                "consecutive_failures_gte_3"
                if consecutive_failures >= ANALYTICS_CONSECUTIVE_INCIDENT
                else "no_successful_export_within_48h"
            ),
            "actionable_incident": True,
            "consecutive_failures": consecutive_failures,
            "hours_since_last_success": hours_since_success,
        }
    if consecutive_failures >= ANALYTICS_CONSECUTIVE_DEGRADED:
        return {
            "level": "degraded",
            "reason": "consecutive_failures_gte_2",
            "actionable_incident": False,
            "consecutive_failures": consecutive_failures,
            "hours_since_last_success": hours_since_success,
        }
    if consecutive_failures >= ANALYTICS_CONSECUTIVE_WARNING:
        return {
            "level": "warning",
            "reason": "consecutive_failures_gte_1",
            "actionable_incident": False,
            "consecutive_failures": consecutive_failures,
            "hours_since_last_success": hours_since_success,
        }
    return {
        "level": "ok",
        "reason": "healthy",
        "actionable_incident": False,
        "consecutive_failures": consecutive_failures,
        "hours_since_last_success": hours_since_success,
    }


async def _build_analytics_ops(
    *,
    snapshot: Dict[str, Any],
    analytics: Dict[str, Any],
    oauth_analytics: Dict[str, Any],
) -> Dict[str, Any]:
    period_start, period_end = resolve_daily_reporting_period()
    analytics_target = analytics_target_config_snapshot()
    schedule_state = schedule_enabled_state()
    now = datetime.now(timezone.utc)
    consecutive = await _analytics_consecutive_failures()
    analytics = {**analytics, "consecutive_failures": consecutive}
    job_markers = await _analytics_schedule_job_run_markers()
    lock_status = await analytics_export_run_lock_status()
    duplicate_skips = await _analytics_duplicate_skip_count()
    analytics_dl = await _analytics_dead_letter_count()
    next_from_scheduler = scheduler_job_next_run_iso()
    next_run = next_from_scheduler
    if schedule_state.get("schedule_registration_allowed") and not next_run:
        next_run = next_daily_run_utc().isoformat()
    kill = bool(snapshot.get("kill_switch_active"))
    policy = _analytics_incident_policy(
        kill_switch=kill,
        schedule_state=schedule_state,
        consecutive_failures=int(analytics.get("consecutive_failures") or 0),
        last_success_at=analytics.get("last_success_at"),
        now=now,
    )
    schedule_registered = bool(schedule_state.get("schedule_registration_allowed"))
    return {
        "enabled": bool(analytics.get("enabled")),
        "healthy": (
            bool(analytics.get("enabled"))
            and oauth_analytics.get("oauth_status") == "healthy"
            and analytics_target.get("target_complete")
            and int(analytics.get("consecutive_failures") or 0) == 0
            and policy.get("level") in ("ok", "disabled_expected", "warning")
        )
        or (
            not bool(analytics.get("enabled"))
            and analytics_target.get("target_complete") is not None
        ),
        "configuration_complete": bool(analytics_target.get("target_complete")),
        "configuration_missing": list(analytics_target.get("missing") or []),
        "oauth_status": oauth_analytics.get("oauth_status"),
        "last_success_at": analytics.get("last_success_at"),
        "last_success_sync_id": analytics.get("last_success_sync_id"),
        "last_failure_at": analytics.get("last_failure_at"),
        "last_failure_sync_id": analytics.get("last_failure_sync_id"),
        "last_failure_error": analytics.get("last_failure_error"),
        "consecutive_failures": int(analytics.get("consecutive_failures") or 0),
        "failure_count_24h": int(analytics.get("failure_count_24h") or 0),
        "last_success_duration_seconds": analytics.get("last_success_duration_seconds"),
        "current_reporting_period_start": period_start.isoformat(),
        "current_reporting_period_end": period_end.isoformat(),
        "last_exported_period_start": analytics.get("last_success_period_start"),
        "last_exported_period_end": analytics.get("last_success_period_end"),
        "last_exported_period": analytics.get("last_success_period_start"),
        "schedule_enabled": bool(schedule_state.get("schedule_armed")),
        "schedule_registration_allowed": schedule_registered,
        "configured_cadence": ANALYTICS_EXPORT_SCHEDULE_CADENCE if schedule_registered else None,
        "next_scheduled_run": next_run if schedule_registered else None,
        "next_expected_export": next_run if schedule_registered else "manual_only_no_cron",
        "last_scheduled_attempt": job_markers.get("last_scheduled_attempt_at"),
        "last_scheduled_success": job_markers.get("last_scheduled_success_at"),
        "last_scheduled_failure": job_markers.get("last_scheduled_failure_at"),
        "duplicate_skips": duplicate_skips,
        "dead_letter_count": analytics_dl,
        "run_lock_status": lock_status,
        "incident_policy": policy,
        "timestamp_storage": TIMESTAMP_STORAGE_NOTE,
        "api_base": analytics_target.get("api_base"),
        "table_name": analytics_target.get("table_name"),
        "job_id": ANALYTICS_EXPORT_JOB_ID,
    }


async def _crm_consecutive_failures() -> int:
    db = database.get_db()
    try:
        cursor = (
            db[ZOHO_SYNC_RUNS_COLLECTION]
            .find(
                {"integration": "crm"},
                {"_id": 0, "status": 1},
            )
            .sort("completed_at", -1)
            .limit(20)
        )
        streak = 0
        async for row in cursor:
            status = str(row.get("status") or "")
            if status in (SyncStatus.FAILED.value, SyncStatus.DEAD_LETTER.value):
                streak += 1
                continue
            break
        return streak
    except Exception:
        return 0


async def _crm_queue_depth() -> Dict[str, int]:
    db = database.get_db()
    try:
        pending = await db[ZOHO_SYNC_QUEUE_COLLECTION].count_documents(
            {"integration": "crm", "status": "pending"}
        )
        failed = await db[ZOHO_SYNC_QUEUE_COLLECTION].count_documents(
            {"integration": "crm", "status": "failed"}
        )
        return {"pending": int(pending), "failed": int(failed)}
    except Exception:
        return {"pending": 0, "failed": 0}


async def _crm_duplicate_skip_count() -> int:
    """Identity lookups / duplicate recoveries that prevented a net-new CRM create."""
    db = database.get_db()
    try:
        return int(
            await db[ZOHO_SYNC_RUNS_COLLECTION].count_documents(
                {
                    "integration": "crm",
                    "status": SyncStatus.SUCCESS.value,
                    "$or": [
                        {"result_summary.duplicate_create_prevented": True},
                        {
                            "result_summary.identity_source": {
                                "$in": [
                                    "pleerity_lead_id_lookup",
                                    "duplicate_conflict_lookup",
                                ]
                            }
                        },
                    ],
                }
            )
        )
    except Exception:
        return 0


async def _crm_dead_letter_stats() -> Dict[str, int]:
    db = database.get_db()
    try:
        unresolved = int(
            await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].count_documents(
                {"integration": "crm", "resolved": False}
            )
        )
        # Aggregate replay attempts on CRM dead letters (resolved + open).
        pipeline = [
            {"$match": {"integration": "crm"}},
            {"$group": {"_id": None, "replays": {"$sum": {"$ifNull": ["$replay_count", 0]}}}},
        ]
        rows = await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].aggregate(pipeline).to_list(1)
        replay_count = int((rows[0] or {}).get("replays") or 0) if rows else 0
        return {"unresolved": unresolved, "replay_count": replay_count}
    except Exception:
        return {"unresolved": 0, "replay_count": 0}


def _crm_incident_policy(
    *,
    kill_switch: bool,
    enabled: bool,
    consecutive_failures: int,
) -> Dict[str, Any]:
    if kill_switch or not enabled:
        return {
            "level": "disabled_expected",
            "reason": "kill_switch_active" if kill_switch else "crm_sync_disabled",
            "actionable_incident": False,
        }
    if consecutive_failures >= ANALYTICS_CONSECUTIVE_INCIDENT:
        return {
            "level": "incident",
            "reason": "consecutive_failures_gte_3",
            "actionable_incident": True,
            "consecutive_failures": consecutive_failures,
        }
    if consecutive_failures >= ANALYTICS_CONSECUTIVE_DEGRADED:
        return {
            "level": "degraded",
            "reason": "consecutive_failures_gte_2",
            "actionable_incident": False,
            "consecutive_failures": consecutive_failures,
        }
    if consecutive_failures >= ANALYTICS_CONSECUTIVE_WARNING:
        return {
            "level": "warning",
            "reason": "consecutive_failures_gte_1",
            "actionable_incident": False,
            "consecutive_failures": consecutive_failures,
        }
    return {
        "level": "ok",
        "reason": "healthy",
        "actionable_incident": False,
        "consecutive_failures": consecutive_failures,
    }


async def _build_crm_ops(
    *,
    snapshot: Dict[str, Any],
    crm: Dict[str, Any],
    oauth_crm: Dict[str, Any],
) -> Dict[str, Any]:
    target = crm_target_config_snapshot()
    consecutive = await _crm_consecutive_failures()
    crm = {**crm, "consecutive_failures": consecutive}
    queue = await _crm_queue_depth()
    dl = await _crm_dead_letter_stats()
    duplicates = await _crm_duplicate_skip_count()
    kill = bool(snapshot.get("kill_switch_active"))
    enabled = bool(crm.get("enabled"))
    policy = _crm_incident_policy(
        kill_switch=kill,
        enabled=enabled,
        consecutive_failures=consecutive,
    )
    return {
        "enabled": enabled,
        "manual_only": True,
        "healthy": (
            enabled
            and oauth_crm.get("oauth_status") == "healthy"
            and target.get("target_complete")
            and consecutive == 0
        )
        or (not enabled and target.get("target_complete") is not None),
        "configuration_complete": bool(target.get("target_complete")),
        "configuration_missing": list(target.get("missing") or []),
        "crm_target": target,
        "oauth_status": oauth_crm.get("oauth_status"),
        "last_success_at": crm.get("last_success_at"),
        "last_success_sync_id": crm.get("last_success_sync_id"),
        "last_failure_at": crm.get("last_failure_at"),
        "last_failure_sync_id": crm.get("last_failure_sync_id"),
        "last_failure_error": crm.get("last_failure_error"),
        "consecutive_failures": consecutive,
        "failure_count_24h": int(crm.get("failure_count_24h") or 0),
        "queue_depth_pending": queue.get("pending", 0),
        "queue_depth_failed": queue.get("failed", 0),
        "duplicate_skips": duplicates,
        "dead_letter_count": dl.get("unresolved", 0),
        "replay_count": dl.get("replay_count", 0),
        "next_expected_sync": "manual_only_no_cron",
        "incident_policy": policy,
        "identity_resolution_order": target.get("identity_resolution_order"),
    }


def _derive_overall_status(
    *,
    master_enabled: bool,
    kill_switch: bool,
    oauth: Dict[str, Any],
    integrations: Dict[str, Any],
    queue: Dict[str, Any],
    dead_letter: Dict[str, Any],
    circuit_breakers_open: List[str],
) -> str:
    if not master_enabled:
        return "dormant"
    if kill_switch:
        return "disabled"
    degraded = False
    oauth_by_integration = oauth.get("by_integration") or {}
    for name, row in integrations.items():
        if not row.get("enabled"):
            continue
        oauth_row = oauth_by_integration.get(name) or {}
        if oauth_row.get("requires_oauth") and oauth_row.get("credentials_configured"):
            if oauth_row.get("oauth_status") in ("authentication_failed", "cached_expired"):
                degraded = True
            if oauth_row.get("oauth_status") == "not_configured":
                degraded = True
    if master_enabled and oauth.get("configured") and not oauth.get("token_valid") and oauth.get("token_cached") is False:
        pass
    if dead_letter.get("unresolved", 0) > DEAD_LETTER_DEGRADED_THRESHOLD:
        degraded = True
    if queue.get("pending", 0) > QUEUE_LAG_DEGRADED_THRESHOLD:
        oldest_age = queue.get("oldest_pending_age_seconds")
        if oldest_age is not None and oldest_age > QUEUE_LAG_HOURS * 3600:
            degraded = True
    if circuit_breakers_open:
        degraded = True
    for row in integrations.values():
        if row.get("enabled") and row.get("circuit_breaker") == "open":
            degraded = True
        if row.get("enabled") and row.get("failure_count_24h", 0) > 10:
            degraded = True
    if degraded:
        return "degraded"
    return "healthy"


async def build_zoho_operational_snapshot() -> Dict[str, Any]:
    """Full operational snapshot for admin and platform observability."""
    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(hours=24)).isoformat()
    master_enabled = zoho_integration_enabled()
    kill_switch = zoho_kill_switch_active()
    oauth = await _oauth_health()
    integrations = {
        name: await _integration_sync_summary(name, since_24h)
        for name in INTEGRATION_FLAG_CHECKERS.keys()
    }
    queue = await _queue_stats(now)
    dead_letter = await _dead_letter_stats()
    webhooks_24h = await _webhook_stats_24h(since_24h)
    circuit_breakers = zoho_circuit_breaker.snapshot()
    circuit_open = [k for k, v in circuit_breakers.items() if v.get("open")]

    overall_status = _derive_overall_status(
        master_enabled=master_enabled,
        kill_switch=kill_switch,
        oauth=oauth,
        integrations=integrations,
        queue=queue,
        dead_letter=dead_letter,
        circuit_breakers_open=circuit_open,
    )

    schedule_state = schedule_enabled_state()
    oauth_by_integration = oauth.get("by_integration") or {}
    analytics_ops = await _build_analytics_ops(
        snapshot={
            "kill_switch_active": kill_switch,
            "zoho_integration_enabled": master_enabled,
        },
        analytics=integrations.get("analytics") or {},
        oauth_analytics=oauth_by_integration.get("analytics") or {},
    )
    crm_ops = await _build_crm_ops(
        snapshot={
            "kill_switch_active": kill_switch,
            "zoho_integration_enabled": master_enabled,
        },
        crm=integrations.get("crm") or {},
        oauth_crm=oauth_by_integration.get("crm") or {},
    )

    # Degrade overall when Analytics/CRM policy reports degraded/incident.
    if master_enabled and not kill_switch:
        for ops in (analytics_ops, crm_ops):
            level = (ops.get("incident_policy") or {}).get("level")
            if level in ("degraded", "incident") and overall_status == "healthy":
                overall_status = "degraded"

    return {
        "generated_at": now.isoformat(),
        "overall_status": overall_status,
        "zoho_integration_enabled": master_enabled,
        "kill_switch_active": kill_switch,
        "oauth": oauth,
        "integrations": integrations,
        "queue": queue,
        "dead_letter": dead_letter,
        "webhooks_24h": webhooks_24h,
        "circuit_breakers": circuit_breakers,
        "versions": version_metadata_snapshot(),
        "manual_jobs_only": not bool(schedule_state.get("schedule_registration_allowed")),
        "analytics_ops": analytics_ops,
        "crm_ops": crm_ops,
        "admin_path": "/api/admin/integrations/zoho/status",
    }


def build_zoho_operational_health_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure summary over ``build_zoho_operational_snapshot`` — same pattern as recalc queue health.
    """
    queue = snapshot.get("queue") or {}
    dead_letter = snapshot.get("dead_letter") or {}
    oauth = snapshot.get("oauth") or {}
    oauth_by_integration = oauth.get("by_integration") or {}
    circuit_breakers = snapshot.get("circuit_breakers") or {}
    open_breakers = [k for k, v in circuit_breakers.items() if v.get("open")]
    oauth_integrations_healthy = [
        name
        for name, row in oauth_by_integration.items()
        if row.get("requires_oauth") and row.get("oauth_status") == "healthy"
    ]
    oauth_integrations_configured = [
        name
        for name, row in oauth_by_integration.items()
        if row.get("requires_oauth") and row.get("credentials_configured")
    ]
    analytics = (snapshot.get("integrations") or {}).get("analytics") or {}
    period_start, period_end = resolve_daily_reporting_period()
    analytics_target = analytics_target_config_snapshot()
    oauth_analytics = oauth_by_integration.get("analytics") or {}
    schedule_registered = bool(schedule_enabled_state().get("schedule_registration_allowed"))
    analytics_ops = snapshot.get("analytics_ops")
    if not isinstance(analytics_ops, dict):
        # Lightweight sync fallback for unit tests that build a partial snapshot.
        analytics_ops = {
            "enabled": bool(analytics.get("enabled")),
            "healthy": (
                bool(analytics.get("enabled"))
                and oauth_analytics.get("oauth_status") == "healthy"
                and analytics_target.get("target_complete")
                and int(analytics.get("consecutive_failures") or 0) == 0
            )
            or (
                not bool(analytics.get("enabled"))
                and analytics_target.get("target_complete") is not None
            ),
            "configuration_complete": bool(analytics_target.get("target_complete")),
            "configuration_missing": list(analytics_target.get("missing") or []),
            "oauth_status": oauth_analytics.get("oauth_status"),
            "last_success_at": analytics.get("last_success_at"),
            "last_success_sync_id": analytics.get("last_success_sync_id"),
            "last_failure_at": analytics.get("last_failure_at"),
            "last_failure_sync_id": analytics.get("last_failure_sync_id"),
            "last_failure_error": analytics.get("last_failure_error"),
            "consecutive_failures": int(analytics.get("consecutive_failures") or 0),
            "failure_count_24h": int(analytics.get("failure_count_24h") or 0),
            "last_success_duration_seconds": analytics.get("last_success_duration_seconds"),
            "current_reporting_period_start": period_start.isoformat(),
            "current_reporting_period_end": period_end.isoformat(),
            "last_exported_period_start": analytics.get("last_success_period_start"),
            "last_exported_period_end": analytics.get("last_success_period_end"),
            "last_exported_period": analytics.get("last_success_period_start"),
            "schedule_enabled": False,
            "schedule_registration_allowed": schedule_registered,
            "configured_cadence": ANALYTICS_EXPORT_SCHEDULE_CADENCE if schedule_registered else None,
            "next_scheduled_run": None,
            "next_expected_export": (
                next_daily_run_utc().isoformat() if schedule_registered else "manual_only_no_cron"
            ),
            "last_scheduled_attempt": None,
            "last_scheduled_success": None,
            "last_scheduled_failure": None,
            "duplicate_skips": 0,
            "dead_letter_count": 0,
            "run_lock_status": {"held": False, "status": "unknown"},
            "incident_policy": {"level": "ok", "reason": "snapshot_partial"},
            "timestamp_storage": TIMESTAMP_STORAGE_NOTE,
            "api_base": analytics_target.get("api_base"),
            "table_name": analytics_target.get("table_name"),
            "job_id": ANALYTICS_EXPORT_JOB_ID,
        }
    return {
        "overall_status": snapshot.get("overall_status") or "dormant",
        "zoho_integration_enabled": bool(snapshot.get("zoho_integration_enabled")),
        "kill_switch_active": bool(snapshot.get("kill_switch_active")),
        "oauth_configured": bool(oauth.get("configured")),
        "oauth_shared_client_configured": bool(oauth.get("shared_client_configured")),
        "oauth_token_valid": bool(oauth.get("token_valid")),
        "oauth_integrations_configured": oauth_integrations_configured,
        "oauth_integrations_healthy": oauth_integrations_healthy,
        "queue_depth_pending": int(queue.get("pending") or 0),
        "queue_depth_processing": int(queue.get("processing") or 0),
        "dead_letter_unresolved": int(dead_letter.get("unresolved") or 0),
        "circuit_breakers_open": open_breakers,
        "circuit_breaker_open_count": len(open_breakers),
        "webhooks_accepted_24h": int((snapshot.get("webhooks_24h") or {}).get("accepted") or 0),
        "webhooks_rejected_24h": int((snapshot.get("webhooks_24h") or {}).get("rejected") or 0),
        "integration_layer_version": (snapshot.get("versions") or {}).get("integration_layer_version"),
        "manual_jobs_only": bool(
            snapshot.get("manual_jobs_only", not schedule_registered)
        ),
        "health_posture": "INTEGRATED_WITH_PLATFORM_OBSERVABILITY",
        "admin_path": snapshot.get("admin_path"),
        "analytics_ops": analytics_ops,
        "crm_ops": snapshot.get("crm_ops")
        if isinstance(snapshot.get("crm_ops"), dict)
        else {
            "enabled": bool(((snapshot.get("integrations") or {}).get("crm") or {}).get("enabled")),
            "manual_only": True,
            "next_expected_sync": "manual_only_no_cron",
            "configuration_complete": bool(crm_target_config_snapshot().get("target_complete")),
            "configuration_missing": list(crm_target_config_snapshot().get("missing") or []),
            "incident_policy": {"level": "ok", "reason": "snapshot_partial"},
        },
    }
