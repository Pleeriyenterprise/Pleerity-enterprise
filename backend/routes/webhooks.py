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


@router.post("/api/webhook/postmark/delivery")
async def postmark_delivery_webhook(request: Request):
    """Handle Postmark delivery webhooks."""
    try:
        body = await request.json()
        
        message_id = body.get("MessageID")
        if not message_id:
            return {"status": "ignored"}
        
        db = database.get_db()
        
        # Update message log
        await db.message_logs.update_one(
            {"postmark_message_id": message_id},
            {
                "$set": {
                    "status": "delivered",
                    "delivered_at": body.get("DeliveredAt")
                }
            }
        )
        
        logger.info(f"Email delivered: {message_id}")
        return {"status": "received"}
    
    except Exception as e:
        logger.error(f"Postmark delivery webhook error: {e}")
        return {"status": "error"}


@router.post("/postmark/bounce")
async def postmark_bounce_webhook(request: Request):
    """Handle Postmark bounce webhooks."""
    try:
        body = await request.json()
        
        message_id = body.get("MessageID")
        if not message_id:
            return {"status": "ignored"}
        
        db = database.get_db()
        
        # Update message log
        await db.message_logs.update_one(
            {"postmark_message_id": message_id},
            {
                "$set": {
                    "status": "bounced",
                    "bounced_at": body.get("BouncedAt"),
                    "error_message": body.get("Description")
                }
            }
        )
        
        logger.warning(f"Email bounced: {message_id}")
        return {"status": "received"}
    
    except Exception as e:
        logger.error(f"Postmark bounce webhook error: {e}")
        return {"status": "error"}
