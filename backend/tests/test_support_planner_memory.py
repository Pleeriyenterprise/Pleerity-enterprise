"""Planner memory shaping for GPT-first support."""
from services.support_planner_memory import (
    apply_brain_turn_memory_update,
    build_planner_conversation_memory,
)


def test_memory_decay_trims_recent_entities():
    ctx = {
        "recent_entities": ["one", "two", "three", "four"],
        "active_topic": "pricing",
        "last_user_goal": "old goal",
    }
    mem = build_planner_conversation_memory(ctx)
    assert mem["recent_user_messages"] == ["three", "four"]
    assert len(mem["recent_user_messages"]) == 2


def test_handoff_pending_omits_stale_last_user_goal():
    ctx = {
        "recent_entities": ["what do I do"],
        "pending_handoff": True,
        "last_user_goal": "compare plans",
        "active_topic": "pricing",
    }
    mem = build_planner_conversation_memory(ctx)
    assert "last_user_goal" not in mem
    assert mem.get("operational_note")


def test_topic_switch_clears_handoff_carryover():
    ctx = {
        "active_topic": "pricing",
        "pending_handoff": True,
        "clarification_pending": True,
        "last_clarification_question": "Which plan?",
    }
    apply_brain_turn_memory_update(
        ctx,
        message="what is compliance vault",
        parsed={"topic": "compliance", "user_goal": "learn about cvp"},
    )
    assert ctx["active_topic"] == "compliance"
    assert ctx["pending_handoff"] is False
    assert ctx["clarification_pending"] is False
