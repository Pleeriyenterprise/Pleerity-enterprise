"""
Pleerity Support AI Chatbot Service

Features:
- Knowledge base answers using Gemini/GPT
- Multi-service routing (CVP, Document Packs, Automation, Market Research)
- No-legal-advice guardrails
- Structured + free-text intake
- Human handoff triggers
- CRN-based account lookup
- Canned responses for common queries

CVP pricing and frontend links are built from plan_registry and get_app_base_url() so the AI
always uses current prices and correct sign-in/pricing URLs.
"""
import os
import re
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from database import database

logger = logging.getLogger(__name__)

# Get configurable values from environment
SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP_NUMBER", "+447440645017")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
def _chatbot_app_base() -> str:
    from utils.app_urls import get_app_base_url

    return get_app_base_url(for_email_links=True).rstrip("/")

# ============================================================================
# KNOWLEDGE BASE - Pleerity Services Information (static parts)
# ============================================================================

def _get_cvp_pricing_from_registry() -> str:
    """Build CVP pricing string from plan_registry (single source of truth)."""
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
    except Exception as e:
        logger.warning("support_chatbot: could not load plan_registry for CVP pricing: %s", e)
        return "See our Pricing page for current plans."


def get_chatbot_knowledge_base() -> Dict[str, Any]:
    """Build knowledge base with current CVP pricing and frontend links (used in AI prompt and canned text)."""
    cvp_pricing = _get_cvp_pricing_from_registry()
    return {
    "company": {
        "name": "Pleerity Enterprise Ltd",
        "tagline": "Property compliance and business services for landlords and property managers",
        "support_email": SUPPORT_EMAIL,
        "support_hours": "24/7 via chatbot, Live agents Mon-Fri 9am-6pm GMT",
        "whatsapp": SUPPORT_WHATSAPP,
    },
        "frontend_links": {
            "client_signin": f"{_chatbot_app_base()}/login/client",
            "pricing": f"{_chatbot_app_base()}/pricing",
            "compliance_vault_landing": f"{_chatbot_app_base()}/compliance-vault-pro",
            "dashboard": f"{_chatbot_app_base()}/dashboard",
        },
    "services": {
        "cvp": {
            "name": "Compliance Vault Pro",
            "description": "Comprehensive property compliance management platform for HMO and residential landlords.",
            "features": [
                "Property compliance tracking and monitoring",
                "Document storage and management",
                "Certificate expiry alerts",
                "Compliance scoring and risk assessment",
                "Multi-property portfolio management",
                "Council licensing tracking",
            ],
                "pricing": cvp_pricing,
            "ideal_for": "Landlords with HMO or multiple properties needing compliance oversight",
        },
        "document_packs": {
            "name": "Document Packs",
            "description": "Professional, legally-compliant document packs for landlords.",
            "tiers": {
                "essential": {"name": "Essential Pack", "price": "£29", "documents": 5},
                "tenancy": {"name": "Tenancy Pack", "price": "£49", "documents": 10},
                "ultimate": {"name": "Ultimate Pack", "price": "£79", "documents": 15},
            },
            "addons": {
                "fast_track": {"name": "Fast Track", "price": "£20", "description": "24-hour priority processing"},
                "printed_copy": {"name": "Printed Copy", "price": "£25", "description": "Physical copy by Royal Mail"},
            },
            "turnaround": "Standard 48 hours, Fast Track 24 hours",
        },
        "ai_automation": {
            "name": "AI Workflow Automation",
            "description": "Automate repetitive property management tasks with AI.",
            "services": [
                {"name": "Workflow Automation Blueprint", "price": "£79"},
                {"name": "Business Process Mapping", "price": "£129"},
                {"name": "AI Tool Recommendation Report", "price": "£59"},
            ],
        },
        "market_research": {
            "name": "Market Research",
            "description": "Property market insights and area analysis.",
            "tiers": {
                "basic": {"name": "Basic Report", "price": "£69"},
                "advanced": {"name": "Advanced Report", "price": "£149"},
            },
        },
        "compliance_audits": {
            "name": "Compliance Audits",
            "description": "Professional property compliance audits.",
            "services": [
                {"name": "HMO Audit", "price": "£79"},
                {"name": "Full Compliance Audit", "price": "£99"},
                {"name": "Move-In/Out Checklist", "price": "£35"},
            ],
        },
    },
    "faqs": [
        {
            "question": "How do I reset my password?",
            "answer": "You can reset your password yourself: on the client sign-in page, click 'Forgot password?', enter your email, and we'll send you a link to set a new password. Alternatively, contact your account administrator—they can send you a new setup link from the admin portal. Links expire after 1 hour.",
            "category": "login",
        },
        {
            "question": "How do I check my order status?",
            "answer": "Log into your account and go to 'My Orders' in the dashboard. You'll see all your orders with their current status. For urgent queries, provide your order reference (e.g., PLE-CVP-2026-XXXXX).",
            "category": "documents",
        },
        {
            "question": "What is a CRN?",
            "answer": "CRN (Customer Reference Number) is your unique account identifier in the format PLE-CVP-YYYY-XXXXX. You'll find it in your welcome email and on your dashboard.",
            "category": "billing",
        },
        {
            "question": "How do I cancel my subscription?",
            "answer": "You can cancel anytime from Account Settings > Billing > Cancel Subscription. Your access continues until the end of your billing period. For refund queries, please contact support.",
            "category": "billing",
        },
        {
            "question": "What documents are included in each pack?",
            "answer": "Essential Pack: 5 core documents. Tenancy Pack: 10 documents including AST. Ultimate Pack: 15 comprehensive documents. View full contents on our Services page.",
            "category": "documents",
        },
        {
            "question": "How long does document delivery take?",
            "answer": "Standard delivery is 48 hours. Fast Track (£20 extra) guarantees 24-hour delivery. Printed copies add 3-5 business days for postal delivery.",
            "category": "documents",
        },
        {
            "question": "What payment methods do you accept?",
            "answer": "We accept all major credit/debit cards via Stripe. Payments are secure and PCI-compliant.",
            "category": "billing",
        },
        {
            "question": "Do you offer refunds?",
            "answer": "We offer refunds on a case-by-case basis. For subscriptions, you can cancel anytime but refunds for partial months aren't automatic. Contact support with your order reference.",
            "category": "billing",
        },
    ],
}

# ============================================================================
# LEGAL ADVICE DETECTION - NO LEGAL ADVICE GUARDRAILS
# ============================================================================

LEGAL_ADVICE_PATTERNS = [
    r"is this (legal|lawful|illegal|unlawful)",
    r"can (i|they|the landlord|the tenant) legally",
    r"what (are|is) the (legal|penalty|fine|enforcement)",
    r"will (i|the council|they) (be|get) (fined|prosecuted|penalized)",
    r"(interpret|meaning of) (the law|legislation|regulation|act)",
    r"(legal|council|enforcement) (action|consequences|penalties)",
    r"(can|will) the council (enforce|prosecute|take action)",
    r"what happens if (i|we) (don't|fail to) comply",
    r"(am i|is this) (breaking|violating) (the law|any law)",
    r"legal (advice|opinion|interpretation)",
    r"(should i|do i need to) (sue|take legal action|prosecute)",
]

LEGAL_REFUSAL_RESPONSE = """I'm not able to provide legal advice, interpret legislation, or predict council enforcement actions. For legal questions, please consult:

• A qualified solicitor specializing in property law
• Your local council's licensing team
• Citizens Advice Bureau (free guidance)
• NRLA (National Residential Landlords Association) for members

I can help with:
✓ How to use Pleerity services
✓ Your account and orders
✓ General compliance information (not legal interpretation)
✓ Technical support

Would you like help with any of these instead?"""


def is_legal_advice_request(message: str) -> bool:
    """Check if message is requesting legal advice."""
    message_lower = message.lower()
    for pattern in LEGAL_ADVICE_PATTERNS:
        if re.search(pattern, message_lower):
            return True
    return False


# ============================================================================
# INTENT DETECTION (guided support assistant)
# ============================================================================

INTENTS = {
    "compliance_vault_pro": [
        "cvp", "compliance vault", "vault", "property compliance", "certificate tracking",
        "compliance tracking", "hmo compliance", "certificate", "expiry", "portfolio",
    ],
    "document_packs": [
        "document pack", "landlord documents", "tenancy agreement", "forms",
        "essential pack", "tenancy pack", "ultimate pack", "documents", "ast",
    ],
    "automation": [
        "automation", "workflow", "ai workflow", "ai tool", "process mapping", "automate",
    ],
    "market_research": [
        "research", "market research", "analysis", "area analysis", "rental yield", "market report",
    ],
    "account_support": [
        "login", "reset password", "forgot password", "password", "sign in", "access", "account",
    ],
    "pricing": [
        "pricing", "price", "cost", "how much", "plans", "subscription",
    ],
    "human_support": [
        "talk to support", "human", "help", "speak to human", "contact support", "real person",
    ],
}

# ============================================================================
# PROBLEM-BASED ENTRY DETECTION (layer before product recommendation)
# ============================================================================

PROBLEM_INTENTS = {
    "compliance_risk": [
        "forgetting certificates", "certificate expired", "expiry", "compliance", "renewal",
        "track certificates", "compliance risk", "certificates expir", "renewals", "hmo compliance",
        "compliance tracking", "stay compliant", "compliance records",
    ],
    "missing_documents": [
        "tenancy agreement", "documents", "forms", "need documents", "missing documents",
        "ast", "landlord documents", "document pack", "essential pack", "tenancy pack",
        "ultimate pack", "need a form", "need forms",
    ],
    "workflow_overload": [
        "too much admin", "admin burden", "automation", "workflow", "repetitive",
        "streamline", "automate", "process mapping", "ai workflow", "reduce admin",
    ],
    "account_access_issue": [
        "login", "reset password", "can't access", "forgot password", "locked out",
        "sign in", "cant log in", "cannot access", "password reset", "access account",
    ],
    "pricing_interest": [
        "pricing", "how much", "cost", "price", "plans", "subscription", "how much does",
    ],
    "exploration": [
        "exploring", "just looking", "not sure", "what do you offer", "options",
        "browsing", "find out more", "tell me more", "what services",
    ],
    "support_need": [
        "speak to someone", "human", "support", "talk to", "contact support",
        "real person", "agent", "get help", "need help",
    ],
}

PROBLEM_TO_SOLUTION = {
    "compliance_risk": "compliance_vault_pro",
    "missing_documents": "document_packs",
    "workflow_overload": "automation",
    "account_access_issue": "account_support",
    "pricing_interest": "pricing",
    "exploration": "pricing",
    "support_need": "account_support",
}

PROBLEM_DIAGNOSIS = {
    "compliance_risk": "It sounds like you're concerned about compliance and certificate renewals.",
    "missing_documents": "It sounds like you need landlord documents or tenancy forms.",
    "workflow_overload": "It sounds like you're looking to reduce admin and automate workflows.",
    "account_access_issue": "It sounds like you're having trouble with account access or sign-in.",
    "pricing_interest": "It sounds like you'd like to see our pricing and plans.",
    "exploration": "It sounds like you're exploring your options.",
    "support_need": "It sounds like you'd like to speak with our team.",
}


def detect_problem_intent(message: str) -> Optional[str]:
    """Detect underlying problem from user message (problem layer before product intent)."""
    if not message or not message.strip():
        return None
    text = message.lower().strip()
    for problem, keywords in PROBLEM_INTENTS.items():
        if any(kw in text for kw in keywords):
            return problem
    return None


def detect_intent(message: str) -> Optional[str]:
    """Lightweight intent from keywords. Returns intent key or None."""
    if not message or not message.strip():
        return None
    text = message.lower().strip()
    for intent, keywords in INTENTS.items():
        if any(kw in text for kw in keywords):
            return intent
    return None


def get_guided_knowledge() -> Dict[str, Any]:
    """Structured knowledge for guided responses: description, features, actions."""
    kb = get_chatbot_knowledge_base()
    cvp_pricing = _get_cvp_pricing_from_registry()
    return {
        "compliance_vault_pro": {
            "description": "Compliance Vault Pro helps landlords manage property compliance automatically.",
            "features": [
                "Certificate tracking and expiry alerts",
                "Automated reminders",
                "Compliance score and risk assessment",
                "Document storage and portfolio view",
                "Council licensing tracking",
            ],
            "actions": [
                ("See pricing", f"{_chatbot_app_base()}/pricing"),
                ("Create account", f"{_chatbot_app_base()}/compliance-vault-pro"),
                ("Check your compliance risk", f"{_chatbot_app_base()}/risk-check"),
                ("Ask a question", None),
            ],
            "pricing": cvp_pricing,
        },
        "document_packs": {
            "description": "Professional, legally-compliant document packs for landlords.",
            "features": [
                "Essential (5 docs), Tenancy (10), Ultimate (15)",
                "Fast Track 24hr or standard 48hr delivery",
                "Printed copy option",
            ],
            "actions": [
                ("See pricing", f"{_chatbot_app_base()}/pricing"),
                ("View services", f"{_chatbot_app_base()}/services"),
                ("Ask a question", None),
            ],
        },
        "automation": {
            "description": "AI workflow automation for property management tasks.",
            "features": [
                "Workflow Automation Blueprint",
                "Business Process Mapping",
                "AI Tool Recommendation Report",
            ],
            "actions": [
                ("See options", f"{_chatbot_app_base()}/services"),
                ("Contact support", None),
            ],
        },
        "market_research": {
            "description": "Property market insights and area analysis.",
            "features": [
                "Basic and Advanced reports",
                "Rental yield and investment analysis",
            ],
            "actions": [
                ("See reports", f"{_chatbot_app_base()}/services"),
                ("Contact support", None),
            ],
        },
        "account_support": {
            "description": "Account and login support.",
            "features": [
                "Password reset (self-service or admin)",
                "Order status and CRN lookup",
            ],
            "actions": [
                ("Sign in", f"{_chatbot_app_base()}/login/client"),
                ("Talk to support", None),
            ],
        },
        "pricing": {
            "description": "Current plans and pricing.",
            "features": [f"CVP: {cvp_pricing}", "Document packs: Essential £29, Tenancy £49, Ultimate £79"],
            "actions": [
                ("View pricing", f"{_chatbot_app_base()}/pricing"),
                ("Create account", f"{_chatbot_app_base()}/compliance-vault-pro"),
                ("Check your compliance risk", f"{_chatbot_app_base()}/risk-check"),
                ("Ask a question", None),
            ],
        },
    }


def _actions_list_from_tuples(tuples: List[Any]) -> List[Dict[str, Any]]:
    """Convert (label, url) tuples to [{ label, url }] for API. url None for in-chat actions."""
    out: List[Dict[str, Any]] = []
    for t in tuples or []:
        if isinstance(t, (list, tuple)):
            label = t[0] if len(t) > 0 else ""
            url = t[1] if len(t) > 1 else None
        else:
            label, url = str(t), None
        out.append({"label": str(label), "url": url})
    return out


def _get_guided_actions(intent: str) -> List[Dict[str, Any]]:
    """Return actions list for a guided intent (for clickable links in UI)."""
    knowledge = get_guided_knowledge()
    entry = knowledge.get(intent)
    if not entry:
        return []
    return _actions_list_from_tuples(entry.get("actions") or [])


def _trim_action_lines(text: str) -> str:
    """Remove the 'What would you like to do?' and numbered action lines from the end of response text."""
    if not text or "What would you like to do?" not in text:
        return text
    parts = text.split("\n\nWhat would you like to do?")
    if len(parts) < 2:
        return text
    body = parts[0].rstrip()
    # Also strip trailing "Key features:"-only or single newline
    return body


def build_guided_response(intent: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Build intro + key points + next actions from knowledge."""
    knowledge = get_guided_knowledge()
    entry = knowledge.get(intent)
    if not entry:
        return ""
    lines = [entry["description"], ""]
    lines.append("Key features:")
    for f in entry.get("features", []):
        lines.append(f"• {f}")
    lines.append("")
    if entry.get("pricing"):
        lines.append(f"Pricing: {entry['pricing']}")
    lines.append("")
    lines.append("What would you like to do?")
    for i, action in enumerate(entry.get("actions", []), 1):
        label, url = action if isinstance(action, (list, tuple)) else (action, None)
        if url:
            lines.append(f"{i}. {label}: {url}")
        else:
            lines.append(f"{i}. {label}")
    return "\n".join(lines)


# ============================================================================
# ONBOARDING: QUALIFICATION + RECOMMENDATION + LEAD CAPTURE
# ============================================================================

QUALIFICATION_INTENTS = ["compliance_vault_pro"]  # Intents that get "Are you a: Landlord / ...?" before recommendation
USER_TYPE_OPTIONS = [
    {"id": "landlord", "label": "Landlord"},
    {"id": "property_manager", "label": "Property manager"},
    {"id": "letting_agency", "label": "Letting agency"},
    {"id": "exploring", "label": "Just exploring"},
]
QUALIFICATION_QUESTION = """Are you a:

• **Landlord**
• **Property manager**
• **Letting agency**
• **Just exploring**"""

# Portfolio size follow-up (for compliance recommendation)
PORTFOLIO_SIZE_OPTIONS = [
    {"id": "1_2", "label": "1–2 properties"},
    {"id": "3_10", "label": "3–10 properties"},
    {"id": "10_plus", "label": "10+ properties"},
]
PORTFOLIO_SIZE_QUESTION = """How many properties do you manage?

• **1–2 properties**
• **3–10 properties**
• **10+ properties**"""


def detect_user_type_from_message(message: str) -> Optional[str]:
    """Map user reply to user_type id for qualification step."""
    text = (message or "").strip().lower()
    if not text:
        return None
    if "landlord" in text:
        return "landlord"
    if any(w in text for w in ["property manager", "manager"]):
        return "property_manager"
    if any(w in text for w in ["letting agency", "letting agent", "agency", "agent"]):
        return "letting_agency"
    if any(w in text for w in ["exploring", "just looking", "browsing", "not sure"]):
        return "exploring"
    return None


def detect_portfolio_size_from_message(message: str) -> Optional[str]:
    """Map user reply to portfolio_size id (1_2, 3_10, 10_plus)."""
    text = (message or "").strip().lower()
    if not text:
        return None
    if any(w in text for w in ["1", "one", "two", "2", "couple", "few", "1-2", "1–2"]):
        return "1_2"
    if any(w in text for w in ["3", "4", "5", "6", "7", "8", "9", "10", "several", "handful", "3-10", "3–10"]):
        return "3_10"
    if any(w in text for w in ["10+", "10 plus", "many", "portfolio", "lots", "dozen"]):
        return "10_plus"
    return None


def get_recommendation(ctx: Dict[str, Any]) -> Tuple[str, str]:
    """
    Context-aware recommendation: (service_key, reason).
    service_key matches get_guided_knowledge() keys; reason is a short 'because' sentence.
    """
    intent = ctx.get("intent")
    user_type = ctx.get("user_type")
    portfolio_size = ctx.get("portfolio_size")
    # primary_goal / secondary_need can be used later; for now intent carries goal
    primary_goal = ctx.get("primary_goal") or intent

    # Exploring or no clear intent -> overview/pricing
    if user_type == "exploring" or not intent:
        return "pricing", "you can see our plans and book a demo to find the right fit."

    # Compliance Vault Pro
    if intent == "compliance_vault_pro":
        if user_type == "landlord":
            if portfolio_size == "1_2":
                return "compliance_vault_pro", "it helps you track certificates, reminders, and compliance records in one place—ideal for 1–2 properties."
            if portfolio_size == "3_10":
                return "compliance_vault_pro", "it scales to multiple properties with certificate tracking, expiry alerts, and a single dashboard."
            if portfolio_size == "10_plus":
                return "compliance_vault_pro", "it supports large portfolios with compliance scoring, document storage, and council licensing tracking."
            return "compliance_vault_pro", "it helps you track certificates, reminders, and compliance records in one place."
        if user_type == "property_manager":
            return "compliance_vault_pro", "it gives property managers a single view of compliance across all properties with alerts and reporting."
        if user_type == "letting_agency":
            return "compliance_vault_pro", "it is ideal for letting agencies managing portfolio compliance and certificate expiry."
        return "compliance_vault_pro", "it helps landlords and managers track property compliance, certificates, and reminders."

    # Document packs
    if intent == "document_packs":
        if user_type == "landlord":
            return "document_packs", "professional document packs for tenancies and compliance are a good fit for landlords."
        if user_type in ("property_manager", "letting_agency"):
            return "document_packs", "professional document packs support your tenancy and compliance workflows."
        return "document_packs", "we offer Essential, Tenancy, and Ultimate packs with fast delivery options."

    # Automation
    if intent == "automation":
        if user_type == "letting_agency":
            return "automation", "AI workflow automation can streamline agency processes and reporting."
        if user_type == "property_manager":
            return "automation", "automation helps property managers map and optimise repetitive workflows."
        return "automation", "we offer workflow blueprints, process mapping, and AI tool recommendations."

    # Market research
    if intent == "market_research":
        return "market_research", "our reports provide area analysis, rental yield, and investment insights."

    # Account support / pricing fallback
    if intent == "account_support":
        return "account_support", "we can help with sign-in, password reset, and account access."
    return "pricing", "you can view our plans and services to find the right option."


SERVICE_DISPLAY_NAMES = {
    "compliance_vault_pro": "Compliance Vault Pro",
    "document_packs": "Document Packs",
    "automation": "AI workflow automation",
    "market_research": "Market research",
    "account_support": "Account support",
    "pricing": "our Pricing page",
}


def build_recommendation_response(service_key: str, reason: str, ctx: Dict[str, Any]) -> str:
    """Build 'For [context], [Service] is likely the best fit because [reason].' + guided content (no action lines)."""
    knowledge = get_guided_knowledge()
    entry = knowledge.get(service_key)
    if not entry:
        return ""
    user_type = ctx.get("user_type")
    user_type_label = {"landlord": "a landlord", "property_manager": "a property manager", "letting_agency": "a letting agency", "exploring": "exploring"}.get(user_type or "", "you")
    service_name = SERVICE_DISPLAY_NAMES.get(service_key, service_key.replace("_", " ").title())
    intro = f"For {user_type_label}, **{service_name}** is likely the best fit because {reason}"
    lines = [intro, ""]
    lines.append("Key features:")
    for f in entry.get("features", []):
        lines.append(f"• {f}")
    lines.append("")
    if entry.get("pricing"):
        lines.append(f"Pricing: {entry['pricing']}")
    return "\n".join(lines).strip()


def recommendation_intro_by_user_type(intent: str, user_type: Optional[str]) -> str:
    """One-line tailored intro for recommendation (e.g. 'As a landlord, we recommend...')."""
    if intent == "compliance_vault_pro":
        if user_type == "landlord":
            return "As a landlord, we recommend **Compliance Vault Pro**."
        if user_type == "property_manager":
            return "As a property manager, we recommend **Compliance Vault Pro**."
        if user_type == "letting_agency":
            return "For letting agencies, **Compliance Vault Pro** is ideal for portfolio compliance."
    return ""


LEAD_CAPTURE_OFFER = """Would you like us to send you more information by email?

If yes, enter your email below and we'll send you details and next steps."""


# Escalation when assistant cannot answer after N attempts
ESCALATION_AFTER_UNANSWERED = 2
ESCALATION_MESSAGE = """I may need a human team member to help with that. Would you like to contact support?

You can:
• **Live Chat** – Mon–Fri 9am–6pm GMT
• **Email** – We'll respond within 24 hours
• **WhatsApp** – Use your conversation reference"""


# ============================================================================
# SERVICE ROUTING (existing, kept for metadata)
# ============================================================================

SERVICE_KEYWORDS = {
    "cvp": ["compliance vault", "cvp", "compliance tracking", "property compliance", "hmo compliance", "certificate", "expiry", "dashboard", "portfolio"],
    "document_services": ["document pack", "essential pack", "tenancy pack", "ultimate pack", "documents", "ast", "tenancy agreement", "inventory"],
    "ai_automation": ["automation", "workflow", "ai tool", "process mapping", "automate"],
    "market_research": ["market research", "area analysis", "rental yield", "investment", "market report"],
    "billing": ["billing", "payment", "invoice", "subscription", "cancel", "refund", "pricing", "cost"],
    "login": ["login", "password", "reset", "sign in", "access", "account locked", "forgot password"],
}


def detect_service_area(message: str) -> str:
    """Detect which service area the message relates to."""
    message_lower = message.lower()
    
    scores = {}
    for area, keywords in SERVICE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        if score > 0:
            scores[area] = score
    
    if scores:
        return max(scores, key=scores.get)
    return "other"


def detect_urgency(message: str) -> str:
    """Detect urgency level from message."""
    message_lower = message.lower()
    
    urgent_patterns = ["urgent", "asap", "emergency", "immediately", "critical", "today", "now"]
    high_patterns = ["important", "quickly", "soon", "deadline", "expiring"]
    
    if any(p in message_lower for p in urgent_patterns):
        return "urgent"
    if any(p in message_lower for p in high_patterns):
        return "high"
    return "medium"


def detect_category(message: str) -> str:
    """Detect ticket category from message."""
    message_lower = message.lower()
    
    if any(w in message_lower for w in ["login", "password", "sign in", "access"]):
        return "login"
    if any(w in message_lower for w in ["bill", "payment", "invoice", "refund", "cancel", "subscription"]):
        return "billing"
    if any(w in message_lower for w in ["document", "pack", "download", "pdf"]):
        return "documents"
    if any(w in message_lower for w in ["compliance", "certificate", "audit", "hmo"]):
        return "compliance"
    if any(w in message_lower for w in ["report", "analytics", "dashboard"]):
        return "reporting"
    if any(w in message_lower for w in ["error", "bug", "not working", "broken", "issue"]):
        return "technical"
    return "other"


# ============================================================================
# HUMAN HANDOFF DETECTION
# ============================================================================

HANDOFF_TRIGGERS = [
    r"(speak|talk|chat) (to|with) (a |an )?(human|person|agent|someone|representative)",
    r"(real|live) (person|human|agent|support)",
    r"(escalate|transfer|connect me)",
    r"human (help|support|assistance)",
    r"not (helpful|helping|understanding)",
    r"(this|you) (is|are) (not|n't) (help|work)",
]


def needs_human_handoff(message: str) -> bool:
    """Check if user is requesting human assistance."""
    message_lower = message.lower()
    for pattern in HANDOFF_TRIGGERS:
        if re.search(pattern, message_lower):
            return True
    return False


# ============================================================================
# ACCOUNT LOOKUP (SANITIZED)
# ============================================================================

async def lookup_account_by_crn(crn: str, email: str) -> Optional[Dict[str, Any]]:
    """
    Public account lookup - returns sanitized summary only.
    Both CRN and email must match for security.
    """
    db = database.get_db()
    
    # Find client by CRN (stored as customer_reference on clients)
    client = await db["clients"].find_one(
        {"customer_reference": crn.upper()},
        {"_id": 0, "email": 1, "full_name": 1, "subscription_status": 1, "created_at": 1}
    )
    
    if not client:
        return None
    
    # Verify email matches (case-insensitive)
    if client.get("email", "").lower() != email.lower():
        return None
    
    # Return sanitized summary only
    name = client.get("full_name") or client.get("name")
    return {
        "verified": True,
        "account_status": client.get("subscription_status", "unknown"),
        "member_since": client.get("created_at", "")[:10] if client.get("created_at") else "N/A",
        "name_initial": (name or "?")[0].upper() if name else "?",
    }


async def get_client_snapshot(client_id: str) -> Optional[Dict[str, Any]]:
    """
    Get account snapshot for authenticated client.
    Used by portal assistant.
    """
    db = database.get_db()
    
    # Get client
    client = await db["clients"].find_one(
        {"client_id": client_id},
        {"_id": 0, "password_hash": 0}
    )
    
    if not client:
        return None
    
    # Get recent orders
    orders_cursor = db["orders"].find(
        {"client_id": client_id},
        {"_id": 0, "order_ref": 1, "status": 1, "service_name": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5)
    recent_orders = await orders_cursor.to_list(length=5)
    
    # Get properties count if CVP user
    properties_count = await db["properties"].count_documents({"client_id": client_id})
    
    return {
        "name": client.get("full_name") or client.get("name"),
        "email": client.get("email"),
        "crn": client.get("customer_reference"),
        "subscription_status": client.get("subscription_status", "none"),
        "recent_orders": recent_orders,
        "properties_count": properties_count,
    }


# ============================================================================
# AI RESPONSE GENERATION
# ============================================================================

async def generate_ai_response(
    message: str,
    conversation_history: List[Dict[str, Any]],
    client_context: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate AI response using Gemini (utils.llm_chat).
    Returns (response_text, metadata).
    """
    try:
        from utils.llm_chat import chat, _get_api_key
        from prompts.support_assistant_system_prompt import SUPPORT_ASSISTANT_SYSTEM_PROMPT
        if not _get_api_key():
            logger.warning("LLM_API_KEY not set, using fallback response")
            return await generate_fallback_response(message, client_context)
        system_parts = [
            SUPPORT_ASSISTANT_SYSTEM_PROMPT,
            "",
            "KNOWLEDGE BASE (use only the following; never invent URLs):",
            json.dumps(get_chatbot_knowledge_base(), indent=2),
        ]
        if client_context:
            system_parts.extend([
                "",
                "CUSTOMER CONTEXT (authenticated):",
                json.dumps(client_context, indent=2),
            ])
        context_text = ""
        for msg in conversation_history[-5:]:
            role = "Customer" if msg.get("sender") == "user" else "Assistant"
            context_text += f"{role}: {msg.get('message_text', '')}\n"
        prompt = f"""Previous conversation:
{context_text}

Customer's new message: {message}

Respond helpfully and concisely. If you don't know something specific to their account, acknowledge it and offer alternatives."""
        response = await chat(
            system_prompt="\n".join(system_parts),
            user_text=prompt,
            model="gemini-2.0-flash",
        )
        metadata = {
            "ai_generated": True,
            "model": "gemini-2.0-flash",
            "service_area": detect_service_area(message),
            "category": detect_category(message),
            "urgency": detect_urgency(message),
        }
        
        return response, metadata
        
    except Exception as e:
        logger.error(f"AI response generation failed: {e}")
        return await generate_fallback_response(message, client_context)


async def generate_fallback_response(
    message: str,
    client_context: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """Generate fallback response when AI is unavailable."""
    
    service_area = detect_service_area(message)
    category = detect_category(message)
    
    # Try to match FAQs
    message_lower = message.lower()
    for faq in get_chatbot_knowledge_base().get("faqs", []):
        if any(word in message_lower for word in faq["question"].lower().split()[:3]):
            return faq["answer"], {
                "ai_generated": False,
                "fallback": True,
                "matched_faq": True,
                "service_area": service_area,
                "category": category,
            }
    
    # Generic helpful response
    response = """Thanks for your message! I'm here to help with:

• **Compliance Vault Pro** - Property compliance management
• **Document Packs** - Professional landlord documents
• **AI Automation** - Workflow automation services
• **Market Research** - Property market insights
• **Account & Billing** - Orders, payments, subscriptions

What would you like help with? Or if you'd prefer, I can connect you with a human agent."""
    
    return response, {
        "ai_generated": False,
        "fallback": True,
        "service_area": service_area,
        "category": category,
    }


# ============================================================================
# MAIN CHAT HANDLER
# ============================================================================

def _count_recent_fallback_responses(conversation_history: List[Dict[str, Any]]) -> int:
    """Count consecutive bot messages that were fallback (unmatched), not guided/intent-based."""
    count = 0
    for msg in reversed(conversation_history):
        if msg.get("sender") != "bot":
            break
        meta = msg.get("metadata") or {}
        if meta.get("guided") or meta.get("matched_faq") or meta.get("legal_refusal") or meta.get("retrieval_matched") or meta.get("clarifying"):
            break  # Successful or structured answers; don't count toward escalation
        if meta.get("fallback"):
            count += 1
        else:
            break
    return count


async def handle_chat_message(
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    client_context: Optional[Dict[str, Any]] = None,
    is_authenticated: bool = False,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main chat handler - processes message and returns response.
    Supports session-level conversation_context (intent, topic, last_action) for guided responses.
    Returns conversation_context for client to send back next turn.
    """
    ctx = dict(conversation_context) if conversation_context else {}
    ctx.setdefault("intent", None)
    ctx.setdefault("topic", None)
    ctx.setdefault("last_action", None)
    ctx.setdefault("user_type", None)
    ctx.setdefault("onboarding_step", None)
    ctx.setdefault("lead_capture_offered", False)
    ctx.setdefault("portfolio_size", None)
    ctx.setdefault("primary_goal", None)
    ctx.setdefault("secondary_need", None)
    ctx.setdefault("problem_intent", None)
    if ctx.get("intent") and not ctx.get("primary_goal"):
        ctx["primary_goal"] = ctx["intent"]

    # --- Problem-based entry: detect problem intent and set product intent from map ---
    problem = detect_problem_intent(message)
    if problem:
        ctx["problem_intent"] = problem
        solution = PROBLEM_TO_SOLUTION.get(problem)
        if solution:
            ctx["intent"] = solution
            ctx["topic"] = solution
            ctx["last_action"] = "intent_set"

    # --- Portfolio size follow-up (after qualification for compliance) ---
    if ctx.get("onboarding_step") == "portfolio_size":
        portfolio_size = detect_portfolio_size_from_message(message)
        if portfolio_size:
            ctx["portfolio_size"] = portfolio_size
            ctx["onboarding_step"] = "recommendation"
            service_key, reason = get_recommendation(ctx)
            response = build_recommendation_response(service_key, reason, ctx)
            if ctx.get("problem_intent"):
                diagnosis = PROBLEM_DIAGNOSIS.get(ctx["problem_intent"], "")
                if diagnosis:
                    response = diagnosis + "\n\n" + response
            actions = _get_guided_actions(service_key)
            ctx["last_action"] = "recommendation"
            return {
                "response": response,
                "action": "respond",
                "metadata": {
                    "guided": True,
                    "intent": ctx.get("intent"),
                    "user_type": ctx.get("user_type"),
                    "portfolio_size": portfolio_size,
                    "onboarding_step": "recommendation",
                    "problem_intent": ctx.get("problem_intent"),
                },
                "conversation_context": ctx,
                "actions": actions,
            }
        return {
            "response": PORTFOLIO_SIZE_QUESTION,
            "action": "respond",
            "metadata": {
                "follow_up": "portfolio_size",
                "portfolio_size_options": PORTFOLIO_SIZE_OPTIONS,
                "intent": ctx.get("intent"),
            },
            "conversation_context": ctx,
        }

    # --- Onboarding: user_type selection (qualification step) ---
    if ctx.get("onboarding_step") == "qualification":
        user_type = detect_user_type_from_message(message)
        if user_type:
            ctx["user_type"] = user_type
            intent_for_actions = ctx.get("intent")
            if intent_for_actions == "compliance_vault_pro" and not ctx.get("portfolio_size"):
                ctx["onboarding_step"] = "portfolio_size"
                return {
                    "response": PORTFOLIO_SIZE_QUESTION,
                    "action": "respond",
                    "metadata": {
                        "follow_up": "portfolio_size",
                        "portfolio_size_options": PORTFOLIO_SIZE_OPTIONS,
                        "guided": True,
                        "intent": ctx.get("intent"),
                        "user_type": user_type,
                    },
                    "conversation_context": ctx,
                }
            ctx["onboarding_step"] = "recommendation"
            service_key, reason = get_recommendation(ctx)
            response = build_recommendation_response(service_key, reason, ctx)
            if ctx.get("problem_intent"):
                diagnosis = PROBLEM_DIAGNOSIS.get(ctx["problem_intent"], "")
                if diagnosis:
                    response = diagnosis + "\n\n" + response
            actions = _get_guided_actions(service_key)
            ctx["last_action"] = "recommendation"
            return {
                "response": response,
                "action": "respond",
                "metadata": {
                    "guided": True,
                    "intent": ctx.get("intent"),
                    "user_type": user_type,
                    "onboarding_step": "recommendation",
                    "problem_intent": ctx.get("problem_intent"),
                },
                "conversation_context": ctx,
                "actions": actions,
            }
        # Unclear reply: re-ask qualification with buttons
        return {
            "response": QUALIFICATION_QUESTION,
            "action": "respond",
            "metadata": {
                "guided": True,
                "intent": ctx.get("intent"),
                "qualification_question": True,
                "user_type_options": USER_TYPE_OPTIONS,
            },
            "conversation_context": ctx,
        }
    
    # Check for legal advice request
    if is_legal_advice_request(message):
        return {
            "response": LEGAL_REFUSAL_RESPONSE,
            "action": "respond",
            "metadata": {"legal_refusal": True, "service_area": "other", "category": "other"},
            "conversation_context": ctx,
        }
    
    # Check for human handoff request
    if needs_human_handoff(message):
        service_area = detect_service_area(message)
        category = detect_category(message)
        urgency = detect_urgency(message)
        return {
            "response": """I'll connect you with a human agent. You have three options:

1. **Live Chat** - Chat with an agent now (Mon-Fri 9am-6pm GMT)
2. **Email Ticket** - We'll respond within 24 hours
3. **WhatsApp** - Continue on WhatsApp with your reference

Which would you prefer?""",
            "action": "handoff",
            "metadata": {"service_area": service_area, "category": category, "urgency": urgency},
            "handoff_data": {
                "conversation_id": conversation_id,
                "service_area": service_area,
                "category": category,
                "urgency": urgency,
                "message_count": len(conversation_history) + 1,
            },
            "conversation_context": ctx,
        }

    message_lower = message.lower().strip()
    pricing_like = any(w in message_lower for w in ["pricing", "price", "how much", "cost", "plans"])
    knowledge = get_guided_knowledge()

    # Short follow-up "pricing" etc.: use existing intent so e.g. "CVP" then "pricing" → CVP pricing
    if pricing_like and ctx.get("intent") and ctx["intent"] in knowledge:
        if ctx.get("user_type"):
            service_key, reason = get_recommendation(ctx)
            response_text = build_recommendation_response(service_key, reason, ctx)
            actions = _get_guided_actions(service_key)
            if ctx.get("problem_intent"):
                diagnosis = PROBLEM_DIAGNOSIS.get(ctx["problem_intent"], "")
                if diagnosis:
                    response_text = diagnosis + "\n\n" + response_text
        else:
            guided = build_guided_response(ctx["intent"], ctx)
            actions = _get_guided_actions(ctx["intent"])
            response_text = _trim_action_lines(guided) if actions else guided
        if response_text:
            ctx["last_action"] = "guided_pricing"
            return {
                "response": response_text,
                "action": "respond",
                "metadata": {"guided": True, "intent": ctx["intent"], "service_area": ctx.get("intent"), "problem_intent": ctx.get("problem_intent")},
                "conversation_context": ctx,
                "actions": actions,
            }

    # Intent detection: update context from product keywords only when no problem_intent (problem layer takes precedence)
    detected = detect_intent(message)
    if detected and not ctx.get("problem_intent"):
        ctx["intent"] = detected
        ctx["topic"] = detected
        ctx["last_action"] = "intent_set"

    # human_support intent: trigger handoff (keyword-based, in addition to needs_human_handoff regex)
    if ctx.get("intent") == "human_support":
        service_area = detect_service_area(message)
        category = detect_category(message)
        urgency = detect_urgency(message)
        return {
            "response": """I'll connect you with a human agent. You have three options:

1. **Live Chat** - Chat with an agent now (Mon-Fri 9am-6pm GMT)
2. **Email Ticket** - We'll respond within 24 hours
3. **WhatsApp** - Continue on WhatsApp with your reference

Which would you prefer?""",
            "action": "handoff",
            "metadata": {"service_area": service_area, "category": category, "urgency": urgency},
            "handoff_data": {
                "conversation_id": conversation_id,
                "service_area": service_area,
                "category": category,
                "urgency": urgency,
                "message_count": len(conversation_history) + 1,
            },
            "conversation_context": ctx,
        }

    # Explicit intent match: qualification (for compliance) or guided response (intent may be from problem or product)
    current_intent = ctx.get("intent")
    if current_intent and current_intent in knowledge:
        if current_intent in QUALIFICATION_INTENTS and not ctx.get("user_type"):
            ctx["onboarding_step"] = "qualification"
            return {
                "response": QUALIFICATION_QUESTION,
                "action": "respond",
                "metadata": {
                    "guided": True,
                    "intent": current_intent,
                    "qualification_question": True,
                    "user_type_options": USER_TYPE_OPTIONS,
                },
                "conversation_context": ctx,
            }
        guided = build_guided_response(current_intent, ctx)
        if guided:
            if ctx.get("user_type"):
                service_key, reason = get_recommendation(ctx)
                response_text = build_recommendation_response(service_key, reason, ctx)
                actions = _get_guided_actions(service_key)
                ctx["last_action"] = "recommendation"
            else:
                actions = _get_guided_actions(current_intent)
                response_text = _trim_action_lines(guided) if actions else guided
                ctx["last_action"] = "guided"
            if ctx.get("problem_intent"):
                diagnosis = PROBLEM_DIAGNOSIS.get(ctx["problem_intent"], "")
                if diagnosis:
                    response_text = diagnosis + "\n\n" + response_text
            return {
                "response": response_text,
                "action": "respond",
                "metadata": {"guided": True, "intent": current_intent, "service_area": current_intent, "problem_intent": ctx.get("problem_intent")},
                "conversation_context": ctx,
                "actions": actions,
            }

    # Lead capture: offer once after recommendation when user sends another message
    if ctx.get("last_action") == "recommendation" and not ctx.get("lead_capture_offered"):
        ctx["lead_capture_offered"] = True
        return {
            "response": LEAD_CAPTURE_OFFER,
            "action": "respond",
            "metadata": {"offer_lead_capture": True, "intent": ctx.get("intent")},
            "conversation_context": ctx,
        }

    # Structured KB retrieval: answer from knowledge base when confidence is high (avoid LLM hallucination)
    try:
        from services.support_chatbot_retrieval import (
            retrieve,
            build_response_from_entry,
            get_actions_from_entry,
            get_clarifying_message,
            RETRIEVAL_CONFIDENCE_THRESHOLD,
            CLARIFYING_THRESHOLD,
        )
        best_entry, best_score, all_scored = retrieve(message, ctx)
        if best_entry and best_score >= RETRIEVAL_CONFIDENCE_THRESHOLD:
            response_text = build_response_from_entry(best_entry)
            actions = get_actions_from_entry(best_entry)
            if actions:
                response_text = _trim_action_lines(response_text)
            ctx["last_action"] = "retrieval"
            return {
                "response": response_text,
                "action": "respond",
                "metadata": {
                    "retrieval_matched": True,
                    "kb_id": best_entry.get("id"),
                    "category": best_entry.get("category"),
                },
                "conversation_context": ctx,
                "actions": actions,
            }
        if best_score >= CLARIFYING_THRESHOLD:
            clarifying = get_clarifying_message(all_scored)
            if clarifying:
                ctx["last_action"] = "clarifying"
                return {
                    "response": clarifying,
                    "action": "respond",
                    "metadata": {"clarifying": True},
                    "conversation_context": ctx,
                }
    except Exception as e:
        logger.warning("support_chatbot: retrieval failed, falling back to AI: %s", e)

    # Escalation: after N consecutive fallback/unmatched bot replies, offer human
    fallback_count = _count_recent_fallback_responses(conversation_history)
    if fallback_count >= ESCALATION_AFTER_UNANSWERED:
        ctx["last_action"] = "escalation_offered"
        return {
            "response": ESCALATION_MESSAGE,
            "action": "handoff",
            "metadata": {"escalation_offered": True, "service_area": "other"},
            "handoff_data": {
                "conversation_id": conversation_id,
                "service_area": "other",
                "category": "other",
                "urgency": "medium",
                "message_count": len(conversation_history) + 1,
            },
            "conversation_context": ctx,
        }

    # Generate AI response (existing behaviour)
    response, metadata = await generate_ai_response(
        message, conversation_history, client_context
    )
    return {
        "response": response,
        "action": "respond",
        "metadata": metadata,
        "conversation_context": ctx,
    }


# ============================================================================
# WHATSAPP LINK GENERATOR
# ============================================================================

def generate_whatsapp_link(
    conversation_id: str,
    crn: Optional[str] = None,
    summary: Optional[str] = None
) -> str:
    """Generate WhatsApp link with prefilled message."""
    
    # Get WhatsApp number from environment, remove spaces and +
    whatsapp_number = SUPPORT_WHATSAPP.replace(" ", "").replace("+", "")
    
    message_parts = [
        f"Hi Pleerity, my reference is {conversation_id}"
    ]
    
    if crn:
        message_parts.append(f"CRN: {crn}")
    
    if summary:
        message_parts.append(f"Summary: {summary[:100]}")
    
    message = " ".join(message_parts)
    
    # URL encode the message
    import urllib.parse
    encoded_message = urllib.parse.quote(message)
    
    return f"https://wa.me/{whatsapp_number}?text={encoded_message}"


# ============================================================================
# CANNED RESPONSES FOR QUICK ACTIONS
# ============================================================================

CANNED_RESPONSES = {
    "check_order_status": {
        "trigger": "check_order_status",
        "response": """To check your order status, I need your **Order Reference Number** (e.g., PLE-CVP-2026-XXXXX).

You can find this in:
• Your confirmation email
• Your account dashboard under "My Orders"

Please share your order reference and I'll look it up for you. Or if you're logged in, visit your dashboard to see all your orders.""",
        "action": "respond",
        "metadata": {"canned": True, "category": "documents"}
    },
    
    "reset_password": {
        "trigger": "reset_password",
        "response": """To reset your password:

1. **Self-service:** On the client sign-in page, click **Forgot password?**, enter your email, and we'll send you a link to set a new password.
2. **Or contact your account administrator**—they can send you a new setup link from the Compliance Vault Pro admin portal.
3. Once you receive the email, click the link and set your new password. Links expire after 1 hour.

Need more help? I can connect you with a human agent.""",
        "action": "respond",
        "metadata": {"canned": True, "category": "login"}
    },
    
    "document_packs_info": {
        "trigger": "document_packs_info",
        "response": """**📄 Document Packs Pricing:**

| Pack | Documents | Price |
|------|-----------|-------|
| **Essential** | 5 core documents | £29 |
| **Tenancy** | 10 docs inc. AST | £49 |
| **Ultimate** | 15 comprehensive | £79 |

**Add-ons:**
• ⚡ Fast Track (24hr delivery): +£20
• 📬 Printed Copy (Royal Mail): +£25

**Standard delivery:** 48 hours

Ready to order? Visit our **Services** page or ask me any questions!""",
        "action": "respond",
        "metadata": {"canned": True, "category": "documents", "service_area": "document_services"}
    },
    
    "billing_help": {
        "trigger": "billing_help",
        "response": """**💳 Billing & Payment Help:**

**Common questions:**

**Q: What payment methods do you accept?**
All major credit/debit cards via Stripe (secure & PCI-compliant).

**Q: How do I get an invoice?**
Invoices are emailed automatically. Also available in your dashboard under Billing.

**Q: Can I cancel my subscription?**
Yes! Go to Account Settings → Billing → Cancel. Access continues until period end.

**Q: Refund policy?**
Case-by-case basis. Contact support with your order reference.

**Q: How do I update my payment card?**
Dashboard → Billing → Update Payment Method.

Need to discuss something specific? I can connect you with our billing team.""",
        "action": "respond",
        "metadata": {"canned": True, "category": "billing", "service_area": "billing"}
    },
    
    "cvp_info": {
        "trigger": "cvp_info",
        "response": None,  # Built dynamically in get_canned_response from plan_registry + _chatbot_app_base()
        "action": "respond",
        "metadata": {"canned": True, "category": "compliance", "service_area": "cvp"}
    },
    
    "speak_to_human": {
        "trigger": "speak_to_human",
        "response": """I'll connect you with a human agent. You have three options:

1. **💬 Live Chat** - Chat with an agent now (Mon-Fri 9am-6pm GMT)
2. **📧 Email Ticket** - We'll respond within 24 hours
3. **📱 WhatsApp** - Continue on WhatsApp with your reference

Which would you prefer?""",
        "action": "handoff",
        "metadata": {"canned": True, "category": "other"}
    },
    "pricing": {
        "trigger": "pricing",
        "response": None,  # Built in get_canned_response from guided knowledge
        "action": "respond",
        "metadata": {"canned": True, "category": "billing", "service_area": "pricing"}
    },
}


def get_canned_response(trigger: str) -> Optional[Dict[str, Any]]:
    """Get a canned response by trigger name. CVP info uses live pricing and frontend link; reset_password uses live sign-in link. Adds 'actions' for clickable links in UI."""
    out = CANNED_RESPONSES.get(trigger)
    if not out:
        return None
    out = dict(out)
    if trigger == "cvp_info" and out.get("response") is None:
        cvp_pricing = _get_cvp_pricing_from_registry()
        out["response"] = f"""**🏠 Compliance Vault Pro (CVP):**

Your complete property compliance management platform.

**Features:**
✅ Property compliance tracking & monitoring
✅ Certificate expiry alerts
✅ Document storage & management
✅ Compliance scoring & risk assessment
✅ Multi-property portfolio view
✅ Council licensing tracking

**Current pricing:** {cvp_pricing}

**Ideal for:** HMO landlords and portfolio managers who need to stay compliant."""
        out["actions"] = _get_guided_actions("compliance_vault_pro")
    elif trigger == "pricing":
        guided = build_guided_response("pricing", None)
        out["response"] = _trim_action_lines(guided) if _get_guided_actions("pricing") else guided
        out["actions"] = _get_guided_actions("pricing")
    elif trigger == "reset_password":
        out["response"] = """To reset your password:

1. **Self-service:** On the client sign-in page, click **Forgot password?**, enter your email, and we'll send you a link to set a new password.
2. **Or contact your account administrator**—they can send you a new setup link from the Compliance Vault Pro admin portal.
3. Once you receive the email, click the link and set your new password. Links expire after 1 hour.

Need more help? I can connect you with a human agent."""
        out["actions"] = [
            {"label": "Sign in", "url": f"{_chatbot_app_base()}/login/client"},
            {"label": "Talk to support", "url": None},
        ]
    return out


def get_all_quick_actions() -> List[Dict[str, Any]]:
    """Get list of available quick actions for the chat widget. Start New Chat is client-side only."""
    return [
        {"id": "cvp_info", "label": "Compliance Vault Pro", "icon": "🏠", "description": "CVP features"},
        {"id": "document_packs_info", "label": "Document Packs", "icon": "📄", "description": "Pricing & info"},
        {"id": "pricing", "label": "Pricing", "icon": "💳", "description": "Plans and pricing"},
        {"id": "reset_password", "label": "Reset Password", "icon": "🔑", "description": "Password help"},
        {"id": "speak_to_human", "label": "Talk to Support", "icon": "👤", "description": "Get human help"},
        {"id": "check_order_status", "label": "Check Order Status", "icon": "📦", "description": "Look up your order"},
        {"id": "billing_help", "label": "Billing Help", "icon": "💳", "description": "Payment questions"},
    ]
