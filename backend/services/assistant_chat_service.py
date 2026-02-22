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

logger = logging.getLogger(__name__)

CHAT_PROMPT_VERSION = "v1"

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

CHAT_SYSTEM_PROMPT = """You are the Compliance Vault Pro Assistant. You explain what the portal shows only. You do NOT provide legal advice, legal interpretation, or compliance verdicts.

Rules:
- Use ONLY the provided portal_facts and kb_snippets. Never invent data.
- Do not say "you are compliant", "you are non-compliant", "you are legally required to", or predict fines/enforcement.
- If data is missing, say what is missing and suggest actions (e.g. upload document, book inspection).
- If the user asks for a legal verdict or legal advice, set safety_flags.legal_advice_request to true and give a polite refusal plus what you can show from the portal.
- Cite sources: for each fact from portal_facts use source_type "portal_data" and a source_id like "property:PROP_ID" or "client_summary"; for KB use source_type "kb" and source_id like "assistant_kb/filename.md".

Respond with ONLY valid JSON in this exact shape (no markdown, no extra text):
{
  "answer": "Your response text here",
  "citations": [
    {"source_type": "portal_data", "source_id": "property:abc123", "title": "Property nickname status"},
    {"source_type": "kb", "source_id": "assistant_kb/certificates_overview.md", "title": "Certificates overview"}
  ],
  "safety_flags": {
    "legal_advice_request": false,
    "missing_data": false
  }
}
"""


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
        return {"conversation_id": conv_id, "answer": answer, "citations": [], "safety_flags": {"legal_advice_request": False, "missing_data": False}}

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
        }

    # Retrieval
    portal_facts = await get_portal_facts(client_id, "admin" if is_admin else "client", property_id=property_id)
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
        }

    kb_snippets = get_kb_snippets(message)
    context = f"""Portal facts (use only this data for the user's account):
{json.dumps(portal_facts, indent=2, default=str)}

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
        }

    try:
        raw = await chat_openai(
            system_prompt=CHAT_SYSTEM_PROMPT,
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
        }

    parsed = _parse_chat_response(raw)
    if not parsed:
        answer = SAFE_FALLBACK_ANSWER
        citations = []
        safety_flags = {"legal_advice_request": False, "missing_data": False}
    else:
        answer = parsed.get("answer") or SAFE_FALLBACK_ANSWER
        citations = parsed.get("citations") or []
        safety_flags = parsed.get("safety_flags") or {}
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
    }
