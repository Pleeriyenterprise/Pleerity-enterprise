"""ClearForm Stripe Webhook Handler

Handles ClearForm-specific Stripe webhooks:
- Credit purchase completion
- Subscription lifecycle (created, renewed, cancelled)
- Payment failures

Uses same Stripe account but separate webhook handling.
"""

from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone, timedelta
import logging
import os
import stripe

from database import database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clearform/webhook", tags=["ClearForm Webhooks"])


@router.post("/stripe")
async def handle_clearform_stripe_webhook(request: Request):
    """Handle Stripe webhooks for ClearForm.
    
    Separate from Pleerity webhooks to maintain isolation.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    # Use same webhook secret for simplicity, but could be separate
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        logger.error("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Check if this is a ClearForm event
    metadata = event.data.object.get("metadata", {})
    if metadata.get("product") != "clearform":
        # Not a ClearForm event, ignore
        return {"status": "ignored", "reason": "not_clearform"}
    
    event_type = event.type
    
    logger.info(f"ClearForm webhook: {event_type}")
    
    try:
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(event.data.object)
        elif event_type == "invoice.paid":
            await handle_invoice_paid(event.data.object)
        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(event.data.object)
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(event.data.object)
        else:
            logger.info(f"Unhandled ClearForm event type: {event_type}")
        
        return {"status": "success", "event_type": event_type}
        
    except Exception as e:
        logger.error(f"ClearForm webhook handler error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def handle_checkout_completed(session):
    """Handle completed checkout session.
    
    Could be:
    - Credit purchase (mode=payment)
    - Subscription (mode=subscription)
    """
    metadata = session.get("metadata", {})
    session_type = metadata.get("type")
    user_id = metadata.get("clearform_user_id")
    
    if not user_id:
        logger.error("No user_id in checkout session metadata")
        return
    
    db = database.get_db()
    
    if session_type == "credit_purchase":
        # Process credit top-up
        credits = int(metadata.get("credits", 0))
        package_id = metadata.get("package_id")
        
        logger.info(f"Processing credit purchase: {credits} credits for user {user_id}")
        
        # Update top-up record
        await db.clearform_credit_topups.update_one(
            {"stripe_checkout_session_id": session["id"]},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                }
            }
        )
        
        # Add credits to user
        from clearform.services.credit_service import credit_service
        from clearform.models.credits import CreditTransactionType
        
        await credit_service.add_credits(
            user_id=user_id,
            amount=credits,
            transaction_type=CreditTransactionType.PURCHASE,
            description=f"Credit purchase: {credits} credits",
            reference_id=session["id"],
            reference_type="stripe_checkout",
        )
        
        logger.info(f"Added {credits} credits to user {user_id}")
        
    elif session_type == "subscription":
        # Process new subscription
        plan = metadata.get("plan")
        monthly_credits = int(metadata.get("monthly_credits", 0))
        
        logger.info(f"Processing subscription: {plan} for user {user_id}")
        
        # Get Stripe subscription ID
        stripe_sub_id = session.get("subscription")
        
        # Get subscription details from Stripe
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        
        # Create subscription record
        from clearform.models.subscriptions import ClearFormSubscription, ClearFormSubscriptionStatus
        
        subscription = ClearFormSubscription(
            user_id=user_id,
            plan=plan,
            status=ClearFormSubscriptionStatus.ACTIVE,
            monthly_credits=monthly_credits,
            stripe_subscription_id=stripe_sub_id,
            current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start, timezone.utc),
            current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end, timezone.utc),
        )
        
        await db.clearform_subscriptions.insert_one(subscription.model_dump())
        
        # Update user with subscription info
        await db.clearform_users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "subscription_id": subscription.subscription_id,
                    "subscription_plan": plan,
                    "next_credit_grant_at": subscription.current_period_end,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        # Grant initial subscription credits
        from clearform.services.credit_service import credit_service
        from clearform.models.credits import CreditTransactionType
        
        await credit_service.add_credits(
            user_id=user_id,
            amount=monthly_credits,
            transaction_type=CreditTransactionType.SUBSCRIPTION_GRANT,
            description=f"Subscription credit grant: {monthly_credits} credits",
            reference_id=subscription.subscription_id,
            reference_type="subscription",
        )
        
        logger.info(f"Created subscription {subscription.subscription_id} for user {user_id}")


async def handle_invoice_paid(invoice):
    """Handle paid invoice (subscription renewal)."""
    metadata = invoice.get("subscription_details", {}).get("metadata", {})
    if metadata.get("product") != "clearform":
        return
    
    user_id = metadata.get("clearform_user_id")
    monthly_credits = int(metadata.get("monthly_credits", 0))
    
    if not user_id or not monthly_credits:
        logger.warning("Missing user_id or monthly_credits in invoice")
        return
    
    # This could be a renewal - grant monthly credits
    subscription_id = invoice.get("subscription")
    
    db = database.get_db()
    
    # Find subscription
    subscription = await db.clearform_subscriptions.find_one({
        "stripe_subscription_id": subscription_id,
    }, {"_id": 0})
    
    if not subscription:
        logger.warning(f"Subscription not found for Stripe ID: {subscription_id}")
        return
    
    # Check if we've already granted credits for this period
    if subscription.get("credits_granted_this_period"):
        logger.info("Credits already granted for this period")
        return
    
    # Grant renewal credits
    from clearform.services.credit_service import credit_service
    from clearform.models.credits import CreditTransactionType
    
    await credit_service.add_credits(
        user_id=user_id,
        amount=monthly_credits,
        transaction_type=CreditTransactionType.SUBSCRIPTION_GRANT,
        description=f"Monthly subscription renewal: {monthly_credits} credits",
        reference_id=subscription["subscription_id"],
        reference_type="subscription_renewal",
    )
    
    # Get updated period from Stripe
    stripe.api_key = os.getenv("STRIPE_API_KEY")
    stripe_sub = stripe.Subscription.retrieve(subscription_id)
    
    # Update subscription period
    await db.clearform_subscriptions.update_one(
        {"subscription_id": subscription["subscription_id"]},
        {
            "$set": {
                "current_period_start": datetime.fromtimestamp(stripe_sub.current_period_start, timezone.utc),
                "current_period_end": datetime.fromtimestamp(stripe_sub.current_period_end, timezone.utc),
                "credits_granted_this_period": True,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    # Update user's next grant date
    await db.clearform_users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "next_credit_grant_at": datetime.fromtimestamp(stripe_sub.current_period_end, timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Renewed subscription {subscription['subscription_id']} for user {user_id}")


async def handle_payment_failed(invoice):
    """Handle failed payment."""
    metadata = invoice.get("subscription_details", {}).get("metadata", {})
    if metadata.get("product") != "clearform":
        return
    
    user_id = metadata.get("clearform_user_id")
    subscription_id = invoice.get("subscription")
    
    logger.warning(f"Payment failed for ClearForm user {user_id}")
    
    db = database.get_db()
    
    # Update subscription status
    from clearform.models.subscriptions import ClearFormSubscriptionStatus
    
    await db.clearform_subscriptions.update_one(
        {"stripe_subscription_id": subscription_id},
        {
            "$set": {
                "status": ClearFormSubscriptionStatus.PAST_DUE.value,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )


async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation/expiry."""
    metadata = subscription.get("metadata", {})
    if metadata.get("product") != "clearform":
        return
    
    user_id = metadata.get("clearform_user_id")
    
    logger.info(f"Subscription deleted for ClearForm user {user_id}")
    
    db = database.get_db()
    
    from clearform.models.subscriptions import ClearFormSubscriptionStatus
    
    # Update subscription
    await db.clearform_subscriptions.update_one(
        {"stripe_subscription_id": subscription["id"]},
        {
            "$set": {
                "status": ClearFormSubscriptionStatus.EXPIRED.value,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    # Clear user subscription info
    await db.clearform_users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "subscription_id": None,
                "subscription_plan": None,
                "next_credit_grant_at": None,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
