"""Admin pilot invite API helpers — code suggestion, distribution, operational config."""
from __future__ import annotations

from unittest.mock import AsyncMock

from services.pilot_invite_service import (
    build_invite_distribution,
    get_pilot_invite_operational_config,
    render_pilot_invite_email,
    send_pilot_invite_email,
    suggest_invite_code,
)
import pytest


def test_suggest_invite_code_format():
    code = suggest_invite_code(prefix="LANDLORD-PILOT", variant="ALPHA")
    assert "LANDLORD" in code
    assert "ALPHA" in code
    assert len(code) >= 4
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


def test_build_invite_distribution_uses_canonical_encoded_intake_url(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    doc = {
        "code": "FOUNDING+ALPHA",
        "status": "active",
        "applies_to_plan_codes": ["PLAN_1_SOLO"],
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "discount_percent": 100,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
        "program_type": "FOUNDING_PILOT",
    }
    dist = build_invite_distribution(doc, base_url="https://app.example.com/", plan_code="PLAN_1_SOLO")
    assert dist["canonical_intake_path"] == "/intake/start"
    assert "/intake/start?" in dist["invite_url"]
    assert "invite=FOUNDING%2BALPHA" in dist["invite_url"]
    assert "plan=PLAN_1_SOLO" in dist["invite_url"]


def test_render_pilot_invite_email_contains_cta_and_plain_raw_url():
    doc = {
        "code": "FOUNDING-8K4D",
        "status": "active",
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "discount_percent": 100,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
        "program_type": "FOUNDING_PILOT",
    }
    dist = build_invite_distribution(doc, base_url="https://app.example.com", plan_code="PLAN_1_SOLO")
    rendered = render_pilot_invite_email(doc, dist, recipient_name="Ava", personal_note="Welcome aboard.")
    assert "Start your founding pilot access" in rendered["html"]
    assert dist["invite_url"].replace("&", "&amp;") in rendered["html"]
    assert "Your first 2 months are free." in rendered["html"]
    assert dist["invite_url"] in rendered["text"]
    assert "Welcome aboard." in rendered["text"]


def test_build_invite_distribution_rejects_inactive_and_disallowed_plan():
    doc = {
        "code": "FOUNDING-8K4D",
        "status": "disabled",
        "applies_to_plan_codes": ["PLAN_1_SOLO"],
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "discount_percent": 100,
    }
    with pytest.raises(ValueError, match="not active"):
        build_invite_distribution(doc, base_url="https://app.example.com", plan_code="PLAN_1_SOLO")
    doc["status"] = "active"
    with pytest.raises(ValueError, match="selected plan"):
        build_invite_distribution(doc, base_url="https://app.example.com", plan_code="PLAN_3_PRO")
    with pytest.raises(ValueError, match="Unsupported plan_code"):
        build_invite_distribution(doc, base_url="https://app.example.com", plan_code="UNKNOWN_PLAN")


@pytest.mark.asyncio
async def test_send_pilot_invite_email_audits_orchestrator_and_preserves_usage(monkeypatch):
    inserted = []
    updates = []
    sent = []

    class FakeCollection:
        async def insert_one(self, doc):
            inserted.append(doc)

        async def update_one(self, query, update):
            updates.append((query, update))
            for row in inserted:
                if row.get("attempt_id") == query.get("attempt_id"):
                    row.update(update.get("$set") or {})

    class FakeDb(dict):
        def __getitem__(self, name):
            if name not in self:
                self[name] = FakeCollection()
            return dict.__getitem__(self, name)

    class FakeOrchestrator:
        async def send(self, **kwargs):
            sent.append(kwargs)
            return type(
                "Result",
                (),
                {
                    "outcome": "sent",
                    "message_id": "msg_123",
                    "details": {"provider_message_id": "pm_123"},
                    "error_message": None,
                    "block_reason": None,
                },
            )()

    import services.notification_orchestrator as orchestrator_module
    import services.pilot_invite_service as invite_service

    db = FakeDb()
    monkeypatch.setattr(invite_service.database, "get_db", lambda: db)
    monkeypatch.setattr(orchestrator_module, "notification_orchestrator", FakeOrchestrator())
    doc = {
        "invite_code_id": "inv_123",
        "code": "FOUNDING-8K4D",
        "status": "active",
        "used_count": 0,
        "max_uses": 5,
        "remaining_uses": 5,
        "applies_to_plan_codes": ["PLAN_1_SOLO"],
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "discount_percent": 100,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
        "program_type": "FOUNDING_PILOT",
    }

    result = await send_pilot_invite_email(
        doc,
        base_url="https://app.example.com",
        recipient_email="pilot@example.com",
        recipient_name="Pilot",
        plan_code="PLAN_1_SOLO",
        personal_note="Looking forward to working together.",
        sent_by="admin@example.com",
    )

    assert result["status"] == "sent"
    assert inserted[0]["invite_code"] == "FOUNDING-8K4D"
    assert inserted[0]["recipient_email"] == "pilot@example.com"
    assert inserted[0]["status"] == "sent"
    assert inserted[0]["provider_message_id"] == "pm_123"
    assert sent[0]["template_key"] == "PILOT_INVITE_SEND"
    assert sent[0]["context"]["recipient"] == "pilot@example.com"
    assert "Start your founding pilot access" in sent[0]["context"]["message"]
    assert "/intake/start?" in sent[0]["context"]["text_message"]
    assert doc["used_count"] == 0


@pytest.mark.asyncio
async def test_send_endpoint_returns_404_for_invalid_invite(monkeypatch):
    from fastapi import HTTPException
    import routes.admin_pilot_invites as route_module

    class FakeRequest:
        headers = {"origin": "https://app.example.com"}
        base_url = "https://api.example.com/"

    monkeypatch.setattr(route_module, "get_invite_code", AsyncMock(return_value=None))

    body = route_module.PilotInviteSendBody(
        recipient_email="pilot@example.com",
        plan_code="PLAN_1_SOLO",
    )
    with pytest.raises(HTTPException) as exc:
        await route_module.send_pilot_invite(
            FakeRequest(),
            "MISSING",
            body,
            _user={"email": "admin@example.com"},
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Invite code not found"


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
