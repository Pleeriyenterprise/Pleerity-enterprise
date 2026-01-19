from fastapi import APIRouter, HTTPException, Request, Header, status
from database import database
from services.stripe_service import stripe_service
from services.provisioning import provisioning_service
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhooks"])

@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """Handle Stripe webhooks."""
    try:
        body = await request.body()
        webhook_data = json.loads(body)
        
        # Process webhook
        await stripe_service.handle_webhook(webhook_data, stripe_signature)
        
        # If payment completed, trigger provisioning
        event_type = webhook_data.get("type")
        if event_type == "checkout.session.completed":
            data = webhook_data.get("data", {}).get("object", {})
            metadata = data.get("metadata", {})
            client_id = metadata.get("client_id")
            
            if client_id:
                # Trigger provisioning in background
                success, message = await provisioning_service.provision_client_portal(client_id)
                if success:
                    logger.info(f"Provisioning triggered for client {client_id}")
                else:
                    logger.error(f"Provisioning failed for client {client_id}: {message}")
        
        return {"status": "received"}
    
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

@router.post("/postmark/delivery")
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
