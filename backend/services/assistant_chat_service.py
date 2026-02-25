"""
Compliance Vault Assistant chat flow: conversation/message storage, retrieval, LLM with
citations + safety_flags, post-process guardrails, audit. Used by POST /api/assistant/chat
and POST /api/admin/assistant/chat only.
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction
from utils import ai_config
from utils.audit import create_audit_log

from services.assistant_retrieval_service import get_portal_facts, get_kb_snippets
from services.assistant_prompt import ASSISTANT_SYSTEM_PROMPT, get_portal_urls

logger = logging.getLogger(__name__)

CHAT_PROMPT_VERSION = "v1"

# Keywords that suggest user wants human handover (task: human, complaint, refund, legal, cancel)
ESCALATION_KEYWORDS = re.compile(
    r"\b(human|complaint|refund|legal|cancel|speak to (a )?person|talk to (a )?person|"
    r"real person|live agent|transfer (me )?to|escalat)\b",
    re.I,
)


def _should_suggest_handover(message: str) -> bool:
    """True if user message suggests they want human support."""
    return bool(message and ESCALATION_KEYWORDS.search(message.strip()))

# Phrases that must not appear in assistant output (compliance verdict / legal)
VERDICT_BLOCK_PATTERNS = [
    re.compile(r"\byou\s+are\s+compliant\b", re.I),
    re.compile(r"\byou\s+are\s+non[- ]?compliant\b", re.I),
    re.compile(r"\byou\s+are\s+legally\s+required\s+to\b", re.I),
    re.compile(r"\bthis\s+guarantees\s+compliance\b", re.I),
    re.compile(r"\byou\s+will\s+be\s+fined\b", re.I),
    re.compile(r"\bthis\s+is\s+illegal\b", re.I),
]

SAFE_FALLBACK_ANSWER = (
    "I can help, but I need you to rephrase. I can only describe what your portal currently shows "
    "and suggest actions (e.g. upload a document, book an inspection). "
    "I don't provide legal advice or compliance verdicts. What would you like to know about your data?"
)

# System prompt is in services.assistant_prompt (ASSISTANT_SYSTEM_PROMPT) for single source of truth.
# CHAT_SYSTEM_PROMPT kept as alias for any code that still references it.
CHAT_SYSTEM_PROMPT = ASSISTANT_SYSTEM_PROMPT


def _rewrite_compliance_verdict_language(text: str) -> str:
    """If verdict-like phrases detected, rewrite to safe wording."""
    if not text or not text.strip():
        return text
    out = text
    for pat in VERDICT_BLOCK_PATTERNS:
        if pat.search(out):
            out = re.sub(
                pat,
                "The portal shows the following; this is not a legal judgment. For legal advice please consult a qualified adviser.",
                out,
                flags=re.I,
            )
    return out


def _parse_chat_response(raw: str) -> Dict[str, Any]:
    """Parse LLM JSON; return dict with answer, citations, safety_flags or None on failure."""
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    try:
        data = json.loads(raw)
        answer = data.get("answer") or ""
        citations = data.get("citations")
        if not isinstance(citations, list):
            citations = []
        safety_flags = data.get("safety_flags")
        if not isinstance(safety_flags, dict):
            safety_flags = {"legal_advice_request": False, "missing_data": False}
        return {"answer": answer, "citations": citations, "safety_flags": safety_flags}
    except (json.JSONDecodeError, TypeError):
        return None


async def _ensure_conversation(
    db,
    client_id: str,
    created_by_user_id: str,
    conversation_id: Optional[str],
) -> str:
    """Create or return existing conversation_id."""
    if conversation_id:
        conv = await db.assistant_conversations.find_one(
            {"conversation_id": conversation_id, "client_id": client_id},
            {"conversation_id": 1},
        )
        if conv:
            await db.assistant_conversations.update_one(
                {"conversation_id": conversation_id},
                {"$set": {"last_activity_at": datetime.now(timezone.utc).isoformat()}},
            )
            return conversation_id
    new_id = f"conv-{uuid.uuid4().hex[:14]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.assistant_conversations.insert_one({
        "conversation_id": new_id,
        "client_id": client_id,
        "created_by_user_id": created_by_user_id,
        "created_at": now,
        "last_activity_at": now,
        "escalated": False,
    })
    return new_id


async def chat_turn(
    client_id: str,
    user_id: str,
    message: str,
    conversation_id: Optional[str] = None,
    property_id: Optional[str] = None,
    is_admin: bool = False,
) -> Dict[str, Any]:
    """
    One assistant chat turn. Uses portal_facts + kb_snippets, LLM, guardrails, storage, audit.
    Returns: { conversation_id, answer, citations, safety_flags } or error dict.
    """
    db = database.get_db()
    conv_id = await _ensure_conversation(db, client_id, user_id, conversation_id)
    now = datetime.now(timezone.utc).isoformat()

    # Store user message
    await db.assistant_messages.insert_one({
        "message_id": f"msg-{uuid.uuid4().hex[:12]}",
        "conversation_id": conv_id,
        "client_id": client_id,
        "user_id": user_id,
        "role": "user",
        "message": message,
        "created_at": now,
    })

    # Audit request
    await create_audit_log(
        action=AuditAction.ASSISTANT_CHAT_REQUESTED,
        actor_id=user_id,
        client_id=client_id,
        resource_type="assistant_conversation",
        resource_id=conv_id,
        metadata={"message_length": len(message), "property_id": property_id, "is_admin": is_admin},
    )

    # When AI is disabled, return without calling any LLM (no env vars required).
    if not ai_config.AI_ENABLED:
        answer = "Assistant is currently disabled. Enable AI in configuration to use the assistant."
        await create_audit_log(
            action=AuditAction.ASSISTANT_CHAT_RESPONDED,
            actor_id=user_id,
            client_id=client_id,
            resource_type="assistant_conversation",
            resource_id=conv_id,
            metadata={"answer_preview": answer[:200], "ai_disabled": True},
        )
        await db.assistant_messages.insert_one({
            "message_id": f"msg-{uuid.uuid4().hex[:12]}",
            "conversation_id": conv_id,
            "client_id": client_id,
            "user_id": user_id,
            "role": "assistant",
            "message": answer,
            "citations": [],
            "safety_flags": {"legal_advice_request": False, "missing_data": False},
            "model": None,
            "prompt_version": CHAT_PROMPT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"conversation_id": conv_id, "answer": answer, "citations": [], "safety_flags": {"legal_advice_request": False, "missing_data": False}, "handover_suggested": _should_suggest_handover(message)}

    # When AI enabled but not configured (e.g. missing OPENAI_API_KEY), route should 503; guard here too.
    if not ai_config.is_configured() or ai_config.AI_PROVIDER != "openai":
        await create_audit_log(
            action=AuditAction.ASSISTANT_CHAT_ERROR,
            actor_id=user_id,
            client_id=client_id,
            resource_type="assistant_conversation",
            resource_id=conv_id,
            metadata={"error": "AI not configured or provider not openai"},
        )
        return {
            "conversation_id": conv_id,
            "answer": "Assistant is temporarily unavailable.",
            "citations": [],
            "safety_flags": {"legal_advice_request": False, "missing_data": False},
            "handover_suggested": _should_suggest_handover(message),
        }

    # Retrieval
    portal_facts = await get_portal_facts(
        client_id,
        "admin" if is_admin else "client",
        property_id=property_id,
        portal_user_id=user_id or None,
    )
    if portal_facts.get("error"):
        await create_audit_log(
            action=AuditAction.ASSISTANT_CHAT_ERROR,
            actor_id=user_id,
            client_id=client_id,
            resource_type="assistant_conversation",
            resource_id=conv_id,
            metadata={"error": portal_facts["error"]},
        )
        return {
            "conversation_id": conv_id,
            "answer": "I couldn't load your portal data. Please try again or contact support.",
            "citations": [],
            "safety_flags": {"legal_advice_request": False, "missing_data": True},
            "handover_suggested": _should_suggest_handover(message),
        }

    kb_snippets = get_kb_snippets(message)
    portal_urls = get_portal_urls()
    context = f"""Portal facts (use only this data for the user's account):
{json.dumps(portal_facts, indent=2, default=str)}

Portal URLs (use ONLY these when linking to the portal; do not invent or alter URLs):
{json.dumps(portal_urls, indent=2)}

Knowledge base snippets:
{chr(10).join(f"--- {s.get('title', '')} ({s.get('source_id', '')}) ---{chr(10)}{s.get('content', '')}" for s in kb_snippets)}

User message: {message}

Respond with ONLY the JSON object (answer, citations, safety_flags). No other text."""

    model_name = ai_config.AI_MODEL
    try:
        from utils.llm_chat import chat_openai
    except ImportError:
        logger.warning("utils.llm_chat chat_openai not available")
        await create_audit_log(
            action=AuditAction.ASSISTANT_CHAT_ERROR,
            actor_id=user_id,
            client_id=client_id,
            resource_type="assistant_conversation",
            resource_id=conv_id,
            metadata={"error": "LLM not configured"},
        )
        return {
            "conversation_id": conv_id,
            "answer": "Assistant is temporarily unavailable.",
            "citations": [],
            "safety_flags": {"legal_advice_request": False, "missing_data": False},
            "handover_suggested": _should_suggest_handover(message),
        }

    try:
        raw = await chat_openai(
            system_prompt=ASSISTANT_SYSTEM_PROMPT,
            user_text=context,
        )
    except Exception as e:
        logger.exception("Assistant chat LLM error: %s", e)
        await create_audit_log(
            action=AuditAction.ASSISTANT_CHAT_ERROR,
            actor_id=user_id,
            client_id=client_id,
            resource_type="assistant_conversation",
            resource_id=conv_id,
            metadata={"error": str(e)[:500]},
        )
        return {
            "conversation_id": conv_id,
            "answer": "Assistant is temporarily unavailable. Please try again.",
            "citations": [],
            "safety_flags": {"legal_advice_request": False, "missing_data": False},
            "handover_suggested": _should_suggest_handover(message),
        }

    parsed = _parse_chat_response(raw)
    if not parsed:
        answer = SAFE_FALLBACK_ANSWER
        citations = []
        safety_flags = {"legal_advice_request": False, "missing_data": False}
    else:
        answer = parsed.get("answer") or SAFE_FALLBACK_ANSWER
        citations = list(parsed.get("citations") or [])
        safety_flags = parsed.get("safety_flags") or {}
        # Ensure KB-derived guidance has a citation
        citation_ids = {c.get("source_id") for c in citations if c.get("source_id")}
        for s in kb_snippets:
            sid = s.get("source_id")
            if sid and sid not in citation_ids:
                citations.append({"source_type": "kb", "source_id": sid, "title": s.get("title", "")})
                citation_ids.add(sid)
        answer = _rewrite_compliance_verdict_language(answer)
        if safety_flags.get("legal_advice_request"):
            await create_audit_log(
                action=AuditAction.ASSISTANT_CHAT_REFUSED_LEGAL,
                actor_id=user_id,
                client_id=client_id,
                resource_type="assistant_conversation",
                resource_id=conv_id,
                metadata={"answer_preview": answer[:200]},
            )
        else:
            await create_audit_log(
                action=AuditAction.ASSISTANT_CHAT_RESPONDED,
                actor_id=user_id,
                client_id=client_id,
                resource_type="assistant_conversation",
                resource_id=conv_id,
                metadata={"answer_preview": answer[:200], "model": model_name, "prompt_version": CHAT_PROMPT_VERSION},
            )

    # Store assistant message
    await db.assistant_messages.insert_one({
        "message_id": f"msg-{uuid.uuid4().hex[:12]}",
        "conversation_id": conv_id,
        "client_id": client_id,
        "user_id": user_id,
        "role": "assistant",
        "message": answer,
        "citations": citations,
        "safety_flags": safety_flags,
        "model": model_name,
        "prompt_version": CHAT_PROMPT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "conversation_id": conv_id,
        "answer": answer,
        "citations": citations,
        "safety_flags": safety_flags,
        "handover_suggested": _should_suggest_handover(message),
    }


async def get_assistant_transcript(conversation_id: str, client_id: str) -> str:
    """Build a plain-text transcript of assistant conversation for support."""
    db = database.get_db()
    cursor = db.assistant_messages.find(
        {"conversation_id": conversation_id, "client_id": client_id},
        {"_id": 0, "role": 1, "message": 1, "created_at": 1},
    ).sort("created_at", 1)
    messages = await cursor.to_list(length=500)
    lines = []
    for msg in messages:
        role = (msg.get("role") or "user").upper()
        ts = (msg.get("created_at") or "")[:19].replace("T", " ")
        text = (msg.get("message") or "").strip()
        lines.append(f"[{ts}] {role}: {text}")
    return "\n".join(lines) if lines else "(No messages)"


async def escalate_assistant_conversation(
    conversation_id: str,
    client_id: str,
    user_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mark assistant conversation as escalated, create support ticket with full transcript,
    notify support dashboard. Returns { escalated, ticket_id?, message } or error dict.
    """
    db = database.get_db()
    conv = await db.assistant_conversations.find_one(
        {"conversation_id": conversation_id, "client_id": client_id},
        {"conversation_id": 1, "escalated": 1},
    )
    if not conv:
        return {"error": "Conversation not found", "escalated": False}
    if conv.get("escalated"):
        return {"escalated": True, "message": "Already escalated to support."}

    now = datetime.now(timezone.utc).isoformat()
    transcript = await get_assistant_transcript(conversation_id, client_id)
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "email": 1, "customer_reference": 1},
    )
    client_email = (client or {}).get("email") or ""
    client_crn = (client or {}).get("customer_reference") or ""

    await db.assistant_conversations.update_one(
        {"conversation_id": conversation_id, "client_id": client_id},
        {
            "$set": {
                "escalated": True,
                "escalation_reason": reason or "User requested human",
                "escalated_at": now,
            }
        },
    )

    from services.support_service import (
        TicketService,
        TicketCreate,
        ServiceArea,
        TicketCategory,
        TicketPriority,
        ContactMethod,
    )
    from services.support_email_service import send_internal_ticket_notification

    subject = "Portal Assistant escalation"
    description = f"User requested human handover from Portal Assistant.\nConversation ID: {conversation_id}\nClient ID: {client_id}\n\n--- Transcript ---\n{transcript}"
    ticket_data = TicketCreate(
        subject=subject,
        description=description,
        category=TicketCategory.OTHER,
        priority=TicketPriority.MEDIUM,
        contact_method=ContactMethod.EMAIL,
        service_area=ServiceArea.CVP,
        email=client_email or None,
        crn=client_crn or None,
    )
    ticket = await TicketService.create_ticket(ticket_data, conversation_id=None)
    internal_sent = await send_internal_ticket_notification(
        ticket_id=ticket["ticket_id"],
        customer_email=client_email,
        customer_crn=client_crn,
        subject=subject,
        description=description,
        category=ticket_data.category.value,
        priority=ticket_data.priority.value,
        service_area=ticket_data.service_area.value,
        transcript=transcript,
    )
    await create_audit_log(
        action=AuditAction.ASSISTANT_ESCALATED,
        actor_id=user_id,
        client_id=client_id,
        resource_type="assistant_conversation",
        resource_id=conversation_id,
        metadata={"ticket_id": ticket["ticket_id"], "reason": reason},
    )
    return {
        "escalated": True,
        "ticket_id": ticket["ticket_id"],
        "message": "Support has been notified. We'll be in touch shortly.",
    }
