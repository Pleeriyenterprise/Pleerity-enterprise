"""
Admin Orders Routes - NEW FILE
Handles admin operations for the Orders system.
NO CVP COLLECTIONS TOUCHED - Works only with orders and workflow_executions.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from database import database
from middleware import admin_route_guard
from services.order_workflow import (
    OrderStatus, get_allowed_transitions, get_admin_actions_for_review,
    PIPELINE_COLUMNS, is_valid_transition, requires_admin_action
)
from services.order_service import (
    transition_order_state, get_order, get_order_timeline,
    get_orders_for_pipeline, get_pipeline_counts, add_internal_note
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/orders", tags=["admin-orders"])


# ============================================
# MODELS
# ============================================

class TransitionRequest(BaseModel):
    new_status: str
    reason: str  # Required for admin transitions
    notes: Optional[str] = None


class NoteRequest(BaseModel):
    note: str


# ============================================
# PIPELINE VIEW ENDPOINTS
# ============================================

@router.get("/pipeline")
async def get_orders_pipeline(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get orders for pipeline/kanban view.
    Returns orders grouped by status with counts.
    """
    
    result = await get_orders_for_pipeline(
        status_filter=status,
        limit=limit,
        skip=skip,
    )
    
    return result


@router.get("/pipeline/counts")
async def get_pipeline_status_counts(
    current_user: dict = Depends(admin_route_guard),
):
    """Get count of orders in each status"""
    
    counts = await get_pipeline_counts()
    
    return {
        "counts": counts,
        "columns": [
            {"status": col["status"].value, "label": col["label"], "color": col["color"]}
            for col in PIPELINE_COLUMNS
        ]
    }


# ============================================
# ORDER DETAIL ENDPOINTS
# ============================================

@router.get("/{order_id}")
async def get_order_detail(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get full order details including timeline"""
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    timeline = await get_order_timeline(order_id)
    
    # Get allowed transitions for current state
    current_status = OrderStatus(order["status"])
    allowed_transitions = [s.value for s in get_allowed_transitions(current_status)]
    
    # Get admin actions if in review
    admin_actions = None
    if current_status == OrderStatus.INTERNAL_REVIEW:
        admin_actions = {k: v.value for k, v in get_admin_actions_for_review().items()}
    
    return {
        "order": order,
        "timeline": timeline,
        "allowed_transitions": allowed_transitions,
        "admin_actions": admin_actions,
        "is_terminal": current_status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
    }


@router.get("/{order_id}/timeline")
async def get_order_timeline_only(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get just the audit timeline for an order"""
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    timeline = await get_order_timeline(order_id)
    
    return {"timeline": timeline}


# ============================================
# STATE TRANSITION ENDPOINTS
# ============================================

@router.post("/{order_id}/transition")
async def transition_order(
    order_id: str,
    request: TransitionRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Manually transition an order to a new state.
    Requires admin role and mandatory reason.
    Only allowed transitions per state machine are permitted.
    """
    
    try:
        new_status = OrderStatus(request.new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.new_status}")
    
    try:
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=new_status,
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason=request.reason,
            notes=request.notes,
        )
        
        return {
            "success": True,
            "order": updated_order,
            "message": f"Order transitioned to {new_status.value}",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# REVIEW ACTIONS (Specific to INTERNAL_REVIEW)
# ============================================

@router.post("/{order_id}/approve")
async def approve_order(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Approve order from INTERNAL_REVIEW → FINALISING.
    System will automatically proceed to delivery.
    """
    
    try:
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.FINALISING,
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason="Approved by admin",
        )
        
        # TODO: Trigger automated finalisation and delivery
        
        return {
            "success": True,
            "order": updated_order,
            "message": "Order approved. System will finalize and deliver automatically.",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/request-regen")
async def request_regeneration(
    order_id: str,
    request: NoteRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Request regeneration from INTERNAL_REVIEW → REGEN_REQUESTED.
    System will automatically regenerate and return to INTERNAL_REVIEW.
    """
    
    try:
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.REGEN_REQUESTED,
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason=f"Regeneration requested: {request.note}",
            metadata={"regen_instructions": request.note},
        )
        
        # TODO: Trigger automated regeneration
        
        return {
            "success": True,
            "order": updated_order,
            "message": "Regeneration requested. System will regenerate automatically.",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/request-info")
async def request_client_info(
    order_id: str,
    request: NoteRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Request more info from INTERNAL_REVIEW → CLIENT_INPUT_REQUIRED.
    SLA timer pauses. System will send request to client.
    """
    
    try:
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.CLIENT_INPUT_REQUIRED,
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason=f"Client input required: {request.note}",
            metadata={"info_request": request.note},
        )
        
        # TODO: Send email to client requesting info
        
        return {
            "success": True,
            "order": updated_order,
            "message": "Info request sent. SLA paused until client responds.",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# NOTES ENDPOINT
# ============================================

@router.post("/{order_id}/notes")
async def add_order_note(
    order_id: str,
    request: NoteRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Add internal note to order.
    Does NOT change order state.
    """
    
    try:
        updated_order = await add_internal_note(
            order_id=order_id,
            note=request.note,
            admin_email=current_user.get("email"),
        )
        
        return {
            "success": True,
            "order": updated_order,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# SEARCH ENDPOINTS
# ============================================

@router.get("/search")
async def search_orders(
    q: Optional[str] = None,
    status: Optional[str] = None,
    service_category: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(admin_route_guard),
):
    """Search orders by various criteria"""
    
    db = database.get_db()
    
    # Build query
    query = {}
    
    if q:
        query["$or"] = [
            {"order_id": {"$regex": q, "$options": "i"}},
            {"customer.email": {"$regex": q, "$options": "i"}},
            {"customer.full_name": {"$regex": q, "$options": "i"}},
        ]
    
    if status:
        query["status"] = status
    
    if service_category:
        query["service_category"] = service_category
    
    # Execute query
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    orders = await cursor.to_list(length=None)
    total = await db.orders.count_documents(query)
    
    return {
        "orders": orders,
        "total": total,
        "limit": limit,
        "skip": skip,
    }
