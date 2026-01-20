"""Webhook Routes - Configure and manage webhooks for external integrations.

Endpoints:
- POST /api/webhooks - Create webhook
- GET /api/webhooks - List webhooks
- GET /api/webhooks/{id} - Get webhook details
- PATCH /api/webhooks/{id} - Update webhook
- DELETE /api/webhooks/{id} - Delete webhook
- POST /api/webhooks/{id}/test - Test webhook
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from models import Webhook, WebhookEventType, AuditAction
from utils.audit import create_audit_log
from services.webhook_service import webhook_service
from typing import Optional, List
from pydantic import BaseModel
import uuid
import secrets
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class CreateWebhookRequest(BaseModel):
    name: str
    url: str
    event_types: List[str]
    secret: Optional[str] = None  # If not provided, one will be generated


class UpdateWebhookRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    event_types: Optional[List[str]] = None
    is_active: Optional[bool] = None


@router.post("")
async def create_webhook(request: Request, data: CreateWebhookRequest):
    """Create a new webhook configuration."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Validate event types
        valid_events = [e.value for e in WebhookEventType]
        for event in data.event_types:
            if event not in valid_events:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid event type: {event}. Valid types: {valid_events}"
                )
        
        # Validate URL
        if not data.url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL must start with http:// or https://"
            )
        
        # Generate secret if not provided
        secret = data.secret if data.secret else secrets.token_hex(32)
        
        webhook = {
            "webhook_id": str(uuid.uuid4()),
            "client_id": user["client_id"],
            "name": data.name,
            "url": data.url,
            "secret": secret,
            "event_types": data.event_types,
            "is_active": True,
            "last_triggered": None,
            "last_status": None,
            "failure_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user["portal_user_id"]
        }
        
        await db.webhooks.insert_one(webhook)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="webhook",
            resource_id=webhook["webhook_id"],
            metadata={
                "action": "webhook_created",
                "name": data.name,
                "url": data.url,
                "event_types": data.event_types
            }
        )
        
        logger.info(f"Webhook created: {webhook['webhook_id']} by {user['email']}")
        
        return {
            "message": "Webhook created successfully",
            "webhook_id": webhook["webhook_id"],
            "secret": secret  # Return secret only on creation
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create webhook"
        )


@router.get("")
async def list_webhooks(request: Request):
    """List all webhooks for the client."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        webhooks = await db.webhooks.find(
            {"client_id": user["client_id"]},
            {"_id": 0, "secret": 0}  # Don't expose secrets in list
        ).to_list(100)
        
        return {
            "webhooks": webhooks,
            "available_events": [
                {
                    "type": e.value,
                    "description": _get_event_description(e)
                }
                for e in WebhookEventType
            ]
        }
    
    except Exception as e:
        logger.error(f"List webhooks error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list webhooks"
        )


@router.get("/{webhook_id}")
async def get_webhook(request: Request, webhook_id: str):
    """Get webhook details."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        webhook = await db.webhooks.find_one(
            {"webhook_id": webhook_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        # Mask the secret
        if webhook.get("secret"):
            webhook["secret"] = webhook["secret"][:8] + "..." + webhook["secret"][-4:]
        
        return webhook
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get webhook"
        )


@router.patch("/{webhook_id}")
async def update_webhook(request: Request, webhook_id: str, data: UpdateWebhookRequest):
    """Update webhook configuration."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify ownership
        webhook = await db.webhooks.find_one({
            "webhook_id": webhook_id,
            "client_id": user["client_id"]
        })
        
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        # Build update
        update = {}
        if data.name is not None:
            update["name"] = data.name
        if data.url is not None:
            if not data.url.startswith(("http://", "https://")):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="URL must start with http:// or https://"
                )
            update["url"] = data.url
        if data.event_types is not None:
            valid_events = [e.value for e in WebhookEventType]
            for event in data.event_types:
                if event not in valid_events:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid event type: {event}"
                    )
            update["event_types"] = data.event_types
        if data.is_active is not None:
            update["is_active"] = data.is_active
            # Reset failure count when re-enabling
            if data.is_active:
                update["failure_count"] = 0
        
        if update:
            await db.webhooks.update_one(
                {"webhook_id": webhook_id},
                {"$set": update}
            )
        
        return {"message": "Webhook updated"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update webhook"
        )


@router.delete("/{webhook_id}")
async def delete_webhook(request: Request, webhook_id: str):
    """Delete a webhook."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        result = await db.webhooks.delete_one({
            "webhook_id": webhook_id,
            "client_id": user["client_id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="webhook",
            resource_id=webhook_id,
            metadata={"action": "webhook_deleted"}
        )
        
        return {"message": "Webhook deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete webhook"
        )


@router.post("/{webhook_id}/test")
async def test_webhook(request: Request, webhook_id: str):
    """Send a test request to the webhook URL."""
    user = await client_route_guard(request)
    
    try:
        result = await webhook_service.test_webhook(
            webhook_id=webhook_id,
            client_id=user["client_id"]
        )
        
        if not result.get("success") and result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )
        
        return {
            "message": "Test webhook sent",
            "success": result["success"],
            "status_code": result.get("status_code"),
            "triggered_at": result.get("triggered_at")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test webhook"
        )


@router.post("/{webhook_id}/regenerate-secret")
async def regenerate_webhook_secret(request: Request, webhook_id: str):
    """Regenerate the webhook signing secret."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify ownership
        webhook = await db.webhooks.find_one({
            "webhook_id": webhook_id,
            "client_id": user["client_id"]
        })
        
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        new_secret = secrets.token_hex(32)
        
        await db.webhooks.update_one(
            {"webhook_id": webhook_id},
            {"$set": {"secret": new_secret}}
        )
        
        return {
            "message": "Secret regenerated",
            "secret": new_secret
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regenerate secret error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate secret"
        )


def _get_event_description(event: WebhookEventType) -> str:
    """Get human-readable description for event type."""
    descriptions = {
        WebhookEventType.COMPLIANCE_STATUS_CHANGED: "Fired when a property's compliance status changes (e.g., GREEN → AMBER)",
        WebhookEventType.REQUIREMENT_EXPIRING: "Fired when a requirement is expiring soon (within 30 days)",
        WebhookEventType.REQUIREMENT_OVERDUE: "Fired when a requirement becomes overdue",
        WebhookEventType.DOCUMENT_UPLOADED: "Fired when a new document is uploaded",
        WebhookEventType.PROPERTY_CREATED: "Fired when a new property is added"
    }
    return descriptions.get(event, "Unknown event type")
