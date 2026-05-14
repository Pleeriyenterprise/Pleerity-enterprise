"""
Support hardening: rate limits, ChatResponse contract, small-talk, handoff options, portal ticket fields.
"""
import os
import asyncio
import pytest
from unittest.mock import AsyncMock

from routes.support import ChatResponse, SUPPORT_CHAT_RATE_LIMIT_MESSAGE
from services.support_chatbot import (
    try_small_talk_reply,
    needs_human_handoff,
    build_public_handoff_options,
    is_legal_advice_request,
)


def test_chat_response_serializes_handoff_summary():
    m = ChatResponse(
        conversation_id="CONV-test",
        response="Handoff text",
        action="handoff",
        metadata={"service_area": "other"},
        handoff_summary="Structured summary line 1\nLine 2",
    )
    dumped = m.model_dump()
    assert dumped["handoff_summary"] == "Structured summary line 1\nLine 2"
    assert dumped["metadata"].get("handoff_summary") is None


@pytest.mark.integration
def test_support_chat_rate_limit_blocks_excess_and_lookup_still_works(monkeypatch):
    """POST /api/support/chat is IP rate limited; lookup uses a separate bucket."""
    try:
        from pymongo import MongoClient

        MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=2000).admin.command("ping")
    except Exception:
        pytest.skip("MongoDB unreachable")

    from fastapi.testclient import TestClient
    from server import app
    import routes.support as support_mod

    real_check = support_mod.rate_limiter.check_rate_limit
    ip_hits = {}

    async def shim(key, max_attempts, window_minutes):
        if key.startswith("support_lookup:"):
            return await real_check(key, max_attempts, window_minutes)
        if key.startswith("support_chat:conv:"):
            return await real_check(key, max_attempts, window_minutes)
        if key.startswith("support_chat:ip:"):
            ip_hits[key] = ip_hits.get(key, 0) + 1
            if ip_hits[key] >= 3:
                return False, "internal detail must not reach client"
            return True, None
        return await real_check(key, max_attempts, window_minutes)

    monkeypatch.setattr(support_mod.rate_limiter, "check_rate_limit", shim)

    ip = "203.0.113.51"
    headers = {"X-Forwarded-For": ip}

    with TestClient(app) as client:
        for i in range(2):
            r = client.post(
                "/api/support/chat",
                json={"message": f"rate test {i}", "channel": "web"},
                headers=headers,
            )
            assert r.status_code == 200, r.text

        r3 = client.post(
            "/api/support/chat",
            json={"message": "should 429", "channel": "web"},
            headers=headers,
        )
        assert r3.status_code == 429
        body = r3.json()
        assert body["detail"] == SUPPORT_CHAT_RATE_LIMIT_MESSAGE
        assert "internal detail" not in body["detail"].lower()
        assert "seconds" not in body["detail"].lower()

        lr = client.post(
            "/api/support/lookup",
            json={"crn": "PLE-CVP-2026-TEST01", "email": "nobody@example.com"},
            headers=headers,
        )
        assert lr.status_code in (200, 404), lr.text


def test_try_small_talk_how_are_you():
    ctx = {}
    out = try_small_talk_reply("how are you?", ctx)
    assert out is not None
    assert out["action"] == "respond"
    assert "pleerity" in out["response"].lower()
    assert out["metadata"].get("small_talk") is True


def test_try_small_talk_skips_human_handoff():
    ctx = {}
    assert needs_human_handoff("can I speak to a human")
    assert try_small_talk_reply("can I speak to a human", ctx) is None


def test_try_small_talk_hello_not_guided():
    ctx = {}
    out = try_small_talk_reply("hello", ctx)
    assert out is not None
    assert out["metadata"].get("guided") is None


def test_try_small_talk_does_not_match_pricing_question():
    ctx = {}
    assert try_small_talk_reply("what is your pricing", ctx) is None


def test_is_legal_advice_request_direct_and_indirect():
    assert is_legal_advice_request("Is it legal for my landlord to evict me without notice?")
    assert is_legal_advice_request("Am I legally compliant with HMO rules?")
    assert is_legal_advice_request("Can you tell me if I will pass inspection?")
    assert is_legal_advice_request("Can I evict a tenant who has not paid rent?")
    assert is_legal_advice_request("What should I legally do about my tenant?")


def test_is_legal_advice_request_does_not_match_normal_queries():
    assert not is_legal_advice_request("What is your pricing for CVP?")
    assert not is_legal_advice_request("how are you?")
    assert not is_legal_advice_request("I want to speak to a human")
    assert not is_legal_advice_request("How do I upload a gas certificate in the portal?")
    assert not is_legal_advice_request("Hello")


@pytest.mark.parametrize(
    "env,expect_live,expect_link",
    [
        ({"TAWKTO_PROPERTY_ID": "", "TAWKTO_WIDGET_ID": "", "SUPPORT_WHATSAPP_NUMBER": "+441234567890"}, False, True),
        (
            {
                "TAWKTO_PROPERTY_ID": "pid",
                "TAWKTO_WIDGET_ID": "wid",
                "SUPPORT_WHATSAPP_NUMBER": "+441234567890",
            },
            True,
            True,
        ),
    ],
)
def test_build_public_handoff_options_tawk_whatsapp(monkeypatch, env, expect_live, expect_link):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    ho = build_public_handoff_options(
        conversation_id="CONV-x",
        crn=None,
        message_snippet="hi",
        transcript_summary="1 messages",
    )
    assert ho["live_chat"]["available"] is expect_live
    if expect_link:
        assert ho["whatsapp"]["link"] and "wa.me" in ho["whatsapp"]["link"]
    if not expect_live:
        assert ho.get("live_chat_notice")
        assert "ticket" in ho["live_chat_notice"].lower()


def test_escalate_assistant_passes_bridge_fields(monkeypatch):
    captured = {}

    async def fake_create_ticket(data, conversation_id=None, **kwargs):
        captured.update(kwargs)
        return {"ticket_id": "TKT-test-123"}

    class FakeAC:
        async def find_one(self, filt, proj=None):
            return {"conversation_id": filt.get("conversation_id"), "escalated": False}

        async def update_one(self, *a, **k):
            return None

    class FakeClients:
        async def find_one(self, *a, **k):
            return {"email": "c@example.com", "customer_reference": "PLE-X"}

    class FakeDb:
        def __init__(self):
            self.assistant_conversations = FakeAC()
            self.clients = FakeClients()

    import services.assistant_chat_service as acs

    monkeypatch.setattr(acs, "get_assistant_transcript", AsyncMock(return_value="user: hi"))
    monkeypatch.setattr(acs.database, "get_db", lambda: FakeDb())
    monkeypatch.setattr(
        "services.support_email_service.send_internal_ticket_notification",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(acs, "create_audit_log", AsyncMock())
    monkeypatch.setattr(
        "services.support_service.TicketService.create_ticket",
        fake_create_ticket,
    )

    out = asyncio.run(
        acs.escalate_assistant_conversation(
            conversation_id="asst-1",
            client_id="cli-1",
            user_id="u1",
            reason="test",
        )
    )
    assert out.get("escalated") is True
    assert captured.get("assistant_conversation_id") == "asst-1"
    assert captured.get("ticket_source") == "portal_assistant"
