"""
Conversational-first stage for public support (anonymous web widget).

Runs before router_turn: light memory, vague help starters, retrieval hits with
optional LLM-grounded synthesis. Does not replace legal checks, tickets,
escalation, or deterministic operational tools (those follow in support_chatbot / router).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_GENERAL_HELP = re.compile(
    r"^(i\s+need\s+help|i\s+need\s+assistance|help\s*!*|can\s+you\s+help|"
    r"i'?m\s+stuck|i\s+am\s+stuck|need\s+support|support\s+please)\s*[\s!.?]*$",
    re.I,
)


def ensure_conversation_memory_defaults(ctx: Dict[str, Any]) -> None:
    """Lightweight session fields (client round-trips conversation_context)."""
    ctx.setdefault("active_topic", None)
    ctx.setdefault("last_user_goal", None)
    ctx.setdefault("last_support_area", None)
    ctx.setdefault("recent_entities", [])
    ctx.setdefault("escalation_context", None)
    ctx.setdefault("last_clarification_question", None)
    ctx.setdefault("clarification_pending", False)


def touch_session_memory(message: str, ctx: Dict[str, Any]) -> None:
    """Append recent user text for continuity (bounded list, no PII parsing)."""
    ensure_conversation_memory_defaults(ctx)
    msg = (message or "").strip()
    if not msg or len(msg) > 600:
        return
    recent = ctx["recent_entities"]
    if not isinstance(recent, list):
        ctx["recent_entities"] = []
        recent = ctx["recent_entities"]
    if recent and recent[-1] == msg:
        return
    recent.append(msg[:400])
    while len(recent) > 6:
        recent.pop(0)
    ctx["last_user_goal"] = msg[:280]


def try_generalist_help_starter(message: str, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Very short generic help requests → natural reply without menus/cards.
    Skips when we already have an active conversational topic (avoid nagging).
    """
    raw = (message or "").strip()
    if not raw or len(raw) > 90:
        return None
    if not _GENERAL_HELP.match(raw):
        return None
    if ctx.get("active_topic"):
        return {
            "response": (
                "What part should we dig into next? If it’s billing, login, orders, or a "
                "compliance feature, say which one."
            ),
            "action": "respond",
            "metadata": {"conversational_first": True, "service_area": "other", "category": "other"},
            "conversation_context": ctx,
        }
    return {
        "response": (
            "Of course — what are you stuck on? A few words is enough "
            "(for example billing, login, an order, or a compliance feature)."
        ),
        "action": "respond",
        "metadata": {"conversational_first": True, "service_area": "other", "category": "other"},
        "conversation_context": ctx,
    }


async def _maybe_llm_synthesize_answer(
    user_message: str,
    synthesis_rows: List[Dict[str, str]],
    *,
    retrieval_path: List[str],
) -> Optional[str]:
    """Grounded paraphrase; returns None to keep templated gist."""
    if not synthesis_rows:
        return None
    try:
        from utils.llm_chat import chat, _get_api_key

        if not _get_api_key():
            return None
    except Exception:
        return None

    ctx_lines: List[str] = []
    for i, row in enumerate(synthesis_rows[:2], 1):
        title = (row.get("title") or "Untitled").strip()
        excerpt = (row.get("excerpt") or "").strip()
        if not excerpt:
            continue
        ctx_lines.append(f"[{i}] {title}\n{excerpt[:3500]}")
    if not ctx_lines:
        return None
    ctx_block = "\n\n".join(ctx_lines)[:12000]
    path_hint = retrieval_path[0] if retrieval_path else "help content"
    system = (
        "You are a careful public support assistant for a UK property/compliance software platform.\n"
        "Write 2–4 short sentences answering the user's latest message.\n"
        "Rules:\n"
        "- Use ONLY the CONTEXT for factual claims. If the context does not contain the answer, say so briefly.\n"
        "- Never invent prices, fees, discounts, legal outcomes, or guarantees.\n"
        "- Do not use markdown heading syntax (no lines starting with #).\n"
        "- Avoid repeating the company name; prefer 'we' or neutral wording.\n"
        "- Do not paste bullet lists from the context; paraphrase in flowing prose.\n"
        f"- Source type for this turn: {path_hint}.\n"
    )
    user_block = f"CONTEXT:\n{ctx_block}\n\nUSER MESSAGE:\n{user_message.strip()[:2000]}"
    try:
        out = await chat(system, user_block, model="gemini-2.0-flash")
        text = (out or "").strip()
        if len(text) < 32:
            return None
        return text
    except Exception as e:
        logger.warning("conversational_orchestrator: synthesis LLM failed: %s", e)
        return None


async def run_conversational_first_turn(
    *,
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    ctx: Dict[str, Any],
    is_authenticated: bool,
    client_context: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Public-path conversational layer before router_turn.

    Returns a handler dict to short-circuit the pipeline, or None to continue
    with router_turn and existing guided/retrieval/LLM stages.
    """
    ensure_conversation_memory_defaults(ctx)
    touch_session_memory(message, ctx)

    # Portal sessions keep existing tool-first ordering after this stage.
    if is_authenticated:
        return None

    starter = try_generalist_help_starter(message, ctx)
    if starter:
        return starter

    from services.support_chatbot import defer_public_kb_for_operational_routing

    if defer_public_kb_for_operational_routing(message, ctx):
        return None

    try:
        from services.support_public_content_retrieval import try_public_support_content_answer

        pub = await try_public_support_content_answer(message, ctx)
    except Exception as e:
        logger.warning("conversational_orchestrator: retrieval failed: %s", e)
        return None

    if not pub:
        return None

    meta = dict(pub.get("metadata") or {})
    rows = meta.get("_synthesis_context")
    retrieval_path = list(meta.get("retrieval_path") or [])
    if isinstance(rows, list) and rows:
        synthesized = await _maybe_llm_synthesize_answer(
            message,
            [r for r in rows if isinstance(r, dict)],
            retrieval_path=retrieval_path,
        )
        if synthesized:
            rp0 = retrieval_path[0] if retrieval_path else ""
            if rp0 == "site_page":
                footer = "\n\n_From website content._"
            else:
                footer = "\n\n_From Knowledge Centre._"
            pub["response"] = synthesized.strip() + footer
            meta["conversational_synthesis"] = "llm_grounded"
    meta.pop("_synthesis_context", None)
    pub["metadata"] = meta

    ctx["last_action"] = "public_content_index"
    if retrieval_path:
        ctx["active_topic"] = retrieval_path[0]
        ctx["last_support_area"] = retrieval_path[0]
    return pub
