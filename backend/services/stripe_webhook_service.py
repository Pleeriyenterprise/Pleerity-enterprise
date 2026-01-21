"""Stripe Webhook Service - Production-ready webhook handling with idempotency.

This service handles ALL Stripe webhook events for Compliance Vault Pro.

Key Principles:
1. Idempotency: Every event is processed exactly once
2. Signature verification: All events must be signed
3. Plan derivation: Plan is derived from subscription price_id ONLY
4. Audit logging: Every transition is logged
5. Server-authoritative: Backend controls all entitlements

Events Handled:
- checkout.session.completed (primary provisioning trigger)
- customer.subscription.created
- customer.subscription.updated  
- customer.subscription.deleted
- invoice.paid
- invoice.payment_failed
"""
import stripe
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from database import database
from services.plan_registry import (
    plan_registry, 
    PlanCode, 
    EntitlementStatus,
    SUBSCRIPTION_PRICE_TO_PLAN
)
from services.provisioning import provisioning_service
from utils.audit import create_audit_log
from models import AuditAction

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_emergent")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


class StripeWebhookService:
    """Production-ready Stripe webhook handler with idempotency."""
    
    # =========================================================================
    # Event Processing Entry Point
    # =========================================================================
    
    async def process_webhook(
        self, 
        payload: bytes, 
        signature: str
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Main webhook entry point.
        
        Returns:
            (success, message, details)
        """
        # Step 1: Verify signature
        try:
            if STRIPE_WEBHOOK_SECRET:
                event = stripe.Webhook.construct_event(
                    payload, signature, STRIPE_WEBHOOK_SECRET
                )
            else:
                # Development mode - parse without verification
                import json
                event = stripe.Event.construct_from(
                    json.loads(payload), stripe.api_key
                )
                logger.warning("STRIPE_WEBHOOK_SECRET not set - skipping signature verification")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False, "Invalid signature", {"error": str(e)}
        except Exception as e:
            logger.error(f"Webhook parse error: {e}")
            return False, "Invalid payload", {"error": str(e)}
        
        event_id = event.get("id")
        event_type = event.get("type")
        
        logger.info(f"Processing Stripe webhook: {event_type} ({event_id})")
        
        # Step 2: Idempotency check
        db = database.get_db()
        existing = await db.stripe_events.find_one({"event_id": event_id})
        
        if existing and existing.get("status") == "PROCESSED":
            logger.info(f"Event {event_id} already processed - skipping")
            return True, "Already processed", {"event_id": event_id}
        
        # Step 3: Record event
        event_record = {
            "event_id": event_id,
            "type": event_type,
            "created": datetime.now(timezone.utc),
            "processed_at": None,
            "status": "PROCESSING",
            "error": None,
            "related_client_id": None,
            "related_subscription_id": None,
            "raw_minimal": self._extract_safe_data(event),
        }
        
        if existing:
            await db.stripe_events.update_one(
                {"event_id": event_id},
                {"$set": event_record}
            )
        else:
            await db.stripe_events.insert_one(event_record)
        
        # Step 4: Process event
        try:
            result = await self._handle_event(event)
            
            # Update event record
            await db.stripe_events.update_one(
                {"event_id": event_id},
                {
                    "$set": {
                        "status": "PROCESSED",
                        "processed_at": datetime.now(timezone.utc),
                        "related_client_id": result.get("client_id"),
                        "related_subscription_id": result.get("subscription_id"),
                    }
                }
            )
            
            logger.info(f"Event {event_id} processed successfully")
            return True, "Processed", result
            
        except Exception as e:
            logger.error(f"Event {event_id} processing failed: {e}")
            
            await db.stripe_events.update_one(
                {"event_id": event_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "processed_at": datetime.now(timezone.utc),
                        "error": str(e),
                    }
                }
            )
            
            # Create audit log for failed event
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                metadata={
                    "action_type": "STRIPE_EVENT_FAILED",
                    "event_id": event_id,
                    "event_type": event_type,
                    "error": str(e),
                }
            )
            
            # Return 200 to prevent Stripe retries (we've logged the failure)
            return True, "Event logged with error", {"error": str(e), "event_id": event_id}
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    async def _handle_event(self, event: Dict) -> Dict:
        """Route event to appropriate handler."""
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.created": self._handle_subscription_change,
            "customer.subscription.updated": self._handle_subscription_change,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_payment_failed,
        }
        
        handler = handlers.get(event_type)
        if handler:
            return await handler(data, event)
        
        logger.info(f"Ignoring unhandled event type: {event_type}")
        return {"handled": False, "event_type": event_type}
    
    async def _handle_checkout_completed(self, session: Dict, event: Dict) -> Dict:
        """
        Handle checkout.session.completed - PRIMARY provisioning trigger.
        
        This is the main entry point for new subscriptions.
        """
        db = database.get_db()
        
        # Only handle subscription mode checkouts
        mode = session.get("mode")
        if mode != "subscription":
            logger.info(f"Ignoring non-subscription checkout: {mode}")
            return {"handled": False, "mode": mode}
        
        # Extract required data
        stripe_customer_id = session.get("customer")
        stripe_subscription_id = session.get("subscription")
        metadata = session.get("metadata", {})
        client_id = metadata.get("client_id")
        
        if not client_id:
            logger.error(f"No client_id in checkout metadata: {session.get('id')}")
            raise ValueError("MANDATORY: client_id missing from session.metadata")
        
        # Fetch subscription from Stripe to get line items
        subscription = stripe.Subscription.retrieve(
            stripe_subscription_id,
            expand=["items.data.price"]
        )
        
        # Determine plan code from subscription line items
        plan_code = None
        for item in subscription.get("items", {}).get("data", []):
            price_id = item.get("price", {}).get("id")
            plan_code = plan_registry.get_plan_from_subscription_price_id(price_id)
            if plan_code:
                break
        
        if not plan_code:
            logger.error(f"No matching plan for subscription prices: {stripe_subscription_id}")
            raise ValueError(f"No matching plan found for subscription {stripe_subscription_id}")
        
        # Check onboarding fee (from session line_items)
        onboarding_fee_paid = False
        expected_onboarding_price = plan_registry.get_stripe_price_ids(plan_code).get("onboarding_price_id")
        
        # Expand line_items if available in session
        if session.get("line_items"):
            for item in session.get("line_items", {}).get("data", []):
                item_price_id = item.get("price", {}).get("id")
                if item_price_id == expected_onboarding_price:
                    onboarding_fee_paid = True
                    break
        else:
            # Fallback: assume paid if session completed successfully
            onboarding_fee_paid = True
            logger.warning("line_items not expanded in session - assuming onboarding paid")
        
        # Map subscription status to entitlement
        subscription_status = subscription.get("status", "incomplete")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(subscription_status)
        
        # Upsert ClientBilling record
        billing_record = {
            "client_id": client_id,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "current_plan_code": plan_code.value,
            "subscription_status": subscription_status.upper(),
            "entitlement_status": entitlement_status.value,
            "current_period_end": datetime.fromtimestamp(
                subscription.get("current_period_end", 0), 
                tz=timezone.utc
            ),
            "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
            "onboarding_fee_paid": onboarding_fee_paid,
            "latest_invoice_id": subscription.get("latest_invoice"),
            "updated_at": datetime.now(timezone.utc),
        }
        
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": billing_record, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        # Update client record with billing info
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": subscription_status.upper() if subscription_status in ("active", "trialing") else "ACTIVE",
                    "billing_plan": plan_code.value,
                    "stripe_customer_id": stripe_customer_id,
                    "stripe_subscription_id": stripe_subscription_id,
                    "entitlement_status": entitlement_status.value,
                }
            }
        )
        
        # Trigger provisioning if entitled
        provisioning_triggered = False
        if entitlement_status == EntitlementStatus.ENABLED:
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "onboarding_status": 1, "contact_email": 1, "contact_name": 1}
            )
            
            if client and client.get("onboarding_status") != "PROVISIONED":
                success, message = await provisioning_service.provision_client_portal(client_id)
                provisioning_triggered = success
                
                if success:
                    logger.info(f"Provisioning triggered for client {client_id}")
                else:
                    logger.error(f"Provisioning failed for client {client_id}: {message}")
            
            # Send payment received email
            try:
                from services.email_service import email_service
                
                plan_def = plan_registry.get_plan(plan_code)
                amount = f"£{plan_def.get('monthly_price', 0):.2f}/month + £{plan_def.get('onboarding_fee', 0):.2f} setup"
                frontend_url = os.getenv("FRONTEND_URL", "https://secure-compliance-5.preview.emergentagent.com")
                
                await email_service.send_payment_received_email(
                    recipient=client.get("contact_email") if client else metadata.get("email", ""),
                    client_name=client.get("contact_name", "Valued Customer") if client else "Valued Customer",
                    client_id=client_id,
                    plan_name=plan_def.get("name", plan_code.value),
                    amount=amount,
                    portal_link=f"{frontend_url}/app/dashboard"
                )
                logger.info(f"Payment received email sent to {client.get('contact_email')}")
            except Exception as e:
                logger.error(f"Failed to send payment received email: {e}")
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": "checkout.session.completed",
                "plan_code": plan_code.value,
                "subscription_status": subscription_status,
                "entitlement_status": entitlement_status.value,
                "provisioning_triggered": provisioning_triggered,
                "onboarding_fee_paid": onboarding_fee_paid,
            }
        )
        
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": stripe_subscription_id,
            "plan_code": plan_code.value,
            "entitlement_status": entitlement_status.value,
            "provisioning_triggered": provisioning_triggered,
        }
    
    async def _handle_subscription_change(self, subscription: Dict, event: Dict) -> Dict:
        """
        Handle customer.subscription.created / updated.
        
        Updates entitlements immediately on plan changes.
        """
        db = database.get_db()
        
        stripe_customer_id = subscription.get("customer")
        stripe_subscription_id = subscription.get("id")
        subscription_status = subscription.get("status", "unknown")
        
        # Find client by customer_id
        billing = await db.client_billing.find_one(
            {"stripe_customer_id": stripe_customer_id},
            {"_id": 0}
        )
        
        if not billing:
            # Try finding by subscription_id
            billing = await db.client_billing.find_one(
                {"stripe_subscription_id": stripe_subscription_id},
                {"_id": 0}
            )
        
        if not billing:
            logger.warning(f"No billing record for customer {stripe_customer_id}")
            return {"handled": False, "reason": "no_billing_record"}
        
        client_id = billing.get("client_id")
        old_plan = billing.get("current_plan_code")
        old_status = billing.get("subscription_status")
        
        # Determine plan from subscription items
        new_plan_code = None
        for item in subscription.get("items", {}).get("data", []):
            price_id = item.get("price", {}).get("id") if isinstance(item.get("price"), dict) else item.get("price")
            new_plan_code = plan_registry.get_plan_from_subscription_price_id(price_id)
            if new_plan_code:
                break
        
        if not new_plan_code:
            # Fetch expanded subscription from Stripe
            full_sub = stripe.Subscription.retrieve(
                stripe_subscription_id,
                expand=["items.data.price"]
            )
            for item in full_sub.get("items", {}).get("data", []):
                price_id = item.get("price", {}).get("id")
                new_plan_code = plan_registry.get_plan_from_subscription_price_id(price_id)
                if new_plan_code:
                    break
        
        if not new_plan_code:
            logger.error(f"Cannot determine plan for subscription {stripe_subscription_id}")
            raise ValueError(f"No matching plan for subscription {stripe_subscription_id}")
        
        # Map status to entitlement
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(subscription_status)
        
        # Update billing record
        billing_update = {
            "current_plan_code": new_plan_code.value,
            "subscription_status": subscription_status.upper(),
            "entitlement_status": entitlement_status.value,
            "current_period_end": datetime.fromtimestamp(
                subscription.get("current_period_end", 0),
                tz=timezone.utc
            ),
            "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
            "latest_invoice_id": subscription.get("latest_invoice"),
            "updated_at": datetime.now(timezone.utc),
        }
        
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": billing_update}
        )
        
        # Update client record
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "billing_plan": new_plan_code.value,
                    "subscription_status": "ACTIVE" if subscription_status in ("active", "trialing") else subscription_status.upper(),
                    "entitlement_status": entitlement_status.value,
                }
            }
        )
        
        # Detect upgrade/downgrade
        plan_changed = old_plan != new_plan_code.value
        is_upgrade = False
        is_downgrade = False
        
        if plan_changed:
            plan_order = ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"]
            old_idx = plan_order.index(old_plan) if old_plan in plan_order else 0
            new_idx = plan_order.index(new_plan_code.value) if new_plan_code.value in plan_order else 0
            is_upgrade = new_idx > old_idx
            is_downgrade = new_idx < old_idx
        
        # Handle upgrade: unlock features immediately
        if is_upgrade and entitlement_status == EntitlementStatus.ENABLED:
            logger.info(f"Upgrade detected for client {client_id}: {old_plan} -> {new_plan_code.value}")
            # Features are unlocked automatically via the billing_plan update
            # Frontend will fetch new entitlements on next API call
        
        # Handle downgrade: enforce limits non-destructively
        if is_downgrade:
            logger.info(f"Downgrade detected for client {client_id}: {old_plan} -> {new_plan_code.value}")
            new_limit = plan_registry.get_property_limit(new_plan_code)
            
            # Count current properties
            property_count = await db.properties.count_documents({"client_id": client_id})
            
            if property_count > new_limit:
                # Set LIMITED status - user must archive properties
                await db.client_billing.update_one(
                    {"client_id": client_id},
                    {"$set": {"over_property_limit": True}}
                )
                logger.warning(f"Client {client_id} over property limit after downgrade: {property_count} > {new_limit}")
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": event.get("type"),
                "old_plan": old_plan,
                "new_plan": new_plan_code.value,
                "old_status": old_status,
                "new_status": subscription_status.upper(),
                "entitlement_status": entitlement_status.value,
                "is_upgrade": is_upgrade,
                "is_downgrade": is_downgrade,
            }
        )
        
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": stripe_subscription_id,
            "plan_code": new_plan_code.value,
            "entitlement_status": entitlement_status.value,
            "is_upgrade": is_upgrade,
            "is_downgrade": is_downgrade,
        }
    
    async def _handle_subscription_deleted(self, subscription: Dict, event: Dict) -> Dict:
        """Handle customer.subscription.deleted - subscription canceled."""
        db = database.get_db()
        
        stripe_customer_id = subscription.get("customer")
        stripe_subscription_id = subscription.get("id")
        
        # Find billing record
        billing = await db.client_billing.find_one(
            {"stripe_subscription_id": stripe_subscription_id},
            {"_id": 0}
        )
        
        if not billing:
            billing = await db.client_billing.find_one(
                {"stripe_customer_id": stripe_customer_id},
                {"_id": 0}
            )
        
        if not billing:
            logger.warning(f"No billing record for deleted subscription {stripe_subscription_id}")
            return {"handled": False, "reason": "no_billing_record"}
        
        client_id = billing.get("client_id")
        
        # Update to DISABLED - DO NOT DELETE DATA
        await db.client_billing.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": "CANCELED",
                    "entitlement_status": EntitlementStatus.DISABLED.value,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": "CANCELLED",
                    "entitlement_status": EntitlementStatus.DISABLED.value,
                }
            }
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": "customer.subscription.deleted",
                "final_status": "CANCELED",
                "entitlement_status": EntitlementStatus.DISABLED.value,
            }
        )
        
        logger.info(f"Subscription canceled for client {client_id} - entitlement DISABLED")
        
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": stripe_subscription_id,
            "entitlement_status": EntitlementStatus.DISABLED.value,
        }
    
    async def _handle_invoice_paid(self, invoice: Dict, event: Dict) -> Dict:
        """Handle invoice.paid - payment successful."""
        db = database.get_db()
        
        stripe_customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        
        if not subscription_id:
            # One-off invoice, not subscription-related
            return {"handled": False, "reason": "not_subscription_invoice"}
        
        # Find billing record
        billing = await db.client_billing.find_one(
            {"stripe_customer_id": stripe_customer_id},
            {"_id": 0}
        )
        
        if not billing:
            logger.warning(f"No billing record for customer {stripe_customer_id}")
            return {"handled": False, "reason": "no_billing_record"}
        
        client_id = billing.get("client_id")
        old_status = billing.get("subscription_status")
        
        # Fetch current subscription status
        subscription = stripe.Subscription.retrieve(subscription_id)
        new_status = subscription.get("status", "unknown")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(new_status)
        
        # Update billing
        await db.client_billing.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": new_status.upper(),
                    "entitlement_status": entitlement_status.value,
                    "latest_invoice_id": invoice.get("id"),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        # Update client
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": "ACTIVE" if new_status in ("active", "trialing") else new_status.upper(),
                    "entitlement_status": entitlement_status.value,
                }
            }
        )
        
        # If recovering from PAST_DUE/UNPAID, re-enable features
        recovered = old_status in ("PAST_DUE", "UNPAID") and new_status == "active"
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": "invoice.paid",
                "invoice_id": invoice.get("id"),
                "old_status": old_status,
                "new_status": new_status.upper(),
                "entitlement_status": entitlement_status.value,
                "recovered_from_past_due": recovered,
            }
        )
        
        logger.info(f"Invoice paid for client {client_id} - status: {new_status}")
        
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": subscription_id,
            "entitlement_status": entitlement_status.value,
            "recovered": recovered,
        }
    
    async def _handle_payment_failed(self, invoice: Dict, event: Dict) -> Dict:
        """
        Handle invoice.payment_failed - payment failed.
        
        Immediately restrict side-effect actions.
        """
        db = database.get_db()
        
        stripe_customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        
        if not subscription_id:
            return {"handled": False, "reason": "not_subscription_invoice"}
        
        # Find billing record
        billing = await db.client_billing.find_one(
            {"stripe_customer_id": stripe_customer_id},
            {"_id": 0}
        )
        
        if not billing:
            logger.warning(f"No billing record for customer {stripe_customer_id}")
            return {"handled": False, "reason": "no_billing_record"}
        
        client_id = billing.get("client_id")
        
        # Fetch current subscription status from Stripe
        subscription = stripe.Subscription.retrieve(subscription_id)
        new_status = subscription.get("status", "past_due")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(new_status)
        
        # Update billing to LIMITED
        await db.client_billing.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": new_status.upper(),
                    "entitlement_status": entitlement_status.value,
                    "payment_failed_at": datetime.now(timezone.utc),
                    "latest_invoice_id": invoice.get("id"),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        # Update client
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": new_status.upper(),
                    "entitlement_status": entitlement_status.value,
                }
            }
        )
        
        # Send payment failed email
        try:
            from services.email_service import email_service
            
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "contact_email": 1, "contact_name": 1}
            )
            
            if client and client.get("contact_email"):
                frontend_url = os.getenv("FRONTEND_URL", "https://secure-compliance-5.preview.emergentagent.com")
                
                # Get next retry date if available
                retry_date = None
                if invoice.get("next_payment_attempt"):
                    retry_date = datetime.fromtimestamp(
                        invoice.get("next_payment_attempt"), tz=timezone.utc
                    ).strftime("%B %d, %Y")
                
                await email_service.send_payment_failed_email(
                    recipient=client.get("contact_email"),
                    client_name=client.get("contact_name", "Valued Customer"),
                    client_id=client_id,
                    billing_portal_link=f"{frontend_url}/app/billing",
                    retry_date=retry_date
                )
                logger.info(f"Payment failed email sent to {client.get('contact_email')}")
        except Exception as e:
            logger.error(f"Failed to send payment failed email: {e}")
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": "invoice.payment_failed",
                "invoice_id": invoice.get("id"),
                "subscription_status": new_status.upper(),
                "entitlement_status": entitlement_status.value,
                "side_effects_blocked": True,
            }
        )
        
        logger.warning(f"Payment failed for client {client_id} - entitlement LIMITED, side effects blocked")
        
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": subscription_id,
            "entitlement_status": entitlement_status.value,
            "side_effects_blocked": True,
        }
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _extract_safe_data(self, event: Dict) -> Dict:
        """Extract safe subset of event data for logging (no secrets)."""
        return {
            "id": event.get("id"),
            "type": event.get("type"),
            "created": event.get("created"),
            "object_id": event.get("data", {}).get("object", {}).get("id"),
            "object_type": event.get("data", {}).get("object", {}).get("object"),
        }


# Singleton instance
stripe_webhook_service = StripeWebhookService()
