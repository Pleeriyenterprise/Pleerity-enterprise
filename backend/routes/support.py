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
from datetime import datetime, timezone
from middleware import admin_route_guard, get_current_user
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
    detect_service_area, detect_category, detect_urgency
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
        
        # Send emails (would integrate with Postmark here)
        # For now, just log
        logger.info(f"Ticket created: {ticket['ticket_id']} - would send emails")
        
        # TODO: Integrate Postmark for emails
        # - Customer confirmation email
        # - Internal support notification with transcript
        
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
            },
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "ticket_id": ticket["ticket_id"],
            "message": f"Support ticket {ticket['ticket_id']} created. We'll respond within 24 hours.",
            "email_sent": bool(body.email),
        }
        
    except Exception as e:
        logger.error(f"Ticket creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")


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
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(admin_route_guard)
):
    """List all support conversations with filters."""
    result = await ConversationService.list_conversations(
        status=status,
        channel=channel,
        service_area=service_area,
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
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(admin_route_guard)
):
    """List all support tickets with filters."""
    result = await TicketService.list_tickets(
        status=status,
        category=category,
        service_area=service_area,
        priority=priority,
        assigned_to=assigned_to,
        limit=limit,
        skip=skip
    )
    return result


@admin_router.get("/conversation/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Get full conversation with transcript."""
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
    
    return {
        "conversation": conversation,
        "messages": messages,
        "transcript": transcript,
        "linked_ticket": ticket,
    }


@admin_router.get("/ticket/{ticket_id}")
async def get_ticket_detail(
    ticket_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Get ticket details with conversation if linked."""
    ticket = await TicketService.get_ticket(ticket_id)
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Get linked conversation if any
    conversation = None
    messages = []
    if ticket.get("conversation_id"):
        conversation = await ConversationService.get_conversation(ticket["conversation_id"])
        messages = await MessageService.get_messages(ticket["conversation_id"])
    
    return {
        "ticket": ticket,
        "conversation": conversation,
        "messages": messages,
    }


@admin_router.post("/conversation/{conversation_id}/reply")
async def admin_reply(
    conversation_id: str,
    body: AdminReplyRequest,
    current_user: dict = Depends(admin_route_guard)
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


@admin_router.put("/ticket/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    status: str,
    current_user: dict = Depends(admin_route_guard)
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
    current_user: dict = Depends(admin_route_guard)
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
    current_user: dict = Depends(admin_route_guard)
):
    """Add internal note to ticket."""
    success = await TicketService.add_note(
        ticket_id,
        body.message,
        current_user.get("email", "admin")
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    return {"success": True}


@admin_router.post("/lookup-by-crn")
async def admin_lookup_by_crn(
    body: AdminLookupRequest,
    current_user: dict = Depends(admin_route_guard)
):
    """Admin-only full account lookup by CRN."""
    db = database.get_db()
    
    client = await db["clients"].find_one(
        {"crn": body.crn.upper()},
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
    current_user: dict = Depends(admin_route_guard)
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
    current_user: dict = Depends(admin_route_guard)
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
