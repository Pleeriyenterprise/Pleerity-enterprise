from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse
from database import database
from models import PaymentTransaction, BillingPlan, SubscriptionStatus, AuditAction
from utils.audit import create_audit_log
import os
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Billing plan pricing (in GBP)
# Monthly subscription: £9.99 / client (not per property)
# One-time setup fee: £49.99 / client
BILLING_PLANS = {
    BillingPlan.PLAN_1: {"monthly": 9.99, "setup": 49.99, "name": "Starter (1 Property)"},
    BillingPlan.PLAN_2_5: {"monthly": 9.99, "setup": 49.99, "name": "Growth (Up to 5 Properties)"},
    BillingPlan.PLAN_6_15: {"monthly": 9.99, "setup": 49.99, "name": "Portfolio (Up to 15 Properties)"}
}

class StripeService:
    def __init__(self):
        self.api_key = os.getenv("STRIPE_API_KEY", "sk_test_emergent")
    
    async def create_checkout_session(
        self,
        client_id: str,
        billing_plan: BillingPlan,
        origin_url: str
    ) -> CheckoutSessionResponse:
        """Create Stripe checkout session.
        
        Pricing: £9.99/month subscription + £49.99 one-time setup fee
        """
        db = database.get_db()
        
        # Get amount from server-defined plans
        plan_info = BILLING_PLANS.get(billing_plan)
        if not plan_info:
            raise ValueError(f"Invalid billing plan: {billing_plan}")
        
        # Total first payment = monthly + setup fee
        monthly = plan_info["monthly"]
        setup = plan_info["setup"]
        total_amount = monthly + setup
        
        # Initialize Stripe checkout
        webhook_url = f"{origin_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(
            api_key=self.api_key,
            webhook_url=webhook_url
        )
        
        # Create checkout session
        success_url = f"{origin_url}/checkout/success?session_id={{{{CHECKOUT_SESSION_ID}}}}"
        cancel_url = f"{origin_url}/checkout/cancel"
        
        checkout_request = CheckoutSessionRequest(
            amount=total_amount,
            currency="gbp",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "client_id": client_id,
                "billing_plan": billing_plan.value,
                "service": "VAULT_PRO",
                "monthly_price": str(monthly),
                "setup_fee": str(setup)
            }
        )
        
        session = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Create payment transaction record
        transaction = PaymentTransaction(
            client_id=client_id,
            stripe_session_id=session.session_id,
            amount=total_amount,
            currency="gbp",
            billing_plan=billing_plan,
            payment_status="pending",
            metadata={
                **checkout_request.metadata,
                "breakdown": {
                    "monthly": monthly,
                    "setup_fee": setup,
                    "total": total_amount
                }
            }
        )
        
        doc = transaction.model_dump()
        for key in ["created_at", "updated_at"]:
            if doc.get(key):
                doc[key] = doc[key].isoformat()
        
        await db.payment_transactions.insert_one(doc)
        
        logger.info(f"Checkout session created for client {client_id}: {session.session_id} (£{total_amount})")
        
        return session
    
    async def handle_webhook(self, webhook_data: Dict, signature: str):
        """Handle Stripe webhook events."""
        db = database.get_db()
        
        event_type = webhook_data.get("type")
        data = webhook_data.get("data", {}).get("object", {})
        
        logger.info(f"Received Stripe webhook: {event_type}")
        
        if event_type == "checkout.session.completed":
            session_id = data.get("id")
            metadata = data.get("metadata", {})
            client_id = metadata.get("client_id")
            
            if not client_id:
                logger.error(f"No client_id in webhook metadata: {session_id}")
                return
            
            # Update payment transaction
            await db.payment_transactions.update_one(
                {"stripe_session_id": session_id},
                {
                    "$set": {
                        "payment_status": "completed",
                        "stripe_payment_intent_id": data.get("payment_intent")
                    }
                }
            )
            
            # Update client subscription status
            billing_plan = metadata.get("billing_plan")
            await db.clients.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "subscription_status": SubscriptionStatus.ACTIVE.value,
                        "billing_plan": billing_plan,
                        "stripe_customer_id": data.get("customer"),
                        "stripe_subscription_id": data.get("subscription")
                    }
                }
            )
            
            # Audit log
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                client_id=client_id,
                metadata={
                    "event": "payment_completed",
                    "session_id": session_id,
                    "billing_plan": billing_plan
                }
            )
            
            logger.info(f"Payment completed for client {client_id}")
        
        elif event_type in ["customer.subscription.updated", "customer.subscription.deleted"]:
            subscription = data
            customer_id = subscription.get("customer")
            
            # Find client by customer_id
            client = await db.clients.find_one(
                {"stripe_customer_id": customer_id},
                {"_id": 0}
            )
            
            if not client:
                logger.warning(f"Client not found for customer {customer_id}")
                return
            
            # Update subscription status
            status = subscription.get("status")
            new_status = SubscriptionStatus.ACTIVE if status == "active" else SubscriptionStatus.CANCELLED
            
            await db.clients.update_one(
                {"client_id": client["client_id"]},
                {"$set": {"subscription_status": new_status.value}}
            )
            
            # Audit log
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                client_id=client["client_id"],
                metadata={
                    "event": event_type,
                    "subscription_status": new_status.value
                }
            )
            
            logger.info(f"Subscription updated for client {client['client_id']}: {new_status.value}")

stripe_service = StripeService()
