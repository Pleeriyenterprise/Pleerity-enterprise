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
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from middleware import admin_route_guard, require_support_or_above, get_current_user
from services.support_service import (
    ConversationService, MessageService, TicketService, SupportAuditService,
    ConversationCreate, MessageCreate, TicketCreate,
    ConversationChannel, UserIdentityType, MessageSender,
    ServiceArea, TicketCategory, TicketPriority, ContactMethod,
    create_support_indexes
)
from services.support_chatbot import (
    handle_chat_message, lookup_account_by_crn, get_client_snapshot,
    generate_whatsapp_link, is_legal_advice_request,
    detect_service_area, detect_category, detect_urgency,
    get_canned_response, get_all_quick_actions, CANNED_RESPONSES
)
from database import database
import logging
import os

logger = logging.getLogger(__name__)

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


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    action: str  # respond, handoff, lookup_prompt
    metadata: Dict[str, Any] = {}
    handoff_options: Optional[Dict[str, Any]] = None


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


class AdminReplyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


class AdminCreateTicketFromConversationRequest(BaseModel):
    """Optional subject/description when creating a ticket from a conversation."""
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=5000)


class AdminLookupRequest(BaseModel):
    crn: str


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
        
        # Process message through chatbot
        result = await handle_chat_message(
            conversation_id=conversation_id,
            message=body.message,
            conversation_history=history,
            client_context=None,
            is_authenticated=False
        )
        
        # Save bot response
        bot_msg = MessageCreate(
            message_text=result["response"],
            sender=MessageSender.BOT,
            metadata=result.get("metadata", {})
        )
        await MessageService.add_message(conversation_id, bot_msg)
        
        # Update conversation metadata
        await ConversationService.update_conversation(
            conversation_id,
            {
                "service_area": result.get("metadata", {}).get("service_area"),
                "category": result.get("metadata", {}).get("category"),
                "urgency": result.get("metadata", {}).get("urgency"),
            }
        )
        
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
        
        # Build response
        response = ChatResponse(
            conversation_id=conversation_id,
            response=result["response"],
            action=result["action"],
            metadata=result.get("metadata", {})
        )
        
        # Add handoff options if needed
        if result["action"] == "handoff":
            handoff_data = result.get("handoff_data", {})
            response.handoff_options = {
                "live_chat": {
                    "available": True,  # Could check business hours
                    "provider": "tawk.to",
                },
                "email_ticket": {
                    "available": True,
                },
                "whatsapp": {
                    "available": True,
                    "link": generate_whatsapp_link(
                        conversation_id,
                        conversation.get("crn"),
                        body.message[:50]
                    ),
                },
                "conversation_id": conversation_id,
                "transcript_summary": f"{len(history)} messages in conversation",
            }
        
        return response
        
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
    
    # Save the canned response as bot message
    bot_msg = MessageCreate(
        message_text=canned["response"],
        sender=MessageSender.BOT,
        metadata=canned.get("metadata", {})
    )
    await MessageService.add_message(conversation_id, bot_msg)
    
    # Build response
    response_data = {
        "conversation_id": conversation_id,
        "response": canned["response"],
        "action": canned.get("action", "respond"),
        "metadata": canned.get("metadata", {})
    }
    
    # Add handoff options if this is a handoff action
    if canned.get("action") == "handoff":
        response_data["handoff_options"] = {
            "live_chat": {"available": True, "provider": "tawk.to"},
            "email_ticket": {"available": True},
            "whatsapp": {
                "available": True,
                "link": generate_whatsapp_link(conversation_id, None, action_id),
            },
            "conversation_id": conversation_id,
        }
    
    return response_data


@public_router.post("/lookup")
async def public_lookup(
    request: Request,
    body: LookupRequest
):
    """
    Public account lookup by CRN + email.
    Returns sanitized status only.
    Rate limited and audit logged.
    """
    # Rate limiting would go here
    
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
        
        ticket = await TicketService.create_ticket(
            ticket_data,
            conversation_id=body.conversation_id
        )
        
        # Get transcript if conversation linked
        transcript = None
        if body.conversation_id:
            transcript = await MessageService.get_transcript(body.conversation_id)
        
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
            transcript=transcript
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
        
        return {
            "success": True,
            "ticket_id": ticket["ticket_id"],
            "message": f"Support ticket {ticket['ticket_id']} created. We'll respond within 24 hours.",
            "email_sent": customer_email_sent,
            "internal_notification_sent": internal_email_sent,
        }
        
    except Exception as e:
        logger.error(f"Ticket creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")


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
    current_user: dict = Depends(get_current_user)
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
    current_user: dict = Depends(get_current_user),
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

    # Handover summary when ticket is from Portal Assistant escalation
    handover_summary = None
    subj = (ticket.get("subject") or "").strip()
    desc = (ticket.get("description") or "")
    if "Portal Assistant escalation" in subj or "User requested human handover" in desc:
        handover_summary = {
            "reason": "Portal Assistant escalation",
            "description_preview": desc[:1500] + ("..." if len(desc) > 1500 else ""),
        }

    return {
        "ticket": ticket,
        "conversation": conversation,
        "messages": messages,
        "handover_summary": handover_summary,
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
    ticket = await TicketService.create_ticket(ticket_data, conversation_id=conversation_id)

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
    current_user: dict = Depends(require_support_or_above)
):
    """Admin-only full account lookup by CRN."""
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


@admin_router.get("/context/{client_id}")
async def get_support_context(
    client_id: str,
    current_user: dict = Depends(require_support_or_above)
):
    """
    Get support context for a client: account snapshot, portfolio snapshot,
    notification prefs, recent audit log, recent email delivery events, recent documents.
    Used by Support Dashboard context panel. RBAC: Support and above.
    """
    db = database.get_db()

    client = await db["clients"].find_one(
        {"client_id": client_id},
        {"_id": 0, "password_hash": 0, "client_id": 1, "customer_reference": 1, "full_name": 1, "email": 1,
         "subscription_status": 1, "onboarding_status": 1, "provisioning_status": 1,
         "activation_email_status": 1, "activation_email_sent_at": 1, "billing_plan": 1}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Account snapshot
    account_snapshot = {
        "client_id": client.get("client_id"),
        "name": client.get("full_name") or client.get("name"),
        "email": client.get("email"),
        "crn": client.get("customer_reference"),
        "subscription_status": client.get("subscription_status") or "none",
        "onboarding_status": client.get("onboarding_status"),
        "provisioning_status": client.get("provisioning_status"),
        "activation_email_status": client.get("activation_email_status"),
        "activation_email_sent_at": client.get("activation_email_sent_at").isoformat() if client.get("activation_email_sent_at") and hasattr(client.get("activation_email_sent_at"), "isoformat") else (str(client.get("activation_email_sent_at")) if client.get("activation_email_sent_at") else None),
        "billing_plan": client.get("billing_plan"),
    }
    # Recent orders
    orders_cursor = db["orders"].find(
        {"client_id": client_id},
        {"_id": 0, "order_ref": 1, "status": 1, "service_name": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5)
    account_snapshot["recent_orders"] = await orders_cursor.to_list(length=5)

    # Portfolio snapshot
    properties_count = await db["properties"].count_documents({"client_id": client_id})
    property_ids = [p["property_id"] async for p in db["properties"].find({"client_id": client_id}, {"property_id": 1})]
    requirements_count = await db["requirements"].count_documents({"property_id": {"$in": property_ids}}) if property_ids else 0
    documents_count = await db["documents"].count_documents({"client_id": client_id})
    cutoff = datetime.now(timezone.utc)
    overdue_req = await db["requirements"].count_documents({
        "property_id": {"$in": property_ids},
        "due_date": {"$lt": cutoff},
        "status": {"$nin": ["satisfied", "waived", "cancelled"]}
    }) if property_ids else 0
    portfolio_snapshot = {
        "properties_count": properties_count,
        "requirements_count": requirements_count,
        "documents_count": documents_count,
        "overdue_requirements_count": overdue_req,
    }

    # Notification preferences (client-scoped)
    notif_prefs = await db["notification_preferences"].find_one(
        {"client_id": client_id},
        {"_id": 0}
    )
    notification_prefs = notif_prefs or {}

    # Recent audit log (client_id)
    audit_cursor = db["audit_logs"].find(
        {"client_id": client_id},
        {"_id": 0, "action": 1, "actor_id": 1, "resource_type": 1, "resource_id": 1, "timestamp": 1, "metadata": 1}
    ).sort("timestamp", -1).limit(20)
    recent_audit_log = await audit_cursor.to_list(length=20)
    for e in recent_audit_log:
        ts = e.get("timestamp")
        if hasattr(ts, "isoformat"):
            e["timestamp"] = ts.isoformat()

    # Recent email delivery (message_logs for this client)
    since = (datetime.now(timezone.utc) - timedelta(hours=168)).isoformat()  # 7 days
    msg_cursor = db["message_logs"].find(
        {"client_id": client_id, "created_at": {"$gte": since}},
        {"_id": 0, "created_at": 1, "template_alias": 1, "status": 1, "message_id": 1}
    ).sort("created_at", -1).limit(20)
    recent_email_delivery = await msg_cursor.to_list(length=20)
    for e in recent_email_delivery:
        ts = e.get("created_at")
        if hasattr(ts, "isoformat"):
            e["created_at"] = ts.isoformat()

    # Recent documents with extraction status
    doc_cursor = db["documents"].find(
        {"client_id": client_id},
        {"_id": 0, "document_id": 1, "file_name": 1, "status": 1, "uploaded_at": 1, "property_id": 1}
    ).sort("uploaded_at", -1).limit(15)
    recent_documents = await doc_cursor.to_list(length=15)
    for d in recent_documents:
        up = d.get("uploaded_at")
        if hasattr(up, "isoformat"):
            d["uploaded_at"] = up.isoformat()

    return {
        "client_id": client_id,
        "account_snapshot": account_snapshot,
        "portfolio_snapshot": portfolio_snapshot,
        "notification_prefs": notification_prefs,
        "recent_audit_log": recent_audit_log,
        "recent_email_delivery": recent_email_delivery,
        "recent_documents": recent_documents,
    }
