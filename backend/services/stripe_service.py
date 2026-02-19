"""Stripe Service - Checkout session creation and billing management.

This service handles:
- Creating checkout sessions for new subscriptions
- Managing subscription upgrades/downgrades
- Billing portal access

Key Principles:
- Uses plan_registry as single source of truth for pricing
- All price_ids come from plan_registry
- Metadata includes client_id for webhook tracing
"""
import stripe
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from database import database
from services.plan_registry import (
    plan_registry, PlanCode, EntitlementStatus,
    get_stripe_price_mappings, _get_stripe_mode, StripeModeMismatchError,
)
from utils.audit import create_audit_log
from models import AuditAction

logger = logging.getLogger(__name__)

# Initialize Stripe (no placeholder default; missing key fails at checkout with clear error)
stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY") or "").strip()


class StripeService:
    """Stripe billing operations service."""
    
    async def create_checkout_session(
        self,
        client_id: str,
        plan_code: str,
        origin_url: str,
        customer_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Stripe checkout session for new subscription.
        
        Includes:
        - Subscription line item (recurring)
        - Onboarding fee line item (one-time)
        
        Args:
            client_id: Internal client ID (MANDATORY for webhook)
            plan_code: Plan code (PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO)
            origin_url: Base URL for success/cancel redirects
            customer_email: Optional customer email for prefill
        
        Returns:
            Dict with checkout_url and session_id
        """
        if not (stripe.api_key or "").strip():
            raise ValueError("STRIPE_SECRET_KEY or STRIPE_API_KEY is not set. Configure env and restart.")

        db = database.get_db()

        # Stripe mode safety: determine mode from key, fetch prices for that mode only
        mode = _get_stripe_mode()
        try:
            config = get_stripe_price_mappings(mode)
        except StripeModeMismatchError as e:
            raise  # Re-raise for route to return 400 STRIPE_MODE_MISMATCH

        # Resolve plan code
        try:
            plan = PlanCode(plan_code)
        except ValueError:
            plan = plan_registry._resolve_plan_code(plan_code)

        # Get plan definition and prices for current mode
        plan_def = plan_registry.get_plan(plan)
        prices = config["mappings"].get(plan.value, {})
        subscription_price_id = prices.get("subscription_price_id")
        onboarding_price_id = prices.get("onboarding_price_id")

        if not subscription_price_id:
            raise StripeModeMismatchError(
                f"No {mode} subscription price configured for plan {plan_code}. Set STRIPE_{mode.upper()}_PRICE_{plan.value}_MONTHLY."
            )
        
        # Validate origin_url for success/cancel redirects (must be http(s) base URL)
        base = (origin_url or "").strip().rstrip("/")
        if not base.startswith("http://") and not base.startswith("https://"):
            raise ValueError(
                "Invalid redirect base URL: origin must be http or https. "
                "Set Origin header or FRONTEND_ORIGIN env."
            )
        
        # Build line items
        line_items = [
            {
                "price": subscription_price_id,
                "quantity": 1,
            },
        ]
        
        # Add onboarding (setup) fee only if not already paid (idempotent: no double charge)
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "onboarding_fee_paid": 1}
        )
        already_paid = billing and billing.get("onboarding_fee_paid") is True
        if onboarding_price_id and not already_paid:
            line_items.append({
                "price": onboarding_price_id,
                "quantity": 1,
            })
        
        # Success and cancel URLs (base already stripped trailing slash)
        success_url = f"{base}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base}/checkout/cancel"
        
        # Create checkout session
        try:
            session_params = {
                "mode": "subscription",
                "line_items": line_items,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "client_id": client_id,  # MANDATORY for webhook
                    "plan_code": plan.value,
                    "service": "COMPLIANCE_VAULT_PRO",
                },
                "subscription_data": {
                    "metadata": {
                        "client_id": client_id,
                        "plan_code": plan.value,
                    },
                },
                "expand": ["line_items"],  # Expand for webhook processing
            }
            
            if customer_email:
                session_params["customer_email"] = customer_email
            
            session = stripe.checkout.Session.create(**session_params)
            
            # Record checkout attempt
            checkout_record = {
                "client_id": client_id,
                "session_id": session.id,
                "plan_code": plan.value,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "checkout_url": session.url,
                "amount_total": session.amount_total,
                "currency": session.currency,
            }
            
            await db.checkout_sessions.insert_one(checkout_record)
            
            logger.info(f"Checkout session created for client {client_id}: {session.id}")
            
            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "plan_code": plan.value,
                "plan_name": plan_def["name"],
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout error for client {client_id}: {e}")
            raise ValueError(f"Failed to create checkout session: {str(e)}")
    
    async def create_upgrade_session(
        self,
        client_id: str,
        new_plan_code: str,
        origin_url: str
    ) -> Dict[str, Any]:
        """
        Create checkout session for plan upgrade.
        
        For existing customers, uses Stripe Billing Portal or creates
        a new checkout session that will update the subscription.
        """
        db = database.get_db()
        
        # Get current billing info
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not billing or not billing.get("stripe_customer_id"):
            # No existing subscription - treat as new checkout
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "contact_email": 1}
            )
            return await self.create_checkout_session(
                client_id=client_id,
                plan_code=new_plan_code,
                origin_url=origin_url,
                customer_email=client.get("contact_email") if client else None
            )
        
        # Existing customer - create portal session for upgrade
        stripe_customer_id = billing.get("stripe_customer_id")
        
        try:
            # Create billing portal session
            portal_session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=f"{origin_url}/app/billing",
            )
            
            logger.info(f"Billing portal session created for client {client_id}")
            
            return {
                "portal_url": portal_session.url,
                "type": "billing_portal",
                "current_plan": billing.get("current_plan_code"),
                "target_plan": new_plan_code,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe portal error for client {client_id}: {e}")
            raise ValueError(f"Failed to create billing portal session: {str(e)}")
    
    async def get_subscription_status(self, client_id: str) -> Dict[str, Any]:
        """Get current subscription status for a client."""
        db = database.get_db()
        
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not billing:
            return {
                "has_subscription": False,
                "status": "NONE",
                "entitlement_status": EntitlementStatus.DISABLED.value,
            }
        
        return {
            "has_subscription": True,
            "stripe_subscription_id": billing.get("stripe_subscription_id"),
            "current_plan_code": billing.get("current_plan_code"),
            "subscription_status": billing.get("subscription_status"),
            "entitlement_status": billing.get("entitlement_status"),
            "current_period_end": billing.get("current_period_end"),
            "cancel_at_period_end": billing.get("cancel_at_period_end", False),
            "onboarding_fee_paid": billing.get("onboarding_fee_paid", False),
        }
    
    async def cancel_subscription(
        self, 
        client_id: str, 
        cancel_immediately: bool = False
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.
        
        Args:
            client_id: Client ID
            cancel_immediately: If True, cancel now. If False, cancel at period end.
        """
        db = database.get_db()
        
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not billing or not billing.get("stripe_subscription_id"):
            raise ValueError("No active subscription found")
        
        subscription_id = billing.get("stripe_subscription_id")
        
        try:
            if cancel_immediately:
                # Cancel immediately
                subscription = stripe.Subscription.delete(subscription_id)
            else:
                # Cancel at period end
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            
            # Update local record
            await db.client_billing.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "cancel_at_period_end": not cancel_immediately,
                        "subscription_status": "CANCELED" if cancel_immediately else billing.get("subscription_status"),
                        "entitlement_status": EntitlementStatus.DISABLED.value if cancel_immediately else billing.get("entitlement_status"),
                        "updated_at": datetime.now(timezone.utc),
                    }
                }
            )
            
            # Audit log
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="CLIENT",
                client_id=client_id,
                metadata={
                    "action": "subscription_cancellation_requested",
                    "immediate": cancel_immediately,
                    "subscription_id": subscription_id,
                }
            )
            
            logger.info(f"Subscription cancellation requested for client {client_id}, immediate={cancel_immediately}")
            
            return {
                "success": True,
                "cancel_at_period_end": not cancel_immediately,
                "current_period_end": billing.get("current_period_end"),
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe cancel error for client {client_id}: {e}")
            raise ValueError(f"Failed to cancel subscription: {str(e)}")

    async def list_invoices(self, client_id: str, limit: int = 24) -> Dict[str, Any]:
        """
        List paid invoices for the client (billing history).
        Returns subscription invoices and identifies setup fee line items.
        """
        db = database.get_db()
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "stripe_customer_id": 1}
        )
        if not billing or not billing.get("stripe_customer_id"):
            return {"invoices": [], "has_more": False}

        stripe_customer_id = billing["stripe_customer_id"]
        onboarding_price_ids = set()
        for plan in (PlanCode.PLAN_1_SOLO, PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO):
            pid = plan_registry.get_stripe_price_ids(plan).get("onboarding_price_id")
            if pid:
                onboarding_price_ids.add(pid)

        try:
            invoices = stripe.Invoice.list(
                customer=stripe_customer_id,
                status="paid",
                limit=min(limit, 100),
                expand=["data.lines.data.price"],
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe invoice list error for client {client_id}: {e}")
            return {"invoices": [], "has_more": False}

        result = []
        for inv in invoices.get("data", []):
            lines = []
            for line in inv.get("lines", {}).get("data", []):
                price = line.get("price")
                if isinstance(price, str):
                    price_id = price
                elif isinstance(price, dict):
                    price_id = price.get("id")
                else:
                    price_id = getattr(price, "id", None) if price else None
                is_setup_fee = price_id in onboarding_price_ids if price_id else False
                amount = line.get("amount", 0)
                desc = line.get("description")
                if not desc and isinstance(price, dict):
                    desc = price.get("nickname") or price.get("product")
                if is_setup_fee:
                    desc = "Setup fee"
                lines.append({
                    "description": desc or "Subscription",
                    "amount_cents": amount,
                    "type": "setup_fee" if is_setup_fee else "subscription",
                })
            result.append({
                "id": inv.get("id"),
                "number": inv.get("number"),
                "created": inv.get("created"),
                "amount_paid": inv.get("amount_paid", 0),
                "currency": (inv.get("currency") or "gbp").upper(),
                "lines": lines,
            })
        return {
            "invoices": result,
            "has_more": invoices.get("has_more", False),
        }


# Singleton instance
stripe_service = StripeService()
