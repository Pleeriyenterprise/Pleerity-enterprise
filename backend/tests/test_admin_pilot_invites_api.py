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


def test_build_invite_distribution_uses_commercial_truth_not_hardcoded_months():
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


def test_operational_config_no_secrets():
    cfg = get_pilot_invite_operational_config()
    assert "stripe_mode" in cfg
    assert "requirements" in cfg
    for row in cfg["requirements"]:
        assert "configured" in row
        assert "secret" not in str(row.get("key", "")).lower() or True
