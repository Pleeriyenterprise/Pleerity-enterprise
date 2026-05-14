"""Conversational-first orchestration (public support) — unit tests."""
import pytest

from services.support_conversational_orchestrator import (
    ensure_conversation_memory_defaults,
    try_generalist_help_starter,
    touch_session_memory,
)
from services.support_chatbot import (
    defer_public_kb_for_operational_routing,
    is_informational_public_support_query,
    is_legal_advice_request,
)


def test_ensure_conversation_memory_defaults():
    ctx = {}
    ensure_conversation_memory_defaults(ctx)
    assert ctx["active_topic"] is None
    assert ctx["last_user_goal"] is None
    assert ctx["recent_entities"] == []


def test_touch_session_memory_rounds_recent():
    ctx = {}
    touch_session_memory("first question", ctx)
    touch_session_memory("second question", ctx)
    assert len(ctx["recent_entities"]) == 2
    assert ctx["last_user_goal"] == "second question"


def test_generalist_help_starter_natural():
    ctx = {}
    out = try_generalist_help_starter("I need help", ctx)
    assert out is not None
    assert "pleerity" not in out["response"].lower()
    assert out["metadata"].get("conversational_first") is True


def test_generalist_help_with_active_topic_follow_up():
    ctx = {"active_topic": "kc_article"}
    out = try_generalist_help_starter("help", ctx)
    assert out is not None
    assert "dig into" in out["response"].lower() or "next" in out["response"].lower()


@pytest.mark.asyncio
async def test_conversational_first_turn_skips_when_authenticated():
    from services.support_conversational_orchestrator import run_conversational_first_turn

    out = await run_conversational_first_turn(
        conversation_id="CONV-x",
        message="How do I upload evidence?",
        conversation_history=[],
        ctx={},
        is_authenticated=True,
        client_context={"crn": "X"},
    )
    assert out is None


@pytest.mark.asyncio
async def test_conversational_first_turn_defers_pricing(monkeypatch):
    from services.support_conversational_orchestrator import run_conversational_first_turn

    async def no_pub(*a, **k):
        raise AssertionError("retrieval should not run when deferring pricing")

    monkeypatch.setattr(
        "services.support_public_content_retrieval.try_public_support_content_answer",
        no_pub,
    )
    out = await run_conversational_first_turn(
        conversation_id="CONV-x",
        message="How much does CVP cost per month?",
        conversation_history=[],
        ctx={},
        is_authenticated=False,
        client_context=None,
    )
    assert out is None


@pytest.mark.asyncio
async def test_conversational_first_turn_strips_synthesis_context(monkeypatch):
    from services.support_conversational_orchestrator import run_conversational_first_turn

    monkeypatch.setattr(
        "services.support_chatbot.defer_public_kb_for_operational_routing",
        lambda _m, _c: False,
    )

    async def fake_pub(message, ctx):
        return {
            "response": "stub",
            "action": "respond",
            "metadata": {
                "kc_article_matched": True,
                "public_content_retrieval": True,
                "conversational_synthesis": True,
                "sources": [],
                "retrieval_path": ["kc_article"],
                "_synthesis_context": [{"title": "T", "excerpt": "body text " * 20}],
            },
            "conversation_context": ctx,
            "actions": None,
        }

    monkeypatch.setattr(
        "services.support_public_content_retrieval.try_public_support_content_answer",
        fake_pub,
    )
    async def _stub_synth(*a, **k):
        return None

    monkeypatch.setattr(
        "services.support_conversational_orchestrator._maybe_llm_synthesize_answer",
        _stub_synth,
    )
    out = await run_conversational_first_turn(
        conversation_id="CONV-x",
        message="What documents count toward my compliance score?",
        conversation_history=[],
        ctx={},
        is_authenticated=False,
        client_context=None,
    )
    assert out is not None
    assert "_synthesis_context" not in (out.get("metadata") or {})


def test_informational_compliance_score_allows_kb_before_router():
    assert is_informational_public_support_query("How do I understand my compliance score?")
    assert not defer_public_kb_for_operational_routing(
        "How do I understand my compliance score?",
        {},
    )


def test_whats_my_compliance_score_still_operational():
    assert not is_informational_public_support_query("What's my compliance score?")
    assert defer_public_kb_for_operational_routing("What's my compliance score?", {})


def test_forgot_password_still_defers_kb():
    assert defer_public_kb_for_operational_routing("I forgot my password", {})


@pytest.mark.asyncio
async def test_router_turn_skips_ask_verify_for_informational_compliance():
    from services.support_assistant_orchestrator import router_turn

    out = await router_turn(
        conversation_id="conv-test",
        message="How do I understand my compliance score?",
        conversation_history=[],
        ctx={},
        is_authenticated=False,
        client_context=None,
    )
    assert out is None


def test_legal_refusal_precedes_conversational_layer_contract():
    """Legal guard stays in support_chatbot before orchestrator; contract test only."""
    assert is_legal_advice_request("Can I evict a tenant who has not paid rent?")
