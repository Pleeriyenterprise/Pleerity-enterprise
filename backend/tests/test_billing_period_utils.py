"""Tests for stored period-end coercion (Mongo may persist datetime, ISO string, or unix int)."""
from datetime import datetime, timezone

from services.billing_period_utils import (
    coerce_stored_period_end_to_datetime,
    normalize_stored_period_end_for_api,
    period_end_from_stripe_subscription_dict,
    period_end_from_stripe_unix,
    period_end_stored_value_is_valid,
    period_start_from_stripe_subscription_dict,
)


def test_coerce_datetime_utc():
    dt = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert coerce_stored_period_end_to_datetime(dt) == dt


def test_coerce_datetime_naive_treated_as_utc():
    dt = datetime(2026, 4, 15, 12, 0, 0)
    out = coerce_stored_period_end_to_datetime(dt)
    assert out is not None
    assert out.tzinfo == timezone.utc


def test_coerce_iso_string_z():
    s = "2026-04-15T12:00:00+00:00"
    out = coerce_stored_period_end_to_datetime(s)
    assert out is not None
    assert out.year == 2026 and out.month == 4 and out.day == 15


def test_coerce_unix_int():
    # 2026-04-15 ~ 1776268800 (approx) — use a fixed valid ts above MIN_VALID
    ts = 1715792400  # 2024-05-15 UTC
    out = coerce_stored_period_end_to_datetime(ts)
    assert out is not None
    assert out.timestamp() == float(ts)


def test_coerce_rejects_epoch():
    assert coerce_stored_period_end_to_datetime(0) is None
    assert coerce_stored_period_end_to_datetime(datetime(1970, 1, 1, tzinfo=timezone.utc)) is None


def test_normalize_matches_coerce():
    assert normalize_stored_period_end_for_api("2026-04-15T00:00:00Z") == coerce_stored_period_end_to_datetime(
        "2026-04-15T00:00:00Z"
    )


def test_period_end_stored_value_is_valid_string():
    assert period_end_stored_value_is_valid("2026-04-15T00:00:00+00:00") is True
    assert period_end_stored_value_is_valid("invalid") is False


def test_period_end_from_stripe_unix_accepts_numeric_string():
    ts = 1715792400
    assert period_end_from_stripe_unix(str(ts)) == period_end_from_stripe_unix(ts)


def test_subscription_dict_falls_back_to_item_current_period_end():
    cpe = 1715792400
    cps = 1713108000
    sub = {
        "current_period_end": None,
        "current_period_start": None,
        "items": {"data": [{"current_period_end": cpe, "current_period_start": cps}]},
    }
    end = period_end_from_stripe_subscription_dict(sub)
    start = period_start_from_stripe_subscription_dict(sub)
    assert end is not None and int(end.timestamp()) == cpe
    assert start is not None and int(start.timestamp()) == cps


def test_subscription_dict_prefers_top_level_when_present():
    top_end = 1715888800
    item_end = 1715792400
    sub = {
        "current_period_end": top_end,
        "current_period_start": top_end - 86400,
        "items": {"data": [{"current_period_end": item_end, "current_period_start": item_end - 86400}]},
    }
    assert int(period_end_from_stripe_subscription_dict(sub).timestamp()) == top_end
