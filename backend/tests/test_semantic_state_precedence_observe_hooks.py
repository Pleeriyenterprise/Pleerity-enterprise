from __future__ import annotations

from unittest.mock import patch

from services.semantic_state_precedence_adapter import (
    NO_DELTA,
    PORTFOLIO_SCORE,
    REMINDER_ENGINE,
    REPORT_EXPORT,
    get_observed_delta_events,
    observe_consumer_precedence_delta,
    reset_observed_delta_events,
    summarize_observed_deltas,
)


def test_observe_hook_generates_deterministic_payload():
    reset_observed_delta_events()
    out = observe_consumer_precedence_delta(
        REPORT_EXPORT,
        "EXPIRY_REVIEW_REQUIRED",
        property_id="p1",
        requirement_id="r1",
    )
    assert out["consumer"] == REPORT_EXPORT
    assert out["semantic_state"] == "EXPIRY_REVIEW_REQUIRED"
    assert out["property_id"] == "p1"
    assert out["requirement_id"] == "r1"
    assert out["non_blocking"] is True
    events = get_observed_delta_events()
    assert len(events) == 1


def test_observe_hook_is_non_blocking_when_adapter_fails():
    reset_observed_delta_events()
    with patch(
        "services.semantic_state_precedence_adapter.adapt_report_export_semantic_interpretation",
        side_effect=RuntimeError("boom"),
    ):
        out = observe_consumer_precedence_delta(REPORT_EXPORT, "OPERATIONALLY_OPEN")
    assert out["non_blocking"] is True
    assert out["delta_impact"] == NO_DELTA
    assert out.get("observation_error") == "RuntimeError"


def test_observe_hook_runtime_behavior_remains_legacy_selected():
    reset_observed_delta_events()
    out = observe_consumer_precedence_delta(PORTFOLIO_SCORE, "PARTIALLY_COMPLETE")
    assert out["legacy_interpretation"] in ("PENDING_LIKE", "CURRENT_LIKE", "UNKNOWN_LIKE")
    # Observation event should not enforce semantic runtime output.
    assert out["non_blocking"] is True


def test_high_risk_states_are_sampled_and_aggregated():
    reset_observed_delta_events()
    observe_consumer_precedence_delta(REMINDER_ENGINE, "OPERATIONALLY_OPEN")
    observe_consumer_precedence_delta(REMINDER_ENGINE, "EXPIRY_REVIEW_REQUIRED")
    observe_consumer_precedence_delta(REPORT_EXPORT, "EXPIRY_REVIEW_REQUIRED")
    observe_consumer_precedence_delta(PORTFOLIO_SCORE, "PARTIALLY_COMPLETE")
    agg = summarize_observed_deltas()
    assert agg["event_count"] == 4
    assert agg["delta_count"] >= 1
    assert agg["by_consumer"][REMINDER_ENGINE] == 2
    assert agg["by_semantic_state"]["EXPIRY_REVIEW_REQUIRED"] == 2
    assert agg["non_blocking"] is True
