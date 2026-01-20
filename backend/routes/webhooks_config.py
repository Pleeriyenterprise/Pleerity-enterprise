"""Webhook Configuration Routes - Manage webhook endpoints for external integrations.

Endpoints:
- POST /api/webhooks - Create webhook
- GET /api/webhooks - List webhooks
- GET /api/webhooks/events - Get available event types
- GET /api/webhooks/stats - Get delivery statistics
- GET /api/webhooks/{id} - Get webhook details
- PATCH /api/webhooks/{id} - Update webhook
- DELETE /api/webhooks/{id} - Soft delete webhook
- POST /api/webhooks/{id}/test - Test webhook
- POST /api/webhooks/{id}/enable - Enable webhook
- POST /api/webhooks/{id}/disable - Disable webhook
- POST /api/webhooks/{id}/regenerate-secret - Regenerate signing secret
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from models import WebhookEventType, AuditAction
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


# Rate limit and retry policy info shown in UI
RATE_LIMIT_INFO = {
    "max_requests_per_minute": 100,
    "max_retries": 3,
    "retry_backoff": "exponential (1s, 2s, 4s)",
    "timeout_seconds": 10,
    "auto_disable_after_failures": 5
}


class CreateWebhookRequest(BaseModel):
    name: str
    url: str
    event_types: List[str]
    secret: Optional[str] = None  # If not provided, one will be generated


class UpdateWebhookRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    event_types: Optional[List[str]] = None


@router.get("/events")
async def get_available_events(request: Request):
    """Get list of available webhook event types with descriptions."""
    await client_route_guard(request)
    
    events = [
        {
            "type": WebhookEventType.COMPLIANCE_STATUS_CHANGED.value,
            "name": "Compliance Status Changed",
            "description": "Fired when a property's compliance status changes (e.g., GREEN → AMBER → RED)",
            "payload_fields": ["property_id", "property_address", "before.status", "after.status", "reason"]
        },
        {
            "type": WebhookEventType.REQUIREMENT_STATUS_CHANGED.value,
            "name": "Requirement Status Changed",
            "description": "Fired when a requirement status changes (e.g., PENDING → COMPLIANT or → OVERDUE)",
            "payload_fields": ["requirement_id", "requirement_type", "property_id", "before.status", "after.status"]
        },
        {
            "type": WebhookEventType.DOCUMENT_VERIFICATION_CHANGED.value,
            "name": "Document Verification Changed",
            "description": "Fired when a document verification status changes (PENDING → VERIFIED or REJECTED)",
            "payload_fields": ["document_id", "filename", "property_id", "before.status", "after.status"]
        },
        {
            "type": WebhookEventType.DIGEST_SENT.value,
            "name": "Digest Sent",
            "description": "Fired when a monthly or scheduled compliance digest is sent",
            "payload_fields": ["digest_type", "recipients_count", "properties_count", "requirements_summary"]
        },
        {
            "type": WebhookEventType.REMINDER_SENT.value,
            "name": "Reminder Sent",
            "description": "Fired when a daily compliance reminder is sent",
            "payload_fields": ["recipient", "expiring_requirements", "overdue_requirements"]
        }
    ]
    
    return {
        "events": events,
        "rate_limit": RATE_LIMIT_INFO,
        "signature_info": {
            "algorithm": "HMAC-SHA256",
            "header": "X-Webhook-Signature",
            "format": "sha256={hex_digest}"
        }
    }


@router.get("/stats")
async def get_webhook_stats(request: Request):
    """Get webhook delivery statistics for the client."""
    user = await client_route_guard(request)
    
    try:
        stats = await webhook_service.get_webhook_stats(user["client_id"])
        return stats
    except Exception as e:
        logger.error(f"Get webhook stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )


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
        
        # Check for duplicate webhook (same URL and events)
        existing = await db.webhooks.find_one({
            "client_id": user["client_id"],
            "url": data.url,
            "is_deleted": {"$ne": True}
        })
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A webhook with this URL already exists"
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
            "is_deleted": False,
            "last_triggered": None,
            "last_status": None,
            "last_response_body": None,
            "last_error": None,
            "failure_count": 0,
            "total_deliveries": 0,
            "successful_deliveries": 0,
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
        
        logger.info(f"Webhook created: {webhook['webhook_id']} by {user.get('email', 'unknown')}")
        
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
    """List all webhooks for the client (excluding soft-deleted)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        webhooks = await db.webhooks.find(
            {
                "client_id": user["client_id"],
                "is_deleted": {"$ne": True}
            },
            {"_id": 0, "secret": 0}  # Don't expose secrets in list
        ).sort("created_at", -1).to_list(100)
        
        # Mask any remaining sensitive data and format for display
        for webhook in webhooks:
            # Calculate success rate
            total = webhook.get("total_deliveries", 0)
            successful = webhook.get("successful_deliveries", 0)
            webhook["success_rate"] = round((successful / total * 100), 1) if total > 0 else None
        
        return {
            "webhooks": webhooks,
            "rate_limit": RATE_LIMIT_INFO
        }
    
    except Exception as e:
        logger.error(f"List webhooks error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list webhooks"
        )


@router.get("/{webhook_id}")
async def get_webhook(request: Request, webhook_id: str):
    """Get webhook details with masked secret."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        webhook = await db.webhooks.find_one(
            {
                "webhook_id": webhook_id, 
                "client_id": user["client_id"],
                "is_deleted": {"$ne": True}
            },
            {"_id": 0}
        )
        
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        # Mask the secret
        if webhook.get("secret"):
            secret = webhook["secret"]
            webhook["secret_masked"] = f"{secret[:8]}...{secret[-4:]}"
            del webhook["secret"]
        
        # Calculate success rate
        total = webhook.get("total_deliveries", 0)
        successful = webhook.get("successful_deliveries", 0)
        webhook["success_rate"] = round((successful / total * 100), 1) if total > 0 else None
        
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
            "client_id": user["client_id"],
            "is_deleted": {"$ne": True}
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
        
        if update:
            await db.webhooks.update_one(
                {"webhook_id": webhook_id},
                {"$set": update}
            )
            
            # Audit log
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                resource_type="webhook",
                resource_id=webhook_id,
                metadata={"action": "webhook_updated", "changes": update}
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
    """Soft delete a webhook."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify ownership
        webhook = await db.webhooks.find_one({
            "webhook_id": webhook_id,
            "client_id": user["client_id"],
            "is_deleted": {"$ne": True}
        })
        
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        # Soft delete
        await db.webhooks.update_one(
            {"webhook_id": webhook_id},
            {"$set": {
                "is_deleted": True,
                "is_active": False,
                "deleted_at": datetime.now(timezone.utc).isoformat()
            }}
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
        
        if not result.get("success") and result.get("error") == "Webhook not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        return {
            "message": "Test webhook sent",
            "success": result["success"],
            "status_code": result.get("status_code"),
            "triggered_at": result.get("triggered_at"),
            "error": result.get("error"),
            "response_preview": result.get("response_preview")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test webhook"
        )


@router.post("/{webhook_id}/enable")
async def enable_webhook(request: Request, webhook_id: str):
    """Enable a webhook."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        result = await db.webhooks.update_one(
            {
                "webhook_id": webhook_id,
                "client_id": user["client_id"],
                "is_deleted": {"$ne": True}
            },
            {"$set": {"is_active": True, "failure_count": 0}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        return {"message": "Webhook enabled", "is_active": True}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enable webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable webhook"
        )


@router.post("/{webhook_id}/disable")
async def disable_webhook(request: Request, webhook_id: str):
    """Disable a webhook."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        result = await db.webhooks.update_one(
            {
                "webhook_id": webhook_id,
                "client_id": user["client_id"],
                "is_deleted": {"$ne": True}
            },
            {"$set": {"is_active": False}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        return {"message": "Webhook disabled", "is_active": False}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disable webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable webhook"
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
            "client_id": user["client_id"],
            "is_deleted": {"$ne": True}
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
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="webhook",
            resource_id=webhook_id,
            metadata={"action": "secret_regenerated"}
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
