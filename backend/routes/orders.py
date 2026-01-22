"""
Orders API Routes - Public order creation and checkout
NO CVP COLLECTIONS TOUCHED - Works only with orders collection.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict
from datetime import datetime, timezone
from database import database
from services.order_service import create_order, get_order, transition_order_state
from services.order_workflow import OrderStatus
import logging
import os
import stripe

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orders", tags=["orders"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


class CreateOrderRequest(BaseModel):
    order_type: str
    service_code: str
    service_name: str
    service_category: str
    customer_email: EmailStr
    customer_name: str
    customer_phone: Optional[str] = None
    customer_company: Optional[str] = None
    parameters: Optional[Dict] = None
    base_price: int  # In pence
    vat_amount: int = 0
    sla_hours: Optional[int] = None


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str


@router.post("/create")
async def create_new_order(request: CreateOrderRequest):
    """
    Create a new order (CREATED status).
    Returns order_id for subsequent checkout.
    """
    try:
        order = await create_order(
            order_type=request.order_type,
            service_code=request.service_code,
            service_name=request.service_name,
            service_category=request.service_category,
            customer_email=request.customer_email,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            customer_company=request.customer_company,
            parameters=request.parameters,
            base_price=request.base_price,
            vat_amount=request.vat_amount,
            sla_hours=request.sla_hours,
        )
        
        return {
            "success": True,
            "order_id": order["order_id"],
            "status": order["status"],
            "total_amount": order["pricing"]["total_amount"],
        }
        
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create order")


@router.post("/{order_id}/checkout")
async def create_order_checkout(order_id: str, request: CheckoutRequest):
    """
    Create Stripe checkout session for an order.
    Idempotent: If session already exists, returns existing session.
    """
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order["status"] != OrderStatus.CREATED.value:
        raise HTTPException(
            status_code=400, 
            detail=f"Order cannot be checked out in {order['status']} status"
        )
    
    # Check for existing session (idempotency)
    existing_session_id = order.get("pricing", {}).get("stripe_checkout_session_id")
    if existing_session_id:
        try:
            existing_session = stripe.checkout.Session.retrieve(existing_session_id)
            if existing_session.status == "open":
                return {
                    "checkout_url": existing_session.url,
                    "session_id": existing_session_id,
                }
        except stripe.error.InvalidRequestError:
            pass  # Session expired, create new one
    
    try:
        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            client_reference_id=order_id,
            customer_email=order["customer"]["email"],
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": order["service_name"],
                        "description": f"Order {order_id}",
                    },
                    "unit_amount": order["pricing"]["total_amount"],
                },
                "quantity": 1,
            }],
            success_url=request.success_url + f"?order_id={order_id}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=request.cancel_url + f"?order_id={order_id}",
            metadata={
                "order_id": order_id,
                "service_code": order["service_code"],
            },
        )
        
        # Store session ID on order
        db = database.get_db()
        await db.orders.update_one(
            {"order_id": order_id},
            {"$set": {
                "pricing.stripe_checkout_session_id": session.id,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.get("/{order_id}/status")
async def get_order_status(order_id: str, token: Optional[str] = None):
    """
    Get order status (limited public view).
    Token-protected for customer access.
    """
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Return limited info for public view
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "service_name": order["service_name"],
        "created_at": order["created_at"].isoformat() if order.get("created_at") else None,
        "completed_at": order["completed_at"].isoformat() if order.get("completed_at") else None,
    }


@router.post("/webhook/payment")
async def handle_order_payment_webhook(request: Request):
    """
    Handle Stripe webhook for order payments.
    Verifies signature and processes checkout.session.completed events.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    webhook_secret = os.getenv("STRIPE_ORDERS_WEBHOOK_SECRET")
    
    if not webhook_secret:
        logger.error("STRIPE_ORDERS_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle checkout.session.completed
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        
        if not order_id:
            order_id = session.get("client_reference_id")
        
        if order_id:
            try:
                order = await get_order(order_id)
                if order and order["status"] == OrderStatus.CREATED.value:
                    # Update payment info
                    db = database.get_db()
                    await db.orders.update_one(
                        {"order_id": order_id},
                        {"$set": {
                            "pricing.stripe_payment_intent_id": session.get("payment_intent"),
                            "updated_at": datetime.now(timezone.utc),
                        }}
                    )
                    
                    # Transition to PAID
                    await transition_order_state(
                        order_id=order_id,
                        new_status=OrderStatus.PAID,
                        triggered_by_type="system",
                        reason="Payment confirmed via Stripe webhook",
                        metadata={"session_id": session["id"]},
                    )
                    
                    # Auto-transition to QUEUED
                    await transition_order_state(
                        order_id=order_id,
                        new_status=OrderStatus.QUEUED,
                        triggered_by_type="system",
                        reason="Automatically queued after payment",
                    )
                    
                    logger.info(f"Order {order_id} paid and queued")
                    
            except Exception as e:
                logger.error(f"Error processing order payment: {e}")
    
    return {"received": True}
