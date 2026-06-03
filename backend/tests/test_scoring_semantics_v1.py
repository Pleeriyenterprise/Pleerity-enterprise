"""Unit tests for SCORING_SEMANTICS_V1 helpers (stale, partial, portfolio refinement)."""
from datetime import datetime, timezone

from services.scoring_semantics_v1 import (
    SCORE_STATUS_CALCULATING,
    SCORE_STATUS_OK,
    SCORE_STATUS_PARTIAL,
    SCORE_STATUS_RECONCILIATION_REQUIRED,
    SCORE_STATUS_STALE,
    SCORE_STATUS_UNAVAILABLE,
    aggregate_persisted_portfolio_headline,
    headline_score_display_for_export,
    is_property_score_stale,
    refine_portfolio_score_status,
    resolve_property_score_status,
)


def _prop(score, *, last_iso=None, pending=False, override=None):
    row = {"compliance_score": score, "compliance_score_pending": pending}
    if last_iso is not None:
        row["compliance_last_calculated_at"] = last_iso
    if override is not None:
        row["compliance_headline_status_override"] = override
    return row


def test_resolve_property_score_status_ok_and_stale():
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    fresh = _prop(80, last_iso="2026-03-01T00:00:00+00:00")
    assert resolve_property_score_status(fresh, now=now) == SCORE_STATUS_OK
    old = _prop(80, last_iso="2025-01-01T00:00:00+00:00")
    assert resolve_property_score_status(old, now=now) == SCORE_STATUS_STALE


def test_resolve_property_score_pending_overrides_existing_score():
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    row = _prop(55, last_iso="2026-03-01T00:00:00+00:00", pending=True)
    assert resolve_property_score_status(row, now=now) == SCORE_STATUS_CALCULATING


def test_resolve_property_calculating_and_reconciliation():
    now = datetime.now(timezone.utc)
    assert resolve_property_score_status(_prop(None, pending=True), now=now) == SCORE_STATUS_CALCULATING
    assert resolve_property_score_status(_prop(None, pending=False), now=now) == SCORE_STATUS_RECONCILIATION_REQUIRED


def test_aggregate_empty_and_all_missing():
    h0 = aggregate_persisted_portfolio_headline([])
    assert h0["score_status"] == SCORE_STATUS_UNAVAILABLE
    assert h0["portfolio_score"] is None

    props = [_prop(None), _prop(None, pending=True)]
    h = aggregate_persisted_portfolio_headline(props, now=datetime(2026, 4, 1, tzinfo=timezone.utc))
    assert h["score_status"] == SCORE_STATUS_CALCULATING

    props2 = [_prop(None), _prop(None, pending=False)]
    h2 = aggregate_persisted_portfolio_headline(props2, now=datetime(2026, 4, 1, tzinfo=timezone.utc))
    assert h2["score_status"] == SCORE_STATUS_RECONCILIATION_REQUIRED


def test_aggregate_all_scored_with_pending_recalc():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    props = [
        _prop(80, last_iso="2026-03-01T00:00:00+00:00", pending=True),
        _prop(70, last_iso="2026-03-01T00:00:00+00:00", pending=False),
    ]
    h = aggregate_persisted_portfolio_headline(props, now=now)
    assert h["portfolio_score"] == 75
    assert h["score_status"] == SCORE_STATUS_PARTIAL
    assert "score updates processing" in (h.get("score_status_message") or "").lower()


def test_aggregate_partial_vs_stale_precedence():
    """Partial coverage (missing scores) must dominate stale when both apply."""
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    old_score = _prop(70, last_iso="2024-01-01T00:00:00+00:00")
    missing = _prop(None, pending=False)
    h = aggregate_persisted_portfolio_headline([old_score, missing], now=now)
    assert h["score_status"] == SCORE_STATUS_PARTIAL
    assert h["properties_missing_score"] == 1


def test_refine_portfolio_score_status():
    assert refine_portfolio_score_status(SCORE_STATUS_OK, has_missing=True, any_stale_among_scored=True) == SCORE_STATUS_PARTIAL
    assert refine_portfolio_score_status(SCORE_STATUS_OK, has_missing=False, any_stale_among_scored=True) == SCORE_STATUS_STALE
    assert refine_portfolio_score_status(SCORE_STATUS_OK, has_missing=False, any_stale_among_scored=False) == SCORE_STATUS_OK


def test_headline_score_display_for_export():
    assert headline_score_display_for_export(72, SCORE_STATUS_OK) == "72"
    assert headline_score_display_for_export(72, SCORE_STATUS_PARTIAL) == "72"
    assert headline_score_display_for_export(None, SCORE_STATUS_RECONCILIATION_REQUIRED) == "N/A"
    assert headline_score_display_for_export(None, SCORE_STATUS_CALCULATING) == "Calculating"


def test_is_property_score_stale_no_score():
    assert is_property_score_stale(_prop(None, last_iso="2020-01-01")) is False
