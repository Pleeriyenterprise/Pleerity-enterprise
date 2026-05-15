"""
Lightweight conversation memory shaping for the GPT-first support planner.

Not routing — only trims stale hints passed into the planner payload.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def build_planner_conversation_memory(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Session hints for the planner. Deliberately shallow — user_message wins on conflict.
    """
    recent = ctx.get("recent_entities") or []
    if not isinstance(recent, list):
        recent = []
    # Stale context decay: only the last two user lines, not full session history.
    recent_trimmed = [str(m)[:400] for m in recent[-2:]]

    clar_pending = bool(ctx.get("clarification_pending") or ctx.get("pending_clarification"))
    handoff_pending = bool(ctx.get("pending_handoff"))

    memory: Dict[str, Any] = {
        "active_topic": ctx.get("active_topic"),
        "last_support_area": ctx.get("last_support_area"),
        "recent_user_messages": recent_trimmed,
        "weighting_note": (
            "Weak hints only. Latest user_message overrides these fields when the topic changed, "
            "the user corrected you, or conversation_state shows handoff/ticket follow-up."
        ),
    }

    if clar_pending:
        memory["last_clarification_question"] = ctx.get("last_clarification_question")
        memory["clarification_pending"] = True
    else:
        memory["clarification_pending"] = False

    # Reduce stale operational carryover: omit last_user_goal when handoff UI is active.
    if not handoff_pending:
        memory["last_user_goal"] = ctx.get("last_user_goal")

    if handoff_pending:
        memory["operational_note"] = (
            "Handoff or ticket step may be active — do not reuse old pricing or plan thread "
            "unless the user_message asks about plans."
        )

    return memory


def apply_brain_turn_memory_update(
    ctx: Dict[str, Any],
    *,
    message: str,
    parsed: Dict[str, Any],
) -> None:
    """Update session ctx after a successful brain turn (no new routers)."""
    from services.support_conversational_orchestrator import (
        clear_handoff_pending,
        mark_handoff_offered,
        touch_session_memory,
    )

    touch_session_memory(message, ctx)

    prior_topic = (ctx.get("active_topic") or "").strip().lower()
    new_topic = (parsed.get("topic") or "").strip().lower()

    if parsed.get("user_goal"):
        ctx["last_user_goal"] = parsed["user_goal"][:280]
    if new_topic:
        ctx["active_topic"] = new_topic[:80]
        ctx["last_support_area"] = new_topic[:80]

    # Topic switch / interruption: drop stale clarification and handoff carryover.
    if new_topic and prior_topic and new_topic != prior_topic:
        ctx["clarification_pending"] = False
        ctx["pending_clarification"] = False
        ctx["last_clarification_question"] = None
        if new_topic not in ("handoff",):
            clear_handoff_pending(ctx)

    if parsed.get("needs_clarification") and parsed.get("clarification_question"):
        ctx["last_clarification_question"] = parsed["clarification_question"][:400]
        ctx["clarification_pending"] = True
        ctx["pending_clarification"] = True
        ctx["last_assistant_action_type"] = "clarification"
    else:
        ctx["clarification_pending"] = False
        ctx["pending_clarification"] = False

    if parsed.get("escalation_suggested") or new_topic == "handoff":
        mark_handoff_offered(ctx)
        ctx["last_assistant_action_type"] = "handoff_suggested"
    elif ctx.get("last_assistant_action_type") != "handoff_offered":
        ctx["last_assistant_action_type"] = "support_ai_reply"

    ctx["last_action"] = "support_ai_brain"
