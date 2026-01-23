"""
Support System Data Models and Services

Handles:
- Conversations (web/portal/whatsapp channels)
- Conversation Messages (user/bot/human senders)
- Support Tickets with escalation
- Audit logging for all support actions
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from database import database
import uuid
import logging

logger = logging.getLogger(__name__)

# Collections
CONVERSATIONS_COLLECTION = "support_conversations"
MESSAGES_COLLECTION = "support_messages"
TICKETS_COLLECTION = "support_tickets"
AUDIT_COLLECTION = "support_audit_log"


# ============================================================================
# ENUMS
# ============================================================================

class ConversationChannel(str, Enum):
    WEB = "web"
    PORTAL = "portal"
    WHATSAPP = "whatsapp"


class UserIdentityType(str, Enum):
    ANONYMOUS = "anonymous"
    CLIENT = "client"
    ADMIN = "admin"


class ConversationStatus(str, Enum):
    OPEN = "open"
    ESCALATED = "escalated"
    CLOSED = "closed"


class MessageSender(str, Enum):
    USER = "user"
    BOT = "bot"
    HUMAN = "human"


class ServiceArea(str, Enum):
    CVP = "cvp"
    DOCUMENT_SERVICES = "document_services"
    AI_AUTOMATION = "ai_automation"
    MARKET_RESEARCH = "market_research"
    BILLING = "billing"
    OTHER = "other"


class TicketCategory(str, Enum):
    BILLING = "billing"
    LOGIN = "login"
    DOCUMENTS = "documents"
    COMPLIANCE = "compliance"
    REPORTING = "reporting"
    TECHNICAL = "technical"
    OTHER = "other"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ContactMethod(str, Enum):
    EMAIL = "email"
    LIVECHAT = "livechat"
    WHATSAPP = "whatsapp"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ConversationCreate(BaseModel):
    channel: ConversationChannel = ConversationChannel.WEB
    user_identity_type: UserIdentityType = UserIdentityType.ANONYMOUS
    client_id: Optional[str] = None
    email: Optional[str] = None
    crn: Optional[str] = None


class MessageCreate(BaseModel):
    message_text: str
    sender: MessageSender = MessageSender.USER
    metadata: Optional[Dict[str, Any]] = None


class TicketCreate(BaseModel):
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.MEDIUM
    contact_method: ContactMethod = ContactMethod.EMAIL
    service_area: ServiceArea = ServiceArea.OTHER
    subject: str
    description: str
    email: Optional[str] = None
    crn: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_conversation_id() -> str:
    """Generate unique conversation ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:8].upper()
    return f"CONV-{timestamp}-{unique}"


def generate_ticket_id() -> str:
    """Generate unique ticket ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique = uuid.uuid4().hex[:6].upper()
    return f"TKT-{timestamp}-{unique}"


def generate_message_id() -> str:
    """Generate unique message ID."""
    return uuid.uuid4().hex


# ============================================================================
# CONVERSATION SERVICE
# ============================================================================

class ConversationService:
    """Service for managing support conversations."""
    
    @staticmethod
    async def create_conversation(data: ConversationCreate) -> Dict[str, Any]:
        """Create a new conversation."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        conversation = {
            "conversation_id": generate_conversation_id(),
            "channel": data.channel.value,
            "user_identity_type": data.user_identity_type.value,
            "client_id": data.client_id,
            "email": data.email,
            "crn": data.crn,
            "status": ConversationStatus.OPEN.value,
            "started_at": now,
            "ended_at": None,
            "last_message_at": now,
            "message_count": 0,
            "metadata": {},
            "service_area": None,
            "category": None,
            "urgency": None,
        }
        
        await db[CONVERSATIONS_COLLECTION].insert_one(conversation)
        
        # Remove MongoDB _id before returning
        conversation.pop("_id", None)
        
        logger.info(f"Created conversation: {conversation['conversation_id']}")
        return conversation
    
    @staticmethod
    async def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID."""
        db = database.get_db()
        return await db[CONVERSATIONS_COLLECTION].find_one(
            {"conversation_id": conversation_id},
            {"_id": 0}
        )
    
    @staticmethod
    async def update_conversation(
        conversation_id: str, 
        updates: Dict[str, Any]
    ) -> bool:
        """Update a conversation."""
        db = database.get_db()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db[CONVERSATIONS_COLLECTION].update_one(
            {"conversation_id": conversation_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    @staticmethod
    async def escalate_conversation(conversation_id: str) -> bool:
        """Mark conversation as escalated."""
        return await ConversationService.update_conversation(
            conversation_id,
            {"status": ConversationStatus.ESCALATED.value}
        )
    
    @staticmethod
    async def close_conversation(conversation_id: str) -> bool:
        """Close a conversation."""
        return await ConversationService.update_conversation(
            conversation_id,
            {
                "status": ConversationStatus.CLOSED.value,
                "ended_at": datetime.now(timezone.utc).isoformat()
            }
        )
    
    @staticmethod
    async def list_conversations(
        status: Optional[str] = None,
        channel: Optional[str] = None,
        service_area: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> Dict[str, Any]:
        """List conversations with filters."""
        db = database.get_db()
        
        query = {}
        if status:
            query["status"] = status
        if channel:
            query["channel"] = channel
        if service_area:
            query["service_area"] = service_area
        
        total = await db[CONVERSATIONS_COLLECTION].count_documents(query)
        
        cursor = db[CONVERSATIONS_COLLECTION].find(
            query, {"_id": 0}
        ).sort("last_message_at", -1).skip(skip).limit(limit)
        
        conversations = await cursor.to_list(length=limit)
        
        return {
            "conversations": conversations,
            "total": total,
            "limit": limit,
            "skip": skip
        }


# ============================================================================
# MESSAGE SERVICE
# ============================================================================

class MessageService:
    """Service for managing conversation messages."""
    
    @staticmethod
    async def add_message(
        conversation_id: str,
        data: MessageCreate
    ) -> Dict[str, Any]:
        """Add a message to a conversation."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        message = {
            "message_id": generate_message_id(),
            "conversation_id": conversation_id,
            "sender": data.sender.value,
            "message_text": data.message_text,
            "timestamp": now,
            "metadata": data.metadata or {},
            "redaction_flags": [],
        }
        
        await db[MESSAGES_COLLECTION].insert_one(message)
        
        # Update conversation
        await db[CONVERSATIONS_COLLECTION].update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {"last_message_at": now},
                "$inc": {"message_count": 1}
            }
        )
        
        # Remove MongoDB _id before returning
        message.pop("_id", None)
        return message
    
    @staticmethod
    async def get_messages(
        conversation_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get messages for a conversation."""
        db = database.get_db()
        
        cursor = db[MESSAGES_COLLECTION].find(
            {"conversation_id": conversation_id},
            {"_id": 0}
        ).sort("timestamp", 1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    @staticmethod
    async def get_transcript(
        conversation_id: str,
        format_type: str = "text"
    ) -> str:
        """Get formatted transcript of conversation."""
        messages = await MessageService.get_messages(conversation_id)
        
        if format_type == "text":
            lines = []
            for msg in messages:
                sender = msg["sender"].upper()
                timestamp = msg["timestamp"][:19].replace("T", " ")
                text = msg["message_text"]
                lines.append(f"[{timestamp}] {sender}: {text}")
            return "\n".join(lines)
        
        return messages


# ============================================================================
# TICKET SERVICE
# ============================================================================

class TicketService:
    """Service for managing support tickets."""
    
    @staticmethod
    async def create_ticket(
        data: TicketCreate,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a support ticket."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        ticket = {
            "ticket_id": generate_ticket_id(),
            "conversation_id": conversation_id,
            "category": data.category.value,
            "priority": data.priority.value,
            "service_area": data.service_area.value,
            "contact_method": data.contact_method.value,
            "subject": data.subject,
            "description": data.description,
            "email": data.email,
            "crn": data.crn,
            "status": TicketStatus.NEW.value,
            "assigned_to": None,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
            "notes": [],
        }
        
        await db[TICKETS_COLLECTION].insert_one(ticket)
        
        # If linked to conversation, escalate it
        if conversation_id:
            await ConversationService.escalate_conversation(conversation_id)
        
        ticket.pop("_id", None)
        
        logger.info(f"Created ticket: {ticket['ticket_id']}")
        return ticket
    
    @staticmethod
    async def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get a ticket by ID."""
        db = database.get_db()
        return await db[TICKETS_COLLECTION].find_one(
            {"ticket_id": ticket_id},
            {"_id": 0}
        )
    
    @staticmethod
    async def update_ticket(
        ticket_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update a ticket."""
        db = database.get_db()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db[TICKETS_COLLECTION].update_one(
            {"ticket_id": ticket_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    @staticmethod
    async def add_note(ticket_id: str, note: str, author: str) -> bool:
        """Add a note to a ticket."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db[TICKETS_COLLECTION].update_one(
            {"ticket_id": ticket_id},
            {
                "$push": {
                    "notes": {
                        "note": note,
                        "author": author,
                        "timestamp": now
                    }
                },
                "$set": {"updated_at": now}
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    async def list_tickets(
        status: Optional[str] = None,
        category: Optional[str] = None,
        service_area: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> Dict[str, Any]:
        """List tickets with filters."""
        db = database.get_db()
        
        query = {}
        if status:
            query["status"] = status
        if category:
            query["category"] = category
        if service_area:
            query["service_area"] = service_area
        if priority:
            query["priority"] = priority
        if assigned_to:
            query["assigned_to"] = assigned_to
        
        total = await db[TICKETS_COLLECTION].count_documents(query)
        
        cursor = db[TICKETS_COLLECTION].find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit)
        
        tickets = await cursor.to_list(length=limit)
        
        return {
            "tickets": tickets,
            "total": total,
            "limit": limit,
            "skip": skip
        }


# ============================================================================
# AUDIT SERVICE
# ============================================================================

class SupportAuditService:
    """Service for audit logging support actions."""
    
    @staticmethod
    async def log_action(
        action: str,
        actor_type: str,  # "user", "bot", "admin"
        actor_id: Optional[str],
        resource_type: str,  # "conversation", "ticket", "lookup"
        resource_id: Optional[str],
        details: Dict[str, Any],
        ip_address: Optional[str] = None
    ):
        """Log a support action for audit."""
        db = database.get_db()
        
        log_entry = {
            "log_id": uuid.uuid4().hex,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
        }
        
        await db[AUDIT_COLLECTION].insert_one(log_entry)
        logger.info(f"Audit log: {action} on {resource_type}/{resource_id}")
    
    @staticmethod
    async def get_logs(
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit logs with filters."""
        db = database.get_db()
        
        query = {}
        if resource_type:
            query["resource_type"] = resource_type
        if resource_id:
            query["resource_id"] = resource_id
        if action:
            query["action"] = action
        
        cursor = db[AUDIT_COLLECTION].find(
            query, {"_id": 0}
        ).sort("timestamp", -1).skip(skip).limit(limit)
        
        return await cursor.to_list(length=limit)


# ============================================================================
# DATABASE INDEXES
# ============================================================================

async def create_support_indexes():
    """Create indexes for support collections."""
    db = database.get_db()
    
    # Conversations
    await db[CONVERSATIONS_COLLECTION].create_index("conversation_id", unique=True)
    await db[CONVERSATIONS_COLLECTION].create_index("status")
    await db[CONVERSATIONS_COLLECTION].create_index("channel")
    await db[CONVERSATIONS_COLLECTION].create_index("client_id")
    await db[CONVERSATIONS_COLLECTION].create_index("crn")
    await db[CONVERSATIONS_COLLECTION].create_index("last_message_at")
    
    # Messages
    await db[MESSAGES_COLLECTION].create_index("message_id", unique=True)
    await db[MESSAGES_COLLECTION].create_index("conversation_id")
    await db[MESSAGES_COLLECTION].create_index("timestamp")
    
    # Tickets
    await db[TICKETS_COLLECTION].create_index("ticket_id", unique=True)
    await db[TICKETS_COLLECTION].create_index("conversation_id")
    await db[TICKETS_COLLECTION].create_index("status")
    await db[TICKETS_COLLECTION].create_index("priority")
    await db[TICKETS_COLLECTION].create_index("category")
    await db[TICKETS_COLLECTION].create_index("created_at")
    
    # Audit
    await db[AUDIT_COLLECTION].create_index("log_id", unique=True)
    await db[AUDIT_COLLECTION].create_index("timestamp")
    await db[AUDIT_COLLECTION].create_index("resource_type")
    await db[AUDIT_COLLECTION].create_index("resource_id")
    
    logger.info("Support system indexes created")
