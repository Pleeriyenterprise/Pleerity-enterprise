"""GPT-first public support planner (feature-flagged)."""
import json

import pytest

from services.support_gpt_first_planner import (
    _extract_json_object,
    _normalize_planner_payload,
    support_gpt_first_enabled,
    try_gpt_first_deterministic_shortcuts,
)


def test_support_gpt_first_enabled_default_off(monkeypatch):
    monkeypatch.delenv("SUPPORT_GPT_FIRST_ENABLED", raising=False)
    assert support_gpt_first_enabled() is False
    monkeypatch.setenv("SUPPORT_GPT_FIRST_ENABLED", "true")
    assert support_gpt_first_enabled() is True


def test_extract_json_object_fenced():
    raw = """Here is JSON:
```json
{"reply_text": "Hello there", "intent_summary": "x", "confidence": 0.8, "should_show_actions": false, "actions": [], "needs_clarification": false, "clarification_question": "", "escalation_recommended": false, "safety_boundary": "none", "sources_used": []}
```
"""
    obj = _extract_json_object(raw)
    assert obj and obj.get("reply_text") == "Hello there"


def test_normalize_planner_payload_requires_reply():
    assert _normalize_planner_payload({}) is None
    assert _normalize_planner_payload({"reply_text": "x" * 3}) is None
    out = _normalize_planner_payload(
        {
            "reply_text": "This is a valid reply for the user.",
            "intent_summary": "billing_question",
            "confidence": 0.72,
            "should_show_actions": True,
            "actions": ["sign_in", "invalid_id"],
            "needs_clarification": False,
            "clarification_question": "",
            "escalation_recommended": False,
            "safety_boundary": "none",
            "sources_used": [{"type": "kc_article", "title": "T"}],
        }
    )
    assert out is not None
    assert out["action_ids"] == ["sign_in"]


@pytest.mark.asyncio
async def test_try_gpt_first_shortcut_password(monkeypatch):
    monkeypatch.setenv("SUPPORT_GPT_FIRST_ENABLED", "true")
    out = await try_gpt_first_deterministic_shortcuts(
        conversation_id="c1",
        message="I forgot my password",
        conversation_history=[],
        ctx={},
        client_context=None,
    )
    assert out is not None
    assert out.get("metadata", {}).get("gpt_first_shortcut") == "password_reset"
    assert "Forgot password" in out.get("response", "") or "forgot password" in out.get("response", "").lower()


@pytest.mark.asyncio
async def test_run_gpt_first_public_turn_returns_none_when_flag_off(monkeypatch):
    monkeypatch.delenv("SUPPORT_GPT_FIRST_ENABLED", raising=False)
    from services.support_gpt_first_planner import run_gpt_first_public_turn

    out = await run_gpt_first_public_turn(
        conversation_id="c1",
        message="How do I upload a certificate?",
        conversation_history=[],
        ctx={},
    )
    assert out is None


@pytest.mark.asyncio
async def test_run_gpt_first_public_turn_planner_success(monkeypatch):
    monkeypatch.setenv("SUPPORT_GPT_FIRST_ENABLED", "true")
    from services import support_gpt_first_planner as mod

    async def fake_chat(system, user, model="gemini-2.0-flash"):
        payload = {
            "reply_text": "You can upload certificates from the property record after signing in.",
            "intent_summary": "upload_help",
            "confidence": 0.85,
            "should_show_actions": True,
            "actions": ["sign_in"],
            "needs_clarification": False,
            "clarification_question": "",
            "escalation_recommended": False,
            "safety_boundary": "none",
            "sources_used": [{"type": "kc_article", "title": "Certificates"}],
        }
        return json.dumps(payload)

    monkeypatch.setattr(mod, "support_gpt_first_enabled", lambda: True)
    monkeypatch.setattr("utils.llm_chat._get_api_key", lambda: "fake")
    monkeypatch.setattr("utils.llm_chat.chat", fake_chat)
    monkeypatch.setattr(
        "services.support_chatbot.defer_public_kb_for_operational_routing",
        lambda _m, _c: True,
    )

    out = await mod.run_gpt_first_public_turn(
        conversation_id="c1",
        message="How do I upload a certificate?",
        conversation_history=[],
        ctx={},
    )
    assert out is not None
    assert out["metadata"].get("gpt_first") is True
    assert "sign in" in (out.get("actions") or [{}])[0].get("label", "").lower()
