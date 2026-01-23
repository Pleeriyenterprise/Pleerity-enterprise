"""
Admin Canned Responses Management Routes

Provides APIs for admins to manage canned/quick responses for the support chatbot:
- CRUD operations for canned responses
- Category and channel filtering
- Preview functionality
- Soft delete (is_active flag)
- Full audit logging
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from middleware import admin_route_guard
from database import database
import logging
import uuid
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/support/responses", tags=["admin-canned-responses"])

COLLECTION = "canned_responses"


# ============================================================================
# ENUMS
# ============================================================================

class ResponseChannel(str, Enum):
    WEB_CHAT = "WEB_CHAT"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"


class ResponseCategory(str, Enum):
    ORDERS = "orders"
    BILLING = "billing"
    LOGIN = "login"
    DOCUMENTS = "documents"
    COMPLIANCE = "compliance"
    CVP = "cvp"
    TECHNICAL = "technical"
    HANDOFF = "handoff"
    OTHER = "other"


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class QuickActionButton(BaseModel):
    """Quick action button that can be attached to a response."""
    label: str = Field(..., min_length=1, max_length=50)
    url: Optional[str] = None  # URL to navigate to
    action: Optional[str] = None  # Action ID to trigger


class CannedResponseCreate(BaseModel):
    """Request to create a canned response."""
    label: str = Field(..., min_length=2, max_length=100)
    category: ResponseCategory
    channel: ResponseChannel = ResponseChannel.WEB_CHAT
    response_text: str = Field(..., min_length=10, max_length=5000)
    quick_actions: Optional[List[QuickActionButton]] = None
    trigger_keywords: Optional[List[str]] = None  # Keywords that trigger this response
    icon: Optional[str] = "💬"  # Emoji icon
    order: int = 0  # Display order


class CannedResponseUpdate(BaseModel):
    """Request to update a canned response."""
    label: Optional[str] = Field(None, min_length=2, max_length=100)
    category: Optional[ResponseCategory] = None
    channel: Optional[ResponseChannel] = None
    response_text: Optional[str] = Field(None, min_length=10, max_length=5000)
    quick_actions: Optional[List[QuickActionButton]] = None
    trigger_keywords: Optional[List[str]] = None
    icon: Optional[str] = None
    order: Optional[int] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_response_id() -> str:
    """Generate unique response ID."""
    return f"resp-{uuid.uuid4().hex[:12]}"


async def log_canned_response_action(
    action: str,
    response_id: str,
    actor_email: str,
    before_state: Optional[Dict] = None,
    after_state: Optional[Dict] = None,
    details: Optional[Dict] = None
):
    """Create audit log entry for canned response actions."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db["audit_logs"].insert_one({
        "action": action,
        "actor_type": "admin",
        "actor_id": actor_email,
        "resource_type": "canned_response",
        "resource_id": response_id,
        "details": {
            **(details or {}),
            "before_state": json.dumps(before_state, default=str)[:5000] if before_state else None,
            "after_state": json.dumps(after_state, default=str)[:5000] if after_state else None,
        },
        "created_at": now,
    })


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("")
async def list_canned_responses(
    category: Optional[ResponseCategory] = None,
    channel: Optional[ResponseChannel] = None,
    include_inactive: bool = False,
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(admin_route_guard)
):
    """List all canned responses with filters."""
    db = database.get_db()
    
    # Build filter
    filter_query = {}
    if not include_inactive:
        filter_query["is_active"] = True
    if category:
        filter_query["category"] = category.value
    if channel:
        filter_query["channel"] = channel.value
    if search:
        filter_query["$or"] = [
            {"label": {"$regex": search, "$options": "i"}},
            {"response_text": {"$regex": search, "$options": "i"}},
        ]
    
    # Get responses
    cursor = db[COLLECTION].find(
        filter_query,
        {"_id": 0}
    ).sort([("order", 1), ("created_at", -1)]).skip(skip).limit(limit)
    
    responses = await cursor.to_list(length=limit)
    total = await db[COLLECTION].count_documents(filter_query)
    
    # Get category counts
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    ]
    category_counts = {}
    async for doc in db[COLLECTION].aggregate(pipeline):
        category_counts[doc["_id"]] = doc["count"]
    
    return {
        "responses": responses,
        "total": total,
        "category_counts": category_counts,
        "channels": [c.value for c in ResponseChannel],
        "categories": [c.value for c in ResponseCategory],
    }


@router.get("/{response_id}")
async def get_canned_response(
    response_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Get a single canned response by ID."""
    db = database.get_db()
    
    response = await db[COLLECTION].find_one(
        {"response_id": response_id},
        {"_id": 0}
    )
    
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    
    return response


@router.post("")
async def create_canned_response(
    request: CannedResponseCreate,
    current_user: dict = Depends(admin_route_guard)
):
    """Create a new canned response."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    response_id = generate_response_id()
    
    doc = {
        "response_id": response_id,
        "label": request.label,
        "category": request.category.value,
        "channel": request.channel.value,
        "response_text": request.response_text,
        "quick_actions": [qa.model_dump() for qa in request.quick_actions] if request.quick_actions else [],
        "trigger_keywords": request.trigger_keywords or [],
        "icon": request.icon or "💬",
        "order": request.order,
        "is_active": True,
        "created_at": now,
        "created_by": current_user.get("email"),
        "updated_at": now,
        "updated_by": current_user.get("email"),
    }
    
    await db[COLLECTION].insert_one(doc)
    
    # Remove _id for response
    doc.pop("_id", None)
    
    # Audit log
    await log_canned_response_action(
        action="CANNED_RESPONSE_CREATED",
        response_id=response_id,
        actor_email=current_user.get("email"),
        after_state=doc,
    )
    
    logger.info(f"Canned response created: {response_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "response_id": response_id,
        "response": doc,
    }


@router.put("/{response_id}")
async def update_canned_response(
    response_id: str,
    request: CannedResponseUpdate,
    current_user: dict = Depends(admin_route_guard)
):
    """Update an existing canned response."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get current state
    current = await db[COLLECTION].find_one({"response_id": response_id})
    if not current:
        raise HTTPException(status_code=404, detail="Response not found")
    
    before_state = {k: v for k, v in current.items() if k != "_id"}
    
    # Build update
    update_data = {"updated_at": now, "updated_by": current_user.get("email")}
    
    if request.label is not None:
        update_data["label"] = request.label
    if request.category is not None:
        update_data["category"] = request.category.value
    if request.channel is not None:
        update_data["channel"] = request.channel.value
    if request.response_text is not None:
        update_data["response_text"] = request.response_text
    if request.quick_actions is not None:
        update_data["quick_actions"] = [qa.model_dump() for qa in request.quick_actions]
    if request.trigger_keywords is not None:
        update_data["trigger_keywords"] = request.trigger_keywords
    if request.icon is not None:
        update_data["icon"] = request.icon
    if request.order is not None:
        update_data["order"] = request.order
    
    await db[COLLECTION].update_one(
        {"response_id": response_id},
        {"$set": update_data}
    )
    
    # Get updated doc
    updated = await db[COLLECTION].find_one({"response_id": response_id}, {"_id": 0})
    
    # Audit log
    await log_canned_response_action(
        action="CANNED_RESPONSE_UPDATED",
        response_id=response_id,
        actor_email=current_user.get("email"),
        before_state=before_state,
        after_state=updated,
    )
    
    logger.info(f"Canned response updated: {response_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "response": updated,
    }


@router.delete("/{response_id}")
async def deactivate_canned_response(
    response_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Soft delete (deactivate) a canned response."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get current state
    current = await db[COLLECTION].find_one({"response_id": response_id})
    if not current:
        raise HTTPException(status_code=404, detail="Response not found")
    
    before_state = {k: v for k, v in current.items() if k != "_id"}
    
    # Soft delete
    await db[COLLECTION].update_one(
        {"response_id": response_id},
        {
            "$set": {
                "is_active": False,
                "deactivated_at": now,
                "deactivated_by": current_user.get("email"),
            }
        }
    )
    
    # Audit log
    await log_canned_response_action(
        action="CANNED_RESPONSE_DEACTIVATED",
        response_id=response_id,
        actor_email=current_user.get("email"),
        before_state=before_state,
        details={"deactivated_at": now},
    )
    
    logger.info(f"Canned response deactivated: {response_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": "Response deactivated",
    }


@router.post("/{response_id}/reactivate")
async def reactivate_canned_response(
    response_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Reactivate a deactivated canned response."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    result = await db[COLLECTION].update_one(
        {"response_id": response_id},
        {
            "$set": {
                "is_active": True,
                "reactivated_at": now,
                "reactivated_by": current_user.get("email"),
            },
            "$unset": {"deactivated_at": 1, "deactivated_by": 1}
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Response not found")
    
    # Audit log
    await log_canned_response_action(
        action="CANNED_RESPONSE_REACTIVATED",
        response_id=response_id,
        actor_email=current_user.get("email"),
        details={"reactivated_at": now},
    )
    
    return {"success": True, "message": "Response reactivated"}


@router.get("/{response_id}/preview")
async def preview_response(
    response_id: str,
    channel: ResponseChannel = ResponseChannel.WEB_CHAT,
    current_user: dict = Depends(admin_route_guard)
):
    """Preview how a response will look in different channels."""
    db = database.get_db()
    
    response = await db[COLLECTION].find_one(
        {"response_id": response_id},
        {"_id": 0}
    )
    
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    
    # Format preview based on channel
    preview = {
        "channel": channel.value,
        "response_text": response["response_text"],
        "quick_actions": response.get("quick_actions", []),
    }
    
    if channel == ResponseChannel.WHATSAPP:
        # WhatsApp uses plain text, strip markdown
        plain_text = response["response_text"]
        plain_text = plain_text.replace("**", "").replace("*", "")
        preview["formatted_text"] = plain_text
        preview["preview_note"] = "WhatsApp: Plain text only, no buttons"
    
    elif channel == ResponseChannel.EMAIL:
        preview["formatted_text"] = response["response_text"]
        preview["preview_note"] = "Email: Full HTML/Markdown supported"
    
    else:  # WEB_CHAT
        preview["formatted_text"] = response["response_text"]
        preview["preview_note"] = "Web Chat: Markdown + Quick Action buttons"
    
    return preview


# ============================================================================
# PUBLIC ENDPOINT - Get active responses for chat widget
# ============================================================================

async def get_active_quick_actions() -> List[Dict[str, Any]]:
    """
    Get active canned responses formatted for the chat widget.
    Called by support routes.
    """
    db = database.get_db()
    
    cursor = db[COLLECTION].find(
        {"is_active": True, "channel": ResponseChannel.WEB_CHAT.value},
        {"_id": 0}
    ).sort("order", 1).limit(10)
    
    responses = await cursor.to_list(length=10)
    
    return [
        {
            "id": r["response_id"],
            "label": r["label"],
            "icon": r.get("icon", "💬"),
            "description": r["response_text"][:50] + "..." if len(r["response_text"]) > 50 else r["response_text"],
            "category": r["category"],
        }
        for r in responses
    ]


async def get_response_by_id(response_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific canned response by ID."""
    db = database.get_db()
    
    return await db[COLLECTION].find_one(
        {"response_id": response_id, "is_active": True},
        {"_id": 0}
    )
