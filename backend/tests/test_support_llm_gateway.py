"""Support LLM gateway: OpenAI primary, Gemini fallback."""
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import support_llm_gateway as gw
from services.support_ai_brain import _extract_json_object, _normalize_brain_payload


def _valid_planner_json() -> str:
    return json.dumps(
        {
            "reply_text": "We help landlords manage compliance evidence in one place.",
            "intent_summary": "company",
            "user_goal": "learn about the business",
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


@pytest.mark.asyncio
async def test_no_keys_configured_returns_none(monkeypatch):
    monkeypatch.setattr(gw, "_openai_configured", lambda: False)
    monkeypatch.setattr(gw, "_gemini_configured", lambda: False)
    assert gw.is_any_support_llm_configured() is False
    out = await gw.complete_support_planner("sys", "user")
    assert out is None


@pytest.mark.asyncio
async def test_openai_success_gemini_not_called(monkeypatch):
    calls = []

    async def fake_invoke(provider, **kwargs):
        calls.append(provider)
        return _valid_planner_json()

    monkeypatch.setattr(gw, "_openai_configured", lambda: True)
    monkeypatch.setattr(gw, "_gemini_configured", lambda: True)
    monkeypatch.setattr(gw, "_invoke_provider", fake_invoke)

    out = await gw.complete_support_planner("sys", "user", validate_output=lambda r: bool(r))
    assert out is not None
    assert out.provider_used == "openai"
    assert out.fallback_used is False
    assert calls == ["openai"]


@pytest.mark.asyncio
async def test_openai_error_triggers_gemini(monkeypatch):
    calls = []

    async def fake_invoke(provider, **kwargs):
        calls.append(provider)
        if provider == "openai":
            raise TimeoutError("request timed out")
        return _valid_planner_json()

    monkeypatch.setattr(gw, "_openai_configured", lambda: True)
    monkeypatch.setattr(gw, "_gemini_configured", lambda: True)
    monkeypatch.setattr(gw, "_invoke_provider", fake_invoke)

    out = await gw.complete_support_planner("sys", "user", validate_output=lambda r: bool(r))
    assert out is not None
    assert out.provider_used == "gemini"
    assert out.fallback_used is True
    assert calls == ["openai", "gemini"]


@pytest.mark.asyncio
async def test_openai_invalid_json_triggers_gemini(monkeypatch):
    calls = []

    async def fake_invoke(provider, **kwargs):
        calls.append(provider)
        if provider == "openai":
            return "not json at all"
        return _valid_planner_json()

    monkeypatch.setattr(gw, "_openai_configured", lambda: True)
    monkeypatch.setattr(gw, "_gemini_configured", lambda: True)
    monkeypatch.setattr(gw, "_invoke_provider", fake_invoke)

    def validate(raw: str) -> bool:
        return _normalize_brain_payload(_extract_json_object(raw) or {}) is not None

    out = await gw.complete_support_planner("sys", "user", validate_output=validate)
    assert out is not None
    assert out.provider_used == "gemini"
    assert out.fallback_used is True
    assert calls == ["openai", "gemini"]


@pytest.mark.asyncio
async def test_both_providers_fail_returns_none(monkeypatch):
    async def fake_invoke(provider, **kwargs):
        raise ValueError("provider down")

    monkeypatch.setattr(gw, "_openai_configured", lambda: True)
    monkeypatch.setattr(gw, "_gemini_configured", lambda: True)
    monkeypatch.setattr(gw, "_invoke_provider", fake_invoke)

    out = await gw.complete_support_planner("sys", "user")
    assert out is None


@pytest.mark.asyncio
async def test_redact_error_class_no_message_body():
    assert "TimeoutError" in gw._redact_error_class(TimeoutError("secret user email@test.com"))
    summary = gw._error_summary_for_log(ValueError("OPENAI_API_KEY=sk-secret"))
    assert "sk-secret" not in summary
    assert "api_key" in summary or "missing" in summary


@pytest.mark.asyncio
async def test_brain_skips_llm_when_no_keys(monkeypatch):
    monkeypatch.setenv("SUPPORT_GPT_FIRST_ENABLED", "true")
    monkeypatch.setattr(gw, "is_any_support_llm_configured", lambda: False)
    from services.support_ai_brain import run_support_ai_brain_turn

    out = await run_support_ai_brain_turn(
        conversation_id="c1",
        message="Hello",
        conversation_history=[],
        ctx={},
    )
    assert out is None


@pytest.mark.asyncio
async def test_password_shortcut_no_llm():
    from services.support_ai_brain import try_protected_deterministic_shortcuts

    out = await try_protected_deterministic_shortcuts(
        conversation_id="c1",
        message="I forgot my password",
        conversation_history=[],
        ctx={},
        client_context=None,
    )
    assert out is not None
    assert out["metadata"].get("ai_brain_shortcut") == "password_reset"
