"""Admin pilot invite API helpers — code suggestion, distribution, operational config."""
from __future__ import annotations

from services.pilot_invite_service import (
    build_invite_distribution,
    get_pilot_invite_operational_config,
    suggest_invite_code,
)


def test_suggest_invite_code_format():
    code = suggest_invite_code(prefix="LANDLORD-PILOT", variant="ALPHA")
    assert code.startswith("LANDLORD-PILOT-ALPHA")
    assert len(code) >= 10


def test_build_invite_distribution_uses_commercial_truth_not_hardcoded_months(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_dist")
    for plan in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"):
        monkeypatch.setenv(f"STRIPE_TEST_PRICE_{plan}_MONTHLY", f"price_{plan}_monthly")
    doc = {
        "code": "TEST-PILOT",
        "discount_duration": "repeating",
        "discount_duration_in_months": 3,
        "discount_percent": 100,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
        "program_type": "FOUNDING_PILOT",
    }
    dist = build_invite_distribution(doc, base_url="https://app.example.com", plan_code="PLAN_1_SOLO")
    assert "invite=TEST-PILOT" in dist["invite_url"]
    assert "3 month" in dist["commercial_summary"]
    assert "2 month" not in dist["commercial_summary"]


def test_operational_config_no_secrets(monkeypatch):
    import os

    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_ops")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_TEST", "whsec_test_ops")
    cfg = get_pilot_invite_operational_config()
    assert "stripe_mode" in cfg
    assert "mode_badge" in cfg
    assert "requirements" in cfg
    assert "frontend_alignment" in cfg
    for row in cfg["requirements"]:
        assert "configured" in row
    dumped = str(cfg)
    assert "sk_test_ops" not in dumped
    assert "whsec_test_ops" not in dumped
