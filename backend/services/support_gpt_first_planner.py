"""
GPT-first public support planner (feature-flagged).

When SUPPORT_GPT_FIRST_ENABLED is true (anonymous widget only), the LLM plans a
single grounded reply from KC/site excerpts + registry facts + handoff facts.
Deterministic shortcuts (legal handled upstream, handoff, password, verified
order/CRN) bypass the planner.

Falls back to the legacy pipeline if the planner returns nothing or errors.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ALLOWED_ACTION_IDS = frozenset(
    {"sign_in", "pricing", "services", "compliance_vault", "dashboard", "talk_to_support"}
)


def _default_signin_support_actions() -> List[Dict[str, Any]]:
    from services.support_chatbot import _chatbot_app_base

    base = _chatbot_app_base().rstrip("/")
    return [
        {"label": "Sign in", "url": f"{base}/login/client"},
        {"label": "Talk to support", "url": None},
    ]


def support_gpt_first_enabled() -> bool:
    v = (os.environ.get("SUPPORT_GPT_FIRST_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


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


def _normalize_planner_payload(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
    should_act = bool(data.get("should_show_actions"))
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
    intent_summary = (data.get("intent_summary") or "general_support")[:200]
    needs_clar = bool(data.get("needs_clarification"))
    clar_q = (data.get("clarification_question") or "").strip()[:500]
    esc = bool(data.get("escalation_recommended"))
    boundary = (data.get("safety_boundary") or "none").strip()[:80]
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
        "confidence": conf,
        "should_show_actions": should_act and bool(action_ids),
        "action_ids": action_ids[:6],
        "needs_clarification": needs_clar,
        "clarification_question": clar_q,
        "escalation_recommended": esc,
        "safety_boundary": boundary or "none",
        "sources_used": clean_sources,
    }


def _map_action_ids_to_buttons(action_ids: List[str], links: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for aid in action_ids:
        if aid == "sign_in":
            url = links.get("client_signin")
            if url:
                out.append({"label": "Sign in", "url": url})
        elif aid == "pricing":
            url = links.get("pricing")
            if url:
                out.append({"label": "Pricing", "url": url})
        elif aid == "services":
            url = links.get("services")
            if url:
                out.append({"label": "Services", "url": url})
        elif aid == "compliance_vault":
            url = links.get("compliance_vault_landing")
            if url:
                out.append({"label": "Compliance Vault Pro", "url": url})
        elif aid == "dashboard":
            url = links.get("dashboard")
            if url:
                out.append({"label": "Dashboard", "url": url})
        elif aid == "talk_to_support":
            out.append({"label": "Talk to support", "url": None})
    return out


async def try_gpt_first_deterministic_shortcuts(
    *,
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    ctx: Dict[str, Any],
    client_context: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Deterministic paths that must bypass GPT-first planning.
    Mirrors router priorities for handoff, password, verified order/CRN.
    """
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
        service_area = detect_service_area(text)
        category = detect_category(text)
        urgency = detect_urgency(text)
        return _standard_handoff_response_dict(
            conversation_id=conversation_id,
            message=text,
            conversation_history=conversation_history,
            ctx=ctx,
            service_area=service_area,
            category=category,
            urgency=urgency,
            metadata_extra={"gpt_first_shortcut": "human_handoff"},
        )

    ri, conf = classify_support_intent(text, ctx)
    if ri == SupportAssistantIntent.PASSWORD_LOGIN and conf >= 0.99:
        canned = get_canned_response("reset_password")
        if canned:
            out = dict(canned)
            out["conversation_context"] = ctx
            meta = dict(out.get("metadata") or {})
            meta["gpt_first_shortcut"] = "password_reset"
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
                "metadata": {"gpt_first_shortcut": "order_lookup", "tool": "order_lookup", "result": "not_found"},
                "conversation_context": ctx,
                "actions": _default_signin_support_actions(),
            }
        if status == "email_mismatch":
            return {
                "response": "The email you gave does not match the one on that order. We can't show which email is correct. Try again or contact support.",
                "action": "respond",
                "metadata": {"gpt_first_shortcut": "order_lookup", "tool": "order_lookup", "result": "email_mismatch"},
                "conversation_context": ctx,
                "actions": _default_signin_support_actions(),
            }
        return {
            "response": format_tool_answer_order(data or {}),
            "action": "respond",
            "metadata": {"gpt_first_shortcut": "order_lookup", "tool": "order_lookup", "result": "ok"},
            "conversation_context": ctx,
            "actions": _default_signin_support_actions(),
        }

    if explicit_order_question and not (tok.get("order_ref") and tok.get("email")):
        return {
            "response": ASK_ORDER_VERIFY,
            "action": "respond",
            "metadata": {"gpt_first_shortcut": "order_lookup", "clarifying": True, "needs_verification": True},
            "conversation_context": ctx,
        }

    if tok.get("crn") and tok.get("email"):
        client = await resolve_client_by_crn_email(tok["crn"], tok["email"])
        if not client:
            return {
                "response": "We could not verify those details. Check your CRN and email, or use **Talk to support**.",
                "action": "respond",
                "metadata": {"gpt_first_shortcut": "verify_account", "tool": "verify_account", "result": "failed"},
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
                "gpt_first_shortcut": "verified_account_snapshot",
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


async def run_gpt_first_public_turn(
    *,
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    ctx: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Single LLM planning call with KC/site + registry grounding.
    Returns a handler dict or None to fall back to legacy orchestration.
    """
    if not support_gpt_first_enabled():
        return None

    try:
        from utils.llm_chat import chat, _get_api_key
    except Exception:
        return None
    if not _get_api_key():
        return None

    from services.support_assistant_catalog import build_approved_knowledge_dict, format_pricing_paragraph_for_prompt
    from services.support_chatbot import defer_public_kb_for_operational_routing

    text = (message or "").strip()
    approved = build_approved_knowledge_dict()
    links = approved.get("frontend_links") or {}
    registry_facts = (format_pricing_paragraph_for_prompt(approved) or "")[:9000]
    policies = approved.get("policies") or {}

    defer = defer_public_kb_for_operational_routing(text, ctx)
    retrieval_chunks: List[Dict[str, str]] = []
    retrieval_meta_sources: List[Dict[str, Any]] = []
    retrieval_path: List[str] = []

    if not defer:
        try:
            from services.support_public_content_retrieval import try_public_support_content_answer

            pub = await try_public_support_content_answer(text, ctx)
        except Exception as e:
            logger.warning("gpt_first: retrieval failed: %s", e)
            pub = None
        if pub:
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
    else:
        retrieval_path = ["deferred_operational_keywords"]

    ho = None
    try:
        from services.support_chatbot import build_public_handoff_options

        ho = build_public_handoff_options(
            conversation_id=conversation_id,
            crn=None,
            message_snippet=text[:200],
            transcript_summary=f"{len(conversation_history)} messages in conversation",
        )
    except Exception as e:
        logger.warning("gpt_first: handoff options build failed: %s", e)

    lc = (ho or {}).get("live_chat") or {}
    wa = (ho or {}).get("whatsapp") or {}
    handoff_channels = {
        "live_chat_configured": bool(lc.get("configured")),
        "live_chat_enabled": bool(lc.get("enabled", True)),
        "live_chat_available_now": bool(lc.get("available")),
        "email_ticket_available": bool((ho or {}).get("email_ticket", {}).get("available", True)),
        "whatsapp_configured": bool(wa.get("available")),
        "whatsapp_is_deeplink_only": True,
        "do_not_claim_agents_online": True,
    }

    memory = {
        "active_topic": ctx.get("active_topic"),
        "last_user_goal": ctx.get("last_user_goal"),
        "last_support_area": ctx.get("last_support_area"),
        "last_clarification_question": ctx.get("last_clarification_question"),
        "recent_entities": (ctx.get("recent_entities") or [])[-4:],
    }

    allowed_ids = sorted(ALLOWED_ACTION_IDS)
    user_blob = json.dumps(
        {
            "user_message": text,
            "conversation_memory": memory,
            "retrieval_chunks": retrieval_chunks,
            "retrieval_deferred": defer,
            "registry_facts": registry_facts,
            "policy_snippets": {
                "no_legal_advice": policies.get("no_legal_advice", ""),
                "password_reset": policies.get("password_reset", ""),
                "order_status": policies.get("order_status", ""),
            },
            "handoff_channels": handoff_channels,
            "allowed_action_ids": allowed_ids,
            "recent_transcript": _compact_history(conversation_history),
        },
        ensure_ascii=False,
    )[:24000]

    system = """You are the planning layer for a UK property/compliance software public support assistant.
Output a single JSON object ONLY (no markdown outside the JSON) with exactly these keys:
- reply_text (string): natural, concise reply to the user. Do not paste long bullet lists from context; paraphrase. No markdown headings (#). Avoid repeating the company name.
- intent_summary (string): short internal label for logs.
- confidence (number 0-1): your confidence in the reply given the inputs.
- should_show_actions (boolean): true ONLY if the user clearly asked to do something next AND buttons would help (sign in, pricing page, services, CVP landing, dashboard, or talk to support). Default false.
- actions (array of strings): subset of allowed_action_ids; empty if should_show_actions is false.
- needs_clarification (boolean): true if one focused follow-up would materially help.
- clarification_question (string): empty unless needs_clarification is true; one short question only.
- escalation_recommended (boolean): true if a human may help next (do not fabricate availability).
- safety_boundary (string): one of none, legal, pricing, account_pii, live_agent_claims, whatsapp_scope.
- sources_used (array of objects with keys type, title): cite only topics you used from retrieval_chunks; empty if none.

Rules:
- Never give legal advice or guarantee compliance outcomes. If asked for law, refuse briefly and suggest a solicitor/council.
- Never invent prices: use only REGISTRY_FACTS for numeric pricing; if missing, say to open Pricing or sign in.
- Do not claim live chat agents are online; live_chat_available_now is informational only.
- WhatsApp is a deeplink handoff, not an in-app thread - do not imply full integration.
- If retrieval_chunks is empty, answer helpfully without fabricating article text; suggest sign in, pricing link, or support channels as appropriate.
- Keep reply_text under ~180 words unless the user asked for detail.
"""

    try:
        raw = await chat(system, user_blob, model="gemini-2.0-flash")
    except Exception as e:
        logger.warning("gpt_first: planner LLM failed: %s", e)
        return None

    parsed = _normalize_planner_payload(_extract_json_object(raw) or {})
    if not parsed:
        return None

    reply = parsed["reply_text"]
    if retrieval_chunks and retrieval_path and retrieval_path[0] not in ("deferred_operational_keywords",):
        rp0 = retrieval_path[0] if retrieval_path else ""
        if rp0 == "site_page":
            reply = reply.rstrip() + "\n\n_From website content._"
        elif rp0 == "kc_article":
            reply = reply.rstrip() + "\n\n_From Knowledge Centre._"

    actions_out: Optional[List[Dict[str, Any]]] = None
    if parsed["should_show_actions"] and parsed["action_ids"]:
        actions_out = _map_action_ids_to_buttons(parsed["action_ids"], links)

    if parsed.get("needs_clarification") and parsed.get("clarification_question"):
        ctx["last_clarification_question"] = parsed["clarification_question"][:400]
    ctx["last_action"] = "gpt_first_planner"
    if retrieval_path and retrieval_path[0] != "deferred_operational_keywords":
        ctx["active_topic"] = retrieval_path[0]
        ctx["last_support_area"] = retrieval_path[0]

    meta_sources = list(retrieval_meta_sources)
    for su in parsed.get("sources_used") or []:
        if isinstance(su, dict) and su.get("title"):
            meta_sources.append(
                {"source_type": su.get("type") or "planner", "title": su.get("title")}
            )

    metadata: Dict[str, Any] = {
        "gpt_first": True,
        "intent_summary": parsed["intent_summary"],
        "confidence": parsed["confidence"],
        "should_show_actions": parsed["should_show_actions"],
        "needs_clarification": parsed["needs_clarification"],
        "escalation_recommended": parsed["escalation_recommended"],
        "safety_boundary": parsed["safety_boundary"],
        "sources": meta_sources[:20],
        "sources_used": parsed["sources_used"],
        "retrieval_path": retrieval_path or ["gpt_first"],
        "planner_raw_valid": True,
    }
    if parsed.get("escalation_recommended"):
        metadata["suggested_handoff"] = True

    return {
        "response": reply,
        "action": "respond",
        "metadata": metadata,
        "conversation_context": ctx,
        "actions": actions_out,
    }
