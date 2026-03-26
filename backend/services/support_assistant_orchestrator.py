"""
Orchestration: deterministic router, live tools, and escalation metadata for support chat.
Returns a complete handler response dict or None to continue legacy pipeline.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from services.support_assistant_catalog import build_approved_knowledge_dict, format_pricing_paragraph_for_prompt
from services.support_assistant_handoff import build_handoff_summary
from services.support_assistant_intent import SupportAssistantIntent, classify_support_intent, engagement_mode
from services.support_assistant_tools import (
    ASK_ORDER_VERIFY,
    ASK_VERIFY,
    extract_verification_tokens,
    format_tool_answer_account_overview,
    format_tool_answer_order,
    get_billing_subscription_snapshot,
    get_onboarding_snapshot_for_verified_client,
    list_recent_checkout_receipt_summaries,
    lookup_order_for_email,
    resolve_client_by_crn_email,
)

logger = logging.getLogger(__name__)


def _actions_signin_support() -> List[Dict[str, Any]]:
    from services.support_chatbot import _chatbot_app_base

    base = _chatbot_app_base()
    return [
        {"label": "Sign in", "url": f"{base}/login/client"},
        {"label": "Talk to support", "url": None},
    ]


async def router_turn(
    *,
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    ctx: Dict[str, Any],
    is_authenticated: bool,
    client_context: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Early exit handler for router + tools. None = caller continues with qualification/retrieval/LLM.
    """
    from services.support_chatbot import (
        detect_category,
        detect_service_area,
        detect_urgency,
        get_guided_knowledge,
        is_legal_advice_request,
        needs_human_handoff,
        _get_guided_actions,
    )

    text = (message or "").strip()
    if not text:
        return None

    if is_legal_advice_request(text):
        return None

    router_intent, conf = classify_support_intent(text, ctx)
    ctx["router_intent"] = router_intent.value
    ctx["router_confidence"] = conf
    mode = engagement_mode(ctx, router_intent)
    ctx["engagement_mode"] = mode

    # Human handoff: enrich metadata + structured summary
    if needs_human_handoff(text) or router_intent == SupportAssistantIntent.HUMAN_HANDOFF:
        service_area = detect_service_area(text)
        category = detect_category(text)
        urgency = detect_urgency(text)
        summary = build_handoff_summary(
            conversation_id=conversation_id,
            user_message=text,
            router_intent=router_intent,
            intent_confidence=conf,
            conversation_history=conversation_history,
            extra={"engagement_mode": mode},
        )
        return {
            "response": """I'll connect you with a human agent. You can:

1. **Live Chat** — Mon–Fri 9am–6pm GMT
2. **Email ticket** — we respond within 24 hours
3. **WhatsApp** — include your conversation reference

Which would you prefer?""",
            "action": "handoff",
            "metadata": {
                "service_area": service_area,
                "category": category,
                "urgency": urgency,
                "router_intent": router_intent.value,
                "handoff_summary": summary,
            },
            "handoff_data": {
                "conversation_id": conversation_id,
                "service_area": service_area,
                "category": category,
                "urgency": urgency,
                "message_count": len(conversation_history) + 1,
                "structured_summary": summary,
            },
            "handoff_summary": summary,
            "conversation_context": ctx,
        }

    approved = build_approved_knowledge_dict()
    links = approved.get("frontend_links") or {}

    # Authenticated portal: use provided client_context for account facts (already server-loaded)
    if is_authenticated and client_context and router_intent in (
        SupportAssistantIntent.ACCOUNT_BILLING,
        SupportAssistantIntent.RECEIPTS_INVOICES,
        SupportAssistantIntent.ONBOARDING_SETUP,
        SupportAssistantIntent.COMPLIANCE_CRN,
    ):
        crn = client_context.get("crn") or client_context.get("customer_reference")
        sub = client_context.get("subscription_status")
        lines = [
            "Here is your current account summary from your signed-in session:",
            "",
            f"• **CRN:** {crn or '—'}",
            f"• **Subscription:** {sub or '—'}",
        ]
        if client_context.get("recent_orders"):
            lines.append("• **Orders:** open **My Orders** in your dashboard for live status.")
        dash = links.get("dashboard") or ""
        lines.extend(["", f"**Dashboard:** {dash}"])
        return {
            "response": "\n".join(lines),
            "action": "respond",
            "metadata": {
                "guided": True,
                "router_intent": router_intent.value,
                "tool": "client_context_snapshot",
            },
            "conversation_context": ctx,
            "actions": [
                {"label": "Open dashboard", "url": dash or links.get("client_signin")},
                {"label": "Sign in", "url": links.get("client_signin")},
            ],
        }

    tok = extract_verification_tokens(text)

    text_l = text.lower()
    explicit_order_question = bool(tok["order_ref"]) or any(
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

    # Order status tool (reference + email)
    if tok["order_ref"] and tok["email"] and (
        router_intent in (SupportAssistantIntent.COMPLIANCE_CRN, SupportAssistantIntent.ACCOUNT_BILLING)
        or explicit_order_question
    ):
        status, data = await lookup_order_for_email(tok["order_ref"], tok["email"])
        if status == "not_found":
            return {
                "response": "We could not find an order with that reference. Check your confirmation email or use **Talk to support**.",
                "action": "respond",
                "metadata": {"router_intent": router_intent.value, "tool": "order_lookup", "result": "not_found"},
                "conversation_context": ctx,
                "actions": _actions_signin_support(),
            }
        if status == "email_mismatch":
            return {
                "response": "The email you gave does not match the one on that order. We can’t show which email is correct. Try again or contact support.",
                "action": "respond",
                "metadata": {"router_intent": router_intent.value, "tool": "order_lookup", "result": "email_mismatch"},
                "conversation_context": ctx,
                "actions": _actions_signin_support(),
            }
        return {
            "response": format_tool_answer_order(data or {}),
            "action": "respond",
            "metadata": {"router_intent": router_intent.value, "tool": "order_lookup", "result": "ok"},
            "conversation_context": ctx,
            "actions": _actions_signin_support(),
        }

    if explicit_order_question and not (tok["order_ref"] and tok["email"]):
        return {
            "response": ASK_ORDER_VERIFY,
            "action": "respond",
            "metadata": {"router_intent": router_intent.value, "clarifying": True, "needs_verification": True},
            "conversation_context": ctx,
        }

    # CRN + email verified account tools
    account_intents = (
        SupportAssistantIntent.ACCOUNT_BILLING,
        SupportAssistantIntent.RECEIPTS_INVOICES,
        SupportAssistantIntent.ONBOARDING_SETUP,
        SupportAssistantIntent.COMPLIANCE_CRN,
    )
    if router_intent in account_intents and conf >= 0.5:
        if not (tok["crn"] and tok["email"]):
            return {
                "response": ASK_VERIFY,
                "action": "respond",
                "metadata": {"router_intent": router_intent.value, "clarifying": True, "needs_verification": True},
                "conversation_context": ctx,
            }
        client = await resolve_client_by_crn_email(tok["crn"], tok["email"])
        if not client:
            return {
                "response": "We could not verify those details. Check your CRN and email, or use **Talk to support**.",
                "action": "respond",
                "metadata": {"router_intent": router_intent.value, "tool": "verify_account", "result": "failed"},
                "conversation_context": ctx,
                "actions": _actions_signin_support(),
            }
        snap = await get_onboarding_snapshot_for_verified_client(client)
        billing = await get_billing_subscription_snapshot(client["client_id"])
        receipts = await list_recent_checkout_receipt_summaries(client["client_id"])
        body = format_tool_answer_account_overview(snap, billing, receipts)
        if router_intent == SupportAssistantIntent.ONBOARDING_SETUP:
            body += "\n\n**Activation / invite resends:** " + (approved.get("policies") or {}).get(
                "resend_activation", ""
            )
        elif router_intent == SupportAssistantIntent.COMPLIANCE_CRN:
            extras = []
            if "score" in text.lower():
                extras.append(
                    "**Compliance score:** shown per property in the portal after sign-in; public chat cannot display your live score."
                )
            if "verification" in text.lower() or "pending" in text.lower():
                extras.append(
                    f"**Uploads in queue:** {snap.get('documents_awaiting_processing_count', 0)} document(s) currently in **UPLOADED** status."
                )
            if extras:
                body += "\n\n" + "\n\n".join(extras)
        return {
            "response": body,
            "action": "respond",
            "metadata": {
                "router_intent": router_intent.value,
                "tool": "verified_account_snapshot",
                "verified": True,
            },
            "conversation_context": ctx,
            "actions": [
                {"label": "Sign in to portal", "url": links.get("client_signin")},
                {"label": "Talk to support", "url": None},
            ],
        }

    # Company / about
    if router_intent == SupportAssistantIntent.COMPANY_ABOUT and conf >= 0.9:
        co = approved.get("company") or {}
        return {
            "response": "\n".join([
                f"**{co.get('legal_name')}** — {co.get('focus')}",
                "",
                f"• Email: {co.get('support_email')}",
                f"• WhatsApp: {co.get('support_whatsapp')}",
                "",
                f"Compliance Vault Pro: {links.get('compliance_vault_landing', '')}",
            ]),
            "action": "respond",
            "metadata": {"router_intent": router_intent.value, "grounded": True},
            "conversation_context": ctx,
            "actions": [
                {"label": "Pricing", "url": links.get("pricing")},
                {"label": "Services", "url": links.get("services")},
            ],
        }

    # Technical — no guessing
    if router_intent == SupportAssistantIntent.TECHNICAL and conf >= 0.9:
        summary = build_handoff_summary(
            conversation_id=conversation_id,
            user_message=text,
            router_intent=router_intent,
            intent_confidence=conf,
            conversation_history=conversation_history,
        )
        return {
            "response": "\n".join([
                "Thanks for reporting this. I can’t diagnose technical faults reliably from chat alone.",
                "",
                "Try:",
                "• Hard refresh or another browser",
                "• Incognito / private window",
                "• Confirm the site URL matches our official app",
                "",
                "If it continues, create an **email ticket** and paste the summary we prepared below.",
            ]),
            "action": "respond",
            "metadata": {
                "router_intent": router_intent.value,
                "suggested_handoff": True,
                "handoff_summary": summary,
            },
            "conversation_context": ctx,
            "actions": [
                {"label": "Sign in", "url": links.get("client_signin")},
                {"label": "Talk to support", "url": None},
            ],
        }

    # General chit-chat — short steer
    if router_intent == SupportAssistantIntent.GENERAL_CHAT and conf >= 0.65 and len(text) < 80:
        return {
            "response": "Hello — I’m here for Pleerity product and account help (Compliance Vault Pro, document packs, billing, and setup). What do you need today?",
            "action": "respond",
            "metadata": {"router_intent": router_intent.value, "chitchat_steered": True},
            "conversation_context": ctx,
        }

    # CVP / pricing one-shot when confident (sales CTA only outside strict support mode)
    if router_intent == SupportAssistantIntent.CVP_PRICING and conf >= 0.55 and mode != "support":
        para = format_pricing_paragraph_for_prompt(approved)
        first_cvp_line = ""
        for line in (para or "").split("\n"):
            if line.strip().lower().startswith("cvp"):
                first_cvp_line = line.strip()
                break
        if not first_cvp_line and para:
            first_cvp_line = para.split("\n")[0].strip()
        response_body = "**Compliance Vault Pro** — plans from our live registry:\n\n"
        response_body += first_cvp_line or "See the Pricing page for current figures."
        response_body += "\n\nUse **Pricing** for checkout and full plan names."
        actions = _get_guided_actions("compliance_vault_pro") if "compliance_vault_pro" in get_guided_knowledge() else []
        return {
            "response": response_body,
            "action": "respond",
            "metadata": {"router_intent": router_intent.value, "grounded": True, "cta": mode == "convert"},
            "conversation_context": ctx,
            "actions": actions
            or [{"label": "View pricing", "url": links.get("pricing")}],
        }

    return None


def approved_knowledge_json_for_llm() -> str:
    snap = build_approved_knowledge_dict()
    snap["pricing_lines"] = format_pricing_paragraph_for_prompt(snap)
    return json.dumps(snap, indent=2, default=str)
