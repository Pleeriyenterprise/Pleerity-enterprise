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

# ============================================================================
# KNOWLEDGE BASE - Pleerity Services Information
# ============================================================================

KNOWLEDGE_BASE = {
    "company": {
        "name": "Pleerity Enterprise Ltd",
        "tagline": "Property compliance and business services for landlords and property managers",
        "support_email": SUPPORT_EMAIL,
        "support_hours": "24/7 via chatbot, Live agents Mon-Fri 9am-6pm GMT",
        "whatsapp": SUPPORT_WHATSAPP,
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
            "pricing": "£9.99/month + £49.99 setup fee",
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
            "answer": "Click 'Forgot Password' on the login page, enter your email, and follow the reset link sent to your inbox. If you don't receive it, check your spam folder or contact support.",
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
# SERVICE ROUTING
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
    
    # Find client by CRN
    client = await db["clients"].find_one(
        {"crn": crn.upper()},
        {"_id": 0, "email": 1, "name": 1, "subscription_status": 1, "created_at": 1}
    )
    
    if not client:
        return None
    
    # Verify email matches (case-insensitive)
    if client.get("email", "").lower() != email.lower():
        return None
    
    # Return sanitized summary only
    return {
        "verified": True,
        "account_status": client.get("subscription_status", "unknown"),
        "member_since": client.get("created_at", "")[:10] if client.get("created_at") else "N/A",
        "name_initial": client.get("name", "?")[0].upper() if client.get("name") else "?",
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
        "name": client.get("name"),
        "email": client.get("email"),
        "crn": client.get("crn"),
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
    Generate AI response using Gemini via Emergent LLM Key.
    Returns (response_text, metadata).
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        if not emergent_key:
            logger.warning("EMERGENT_LLM_KEY not set, using fallback response")
            return await generate_fallback_response(message, client_context)
        
        # Build system message
        system_parts = [
            "You are Pleerity Support, a helpful AI assistant for Pleerity Enterprise Ltd.",
            "You help customers with: Compliance Vault Pro, Document Packs, AI Automation, Market Research, and general account queries.",
            "",
            "IMPORTANT RULES:",
            "1. NEVER provide legal advice, interpret legislation, or predict council enforcement.",
            "2. Be helpful, professional, and concise.",
            "3. If you can't help, offer to connect them with a human agent.",
            "4. For account-specific queries, ask for their CRN (Customer Reference Number).",
            "",
            "KNOWLEDGE BASE:",
            json.dumps(KNOWLEDGE_BASE, indent=2),
        ]
        
        if client_context:
            system_parts.extend([
                "",
                "CUSTOMER CONTEXT (authenticated):",
                json.dumps(client_context, indent=2),
            ])
        
        # Initialize chat
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"support-{message[:20]}",
            system_message="\n".join(system_parts)
        ).with_model("gemini", "gemini-2.0-flash")
        
        # Build conversation context
        context_text = ""
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = "Customer" if msg.get("sender") == "user" else "Assistant"
            context_text += f"{role}: {msg.get('message_text', '')}\n"
        
        prompt = f"""Previous conversation:
{context_text}

Customer's new message: {message}

Respond helpfully and concisely. If you don't know something specific to their account, acknowledge it and offer alternatives."""
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
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
    for faq in KNOWLEDGE_BASE["faqs"]:
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

async def handle_chat_message(
    conversation_id: str,
    message: str,
    conversation_history: List[Dict[str, Any]],
    client_context: Optional[Dict[str, Any]] = None,
    is_authenticated: bool = False
) -> Dict[str, Any]:
    """
    Main chat handler - processes message and returns response.
    
    Returns:
    {
        "response": str,
        "action": "respond" | "handoff" | "lookup_prompt" | "ticket_created",
        "metadata": {...},
        "handoff_data": {...} (if action is handoff)
    }
    """
    
    # Check for legal advice request
    if is_legal_advice_request(message):
        return {
            "response": LEGAL_REFUSAL_RESPONSE,
            "action": "respond",
            "metadata": {
                "legal_refusal": True,
                "service_area": "other",
                "category": "other",
            }
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
            "metadata": {
                "service_area": service_area,
                "category": category,
                "urgency": urgency,
            },
            "handoff_data": {
                "conversation_id": conversation_id,
                "service_area": service_area,
                "category": category,
                "urgency": urgency,
                "message_count": len(conversation_history) + 1,
            }
        }
    
    # Generate AI response
    response, metadata = await generate_ai_response(
        message,
        conversation_history,
        client_context
    )
    
    return {
        "response": response,
        "action": "respond",
        "metadata": metadata
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

1. Go to the **Login page**
2. Click **"Forgot Password"**
3. Enter your registered email address
4. Check your inbox (and spam folder) for the reset link
5. Click the link and create a new password

The reset link expires in 24 hours. If you don't receive the email within 5 minutes, try again or contact support.

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
        "response": """**🏠 Compliance Vault Pro (CVP):**

Your complete property compliance management platform.

**Features:**
✅ Property compliance tracking & monitoring
✅ Certificate expiry alerts
✅ Document storage & management
✅ Compliance scoring & risk assessment
✅ Multi-property portfolio view
✅ Council licensing tracking

**Pricing:** £9.99/month + £49.99 setup fee

**Ideal for:** HMO landlords and portfolio managers who need to stay compliant.

Would you like to get started or learn more about specific features?""",
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
}


def get_canned_response(trigger: str) -> Optional[Dict[str, Any]]:
    """Get a canned response by trigger name."""
    return CANNED_RESPONSES.get(trigger)


def get_all_quick_actions() -> List[Dict[str, Any]]:
    """Get list of available quick actions for the chat widget."""
    return [
        {
            "id": "check_order_status",
            "label": "Check Order Status",
            "icon": "📦",
            "description": "Look up your order"
        },
        {
            "id": "reset_password",
            "label": "Reset Password",
            "icon": "🔑",
            "description": "Password help"
        },
        {
            "id": "document_packs_info",
            "label": "Document Packs",
            "icon": "📄",
            "description": "Pricing & info"
        },
        {
            "id": "billing_help",
            "label": "Billing Help",
            "icon": "💳",
            "description": "Payment questions"
        },
        {
            "id": "cvp_info",
            "label": "Compliance Vault Pro",
            "icon": "🏠",
            "description": "CVP features"
        },
        {
            "id": "speak_to_human",
            "label": "Speak to Human",
            "icon": "👤",
            "description": "Get human help"
        },
    ]
