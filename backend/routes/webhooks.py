"""Webhook Routes - Stripe and other external webhooks.

Stripe webhook endpoint with:
- Signature verification
- Idempotency (via StripeEvent collection)
- Full audit logging

POST /api/webhook/stripe - Main Stripe webhook endpoint
POST /api/webhooks/stripe - Alias for Stripe webhook (for backward compatibility)
"""
from fastapi import APIRouter, HTTPException, Request, Header, status
from database import database
from services.stripe_webhook_service import stripe_webhook_service
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


async def _handle_stripe_webhook(request: Request, stripe_signature: str = None):
    """
    Core Stripe webhook handler.
    
    Security:
    - Verifies Stripe signature when STRIPE_WEBHOOK_SECRET is set
    - Implements idempotency via StripeEvent collection
    - All events are audit logged
    
    Handled Events:
    - checkout.session.completed (primary provisioning trigger)
    - customer.subscription.created
    - customer.subscription.updated  
    - customer.subscription.deleted
    - invoice.paid
    - invoice.payment_failed
    """
    try:
        payload = await request.body()
        
        success, message, details = await stripe_webhook_service.process_webhook(
            payload=payload,
            signature=stripe_signature or ""
        )
        
        if success:
            return {"status": "received", "message": message, "details": details}
        else:
            # Still return 200 to prevent Stripe retries
            # Errors are logged internally
            logger.error(f"Webhook processing failed: {message}")
            return {"status": "error", "message": message}
    
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        # Return 200 to prevent Stripe retries - we've logged the error
        return {"status": "error", "message": str(e)}


# Primary webhook endpoint
@router.post("/api/webhook/stripe")
async def stripe_webhook(
    request: Request, 
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """Handle Stripe webhooks at /api/webhook/stripe"""
    return await _handle_stripe_webhook(request, stripe_signature)


# Alias endpoint for backward compatibility (Stripe may be configured with this URL)
@router.post("/api/webhooks/stripe")
async def stripe_webhook_alias(
    request: Request, 
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """Handle Stripe webhooks at /api/webhooks/stripe (alias)"""
    return await _handle_stripe_webhook(request, stripe_signature)


@router.post("/api/webhooks/postmark")
async def postmark_webhook(request: Request):
    """Single Postmark webhook: Delivered, Bounce, SpamComplaint. Updates message_logs and writes audits."""
    from datetime import datetime, timezone
    from models import AuditAction
    from utils.audit import create_audit_log
    try:
        body = await request.json()
        message_id = body.get("MessageID") or body.get("MessageId")
        record_type = (body.get("RecordType") or body.get("MessageStatus") or "").strip()
        if not message_id:
            return {"status": "ignored"}
        db = database.get_db()
        now = datetime.now(timezone.utc)
        log = await db.message_logs.find_one(
            {"$or": [{"postmark_message_id": message_id}, {"provider_message_id": message_id}]},
            {"_id": 0, "message_id": 1, "client_id": 1},
        )
        if record_type in ("Delivery", "Delivered", "delivered"):
            update = {"status": "DELIVERED", "delivered_at": body.get("DeliveredAt") or now}
            await db.message_logs.update_many(
                {"$or": [{"postmark_message_id": message_id}, {"provider_message_id": message_id}]},
                {"$set": update},
            )
            if log:
                await create_audit_log(
                    action=AuditAction.EMAIL_DELIVERED,
                    client_id=log.get("client_id"),
                    metadata={"message_id": log.get("message_id"), "provider_message_id": message_id},
                )
            logger.info(f"Email delivered: {message_id}")
            return {"status": "received"}
        if record_type in ("Bounce", "HardBounce", "SoftBounce", "bounce"):
            update = {
                "status": "BOUNCED",
                "bounced_at": body.get("BouncedAt") or body.get("OccurredAt") or now,
                "error_message": body.get("Description") or body.get("DescriptionPlain") or "Bounced",
            }
            await db.message_logs.update_many(
                {"$or": [{"postmark_message_id": message_id}, {"provider_message_id": message_id}]},
                {"$set": update},
            )
            if log:
                await create_audit_log(
                    action=AuditAction.EMAIL_BOUNCED,
                    client_id=log.get("client_id"),
                    metadata={"message_id": log.get("message_id"), "provider_message_id": message_id},
                )
            logger.warning(f"Email bounced: {message_id}")
            return {"status": "received"}
        if record_type in ("SpamComplaint", "Spam", "spam_complaint"):
            update = {"status": "BOUNCED", "error_message": "Spam complaint"}
            await db.message_logs.update_many(
                {"$or": [{"postmark_message_id": message_id}, {"provider_message_id": message_id}]},
                {"$set": update},
            )
            if log:
                await create_audit_log(
                    action=AuditAction.EMAIL_SPAM_COMPLAINT,
                    client_id=log.get("client_id"),
                    metadata={"message_id": log.get("message_id"), "provider_message_id": message_id},
                )
            logger.warning(f"Email spam complaint: {message_id}")
            return {"status": "received"}
        return {"status": "ignored", "RecordType": record_type}
    except Exception as e:
        logger.error(f"Postmark webhook error: {e}")
        return {"status": "error"}


@router.post("/api/webhook/postmark/delivery")
async def postmark_delivery_webhook(request: Request):
    """Legacy: Handle Postmark delivery webhooks. Prefer POST /api/webhooks/postmark."""
    try:
        body = await request.json()
        message_id = body.get("MessageID")
        if not message_id:
            return {"status": "ignored"}
        db = database.get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        await db.message_logs.update_many(
            {"$or": [{"postmark_message_id": message_id}, {"provider_message_id": message_id}]},
            {"$set": {"status": "DELIVERED", "delivered_at": body.get("DeliveredAt") or now}},
        )
        logger.info(f"Email delivered: {message_id}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Postmark delivery webhook error: {e}")
        return {"status": "error"}


@router.post("/api/webhook/postmark/bounce")
async def postmark_bounce_webhook(request: Request):
    """Legacy: Handle Postmark bounce webhooks. Prefer POST /api/webhooks/postmark."""
    try:
        body = await request.json()
        message_id = body.get("MessageID")
        if not message_id:
            return {"status": "ignored"}
        db = database.get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        await db.message_logs.update_many(
            {"$or": [{"postmark_message_id": message_id}, {"provider_message_id": message_id}]},
            {"$set": {"status": "BOUNCED", "bounced_at": body.get("BouncedAt") or now, "error_message": body.get("Description") or "Bounced"}},
        )
        logger.warning(f"Email bounced: {message_id}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Postmark bounce webhook error: {e}")
        return {"status": "error"}
