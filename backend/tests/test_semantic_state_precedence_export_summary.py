from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.semantic_state_precedence_adapter import (
    HIGH_COLLAPSE_HIGH_PRIORITY,
    HIGH_DELTA,
    INSUFFICIENT_SAMPLE_VOLUME,
    LOW_RISK_FIRST_MIGRATION,
    REMINDER_ENGINE,
    REPORT_EXPORT,
    WIDESPREAD_COLLAPSE_DELTA,
    build_semantic_delta_export_snapshot,
    build_semantic_delta_rollout_summary,
    get_semantic_delta_summary,
    get_semantic_delta_summary_by_consumer,
    get_semantic_delta_summary_by_impact,
    get_semantic_delta_summary_by_semantic_state,
    observe_consumer_precedence_delta,
    reset_observed_delta_events,
)


def _seed_events():
    reset_observed_delta_events()
    observe_consumer_precedence_delta(REMINDER_ENGINE, "OPERATIONALLY_OPEN")
    observe_consumer_precedence_delta(REMINDER_ENGINE, "EXPIRY_REVIEW_REQUIRED")
    observe_consumer_precedence_delta(REPORT_EXPORT, "EXPIRY_REVIEW_REQUIRED")
    observe_consumer_precedence_delta(REPORT_EXPORT, "OPERATIONALLY_OPEN")
    observe_consumer_precedence_delta(REPORT_EXPORT, "PARTIALLY_COMPLETE")


def test_summary_helpers_are_deterministic():
    _seed_events()
    s = get_semantic_delta_summary()
    assert s["event_count"] == 5
    assert s["delta_count"] >= 1
    assert s["by_consumer"][REPORT_EXPORT] == 3
    assert s["non_blocking"] is True


def test_filtering_and_grouping_work():
    _seed_events()
    s1 = get_semantic_delta_summary(consumer=REMINDER_ENGINE)
    assert s1["event_count"] == 2
    s2 = get_semantic_delta_summary(semantic_state="EXPIRY_REVIEW_REQUIRED")
    assert s2["event_count"] == 2
    s3 = get_semantic_delta_summary_by_semantic_state()
    assert s3["by_semantic_state"]["OPERATIONALLY_OPEN"]["event_count"] == 2
    s4 = get_semantic_delta_summary_by_impact(high_impact_only=True)
    assert any(k in s4["by_delta_impact"] for k in (HIGH_DELTA, WIDESPREAD_COLLAPSE_DELTA))


def test_time_window_filter_is_lightweight_and_stable():
    _seed_events()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    s = get_semantic_delta_summary(since_iso=past, until_iso=future)
    assert s["event_count"] == 5


def test_export_snapshot_is_deterministic():
    _seed_events()
    snap = build_semantic_delta_export_snapshot()
    rows = snap["snapshot"]
    assert len(rows) >= 2
    assert rows[0]["runtime_behavior_changed"] is False
    assert snap["non_blocking"] is True


def test_rollout_readiness_signals_classify_correctly():
    _seed_events()
    roll = build_semantic_delta_rollout_summary()
    rows = {r["consumer"]: r for r in roll["rollout_summary"]}
    # with <5 samples per consumer, signal should remain insufficient volume
    assert rows[REMINDER_ENGINE]["rollout_signal"] == INSUFFICIENT_SAMPLE_VOLUME
    assert rows[REPORT_EXPORT]["rollout_signal"] == INSUFFICIENT_SAMPLE_VOLUME

    # simulate higher volume high-collapse reminder stream
    reset_observed_delta_events()
    for _ in range(6):
        observe_consumer_precedence_delta(REMINDER_ENGINE, "OPERATIONALLY_OPEN")
    roll2 = build_semantic_delta_rollout_summary()
    row2 = {r["consumer"]: r for r in roll2["rollout_summary"]}[REMINDER_ENGINE]
    assert row2["highest_impact"] in (HIGH_DELTA, WIDESPREAD_COLLAPSE_DELTA)
    assert row2["rollout_signal"] in (HIGH_COLLAPSE_HIGH_PRIORITY, LOW_RISK_FIRST_MIGRATION, INSUFFICIENT_SAMPLE_VOLUME)


def test_helpers_remain_non_blocking_and_runtime_unchanged():
    _seed_events()
    by_cons = get_semantic_delta_summary_by_consumer()
    assert by_cons["non_blocking"] is True
    snap = build_semantic_delta_export_snapshot()
    assert all(r["runtime_behavior_changed"] is False for r in snap["snapshot"])
