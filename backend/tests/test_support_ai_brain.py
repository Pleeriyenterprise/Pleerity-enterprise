"""AI-first public support brain (feature-flagged)."""
import json

import pytest

from services.support_ai_brain import (
    _extract_json_object,
    _normalize_brain_payload,
    support_ai_brain_enabled,
    try_protected_deterministic_shortcuts,
)
from services.support_ai_instructions import build_support_ai_system_instruction


def test_support_ai_brain_enabled_flag(monkeypatch):
    monkeypatch.delenv("SUPPORT_GPT_FIRST_ENABLED", raising=False)
    assert support_ai_brain_enabled() is False
    monkeypatch.setenv("SUPPORT_GPT_FIRST_ENABLED", "true")
    assert support_ai_brain_enabled() is True


def test_system_instruction_covers_tone_and_boundaries():
    text = build_support_ai_system_instruction().lower()
    assert "legal" in text
    assert "registry" in text or "pricing" in text
    assert "menu" in text or "sales" in text


def test_normalize_brain_payload_new_schema():
    out = _normalize_brain_payload(
        {
            "reply_text": "We help landlords manage compliance evidence in one place.",
            "intent_summary": "company_about",
            "user_goal": "learn what the business does",
            "topic": "company",
            "confidence": 0.9,
            "show_actions": False,
            "actions": [],
            "needs_clarification": False,
            "clarification_question": "",
            "escalation_suggested": False,
            "safety_boundary": "none",
            "sources_used": [],
        }
    )
    assert out is not None
    assert out["topic"] == "company"
    assert out["show_actions"] is False


@pytest.mark.asyncio
async def test_protected_password_shortcut(monkeypatch):
    out = await try_protected_deterministic_shortcuts(
        conversation_id="c1",
        message="I forgot my password",
        conversation_history=[],
        ctx={},
        client_context=None,
    )
    assert out is not None
    assert out.get("metadata", {}).get("ai_brain_shortcut") == "password_reset"


@pytest.mark.asyncio
async def test_brain_turn_off_without_flag(monkeypatch):
    monkeypatch.delenv("SUPPORT_GPT_FIRST_ENABLED", raising=False)
    from services.support_ai_brain import run_support_ai_brain_turn

    assert await run_support_ai_brain_turn(
        conversation_id="c1",
        message="Hello",
        conversation_history=[],
        ctx={},
    ) is None


@pytest.mark.asyncio
async def test_brain_turn_success(monkeypatch):
    monkeypatch.setenv("SUPPORT_GPT_FIRST_ENABLED", "true")
    from services import support_ai_brain as brain

    async def fake_chat(system, user, model="gemini-2.0-flash"):
        return json.dumps(
            {
                "reply_text": "We're a property compliance platform for landlords and managers.",
                "intent_summary": "company_about",
                "user_goal": "understand the business",
                "topic": "company",
                "confidence": 0.88,
                "show_actions": False,
                "actions": [],
                "needs_clarification": False,
                "clarification_question": "",
                "escalation_suggested": False,
                "safety_boundary": "none",
                "sources_used": [],
            }
        )

    monkeypatch.setattr("utils.llm_chat._get_api_key", lambda: "fake")
    monkeypatch.setattr("utils.llm_chat.chat", fake_chat)
    async def _empty_retrieval(*a, **k):
        return [], [], [], None

    monkeypatch.setattr(brain, "_gather_retrieval_context", _empty_retrieval)

    out = await brain.run_support_ai_brain_turn(
        conversation_id="c1",
        message="What is your business about?",
        conversation_history=[],
        ctx={},
    )
    assert out is not None
    assert out["metadata"].get("support_ai_brain") is True
    assert "compliance" in out["response"].lower() or "property" in out["response"].lower()
