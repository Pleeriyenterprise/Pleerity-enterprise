"""ClearForm Subscription Routes

Endpoints:
- GET /api/clearform/subscriptions/plans - Get available plans
- GET /api/clearform/subscriptions/current - Get current subscription
- POST /api/clearform/subscriptions/subscribe - Create subscription checkout
- POST /api/clearform/subscriptions/cancel - Cancel subscription
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel
import logging
import os

from clearform.models.subscriptions import (
    ClearFormPlan,
    ClearFormSubscription,
    ClearFormSubscriptionStatus,
    ClearFormPlanDetails,
    CLEARFORM_PLANS,
)
from clearform.routes.auth import get_current_clearform_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clearform/subscriptions", tags=["ClearForm Subscriptions"])


class SubscribeRequest(BaseModel):
    plan: str  # Plan enum value


class SubscribeResponse(BaseModel):
    checkout_url: str
    session_id: str


class CurrentSubscriptionResponse(BaseModel):
    has_subscription: bool
    subscription: Optional[dict] = None
    plan_details: Optional[dict] = None


@router.get("/plans", response_model=List[ClearFormPlanDetails])
async def get_plans():
    """Get available subscription plans.
    
    No auth required - for display on pricing page.
    """
    return list(CLEARFORM_PLANS.values())


@router.get("/current", response_model=CurrentSubscriptionResponse)
async def get_current_subscription(user = Depends(get_current_clearform_user)):
    """Get user's current subscription."""
    try:
        from database import database
        db = database.get_db()
        
        subscription = await db.clearform_subscriptions.find_one({
            "user_id": user.user_id,
            "status": {"$in": [
                ClearFormSubscriptionStatus.ACTIVE.value,
                ClearFormSubscriptionStatus.PAST_DUE.value,
            ]}
        }, {"_id": 0})
        
        if not subscription:
            return CurrentSubscriptionResponse(
                has_subscription=False,
            )
        
        plan = ClearFormPlan(subscription["plan"])
        plan_details = CLEARFORM_PLANS[plan].model_dump()
        
        return CurrentSubscriptionResponse(
            has_subscription=True,
            subscription=subscription,
            plan_details=plan_details,
        )
        
    except Exception as e:
        logger.error(f"Failed to get subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscription")


@router.post("/subscribe", response_model=SubscribeResponse)
async def create_subscription_checkout(
    request: SubscribeRequest,
    user = Depends(get_current_clearform_user),
):
    """Create Stripe checkout session for subscription.
    
    Returns checkout URL to redirect user.
    """
    try:
        import stripe
        
        # Validate plan
        try:
            plan = ClearFormPlan(request.plan)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid plan: {request.plan}")
        
        if plan == ClearFormPlan.FREE:
            raise HTTPException(status_code=400, detail="Free plan does not require subscription")
        
        plan_details = CLEARFORM_PLANS[plan]
        
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        # Get or create Stripe customer
        from database import database
        db = database.get_db()
        
        user_data = await db.clearform_users.find_one({"user_id": user.user_id}, {"_id": 0})
        
        if user_data.get("stripe_customer_id"):
            customer_id = user_data["stripe_customer_id"]
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={
                    "clearform_user_id": user.user_id,
                    "product": "clearform",
                }
            )
            customer_id = customer.id
            
            await db.clearform_users.update_one(
                {"user_id": user.user_id},
                {"$set": {"stripe_customer_id": customer_id}}
            )
        
        # Create subscription checkout session
        # Note: In production, create actual Stripe products/prices first
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": f"ClearForm {plan_details.name}",
                        "description": f"{plan_details.monthly_credits} credits/month",
                    },
                    "unit_amount": plan_details.monthly_price_gbp,
                    "recurring": {
                        "interval": "month",
                    },
                },
                "quantity": 1,
            }],
            success_url=f"{frontend_url}/clearform/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/clearform/pricing",
            metadata={
                "clearform_user_id": user.user_id,
                "product": "clearform",
                "type": "subscription",
                "plan": plan.value,
                "monthly_credits": str(plan_details.monthly_credits),
            }
        )
        
        return SubscribeResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subscription checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout")


@router.post("/cancel")
async def cancel_subscription(user = Depends(get_current_clearform_user)):
    """Cancel current subscription.
    
    Cancels at end of billing period (access continues until then).
    """
    try:
        import stripe
        
        from database import database
        db = database.get_db()
        
        subscription = await db.clearform_subscriptions.find_one({
            "user_id": user.user_id,
            "status": ClearFormSubscriptionStatus.ACTIVE.value,
        }, {"_id": 0})
        
        if not subscription:
            raise HTTPException(status_code=404, detail="No active subscription found")
        
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        
        # Cancel at period end (user keeps access until billing period ends)
        if subscription.get("stripe_subscription_id"):
            stripe.Subscription.modify(
                subscription["stripe_subscription_id"],
                cancel_at_period_end=True,
            )
        
        # Update local record
        from datetime import datetime, timezone
        await db.clearform_subscriptions.update_one(
            {"subscription_id": subscription["subscription_id"]},
            {
                "$set": {
                    "status": ClearFormSubscriptionStatus.CANCELLED.value,
                    "cancelled_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        return {
            "message": "Subscription will be cancelled at end of billing period",
            "current_period_end": subscription.get("current_period_end"),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


@router.get("/portal")
async def get_billing_portal(user = Depends(get_current_clearform_user)):
    """Get Stripe billing portal URL.
    
    Users can manage payment methods, view invoices, etc.
    """
    try:
        import stripe
        
        from database import database
        db = database.get_db()
        
        user_data = await db.clearform_users.find_one({"user_id": user.user_id}, {"_id": 0})
        
        if not user_data.get("stripe_customer_id"):
            raise HTTPException(status_code=400, detail="No billing account found")
        
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        portal_session = stripe.billing_portal.Session.create(
            customer=user_data["stripe_customer_id"],
            return_url=f"{frontend_url}/clearform/account",
        )
        
        return {"portal_url": portal_session.url}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create billing portal: {e}")
        raise HTTPException(status_code=500, detail="Failed to create billing portal")
