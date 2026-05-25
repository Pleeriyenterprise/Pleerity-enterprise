"""
AI-first public support brain (feature-flagged via SUPPORT_GPT_FIRST_ENABLED).

Orchestration when enabled (anonymous widget):
  legal refusal (caller) -> protected deterministic shortcuts -> AI brain -> legacy fallback

Does not replace tickets, admin tools, indexing, audit, or rate limits.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from services.support_ai_instructions import (
    build_full_planner_system_prompt,
    build_planner_user_payload,
)

logger = logging.getLogger(__name__)

ALLOWED_ACTION_IDS = frozenset(
    {
        "view_pricing",
        "create_account",
        "check_compliance_risk",
        "sign_in",
        "reset_password",
        "create_ticket",
        "talk_to_support",
        "open_help_article",
        "open_compliance_vault",
        "open_services",
        # legacy aliases mapped in action mapper
        "pricing",
        "services",
        "compliance_vault",
        "dashboard",
    }
)


def support_ai_brain_enabled() -> bool:
    v = (os.environ.get("SUPPORT_GPT_FIRST_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


# Back-compat alias
support_gpt_first_enabled = support_ai_brain_enabled


def _compact_history(history: List[Dict[str, Any]], max_messages: int = 12) -> str:
    lines: List[str] = []
    for msg in (history or [])[-max_messages:]:
        s = (msg.get("sender") or "").lower()
        role = "user" if s == "user" else "assistant"
        t = (msg.get("message_text") or "").strip()
        if not t:
            continue
        lines.append(f"{role}: {t[:900]}")
    return "\n".join(lines) if lines else "(no prior messages in this thread)"


def _extract_json_object(raw: str) -> Optional[Dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _normalize_brain_payload(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(data, dict):
        return None
    reply = (data.get("reply_text") or "").strip()
    if len(reply) < 8:
        return None
    try:
        conf = float(data.get("confidence", 0.7))
    except (TypeError, ValueError):
        conf = 0.7
    conf = max(0.0, min(1.0, conf))

    show_actions = bool(data.get("show_actions", data.get("should_show_actions")))
    actions_raw = data.get("actions")
    action_ids: List[str] = []
    if isinstance(actions_raw, list):
        for a in actions_raw:
            if isinstance(a, str) and a in ALLOWED_ACTION_IDS:
                action_ids.append(a)
            elif isinstance(a, dict):
                aid = (a.get("id") or a.get("action_id") or "").strip()
                if aid in ALLOWED_ACTION_IDS:
                    action_ids.append(aid)

    needs_clar = bool(data.get("needs_clarification"))
    clar_q = (data.get("clarification_question") or "").strip()[:500]
    esc = bool(data.get("escalation_suggested", data.get("escalation_recommended")))
    boundary = (data.get("safety_boundary") or "none").strip()[:80]
    intent_summary = (data.get("intent_summary") or "general_support")[:200]
    user_goal = (data.get("user_goal") or "")[:280]
    topic = (data.get("topic") or "")[:80]

    sources_used = data.get("sources_used")
    if not isinstance(sources_used, list):
        sources_used = []
    clean_sources: List[Dict[str, str]] = []
    for s in sources_used[:12]:
        if isinstance(s, dict):
            clean_sources.append(
                {
                    "type": str(s.get("type") or "unknown")[:40],
                    "title": str(s.get("title") or "")[:200],
                }
            )

    return {
        "reply_text": reply[:12000],
        "intent_summary": intent_summary,
        "user_goal": user_goal,
        "topic": topic,
        "confidence": conf,
        "show_actions": show_actions and bool(action_ids),
        "action_ids": action_ids[:6],
        "needs_clarification": needs_clar,
        "clarification_question": clar_q,
        "escalation_suggested": esc,
        "safety_boundary": boundary or "none",
        "sources_used": clean_sources,
    }


def _map_action_ids_to_buttons(
    action_ids: List[str],
    links: Dict[str, Any],
    *,
    article_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    from services.support_chatbot import _chatbot_app_base

    base = _chatbot_app_base().rstrip("/")
    out: List[Dict[str, Any]] = []
    seen: set = set()

    def add(label: str, url: Optional[str]) -> None:
        key = (label, url)
        if key in seen:
            return
        seen.add(key)
        out.append({"label": label, "url": url})

    for aid in action_ids:
        if aid in ("view_pricing", "pricing"):
            add("View pricing", links.get("pricing"))
        elif aid in ("open_services", "services"):
            add("Services", links.get("services"))
        elif aid in ("open_compliance_vault", "compliance_vault"):
            add("Compliance Vault Pro", links.get("compliance_vault_landing"))
        elif aid == "check_compliance_risk":
            add("Free risk check", links.get("risk_check") or f"{base}/risk-check")
        elif aid in ("sign_in", "create_account"):
            add("Sign in", links.get("client_signin") or f"{base}/login/client")
        elif aid == "reset_password":
            add("Sign in", links.get("client_signin") or f"{base}/login/client")
        elif aid in ("talk_to_support", "create_ticket"):
            add("Talk to support", None)
        elif aid == "open_help_article" and article_url:
            add("Read full article", article_url)
        elif aid == "dashboard":
            add("Dashboard", links.get("dashboard"))
    return out


def _default_signin_support_actions() -> List[Dict[str, Any]]:
    from services.support_chatbot import _chatbot_app_base

    base = _chatbot_app_base().rstrip("/")
    return [
        {"label": "Sign in", "url": f"{base}/login/client"},
        {"label": "Talk to support", "url": None},
    ]


async def try_protected_deterministic_shortcuts(
    *,
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    ctx: Dict[str, Any],
    client_context: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Protected operations that bypass the AI brain."""
    from services.support_assistant_intent import SupportAssistantIntent, classify_support_intent
    from services.support_assistant_tools import (
        ASK_ORDER_VERIFY,
        extract_verification_tokens,
        format_tool_answer_account_overview,
        format_tool_answer_order,
        get_billing_subscription_snapshot,
        get_onboarding_snapshot_for_verified_client,
        list_recent_checkout_receipt_summaries,
        lookup_order_for_email,
        resolve_client_by_crn_email,
    )
    from services.support_chatbot import (
        _standard_handoff_response_dict,
        detect_category,
        detect_service_area,
        detect_urgency,
        get_canned_response,
        needs_human_handoff,
    )

    text = (message or "").strip()
    if not text:
        return None

    if needs_human_handoff(text):
        from services.support_conversational_orchestrator import mark_handoff_offered

        mark_handoff_offered(ctx)
        return _standard_handoff_response_dict(
            conversation_id=conversation_id,
            message=text,
            conversation_history=conversation_history,
            ctx=ctx,
            service_area=detect_service_area(text),
            category=detect_category(text),
            urgency=detect_urgency(text),
            metadata_extra={"ai_brain_shortcut": "human_handoff"},
        )

    ri, conf = classify_support_intent(text, ctx)
    if ri == SupportAssistantIntent.PASSWORD_LOGIN and conf >= 0.99:
        canned = get_canned_response("reset_password")
        if canned:
            out = dict(canned)
            out["conversation_context"] = ctx
            meta = dict(out.get("metadata") or {})
            meta["ai_brain_shortcut"] = "password_reset"
            out["metadata"] = meta
            return out

    tok = extract_verification_tokens(text)
    text_l = text.lower()
    explicit_order_question = bool(tok.get("order_ref")) or any(
        k in text_l
        for k in (
            "order status",
            "my order",
            "track order",
            "where is my order",
            "order reference",
            "order ref",
            "haven't received my",
            "not received my order",
        )
    )

    if tok.get("order_ref") and tok.get("email") and (
        ri in (SupportAssistantIntent.COMPLIANCE_CRN, SupportAssistantIntent.ACCOUNT_BILLING)
        or explicit_order_question
    ):
        status, data = await lookup_order_for_email(tok["order_ref"], tok["email"])
        if status == "not_found":
            return {
                "response": "We could not find an order with that reference. Check your confirmation email or use **Talk to support**.",
                "action": "respond",
                "metadata": {"ai_brain_shortcut": "order_lookup", "tool": "order_lookup", "result": "not_found"},
                "conversation_context": ctx,
                "actions": _default_signin_support_actions(),
            }
        if status == "email_mismatch":
            return {
                "response": "The email you gave does not match the one on that order. We can't show which email is correct. Try again or contact support.",
                "action": "respond",
                "metadata": {"ai_brain_shortcut": "order_lookup", "tool": "order_lookup", "result": "email_mismatch"},
                "conversation_context": ctx,
                "actions": _default_signin_support_actions(),
            }
        return {
            "response": format_tool_answer_order(data or {}),
            "action": "respond",
            "metadata": {"ai_brain_shortcut": "order_lookup", "tool": "order_lookup", "result": "ok"},
            "conversation_context": ctx,
            "actions": _default_signin_support_actions(),
        }

    if explicit_order_question and not (tok.get("order_ref") and tok.get("email")):
        return {
            "response": ASK_ORDER_VERIFY,
            "action": "respond",
            "metadata": {"ai_brain_shortcut": "order_lookup", "clarifying": True, "needs_verification": True},
            "conversation_context": ctx,
        }

    if tok.get("crn") and tok.get("email"):
        client = await resolve_client_by_crn_email(tok["crn"], tok["email"])
        if not client:
            return {
                "response": "We could not verify those details. Check your CRN and email, or use **Talk to support**.",
                "action": "respond",
                "metadata": {"ai_brain_shortcut": "verify_account", "tool": "verify_account", "result": "failed"},
                "conversation_context": ctx,
                "actions": _default_signin_support_actions(),
            }
        from services.support_assistant_catalog import build_approved_knowledge_dict

        approved = build_approved_knowledge_dict()
        links = approved.get("frontend_links") or {}
        snap = await get_onboarding_snapshot_for_verified_client(client)
        billing = await get_billing_subscription_snapshot(client["client_id"])
        receipts = await list_recent_checkout_receipt_summaries(client["client_id"])
        body = format_tool_answer_account_overview(snap, billing, receipts)
        return {
            "response": body,
            "action": "respond",
            "metadata": {
                "ai_brain_shortcut": "verified_account_snapshot",
                "tool": "verified_account_snapshot",
                "verified": True,
            },
            "conversation_context": ctx,
            "actions": [
                {"label": "Sign in to portal", "url": links.get("client_signin")},
                {"label": "Talk to support", "url": None},
            ],
        }

    return None


async def _gather_retrieval_context(
    message: str,
    ctx: Dict[str, Any],
) -> tuple[List[Dict[str, str]], List[Dict[str, Any]], List[str], Optional[str]]:
    """KC > site retrieval for brain grounding (always attempted)."""
    retrieval_chunks: List[Dict[str, str]] = []
    retrieval_meta_sources: List[Dict[str, Any]] = []
    retrieval_path: List[str] = []
    article_url: Optional[str] = None

    try:
        from services.support_public_content_retrieval import try_public_support_content_answer
        from utils.app_urls import get_app_base_url

        pub = await try_public_support_content_answer(message, ctx)
    except Exception as e:
        logger.warning("support_ai_brain: retrieval failed: %s", e)
        return retrieval_chunks, retrieval_meta_sources, retrieval_path, article_url

    if not pub:
        return retrieval_chunks, retrieval_meta_sources, retrieval_path, article_url

    meta = dict(pub.get("metadata") or {})
    retrieval_path = list(meta.get("retrieval_path") or [])
    synthesis_rows = meta.get("_synthesis_context")
    if isinstance(synthesis_rows, list):
        for row in synthesis_rows[:4]:
            if isinstance(row, dict):
                retrieval_chunks.append(
                    {
                        "title": (row.get("title") or "")[:200],
                        "excerpt": (row.get("excerpt") or "")[:3500],
                    }
                )
    for s in meta.get("sources") or []:
        if isinstance(s, dict):
            retrieval_meta_sources.append(s)
            if not article_url and s.get("source_type") == "kb_article" and s.get("slug"):
                base = get_app_base_url(for_email_links=True).rstrip("/")
                article_url = f"{base}/support/knowledge-base/{s['slug']}"
    return retrieval_chunks, retrieval_meta_sources, retrieval_path, article_url


def _update_session_memory_from_brain(ctx: Dict[str, Any], parsed: Dict[str, Any], message: str) -> None:
    from services.support_planner_memory import apply_brain_turn_memory_update

    apply_brain_turn_memory_update(ctx, message=message, parsed=parsed)


async def run_support_ai_brain_turn(
    *,
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    ctx: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Primary AI orchestrator for anonymous public chat when flag is on.
    Returns handler dict or None for legacy fallback.
    """
    if not support_ai_brain_enabled():
        return None

    from services.support_llm_gateway import complete_support_planner, is_any_support_llm_configured

    if not is_any_support_llm_configured():
        return None

    from services.support_assistant_catalog import build_approved_knowledge_dict, format_pricing_paragraph_for_prompt
    from services.support_assistant_plan_features import (
        build_cvp_plan_features_for_support,
        format_plan_features_for_prompt,
    )
    from services.support_chatbot import build_public_handoff_options
    from services.support_conversational_orchestrator import ensure_conversation_memory_defaults

    ensure_conversation_memory_defaults(ctx)
    text = (message or "").strip()
    approved = build_approved_knowledge_dict()
    links = approved.get("frontend_links") or {}
    registry_facts = (format_pricing_paragraph_for_prompt(approved) or "")[:9000]
    plan_feature_facts = format_plan_features_for_prompt(build_cvp_plan_features_for_support())
    policies = approved.get("policies") or {}

    retrieval_chunks, retrieval_meta_sources, retrieval_path, article_url = await _gather_retrieval_context(
        text, ctx
    )

    ho = build_public_handoff_options(
        conversation_id=conversation_id,
        crn=None,
        message_snippet=text[:200],
        transcript_summary=f"{len(conversation_history)} messages in conversation",
    )
    lc = ho.get("live_chat") or {}
    wa = ho.get("whatsapp") or {}
    handoff_channels = {
        "live_chat_configured": bool(lc.get("configured")),
        "live_chat_enabled": bool(lc.get("enabled", True)),
        "live_chat_available_now": bool(lc.get("available")),
        "email_ticket_available": bool(ho.get("email_ticket", {}).get("available", True)),
        "whatsapp_configured": bool(wa.get("available")),
        "whatsapp_is_deeplink_only": True,
    }

    from services.support_planner_memory import build_planner_conversation_memory

    memory = build_planner_conversation_memory(ctx)
    conversation_state = {
        "last_assistant_action_type": ctx.get("last_assistant_action_type"),
        "pending_handoff": bool(ctx.get("pending_handoff")),
        "pending_ticket_flow": bool(ctx.get("pending_ticket_flow")),
        "pending_clarification": bool(ctx.get("pending_clarification") or ctx.get("clarification_pending")),
        "note": (
            "If pending_handoff and the user asks what to do / how this works / which option, "
            "explain handoff channels — not prior pricing or plan topics."
        ),
    }

    allowed = sorted(ALLOWED_ACTION_IDS)
    system = build_full_planner_system_prompt(allowed)
    user_blob = build_planner_user_payload(
        user_message=text,
        conversation_memory=memory,
        conversation_state=conversation_state,
        retrieval_chunks=retrieval_chunks,
        registry_facts=registry_facts,
        plan_feature_facts=plan_feature_facts,
        policy_snippets={
            "no_legal_advice": policies.get("no_legal_advice", ""),
            "password_reset": policies.get("password_reset", ""),
            "order_status": policies.get("order_status", ""),
        },
        handoff_channels=handoff_channels,
        recent_transcript=_compact_history(conversation_history),
        allowed_action_ids=allowed,
    )

    def _planner_output_valid(raw: str) -> bool:
        return _normalize_brain_payload(_extract_json_object(raw) or {}) is not None

    llm_result = await complete_support_planner(
        system,
        user_blob,
        validate_output=_planner_output_valid,
    )
    if not llm_result:
        return None

    parsed = _normalize_brain_payload(_extract_json_object(llm_result.text) or {})
    if not parsed:
        return None

    if parsed.get("safety_boundary") == "legal":
        from services.support_chatbot import LEGAL_REFUSAL_RESPONSE

        return {
            "response": LEGAL_REFUSAL_RESPONSE,
            "action": "respond",
            "metadata": {"legal_refusal": True, "support_ai_brain": True, "safety_boundary": "legal"},
            "conversation_context": ctx,
        }

    reply = parsed["reply_text"]

    actions_out: Optional[List[Dict[str, Any]]] = None
    if parsed["show_actions"] and parsed["action_ids"]:
        actions_out = _map_action_ids_to_buttons(
            parsed["action_ids"], links, article_url=article_url
        )

    _update_session_memory_from_brain(ctx, parsed, text)

    meta_sources = list(retrieval_meta_sources)
    for su in parsed.get("sources_used") or []:
        if isinstance(su, dict) and su.get("title"):
            meta_sources.append({"source_type": su.get("type") or "brain", "title": su.get("title")})

    metadata: Dict[str, Any] = {
        "support_ai_brain": True,
        "intent_summary": parsed["intent_summary"],
        "user_goal": parsed.get("user_goal"),
        "topic": parsed.get("topic"),
        "confidence": parsed["confidence"],
        "show_actions": parsed["show_actions"],
        "needs_clarification": parsed["needs_clarification"],
        "escalation_suggested": parsed["escalation_suggested"],
        "safety_boundary": parsed["safety_boundary"],
        "sources": meta_sources[:20],
        "sources_used": parsed["sources_used"],
        "retrieval_path": retrieval_path or ["support_ai_brain"],
        "provider_used": llm_result.provider_used,
        "model_used": llm_result.model_used,
        "fallback_used": llm_result.fallback_used,
        "llm_latency_ms": llm_result.llm_latency_ms,
    }
    if llm_result.llm_error_class:
        metadata["llm_error_class"] = llm_result.llm_error_class
    if parsed.get("escalation_suggested"):
        metadata["suggested_handoff"] = True

    return {
        "response": reply,
        "action": "respond",
        "metadata": metadata,
        "conversation_context": ctx,
        "actions": actions_out,
    }


async def run_public_support_ai_brain(
    *,
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    ctx: Dict[str, Any],
    client_context: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Full AI-first path: protected shortcuts, then brain.
    Returns None to signal legacy fallback.
    """
    from services.support_conversation_recovery import try_frustration_recovery_turn

    recovery = try_frustration_recovery_turn(message, ctx, conversation_history)
    if recovery:
        return recovery

    shortcut = await try_protected_deterministic_shortcuts(
        conversation_id=conversation_id,
        message=message,
        conversation_history=conversation_history,
        ctx=ctx,
        client_context=client_context,
    )
    if shortcut:
        return shortcut
    return await run_support_ai_brain_turn(
        conversation_id=conversation_id,
        message=message,
        conversation_history=conversation_history,
        ctx=ctx,
    )
