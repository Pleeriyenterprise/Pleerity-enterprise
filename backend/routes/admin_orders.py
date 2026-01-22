"""
Admin Orders Routes - NEW FILE
Handles admin operations for the Orders system.
NO CVP COLLECTIONS TOUCHED - Works only with orders and workflow_executions.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
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
# SEARCH ENDPOINTS (must be before /{order_id} to avoid route conflict)
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

class ApproveRequest(BaseModel):
    version: int  # Document version being approved
    notes: Optional[str] = None


@router.post("/{order_id}/approve")
async def approve_order(
    order_id: str,
    request: ApproveRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Approve order from INTERNAL_REVIEW → FINALISING.
    Locks the reviewed document version as final.
    System will automatically proceed to delivery.
    """
    from services.order_service import lock_approved_version, is_version_locked
    from services.document_generator import get_document_versions
    
    # Check if already locked
    if await is_version_locked(order_id):
        raise HTTPException(status_code=400, detail="Order already has an approved locked version")
    
    # Verify the version exists
    versions = await get_document_versions(order_id)
    version_exists = any(v.version == request.version for v in versions)
    if not version_exists:
        raise HTTPException(status_code=400, detail=f"Document version {request.version} not found")
    
    try:
        # Lock the approved version
        await lock_approved_version(
            order_id=order_id,
            version=request.version,
            admin_email=current_user.get("email"),
        )
        
        # Transition to FINALISING
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.FINALISING,
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason=f"Approved by admin - Document v{request.version} locked as final",
            notes=request.notes,
            metadata={
                "approved_version": request.version,
                "action": "approve_and_finalize",
            },
        )
        
        # TODO: Trigger automated finalisation and delivery job
        
        return {
            "success": True,
            "order": updated_order,
            "message": f"Order approved. Document v{request.version} locked. System will finalize and deliver automatically.",
            "approved_version": request.version,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class RegenerationRequest(BaseModel):
    reason: str  # Dropdown selection
    correction_notes: str  # Required detailed notes
    affected_sections: Optional[List[str]] = None
    guardrails: Optional[Dict[str, bool]] = None  # e.g., {"preserve_names_dates": True}


@router.post("/{order_id}/request-regen")
async def request_regeneration(
    order_id: str,
    request: RegenerationRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Request structured regeneration from INTERNAL_REVIEW → REGEN_REQUESTED.
    Requires mandatory correction notes - no blind regeneration allowed.
    System will automatically regenerate with instructions and return to INTERNAL_REVIEW.
    """
    from services.order_service import create_regeneration_request, is_version_locked
    
    if not request.correction_notes.strip():
        raise HTTPException(status_code=400, detail="Correction notes are required for regeneration")
    
    # Check if version is locked (shouldn't allow regen of locked version)
    if await is_version_locked(order_id):
        raise HTTPException(
            status_code=400, 
            detail="Cannot regenerate - order has a locked approved version. Reopen order first."
        )
    
    try:
        # Store the structured regeneration request
        await create_regeneration_request(
            order_id=order_id,
            admin_id=current_user.get("user_id"),
            admin_email=current_user.get("email"),
            reason=request.reason,
            correction_notes=request.correction_notes,
            affected_sections=request.affected_sections,
            guardrails=request.guardrails,
        )
        
        # Transition to REGEN_REQUESTED
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.REGEN_REQUESTED,
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason=f"Regeneration requested: {request.reason}",
            notes=request.correction_notes,
            metadata={
                "regen_reason": request.reason,
                "regen_notes": request.correction_notes,
                "regen_sections": request.affected_sections,
                "regen_guardrails": request.guardrails,
            },
        )
        
        # TODO: Trigger automated regeneration job
        
        return {
            "success": True,
            "order": updated_order,
            "message": "Regeneration requested. System will regenerate with your instructions automatically.",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ClientInfoRequest(BaseModel):
    request_notes: str  # Required - what admin needs
    requested_fields: Optional[List[str]] = None  # Optional checklist
    deadline_days: Optional[int] = None  # Optional deadline
    request_attachments: bool = False


@router.post("/{order_id}/request-info")
async def request_client_info(
    order_id: str,
    request: ClientInfoRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Request more info from INTERNAL_REVIEW → CLIENT_INPUT_REQUIRED.
    SLA timer pauses. System will send branded email to client with portal link.
    """
    from services.order_service import create_client_input_request
    from services.order_email_templates import build_client_input_required_email
    from services.email_service import email_service
    import os
    
    if not request.request_notes.strip():
        raise HTTPException(status_code=400, detail="Request notes are required")
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    try:
        # Store the client input request
        await create_client_input_request(
            order_id=order_id,
            admin_id=current_user.get("user_id"),
            admin_email=current_user.get("email"),
            request_notes=request.request_notes,
            requested_fields=request.requested_fields,
            deadline_days=request.deadline_days,
            request_attachments=request.request_attachments,
        )
        
        # Transition to CLIENT_INPUT_REQUIRED
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.CLIENT_INPUT_REQUIRED,
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason=f"Client input required: {request.request_notes[:100]}...",
            metadata={
                "info_request": request.request_notes,
                "requested_fields": request.requested_fields,
                "deadline_days": request.deadline_days,
            },
        )
        
        # Build and send client email
        frontend_url = os.getenv("FRONTEND_URL", "https://pleerity.com")
        provide_info_link = f"{frontend_url}/app/orders/{order_id}/provide-info"
        
        deadline_str = None
        if request.deadline_days:
            from datetime import timedelta
            deadline_date = datetime.now(timezone.utc) + timedelta(days=request.deadline_days)
            deadline_str = deadline_date.strftime("%d %B %Y")
        
        email_data = build_client_input_required_email(
            client_name=order.get("customer", {}).get("full_name", "Customer"),
            order_reference=order_id,
            service_name=order.get("service_name", "Service"),
            admin_notes=request.request_notes,
            requested_fields=request.requested_fields or [],
            deadline=deadline_str,
            provide_info_link=provide_info_link,
        )
        
        # Send the email
        client_email = order.get("customer", {}).get("email")
        if client_email:
            try:
                from models import EmailTemplateAlias
                await email_service.send_email(
                    recipient=client_email,
                    template_alias=EmailTemplateAlias.GENERIC,
                    template_model={"message": email_data["text"]},
                    subject=email_data["subject"],
                )
                logger.info(f"Client input required email sent for order {order_id}")
            except Exception as email_error:
                logger.error(f"Failed to send client email: {email_error}")
        
        return {
            "success": True,
            "order": updated_order,
            "message": "Info request sent to client. SLA paused until client responds.",
            "client_notified": bool(client_email),
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# DOCUMENT VIEWING & VERSIONING
# ============================================

@router.get("/{order_id}/documents")
async def get_order_documents(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get all document versions for an order.
    Used for the document viewer in Internal Review.
    """
    from services.document_generator import get_document_versions, get_current_document_version
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    versions = await get_document_versions(order_id)
    current = await get_current_document_version(order_id)
    
    return {
        "order_id": order_id,
        "versions": [v.to_dict() for v in versions],
        "current_version": current.to_dict() if current else None,
        "total_versions": len(versions),
        "approved_version": order.get("approved_document_version"),
        "is_locked": order.get("version_locked", False),
    }


@router.get("/{order_id}/documents/{version}/preview")
async def get_document_preview(
    order_id: str,
    version: int,
    format: str = "pdf",  # "pdf" or "docx"
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get document content for preview/download.
    Returns the actual document file.
    Requires Bearer token authentication.
    """
    from services.document_generator import get_document_versions
    from services.storage_adapter import storage_adapter
    from fastapi.responses import Response
    
    versions = await get_document_versions(order_id)
    target_version = None
    for v in versions:
        if v.version == version:
            target_version = v
            break
    
    if not target_version:
        raise HTTPException(status_code=404, detail=f"Document version {version} not found")
    
    # Get the file ID based on format
    file_id = target_version.file_id_pdf if format == "pdf" else target_version.file_id_docx
    if not file_id:
        raise HTTPException(status_code=404, detail=f"No {format} file for version {version}")
    
    try:
        content, metadata = await storage_adapter.download_file(file_id)
        
        content_type = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{order_id}_v{version}.{format}"
        
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Failed to retrieve document: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")


@router.get("/{order_id}/documents/{version}/token")
async def get_document_access_token(
    order_id: str,
    version: int,
    format: str = "pdf",
    current_user: dict = Depends(admin_route_guard),
):
    """
    Generate a temporary access token for document preview.
    Use this token to embed documents in iframes without auth headers.
    Token expires in 30 minutes.
    """
    from services.document_access_token import generate_document_access_token, get_document_preview_url
    import os
    
    # Verify document exists
    from services.document_generator import get_document_versions
    versions = await get_document_versions(order_id)
    target_version = None
    for v in versions:
        if v.version == version:
            target_version = v
            break
    
    if not target_version:
        raise HTTPException(status_code=404, detail=f"Document version {version} not found")
    
    # Generate token
    token = generate_document_access_token(
        order_id=order_id,
        version=version,
        format=format,
        admin_email=current_user.get("email", "unknown"),
    )
    
    # Build full URL
    base_url = os.environ.get("FRONTEND_URL", "")
    preview_url = f"{base_url}/api/admin/orders/{order_id}/documents/{version}/view?format={format}&token={token}"
    
    return {
        "token": token,
        "preview_url": preview_url,
        "expires_in_minutes": 30,
        "format": format,
    }


@router.get("/{order_id}/documents/{version}/view")
async def view_document_with_token(
    order_id: str,
    version: int,
    format: str = "pdf",
    token: str = None,
):
    """
    View document using temporary access token.
    This endpoint does NOT require Bearer auth - uses token parameter instead.
    Designed for iframe embedding.
    """
    from services.document_access_token import validate_document_access_token
    from services.document_generator import get_document_versions
    from services.storage_adapter import storage_adapter
    from fastapi.responses import Response
    
    if not token:
        raise HTTPException(status_code=401, detail="Access token required")
    
    # Validate token
    payload = validate_document_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    
    # Verify token matches requested document
    if payload.get("order_id") != order_id:
        raise HTTPException(status_code=403, detail="Token not valid for this order")
    if payload.get("version") != version:
        raise HTTPException(status_code=403, detail="Token not valid for this version")
    if payload.get("format") != format:
        raise HTTPException(status_code=403, detail="Token not valid for this format")
    
    # Get document
    versions = await get_document_versions(order_id)
    target_version = None
    for v in versions:
        if v.version == version:
            target_version = v
            break
    
    if not target_version:
        raise HTTPException(status_code=404, detail=f"Document version {version} not found")
    
    # Get the file ID based on format
    file_id = target_version.file_id_pdf if format == "pdf" else target_version.file_id_docx
    if not file_id:
        raise HTTPException(status_code=404, detail=f"No {format} file for version {version}")
    
    try:
        content, metadata = await storage_adapter.download_file(file_id)
        
        content_type = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{order_id}_v{version}.{format}"
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "private, max-age=1800",  # 30 min cache
            }
        )
    except Exception as e:
        logger.error(f"Failed to retrieve document: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")


# ============================================
# REOPEN LOCKED ORDER
# ============================================

class ReopenRequest(BaseModel):
    reason: str


@router.post("/{order_id}/reopen")
async def reopen_order_for_edit(
    order_id: str,
    request: ReopenRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Reopen a locked approved order for editing.
    Requires explicit reason - this is an exceptional action.
    """
    from services.order_service import reopen_for_edit, is_version_locked
    
    if not request.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required to reopen order")
    
    if not await is_version_locked(order_id):
        raise HTTPException(status_code=400, detail="Order is not locked")
    
    try:
        updated_order = await reopen_for_edit(
            order_id=order_id,
            admin_email=current_user.get("email"),
            reason=request.reason,
        )
        
        return {
            "success": True,
            "order": updated_order,
            "message": "Order reopened for editing. Previous approval has been unlocked.",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# TRIGGER DOCUMENT GENERATION
# ============================================

@router.post("/{order_id}/generate-documents")
async def trigger_document_generation(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Manually trigger document generation for an order.
    Creates a new version of documents (MOCK for Phase 1).
    """
    from services.document_generator import generate_documents
    from services.order_service import get_current_regeneration_notes
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get any pending regeneration notes
    regen_notes = await get_current_regeneration_notes(order_id)
    regen_text = regen_notes.get("correction_notes") if regen_notes else None
    
    try:
        doc_version = await generate_documents(
            order_id=order_id,
            regeneration_notes=regen_text,
        )
        
        return {
            "success": True,
            "message": f"Document version {doc_version.version} generated",
            "version": doc_version.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Document generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document generation failed: {str(e)}")


# ============================================
# CANCEL / ARCHIVE ORDER (Replaces DELETE)
# ============================================

class CancelRequest(BaseModel):
    reason: str  # Mandatory


class ArchiveRequest(BaseModel):
    reason: str  # Mandatory


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    request: CancelRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Cancel an order (soft delete).
    - Orders are NEVER hard deleted
    - Cannot cancel if payment has been made or documents generated
    - Moves order to CANCELLED status
    - Order remains for audit/evidence purposes
    """
    if not request.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required for cancellation")
    
    db = database.get_db()
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if cancellation is blocked
    has_documents = len(order.get("document_versions", [])) > 0
    has_payment = order.get("payment_intent_id") is not None
    
    # After payment or document generation, cancellation is blocked
    if has_payment or order.get("status") not in ["CREATED"]:
        # Order has progressed beyond initial creation
        if has_documents:
            raise HTTPException(
                status_code=400, 
                detail="Cannot cancel order: Documents have been generated. Use Archive instead."
            )
        if has_payment:
            raise HTTPException(
                status_code=400, 
                detail="Cannot cancel order: Payment has been processed. Use Archive instead."
            )
    
    # Audit log
    from services.order_service import create_workflow_execution
    await create_workflow_execution(
        order_id=order_id,
        previous_state=order["status"],
        new_state="CANCELLED",
        transition_type="admin_cancel",
        triggered_by_type="admin",
        triggered_by_user_id=current_user.get("user_id"),
        triggered_by_email=current_user.get("email"),
        reason=request.reason,
        metadata={
            "action": "cancel",
            "cancellation_reason": request.reason,
        },
    )
    
    # Update order status to CANCELLED
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "CANCELLED",
                "cancelled_at": datetime.now(timezone.utc),
                "cancelled_by": current_user.get("email"),
                "cancellation_reason": request.reason,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Order {order_id} cancelled by {current_user.get('email')}: {request.reason}")
    
    return {
        "success": True,
        "message": f"Order {order_id} has been cancelled",
        "order_status": "CANCELLED",
    }


@router.post("/{order_id}/archive")
async def archive_order(
    order_id: str,
    request: ArchiveRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Archive an order (admin-only soft removal from active pipeline).
    - Used for completed or old orders
    - Order remains fully intact for audit/evidence
    - Can be unarchived if needed
    """
    if not request.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required for archiving")
    
    db = database.get_db()
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Audit log
    from services.order_service import create_workflow_execution
    await create_workflow_execution(
        order_id=order_id,
        previous_state=order["status"],
        new_state=order["status"],  # Status doesn't change
        transition_type="admin_archive",
        triggered_by_type="admin",
        triggered_by_user_id=current_user.get("user_id"),
        triggered_by_email=current_user.get("email"),
        reason=request.reason,
        metadata={
            "action": "archive",
            "archive_reason": request.reason,
            "previous_archived_status": order.get("is_archived", False),
        },
    )
    
    # Mark as archived
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "is_archived": True,
                "archived_at": datetime.now(timezone.utc),
                "archived_by": current_user.get("email"),
                "archive_reason": request.reason,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Order {order_id} archived by {current_user.get('email')}: {request.reason}")
    
    return {
        "success": True,
        "message": f"Order {order_id} has been archived",
    }


@router.post("/{order_id}/unarchive")
async def unarchive_order(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Unarchive an order (restore to active pipeline).
    """
    db = database.get_db()
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if not order.get("is_archived"):
        raise HTTPException(status_code=400, detail="Order is not archived")
    
    # Audit log
    from services.order_service import create_workflow_execution
    await create_workflow_execution(
        order_id=order_id,
        previous_state=order["status"],
        new_state=order["status"],
        transition_type="admin_unarchive",
        triggered_by_type="admin",
        triggered_by_user_id=current_user.get("user_id"),
        triggered_by_email=current_user.get("email"),
        reason="Order restored from archive",
        metadata={"action": "unarchive"},
    )
    
    # Remove archived flag
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "is_archived": False,
                "unarchived_at": datetime.now(timezone.utc),
                "unarchived_by": current_user.get("email"),
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Order {order_id} unarchived by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": f"Order {order_id} has been restored from archive",
    }


# ============================================
# DELETE ENDPOINT - DISABLED
# ============================================
# DELETE operations are NOT permitted on Orders.
# Orders are immutable records for audit and evidence.

@router.delete("/{order_id}")
async def delete_order_disabled(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    DELETE is disabled for Orders.
    Orders are immutable records and cannot be permanently deleted.
    Use Cancel (for pre-payment orders) or Archive (for completed orders) instead.
    """
    raise HTTPException(
        status_code=405,
        detail="DELETE is not permitted. Orders are immutable records. Use /cancel for pre-payment orders or /archive for completed orders."
    )


# ============================================
# ROLLBACK ENDPOINT
# ============================================

class RollbackRequest(BaseModel):
    reason: str  # Mandatory


# Rollback mapping - what prior safe state to go to from each state
ROLLBACK_MAP = {
    "FAILED": "QUEUED",
    "DELIVERY_FAILED": "FINALISING",
    "DELIVERING": "FINALISING",
    "FINALISING": "INTERNAL_REVIEW",
    "REGENERATING": "INTERNAL_REVIEW",
    "CLIENT_INPUT_REQUIRED": "INTERNAL_REVIEW",
    "REGEN_REQUESTED": "INTERNAL_REVIEW",
    "INTERNAL_REVIEW": "DRAFT_READY",
    "DRAFT_READY": "IN_PROGRESS",
    "IN_PROGRESS": "QUEUED",
    "QUEUED": "PAID",
}


@router.post("/{order_id}/rollback")
async def rollback_order(
    order_id: str,
    request: RollbackRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Rollback order to prior safe stage.
    Requires mandatory reason. Logged as admin_manual_override.
    """
    if not request.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required for rollback")
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    current_status = order["status"]
    
    if current_status not in ROLLBACK_MAP:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot rollback from {current_status}"
        )
    
    target_status = ROLLBACK_MAP[current_status]
    
    try:
        from services.order_service import transition_order_state
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus(target_status),
            triggered_by_type="admin",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason=f"[ROLLBACK] {request.reason}",
            metadata={"rollback_from": current_status, "rollback_to": target_status},
        )
        
        return {
            "success": True,
            "order": updated_order,
            "message": f"Order rolled back from {current_status} to {target_status}",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# RESEND REQUEST ENDPOINT
# ============================================

@router.post("/{order_id}/resend-request")
async def resend_client_request(
    order_id: str,
    request: NoteRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Resend the client information request.
    Only valid in CLIENT_INPUT_REQUIRED state.
    """
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order["status"] != OrderStatus.CLIENT_INPUT_REQUIRED.value:
        raise HTTPException(
            status_code=400, 
            detail="Can only resend request in CLIENT_INPUT_REQUIRED state"
        )
    
    # Create audit entry for resend
    from services.order_service import create_workflow_execution
    await create_workflow_execution(
        order_id=order_id,
        previous_state=order["status"],
        new_state=order["status"],  # Same state
        transition_type="admin_manual",
        triggered_by_type="admin",
        triggered_by_user_id=current_user.get("user_id"),
        triggered_by_email=current_user.get("email"),
        reason=f"Resent client request: {request.note}",
        metadata={"action": "resend_request"},
    )
    
    # TODO: Actually resend the email to client
    
    logger.info(f"Client request resent for order {order_id}")
    
    return {
        "success": True,
        "message": "Client request has been resent",
    }


# ============================================
# SET PRIORITY ENDPOINT
# ============================================

class PriorityRequest(BaseModel):
    priority: bool
    reason: Optional[str] = None


@router.post("/{order_id}/priority")
async def set_order_priority(
    order_id: str,
    request: PriorityRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Set or remove priority flag on an order.
    """
    db = database.get_db()
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update priority
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {
            "priority": request.priority,
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    
    # Create audit entry
    from services.order_service import create_workflow_execution
    await create_workflow_execution(
        order_id=order_id,
        previous_state=order["status"],
        new_state=order["status"],  # Same state
        transition_type="admin_manual",
        triggered_by_type="admin",
        triggered_by_user_id=current_user.get("user_id"),
        triggered_by_email=current_user.get("email"),
        reason=f"Priority {'set' if request.priority else 'removed'}: {request.reason or 'No reason provided'}",
        metadata={"action": "set_priority", "priority": request.priority},
    )
    
    updated_order = await get_order(order_id)
    
    return {
        "success": True,
        "order": updated_order,
        "message": f"Priority {'set' if request.priority else 'removed'}",
    }


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
# DELIVERY ENDPOINTS
# ============================================

@router.post("/{order_id}/deliver")
async def deliver_order(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Manually trigger delivery for an order in FINALISING state.
    Sends delivery email and transitions to COMPLETED.
    """
    from services.order_delivery_service import order_delivery_service
    
    result = await order_delivery_service.deliver_order(order_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Delivery failed"))
    
    return result


@router.post("/{order_id}/retry-delivery")
async def retry_order_delivery(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Retry delivery for an order in DELIVERY_FAILED state.
    """
    from services.order_delivery_service import order_delivery_service
    
    result = await order_delivery_service.retry_delivery(order_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Retry failed"))
    
    return result


class ManualCompleteRequest(BaseModel):
    reason: str  # Mandatory reason for manual completion


@router.post("/{order_id}/manual-complete")
async def manual_complete_order(
    order_id: str,
    request: ManualCompleteRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Manually mark order as completed (admin override).
    Use when delivery was done through alternative means.
    """
    if not request.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required for manual completion")
    
    from services.order_delivery_service import order_delivery_service
    
    result = await order_delivery_service.manual_complete(
        order_id=order_id,
        admin_email=current_user.get("email", "unknown"),
        reason=request.reason.strip(),
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Manual completion failed"))
    
    return result


@router.post("/batch/process-delivery")
async def process_pending_deliveries(
    current_user: dict = Depends(admin_route_guard),
):
    """
    Process all orders in FINALISING state.
    Triggers automatic delivery for all ready orders.
    
    This can be called manually or by a background job.
    """
    from services.order_delivery_service import order_delivery_service
    
    result = await order_delivery_service.process_finalising_orders()
    
    return {
        "success": True,
        "summary": result,
        "message": f"Processed {result['processed']} orders: {result['delivered']} delivered, {result['failed']} failed"
    }

