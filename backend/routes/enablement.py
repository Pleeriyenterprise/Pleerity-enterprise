"""
Customer Enablement Automation Engine - Admin Routes
Admin observability and control for the enablement system
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from middleware import admin_route_guard
from models.enablement import (
    EnablementEventType, EnablementCategory, DeliveryChannel,
    EnablementActionStatus, TriggerEnablementRequest,
    CreateSuppressionRequest, UpdatePreferencesRequest
)
from services.enablement_service import (
    emit_enablement_event,
    get_client_enablement_timeline,
    get_enablement_stats,
    create_suppression_rule,
    list_suppression_rules,
    deactivate_suppression_rule,
    update_client_preferences,
    get_client_preferences,
    EnablementEventBus
)
from services.enablement_templates import seed_enablement_templates
from database import database
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/enablement", tags=["Enablement"])


# ============================================
# Dashboard & Statistics
# ============================================

@router.get("/stats")
async def get_stats(
    days: int = Query(30, ge=1, le=365),
    admin: dict = Depends(admin_route_guard)
):
    """Get enablement statistics for dashboard"""
    stats = await get_enablement_stats(days=days)
    return stats


@router.get("/overview")
async def get_overview(admin: dict = Depends(admin_route_guard)):
    """Get enablement system overview"""
    db = database.get_db()
    
    # Get template count
    template_count = await db.enablement_templates.count_documents({"is_active": True})
    
    # Get active suppressions
    suppression_count = await db.enablement_suppressions.count_documents({"active": True})
    
    # Get recent actions
    recent_actions = await db.enablement_actions.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Get event bus subscribers
    subscribers = EnablementEventBus.get_subscribers()
    
    return {
        "active_templates": template_count,
        "active_suppressions": suppression_count,
        "event_subscribers": subscribers,
        "recent_actions": recent_actions
    }


# ============================================
# Client Timeline
# ============================================

class TimelineResponse(BaseModel):
    client_id: str
    actions: list
    total: int
    limit: int
    offset: int


@router.get("/clients/{client_id}/timeline")
async def get_client_timeline(
    client_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(admin_route_guard)
):
    """Get enablement timeline for a specific client"""
    actions, total = await get_client_enablement_timeline(
        client_id=client_id,
        limit=limit,
        offset=offset
    )
    
    return {
        "client_id": client_id,
        "actions": [a.model_dump() for a in actions],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/clients/{client_id}/preferences")
async def get_client_prefs(
    client_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Get enablement preferences for a client"""
    prefs = await get_client_preferences(client_id)
    return prefs.model_dump()


@router.put("/clients/{client_id}/preferences")
async def update_client_prefs(
    client_id: str,
    request: UpdatePreferencesRequest,
    admin: dict = Depends(admin_route_guard)
):
    """Update enablement preferences for a client (admin override)"""
    prefs = await update_client_preferences(
        client_id=client_id,
        in_app_enabled=request.in_app_enabled,
        email_enabled=request.email_enabled,
        assistant_enabled=request.assistant_enabled,
        categories_enabled=request.categories_enabled
    )
    return prefs.model_dump()


# ============================================
# Suppression Rules
# ============================================

@router.get("/suppressions")
async def list_suppressions(
    active_only: bool = True,
    admin: dict = Depends(admin_route_guard)
):
    """List all suppression rules"""
    rules = await list_suppression_rules(active_only=active_only)
    return {"rules": [r.model_dump() for r in rules]}


@router.post("/suppressions")
async def create_suppression(
    request: CreateSuppressionRequest,
    admin: dict = Depends(admin_route_guard)
):
    """Create a new suppression rule"""
    rule = await create_suppression_rule(
        client_id=request.client_id,
        category=request.category,
        template_code=request.template_code,
        reason=request.reason,
        expires_at=request.expires_at,
        created_by=admin.get("portal_user_id", "unknown")
    )
    return rule.model_dump()


@router.delete("/suppressions/{rule_id}")
async def remove_suppression(
    rule_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Deactivate a suppression rule"""
    success = await deactivate_suppression_rule(
        rule_id=rule_id,
        admin_id=admin.get("portal_user_id", "unknown")
    )
    if not success:
        raise HTTPException(status_code=404, detail="Suppression rule not found")
    return {"success": True}


# ============================================
# Templates
# ============================================

@router.get("/templates")
async def list_templates(
    active_only: bool = True,
    category: Optional[EnablementCategory] = None,
    admin: dict = Depends(admin_route_guard)
):
    """List all enablement templates"""
    db = database.get_db()
    
    query = {}
    if active_only:
        query["is_active"] = True
    if category:
        query["category"] = category.value
    
    templates = await db.enablement_templates.find(
        query,
        {"_id": 0}
    ).sort("category", 1).to_list(None)
    
    return {"templates": templates, "total": len(templates)}


@router.post("/templates/seed")
async def reseed_templates(admin: dict = Depends(admin_route_guard)):
    """Reseed default templates (updates existing, adds new)"""
    result = await seed_enablement_templates()
    return {"success": True, **result}


@router.put("/templates/{template_code}/toggle")
async def toggle_template(
    template_code: str,
    admin: dict = Depends(admin_route_guard)
):
    """Toggle a template's active status"""
    db = database.get_db()
    
    template = await db.enablement_templates.find_one({"template_code": template_code})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    new_status = not template.get("is_active", True)
    
    await db.enablement_templates.update_one(
        {"template_code": template_code},
        {"$set": {"is_active": new_status}}
    )
    
    return {"template_code": template_code, "is_active": new_status}


# ============================================
# Manual Trigger (Admin/Testing)
# ============================================

@router.post("/trigger")
async def trigger_enablement(
    request: TriggerEnablementRequest,
    admin: dict = Depends(admin_route_guard)
):
    """
    Manually trigger an enablement event (for testing/admin use).
    This respects all suppression and preference rules.
    """
    db = database.get_db()
    
    # Verify client exists
    client = await db.clients.find_one({"client_id": request.client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Emit the event
    event = await emit_enablement_event(
        event_type=request.event_type,
        client_id=request.client_id,
        plan_code=client.get("plan_code"),
        context_payload=request.context_payload
    )
    
    return {
        "success": True,
        "event_id": event.event_id,
        "message": f"Enablement event {request.event_type.value} triggered for client {request.client_id}"
    }


# ============================================
# Actions Query
# ============================================

@router.get("/actions")
async def list_actions(
    status: Optional[EnablementActionStatus] = None,
    category: Optional[EnablementCategory] = None,
    channel: Optional[DeliveryChannel] = None,
    client_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(admin_route_guard)
):
    """Query enablement actions with filters"""
    db = database.get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if category:
        query["category"] = category.value
    if channel:
        query["channel"] = channel.value
    if client_id:
        query["client_id"] = client_id
    
    total = await db.enablement_actions.count_documents(query)
    
    actions = await db.enablement_actions.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    return {
        "actions": actions,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ============================================
# Events Query
# ============================================

@router.get("/events")
async def list_events(
    event_type: Optional[EnablementEventType] = None,
    client_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(admin_route_guard)
):
    """Query enablement events"""
    db = database.get_db()
    
    query = {}
    if event_type:
        query["event_type"] = event_type.value
    if client_id:
        query["client_id"] = client_id
    
    total = await db.enablement_events.count_documents(query)
    
    events = await db.enablement_events.find(
        query,
        {"_id": 0}
    ).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
    
    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ============================================
# Event Types Reference
# ============================================

@router.get("/event-types")
async def get_event_types(admin: dict = Depends(admin_route_guard)):
    """Get all available enablement event types"""
    return {
        "event_types": [
            {"value": et.value, "label": et.value.replace("_", " ").title()}
            for et in EnablementEventType
        ],
        "categories": [
            {"value": cat.value, "label": cat.value.replace("_", " ").title()}
            for cat in EnablementCategory
        ],
        "channels": [
            {"value": ch.value, "label": ch.value.replace("_", " ").title()}
            for ch in DeliveryChannel
        ],
        "statuses": [
            {"value": st.value, "label": st.value}
            for st in EnablementActionStatus
        ]
    }
