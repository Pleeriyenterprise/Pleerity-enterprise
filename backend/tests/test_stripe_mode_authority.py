"""Stripe mode authority — live/test governance and mixed-mode protection."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from services.stripe_mode_authority import (
    StripeModeConfigurationError,
    StripeObjectModeMismatchError,
    assert_secret_key_matches_mode,
    assert_stripe_object_mode,
    build_stripe_operational_config,
    get_stripe_mode,
    resolve_stripe_secret_key,
    resolve_webhook_secret,
    resolve_webhook_secret_with_source,
)


@pytest.fixture(autouse=True)
def _clear_stripe_env(monkeypatch):
    for key in list(os.environ.keys()):
        if key.startswith("STRIPE_") or key.startswith("REACT_APP_STRIPE_"):
            monkeypatch.delenv(key, raising=False)
    yield


def test_get_stripe_mode_requires_explicit_or_legacy_key(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    assert get_stripe_mode() == "test"

    monkeypatch.delenv("STRIPE_MODE", raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    assert get_stripe_mode() == "test"

    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(StripeModeConfigurationError):
        get_stripe_mode()


def test_resolve_secret_key_mode_specific(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY_LIVE", "sk_live_abc")
    assert resolve_stripe_secret_key() == "sk_live_abc"


def test_reject_cross_mode_legacy_secret(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    with pytest.raises(StripeModeConfigurationError):
        resolve_stripe_secret_key()


def test_no_cross_mode_fallback_between_live_and_test_vars(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_LIVE", "sk_live_only")
    with pytest.raises(StripeModeConfigurationError):
        resolve_stripe_secret_key()


def test_webhook_secret_selected_by_mode(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_TEST", "whsec_test")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_LIVE", "whsec_live")
    assert resolve_webhook_secret() == "whsec_test"
    secret, env_var = resolve_webhook_secret_with_source()
    assert env_var == "STRIPE_WEBHOOK_SECRET_TEST"
    assert secret == "whsec_test"


def test_assert_stripe_object_mode_rejects_opposite_livemode():
    with pytest.raises(StripeObjectModeMismatchError):
        assert_stripe_object_mode({"livemode": True}, expected_mode="test", object_type="coupon")


def test_operational_config_reports_mismatch(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_bad")
    cfg = build_stripe_operational_config()
    assert cfg["stripe_mode"] == "live"
    assert cfg["mode_badge"] == "LIVE MODE"
    assert any("legacy" in e.lower() or "mismatch" in e.lower() for e in cfg.get("errors", []))


def test_operational_config_no_secrets(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_ok")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_TEST", "whsec_test")
    cfg = build_stripe_operational_config()
    dumped = str(cfg)
    assert "sk_test_ok" not in dumped
    assert "whsec_test" not in dumped
    assert "requirements" in cfg
    assert "frontend_alignment" in cfg


def test_configure_stripe_sdk_sets_api_key(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_configure")
    from services.stripe_mode_authority import configure_stripe_sdk
    import stripe

    key = configure_stripe_sdk()
    assert key == "sk_test_configure"
    assert stripe.api_key == "sk_test_configure"


def test_assert_secret_key_prefix():
    assert_secret_key_matches_mode("sk_live_x", "live")
    with pytest.raises(StripeModeConfigurationError):
        assert_secret_key_matches_mode("sk_test_x", "live")
