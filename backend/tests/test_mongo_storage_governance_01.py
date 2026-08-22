"""Unit tests for Mongo storage governance helpers."""
from datetime import datetime, timedelta, timezone

from services.job_run_idle_persist import is_idle_success_result, should_skip_full_persist
from services.mongo_storage_monitor import classify_usage_pct
from services.scheduler_health_authority import (
    SCHEDULER_HEALTH_HEALTHY,
    SCHEDULER_HEALTH_UNHEALTHY,
    SCHEDULER_HEALTH_UNKNOWN,
    evaluate_scheduler_heartbeat,
    map_platform_status,
)
from utils.mongo_capacity_errors import capacity_unavailable_payload, is_mongo_capacity_error


def test_classify_usage_thresholds():
    assert classify_usage_pct(10) == "ok"
    assert classify_usage_pct(60) == "warning"
    assert classify_usage_pct(75) == "attention"
    assert classify_usage_pct(85) == "critical"
    assert classify_usage_pct(90) == "platform_alert"
    assert classify_usage_pct(95) == "emergency"


def test_idle_success_detection():
    assert is_idle_success_result({"count": 0, "outcome_metrics": {"attempted_count": 0}})
    assert not is_idle_success_result({"count": 3, "outcome_metrics": {"attempted_count": 3}})
    assert not is_idle_success_result({"count": 0, "outcome_status": "failed"})
    assert is_idle_success_result(
        {
            "count": 0,
            "outcome_status": "success",
            "outcome_metrics": {
                "outcome_kind": "CONTENTION_ONLY",
                "attempted_count": 10,
                "queue_items_seen_batch": 10,
                "queue_items_claim_skipped": 10,
                "success_count": 0,
            },
        }
    )
    assert is_idle_success_result(
        {
            "count": 0,
            "outcome_status": "success",
            "outcome_metrics": {
                "outcome_kind": "LIFECYCLE_SUPPRESSED",
                "attempted_count": 10,
                "queue_items_seen_batch": 10,
                "queue_items_lifecycle_skipped": 7,
                "queue_items_lifecycle_paused": 3,
                "success_count": 0,
            },
        }
    )
    assert is_idle_success_result(
        {
            "count": 0,
            "outcome_status": "conditional_no_output",
            "outcome_metrics": {"outcome_kind": "NO_WORK_ELIGIBLE", "queue_empty": True, "attempted_count": 0},
        }
    )


def test_should_skip_heartbeat_schedule(monkeypatch):
    monkeypatch.setenv("JOB_RUN_SKIP_IDLE_HIGH_FREQUENCY", "1")
    assert should_skip_full_persist(
        "scheduler_heartbeat", "schedule", {"count": 1, "outcome_metrics": {"outcome_kind": "WORK_PERFORMED"}}
    )
    assert not should_skip_full_persist(
        "scheduler_heartbeat", "manual", {"count": 1, "outcome_metrics": {"outcome_kind": "WORK_PERFORMED"}}
    )


def test_capacity_error_detection():
    assert is_mongo_capacity_error("You exceeded the size limit of your Atlas cluster")
    assert not is_mongo_capacity_error("connection refused")
    body = capacity_unavailable_payload()
    assert body["code"] == "DATABASE_CAPACITY_EXCEEDED"


def test_scheduler_heartbeat_freshness_authority():
    now = datetime(2026, 8, 6, 15, 0, tzinfo=timezone.utc)
    fresh = evaluate_scheduler_heartbeat(
        last_heartbeat_at=(now - timedelta(seconds=60)).isoformat(),
        now=now,
        stale_after_seconds=300,
    )
    assert fresh.status == SCHEDULER_HEALTH_HEALTHY
    assert fresh.stale is False
    assert map_platform_status(fresh) == "healthy"

    stale = evaluate_scheduler_heartbeat(
        last_heartbeat_at=(now - timedelta(days=20)).isoformat(),
        now=now,
        stale_after_seconds=300,
    )
    assert stale.status == SCHEDULER_HEALTH_UNHEALTHY
    assert stale.stale is True
    assert map_platform_status(stale) == "unhealthy"

    missing = evaluate_scheduler_heartbeat(last_heartbeat_at=None, now=now)
    assert missing.status == SCHEDULER_HEALTH_UNKNOWN
    assert map_platform_status(missing) == "unhealthy"


def test_idle_skip_poll_tick_keeps_job_healthy():
    from routes.observability import _compute_job_state_and_reason
    from services.job_schedule_registry import get_job_entry

    now = datetime(2026, 8, 6, 18, 0, tzinfo=timezone.utc)
    entry = get_job_entry("compliance_recalc_worker")
    detail = {
        "last_completed": (now - timedelta(seconds=20)).isoformat(),
        "last_success": (now - timedelta(hours=3)).isoformat(),
        "last_run_status": "success",
        "poll_persist_skipped": True,
        "outcome_metrics": {"outcome_kind": "CONTENTION_ONLY"},
    }
    state, _reason = _compute_job_state_and_reason(
        "compliance_recalc_worker", detail, now, entry, heartbeat_stale=False
    )
    assert state == "healthy"

    hb_state, _ = _compute_job_state_and_reason(
        "scheduler_heartbeat",
        {"last_completed": now.isoformat(), "poll_persist_skipped": True},
        now,
        get_job_entry("scheduler_heartbeat"),
        heartbeat_stale=False,
    )
    assert hb_state == "healthy"


def test_retention_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED", raising=False)
    from services.operational_retention_purge import retention_purge_enabled

    assert retention_purge_enabled() is False
