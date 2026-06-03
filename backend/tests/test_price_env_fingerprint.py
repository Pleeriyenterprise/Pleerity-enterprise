"""Stripe price env fingerprint and read-path degradation."""
from __future__ import annotations

import pytest

from services.plan_registry import (
    PlanCode,
    StripeModeMismatchError,
    fingerprint_stripe_price_env,
    plan_registry,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    import services.plan_registry as pr

    pr._STRIPE_PRICE_CACHE.clear()
    yield
    pr._STRIPE_PRICE_CACHE.clear()


def test_fingerprint_detects_duplicate_monthly_ids(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY_LIVE", "sk_live_fingerprint_test")
    for plan in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"):
        monkeypatch.setenv(f"STRIPE_LIVE_PRICE_{plan}_MONTHLY", "price_same_monthly")
        monkeypatch.setenv(f"STRIPE_LIVE_PRICE_{plan}_ONBOARDING", f"price_{plan}_onb")

    fp = fingerprint_stripe_price_env("live")
    assert fp["duplicate_detected"] is True
    assert len(fp["duplicate_monthly_groups"]) == 1
    assert set(fp["duplicate_monthly_groups"][0]["plan_codes"]) == {
        "PLAN_1_SOLO",
        "PLAN_2_PORTFOLIO",
        "PLAN_3_PRO",
    }


def test_get_plan_degrades_on_duplicate_without_raising(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY_LIVE", "sk_live_fingerprint_test")
    for plan in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"):
        monkeypatch.setenv(f"STRIPE_LIVE_PRICE_{plan}_MONTHLY", "price_dup")
        monkeypatch.setenv(f"STRIPE_LIVE_PRICE_{plan}_ONBOARDING", f"price_{plan}_onb")

    plan = plan_registry.get_plan(PlanCode.PLAN_2_PORTFOLIO)
    assert plan.get("stripe_price_config_degraded") is True
    assert plan.get("stripe_subscription_price_id") is None
    assert plan["monthly_price"] == 39.0


def test_checkout_still_raises_on_duplicate(monkeypatch):
    import services.stripe_service as ss
    from services.stripe_service import StripeService

    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY_LIVE", "sk_live_fingerprint_test")
    for plan in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"):
        monkeypatch.setenv(f"STRIPE_LIVE_PRICE_{plan}_MONTHLY", "price_dup")
        monkeypatch.setenv(f"STRIPE_LIVE_PRICE_{plan}_ONBOARDING", f"price_{plan}_onb")

    with pytest.raises(StripeModeMismatchError, match="Duplicate"):
        ss.get_stripe_price_mappings("live")
