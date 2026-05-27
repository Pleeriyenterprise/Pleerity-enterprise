"""
Support System API Routes

Public endpoints:
- POST /api/support/chat - AI chatbot interaction
- POST /api/support/lookup - CRN+email verification lookup
- POST /api/support/ticket - Create support ticket

Authenticated client endpoints:
- GET /api/support/account-snapshot - Client-scoped account info
- GET /api/support/conversation/{id} - Get conversation history

Admin endpoints:
- GET /api/admin/support/conversations - List all conversations
- GET /api/admin/support/tickets - List all tickets
- GET /api/admin/support/conversation/{id} - Full conversation with transcript
- POST /api/admin/support/conversation/{id}/reply - Admin reply to conversation
- POST /api/admin/support/lookup-by-crn - Admin account lookup
- GET /api/admin/support/audit-log - View audit logs
- POST /api/admin/support/public-content/reindex - Rebuild public support content index (KC + allowlisted site)
- POST /api/admin/support/remediation-correlation-view - Stream C internal correlation (feature-flagged)
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timezone, timedelta
from middleware import require_support_or_above, client_route_guard, require_owner_or_admin, get_current_user
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from services.support_service import (
    ConversationService, MessageService, TicketService, SupportAuditService,
    ConversationCreate, MessageCreate, TicketCreate,
    ConversationChannel, UserIdentityType, MessageSender,
    ServiceArea, TicketCategory, TicketPriority, ContactMethod,
    TICKETS_COLLECTION, create_support_indexes
)
from services.support_chatbot import (
    handle_chat_message, lookup_account_by_crn, get_client_snapshot,
    is_legal_advice_request,
    detect_service_area, detect_category, detect_urgency,
    get_canned_response, get_all_quick_actions, CANNED_RESPONSES,
    build_public_handoff_options,
    format_handoff_intro_message,
)
from database import database
import logging
import os

logger = logging.getLogger(__name__)

SUPPORT_CHAT_RATE_LIMIT_MESSAGE = (
    "We're handling a high volume of messages right now. "
    "Please wait a moment before trying again — or use email ticket from the menu if it's urgent."
)

# Create routers
public_router = APIRouter(prefix="/api/support", tags=["support-public"])
client_router = APIRouter(prefix="/api/support", tags=["support-client"])
admin_router = APIRouter(prefix="/api/admin/support", tags=["admin-support"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    channel: str = "web"
    conversation_context: Optional[Dict[str, Any]] = None  # { intent, topic, last_action } for guided assistant


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    action: str  # respond, handoff, lookup_prompt
    metadata: Dict[str, Any] = {}
    handoff_options: Optional[Dict[str, Any]] = None
    conversation_context: Optional[Dict[str, Any]] = None  # updated context for next turn
    actions: Optional[List[Dict[str, Any]]] = None  # [{ label, url }] for clickable links in UI
    # Canonical handoff narrative for ticket prefill (also stored on conversation); not duplicated in metadata in API responses.
    handoff_summary: Optional[str] = None


class LookupRequest(BaseModel):
    crn: str = Field(..., min_length=10, max_length=25)
    email: EmailStr


class TicketRequest(BaseModel):
    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    category: str = "other"
    priority: str = "medium"
    service_area: str = "other"
    contact_method: str = "email"
    email: Optional[EmailStr] = None
    crn: Optional[str] = None
    conversation_id: Optional[str] = None


def build_public_ticket_created_response(
    *,
    ticket_id: str,
    conversation_id: Optional[str],
    transcript_included: bool,
    email_sent: bool,
    internal_notification_sent: bool,
) -> Dict[str, Any]:
    """
    User-facing ticket confirmation for public API and chat widget.
    Keeps ticket id, optional conversation id, channel/SLA, and transcript note aligned.
    """
    lines = [
        "Your support ticket has been created.",
        "",
        f"Ticket reference: **{ticket_id}**",
    ]
    if conversation_id:
        lines.append(f"Conversation reference: **{conversation_id}**")
    lines.extend(
        [
            "",
            "Our team will reply **by email** within **24 hours**.",
        ]
    )
    if transcript_included:
        lines.append("Your conversation transcript has been included.")
    elif conversation_id:
        lines.append(
            "A conversation was linked, but no transcript text was available yet."
        )
    else:
        lines.append("No chat transcript was linked to this ticket.")
    return {
        "success": True,
        "ticket_id": ticket_id,
        "conversation_id": conversation_id,
        "response_channel": "email",
        "response_window": "within 24 hours",
        "transcript_included": transcript_included,
        "message": "\n".join(lines),
        "email_sent": email_sent,
        "internal_notification_sent": internal_notification_sent,
    }


class AdminReplyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


class AdminCreateTicketFromConversationRequest(BaseModel):
    """Optional subject/description when creating a ticket from a conversation."""
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=5000)


class PublicContentReindexRequest(BaseModel):
    """Rebuild indexed chunks for public support assistant (no per-chat crawl)."""
    scope: Literal["kb", "site", "all"] = "kb"
    site_base_url: Optional[str] = None  # optional override for marketing origin


class AdminLookupRequest(BaseModel):
    crn: str


class RemediationCorrelationEntry(BaseModel):
    kind: Literal["gap_key", "issue_id", "work_order_id", "risk_signal_id"]
    value: str = Field(..., min_length=1, max_length=512)


class RemediationCorrelationViewRequest(BaseModel):
    """Stream C v1 — property-scoped read-only correlation (admin/support, feature-flagged)."""

    client_id: str = Field(..., min_length=1, max_length=128)
    property_id: str = Field(..., min_length=1, max_length=128)
    entry: RemediationCorrelationEntry
    as_of: Optional[str] = None
    window_half_days: int = Field(14, ge=1, le=31)


# ============================================================================
# PUBLIC ENDPOINTS
# ============================================================================

@public_router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: Request,
    body: ChatRequest
):
    """
    Public AI chatbot endpoint.
    Creates or continues a conversation.
    """
    try:
        client_ip = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        ip_key = f"support_chat:ip:{client_ip}"
        allowed_ip, _ = await rate_limiter.check_rate_limit(
            key=ip_key,
            max_attempts=45,
            window_minutes=10,
        )
        if not allowed_ip:
            log_rate_limit_event("support_chat", "ip", client_ip)
            await SupportAuditService.log_action(
                action="public_chat_rate_limited",
                actor_type="user",
                actor_id=None,
                resource_type="conversation",
                resource_id=body.conversation_id or "new",
                details={},
                ip_address=client_ip,
            )
            raise HTTPException(status_code=429, detail=SUPPORT_CHAT_RATE_LIMIT_MESSAGE)

        if body.conversation_id:
            conv_key = f"support_chat:conv:{body.conversation_id}"
            allowed_conv, _ = await rate_limiter.check_rate_limit(
                key=conv_key,
                max_attempts=80,
                window_minutes=10,
            )
            if not allowed_conv:
                log_rate_limit_event("support_chat", "conv", client_ip)
                await SupportAuditService.log_action(
                    action="public_chat_rate_limited",
                    actor_type="user",
                    actor_id=None,
                    resource_type="conversation",
                    resource_id=body.conversation_id,
                    details={"scope": "conversation"},
                    ip_address=client_ip,
                )
                raise HTTPException(status_code=429, detail=SUPPORT_CHAT_RATE_LIMIT_MESSAGE)

        # Get or create conversation
        if body.conversation_id:
            conversation = await ConversationService.get_conversation(body.conversation_id)
            if not conversation:
                # Create new if not found
                conv_data = ConversationCreate(
                    channel=ConversationChannel(body.channel),
                    user_identity_type=UserIdentityType.ANONYMOUS
                )
                conversation = await ConversationService.create_conversation(conv_data)
        else:
            conv_data = ConversationCreate(
                channel=ConversationChannel(body.channel),
                user_identity_type=UserIdentityType.ANONYMOUS
            )
            conversation = await ConversationService.create_conversation(conv_data)
        
        conversation_id = conversation["conversation_id"]
        
        # Save user message
        user_msg = MessageCreate(
            message_text=body.message,
            sender=MessageSender.USER
        )
        await MessageService.add_message(conversation_id, user_msg)
        
        # Get conversation history
        history = await MessageService.get_messages(conversation_id, limit=20)

        user = await get_current_user(request)
        client_id = (user or {}).get("client_id")
        snapshot = await get_client_snapshot(client_id) if client_id else None
        
        # Process message through chatbot (with optional conversation context for guided assistant)
        result = await handle_chat_message(
            conversation_id=conversation_id,
            message=body.message,
            conversation_history=history,
            client_context=snapshot,
            is_authenticated=bool(snapshot),
            conversation_context=body.conversation_context,
        )

        display_response = result["response"]
        handoff_opts = None
        if result["action"] == "handoff":
            handoff_opts = build_public_handoff_options(
                conversation_id=conversation_id,
                crn=conversation.get("crn"),
                message_snippet=body.message,
                transcript_summary=f"{len(history)} messages in conversation",
            )
            display_response = format_handoff_intro_message(handoff_opts)

        # Save bot response (include actions in metadata for history to show clickable links)
        bot_metadata = dict(result.get("metadata", {}))
        if result.get("actions"):
            bot_metadata["actions"] = result["actions"]
        bot_msg = MessageCreate(
            message_text=display_response,
            sender=MessageSender.BOT,
            metadata=bot_metadata
        )
        await MessageService.add_message(conversation_id, bot_msg)
        
        # Update conversation metadata + last structured assistant handoff (for ticket queue)
        hs = result.get("handoff_summary") or (result.get("metadata") or {}).get("handoff_summary")
        conv_updates: Dict[str, Any] = {
            "service_area": result.get("metadata", {}).get("service_area"),
            "category": result.get("metadata", {}).get("category"),
            "urgency": result.get("metadata", {}).get("urgency"),
        }
        if hs:
            conv_updates["last_assistant_handoff_summary"] = hs[:12000] + ("…" if len(hs) > 12000 else "")
        await ConversationService.update_conversation(conversation_id, conv_updates)
        
        # Audit log
        await SupportAuditService.log_action(
            action="chat_message",
            actor_type="user",
            actor_id=None,
            resource_type="conversation",
            resource_id=conversation_id,
            details={"message_length": len(body.message)},
            ip_address=request.client.host if request.client else None
        )
        
        resp_meta = dict(result.get("metadata", {}) or {})
        hs_top = result.get("handoff_summary")
        if hs_top is None:
            hs_top = resp_meta.pop("handoff_summary", None)
        else:
            resp_meta.pop("handoff_summary", None)

        # Build response
        response = ChatResponse(
            conversation_id=conversation_id,
            response=display_response,
            action=result["action"],
            metadata=resp_meta,
            conversation_context=result.get("conversation_context"),
            actions=result.get("actions"),
            handoff_summary=hs_top,
        )
        
        # Add handoff options if needed
        if result["action"] == "handoff":
            response.handoff_options = handoff_opts

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")


@public_router.get("/quick-actions")
async def get_quick_actions():
    """Get available quick action buttons for the chat widget."""
    return {
        "quick_actions": get_all_quick_actions()
    }


@public_router.post("/quick-action/{action_id}")
async def trigger_quick_action(
    request: Request,
    action_id: str,
    conversation_id: Optional[str] = None
):
    """
    Trigger a quick action and get the canned response.
    Optionally creates/uses a conversation.
    """
    canned = get_canned_response(action_id)
    
    if not canned:
        raise HTTPException(status_code=404, detail=f"Quick action not found: {action_id}")
    
    # Create conversation if needed
    if not conversation_id:
        conv_data = ConversationCreate(
            channel=ConversationChannel.WEB,
            user_identity_type=UserIdentityType.ANONYMOUS
        )
        conversation = await ConversationService.create_conversation(conv_data)
        conversation_id = conversation["conversation_id"]
    else:
        conversation = await ConversationService.get_conversation(conversation_id)
        if not conversation:
            conv_data = ConversationCreate(
                channel=ConversationChannel.WEB,
                user_identity_type=UserIdentityType.ANONYMOUS
            )
            conversation = await ConversationService.create_conversation(conv_data)
            conversation_id = conversation["conversation_id"]
    
    # Save the quick action as a user message
    user_msg = MessageCreate(
        message_text=f"[Quick Action: {action_id}]",
        sender=MessageSender.USER,
        metadata={"quick_action": action_id}
    )
    await MessageService.add_message(conversation_id, user_msg)

    bot_text = canned.get("response") or ""
    handoff_opts = None
    if canned.get("action") == "handoff":
        handoff_opts = build_public_handoff_options(
            conversation_id=conversation_id,
            crn=None,
            message_snippet=action_id,
            transcript_summary="quick action",
        )
        bot_text = format_handoff_intro_message(handoff_opts)

    # Save the canned response as bot message (include actions in metadata for clickable links)
    bot_meta = dict(canned.get("metadata", {}))
    if canned.get("actions"):
        bot_meta["actions"] = canned["actions"]
    bot_msg = MessageCreate(
        message_text=bot_text,
        sender=MessageSender.BOT,
        metadata=bot_meta
    )
    await MessageService.add_message(conversation_id, bot_msg)
    
    # Update conversation context when quick action sets a topic (for guided follow-ups)
    intent_from_action = {
        "cvp_info": "compliance_vault_pro",
        "document_packs_info": "document_packs",
        "pricing": "pricing",
        "billing_help": "pricing",
        "reset_password": "account_support",
        "speak_to_human": None,
        "check_order_status": "account_support",
    }.get(action_id)
    conversation_context = {
        "intent": intent_from_action,
        "topic": intent_from_action,
        "last_action": f"quick_action_{action_id}",
    } if intent_from_action else {"intent": None, "topic": None, "last_action": f"quick_action_{action_id}"}

    # Build response
    response_data = {
        "conversation_id": conversation_id,
        "response": bot_text,
        "action": canned.get("action", "respond"),
        "metadata": canned.get("metadata", {}),
        "conversation_context": conversation_context,
        "actions": canned.get("actions"),
    }

    if handoff_opts is not None:
        response_data["handoff_options"] = handoff_opts

    return response_data


@public_router.post("/lookup")
async def public_lookup(
    request: Request,
    body: LookupRequest
):
    """
    Public account lookup by CRN + email.
    Returns sanitized status only.
    Rate limited (per IP) and audit logged.
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"support_lookup:{client_ip}"
    allowed, rate_err = await rate_limiter.check_rate_limit(
        key=rate_key,
        max_attempts=20,
        window_minutes=60,
    )
    if not allowed:
        await SupportAuditService.log_action(
            action="public_lookup_rate_limited",
            actor_type="user",
            actor_id=None,
            resource_type="lookup",
            resource_id=body.crn,
            details={"ip": client_ip},
            ip_address=client_ip,
        )
        raise HTTPException(status_code=429, detail=rate_err or "Too many lookup attempts. Please try again later.")

    # Audit log the attempt
    await SupportAuditService.log_action(
        action="public_lookup_attempt",
        actor_type="user",
        actor_id=None,
        resource_type="lookup",
        resource_id=body.crn,
        details={"email_domain": body.email.split("@")[-1]},
        ip_address=request.client.host if request.client else None
    )
    
    result = await lookup_account_by_crn(body.crn, body.email)
    
    if not result:
        # Don't reveal if CRN exists
        return {
            "verified": False,
            "message": "Unable to verify account. Please check your CRN and email, or contact support."
        }
    
    return {
        "verified": True,
        "account_status": result["account_status"],
        "member_since": result["member_since"],
        "message": "Account verified successfully."
    }


@public_router.post("/ticket")
async def create_ticket_endpoint(
    request: Request,
    body: TicketRequest
):
    """
    Create a support ticket.
    Sends confirmation email to customer and notification to support.
    """
    from services.support_email_service import (
        send_ticket_confirmation_email,
        send_internal_ticket_notification
    )
    
    try:
        # Create ticket
        ticket_data = TicketCreate(
            subject=body.subject,
            description=body.description,
            category=TicketCategory(body.category) if body.category in [e.value for e in TicketCategory] else TicketCategory.OTHER,
            priority=TicketPriority(body.priority) if body.priority in [e.value for e in TicketPriority] else TicketPriority.MEDIUM,
            service_area=ServiceArea(body.service_area) if body.service_area in [e.value for e in ServiceArea] else ServiceArea.OTHER,
            contact_method=ContactMethod(body.contact_method) if body.contact_method in [e.value for e in ContactMethod] else ContactMethod.EMAIL,
            email=body.email,
            crn=body.crn,
        )
        
        assistant_hs = None
        if body.conversation_id:
            conv = await ConversationService.get_conversation(body.conversation_id)
            if conv:
                assistant_hs = conv.get("last_assistant_handoff_summary")

        transcript = None
        if body.conversation_id:
            transcript = await MessageService.get_transcript(body.conversation_id)
        transcript_included = bool((transcript or "").strip())

        ticket = await TicketService.create_ticket(
            ticket_data,
            conversation_id=body.conversation_id,
            assistant_handoff_summary=assistant_hs,
            ticket_source="public_support",
            transcript_available=bool(body.conversation_id),
        )
        
        # Send confirmation email to customer
        customer_email_sent = False
        if body.email:
            customer_email_sent = await send_ticket_confirmation_email(
                ticket_id=ticket["ticket_id"],
                customer_email=body.email,
                subject=body.subject,
                description=body.description,
                category=ticket_data.category.value,
                priority=ticket_data.priority.value
            )
        
        # Send internal notification to support team
        internal_email_sent = await send_internal_ticket_notification(
            ticket_id=ticket["ticket_id"],
            customer_email=body.email,
            customer_crn=body.crn,
            subject=body.subject,
            description=body.description,
            category=ticket_data.category.value,
            priority=ticket_data.priority.value,
            service_area=ticket_data.service_area.value,
            transcript=transcript,
            assistant_handoff_summary=assistant_hs,
        )
        
        # Audit log
        await SupportAuditService.log_action(
            action="ticket_created",
            actor_type="user",
            actor_id=None,
            resource_type="ticket",
            resource_id=ticket["ticket_id"],
            details={
                "category": body.category,
                "priority": body.priority,
                "has_conversation": bool(body.conversation_id),
                "customer_email_sent": customer_email_sent,
                "internal_email_sent": internal_email_sent,
            },
            ip_address=request.client.host if request.client else None
        )
        
        return build_public_ticket_created_response(
            ticket_id=ticket["ticket_id"],
            conversation_id=body.conversation_id,
            transcript_included=transcript_included,
            email_sent=customer_email_sent,
            internal_notification_sent=internal_email_sent,
        )
        
    except Exception as e:
        logger.error(f"Ticket creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")


@public_router.post("/conversation/{conversation_id}/live-chat-handoff")
async def live_chat_handoff(
    request: Request,
    conversation_id: str,
):
    """
    Record that the user chose Live Chat. Creates a support ticket linked to the
    conversation (so it appears in admin queue) and sets preferred_contact=livechat.
    Idempotent: if a ticket is already linked, returns existing ticket_id.
    """
    conversation = await ConversationService.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db = database.get_db()
    existing_ticket = await db[TICKETS_COLLECTION].find_one(
        {"conversation_id": conversation_id},
        {"_id": 0, "ticket_id": 1},
    )

    await ConversationService.update_conversation(
        conversation_id,
        {"preferred_contact": "livechat"},
    )

    if existing_ticket:
        await SupportAuditService.log_action(
            action="live_chat_handoff_recorded",
            actor_type="user",
            actor_id=None,
            resource_type="conversation",
            resource_id=conversation_id,
            details={"ticket_id": existing_ticket["ticket_id"], "already_linked": True},
            ip_address=request.client.host if request.client else None,
        )
        return {"success": True, "ticket_id": existing_ticket["ticket_id"], "already_linked": True}

    transcript = await MessageService.get_transcript(conversation_id)
    desc = (transcript[:5000] + ("..." if len(transcript) > 5000 else "")) if transcript else "User chose Live Chat."
    svc_area = conversation.get("service_area")
    try:
        service_area = ServiceArea(svc_area) if svc_area in [e.value for e in ServiceArea] else ServiceArea.OTHER
    except Exception:
        service_area = ServiceArea.OTHER

    assistant_hs = conversation.get("last_assistant_handoff_summary")
    ticket_data = TicketCreate(
        subject="Live chat handoff",
        description=desc,
        category=TicketCategory.OTHER,
        priority=TicketPriority.MEDIUM,
        contact_method=ContactMethod.LIVECHAT,
        service_area=service_area,
        email=conversation.get("email"),
        crn=conversation.get("crn"),
    )
    ticket = await TicketService.create_ticket(
        ticket_data,
        conversation_id=conversation_id,
        assistant_handoff_summary=assistant_hs,
        ticket_source="public_support",
        transcript_available=True,
    )

    await SupportAuditService.log_action(
        action="live_chat_handoff_recorded",
        actor_type="user",
        actor_id=None,
        resource_type="conversation",
        resource_id=conversation_id,
        details={"ticket_id": ticket["ticket_id"]},
        ip_address=request.client.host if request.client else None,
    )
    return {"success": True, "ticket_id": ticket["ticket_id"], "already_linked": False}


class WhatsAppHandoffAuditRequest(BaseModel):
    """Request for WhatsApp handoff audit logging."""
    conversation_id: Optional[str] = None
    user_role: str = "anonymous"
    client_id: Optional[str] = None
    page_url: str
    timestamp: str


@public_router.post("/audit/whatsapp-handoff")
async def audit_whatsapp_handoff(
    request: Request,
    body: WhatsAppHandoffAuditRequest
):
    """
    Log WhatsApp handoff click for audit purposes.
    Event: SUPPORT_WHATSAPP_HANDOFF_CLICKED
    """
    await SupportAuditService.log_action(
        action="SUPPORT_WHATSAPP_HANDOFF_CLICKED",
        actor_type=body.user_role,
        actor_id=body.client_id,
        resource_type="conversation",
        resource_id=body.conversation_id or "unknown",
        details={
            "user_role": body.user_role,
            "client_id": body.client_id,
            "page_url": body.page_url,
            "timestamp": body.timestamp,
        },
        ip_address=request.client.host if request.client else None
    )
    
    return {"success": True, "event": "SUPPORT_WHATSAPP_HANDOFF_CLICKED"}


# ============================================================================
# AUTHENTICATED CLIENT ENDPOINTS
# ============================================================================

@client_router.get("/account-snapshot")
async def get_account_snapshot(
    current_user: dict = Depends(client_route_guard)
):
    """
    Get account snapshot for authenticated client.
    Used by portal assistant.
    """
    client_id = current_user.get("client_id") or current_user.get("user_id")
    
    if not client_id:
        raise HTTPException(status_code=400, detail="Client ID not found")
    
    snapshot = await get_client_snapshot(client_id)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return snapshot


@client_router.get("/my-conversations")
async def get_my_conversations(
    current_user: dict = Depends(client_route_guard),
    limit: int = Query(20, le=100)
):
    """Get client's own conversations."""
    client_id = current_user.get("client_id") or current_user.get("user_id")
    
    db = database.get_db()
    cursor = db["support_conversations"].find(
        {"client_id": client_id},
        {"_id": 0}
    ).sort("last_message_at", -1).limit(limit)
    
    conversations = await cursor.to_list(length=limit)
    
    return {"conversations": conversations}


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@admin_router.get("/conversations")
async def list_conversations(
    status: Optional[str] = None,
    channel: Optional[str] = None,
    service_area: Optional[str] = None,
    search: Optional[str] = Query(None, description="CRN, email, or client_id"),
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(require_support_or_above)
):
    """List all support conversations with filters."""
    result = await ConversationService.list_conversations(
        status=status,
        channel=channel,
        service_area=service_area,
        search=search,
        limit=limit,
        skip=skip
    )
    return result


@admin_router.get("/tickets")
async def list_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    service_area: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    search: Optional[str] = Query(None, description="CRN or email"),
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(require_support_or_above)
):
    """List all support tickets with filters."""
    result = await TicketService.list_tickets(
        status=status,
        category=category,
        service_area=service_area,
        priority=priority,
        assigned_to=assigned_to,
        search=search,
        limit=limit,
        skip=skip
    )
    return result


@admin_router.get("/conversation/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    current_user: dict = Depends(require_support_or_above)
):
    """Get full conversation with transcript and system events."""
    conversation = await ConversationService.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await MessageService.get_messages(conversation_id, limit=500)
    transcript = await MessageService.get_transcript(conversation_id)

    # Get linked ticket if any
    db = database.get_db()
    ticket = await db["support_tickets"].find_one(
        {"conversation_id": conversation_id},
        {"_id": 0}
    )

    # System events from support audit log (admin_reply, ticket_created, etc.)
    audit_logs = await SupportAuditService.get_logs(
        resource_type="conversation",
        resource_id=conversation_id,
        limit=50
    )
    system_events = [
        {
            "type": "system_event",
            "action": e.get("action"),
            "timestamp": e.get("timestamp"),
            "actor_id": e.get("actor_id"),
            "details": e.get("details") or {},
        }
        for e in audit_logs
    ]

    return {
        "conversation": conversation,
        "messages": messages,
        "transcript": transcript,
        "linked_ticket": ticket,
        "system_events": system_events,
    }


@admin_router.get("/ticket/{ticket_id}")
async def get_ticket_detail(
    ticket_id: str,
    current_user: dict = Depends(require_support_or_above)
):
    """Get ticket details with conversation if linked. Includes handover_summary when from Portal Assistant escalation."""
    ticket = await TicketService.get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Linked conversation if any
    conversation = None
    messages = []
    if ticket.get("conversation_id"):
        conversation = await ConversationService.get_conversation(ticket["conversation_id"])
        messages = await MessageService.get_messages(ticket["conversation_id"])

    is_portal_assistant = (
        ticket.get("ticket_source") == "portal_assistant"
        or bool(ticket.get("assistant_conversation_id"))
    )
    subj = (ticket.get("subject") or "").strip()
    desc = ticket.get("description") or ""
    legacy_portal = "Portal Assistant escalation" in subj or "User requested human handover" in desc

    handover_summary = None
    if is_portal_assistant or legacy_portal:
        handover_summary = {
            "source": "portal_assistant",
            "assistant_conversation_id": ticket.get("assistant_conversation_id"),
            "transcript_available": ticket.get("transcript_available", legacy_portal or is_portal_assistant),
            "reason": "Portal Assistant escalation",
            "description_preview": desc[:1500] + ("..." if len(desc) > 1500 else ""),
        }

    assistant_handoff_summary = ticket.get("assistant_handoff_summary")

    return {
        "ticket": ticket,
        "conversation": conversation,
        "messages": messages,
        "handover_summary": handover_summary,
        "assistant_handoff_summary": assistant_handoff_summary,
    }


@admin_router.post("/conversation/{conversation_id}/reply")
async def admin_reply(
    conversation_id: str,
    body: AdminReplyRequest,
    current_user: dict = Depends(require_support_or_above)
):
    """Admin reply to a conversation."""
    conversation = await ConversationService.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Add message as human agent
    msg = MessageCreate(
        message_text=body.message,
        sender=MessageSender.HUMAN,
        metadata={"admin_id": current_user.get("email")}
    )
    message = await MessageService.add_message(conversation_id, msg)
    
    # Audit log
    await SupportAuditService.log_action(
        action="admin_reply",
        actor_type="admin",
        actor_id=current_user.get("email"),
        resource_type="conversation",
        resource_id=conversation_id,
        details={"message_length": len(body.message)}
    )
    
    return {
        "success": True,
        "message": message
    }


@admin_router.post("/conversation/{conversation_id}/create-ticket")
async def create_ticket_from_conversation(
    conversation_id: str,
    body: AdminCreateTicketFromConversationRequest | None = None,
    current_user: dict = Depends(require_support_or_above)
):
    """Create a support ticket linked to this conversation. Subject/description default from transcript."""
    conversation = await ConversationService.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db = database.get_db()
    existing = await db["support_tickets"].find_one({"conversation_id": conversation_id}, {"ticket_id": 1})
    if existing:
        raise HTTPException(status_code=400, detail="A ticket is already linked to this conversation")

    transcript = await MessageService.get_transcript(conversation_id)
    subject = (body and body.subject and body.subject.strip()) or "Conversation escalation"
    description = (body and body.description and body.description.strip()) or (transcript[:4000] if transcript else "No transcript.")

    assistant_hs = conversation.get("last_assistant_handoff_summary")
    ticket_data = TicketCreate(
        subject=subject[:200],
        description=description[:5000],
        category=TicketCategory.OTHER,
        priority=TicketPriority.MEDIUM,
        contact_method=ContactMethod.EMAIL,
        service_area=ServiceArea.OTHER,
        email=conversation.get("email"),
        crn=conversation.get("crn"),
    )
    ticket = await TicketService.create_ticket(
        ticket_data,
        conversation_id=conversation_id,
        assistant_handoff_summary=assistant_hs,
        ticket_source="support_conversation",
        transcript_available=True,
    )

    await SupportAuditService.log_action(
        action="ticket_created_from_conversation",
        actor_type="admin",
        actor_id=current_user.get("email"),
        resource_type="conversation",
        resource_id=conversation_id,
        details={"ticket_id": ticket["ticket_id"]},
    )

    return {"success": True, "ticket_id": ticket["ticket_id"], "ticket": ticket}


@admin_router.get("/canned-responses")
async def list_canned_responses_for_reply(
    current_user: dict = Depends(require_support_or_above)
):
    """List active canned responses for the reply bar (label, response_text, response_id). Support and above."""
    db = database.get_db()
    cursor = db["canned_responses"].find(
        {"is_active": True},
        {"_id": 0, "response_id": 1, "label": 1, "response_text": 1, "category": 1}
    ).sort("order", 1).limit(100)
    items = await cursor.to_list(length=100)
    return {"responses": items}


@admin_router.put("/ticket/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    status: str,
    current_user: dict = Depends(require_support_or_above)
):
    """Update ticket status."""
    from services.support_service import TicketStatus
    
    if status not in [e.value for e in TicketStatus]:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    updates = {"status": status}
    if status == "resolved":
        updates["resolved_at"] = datetime.now(timezone.utc).isoformat()
    
    success = await TicketService.update_ticket(ticket_id, updates)
    
    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Audit log
    await SupportAuditService.log_action(
        action="ticket_status_update",
        actor_type="admin",
        actor_id=current_user.get("email"),
        resource_type="ticket",
        resource_id=ticket_id,
        details={"new_status": status}
    )
    
    return {"success": True, "status": status}


@admin_router.put("/ticket/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    assignee: str,
    current_user: dict = Depends(require_support_or_above)
):
    """Assign ticket to admin."""
    success = await TicketService.update_ticket(
        ticket_id,
        {"assigned_to": assignee, "status": "open"}
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Audit log
    await SupportAuditService.log_action(
        action="ticket_assigned",
        actor_type="admin",
        actor_id=current_user.get("email"),
        resource_type="ticket",
        resource_id=ticket_id,
        details={"assigned_to": assignee}
    )
    
    return {"success": True, "assigned_to": assignee}


@admin_router.post("/ticket/{ticket_id}/note")
async def add_ticket_note(
    ticket_id: str,
    body: AdminReplyRequest,
    current_user: dict = Depends(require_support_or_above)
):
    """Add internal note to ticket."""
    success = await TicketService.add_note(
        ticket_id,
        body.message,
        current_user.get("email", "admin")
    )

    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await SupportAuditService.log_action(
        action="ticket_note_added",
        actor_type="admin",
        actor_id=current_user.get("email"),
        resource_type="ticket",
        resource_id=ticket_id,
        details={"note_length": len(body.message)},
    )

    return {"success": True}


@admin_router.post("/lookup-by-crn")
async def admin_lookup_by_crn(
    body: AdminLookupRequest,
    current_user: dict = Depends(require_owner_or_admin)
):
    """Admin-only (ROLE_ADMIN) account lookup by CRN. Support role cannot access."""
    db = database.get_db()
    crn_upper = (body.crn or "").strip().upper()
    client = await db["clients"].find_one(
        {"customer_reference": crn_upper},
        {"_id": 0, "password_hash": 0}
    )
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get additional data
    orders_cursor = db["orders"].find(
        {"client_id": client.get("client_id")},
        {"_id": 0}
    ).sort("created_at", -1).limit(10)
    orders = await orders_cursor.to_list(length=10)
    
    properties_count = await db["properties"].count_documents(
        {"client_id": client.get("client_id")}
    )
    
    # Audit log
    await SupportAuditService.log_action(
        action="admin_crn_lookup",
        actor_type="admin",
        actor_id=current_user.get("email"),
        resource_type="lookup",
        resource_id=body.crn,
        details={"found": True}
    )
    
    return {
        "client": client,
        "recent_orders": orders,
        "properties_count": properties_count,
    }


@admin_router.get("/audit-log")
async def get_audit_log(
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(100, le=500),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(require_support_or_above)
):
    """View support audit logs."""
    logs = await SupportAuditService.get_logs(
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        limit=limit,
        skip=skip
    )
    
    return {"logs": logs, "total": len(logs)}


@admin_router.post("/remediation-correlation-view")
async def remediation_correlation_view(
    body: RemediationCorrelationViewRequest,
    current_user: dict = Depends(require_support_or_above),
):
    """
    Stream C internal remediation correlation read-model (v1).

    Read-only joins across compliance_gaps, maintenance_issues, work_orders,
    risk_signals, audit_logs, property_compliance_score_history, score_change_log.
    Requires FEATURE_REMEDIATION_CORRELATION_VIEW_V1. Not a source of truth.
    """
    from services.remediation_correlation_view import (
        is_remediation_correlation_view_v1_enabled,
        build_remediation_correlation_view,
    )

    if not is_remediation_correlation_view_v1_enabled():
        raise HTTPException(
            status_code=404,
            detail="Remediation correlation view is disabled",
        )

    db = database.get_db()
    try:
        return await build_remediation_correlation_view(
            db,
            client_id=body.client_id.strip(),
            property_id=body.property_id.strip(),
            entry_kind=body.entry.kind,
            entry_value=body.entry.value.strip(),
            as_of_raw=body.as_of,
            window_half_days=body.window_half_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Anchor not found for client_id, property_id, and entry",
        ) from None


@admin_router.post("/public-content/reindex")
async def admin_reindex_public_support_content(
    body: PublicContentReindexRequest,
    current_user: dict = Depends(require_support_or_above),
):
    """
    Rebuild support_public_content_chunks from published USER KC articles and/or
    allowlisted marketing pages. Site fetch runs only here (scheduled/manual), not per chat.
    """
    from services.support_public_content_index_service import (
        full_reindex_public_support_content,
        reindex_all_published_user_kb_articles,
        reindex_allowlisted_site_pages,
        ensure_support_public_content_indexes,
    )

    try:
        await ensure_support_public_content_indexes()
        if body.scope == "kb":
            out = await reindex_all_published_user_kb_articles()
        elif body.scope == "site":
            out = await reindex_allowlisted_site_pages(base_url=body.site_base_url)
        else:
            out = await full_reindex_public_support_content(
                include_site=True,
                site_base_url=body.site_base_url,
            )
        await SupportAuditService.log_action(
            action="public_support_content_reindex",
            actor_type="admin",
            actor_id=current_user.get("email"),
            resource_type="support_public_content",
            resource_id=body.scope,
            details={"result": out},
            ip_address=None,
        )
        return {"success": True, "result": out}
    except Exception as e:
        logger.error("public-content reindex failed: %s", e)
        raise HTTPException(status_code=500, detail="Reindex failed") from e


@admin_router.get("/stats")
async def get_support_stats(
    current_user: dict = Depends(require_support_or_above)
):
    """Get support system statistics."""
    db = database.get_db()

    # Conversation stats
    total_conversations = await db["support_conversations"].count_documents({})
    open_conversations = await db["support_conversations"].count_documents({"status": "open"})
    escalated_conversations = await db["support_conversations"].count_documents({"status": "escalated"})

    # Ticket stats
    total_tickets = await db["support_tickets"].count_documents({})
    new_tickets = await db["support_tickets"].count_documents({"status": "new"})
    open_tickets = await db["support_tickets"].count_documents({"status": "open"})
    pending_tickets = await db["support_tickets"].count_documents({"status": "pending"})

    # Priority breakdown
    high_priority = await db["support_tickets"].count_documents({"priority": {"$in": ["high", "urgent"]}})

    return {
        "conversations": {
            "total": total_conversations,
            "open": open_conversations,
            "escalated": escalated_conversations,
        },
        "tickets": {
            "total": total_tickets,
            "new": new_tickets,
            "open": open_tickets,
            "pending": pending_tickets,
            "high_priority": high_priority,
        }
    }


def _support_ctx_iso_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


@admin_router.get("/context/{client_id}")
async def get_support_context(
    client_id: str,
    current_user: dict = Depends(require_support_or_above)
):
    """
    Get support context for a client: account snapshot, portfolio snapshot,
    notification prefs, recent audit log, recent email delivery events, recent documents.
    Used by Support Dashboard context panel. RBAC: Support and above.

    INV-SU-001: sections degrade independently; endpoint returns 200 unless client missing.
    INV-SU-002: ops_summary_v1 operational reconstruction slice.
    """
    import logging

    from services.support_client_context_ops import (
        build_ops_summary_v1,
        sanitize_for_json,
        _safe_property_ids,
    )

    log = logging.getLogger(__name__)
    db = database.get_db()
    degraded_sections: List[Dict[str, Any]] = []

    if db is None:
        log.error("support.context database unavailable client_id=%s", client_id)
        return sanitize_for_json({
            "client_id": client_id,
            "account_snapshot": {},
            "portfolio_snapshot": {},
            "notification_prefs": {},
            "recent_audit_log": [],
            "recent_email_delivery": [],
            "recent_documents": [],
            "ops_summary_v1": {"available": False, "degraded_sections": [{"section": "database", "error": "unavailable"}]},
            "context_degraded_sections": [{"section": "database", "error": "database unavailable"}],
        })

    client = await db["clients"].find_one(
        {"client_id": client_id},
        {"_id": 0, "password_hash": 0, "client_id": 1, "customer_reference": 1, "full_name": 1, "email": 1,
         "subscription_status": 1, "onboarding_status": 1, "provisioning_status": 1,
         "activation_email_status": 1, "activation_email_sent_at": 1, "billing_plan": 1}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    account_snapshot: Dict[str, Any] = {}
    try:
        account_snapshot = {
            "client_id": client.get("client_id"),
            "name": client.get("full_name") or client.get("name"),
            "email": client.get("email"),
            "crn": client.get("customer_reference"),
            "subscription_status": client.get("subscription_status") or "none",
            "onboarding_status": client.get("onboarding_status"),
            "provisioning_status": client.get("provisioning_status"),
            "activation_email_status": client.get("activation_email_status"),
            "activation_email_sent_at": _support_ctx_iso_ts(client.get("activation_email_sent_at")),
            "billing_plan": client.get("billing_plan"),
        }
        orders_cursor = db["orders"].find(
            {"client_id": client_id},
            {"_id": 0, "order_ref": 1, "status": 1, "service_name": 1, "created_at": 1}
        ).sort("created_at", -1).limit(5)
        account_snapshot["recent_orders"] = await orders_cursor.to_list(length=5)
        for o in account_snapshot.get("recent_orders") or []:
            o["created_at"] = _support_ctx_iso_ts(o.get("created_at"))
    except Exception as exc:
        degraded_sections.append({"section": "account_snapshot", "error": str(exc)[:200]})
        log.warning("support.context account_snapshot degraded client_id=%s: %s", client_id, exc)

    portfolio_snapshot: Dict[str, Any] = {}
    try:
        properties_count = await db["properties"].count_documents({"client_id": client_id})
        property_ids = await _safe_property_ids(db, client_id)
        requirements_count = (
            await db["requirements"].count_documents({"property_id": {"$in": property_ids}})
            if property_ids
            else 0
        )
        documents_count = await db["documents"].count_documents({"client_id": client_id})
        overdue_req = 0
        if property_ids:
            cutoff_iso = datetime.now(timezone.utc).isoformat()
            try:
                overdue_req = await db["requirements"].count_documents({
                    "property_id": {"$in": property_ids},
                    "due_date": {"$lt": cutoff_iso},
                    "status": {"$nin": ["satisfied", "waived", "cancelled"]},
                })
            except Exception:
                overdue_req = await db["requirements"].count_documents({
                    "property_id": {"$in": property_ids},
                    "status": "OVERDUE",
                })
        portfolio_snapshot = {
            "properties_count": properties_count,
            "requirements_count": requirements_count,
            "documents_count": documents_count,
            "overdue_requirements_count": overdue_req,
        }
    except Exception as exc:
        degraded_sections.append({"section": "portfolio_snapshot", "error": str(exc)[:200]})
        log.warning("support.context portfolio_snapshot degraded client_id=%s: %s", client_id, exc)

    notification_prefs: Dict[str, Any] = {}
    try:
        notif_prefs = await db["notification_preferences"].find_one({"client_id": client_id}, {"_id": 0})
        notification_prefs = notif_prefs or {}
    except Exception as exc:
        degraded_sections.append({"section": "notification_prefs", "error": str(exc)[:200]})

    recent_audit_log: List[Dict[str, Any]] = []
    try:
        audit_cursor = db["audit_logs"].find(
            {"client_id": client_id},
            {"_id": 0, "action": 1, "actor_id": 1, "resource_type": 1, "resource_id": 1, "timestamp": 1, "metadata": 1}
        ).sort("timestamp", -1).limit(20)
        recent_audit_log = await audit_cursor.to_list(length=20)
        for e in recent_audit_log:
            e["timestamp"] = _support_ctx_iso_ts(e.get("timestamp"))
            if e.get("metadata") is not None:
                e["metadata"] = sanitize_for_json(e.get("metadata"))
    except Exception as exc:
        degraded_sections.append({"section": "recent_audit_log", "error": str(exc)[:200]})
        log.warning("support.context recent_audit_log degraded client_id=%s: %s", client_id, exc)

    recent_email_delivery: List[Dict[str, Any]] = []
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=168)).isoformat()
        msg_cursor = db["message_logs"].find(
            {"client_id": client_id, "created_at": {"$gte": since}},
            {"_id": 0, "created_at": 1, "template_alias": 1, "status": 1, "message_id": 1}
        ).sort("created_at", -1).limit(20)
        recent_email_delivery = await msg_cursor.to_list(length=20)
        for e in recent_email_delivery:
            e["created_at"] = _support_ctx_iso_ts(e.get("created_at"))
    except Exception as exc:
        degraded_sections.append({"section": "recent_email_delivery", "error": str(exc)[:200]})

    recent_documents: List[Dict[str, Any]] = []
    try:
        doc_cursor = db["documents"].find(
            {"client_id": client_id},
            {"_id": 0, "document_id": 1, "file_name": 1, "status": 1, "uploaded_at": 1, "property_id": 1}
        ).sort("uploaded_at", -1).limit(15)
        recent_documents = await doc_cursor.to_list(length=15)
        for d in recent_documents:
            d["uploaded_at"] = _support_ctx_iso_ts(d.get("uploaded_at"))
    except Exception as exc:
        degraded_sections.append({"section": "recent_documents", "error": str(exc)[:200]})

    ops_summary_v1: Dict[str, Any] = {}
    try:
        ops_summary_v1 = await build_ops_summary_v1(db, client_id)
    except Exception as exc:
        degraded_sections.append({"section": "ops_summary_v1", "error": str(exc)[:200]})
        log.warning("support.context ops_summary_v1 degraded client_id=%s: %s", client_id, exc)
        ops_summary_v1 = {"available": False, "degraded_sections": [{"section": "ops_summary_v1", "error": str(exc)[:200]}]}

    if degraded_sections:
        log.info(
            "support.context partial_degrade client_id=%s sections=%s",
            client_id,
            [s.get("section") for s in degraded_sections],
        )

    return sanitize_for_json({
        "client_id": client_id,
        "account_snapshot": account_snapshot,
        "portfolio_snapshot": portfolio_snapshot,
        "notification_prefs": notification_prefs,
        "recent_audit_log": recent_audit_log,
        "recent_email_delivery": recent_email_delivery,
        "recent_documents": recent_documents,
        "ops_summary_v1": ops_summary_v1,
        "context_degraded_sections": degraded_sections,
    })
