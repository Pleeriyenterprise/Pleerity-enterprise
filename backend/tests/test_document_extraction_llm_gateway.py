"""Document extraction LLM gateway — OpenAI primary, Gemini fallback."""
from __future__ import annotations

import pytest

from services import document_extraction_llm_gateway as gw
from services.extraction_error_presentation import user_facing_extraction_message


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for key in list(__import__("os").environ.keys()):
        if key.startswith("OPENAI_") or key.startswith("LLM_") or key.startswith("DOCUMENT_EXTRACTION_"):
            monkeypatch.delenv(key, raising=False)
    yield


@pytest.mark.asyncio
async def test_openai_success_gemini_not_called(monkeypatch):
    calls = []

    async def fake_invoke(provider, **kwargs):
        calls.append(provider)
        return '{"doc_type":"EICR","confidence":{"overall":0.9}}', 10, 20

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_API_KEY", "gem-test")
    monkeypatch.setattr(gw, "_invoke_provider", fake_invoke)

    out = await gw.complete_document_extraction_llm("sys", "user")
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
            raise RuntimeError("429 quota exceeded")
        return '{"doc_type":"GAS_SAFETY","confidence":{"overall":0.8}}', 5, 5

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_API_KEY", "gem-test")
    monkeypatch.setattr(gw, "_invoke_provider", fake_invoke)

    out = await gw.complete_document_extraction_llm("sys", "user")
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
            return "not json", 1, 1
        return '{"doc_type":"EPC","confidence":{"overall":0.7}}', 1, 1

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_API_KEY", "gem-test")
    monkeypatch.setattr(gw, "_invoke_provider", fake_invoke)

    out = await gw.complete_document_extraction_llm("sys", "user")
    assert out is not None
    assert out.provider_used == "gemini"
    assert calls == ["openai", "gemini"]


@pytest.mark.asyncio
async def test_no_keys_returns_none(monkeypatch):
    out = await gw.complete_document_extraction_llm("sys", "user")
    assert out is None


def test_user_message_hides_gemini_quota():
    msg = user_facing_extraction_message(
        "AI_ERROR",
        "429 quota exceeded for generativelanguage.googleapis.com",
    )
    assert "generativelanguage" not in msg
    assert "quota" not in msg.lower()
    assert "review manually" in msg.lower() or "unavailable" in msg.lower()


@pytest.mark.asyncio
async def test_support_gateway_module_untouched():
    """Support gateway remains importable (no accidental cross-module breakage)."""
    from services import support_llm_gateway

    assert hasattr(support_llm_gateway, "complete_support_planner")
