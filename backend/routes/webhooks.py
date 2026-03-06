"""Webhook Routes - Stripe and other external webhooks.

Stripe webhook endpoint with:
- Signature verification
- Idempotency (via StripeEvent collection)
- Full audit logging

POST /api/webhook/stripe - Main Stripe webhook endpoint
POST /api/webhooks/stripe - Alias for Stripe webhook (for backward compatibility)
POST /api/webhooks/postmark - Postmark delivery/bounce/spam; validated by X-Postmark-Token when POSTMARK_WEBHOOK_TOKEN is set.
"""
from fastapi import APIRouter, HTTPException, Request, Header, status
from database import database
from services.stripe_webhook_service import stripe_webhook_service
import logging
import json
import os

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def _stripe_admin_recipients():
    """Admin recipients for Stripe webhook failure: ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL."""
    raw = (os.getenv("ADMIN_ALERT_EMAILS") or "").strip()
    if raw:
        return [e.strip() for e in raw.split(",") if e.strip()]
    email = (os.getenv("OPS_ALERT_EMAIL") or "").strip()
    return [email] if email else []


async def _send_stripe_webhook_failure_admin_alert(error_message: str):
    """Send STRIPE_WEBHOOK_FAILURE_ADMIN to admin list. Call with create_task to avoid blocking webhook response."""
    recipients = _stripe_admin_recipients()
    if not recipients:
        return
    try:
        from services.notification_orchestrator import notification_orchestrator
        subject = "[Admin] Stripe webhook processing failure"
        message = f"Stripe webhook handler raised an exception.\n\nError: {error_message[:1000]}"
        for recipient in recipients:
            idempotency_key = f"STRIPE_WEBHOOK_FAILURE_ADMIN_{hash(error_message[:200] + recipient) % 10**10}"
            await notification_orchestrator.send(
                template_key="STRIPE_WEBHOOK_FAILURE_ADMIN",
                client_id=None,
                context={"recipient": recipient, "subject": subject, "message": message},
                idempotency_key=idempotency_key,
                event_type="stripe_webhook_failure_admin",
            )
    except Exception as send_err:
        logger.warning("Failed to send Stripe webhook failure admin alert: %s", send_err)


def _postmark_webhook_token_ok(header_token: str = None) -> bool:
    """Return True if Postmark webhook request is authorized. When POSTMARK_WEBHOOK_TOKEN is set, header must match."""
    configured = os.getenv("POSTMARK_WEBHOOK_TOKEN") or os.getenv("POSTMARK_WEBHOOK_SECRET")
    if not configured or not configured.strip():
        return True
    return bool(header_token and header_token.strip() == configured.strip())


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
        if message == "Invalid signature":
            logger.error("Stripe webhook rejected: invalid signature (STRIPE_WEBHOOK_SECRET vs key mode mismatch?)")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")
        # Other errors (e.g. invalid payload) - return 200 to avoid Stripe retries; logged internally
        logger.error("Webhook processing failed: %s", message)
        return {"status": "error", "message": message}
    
    except Exception as e:
        logger.exception(f"Stripe webhook error: {e}")
        # Notify admins (STRIPE_WEBHOOK_FAILURE_ADMIN) fire-and-forget
        import asyncio
        asyncio.create_task(_send_stripe_webhook_failure_admin_alert(str(e)))
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
async def postmark_webhook(
    request: Request,
    x_postmark_token: str = Header(None, alias="X-Postmark-Token"),
):
    """Single Postmark webhook: Delivered, Bounce, SpamComplaint. Updates message_logs and writes audits.
    When POSTMARK_WEBHOOK_TOKEN (or POSTMARK_WEBHOOK_SECRET) is set, X-Postmark-Token header must match; else 401 and no DB update."""
    if not _postmark_webhook_token_ok(x_postmark_token):
        logger.warning("Postmark webhook rejected: missing or invalid X-Postmark-Token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
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
            # Update delivery record and order (DELIVERING -> COMPLETED)
            try:
                from repositories.services_repositories import delivery_repository
                from services.order_service import get_order, transition_order_state
                from services.order_workflow import OrderStatus
                delivery = await delivery_repository.find_by_postmark_message_id(message_id)
                if delivery:
                    delivered_at = body.get("DeliveredAt") or now
                    if isinstance(delivered_at, str):
                        from dateutil import parser as date_parser
                        try:
                            delivered_at = date_parser.parse(delivered_at)
                        except Exception:
                            delivered_at = now
                    await delivery_repository.update_delivery_status(
                        delivery["delivery_id"], "DELIVERED", delivered_at=delivered_at
                    )
                    order_id = delivery.get("order_id")
                    if order_id:
                        order = await get_order(order_id)
                        if order and order.get("status") == OrderStatus.DELIVERING.value:
                            await transition_order_state(
                                order_id=order_id,
                                new_status=OrderStatus.COMPLETED,
                                triggered_by_type="system",
                                reason="Delivery confirmed via Postmark webhook",
                                metadata={"postmark_message_id": message_id, "delivered_at": (delivered_at.isoformat() if hasattr(delivered_at, "isoformat") else str(delivered_at))},
                            )
                            await db.orders.update_one(
                                {"order_id": order_id},
                                {"$set": {"delivered_at": delivered_at, "completed_at": delivered_at}},
                            )
                            try:
                                from services.order_notification_service import order_notification_service, OrderNotificationEvent
                                order = await get_order(order_id)
                                if order:
                                    await order_notification_service.notify_order_event(
                                        event_type=OrderNotificationEvent.ORDER_DELIVERED,
                                        order_id=order_id,
                                        order=order,
                                        message=f"Documents delivered to {order.get('customer', {}).get('email', '')}",
                                    )
                            except Exception as notif_err:
                                logger.warning(f"Order delivery notification failed: {notif_err}")
                            logger.info(f"Order {order_id} marked COMPLETED from webhook delivery")
            except Exception as e:
                logger.warning(f"Postmark webhook: delivery record/order update failed: {e}")
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
            # Update delivery record and order (DELIVERING -> DELIVERY_FAILED)
            try:
                from repositories.services_repositories import delivery_repository
                from services.order_service import get_order, transition_order_state
                from services.order_workflow import OrderStatus
                delivery = await delivery_repository.find_by_postmark_message_id(message_id)
                if delivery:
                    bounced_at = body.get("BouncedAt") or body.get("OccurredAt") or now
                    if isinstance(bounced_at, str):
                        from dateutil import parser as date_parser
                        try:
                            bounced_at = date_parser.parse(bounced_at)
                        except Exception:
                            bounced_at = now
                    err_msg = body.get("Description") or body.get("DescriptionPlain") or "Bounced"
                    await delivery_repository.update_delivery_status(
                        delivery["delivery_id"], "BOUNCED",
                        bounced_at=bounced_at,
                        error_message=err_msg,
                    )
                    order_id = delivery.get("order_id")
                    if order_id:
                        order = await get_order(order_id)
                        if order and order.get("status") == OrderStatus.DELIVERING.value:
                            await transition_order_state(
                                order_id=order_id,
                                new_status=OrderStatus.DELIVERY_FAILED,
                                triggered_by_type="system",
                                reason=f"Email bounced: {err_msg[:200]}",
                                metadata={"postmark_message_id": message_id, "bounced_at": (bounced_at.isoformat() if hasattr(bounced_at, "isoformat") else str(bounced_at))},
                            )
                            logger.info(f"Order {order_id} marked DELIVERY_FAILED from webhook bounce")
            except Exception as e:
                logger.warning(f"Postmark webhook: delivery record/order update (bounce) failed: {e}")
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
            # Update delivery record and order (DELIVERING -> DELIVERY_FAILED)
            try:
                from repositories.services_repositories import delivery_repository
                from services.order_service import get_order, transition_order_state
                from services.order_workflow import OrderStatus
                delivery = await delivery_repository.find_by_postmark_message_id(message_id)
                if delivery:
                    await delivery_repository.update_delivery_status(
                        delivery["delivery_id"], "BOUNCED",
                        error_message="Spam complaint",
                    )
                    order_id = delivery.get("order_id")
                    if order_id:
                        order = await get_order(order_id)
                        if order and order.get("status") == OrderStatus.DELIVERING.value:
                            await transition_order_state(
                                order_id=order_id,
                                new_status=OrderStatus.DELIVERY_FAILED,
                                triggered_by_type="system",
                                reason="Email spam complaint",
                                metadata={"postmark_message_id": message_id},
                            )
            except Exception as e:
                logger.warning(f"Postmark webhook: delivery record/order update (spam) failed: {e}")
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
