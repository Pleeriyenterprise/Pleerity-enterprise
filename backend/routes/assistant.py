import os
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from database import database
from middleware import client_route_guard
from middleware.capability_gating import capability_denied_http_detail
from services.account_capability_enforcement import CapabilityEnforcementService
from services.assistant_service import assistant_service
from services.assistant_chat_service import (
    chat_turn as assistant_chat_turn,
    escalate_assistant_conversation,
)
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from utils import ai_config
from config.security_limits import security_limits
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant", tags=["assistant"])

# Rate limits: per user 20/10min, per client 100/day (env)
ASSISTANT_CHAT_PER_USER_PER_10MIN = 20
ASSISTANT_CHAT_CLIENT_PER_DAY = int(os.getenv("ASSISTANT_RATE_LIMIT_CLIENT_PER_DAY", "100"))


def _client_ip_assistant(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


async def _enforce_capability(user: Dict[str, Any], capability_id: str, action: str) -> None:
    if user.get("role") == "ROLE_OWNER":
        return
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    decision = await CapabilityEnforcementService(database.get_db()).evaluate(
        client_id, capability_id, action
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=capability_denied_http_detail(decision))


async def _require_assistant_read(request: Request) -> Dict[str, Any]:
    user = await client_route_guard(request)
    await _enforce_capability(user, "CAP_AI_ASSISTANT", "read")
    return user


async def _require_assistant_write(request: Request) -> Dict[str, Any]:
    user = await client_route_guard(request)
    await _enforce_capability(user, "CAP_AI_ASSISTANT", "write")
    return user


async def _enforce_assistant_ip_rate(request: Request) -> None:
    ip = _client_ip_assistant(request)
    ok, msg = await rate_limiter.check_rate_limit(
        f"assistant_ip:{ip}",
        security_limits.assistant_per_ip_per_hour,
        60,
    )
    if not ok:
        log_rate_limit_event("assistant_ip", ip, ip)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            metadata={"scope": "assistant_ip", "ip": ip},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=msg or "Too many assistant requests from this network. Try again shortly.",
        )


class AskQuestionRequest(BaseModel):
    question: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    property_id: Optional[str] = None


class EscalateRequest(BaseModel):
    conversation_id: str
    reason: Optional[str] = None


class AssistantResponse(BaseModel):
    """Structured response from the AI assistant."""
    answer: str
    what_this_is_based_on: list = []
    next_actions: list = []
    refused: bool = False
    refusal_reason: str = None
    correlation_id: str = None


@router.get("/snapshot")
async def get_snapshot(request: Request):
    """Get sanitized data snapshot for assistant context (read-only).
    
    This endpoint provides the same data the client already sees in their dashboard,
    formatted for AI assistant context.
    """
    user = await _require_assistant_read(request)
    await _enforce_assistant_ip_rate(request)

    try:
        snapshot = await assistant_service.get_client_snapshot(user["client_id"])
        return snapshot
    
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve snapshot"
        )


@router.post("/ask", response_model=AssistantResponse)
async def ask_question(request: Request, data: AskQuestionRequest):
    """Ask assistant a question about compliance data (read-only).
    
    The assistant can only explain existing data. It cannot create, modify,
    or trigger any actions.
    
    Returns structured response with:
    - answer: Main response text
    - what_this_is_based_on: List of data points used
    - next_actions: Recommended portal actions
    - correlation_id: For support/debugging
    """
    user = await _require_assistant_write(request)
    await _enforce_assistant_ip_rate(request)

    try:
        # Rate limiting - 10 questions per 10 minutes per client
        allowed, error_msg = await rate_limiter.check_rate_limit(
            key=f"assistant_{user['client_id']}",
            max_attempts=10,
            window_minutes=10
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        # Validate question
        if not data.question or len(data.question.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty"
            )
        
        if len(data.question) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question too long (max 500 characters)"
            )
        
        # Process question
        result = await assistant_service.ask_question(
            client_id=user["client_id"],
            actor_id=user["portal_user_id"],
            question=data.question
        )
        
        return AssistantResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assistant ask error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assistant unavailable. Please try again or refresh."
        )


@router.post("/chat")
async def post_chat(request: Request, data: ChatRequest):
    """
    Compliance Vault Assistant chat: grounded in portal data + KB, citations, safety_flags.
    Requires authenticated portal user. CRN in message is ignored; client_id from auth only.
    """
    user = await _require_assistant_write(request)
    await _enforce_assistant_ip_rate(request)
    client_id = user["client_id"]
    user_id = user.get("portal_user_id") or user.get("client_id", "")

    if not data.message or len(data.message.strip()) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")
    if len(data.message) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message too long (max 2000 characters)")

    allowed_user, err_user = await rate_limiter.check_rate_limit(
        key=f"assistant_chat_user_{user_id}",
        max_attempts=ASSISTANT_CHAT_PER_USER_PER_10MIN,
        window_minutes=10,
    )
    if not allowed_user:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_user)

    allowed_client, err_client = await rate_limiter.check_rate_limit_daily(
        key=f"assistant_chat_client_{client_id}",
        max_attempts=ASSISTANT_CHAT_CLIENT_PER_DAY,
    )
    if not allowed_client:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_client)

    if ai_config.AI_ENABLED and not ai_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "AI_NOT_CONFIGURED", "detail": "AI service not configured. Set OPENAI_API_KEY when AI_ENABLED=true."},
        )

    result = await assistant_chat_turn(
        client_id=client_id,
        user_id=user_id,
        message=data.message.strip(),
        conversation_id=data.conversation_id,
        property_id=data.property_id,
        is_admin=False,
    )
    return result


@router.post("/escalate")
async def post_escalate(request: Request, data: EscalateRequest):
    """
    Escalate assistant conversation to human support. Marks session escalated,
    creates support ticket with full transcript, notifies support dashboard.
    """
    user = await _require_assistant_write(request)
    await _enforce_assistant_ip_rate(request)
    client_id = user["client_id"]
    user_id = user.get("portal_user_id") or user.get("client_id", "")

    if not data.conversation_id or not data.conversation_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conversation_id is required",
        )

    result = await escalate_assistant_conversation(
        conversation_id=data.conversation_id.strip(),
        client_id=client_id,
        user_id=user_id,
        reason=data.reason,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )
    return result


@router.get("/conversation/{conversation_id}/status")
async def get_conversation_status(request: Request, conversation_id: str):
    """Return escalation status for a conversation (for portal UI: Escalated / Support joined)."""
    user = await _require_assistant_read(request)
    db = database.get_db()
    conv = await db.assistant_conversations.find_one(
        {"conversation_id": conversation_id, "client_id": user["client_id"]},
        {"_id": 0, "escalated": 1, "escalation_reason": 1, "escalated_at": 1},
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return {
        "conversation_id": conversation_id,
        "escalated": conv.get("escalated", False),
        "escalation_reason": conv.get("escalation_reason"),
        "escalated_at": conv.get("escalated_at"),
    }


