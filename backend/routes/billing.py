"""Billing Routes - Subscription and payment management.

Endpoints:
- POST /api/billing/checkout - Create checkout session for new/upgrade subscription
- GET /api/billing/status - Get current subscription status
- POST /api/billing/portal - Create Stripe billing portal session
- POST /api/billing/cancel - Cancel subscription
"""
from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel
from typing import Optional
from database import database
from services.stripe_service import stripe_service
from services.plan_registry import plan_registry, PlanCode
from middleware import client_route_guard
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    """Request to create checkout session."""
    plan_code: str  # PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO


class CancelRequest(BaseModel):
    """Request to cancel subscription."""
    cancel_immediately: bool = False


@router.post("/checkout")
async def create_checkout(request: Request, body: CheckoutRequest):
    """
    Create Stripe checkout session for subscription.
    
    For new customers: Creates full checkout with subscription + onboarding fee.
    For existing customers: Creates billing portal session for upgrade.
    """
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No client_id associated with user"
        )
    
    # Validate plan code
    try:
        plan = PlanCode(body.plan_code)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan code: {body.plan_code}"
        )
    
    # Get origin URL from request
    origin = request.headers.get("origin", "")
    if not origin:
        # Fallback to host
        host = request.headers.get("host", "localhost")
        scheme = "https" if "preview.emergentagent.com" in host else "http"
        origin = f"{scheme}://{host}"
    
    try:
        result = await stripe_service.create_upgrade_session(
            client_id=client_id,
            new_plan_code=body.plan_code,
            origin_url=origin
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Checkout creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.get("/status")
async def get_billing_status(request: Request):
    """Get current subscription and billing status."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No client_id associated with user"
        )
    
    try:
        billing_status = await stripe_service.get_subscription_status(client_id)
        
        # Add plan details if has subscription
        if billing_status.get("current_plan_code"):
            plan_code = billing_status["current_plan_code"]
            plan_def = plan_registry.get_plan_by_code_string(plan_code)
            if plan_def:
                billing_status["plan_name"] = plan_def.get("name")
                billing_status["plan_display_name"] = plan_def.get("display_name")
                billing_status["max_properties"] = plan_def.get("max_properties")
        
        return billing_status
        
    except Exception as e:
        logger.error(f"Failed to get billing status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve billing status"
        )


@router.post("/portal")
async def create_billing_portal(request: Request):
    """Create Stripe billing portal session for subscription management."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No client_id associated with user"
        )
    
    db = database.get_db()
    
    # Get billing record
    billing = await db.client_billing.find_one(
        {"client_id": client_id},
        {"_id": 0}
    )
    
    if not billing or not billing.get("stripe_customer_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found"
        )
    
    # Get origin URL
    origin = request.headers.get("origin", "")
    if not origin:
        host = request.headers.get("host", "localhost")
        scheme = "https" if "preview.emergentagent.com" in host else "http"
        origin = f"{scheme}://{host}"
    
    try:
        import stripe
        import os
        stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_emergent")
        
        portal_session = stripe.billing_portal.Session.create(
            customer=billing.get("stripe_customer_id"),
            return_url=f"{origin}/app/billing",
        )
        
        return {
            "portal_url": portal_session.url,
        }
        
    except Exception as e:
        logger.error(f"Failed to create billing portal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session"
        )


@router.post("/cancel")
async def cancel_subscription(request: Request, body: CancelRequest):
    """
    Cancel subscription.
    
    By default, cancels at end of billing period.
    Set cancel_immediately=true for immediate cancellation.
    """
    user = request.state.user
    client_id = user.get("client_id")
    
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No client_id associated with user"
        )
    
    try:
        result = await stripe_service.cancel_subscription(
            client_id=client_id,
            cancel_immediately=body.cancel_immediately
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.get("/plans")
async def get_available_plans():
    """Get all available subscription plans."""
    plans = plan_registry.get_all_plans()
    
    # Add additional display info
    for plan in plans:
        plan["features_count"] = sum(
            1 for v in plan_registry.get_features_by_string(plan["code"]).values() if v
        )
    
    return {
        "plans": plans,
    }
