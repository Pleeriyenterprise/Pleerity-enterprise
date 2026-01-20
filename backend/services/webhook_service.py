"""Webhook Service - Fire webhooks on compliance events.

Supports events:
- compliance.status_changed: Property compliance_color changes
- requirement.status_changed: Requirement status changes
- document.verification_changed: PENDING→VERIFIED/REJECTED
- digest.sent: Monthly/scheduled digest sent
- reminder.sent: Daily reminder sent

Webhooks are sent as POST requests with JSON payload and HMAC-SHA256 signature.
Implements exponential backoff retries (3 attempts) and comprehensive logging.
"""
import aiohttp
import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from database import database
from models import WebhookEventType, AuditAction

logger = logging.getLogger(__name__)

# Rate limiting and retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10
MAX_WEBHOOKS_PER_MINUTE = 100  # Per client rate limit


class WebhookService:
    """Manages webhook delivery for compliance events."""
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    
    async def trigger_webhooks(
        self,
        client_id: str,
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> int:
        """
        Trigger all active webhooks for a specific event type.
        
        Args:
            client_id: Client who owns the webhooks
            event_type: Type of event that occurred (e.g., "compliance.status_changed")
            payload: Event data to send
            idempotency_key: Optional key to prevent duplicate deliveries
            
        Returns:
            Number of webhooks successfully triggered
        """
        db = database.get_db()
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())
        
        try:
            # Find active, non-deleted webhooks for this client and event type
            webhooks = await db.webhooks.find({
                "client_id": client_id,
                "is_active": True,
                "is_deleted": {"$ne": True},
                "event_types": event_type
            }, {"_id": 0}).to_list(100)
            
            if not webhooks:
                logger.debug(f"No webhooks found for client {client_id} event {event_type}")
                return 0
            
            success_count = 0
            
            for webhook in webhooks:
                try:
                    success = await self._send_webhook_with_retries(
                        webhook, 
                        event_type, 
                        payload,
                        idempotency_key
                    )
                    if success:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Webhook {webhook['webhook_id']} error: {e}")
            
            return success_count
            
        except Exception as e:
            logger.error(f"Trigger webhooks error: {e}")
            return 0
    
    async def _send_webhook_with_retries(
        self,
        webhook: Dict[str, Any],
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: str
    ) -> bool:
        """Send a webhook with exponential backoff retries."""
        
        for attempt in range(MAX_RETRIES):
            success = await self._send_webhook(
                webhook, 
                event_type, 
                payload, 
                idempotency_key,
                attempt + 1
            )
            
            if success:
                return True
            
            # Calculate backoff time
            if attempt < MAX_RETRIES - 1:
                backoff = min(INITIAL_BACKOFF_SECONDS * (2 ** attempt), MAX_BACKOFF_SECONDS)
                logger.info(f"Webhook {webhook['webhook_id']} retry in {backoff}s (attempt {attempt + 1})")
                await asyncio.sleep(backoff)
        
        return False
    
    async def _send_webhook(
        self,
        webhook: Dict[str, Any],
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: str,
        attempt: int = 1
    ) -> bool:
        """Send a single webhook request."""
        db = database.get_db()
        webhook_id = webhook["webhook_id"]
        client_id = webhook["client_id"]
        
        # Generate event ID for tracking
        event_id = f"{event_type}_{idempotency_key}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Build the full payload - sanitized, never include secrets/tokens/payment data
        full_payload = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "client_id": client_id,
            "data": self._sanitize_payload(payload)
        }
        
        # Add property_id if present in payload
        if "property_id" in payload:
            full_payload["property_id"] = payload["property_id"]
        
        payload_json = json.dumps(full_payload, default=str, sort_keys=True)
        
        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Delivery": idempotency_key,
            "X-Webhook-Attempt": str(attempt),
            "User-Agent": "ComplianceVaultPro-Webhook/1.0"
        }
        
        # Add HMAC-SHA256 signature if secret is configured
        if webhook.get("secret"):
            signature = hmac.new(
                webhook["secret"].encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        response_code = 0
        response_body = None
        error_message = None
        success = False
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    webhook["url"],
                    data=payload_json,
                    headers=headers
                ) as response:
                    response_code = response.status
                    
                    # Read response body (truncated for storage)
                    try:
                        response_body = await response.text()
                        if len(response_body) > 500:
                            response_body = response_body[:500] + "...[truncated]"
                    except:
                        response_body = "[Could not read response]"
                    
                    success = 200 <= response_code < 300
                    
                    if success:
                        logger.info(f"Webhook {webhook_id} delivered: {response_code}")
                    else:
                        error_message = f"HTTP {response_code}: {response_body[:100]}"
                        logger.warning(f"Webhook {webhook_id} failed: {response_code}")
                        
        except aiohttp.ClientError as e:
            error_message = f"Connection error: {str(e)}"
            logger.error(f"Webhook {webhook_id} connection error: {e}")
        except asyncio.TimeoutError:
            error_message = f"Request timed out after {REQUEST_TIMEOUT_SECONDS}s"
            logger.error(f"Webhook {webhook_id} timeout")
        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            logger.error(f"Webhook {webhook_id} unexpected error: {e}")
        
        # Update webhook status and statistics
        update_data = {
            "last_triggered": timestamp,
            "last_status": response_code,
            "last_response_body": response_body,
            "last_error": error_message if not success else None,
            "$inc": {"total_deliveries": 1}
        }
        
        if success:
            update_data["failure_count"] = 0
            update_data["$inc"]["successful_deliveries"] = 1
        else:
            # Only increment failure count on final attempt
            if attempt >= MAX_RETRIES:
                new_failure_count = webhook.get("failure_count", 0) + 1
                update_data["failure_count"] = new_failure_count
                
                # Disable webhook after 5 consecutive failures
                if new_failure_count >= 5:
                    update_data["is_active"] = False
                    logger.warning(f"Webhook {webhook_id} disabled due to repeated failures")
        
        # Split $inc and $set operations
        set_update = {k: v for k, v in update_data.items() if k != "$inc"}
        inc_update = update_data.get("$inc", {})
        
        try:
            update_ops = {"$set": set_update}
            if inc_update:
                update_ops["$inc"] = inc_update
            
            await db.webhooks.update_one(
                {"webhook_id": webhook_id},
                update_ops
            )
        except Exception as e:
            logger.error(f"Failed to update webhook status: {e}")
        
        # Log to message_logs for audit trail (on final attempt only)
        if attempt >= MAX_RETRIES or success:
            await self._log_webhook_delivery(
                webhook_id=webhook_id,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                url=webhook["url"],
                response_code=response_code,
                success=success,
                error_message=error_message,
                attempts=attempt
            )
        
        return success
    
    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from payload before sending."""
        # Fields that should never be included in webhooks
        sensitive_fields = {
            "secret", "token", "password", "api_key", "apikey", "auth",
            "credential", "stripe", "payment", "card", "bank", "ssn",
            "social_security", "private_key", "secret_key"
        }
        
        def sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            result = {}
            for key, value in d.items():
                # Skip sensitive keys
                if any(s in key.lower() for s in sensitive_fields):
                    continue
                # Recursively sanitize nested dicts
                if isinstance(value, dict):
                    result[key] = sanitize_dict(value)
                elif isinstance(value, list):
                    result[key] = [
                        sanitize_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    result[key] = value
            return result
        
        return sanitize_dict(payload)
    
    async def _log_webhook_delivery(
        self,
        webhook_id: str,
        client_id: str,
        event_type: str,
        event_id: str,
        url: str,
        response_code: int,
        success: bool,
        error_message: Optional[str],
        attempts: int
    ):
        """Log webhook delivery attempt to audit/message logs."""
        db = database.get_db()
        
        try:
            # Create audit log entry
            audit_log = {
                "audit_id": str(uuid.uuid4()),
                "action": "WEBHOOK_DELIVERED" if success else "WEBHOOK_FAILED",
                "client_id": client_id,
                "resource_type": "webhook",
                "resource_id": webhook_id,
                "metadata": {
                    "event_type": event_type,
                    "event_id": event_id,
                    "target_url": url,
                    "response_code": response_code,
                    "success": success,
                    "error": error_message,
                    "attempts": attempts,
                    "provider": "WEBHOOK"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await db.audit_logs.insert_one(audit_log)
            
            # Also log to message_logs for consistency with email logging
            message_log = {
                "message_id": str(uuid.uuid4()),
                "client_id": client_id,
                "recipient": url,
                "template_alias": f"webhook_{event_type}",
                "subject": f"Webhook: {event_type}",
                "status": "sent" if success else "failed",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "error_message": error_message,
                "metadata": {
                    "provider": "WEBHOOK",
                    "webhook_id": webhook_id,
                    "response_code": response_code,
                    "attempts": attempts
                },
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.message_logs.insert_one(message_log)
            
        except Exception as e:
            logger.error(f"Failed to log webhook delivery: {e}")
    
    async def test_webhook(self, webhook_id: str, client_id: str) -> Dict[str, Any]:
        """
        Send a test webhook to verify configuration.
        
        Returns test result including response status.
        """
        db = database.get_db()
        
        webhook = await db.webhooks.find_one({
            "webhook_id": webhook_id,
            "client_id": client_id,
            "is_deleted": {"$ne": True}
        }, {"_id": 0})
        
        if not webhook:
            return {"success": False, "error": "Webhook not found"}
        
        test_payload = {
            "test": True,
            "message": "This is a test webhook from Compliance Vault Pro",
            "webhook_name": webhook.get("name"),
            "configured_events": webhook.get("event_types", []),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Use single attempt for test (no retries)
        success = await self._send_webhook(
            webhook,
            "test.webhook",
            test_payload,
            idempotency_key=f"test_{webhook_id}_{datetime.now(timezone.utc).timestamp()}",
            attempt=MAX_RETRIES  # Mark as final attempt to ensure logging
        )
        
        # Get updated webhook status
        updated = await db.webhooks.find_one(
            {"webhook_id": webhook_id},
            {"_id": 0, "last_status": 1, "last_triggered": 1, "last_error": 1, "last_response_body": 1}
        )
        
        return {
            "success": success,
            "status_code": updated.get("last_status") if updated else None,
            "triggered_at": updated.get("last_triggered") if updated else None,
            "error": updated.get("last_error") if updated else None,
            "response_preview": updated.get("last_response_body", "")[:200] if updated else None
        }
    
    async def get_webhook_stats(self, client_id: str) -> Dict[str, Any]:
        """Get webhook delivery statistics for a client."""
        db = database.get_db()
        
        webhooks = await db.webhooks.find(
            {"client_id": client_id, "is_deleted": {"$ne": True}},
            {"_id": 0}
        ).to_list(100)
        
        total_webhooks = len(webhooks)
        active_webhooks = sum(1 for w in webhooks if w.get("is_active"))
        total_deliveries = sum(w.get("total_deliveries", 0) for w in webhooks)
        successful_deliveries = sum(w.get("successful_deliveries", 0) for w in webhooks)
        
        return {
            "total_webhooks": total_webhooks,
            "active_webhooks": active_webhooks,
            "total_deliveries": total_deliveries,
            "successful_deliveries": successful_deliveries,
            "success_rate": (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        }


# Singleton instance
webhook_service = WebhookService()


# ============================================================================
# Helper functions to trigger webhooks from other services
# ============================================================================

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
        event_type=WebhookEventType.COMPLIANCE_STATUS_CHANGED.value,
        payload={
            "property_id": property_id,
            "property_address": property_address,
            "before": {"status": old_status},
            "after": {"status": new_status},
            "reason": reason
        },
        idempotency_key=f"compliance_{property_id}_{old_status}_{new_status}_{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    )


async def fire_requirement_status_changed(
    client_id: str,
    requirement_id: str,
    requirement_type: str,
    property_id: str,
    property_address: str,
    old_status: str,
    new_status: str
):
    """Fire webhook when requirement status changes."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.REQUIREMENT_STATUS_CHANGED.value,
        payload={
            "requirement_id": requirement_id,
            "requirement_type": requirement_type,
            "property_id": property_id,
            "property_address": property_address,
            "before": {"status": old_status},
            "after": {"status": new_status}
        },
        idempotency_key=f"requirement_{requirement_id}_{old_status}_{new_status}"
    )


async def fire_document_verification_changed(
    client_id: str,
    document_id: str,
    filename: str,
    property_id: str,
    old_status: str,
    new_status: str,
    verified_by: Optional[str] = None
):
    """Fire webhook when document verification status changes."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.DOCUMENT_VERIFICATION_CHANGED.value,
        payload={
            "document_id": document_id,
            "filename": filename,
            "property_id": property_id,
            "before": {"status": old_status},
            "after": {"status": new_status},
            "verified_by": verified_by
        },
        idempotency_key=f"document_{document_id}_{old_status}_{new_status}"
    )


async def fire_digest_sent(
    client_id: str,
    digest_type: str,
    recipients: List[str],
    properties_count: int,
    requirements_summary: Dict[str, int]
):
    """Fire webhook when a digest email is sent."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.DIGEST_SENT.value,
        payload={
            "digest_type": digest_type,
            "recipients_count": len(recipients),
            "properties_count": properties_count,
            "requirements_summary": requirements_summary
        },
        idempotency_key=f"digest_{client_id}_{digest_type}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    )


async def fire_reminder_sent(
    client_id: str,
    recipient: str,
    expiring_count: int,
    overdue_count: int
):
    """Fire webhook when a reminder is sent."""
    await webhook_service.trigger_webhooks(
        client_id=client_id,
        event_type=WebhookEventType.REMINDER_SENT.value,
        payload={
            "recipient": recipient,
            "expiring_requirements": expiring_count,
            "overdue_requirements": overdue_count
        },
        idempotency_key=f"reminder_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    )
