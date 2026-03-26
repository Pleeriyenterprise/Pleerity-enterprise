"""
Structured Q&A knowledge base for the website support chat assistant.

Entries are used by retrieval to answer direct questions without LLM.
Format: id, title, category, keywords, answer, optional actions, optional audience.
"""
from typing import Any, Dict, List, Optional

import os

def _frontend_base() -> str:
    from utils.app_urls import get_app_base_url

    return get_app_base_url(for_email_links=True).rstrip("/")


def _ai_automation_answer_text() -> str:
    from services.intake_draft_service import SERVICE_BASE_PRICES
    from services.support_assistant_catalog import SERVICE_LABELS

    bits = []
    for code in ("AI_WF_BLUEPRINT", "AI_PROC_MAP", "AI_TOOL_REPORT"):
        p = SERVICE_BASE_PRICES.get(code)
        if p is not None:
            bits.append(f"{SERVICE_LABELS.get(code, code)} (£{int(p) // 100})")
    return (
        "We offer AI workflow services for property management: "
        + ", ".join(bits)
        + ". View details and book on our Services page."
    )


def _market_research_answer_text() -> str:
    from services.intake_draft_service import SERVICE_BASE_PRICES
    from services.support_assistant_catalog import SERVICE_LABELS

    b = SERVICE_BASE_PRICES.get("MR_BASIC")
    a = SERVICE_BASE_PRICES.get("MR_ADV")
    return (
        "We provide property market reports: "
        f"{SERVICE_LABELS.get('MR_BASIC', 'Basic')} (£{int(b) // 100 if b else 0}) and "
        f"{SERVICE_LABELS.get('MR_ADV', 'Advanced')} (£{int(a) // 100 if a else 0}). "
        "See our Services page to order."
    )


def _document_packs_answer_text() -> str:
    from services.pack_registry import PACK_REGISTRY, PACK_ADDONS

    parts = []
    for key in ("ESSENTIAL", "TENANCY", "ULTIMATE"):
        p = PACK_REGISTRY.get(key, {})
        if p:
            parts.append(
                f"{p.get('name')} ({p.get('document_count', '?')} documents, £{int(p.get('price_pence', 0)) // 100})"
            )
    addon_bits = [
        f"{ad.get('name')} +£{int(ad.get('price_pence', 0)) // 100}"
        for ad in PACK_ADDONS.values()
    ]
    return (
        "We offer professional document packs for landlords: "
        + "; ".join(parts)
        + ". Fast Track and printed copy add-ons are priced as follows: "
        + ", ".join(addon_bits)
        + ". Standard fulfilment is 48 hours (24 hours with Fast Track)."
    )


def _cvp_pricing() -> str:
    """Live CVP pricing from plan registry for KB entries that need it."""
    try:
        from services.plan_registry import PLAN_DEFINITIONS, PlanCode
        parts = []
        for code in (PlanCode.PLAN_1_SOLO, PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO):
            plan = PLAN_DEFINITIONS.get(code, {})
            name = plan.get("name", code.value)
            monthly = plan.get("monthly_price")
            onboarding = plan.get("onboarding_fee")
            if monthly is not None and onboarding is not None:
                parts.append(f"{name}: £{monthly:.0f}/month + £{onboarding:.0f} onboarding")
        return " | ".join(parts) if parts else "See our Pricing page for current plans."
    except Exception:
        return "See our Pricing page for current plans."


def get_structured_qa() -> List[Dict[str, Any]]:
    """
    Return the structured Q&A list for retrieval.
    Each entry: id, title, category, keywords, answer, actions (optional), audience (optional).
    actions: list of (label, url) with url None for in-chat actions.
    """
    base = _frontend_base()
    cvp_pricing = _cvp_pricing()
    return [
        {
            "id": "cvp-overview",
            "title": "Compliance Vault Pro overview",
            "category": "cvp",
            "keywords": ["compliance vault", "cvp", "what is cvp", "property compliance", "compliance management", "landlord compliance", "hmo compliance", "portfolio"],
            "answer": "Compliance Vault Pro is our property compliance management platform for landlords and property managers. It helps you track certificates, get expiry alerts, see a compliance score and risk assessment, store documents, and manage multiple properties in one place. It also supports council licensing tracking.",
            "actions": [
                ("See pricing", f"{base}/pricing"),
                ("Create account", f"{base}/compliance-vault-pro"),
                ("Check your compliance risk", f"{base}/risk-check"),
                ("Ask a question", None),
            ],
            "audience": None,
        },
        {
            "id": "cvp-pricing",
            "title": "Compliance Vault Pro pricing",
            "category": "cvp",
            "keywords": ["cvp price", "cvp cost", "cvp pricing", "how much is cvp", "compliance vault price", "subscription cost", "cvp plans"],
            "answer": f"Compliance Vault Pro plans: {cvp_pricing}. You can see full details and sign up on our Pricing page.",
            "actions": [
                ("View pricing", f"{base}/pricing"),
                ("Create account", f"{base}/compliance-vault-pro"),
                ("Check your compliance risk", f"{base}/risk-check"),
                ("Ask a question", None),
            ],
            "audience": None,
        },
        {
            "id": "document-packs",
            "title": "Document packs",
            "category": "document_packs",
            "keywords": ["document pack", "landlord documents", "essential pack", "tenancy pack", "ultimate pack", "ast", "tenancy agreement", "forms", "documents"],
            "answer": _document_packs_answer_text(),
            "actions": [
                ("See pricing", f"{base}/pricing"),
                ("View services", f"{base}/services"),
                ("Ask a question", None),
            ],
            "audience": None,
        },
        {
            "id": "property-management",
            "title": "Property management",
            "category": "property_management",
            "keywords": ["property management", "manage properties", "portfolio management", "multiple properties", "landlord tools"],
            "answer": "Compliance Vault Pro is designed for property managers and landlords with multiple properties. You get a single dashboard for all properties, certificate tracking, compliance scores, document storage, and reminders. For document packs and one-off reports we have Essential, Tenancy, and Ultimate packs plus market research and AI automation services.",
            "actions": [
                ("Compliance Vault Pro", f"{base}/compliance-vault-pro"),
                ("View all services", f"{base}/services"),
                ("Ask a question", None),
            ],
            "audience": None,
        },
        {
            "id": "compliance-score",
            "title": "Compliance score",
            "category": "cvp",
            "keywords": ["compliance score", "risk score", "risk assessment", "how compliant", "compliance rating"],
            "answer": "In Compliance Vault Pro, each property has a compliance score based on the certificates and checks you’ve recorded. It helps you see at a glance how compliant a property is and where action might be needed. You can also use our free compliance risk check to get an initial view.",
            "actions": [
                ("Check your compliance risk", f"{base}/risk-check"),
                ("Compliance Vault Pro", f"{base}/compliance-vault-pro"),
                ("Ask a question", None),
            ],
            "audience": None,
        },
        {
            "id": "evidence-upload",
            "title": "Evidence upload",
            "category": "cvp",
            "keywords": ["upload evidence", "evidence upload", "upload documents", "upload certificate", "add document", "evidence"],
            "answer": "In Compliance Vault Pro you can upload and store documents and certificates per property. Go to the property in your dashboard, then add or update the relevant certificate or document. The system tracks expiry and can send you reminders.",
            "actions": [
                ("Sign in", f"{base}/login/client"),
                ("Compliance Vault Pro", f"{base}/compliance-vault-pro"),
                ("Ask a question", None),
            ],
            "audience": None,
        },
        {
            "id": "reminder-system",
            "title": "Reminder system",
            "category": "cvp",
            "keywords": ["reminder", "reminders", "expiry alert", "certificate expiry", "when does it expire", "alerts"],
            "answer": "Compliance Vault Pro sends automated reminders when certificates are nearing expiry, so you can renew in time. You manage your certificates per property in the dashboard; the system calculates expiry and triggers alerts. For exact timing and channels (email, in-app), check your account settings.",
            "actions": [
                ("Compliance Vault Pro", f"{base}/compliance-vault-pro"),
                ("Sign in", f"{base}/login/client"),
                ("Ask a question", None),
            ],
            "audience": None,
        },
        {
            "id": "password-reset",
            "title": "Password reset",
            "category": "login",
            "keywords": ["password reset", "forgot password", "reset password", "change password", "cant log in", "locked out"],
            "answer": "You can reset your password yourself: on the client sign-in page click 'Forgot password?', enter your email, and we'll send you a link to set a new password. Links expire after 1 hour. Alternatively, your account administrator can send you a new setup link from the Compliance Vault Pro admin portal.",
            "actions": [
                ("Sign in", f"{base}/login/client"),
                ("Talk to support", None),
            ],
            "audience": None,
        },
        {
            "id": "billing-support",
            "title": "Billing support",
            "category": "billing",
            "keywords": ["billing", "payment", "invoice", "subscription", "cancel", "refund", "payment method", "how to pay"],
            "answer": "We accept major credit and debit cards via Stripe (secure and PCI-compliant). You can cancel your subscription anytime from Account Settings > Billing; access continues until the end of the billing period. Refunds are considered on a case-by-case basis; contact support with your order reference for refund queries.",
            "actions": [
                ("Sign in", f"{base}/login/client"),
                ("Talk to support", None),
            ],
            "audience": None,
        },
        {
            "id": "order-status",
            "title": "Order status",
            "category": "documents",
            "keywords": ["order status", "check order", "where is my order", "order reference", "ple-"],
            "answer": "Sign in and open **My Orders**, or send your order reference (format PLE-YYYYMMDD-####) plus the email used at checkout for a verified lookup.",
            "actions": [
                ("Sign in", f"{base}/login/client"),
                ("Talk to support", None),
            ],
            "audience": None,
        },
        {
            "id": "ai-automation",
            "title": "AI automation services",
            "category": "automation",
            "keywords": ["ai automation", "automation", "workflow", "ai tool", "process mapping", "automate", "workflow blueprint"],
            "answer": _ai_automation_answer_text(),
            "actions": [
                ("See options", f"{base}/services"),
                ("Contact support", None),
            ],
            "audience": None,
        },
        {
            "id": "market-research",
            "title": "Market research",
            "category": "market_research",
            "keywords": ["market research", "market report", "area analysis", "rental yield", "investment", "market analysis"],
            "answer": _market_research_answer_text(),
            "actions": [
                ("See reports", f"{base}/services"),
                ("Contact support", None),
            ],
            "audience": None,
        },
        {
            "id": "crn",
            "title": "What is a CRN?",
            "category": "billing",
            "keywords": ["crn", "customer reference", "reference number", "account number"],
            "answer": "CRN (Customer Reference Number) is your unique account identifier in the format PLE-CVP-YYYY-XXXXX. You'll find it in your welcome email and on your dashboard.",
            "actions": [
                ("Sign in", f"{base}/login/client"),
                ("Talk to support", None),
            ],
            "audience": None,
        },
    ]
