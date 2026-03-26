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
- invoice.paid and invoice.payment_succeeded (renewal success, dunning clear)
- invoice.payment_failed (grace window, dunning)
- charge.refunded (normalized payment status = refunded)
"""
import stripe
from pymongo.errors import DuplicateKeyError
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from database import database
from services.plan_registry import plan_registry, PlanCode, EntitlementStatus
from services.billing_period_utils import period_end_from_stripe_unix
from services.subscription_lifecycle_service import (
    sync_subscription_lifecycle,
    grace_period_days,
    build_renewal_email_context,
)
from services.security_monitoring_service import record_security_event
from utils.audit import create_audit_log
from models import AuditAction, ProvisioningJob, ProvisioningJobStatus

logger = logging.getLogger(__name__)

# Initialize Stripe (prefer STRIPE_SECRET_KEY; fallback STRIPE_API_KEY)
_stripe_key = (os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY") or "").strip()
stripe.api_key = _stripe_key

# Webhook secret: support test vs live. If STRIPE_WEBHOOK_SECRET is set, use it; else choose by key prefix.
def _get_webhook_secret() -> str:
    explicit = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()
    if explicit:
        return explicit
    key = (os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY") or "").strip()
    if key.startswith("sk_live_"):
        return (os.getenv("STRIPE_WEBHOOK_SECRET_LIVE") or "").strip()
    if key.startswith("sk_test_"):
        return (os.getenv("STRIPE_WEBHOOK_SECRET_TEST") or "").strip()
    return ""


def _is_production_runtime() -> bool:
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    return env in ("production", "prod")


def _extract_webhook_context(event: Dict) -> Dict[str, Any]:
    """Extract safe fields for structured logging (event_id, event_type, livemode, client_id, subscription_id, checkout_session_id)."""
    obj = event.get("data", {}).get("object", {}) or {}
    metadata = obj.get("metadata", {}) or {}
    return {
        "event_id": event.get("id"),
        "event_type": event.get("type"),
        "livemode": event.get("livemode"),
        "client_id": metadata.get("client_id") or obj.get("customer"),
        "subscription_id": obj.get("subscription") if isinstance(obj.get("subscription"), str) else (obj.get("subscription", {}).get("id") if isinstance(obj.get("subscription"), dict) else None),
        "checkout_session_id": obj.get("id") if event.get("type") == "checkout.session.completed" else None,
    }


class StripeWebhookService:
    """Production-ready Stripe webhook handler with idempotency."""
    
    # =========================================================================
    # Event Processing Entry Point
    # =========================================================================
    
    async def process_webhook(
        self,
        payload: bytes,
        signature: str,
        client_ip: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Main webhook entry point.
        
        Returns:
            (success, message, details)
        """
        # Step 1: Verify signature (use test/live secret by key or explicit STRIPE_WEBHOOK_SECRET)
        webhook_secret = _get_webhook_secret()
        try:
            if webhook_secret:
                event = stripe.Webhook.construct_event(
                    payload, signature, webhook_secret
                )
            else:
                # Production must fail closed when webhook verification is not configured.
                if _is_production_runtime():
                    logger.error("Stripe webhook secret is not configured in production runtime")
                    try:
                        await record_security_event(
                            event_type="webhook.signature_failed",
                            ip=client_ip,
                            details={"source": "stripe", "reason": "webhook_secret_missing_in_production"},
                            severity="high",
                        )
                    except Exception:
                        pass
                    return False, "Invalid signature", {"error": "Webhook secret missing in production"}
                # Development mode - parse without verification
                import json
                event = stripe.Event.construct_from(
                    json.loads(payload), stripe.api_key
                )
                logger.warning("STRIPE_WEBHOOK_SECRET (or _TEST/_LIVE) not set - skipping signature verification")
        except stripe.error.SignatureVerificationError as e:
            logger.error("Webhook signature verification failed: %s (check STRIPE_WEBHOOK_SECRET vs Stripe key mode)", e)
            try:
                await record_security_event(
                    event_type="webhook.signature_failed",
                    ip=client_ip,
                    details={"source": "stripe", "reason": "signature_verification_failed"},
                    severity="high",
                )
            except Exception:
                pass
            return False, "Invalid signature", {"error": str(e)}
        except Exception as e:
            logger.error(f"Webhook parse error: {e}")
            try:
                await record_security_event(
                    event_type="webhook.invalid_payload",
                    ip=client_ip,
                    details={"source": "stripe", "reason": "parse_error"},
                    severity="medium",
                )
            except Exception:
                pass
            return False, "Invalid payload", {"error": str(e)}

        event_id = event.get("id")
        event_type = event.get("type")
        ctx = _extract_webhook_context(event)
        logger.info(
            "WEBHOOK_RECEIVED event_id=%s event_type=%s livemode=%s client_id=%s subscription_id=%s checkout_session_id=%s",
            event_id, event_type, ctx.get("livemode"), ctx.get("client_id"), ctx.get("subscription_id"), ctx.get("checkout_session_id"),
        )
        
        # Step 2: Idempotency check
        db = database.get_db()
        existing = await db.stripe_events.find_one({"event_id": event_id})
        
        if existing and existing.get("status") == "PROCESSED":
            logger.info(f"Event {event_id} already processed - skipping")
            try:
                await record_security_event(
                    event_type="webhook.duplicate_detected",
                    ip=client_ip,
                    details={"source": "stripe", "event_id": event_id, "reason": "already_processed"},
                    severity="low",
                )
            except Exception:
                pass
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
            try:
                await db.stripe_events.insert_one(event_record)
            except Exception as insert_err:
                if "duplicate key" in str(insert_err).lower() or "E11000" in str(insert_err):
                    logger.info(f"Event {event_id} duplicate insert (race) - skipping")
                    try:
                        await record_security_event(
                            event_type="webhook.duplicate_detected",
                            ip=client_ip,
                            details={"source": "stripe", "event_id": event_id, "reason": "insert_race_duplicate"},
                            severity="low",
                        )
                    except Exception:
                        pass
                    return True, "Already processed", {"event_id": event_id}
                raise

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

            logger.info(
                "WEBHOOK_PROCESSED_OK event_id=%s event_type=%s client_id=%s",
                event_id, event_type, result.get("client_id"),
            )
            return True, "Processed", result

        except Exception as e:
            logger.error(
                "WEBHOOK_PROCESSING_FAILED event_id=%s event_type=%s error=%s",
                event_id, event_type, str(e),
            )

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
            
            # Mark as retryable so the route can return 5xx and Stripe retries delivery.
            return False, "Processing failed", {"error": str(e), "event_id": event_id, "retryable": True}
    
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
            "charge.refunded": self._handle_charge_refunded,
        }
        
        handler = handlers.get(event_type)
        if handler:
            return await handler(data, event)
        
        logger.info(f"Ignoring unhandled event type: {event_type}")
        return {"handled": False, "event_type": event_type}
    
    async def _handle_checkout_completed(self, session: Dict, event: Dict) -> Dict:
        """
        Handle checkout.session.completed - PRIMARY provisioning trigger.
        
        Handles two types of checkouts:
        1. subscription - CVP subscription provisioning
        2. payment - Order intake (draft → order conversion)
        """
        db = database.get_db()
        
        mode = session.get("mode")
        metadata = session.get("metadata", {})
        
        # Route based on checkout type
        if mode == "payment" and metadata.get("type") == "order_intake":
            # Handle order intake payment
            return await self._handle_order_payment(session, event)
        elif mode == "subscription":
            # Handle subscription checkout (existing logic)
            return await self._handle_subscription_checkout(session, event)
        else:
            logger.info(f"Ignoring checkout mode: {mode}")
            return {"handled": False, "mode": mode}
    
    async def _handle_order_payment(self, session: Dict, event: Dict) -> Dict:
        """
        Handle one-time payment for order intake.
        
        Converts draft → order and starts workflow.
        Integrates with Document Pack Orchestrator for pack orders.
        """
        from services.intake_draft_service import convert_draft_to_order, get_draft
        from services.document_pack_webhook_handler import document_pack_webhook_handler
        
        metadata = session.get("metadata", {})
        draft_id = metadata.get("draft_id")
        draft_ref = metadata.get("draft_ref")
        service_code = metadata.get("service_code")
        
        if not draft_id:
            logger.error(f"No draft_id in order payment metadata: {session.get('id')}")
            raise ValueError("MANDATORY: draft_id missing from session.metadata")
        if not draft_ref:
            logger.warning(f"Order payment metadata missing draft_ref for session {session.get('id')}")
        if not service_code:
            logger.warning(f"Order payment metadata missing service_code for session {session.get('id')}")
        
        # Get payment intent ID
        payment_intent_id = session.get("payment_intent")
        session_id = session.get("id")
        
        logger.info(f"Processing order payment for draft {draft_ref} (PI: {payment_intent_id})")
        
        # Check if already processed (idempotency)
        db = database.get_db()
        existing = await db.orders.find_one({"source_draft_id": draft_id})
        if existing:
            logger.info(f"Order already exists for draft {draft_id}: {existing.get('order_ref')}")
            return {
                "handled": True,
                "type": "order_payment",
                "draft_id": draft_id,
                "order_id": existing.get("order_id"),
                "order_ref": existing.get("order_ref"),
                "already_processed": True,
            }
        
        # Convert draft to order (idempotency: stripe_events by event_id; orders by session_id/source_draft_id)
        event_id = (event or {}).get("id")
        try:
            order = await convert_draft_to_order(
                draft_id=draft_id,
                stripe_payment_intent_id=payment_intent_id,
                stripe_checkout_session_id=session_id,
                stripe_event_id=event_id,
            )
            
            logger.info(f"Created order {order['order_ref']} from draft {draft_ref}")
            
            # Normalized payment for Revenue Analytics (one-time / pack)
            if event_id and order.get("client_id"):
                order_service_code = order.get("service_code") or service_code
                payment_type = "pack" if order_service_code in document_pack_webhook_handler.VALID_PACK_CODES else "one_time"
                await self._insert_payment(
                    client_id=order["client_id"],
                    stripe_event_id=event_id,
                    amount=order.get("pricing", {}).get("total_pence", 0) or 0,
                    currency="gbp",
                    type=payment_type,
                    status="paid",
                    stripe_payment_intent_id=payment_intent_id,
                )
            
            try:
                from services.analytics_service import log_event
                await log_event(
                    "payment_succeeded",
                    {"client_id": order.get("client_id"), "stripe_session_id": session_id},
                    idempotency_key=(event or {}).get("id"),
                )
            except Exception:
                pass
            
            # Check if this is a Document Pack order
            order_service_code = order.get("service_code") or service_code
            if order_service_code in document_pack_webhook_handler.VALID_PACK_CODES:
                # Process via Document Pack handler
                success, message, details = await document_pack_webhook_handler.handle_checkout_completed(
                    {**session, "metadata": {**metadata, "order_id": order["order_id"], "service_code": order_service_code}}
                )
                
                if success:
                    logger.info(f"Document Pack order {order['order_ref']} processed: {message}")
                else:
                    logger.error(f"Document Pack processing failed: {message}")
                try:
                    from services.lead_automation_service import record_client_event, evaluate_client_automation_rules, EVENT_PAYMENT_SUCCESSFUL
                    if order.get("client_id"):
                        await record_client_event(
                            client_id=order["client_id"],
                            event_type=EVENT_PAYMENT_SUCCESSFUL,
                            source="stripe_webhook.order_payment",
                            metadata={"order_id": order.get("order_id"), "order_ref": order.get("order_ref")},
                            source_ref=session_id,
                        )
                        await evaluate_client_automation_rules(order["client_id"], EVENT_PAYMENT_SUCCESSFUL)
                except Exception as flow_err:
                    logger.warning("Post-payment automation trigger skipped for order %s: %s", order.get("order_id"), flow_err)
                
                return {
                    "handled": True,
                    "type": "document_pack_order",
                    "draft_id": draft_id,
                    "draft_ref": draft_ref,
                    "order_id": order["order_id"],
                    "order_ref": order["order_ref"],
                    "service_code": order_service_code,
                    "pack_processing": details,
                }
            
            return {
                "handled": True,
                "type": "order_payment",
                "draft_id": draft_id,
                "draft_ref": draft_ref,
                "order_id": order["order_id"],
                "order_ref": order["order_ref"],
            }
            
        except Exception as e:
            logger.error(f"Failed to convert draft {draft_id} to order: {e}")
            raise
    
    async def _handle_subscription_checkout(self, session: Dict, event: Dict) -> Dict:
        """
        Handle subscription checkout - CVP provisioning.
        
        This is the existing subscription logic moved to a separate method.
        """
        db = database.get_db()
        checkout_session_id = session.get("id")
        stripe_customer_id = session.get("customer")
        stripe_subscription_id = session.get("subscription")
        metadata = session.get("metadata", {}) or {}
        client_id = metadata.get("client_id")
        plan_code_meta = metadata.get("plan_code")
        logger.info(
            "HANDLER_START event.type=checkout.session.completed stripe_customer_id=%s subscription_id=%s checkout_session_id=%s metadata.client_id=%s metadata.plan_code=%s computed_client_id=%s",
            stripe_customer_id, stripe_subscription_id, checkout_session_id, metadata.get("client_id"), plan_code_meta, client_id,
        )
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
        
        # Check onboarding (setup) fee from session line_items; persist amount and invoice for billing history
        onboarding_fee_paid = False
        setup_fee_amount_cents = None
        setup_fee_invoice_id = None
        expected_onboarding_price = plan_registry.get_stripe_price_ids(plan_code).get("onboarding_price_id")
        
        if session.get("line_items"):
            for item in session.get("line_items", {}).get("data", []):
                item_price_id = item.get("price", {}).get("id")
                if item_price_id == expected_onboarding_price:
                    onboarding_fee_paid = True
                    setup_fee_amount_cents = item.get("amount", 0)
                    break
            if onboarding_fee_paid and session.get("invoice"):
                setup_fee_invoice_id = session["invoice"] if isinstance(session["invoice"], str) else (session["invoice"] or {}).get("id")
        else:
            onboarding_fee_paid = True
            logger.warning("line_items not expanded in session - assuming onboarding paid")
        
        # Map subscription status to entitlement
        subscription_status = subscription.get("status", "incomplete")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(subscription_status)
        
        # Upsert ClientBilling record; increment entitlements_version (Stripe is source of truth)
        period_end_dt = period_end_from_stripe_unix(subscription.get("current_period_end"))
        billing_record = {
            "client_id": client_id,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "current_plan_code": plan_code.value,
            "subscription_status": subscription_status.upper(),
            "entitlement_status": entitlement_status.value,
            "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
            "onboarding_fee_paid": onboarding_fee_paid,
            "latest_invoice_id": subscription.get("latest_invoice"),
            "updated_at": datetime.now(timezone.utc),
        }
        if period_end_dt:
            billing_record["current_period_end"] = period_end_dt
        if setup_fee_amount_cents is not None:
            billing_record["setup_fee_amount_cents"] = setup_fee_amount_cents
        if setup_fee_invoice_id:
            billing_record["setup_fee_invoice_id"] = setup_fee_invoice_id
        checkout_billing_update: Dict[str, Any] = {
            "$set": billing_record,
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            "$inc": {"entitlements_version": 1},
        }
        dunning_unset = {
            "payment_failed_at": "",
            "grace_period_ends_at": "",
            "dunning_stripe_invoice_id": "",
            "grace_mid_reminder_sent_at": "",
            "renewal_reminder_period_key_7d": "",
            "renewal_reminder_period_key_3d": "",
        }
        if not period_end_dt:
            checkout_billing_update["$unset"] = {**dunning_unset, "current_period_end": ""}
        else:
            checkout_billing_update["$unset"] = dunning_unset
        await db.client_billing.update_one(
            {"client_id": client_id},
            checkout_billing_update,
            upsert=True
        )
        billing_after = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "entitlements_version": 1}
        )
        entitlements_version = (billing_after or {}).get("entitlements_version", 1)

        # Update client record with billing info and entitlements_version
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": subscription_status.upper() if subscription_status in ("active", "trialing") else "ACTIVE",
                    "billing_plan": plan_code.value,
                    "stripe_customer_id": stripe_customer_id,
                    "stripe_subscription_id": stripe_subscription_id,
                    "entitlement_status": entitlement_status.value,
                    "entitlements_version": entitlements_version,
                }
            }
        )

        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            logger.warning("sync_subscription_lifecycle after checkout failed: %s", lc_err)

        # CRN: generate on payment confirmation only (idempotent; once set, never changed)
        client_crn = None
        try:
            from services.crn_service import ensure_client_crn
            client_crn = await ensure_client_crn(client_id, stripe_event_id=event.get("id") if event else None)
        except Exception as crn_err:
            logger.error(f"CRN assignment failed for {client_id}: {crn_err}")
            raise

        # Provisioning jobs: persist state only; return 200 quickly. Poller processes PAYMENT_CONFIRMED jobs.
        checkout_session_id = session.get("id")
        provisioning_triggered = False
        if entitlement_status == EntitlementStatus.ENABLED and checkout_session_id:
            existing_job = await db.provisioning_jobs.find_one(
                {"checkout_session_id": checkout_session_id},
                {"_id": 0, "job_id": 1, "status": 1}
            )
            if existing_job:
                existing_status = existing_job.get("status")
                if existing_status in (
                    ProvisioningJobStatus.PAYMENT_CONFIRMED.value,
                    ProvisioningJobStatus.FAILED.value,
                ):
                    await db.provisioning_jobs.update_one(
                        {"checkout_session_id": checkout_session_id},
                        {"$set": {"needs_run": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
                    )
                    provisioning_triggered = True
                    job_id = existing_job.get("job_id")
                    logger.info("PROVISIONING_ENQUEUED client_id=%s job_id=%s checkout_session_id=%s (re-dispatch)", client_id, job_id, checkout_session_id)
                    if job_id:
                        try:
                            import asyncio
                            asyncio.create_task(_run_provisioning_after_webhook(job_id))
                        except Exception as bg_err:
                            logger.warning("In-process provisioning trigger failed: %s", bg_err)
                else:
                    logger.info(f"Checkout {checkout_session_id} already has job {existing_job.get('job_id')} status={existing_status}")
            else:
                client_for_job = await db.clients.find_one(
                    {"client_id": client_id},
                    {"_id": 0, "intake_session_id": 1}
                )
                now = datetime.now(timezone.utc)
                job = ProvisioningJob(
                    client_id=client_id,
                    intake_session_id=(client_for_job or {}).get("intake_session_id"),
                    checkout_session_id=checkout_session_id,
                    status=ProvisioningJobStatus.PAYMENT_CONFIRMED,
                    attempt_count=0,
                    payment_confirmed_at=now,
                    needs_run=True,
                )
                doc = job.model_dump()
                for k in ["payment_confirmed_at", "provisioning_started_at", "provisioning_completed_at", "welcome_email_sent_at", "failed_at", "created_at", "updated_at", "locked_until"]:
                    if doc.get(k) and isinstance(doc[k], datetime):
                        doc[k] = doc[k].isoformat()
                try:
                    await db.provisioning_jobs.insert_one(doc)
                    provisioning_triggered = True
                    job_id = doc["job_id"]
                    logger.info("PROVISIONING_ENQUEUED client_id=%s job_id=%s checkout_session_id=%s", client_id, job_id, checkout_session_id)
                    # In-process trigger: run job in background so provisioning can complete without a separate worker
                    try:
                        import asyncio
                        asyncio.create_task(_run_provisioning_after_webhook(job_id))
                    except Exception as bg_err:
                        logger.warning("In-process provisioning trigger failed (poller will pick up): %s", bg_err)
                except Exception as e:
                    if "duplicate key" in str(e).lower() or "E11000" in str(e):
                        await db.provisioning_jobs.update_one(
                            {"checkout_session_id": checkout_session_id},
                            {"$set": {"needs_run": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
                        )
                        provisioning_triggered = True
                        existing_job = await db.provisioning_jobs.find_one(
                            {"checkout_session_id": checkout_session_id},
                            {"_id": 0, "job_id": 1}
                        )
                        job_id = (existing_job or {}).get("job_id")
                        logger.info("PROVISIONING_ENQUEUED client_id=%s job_id=%s checkout_session_id=%s (re-dispatch)", client_id, job_id, checkout_session_id)
                        if job_id:
                            try:
                                import asyncio
                                asyncio.create_task(_run_provisioning_after_webhook(job_id))
                            except Exception as bg_err:
                                logger.warning("In-process provisioning trigger failed: %s", bg_err)
                    else:
                        logger.error(f"Failed to create provisioning job: {e}")
                        raise
        
        # Audit log (plan updated from Stripe; used for pre-check and verification)
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "PLAN_UPDATED_FROM_STRIPE",
                "event_type": "checkout.session.completed",
                "plan_code": plan_code.value,
                "subscription_status": subscription_status,
                "entitlement_status": entitlement_status.value,
                "entitlements_version": entitlements_version,
                "provisioning_triggered": provisioning_triggered,
                "onboarding_fee_paid": onboarding_fee_paid,
            }
        )

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

        # Billing notification: payment confirmation only (no dashboard link until password is set).
        try:
            plan_def = plan_registry.get_plan(plan_code)
            client_for_email = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "contact_name": 1, "full_name": 1, "customer_reference": 1, "email": 1, "contact_email": 1},
            )
            client_name = (client_for_email or {}).get("contact_name") or (client_for_email or {}).get("full_name") or ""
            client_email_for_pdf = (
                (client_for_email or {}).get("email") or (client_for_email or {}).get("contact_email") or ""
            ).strip()
            plan_pricing_line = f"£{plan_def.get('monthly_price', 0):.2f}/month + £{plan_def.get('onboarding_fee', 0):.2f} setup"
            amount_total_cents = session.get("amount_total")
            currency = (session.get("currency") or "gbp").strip().upper()
            if amount_total_cents is not None:
                sym = "£" if currency == "GBP" else ""
                amt_display = f"{sym}{amount_total_cents / 100:.2f}" + ("" if sym else f" {currency}")
            else:
                amt_display = plan_pricing_line
            payment_dt = datetime.now(timezone.utc)
            payment_date_display = payment_dt.strftime("%d %B %Y %H:%M UTC")
            sess_id = checkout_session_id or (session.get("id") or "")
            pi = session.get("payment_intent")
            if isinstance(pi, dict):
                pi_ref = pi.get("id") or ""
            else:
                pi_ref = (pi or "") if isinstance(pi, str) else ""
            event_id = (event or {}).get("id", "")
            reference_display = sess_id or pi_ref or event_id or client_id
            support_email = (os.getenv("SUPPORT_EMAIL") or "info@pleerityenterprise.co.uk").strip()
            idempotency_key = f"{event_id}_SUBSCRIPTION_CONFIRMED" if event_id else None
            from services.notification_orchestrator import notification_orchestrator
            import base64

            from services.order_receipt_service import ensure_subscription_checkout_invoice_pdf

            sub_ctx = {
                "payment_receipt_layout": "structured",
                "client_name": client_name or "Valued Customer",
                "plan_name": plan_def.get("name", plan_code.value),
                "amount_display": amt_display,
                "payment_date_display": payment_date_display,
                "reference_display": reference_display,
                "support_email": support_email,
                "customer_reference": (client_for_email or {}).get("customer_reference") or "",
                "subject": "Payment received — Compliance Vault Pro",
            }
            subscription_invoice_number = None
            try:
                period_start = period_end_from_stripe_unix(subscription.get("current_period_start"))
                period_end = period_end_from_stripe_unix(subscription.get("current_period_end"))
                ok_pdf, pdf_sub, inv_no, pdf_err = await ensure_subscription_checkout_invoice_pdf(
                    client_id=client_id,
                    checkout_session_id=checkout_session_id or "",
                    session=session,
                    customer_name=client_name or "Valued Customer",
                    customer_email=client_email_for_pdf,
                    plan_code=plan_code,
                    billing_period_start=period_start,
                    billing_period_end=period_end,
                )
                if ok_pdf and pdf_sub and inv_no:
                    subscription_invoice_number = inv_no
                    sub_ctx["attachments"] = [
                        {
                            "Name": f"{inv_no}.pdf",
                            "Content": base64.b64encode(pdf_sub).decode("utf-8"),
                            "ContentType": "application/pdf",
                        }
                    ]
                    await create_audit_log(
                        action=AuditAction.ORDER_RECEIPT_PDF_GENERATED,
                        client_id=client_id,
                        resource_type="stripe_checkout",
                        resource_id=checkout_session_id or "",
                        metadata={"source": "cvp_subscription_checkout", "invoice_number": inv_no},
                    )
                elif pdf_err:
                    logger.warning("CVP subscription invoice PDF skipped: %s", pdf_err)
            except Exception as pdf_ex:
                logger.warning("CVP subscription invoice PDF failed (non-blocking): %s", pdf_ex)

            result = await notification_orchestrator.send(
                template_key="SUBSCRIPTION_CONFIRMED",
                client_id=client_id,
                context=sub_ctx,
                idempotency_key=idempotency_key,
                event_type="checkout.session.completed",
            )
            if result.outcome in ("sent", "duplicate_ignored") and sub_ctx.get("attachments") and subscription_invoice_number:
                try:
                    await create_audit_log(
                        action=AuditAction.ORDER_RECEIPT_ATTACHED_TO_EMAIL,
                        client_id=client_id,
                        metadata={
                            "source": "cvp_subscription_checkout",
                            "invoice_number": subscription_invoice_number,
                            "template_key": "SUBSCRIPTION_CONFIRMED",
                        },
                    )
                except Exception:
                    pass
            if result.outcome in ("sent", "duplicate_ignored"):
                from services.onboarding_email_governance import milestone_set_payload

                logger.info(
                    "onboarding_payment_confirmation_email_sent client_id=%s template=SUBSCRIPTION_CONFIRMED stripe_event_id=%s",
                    client_id,
                    event_id,
                )
                await db.clients.update_one(
                    {"client_id": client_id},
                    {
                        "$set": {
                            "onboarding_payment_confirmation_email_sent_at": payment_dt.isoformat(),
                            **milestone_set_payload("payment_confirmed_at", payment_dt),
                            **milestone_set_payload("payment_email_sent_at", payment_dt),
                        }
                    },
                )
                if checkout_session_id:
                    try:
                        from services.order_receipt_service import STRIPE_CHECKOUT_INVOICES

                        await db[STRIPE_CHECKOUT_INVOICES].update_one(
                            {"_id": checkout_session_id},
                            {"$set": {"receipt_email_sent_at": payment_dt}},
                        )
                    except Exception as _inv_e:
                        logger.warning("receipt_email_sent_at not set on checkout invoice: %s", _inv_e)
                await create_audit_log(
                    action=AuditAction.ONBOARDING_PAYMENT_CONFIRMATION_EMAIL_SENT,
                    client_id=client_id,
                    metadata={
                        "template_key": "SUBSCRIPTION_CONFIRMED",
                        "stripe_event_id": event_id,
                        "message_id": getattr(result, "message_id", None),
                    },
                )
        except Exception as e:
            logger.warning(f"SUBSCRIPTION_CONFIRMED notification: {e}")
        
        logger.info(
            "HANDLER_END event.type=checkout.session.completed client_id=%s db_updated=subscription_status=%s billing_plan=%s entitlement_status=%s onboarding_status=(unchanged) provisioning_triggered=%s",
            client_id, subscription_status.upper(), plan_code.value, entitlement_status.value, provisioning_triggered,
        )
        try:
            from services.analytics_service import log_event
            await log_event(
                "payment_succeeded",
                {"client_id": client_id, "stripe_subscription_id": stripe_subscription_id, "stripe_session_id": checkout_session_id},
                idempotency_key=(event or {}).get("id"),
            )
        except Exception:
            pass

        # Mark risk-check lead as converted (authoritative; only on payment). Idempotent.
        lead_id_meta = metadata.get("lead_id")
        if lead_id_meta and (lead_id_meta or "").strip():
            try:
                now_utc = datetime.now(timezone.utc)
                res = await db.risk_leads.update_one(
                    {"lead_id": (lead_id_meta or "").strip(), "status": {"$ne": "converted"}},
                    {"$set": {
                        "status": "converted",
                        "converted_at": now_utc.isoformat(),
                        "client_id": client_id,
                        "customer_reference": client_crn or "",
                        "lead_reference": (lead_id_meta or "").strip(),
                        "stripe_subscription_id": stripe_subscription_id,
                        "updated_at": now_utc.isoformat(),
                    }},
                )
                if res.modified_count:
                    lead_doc = await db.risk_leads.find_one(
                        {"lead_id": (lead_id_meta or "").strip()},
                        {"_id": 0, "snapshot": 1, "computed_score": 1, "exposure_range_label": 1, "flags": 1, "created_at": 1, "email": 1},
                    )
                    # Optional: import risk snapshot into client (once; does not affect compliance scoring)
                    if lead_doc and not (await db.clients.find_one({"client_id": client_id}, {"_id": 0, "initial_risk_snapshot": 1}) or {}).get("initial_risk_snapshot"):
                        snapshot = lead_doc.get("snapshot")
                        await db.clients.update_one(
                            {"client_id": client_id},
                            {"$set": {"initial_risk_snapshot": {
                                "source": "risk-check",
                                "lead_id": (lead_id_meta or "").strip(),
                                "generated_at": lead_doc.get("created_at"),
                                "score_estimate": lead_doc.get("computed_score"),
                                "exposure_band": lead_doc.get("exposure_range_label"),
                                "flags": lead_doc.get("flags") or [],
                                "disclaimer": "Informational estimate from the pre-intake risk check. Not legal advice.",
                            }}},
                        )
                    # Sync conversion to central leads: convert matching lead (by risk_lead_id in source_metadata or email)
                    if lead_doc and lead_doc.get("email"):
                        try:
                            from services.lead_service import LeadService
                            from services.lead_models import LeadStatus
                            central = await db.leads.find_one(
                                {"$or": [
                                    {"source_metadata.risk_lead_id": (lead_id_meta or "").strip()},
                                    {"email": lead_doc["email"].lower(), "source_platform": "COMPLIANCE_RISK_CHECK"},
                                ], "status": LeadStatus.ACTIVE.value},
                                {"_id": 0, "lead_id": 1},
                            )
                            if central:
                                await LeadService.convert_lead(
                                    central["lead_id"],
                                    client_id,
                                    actor_id="system",
                                    conversion_notes="Stripe checkout; risk-check lead converted",
                                )
                        except Exception as e:
                            logger.warning("Central lead conversion sync failed: %s", e)
            except Exception as e:
                logger.warning("Risk lead conversion mark failed lead_id=%s: %s", lead_id_meta, e)
        else:
            # Fallback: no lead_id in metadata; try to find risk lead by customer email (e.g. user lost link)
            customer_email = (session.get("customer_details") or {}).get("email") or session.get("customer_email")
            if customer_email and isinstance(customer_email, str) and customer_email.strip():
                try:
                    email_lower = customer_email.strip().lower()
                    now_utc = datetime.now(timezone.utc)
                    existing_lead = await db.risk_leads.find_one(
                        {"email": email_lower},
                        {"_id": 0, "lead_id": 1},
                    )
                    res = await db.risk_leads.update_one(
                        {"email": email_lower, "status": {"$ne": "converted"}},
                        {"$set": {
                            "status": "converted",
                            "converted_at": now_utc.isoformat(),
                            "client_id": client_id,
                            "customer_reference": client_crn or "",
                            "lead_reference": (existing_lead or {}).get("lead_id", ""),
                            "stripe_subscription_id": stripe_subscription_id,
                            "updated_at": now_utc.isoformat(),
                        }},
                    )
                    if res.modified_count:
                        lead_doc = await db.risk_leads.find_one(
                            {"email": email_lower},
                            {"_id": 0, "lead_id": 1, "computed_score": 1, "exposure_range_label": 1, "flags": 1, "created_at": 1, "email": 1},
                        )
                        if lead_doc and not (await db.clients.find_one({"client_id": client_id}, {"_id": 0, "initial_risk_snapshot": 1}) or {}).get("initial_risk_snapshot"):
                            await db.clients.update_one(
                                {"client_id": client_id},
                                {"$set": {"initial_risk_snapshot": {
                                    "source": "risk-check",
                                    "lead_id": lead_doc.get("lead_id", ""),
                                    "generated_at": lead_doc.get("created_at"),
                                    "score_estimate": lead_doc.get("computed_score"),
                                    "exposure_band": lead_doc.get("exposure_range_label"),
                                    "flags": lead_doc.get("flags") or [],
                                    "disclaimer": "Informational estimate from the pre-intake risk check. Not legal advice.",
                                }}},
                            )
                        # Sync conversion to central leads by email
                        if lead_doc:
                            try:
                                from services.lead_service import LeadService
                                from services.lead_models import LeadStatus
                                central = await db.leads.find_one(
                                    {"email": email_lower, "source_platform": "COMPLIANCE_RISK_CHECK", "status": LeadStatus.ACTIVE.value},
                                    {"_id": 0, "lead_id": 1},
                                )
                                if central:
                                    await LeadService.convert_lead(
                                        central["lead_id"],
                                        client_id,
                                        actor_id="system",
                                        conversion_notes="Stripe checkout; risk-check lead converted (matched by email)",
                                    )
                            except Exception as e:
                                logger.warning("Central lead conversion sync (by email) failed: %s", e)
                except Exception as e:
                    logger.warning("Risk lead conversion by email failed email=%s: %s", customer_email[:20] if customer_email else "", e)

        try:
            from services.lead_automation_service import record_client_event, evaluate_client_automation_rules, EVENT_PAYMENT_SUCCESSFUL
            await record_client_event(
                client_id=client_id,
                event_type=EVENT_PAYMENT_SUCCESSFUL,
                source="stripe_webhook.subscription_checkout",
                metadata={"subscription_id": stripe_subscription_id, "plan_code": plan_code.value},
                source_ref=checkout_session_id,
            )
            await evaluate_client_automation_rules(client_id, EVENT_PAYMENT_SUCCESSFUL)
        except Exception as flow_err:
            logger.warning("Post-payment automation trigger skipped for client %s: %s", client_id, flow_err)

        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": stripe_subscription_id,
            "plan_code": plan_code.value,
            "entitlement_status": entitlement_status.value,
            "entitlements_version": entitlements_version,
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
        event_type = (event or {}).get("type", "customer.subscription.updated")
        logger.info(
            "HANDLER_START event.type=%s stripe_customer_id=%s subscription_id=%s checkout_session_id=(n/a) metadata.client_id=(from_billing) metadata.plan_code=(from_items) computed_client_id=(lookup)",
            event_type, stripe_customer_id, stripe_subscription_id,
        )
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
        
        # Update billing record; increment entitlements_version on plan/status change from Stripe
        period_end_dt = period_end_from_stripe_unix(subscription.get("current_period_end"))
        billing_update = {
            "current_plan_code": new_plan_code.value,
            "subscription_status": subscription_status.upper(),
            "entitlement_status": entitlement_status.value,
            "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
            "latest_invoice_id": subscription.get("latest_invoice"),
            "updated_at": datetime.now(timezone.utc),
        }
        if period_end_dt:
            billing_update["current_period_end"] = period_end_dt
        sub_status_update: Dict[str, Any] = {
            "$set": billing_update,
            "$inc": {"entitlements_version": 1},
        }
        if not period_end_dt:
            sub_status_update["$unset"] = {"current_period_end": ""}
        await db.client_billing.update_one(
            {"client_id": client_id},
            sub_status_update,
        )
        billing_after = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "entitlements_version": 1}
        )
        entitlements_version = (billing_after or {}).get("entitlements_version", 1)

        # Update client record
        sub_status_set = "ACTIVE" if subscription_status in ("active", "trialing") else subscription_status.upper()
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "billing_plan": new_plan_code.value,
                    "subscription_status": sub_status_set,
                    "entitlement_status": entitlement_status.value,
                    "entitlements_version": entitlements_version,
                }
            }
        )
        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            logger.warning("sync_subscription_lifecycle after subscription change failed: %s", lc_err)

        logger.info(
            "HANDLER_END event.type=%s client_id=%s db_updated=subscription_status=%s billing_plan=%s entitlement_status=%s",
            event_type, client_id, sub_status_set, new_plan_code.value, entitlement_status.value,
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

        # Reconcile plan change: disable/revoke paid features on downgrade or when subscription not active
        try:
            from services.plan_reconciliation_service import reconcile_plan_change
            new_status_upper = subscription_status.upper() if subscription_status else None
            await reconcile_plan_change(
                client_id=client_id,
                old_plan=old_plan,
                new_plan=new_plan_code.value,
                reason="stripe_webhook",
                subscription_status=new_status_upper,
            )
        except Exception as reconcile_err:
            logger.exception("Plan reconciliation failed for client %s: %s", client_id, reconcile_err)
            # Do not fail webhook; audit and continue
        
        # Audit log: plan updated from Stripe (pre-check / verification)
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "PLAN_UPDATED_FROM_STRIPE",
                "event_type": event.get("type"),
                "old_plan": old_plan,
                "new_plan": new_plan_code.value,
                "old_status": old_status,
                "new_status": subscription_status.upper(),
                "entitlement_status": entitlement_status.value,
                "entitlements_version": entitlements_version,
                "is_upgrade": is_upgrade,
                "is_downgrade": is_downgrade,
            }
        )
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
            "entitlements_version": entitlements_version,
            "is_upgrade": is_upgrade,
            "is_downgrade": is_downgrade,
        }
    
    async def _handle_subscription_deleted(self, subscription: Dict, event: Dict) -> Dict:
        """Handle customer.subscription.deleted - subscription canceled."""
        db = database.get_db()
        stripe_customer_id = subscription.get("customer")
        stripe_subscription_id = subscription.get("id")
        logger.info(
            "HANDLER_START event.type=customer.subscription.deleted stripe_customer_id=%s subscription_id=%s checkout_session_id=(n/a) metadata.client_id=(from_billing) computed_client_id=(lookup)",
            stripe_customer_id, stripe_subscription_id,
        )
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
        old_plan = billing.get("current_plan_code")
        
        # Update to DISABLED - DO NOT DELETE DATA
        await db.client_billing.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": "CANCELED",
                    "entitlement_status": EntitlementStatus.DISABLED.value,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$unset": {
                    "payment_failed_at": "",
                    "grace_period_ends_at": "",
                    "dunning_stripe_invoice_id": "",
                    "grace_mid_reminder_sent_at": "",
                },
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

        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            logger.warning("sync_subscription_lifecycle after subscription deleted failed: %s", lc_err)
        
        # Reconcile: revoke all paid-feature state (scheduled reports, SMS, tenant portal, white-label)
        try:
            from services.plan_reconciliation_service import reconcile_plan_change
            await reconcile_plan_change(
                client_id=client_id,
                old_plan=old_plan,
                new_plan=None,
                reason="stripe_webhook",
                subscription_status="CANCELED",
            )
        except Exception as reconcile_err:
            logger.exception("Plan reconciliation failed for client %s on subscription deleted: %s", client_id, reconcile_err)
        
        # Send subscription canceled email via orchestrator
        try:
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "contact_email": 1, "contact_name": 1}
            )
            
            if client and client.get("contact_email"):
                from utils.public_app_url import get_public_app_url
                base_url = get_public_app_url(for_email_links=False)
                access_end_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
                event_id = (event or {}).get("id", "")
                idempotency_key = f"{event_id}_SUBSCRIPTION_CANCELED" if event_id else None
                from services.notification_orchestrator import notification_orchestrator
                await notification_orchestrator.send(
                    template_key="SUBSCRIPTION_CANCELED",
                    client_id=client_id,
                    context={
                        "client_name": client.get("contact_name", "Valued Customer"),
                        "access_end_date": access_end_date,
                        "billing_portal_link": f"{base_url}/settings/billing",
                        "company_name": "Pleerity Enterprise Ltd",
                        "support_email": "info@pleerityenterprise.co.uk",
                    },
                    idempotency_key=idempotency_key,
                    event_type="customer.subscription.deleted",
                )
                logger.info(f"Subscription canceled notification sent for client {client_id}")
        except Exception as e:
            logger.error(f"Failed to send subscription canceled notification: {e}")
        
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
        
        logger.info(
            "HANDLER_END event.type=customer.subscription.deleted client_id=%s db_updated=subscription_status=CANCELED entitlement_status=DISABLED",
            client_id,
        )
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": stripe_subscription_id,
            "entitlement_status": EntitlementStatus.DISABLED.value,
        }
    
    async def _handle_invoice_paid(self, invoice: Dict, event: Dict) -> Dict:
        """Handle invoice.paid / invoice.payment_succeeded — renewal or recovery after failure."""
        db = database.get_db()
        stripe_customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        event_type = (event or {}).get("type") or "invoice.paid"
        logger.info(
            "HANDLER_START event.type=%s stripe_customer_id=%s subscription_id=%s",
            event_type,
            stripe_customer_id,
            subscription_id,
        )
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
        old_status = billing.get("subscription_status")
        
        # Fetch current subscription status (Stripe source of truth)
        subscription = stripe.Subscription.retrieve(subscription_id)
        new_status = subscription.get("status", "unknown")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(new_status)
        period_end_dt = period_end_from_stripe_unix(subscription.get("current_period_end"))
        had_dunning = bool(billing.get("payment_failed_at") or billing.get("grace_period_ends_at"))

        set_doc: Dict[str, Any] = {
            "subscription_status": new_status.upper(),
            "entitlement_status": entitlement_status.value,
            "latest_invoice_id": invoice.get("id"),
            "updated_at": datetime.now(timezone.utc),
        }
        if period_end_dt:
            set_doc["current_period_end"] = period_end_dt

        update: Dict[str, Any] = {"$set": set_doc}
        unset_doc: Dict[str, str] = {}
        if not period_end_dt:
            unset_doc["current_period_end"] = ""
        if had_dunning:
            unset_doc.update(
                {
                    "payment_failed_at": "",
                    "grace_period_ends_at": "",
                    "dunning_stripe_invoice_id": "",
                    "grace_mid_reminder_sent_at": "",
                    "renewal_reminder_period_key_7d": "",
                    "renewal_reminder_period_key_3d": "",
                }
            )
        if unset_doc:
            update["$unset"] = unset_doc
        if had_dunning:
            update["$inc"] = {"entitlements_version": 1}

        await db.client_billing.update_one({"client_id": client_id}, update)

        billing_after = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "entitlements_version": 1},
        )
        entitlements_version = (billing_after or {}).get("entitlements_version", 1)

        sub_for_client = "ACTIVE" if new_status in ("active", "trialing") else new_status.upper()
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": sub_for_client,
                    "entitlement_status": entitlement_status.value,
                    "entitlements_version": entitlements_version,
                }
            },
        )

        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            logger.warning("sync_subscription_lifecycle after invoice.paid failed: %s", lc_err)

        billing_final = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0, "entitlement_status": 1})
        final_ent = (billing_final or {}).get("entitlement_status") or entitlement_status.value

        recovered = old_status in ("PAST_DUE", "UNPAID") and new_status == "active"

        # Recurring cycle confirmation (not initial checkout — that uses SUBSCRIPTION_CONFIRMED)
        if invoice.get("billing_reason") == "subscription_cycle" and new_status == "active":
            try:
                client_row = await db.clients.find_one(
                    {"client_id": client_id},
                    {"_id": 0, "contact_name": 1, "full_name": 1},
                )
                client_name = (client_row or {}).get("contact_name") or (client_row or {}).get("full_name") or "Valued Customer"
                from utils.public_app_url import get_public_app_url
                base_url = get_public_app_url(for_email_links=False)
                cpe_out = period_end_dt or billing.get("current_period_end")
                renewal_display = ""
                if cpe_out:
                    if hasattr(cpe_out, "strftime"):
                        renewal_display = cpe_out.strftime("%d %B %Y")
                    else:
                        renewal_display = str(cpe_out)[:10]
                amt = (invoice.get("amount_paid") or 0) / 100.0
                cur = (invoice.get("currency") or "gbp").lower()
                sym = "£" if cur == "gbp" else ""
                amt_display = f"{sym}{amt:.2f}" + ("" if sym else f" {cur.upper()}")
                # Invoice-stable idempotency: Stripe may emit both invoice.paid and invoice.payment_succeeded
                inv_stable = (invoice.get("id") or "").strip()
                event_id = (event or {}).get("id", "")
                idempotency_key = (
                    f"{inv_stable}_SUBSCRIPTION_RENEWAL_PAID"
                    if inv_stable
                    else (f"{event_id}_SUBSCRIPTION_RENEWAL_PAID" if event_id else None)
                )
                from services.notification_orchestrator import notification_orchestrator
                payment_date_display = datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")
                next_steps = (
                    f"<p>Your subscription remains active. Next renewal: <strong>{renewal_display or 'see Billing'}</strong>.</p>"
                    f"<p>You can review invoices and payment methods any time from Billing.</p>"
                )
                await notification_orchestrator.send(
                    template_key="SUBSCRIPTION_RENEWAL_PAID",
                    client_id=client_id,
                    context={
                        "client_name": client_name,
                        "plan_name": "Compliance Vault Pro subscription",
                        "amount_display": amt_display,
                        "payment_date_display": payment_date_display,
                        "reference_display": (invoice.get("id") or "")[:120],
                        "next_steps_html": next_steps,
                        "receipt_cta_label": "Open Billing",
                        "receipt_cta_url": f"{base_url}/settings/billing",
                    },
                    idempotency_key=idempotency_key,
                    event_type=event_type,
                )
            except Exception as mail_err:
                logger.warning("SUBSCRIPTION_RENEWAL_PAID send failed (non-blocking): %s", mail_err)

        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": event_type,
                "invoice_id": invoice.get("id"),
                "old_status": old_status,
                "new_status": new_status.upper(),
                "entitlement_status": final_ent,
                "recovered_from_past_due": recovered,
                "cleared_dunning": had_dunning,
            }
        )
        
        logger.info(
            "HANDLER_END event.type=%s client_id=%s db_updated=subscription_status=%s entitlement_status=%s",
            event_type,
            client_id,
            new_status.upper(),
            final_ent,
        )
        try:
            from services.analytics_service import log_event
            inv_for_analytics = (invoice.get("id") or "").strip()
            analytics_dedupe = (
                f"invoice_paid:{inv_for_analytics}" if inv_for_analytics else (event or {}).get("id")
            )
            await log_event(
                "payment_succeeded",
                {"client_id": client_id, "stripe_subscription_id": subscription_id},
                idempotency_key=analytics_dedupe,
            )
        except Exception:
            pass
        # Normalized payment record: dedupe by invoice id so invoice.paid + payment_succeed don't double-insert
        event_id_raw = (event or {}).get("id")
        inv_pid = (invoice.get("id") or "").strip()
        payment_row_key = f"stripe_invoice:{inv_pid}:paid" if inv_pid else event_id_raw
        if payment_row_key and client_id:
            charge_id = invoice.get("charge")
            if isinstance(charge_id, dict):
                charge_id = charge_id.get("id") if charge_id else None
            await self._insert_payment(
                client_id=client_id,
                stripe_event_id=payment_row_key,
                amount=invoice.get("amount_paid") or 0,
                currency=(invoice.get("currency") or "gbp").lower(),
                type="subscription",
                status="paid",
                stripe_invoice_id=invoice.get("id"),
                stripe_charge_id=charge_id,
            )
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": subscription_id,
            "entitlement_status": final_ent,
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
        logger.info(
            "HANDLER_START event.type=invoice.payment_failed stripe_customer_id=%s subscription_id=%s checkout_session_id=(n/a) metadata.client_id=(from_billing) computed_client_id=(lookup)",
            stripe_customer_id, subscription_id,
        )
        if not subscription_id:
            return {"handled": False, "reason": "not_subscription_invoice"}
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

        inv_id = invoice.get("id")
        now = datetime.now(timezone.utc)
        g_days = grace_period_days()
        prev_dunning = billing.get("dunning_stripe_invoice_id")
        grace_extra: Dict[str, Any] = {}
        bump = False
        if prev_dunning != inv_id:
            grace_extra["dunning_stripe_invoice_id"] = inv_id
            grace_extra["grace_period_ends_at"] = now + timedelta(days=g_days)
            grace_extra["grace_mid_reminder_sent_at"] = None
            bump = True
        elif not billing.get("grace_period_ends_at"):
            grace_extra["grace_period_ends_at"] = now + timedelta(days=g_days)
            bump = True

        billing_set: Dict[str, Any] = {
            "subscription_status": new_status.upper(),
            "entitlement_status": entitlement_status.value,
            "payment_failed_at": now,
            "latest_invoice_id": inv_id,
            "updated_at": now,
            **grace_extra,
        }
        pay_update: Dict[str, Any] = {"$set": billing_set}
        if bump:
            pay_update["$inc"] = {"entitlements_version": 1}

        await db.client_billing.update_one({"client_id": client_id}, pay_update)

        billing_after = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "entitlements_version": 1},
        )
        entitlements_version = (billing_after or {}).get("entitlements_version", 1)

        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": new_status.upper(),
                    "entitlement_status": entitlement_status.value,
                    "entitlements_version": entitlements_version,
                }
            },
        )

        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            logger.warning("sync_subscription_lifecycle after payment_failed failed: %s", lc_err)

        billing_final = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0, "entitlement_status": 1})
        final_ent = (billing_final or {}).get("entitlement_status") or entitlement_status.value

        # Send payment failed email via orchestrator (idempotent, no direct provider)
        try:
            client_for_name = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "contact_name": 1, "full_name": 1},
            )
            client_name = (client_for_name or {}).get("contact_name") or (client_for_name or {}).get("full_name") or "Valued Customer"
            from utils.public_app_url import get_public_app_url
            base_url = get_public_app_url(for_email_links=False)
            retry_date = None
            if invoice.get("next_payment_attempt"):
                retry_date = datetime.fromtimestamp(
                    invoice.get("next_payment_attempt"), tz=timezone.utc
                ).strftime("%B %d, %Y")
            event_id = (event or {}).get("id", "")
            idempotency_key = f"{event_id}_PAYMENT_FAILED" if event_id else None
            from services.notification_orchestrator import notification_orchestrator
            result = await notification_orchestrator.send(
                template_key="PAYMENT_FAILED",
                client_id=client_id,
                context={
                    "client_name": client_name,
                    "billing_portal_link": f"{base_url}/settings/billing",
                    "retry_date": retry_date or "",
                    "grace_period_days": str(g_days),
                },
                idempotency_key=idempotency_key,
                event_type="invoice.payment_failed",
            )
            if result.outcome == "sent":
                logger.info(f"Payment failed notification sent for client {client_id}")
            elif result.outcome not in ("duplicate_ignored", "blocked"):
                logger.warning(f"Payment failed notification outcome: {result.outcome} - {result.error_message}")
        except Exception as e:
            logger.error(f"Failed to send payment failed notification: {e}")
        
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
                "entitlement_status": final_ent,
                "side_effects_blocked": True,
                "grace_period_days": g_days,
            }
        )
        
        logger.info(
            "HANDLER_END event.type=invoice.payment_failed client_id=%s db_updated=subscription_status=%s entitlement_status=%s",
            client_id, new_status.upper(), final_ent,
        )
        # Normalized payment record (failed) for Revenue Analytics
        event_id = (event or {}).get("id")
        if event_id and client_id:
            await self._insert_payment(
                client_id=client_id,
                stripe_event_id=event_id,
                amount=invoice.get("amount_due") or 0,
                currency=(invoice.get("currency") or "gbp").lower(),
                type="subscription",
                status="failed",
                stripe_invoice_id=invoice.get("id"),
            )
        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": subscription_id,
            "entitlement_status": final_ent,
            "side_effects_blocked": True,
        }
    
    async def _handle_charge_refunded(self, charge: Dict, event: Dict) -> Dict:
        """Handle charge.refunded - mark corresponding payment as refunded."""
        db = database.get_db()
        charge_id = charge.get("id")
        if not charge_id:
            return {"handled": False, "reason": "no_charge_id"}
        # Find payment by stripe_charge_id or by stripe_invoice_id (charge.invoice)
        invoice_id = charge.get("invoice")
        if isinstance(invoice_id, dict):
            invoice_id = invoice_id.get("id") if invoice_id else None
        result = await db.payments.update_one(
            {"$or": [{"stripe_charge_id": charge_id}, {"stripe_invoice_id": invoice_id}]},
            {"$set": {"status": "refunded", "updated_at": datetime.now(timezone.utc)}},
        )
        if result.modified_count:
            logger.info("Payment marked refunded for charge %s", charge_id)
        return {"handled": True, "charge_id": charge_id, "updated": result.modified_count}
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    async def _insert_payment(
        self,
        *,
        client_id: str,
        stripe_event_id: str,
        amount: int,
        currency: str,
        type: str,
        status: str,
        stripe_invoice_id: Optional[str] = None,
        stripe_charge_id: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
        cost_pence: Optional[int] = None,
    ) -> None:
        """Insert normalized payment for Revenue Analytics.

        Idempotent by stripe_event_id (unique index). For subscription invoice *paid* rows,
        pass a stable key such as ``stripe_invoice:{invoice_id}:paid`` so duplicate
        Stripe event types (e.g. invoice.paid + invoice.payment_succeeded) do not double-count.
        """
        db = database.get_db()
        if not db:
            return
        doc = {
            "client_id": client_id,
            "stripe_event_id": stripe_event_id,
            "amount": amount,
            "currency": currency,
            "type": type,
            "status": status,
            "created_at": datetime.now(timezone.utc),
        }
        if stripe_invoice_id:
            doc["stripe_invoice_id"] = stripe_invoice_id
        if stripe_charge_id:
            doc["stripe_charge_id"] = stripe_charge_id
        if stripe_payment_intent_id:
            doc["stripe_payment_intent_id"] = stripe_payment_intent_id
        if cost_pence is not None:
            doc["cost_pence"] = cost_pence
        try:
            await db.payments.insert_one(doc)
        except DuplicateKeyError:
            pass  # idempotent: same event already recorded
    
    def _extract_safe_data(self, event: Dict) -> Dict:
        """Extract safe subset of event data for logging (no secrets)."""
        return {
            "id": event.get("id"),
            "type": event.get("type"),
            "created": event.get("created"),
            "object_id": event.get("data", {}).get("object", {}).get("id"),
            "object_type": event.get("data", {}).get("object", {}).get("object"),
        }


PROVISIONING_BACKGROUND_TIMEOUT_SECONDS = 300  # 5 minutes hard timeout

async def _run_provisioning_after_webhook(job_id: str) -> None:
    """Background task: run one provisioning job after webhook (no separate worker required)."""
    import asyncio
    try:
        from services.provisioning_runner import run_provisioning_job
        await asyncio.wait_for(
            run_provisioning_job(job_id),
            timeout=PROVISIONING_BACKGROUND_TIMEOUT_SECONDS,
        )
        logger.info("Background provisioning job %s finished successfully", job_id)
    except asyncio.TimeoutError:
        logger.error(
            "Background provisioning job %s timed out after %s seconds (poller can retry)",
            job_id, PROVISIONING_BACKGROUND_TIMEOUT_SECONDS,
        )
    except Exception as e:
        logger.warning(
            "Background provisioning job %s failed: %s (poller can retry)",
            job_id, e,
            exc_info=True,
        )


# Singleton instance
stripe_webhook_service = StripeWebhookService()
