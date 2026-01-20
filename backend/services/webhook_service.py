"""Webhook Service - Fire webhooks on compliance events.

Supports events:
- compliance_status_changed: Property status changed (GREEN→AMBER, etc.)
- requirement_expiring: Requirement expiring within threshold
- requirement_overdue: Requirement became overdue
- document_uploaded: New document uploaded
- property_created: New property added

Webhooks are sent as POST requests with JSON payload and optional HMAC signature.
"""
import aiohttp
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from database import database
from models import WebhookEventType

logger = logging.getLogger(__name__)


class WebhookService:
    """Manages webhook delivery for compliance events."""
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
    
    async def trigger_webhooks(
        self,
        client_id: str,
        event_type: WebhookEventType,
        payload: Dict[str, Any]
    ) -> int:
        """
        Trigger all active webhooks for a specific event type.
        
        Args:
            client_id: Client who owns the webhooks
            event_type: Type of event that occurred
            payload: Event data to send
            
        Returns:
            Number of webhooks successfully triggered
        """
        db = database.get_db()
        
        try:
            # Find active webhooks for this client and event type
            webhooks = await db.webhooks.find({
                "client_id": client_id,
                "is_active": True,
                "event_types": event_type.value
            }, {"_id": 0}).to_list(100)
            
            if not webhooks:
                return 0
            
            success_count = 0
            
            for webhook in webhooks:
                try:
                    success = await self._send_webhook(webhook, event_type, payload)
                    if success:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Webhook {webhook['webhook_id']} error: {e}")
            
            return success_count
            
        except Exception as e:
            logger.error(f"Trigger webhooks error: {e}")
            return 0
    
    async def _send_webhook(
        self,
        webhook: Dict[str, Any],
        event_type: WebhookEventType,
        payload: Dict[str, Any]
    ) -> bool:
        """Send a single webhook request."""
        db = database.get_db()
        webhook_id = webhook["webhook_id"]
        
        # Build the full payload
        full_payload = {
            "event": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "webhook_id": webhook_id,
            "data": payload
        }
        
        payload_json = json.dumps(full_payload, default=str)
        
        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type.value,
            "X-Webhook-Timestamp": full_payload["timestamp"]
        }
        
        # Add HMAC signature if secret is configured
        if webhook.get("secret"):
            signature = hmac.new(
                webhook["secret"].encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    webhook["url"],
                    data=payload_json,
                    headers=headers
                ) as response:
                    status_code = response.status
                    
                    # Update webhook status
                    update_data = {
                        "last_triggered": datetime.now(timezone.utc).isoformat(),
                        "last_status": status_code
                    }
                    
                    if status_code >= 200 and status_code < 300:
                        # Success - reset failure count
                        update_data["failure_count"] = 0
                        logger.info(f"Webhook {webhook_id} delivered: {status_code}")
                    else:
                        # Failure - increment failure count
                        update_data["failure_count"] = webhook.get("failure_count", 0) + 1
                        logger.warning(f"Webhook {webhook_id} failed: {status_code}")
                        
                        # Disable webhook after 5 consecutive failures
                        if update_data["failure_count"] >= 5:
                            update_data["is_active"] = False
                            logger.warning(f"Webhook {webhook_id} disabled due to repeated failures")
                    
                    await db.webhooks.update_one(
                        {"webhook_id": webhook_id},
                        {"$set": update_data}
                    )
                    
                    return status_code >= 200 and status_code < 300
                    
        except aiohttp.ClientError as e:
            logger.error(f"Webhook {webhook_id} connection error: {e}")
            
            # Update failure count
            await db.webhooks.update_one(
                {"webhook_id": webhook_id},
                {
                    "$set": {
                        "last_triggered": datetime.now(timezone.utc).isoformat(),
                        "last_status": 0
                    },
                    "$inc": {"failure_count": 1}
                }
            )
            return False
        except Exception as e:
            logger.error(f"Webhook {webhook_id} unexpected error: {e}")
            return False
    
    async def test_webhook(self, webhook_id: str, client_id: str) -> Dict[str, Any]:
        """
        Send a test webhook to verify configuration.
        
        Returns test result including response status.
        """
        db = database.get_db()
        
        webhook = await db.webhooks.find_one({
            "webhook_id": webhook_id,
            "client_id": client_id
        }, {"_id": 0})
        
        if not webhook:
            return {"success": False, "error": "Webhook not found"}
        
        test_payload = {
            "test": True,
            "message": "This is a test webhook from Compliance Vault Pro",
            "webhook_name": webhook.get("name"),
            "configured_events": webhook.get("event_types", [])
        }
        
        success = await self._send_webhook(
            webhook,
            WebhookEventType.COMPLIANCE_STATUS_CHANGED,
            test_payload
        )
        
        # Get updated webhook status
        updated = await db.webhooks.find_one(
            {"webhook_id": webhook_id},
            {"_id": 0, "last_status": 1, "last_triggered": 1}
        )
        
        return {
            "success": success,
            "status_code": updated.get("last_status") if updated else None,
            "triggered_at": updated.get("last_triggered") if updated else None
        }


# Singleton instance
webhook_service = WebhookService()


# Helper functions to trigger webhooks from other services
async def fire_compliance_status_changed(
    client_id: str,
    property_id: str,
    property_address: str,
    old_status: str,
    new_status: str,
    reason: str
):
    """Fire webhook when property compliance status changes."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.COMPLIANCE_STATUS_CHANGED,
        payload={
            "property_id": property_id,
            "property_address": property_address,
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason
        }
    )


async def fire_requirement_expiring(
    client_id: str,
    requirement_id: str,
    requirement_type: str,
    property_address: str,
    due_date: str,
    days_until_due: int
):
    """Fire webhook when requirement is expiring soon."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.REQUIREMENT_EXPIRING,
        payload={
            "requirement_id": requirement_id,
            "requirement_type": requirement_type,
            "property_address": property_address,
            "due_date": due_date,
            "days_until_due": days_until_due
        }
    )


async def fire_document_uploaded(
    client_id: str,
    document_id: str,
    filename: str,
    property_id: str,
    requirement_id: Optional[str]
):
    """Fire webhook when document is uploaded."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.DOCUMENT_UPLOADED,
        payload={
            "document_id": document_id,
            "filename": filename,
            "property_id": property_id,
            "requirement_id": requirement_id
        }
    )


async def fire_property_created(
    client_id: str,
    property_id: str,
    address: str,
    property_type: str,
    requirements_count: int
):
    """Fire webhook when property is created."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.PROPERTY_CREATED,
        payload={
            "property_id": property_id,
            "address": address,
            "property_type": property_type,
            "requirements_created": requirements_count
        }
    )
