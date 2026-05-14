"""
Deterministic intent router for the public support assistant.
Returns coarse intent + confidence; used for orchestration (support vs sales vs escalate).
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class SupportAssistantIntent(str, Enum):
    COMPANY_ABOUT = "company_about"
    CVP_PRICING = "cvp_pricing"
    DOCUMENT_PACKS = "document_packs"
    ONBOARDING_SETUP = "onboarding_setup"
    ACCOUNT_BILLING = "account_billing"
    PASSWORD_LOGIN = "password_login"
    RECEIPTS_INVOICES = "receipts_invoices"
    COMPLIANCE_CRN = "compliance_crn"
    TECHNICAL = "technical"
    GENERAL_CHAT = "general_chat"
    HUMAN_HANDOFF = "human_handoff"


# Priority order: first match wins (high-specificity patterns first)
_INTENT_RULES: Tuple[Tuple[SupportAssistantIntent, Tuple[str, ...]], ...] = (
    (SupportAssistantIntent.HUMAN_HANDOFF, (
        r"\b(speak|talk|chat)\s+(to|with)\s+(a\s+)?(human|person|agent|someone|representative)\b",
        r"\b(real|live)\s+(person|human|agent|support)\b",
        r"\b(handoff|escalate|transfer|connect me)\b",
        r"\b(customer service|support agent|human support)\b",
    )),
    (SupportAssistantIntent.PASSWORD_LOGIN, (
        r"\b(forgot|forgotten)\s+(my\s+)?password\b",
        r"\bforgot\s+password\b",
        r"\breset\s+my\s+password\b",
        r"\bchange\s+my\s+password\b",
        r"\breset\s+password\b",
        r"\bpassword\s+reset\b",
        r"\b(can't|cannot|cant)\s+log\s+in\b",
        r"\blocked\s+out\b",
        r"\bsign\s+in\s+problem\b",
        r"\blogin\s+issue\b",
    )),
    (SupportAssistantIntent.RECEIPTS_INVOICES, (
        r"\b(receipt|receipts|invoice|invoices|vat invoice|payment confirmation|proof of payment)\b",
    )),
    (SupportAssistantIntent.ACCOUNT_BILLING, (
        r"\b(billing|subscription|cancel subscription|payment failed|past due|stripe|charge|refund|card)\b",
    )),
    (SupportAssistantIntent.ONBOARDING_SETUP, (
        r"\b(onboarding|setup|provision|activation email|welcome email|invite|getting started|first login|account setup)\b",
    )),
    (SupportAssistantIntent.COMPLIANCE_CRN, (
        r"\b(crn|customer reference|compliance score|verification pending|pending verification)\b",
    )),
    (SupportAssistantIntent.TECHNICAL, (
        r"\b(bug|error|not working|broken|500|crash|slow|timeout|page won't load|glitch)\b",
    )),
    (SupportAssistantIntent.CVP_PRICING, (
        r"\b(cvp|compliance vault)\b.*\b(price|pricing|cost|plan)\b",
        r"\b(price|pricing|cost|plans|how much)\b.*\b(cvp|compliance vault|subscription)\b",
        r"\bhow much is cvp\b",
    )),
    (SupportAssistantIntent.DOCUMENT_PACKS, (
        r"\b(document packs?|essential pack|tenancy pack|ultimate pack|landlord documents|ast\b|tenancy agreement)\b",
    )),
    (SupportAssistantIntent.COMPANY_ABOUT, (
        r"\b(what is pleerity|about pleerity|company|contact pleerity)\b",
    )),
)


def classify_support_intent(message: str, ctx: Optional[Dict[str, Any]] = None) -> Tuple[SupportAssistantIntent, float]:
    """
    Rule-based classification. Confidence is heuristic: 1.0 for regex intents, 0.55 for soft keyword fallbacks.
    """
    text = (message or "").strip().lower()
    if not text:
        return SupportAssistantIntent.GENERAL_CHAT, 0.3

    for intent, patterns in _INTENT_RULES:
        for pat in patterns:
            if re.search(pat, text, re.I):
                return intent, 1.0

    # Soft keyword fallbacks (lower confidence)
    if any(k in text for k in ["cvp", "compliance vault", "certificate", "hmo compliance", "portfolio compliance"]):
        return SupportAssistantIntent.CVP_PRICING, 0.6
    if any(k in text for k in ["price", "pricing", "cost", "how much", "plans"]):
        return SupportAssistantIntent.CVP_PRICING, 0.55
    if any(k in text for k in ["automation", "workflow", "ai tool", "market research", "audit"]):
        return SupportAssistantIntent.GENERAL_CHAT, 0.45

    # Obvious chit-chat
    if re.match(r"^(hi|hello|hey|good morning|good afternoon|thanks|thank you|ok|okay)\b", text):
        return SupportAssistantIntent.GENERAL_CHAT, 0.7

    return SupportAssistantIntent.GENERAL_CHAT, 0.35


def engagement_mode(ctx: Optional[Dict[str, Any]], router_intent: SupportAssistantIntent) -> str:
    """
    support: resolution-only, no sales CTAs
    explore: education + gentle qualification
    convert: clear next step when intent is purchase-ready
    """
    ctx = ctx or {}
    if ctx.get("force_support_mode"):
        return "support"
    last = ctx.get("last_action")
    if last == "recommendation" or ctx.get("onboarding_step") == "recommendation":
        return "convert"
    pi = ctx.get("problem_intent")
    if pi in ("pricing_interest", "exploration"):
        return "explore"
    if router_intent in (
        SupportAssistantIntent.PASSWORD_LOGIN,
        SupportAssistantIntent.ACCOUNT_BILLING,
        SupportAssistantIntent.RECEIPTS_INVOICES,
        SupportAssistantIntent.TECHNICAL,
        SupportAssistantIntent.HUMAN_HANDOFF,
    ):
        return "support"
    if router_intent == SupportAssistantIntent.GENERAL_CHAT:
        return "support"
    return "explore"
