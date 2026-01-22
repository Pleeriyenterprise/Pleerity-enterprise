"""
Client Orders Routes - Client-facing order operations
Handles client input submission for the Orders workflow.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from database import database
from middleware import client_route_guard
from services.order_workflow import OrderStatus
from services.order_service import (
    get_order, submit_client_input_response, transition_order_state,
    create_in_app_notification
)
from services.storage_adapter import upload_client_file
from services.order_email_templates import build_client_response_received_email
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/client/orders", tags=["client-orders"])


# ============================================
# CLIENT ORDER VIEW
# ============================================

@router.get("/{order_id}")
async def get_client_order(
    order_id: str,
    current_user: dict = Depends(client_route_guard),
):
    """
    Get order details for client view.
    Only returns client-safe information.
    """
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify this order belongs to the client
    if order.get("customer", {}).get("email") != current_user.get("email"):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    
    # Return client-safe view (no internal notes, etc.)
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "service_name": order["service_name"],
        "service_category": order["service_category"],
        "customer": order["customer"],
        "pricing": order["pricing"],
        "created_at": order.get("created_at"),
        "updated_at": order.get("updated_at"),
        "completed_at": order.get("completed_at"),
        "client_input_request": order.get("client_input_request"),
        "client_input_responses": order.get("client_input_responses", []),
    }


# ============================================
# CLIENT INPUT REQUIRED VIEW
# ============================================

@router.get("/{order_id}/input-required")
async def get_client_input_request(
    order_id: str,
    current_user: dict = Depends(client_route_guard),
):
    """
    Get the current input request for an order.
    Shows what information the admin is requesting.
    """
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify ownership
    if order.get("customer", {}).get("email") != current_user.get("email"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Check if order is in CLIENT_INPUT_REQUIRED state
    if order["status"] != OrderStatus.CLIENT_INPUT_REQUIRED.value:
        return {
            "requires_input": False,
            "message": "No information is currently required for this order",
        }
    
    input_request = order.get("client_input_request", {})
    
    return {
        "requires_input": True,
        "order_id": order_id,
        "service_name": order["service_name"],
        "request_notes": input_request.get("request_notes", ""),
        "requested_fields": input_request.get("requested_fields", []),
        "deadline": input_request.get("deadline"),
        "request_attachments": input_request.get("request_attachments", False),
        "requested_at": input_request.get("requested_at"),
        "previous_responses": order.get("client_input_responses", []),
    }


# ============================================
# SUBMIT CLIENT INPUT
# ============================================

class ClientInputPayload(BaseModel):
    fields: Dict[str, Any]  # Dynamic field values
    confirmation: bool = False  # Client confirmation checkbox


@router.post("/{order_id}/submit-input")
async def submit_client_input(
    order_id: str,
    payload: ClientInputPayload,
    current_user: dict = Depends(client_route_guard),
):
    """
    Submit client's response to an input request.
    Validates, stores versioned response, and auto-transitions back to INTERNAL_REVIEW.
    """
    from services.email_service import email_service
    from models import EmailTemplateAlias
    import os
    
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify ownership
    if order.get("customer", {}).get("email") != current_user.get("email"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Verify order is in CLIENT_INPUT_REQUIRED state
    if order["status"] != OrderStatus.CLIENT_INPUT_REQUIRED.value:
        raise HTTPException(
            status_code=400, 
            detail="Order is not awaiting client input"
        )
    
    # Require confirmation
    if not payload.confirmation:
        raise HTTPException(
            status_code=400,
            detail="Please confirm the information is accurate"
        )
    
    try:
        # Store the client response
        updated_order = await submit_client_input_response(
            order_id=order_id,
            client_id=current_user.get("user_id"),
            client_email=current_user.get("email"),
            payload=payload.fields,
            file_references=None,  # Files handled separately
        )
        
        # Transition back to INTERNAL_REVIEW
        updated_order = await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.INTERNAL_REVIEW,
            triggered_by_type="customer",
            triggered_by_user_id=current_user.get("user_id"),
            triggered_by_email=current_user.get("email"),
            reason="Client submitted requested information",
            metadata={
                "response_version": len(order.get("client_input_responses", [])) + 1,
                "fields_submitted": list(payload.fields.keys()),
            },
        )
        
        # Notify admin(s)
        db = database.get_db()
        admin = await db.portal_users.find_one(
            {"role": "admin", "status": "active"},
            {"email": 1, "name": 1, "user_id": 1}
        )
        
        if admin:
            # Send email notification
            frontend_url = os.getenv("FRONTEND_URL", "https://pleerity.com")
            order_link = f"{frontend_url}/admin/orders?order={order_id}"
            
            email_data = build_client_response_received_email(
                admin_name=admin.get("name", "Admin"),
                order_reference=order_id,
                service_name=order.get("service_name", "Service"),
                client_name=order.get("customer", {}).get("full_name", "Client"),
                client_email=order.get("customer", {}).get("email", ""),
                submitted_fields=payload.fields,
                files_uploaded=[],
                order_link=order_link,
            )
            
            try:
                await email_service.send_email(
                    recipient=admin["email"],
                    template_alias=EmailTemplateAlias.GENERIC,
                    template_model={"message": email_data["text"]},
                    subject=email_data["subject"],
                )
            except Exception as e:
                logger.error(f"Failed to send admin notification: {e}")
            
            # Create in-app notification
            await create_in_app_notification(
                recipient_id=admin["user_id"],
                title="Client Info Received",
                message=f"Client submitted info for order {order_id}",
                notification_type="order_update",
                link=f"/admin/orders?order={order_id}",
                metadata={"order_id": order_id},
            )
        
        return {
            "success": True,
            "message": "Thank you! Your information has been submitted. Processing will resume automatically.",
            "order_status": updated_order["status"],
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/upload-file")
async def upload_client_file_endpoint(
    order_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(client_route_guard),
):
    """
    Upload a file as part of client input.
    Files are stored versioned and associated with the order.
    """
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify ownership
    if order.get("customer", {}).get("email") != current_user.get("email"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Verify order is in CLIENT_INPUT_REQUIRED state
    if order["status"] != OrderStatus.CLIENT_INPUT_REQUIRED.value:
        raise HTTPException(
            status_code=400, 
            detail="Order is not awaiting client input"
        )
    
    # Validate file type
    allowed_types = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not allowed"
        )
    
    # Check file size (10MB max)
    max_size = 10 * 1024 * 1024
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB"
        )
    
    try:
        # Determine input version
        existing_responses = order.get("client_input_responses", [])
        input_version = len(existing_responses) + 1
        
        # Upload to storage
        import io
        file_meta = await upload_client_file(
            order_id=order_id,
            file_data=io.BytesIO(file_content),
            filename=file.filename,
            content_type=file.content_type,
            uploaded_by=current_user.get("email"),
            input_version=input_version,
        )
        
        # Store reference on order
        db = database.get_db()
        await db.orders.update_one(
            {"order_id": order_id},
            {
                "$push": {
                    "client_uploaded_files": {
                        "file_id": file_meta.file_id,
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size_bytes": file_meta.size_bytes,
                        "sha256_hash": file_meta.sha256_hash,
                        "uploaded_at": datetime.now(timezone.utc).isoformat(),
                        "uploaded_by": current_user.get("email"),
                        "input_version": input_version,
                    }
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
            }
        )
        
        return {
            "success": True,
            "file_id": file_meta.file_id,
            "filename": file.filename,
            "size_bytes": file_meta.size_bytes,
            "message": "File uploaded successfully",
        }
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")


# ============================================
# CLIENT ORDERS LIST
# ============================================

@router.get("/")
async def list_client_orders(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(client_route_guard),
):
    """
    List all orders for the current client.
    """
    db = database.get_db()
    
    query = {"customer.email": current_user.get("email")}
    if status:
        query["status"] = status
    
    cursor = db.orders.find(
        query,
        {
            "_id": 0,
            "internal_notes": 0,  # Exclude internal notes
            "regen_notes_current": 0,
            "regeneration_history": 0,
        }
    ).sort("created_at", -1).limit(limit)
    
    orders = await cursor.to_list(length=None)
    
    # Count orders requiring action
    action_required = sum(
        1 for o in orders 
        if o["status"] == OrderStatus.CLIENT_INPUT_REQUIRED.value
    )
    
    return {
        "orders": orders,
        "total": len(orders),
        "action_required": action_required,
    }
