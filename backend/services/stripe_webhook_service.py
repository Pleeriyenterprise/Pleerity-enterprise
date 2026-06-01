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
- invoice.paid and invoice.payment_succeeded (same handler; renewal success, dunning clear)
- invoice.payment_failed (grace window, dunning)
- charge.refunded (normalized payment status = refunded)

Stripe customer invoice emails (Dashboard → email settings): if “Successful payments” / invoice
receipts are enabled for the account, customers may receive Stripe’s own receipt in addition to
Pleerity ``SUBSCRIPTION_RENEWAL_PAID`` / ``SUBSCRIPTION_CONFIRMED``. Prefer turning Stripe’s
duplicate subscription-invoice emails off when Pleerity-branded receipts are authoritative.
"""
import html
import stripe
from pymongo.errors import DuplicateKeyError
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from database import database
from services.plan_registry import plan_registry, PlanCode, EntitlementStatus
from services.billing_period_utils import (
    billing_period_from_stripe_invoice_dict,
    coerce_any_timestamp_to_utc_datetime,
    period_end_from_stripe_subscription_dict,
    period_start_from_stripe_subscription_dict,
    period_start_from_stripe_unix,
    normalize_stored_period_end_for_api,
)
from services.billing_stripe_sync_service import (
    retrieve_stripe_subscription_dict,
    persist_subscription_billing_from_stripe,
    stripe_subscription_to_dict,
)
from services.stripe_mode_containment_service import billing_mode_fields_for_write
from services.subscription_lifecycle_service import (
    sync_subscription_lifecycle,
    grace_period_days,
    build_renewal_email_context,
)
from services.security_monitoring_service import record_security_event
from utils.audit import create_audit_log
from services.billing_audit_normalization import normalized_billing_audit_metadata
from services.billing_reconciliation_service import (
    clear_billing_reconciliation_needed,
    mark_billing_reconciliation_needed,
)
from models import AuditAction, ProvisioningJob, ProvisioningJobStatus, UserRole

logger = logging.getLogger(__name__)

# Recurring paid invoices (exclude subscription_create — initial checkout uses SUBSCRIPTION_CONFIRMED).
SUBSCRIPTION_RENEWAL_RECEIPT_BILLING_REASONS = frozenset({"subscription_cycle", "subscription_update"})


def _extract_successful_invoice_payment_fields(
    invoice: Dict[str, Any],
    *,
    source_event_id: Optional[Any] = None,
    source_event_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist last successful charge metadata from a paid Stripe invoice (subscription)."""
    out: Dict[str, Any] = {}
    st = invoice.get("status_transitions") or {}
    paid_at = st.get("paid_at")
    try:
        if paid_at:
            out["last_payment_at"] = datetime.fromtimestamp(int(paid_at), tz=timezone.utc)
        elif invoice.get("created"):
            out["last_payment_at"] = datetime.fromtimestamp(int(invoice["created"]), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        pass
    try:
        out["last_payment_amount_pence"] = int(invoice.get("amount_paid") or 0)
    except (TypeError, ValueError):
        out["last_payment_amount_pence"] = 0
    out["last_payment_status"] = "paid"
    inv_id = (invoice.get("id") or "").strip()
    inv_num = (invoice.get("number") or "").strip()
    if inv_num:
        out["last_payment_invoice_number"] = inv_num
    if inv_id:
        out["last_payment_stripe_invoice_id"] = inv_id
        out["latest_invoice_id"] = inv_id
    icur = invoice.get("currency")
    if icur:
        try:
            out["last_payment_currency"] = str(icur).lower().strip()
        except Exception:
            pass
    sie = str(source_event_id).strip() if source_event_id else ""
    if sie:
        out["last_payment_source_event_id"] = sie
    setype = str(source_event_type or "").strip()
    if setype:
        out["last_payment_source_event_type"] = setype
    nxt = invoice.get("next_payment_attempt")
    try:
        if nxt:
            out["stripe_next_payment_attempt_at"] = datetime.fromtimestamp(int(nxt), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        pass
    return out


from services.stripe_mode_authority import (
    StripeObjectModeMismatchError,
    assert_stripe_object_mode,
    configure_stripe_sdk,
    get_stripe_mode,
    resolve_webhook_secret,
)

try:
    configure_stripe_sdk()
except Exception as _wh_stripe_init:
    logger.warning("Stripe webhook service: SDK not configured at import: %s", _wh_stripe_init)


def _get_webhook_secret() -> str:
    return resolve_webhook_secret()


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
        # Step 1: Verify signature (mode-specific secret from STRIPE_MODE authority)
        webhook_secret = _get_webhook_secret()
        try:
            if webhook_secret:
                event = stripe.Webhook.construct_event(
                    payload, signature, webhook_secret
                )
                try:
                    mode = get_stripe_mode()
                    ev_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
                    assert_stripe_object_mode(ev_dict, expected_mode=mode, object_type="webhook event")
                except StripeObjectModeMismatchError as mode_err:
                    logger.error("Stripe webhook livemode mismatch: %s", mode_err)
                    return False, "Webhook mode mismatch", {"error": str(mode_err)}
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
        deployment_mode = get_stripe_mode()
        event_record = {
            "event_id": event_id,
            "type": event_type,
            "livemode": event.get("livemode"),
            "environment_source": deployment_mode,
            "event_verification_status": "webhook_livemode_authoritative",
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

            cid_touch = result.get("client_id")
            if cid_touch:
                try:
                    now_touch = datetime.now(timezone.utc)
                    await db.client_billing.update_one(
                        {"client_id": cid_touch},
                        {
                            "$set": {
                                "stripe_webhook_last_received_at": now_touch,
                                "stripe_webhook_last_event_type": event_type,
                                "updated_at": now_touch,
                            },
                        },
                    )
                except Exception as touch_err:
                    logger.warning("stripe_webhook_last_received touch failed client_id=%s: %s", cid_touch, touch_err)

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
                actor_role=UserRole.SYSTEM,
                metadata={
                    "action_type": "STRIPE_EVENT_FAILED",
                    "event_id": event_id,
                    "event_type": event_type,
                    "error": str(e),
                    **normalized_billing_audit_metadata(
                        machine_event_type="billing.webhook.failed",
                        human_label="Stripe webhook processing failed",
                        severity="high",
                        actor_type="system",
                        stripe_invoice_id=(event.get("data", {}).get("object", {}) or {}).get("id"),
                        support_explanation="Stripe webhook failed and should be retried.",
                        occurred_at=datetime.now(timezone.utc),
                        correlation_id=event_id,
                    ),
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
            "invoice.payment_succeeded": self._handle_invoice_paid,
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
        agreement_pdf_bytes: Optional[bytes] = None
        agreement_pdf_filename: Optional[str] = None
        agreement_issued_id_for_email: Optional[str] = None
        checkout_session_id = session.get("id")
        if hasattr(session, "to_dict"):
            session = session.to_dict()
        elif not isinstance(session, dict):
            session = dict(session)
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

        if checkout_session_id and (
            not session.get("line_items") or not (session.get("line_items") or {}).get("data")
        ):
            try:
                expanded = stripe.checkout.Session.retrieve(
                    checkout_session_id,
                    expand=["line_items.data.price"],
                )
                session = expanded.to_dict() if hasattr(expanded, "to_dict") else dict(expanded)
            except Exception as ex:
                logger.warning("checkout session line_items expand failed: %s", ex)

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

        from services.billing_line_normalization import build_checkout_pdf_lines_and_breakdown

        _, checkout_breakdown_db = build_checkout_pdf_lines_and_breakdown(
            session, plan_code, billing_period_note=None
        )

        # Onboarding (setup) fee — waived pilots must not infer paid from missing line_items
        from services.pilot_onboarding_fee import (
            onboarding_fields_for_waived_client,
            onboarding_policy_from_client,
            resolve_webhook_onboarding_fee,
        )

        expected_onboarding_price = plan_registry.get_stripe_price_ids(plan_code).get("onboarding_price_id")
        client_before = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        session_md_for_onb = session.get("metadata") or metadata or {}
        onboarding_fee_paid, setup_fee_amount_cents, setup_fee_invoice_id = resolve_webhook_onboarding_fee(
            session_metadata=session_md_for_onb,
            client=client_before,
            session_line_items=session.get("line_items"),
            expected_onboarding_price_id=expected_onboarding_price,
        )
        if onboarding_fee_paid and session.get("invoice") and setup_fee_amount_cents:
            setup_fee_invoice_id = (
                session["invoice"]
                if isinstance(session["invoice"], str)
                else (session["invoice"] or {}).get("id")
            )
        from models.pilot_invite import PilotOnboardingFeePolicy
        from services.pilot_onboarding_fee import onboarding_policy_from_invite

        onb_policy = onboarding_policy_from_client(client_before)
        if not onb_policy and session_md_for_onb.get("onboarding_fee_policy"):
            onb_policy = onboarding_policy_from_invite(
                {
                    "onboarding_fee_policy": session_md_for_onb.get("onboarding_fee_policy"),
                    "waive_onboarding_fee": str(session_md_for_onb.get("onboarding_fee_waived") or "").lower()
                    in ("true", "1", "yes"),
                    "program_type": session_md_for_onb.get("program_type"),
                }
            )
        elif not onb_policy and str(session_md_for_onb.get("program_type") or "").upper() == "FOUNDING_PILOT":
            onb_policy = onboarding_policy_from_invite(
                {
                    "program_type": "FOUNDING_PILOT",
                    "waive_onboarding_fee": str(session_md_for_onb.get("onboarding_fee_waived") or "").lower()
                    in ("true", "1", "yes"),
                    "onboarding_fee_policy": session_md_for_onb.get("onboarding_fee_policy"),
                }
            )
        onb_client_fields: Dict[str, Any] = {}
        if onb_policy in (PilotOnboardingFeePolicy.WAIVED, PilotOnboardingFeePolicy.DEFERRED):
            onb_client_fields = onboarding_fields_for_waived_client(
                policy=onb_policy,
                plan_code=plan_code.value,
                reason=session_md_for_onb.get("onboarding_fee_waiver_reason"),
            )
        
        # Map subscription status to entitlement
        subscription_status = subscription.get("status", "incomplete")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(subscription_status)
        
        # Upsert ClientBilling record; increment entitlements_version (Stripe is source of truth)
        _sub_period = stripe_subscription_to_dict(subscription)
        period_end_dt = period_end_from_stripe_subscription_dict(_sub_period)
        period_start_dt = period_start_from_stripe_subscription_dict(_sub_period)
        anchor_dt = period_start_from_stripe_unix(subscription.get("billing_cycle_anchor"))
        now_sync = datetime.now(timezone.utc)
        event_livemode = event.get("livemode")
        checkout_mode = "live" if event_livemode else "test" if event_livemode is False else None
        billing_record = {
            "client_id": client_id,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            **billing_mode_fields_for_write(checkout_mode),
            "current_plan_code": plan_code.value,
            "subscription_status": subscription_status.upper(),
            "entitlement_status": entitlement_status.value,
            "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
            "onboarding_fee_paid": onboarding_fee_paid,
            "latest_invoice_id": subscription.get("latest_invoice"),
            "updated_at": now_sync,
            "billing_last_synced_at": now_sync,
            "billing_sync_state": "ok" if period_end_dt else "missing_period_end",
        }
        if not period_end_dt:
            logger.warning(
                "checkout webhook: current_period_end missing after Subscription.retrieve client_id=%s subscription_id=%s",
                client_id,
                stripe_subscription_id,
            )
        if period_end_dt:
            billing_record["current_period_end"] = period_end_dt
        if period_start_dt:
            billing_record["current_period_start"] = period_start_dt
        if anchor_dt:
            billing_record["billing_cycle_anchor"] = anchor_dt
        if setup_fee_amount_cents is not None:
            billing_record["setup_fee_amount_cents"] = setup_fee_amount_cents
        if setup_fee_invoice_id:
            billing_record["setup_fee_invoice_id"] = setup_fee_invoice_id
        if onb_client_fields:
            billing_record.update(
                {k: v for k, v in onb_client_fields.items() if k.startswith("onboarding_fee")}
            )
        if checkout_breakdown_db:
            billing_record["last_checkout_billing_breakdown"] = checkout_breakdown_db
        sub_amt = sum(x["amount"] for x in checkout_breakdown_db if x.get("type") == "subscription")
        if sub_amt:
            billing_record["subscription_amount_pence"] = sub_amt
        setup_part = sum(x["amount"] for x in checkout_breakdown_db if x.get("type") == "setup_fee")
        if setup_part:
            billing_record["setup_fee_amount_pence"] = setup_part
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
        unset_merged = dict(dunning_unset)
        # Do not clear period boundaries when Stripe omits them on this payload — keep last known values.
        checkout_billing_update["$unset"] = unset_merged
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
        client_set: Dict[str, Any] = {
            "subscription_status": (subscription_status or "unknown").upper(),
            "billing_plan": plan_code.value,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "entitlement_status": entitlement_status.value,
            "entitlements_version": entitlements_version,
        }
        if onb_client_fields:
            client_set.update(onb_client_fields)
        await db.clients.update_one({"client_id": client_id}, {"$set": client_set})

        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            logger.warning("sync_subscription_lifecycle after checkout failed: %s", lc_err)

        # Founding pilot: tag client and register pending redemption (usage counted after provisioning).
        session_md = session.get("metadata") or {}
        invite_code_meta = (session_md.get("invite_code") or "").strip()
        program_type_meta = (session_md.get("program_type") or "").strip()
        if invite_code_meta or program_type_meta == "FOUNDING_PILOT":
            try:
                from services.pilot_invite_service import (
                    COL_CODES,
                    apply_pilot_tags_to_client,
                    normalize_invite_code,
                    register_pending_redemption,
                )

                normalized_invite = normalize_invite_code(invite_code_meta) if invite_code_meta else ""
                invite_doc = None
                if normalized_invite:
                    invite_doc = await db[COL_CODES].find_one({"code": normalized_invite}, {"_id": 0})
                if invite_doc:
                    pm_raw = session.get("payment_method")
                    pm_id = pm_raw if isinstance(pm_raw, str) else (pm_raw or {}).get("id") if isinstance(pm_raw, dict) else None
                    pm_id = str(pm_id or "").strip() or None
                    cd = session.get("customer_details") or {}
                    redemption_email = None
                    if isinstance(cd, dict):
                        redemption_email = cd.get("email")
                    redemption_email = str(redemption_email or session.get("customer_email") or "").strip() or None
                    registered = await register_pending_redemption(
                        checkout_session_id=checkout_session_id or "",
                        client_id=client_id,
                        invite_doc=invite_doc,
                        stripe_event_id=event.get("id") if event else None,
                        stripe_subscription_id=stripe_subscription_id,
                        redemption_email=redemption_email,
                        stripe_payment_method_id=pm_id,
                        plan_code=plan_code.value,
                    )
                    if registered:
                        await apply_pilot_tags_to_client(
                            client_id=client_id,
                            invite_doc=invite_doc,
                            plan_code=plan_code.value,
                            checkout_session_id=checkout_session_id,
                            stripe_subscription_id=stripe_subscription_id,
                            stripe_event_id=event.get("id") if event else None,
                        )
                    try:
                        from services.pilot_lifecycle_service import sync_stripe_payment_method_status

                        await sync_stripe_payment_method_status(
                            client_id, stripe_customer_id=stripe_customer_id
                        )
                    except Exception as pm_ex:
                        logger.warning("Pilot PM sync after checkout failed client_id=%s: %s", client_id, pm_ex)
                else:
                    logger.error(
                        "Pilot checkout metadata present but invite not found client_id=%s invite_code=%s session=%s",
                        client_id,
                        invite_code_meta,
                        checkout_session_id,
                    )
            except Exception as pilot_ex:
                logger.exception(
                    "Pilot invite webhook tagging failed client_id=%s session=%s: %s",
                    client_id,
                    checkout_session_id,
                    pilot_ex,
                )

        # CRN: generate on payment confirmation only (idempotent; once set, never changed)
        client_crn = None
        try:
            from services.crn_service import ensure_client_crn
            client_crn = await ensure_client_crn(client_id, stripe_event_id=event.get("id") if event else None)
        except Exception as crn_err:
            logger.error(f"CRN assignment failed for {client_id}: {crn_err}")
            raise

        # Service agreement issuance (accepted version; immutable PDF) — not tied to provisioning.
        session_md = session.get("metadata") or {}
        acc_id = (session_md.get("acceptance_id") or "").strip()
        ver_meta = (session_md.get("agreement_template_version_id") or "").strip()
        if not acc_id or not ver_meta:
            try:
                await create_audit_log(
                    action=AuditAction.AGREEMENT_ISSUANCE_SKIPPED_LEGACY_CHECKOUT,
                    actor_role=UserRole.SYSTEM,
                    client_id=client_id,
                    metadata={"checkout_session_id": checkout_session_id, "reason": "missing_acceptance_metadata"},
                )
            except Exception:
                pass
        else:
            try:
                from services.agreement_issuance_service import (
                    issue_agreement_for_subscription_payment,
                    load_issued_pdf_bytes,
                )

                ok_ag, err_ag, issued_doc = await issue_agreement_for_subscription_payment(
                    client_id=client_id,
                    acceptance_id=acc_id,
                    template_version_id_from_metadata=ver_meta,
                    payment_reference=checkout_session_id or (session.get("id") or ""),
                    stripe_event_id=event.get("id") if event else None,
                    crn=client_crn,
                )
                if ok_ag and issued_doc:
                    iid = issued_doc.get("issued_id")
                    fn = (issued_doc.get("document_files") or {}).get("pdf_filename") or f"agreement_{iid}.pdf"
                    if iid:
                        agreement_issued_id_for_email = str(iid)
                        agreement_pdf_bytes = await load_issued_pdf_bytes(str(iid), client_id)
                        agreement_pdf_filename = str(fn)
                        try:
                            await create_audit_log(
                                action=AuditAction.AGREEMENT_EMAIL_ATTACHMENT_ADDED,
                                actor_role=UserRole.SYSTEM,
                                client_id=client_id,
                                resource_type="issued_agreement",
                                resource_id=str(iid),
                                metadata={"checkout_session_id": checkout_session_id, "filename": agreement_pdf_filename},
                            )
                        except Exception:
                            pass
                elif err_ag:
                    logger.error(
                        "Agreement issuance failed client_id=%s acceptance_id=%s err=%s",
                        client_id,
                        acc_id,
                        err_ag,
                    )
            except Exception as ag_ex:
                logger.exception("Agreement issuance raised client_id=%s acceptance_id=%s", client_id, acc_id)

        # Provisioning jobs: persist state only; return 200 quickly. Poller processes PAYMENT_CONFIRMED jobs.
        checkout_session_id = session.get("id") or checkout_session_id
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
            actor_role=UserRole.SYSTEM,
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
            actor_role=UserRole.SYSTEM,
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": "checkout.session.completed",
                "plan_code": plan_code.value,
                "subscription_status": subscription_status,
                "entitlement_status": entitlement_status.value,
                "provisioning_triggered": provisioning_triggered,
                "onboarding_fee_paid": onboarding_fee_paid,
                **normalized_billing_audit_metadata(
                    machine_event_type="billing.webhook.checkout_completed",
                    human_label="Subscription checkout completed",
                    severity="info",
                    actor_type="system",
                    client_id=client_id,
                    stripe_customer_id=str(stripe_customer_id or ""),
                    stripe_subscription_id=str(stripe_subscription_id or ""),
                    stripe_checkout_session_id=str(checkout_session_id or ""),
                    support_explanation="Stripe checkout completion updated billing and entitlement state.",
                    occurred_at=datetime.now(timezone.utc),
                    correlation_id=(event or {}).get("id"),
                ),
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
            from services.pilot_commercial_truth import (
                build_payment_confirmation_pricing_line,
                build_pilot_offer_summary,
                commercial_context_from_client,
            )

            client_full = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
            pilot_ctx = commercial_context_from_client(client_full or {}, plan_code=plan_code.value)
            amount_total_cents = session.get("amount_total")
            currency = (session.get("currency") or "gbp").strip().upper()
            amt_display = build_payment_confirmation_pricing_line(
                pilot_ctx, amount_total_cents=amount_total_cents
            )
            if amount_total_cents is not None and not pilot_ctx:
                sym = "£" if currency == "GBP" else ""
                amt_display = f"{sym}{amount_total_cents / 100:.2f}" + ("" if sym else f" {currency}")
            elif not pilot_ctx:
                amt_display = (
                    f"£{plan_def.get('monthly_price', 0):.2f}/month + "
                    f"£{plan_def.get('onboarding_fee', 0):.2f} setup"
                )
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
                "pilot_offer_line": build_pilot_offer_summary(pilot_ctx) if pilot_ctx else "",
                "payment_date_display": payment_date_display,
                "reference_display": reference_display,
                "support_email": support_email,
                "customer_reference": (client_for_email or {}).get("customer_reference") or "",
                "subject": "Payment received — Compliance Vault Pro",
            }
            subscription_invoice_number = None
            try:
                _sub_pdf = stripe_subscription_to_dict(subscription)
                period_start = period_start_from_stripe_subscription_dict(_sub_pdf)
                period_end = period_end_from_stripe_subscription_dict(_sub_pdf)
                ok_pdf, pdf_sub, inv_no, pdf_err = await ensure_subscription_checkout_invoice_pdf(
                    client_id=client_id,
                    checkout_session_id=checkout_session_id or "",
                    session=session,
                    customer_name=client_name or "Valued Customer",
                    customer_email=client_email_for_pdf,
                    plan_code=plan_code,
                    billing_period_start=period_start,
                    billing_period_end=period_end,
                    setup_fee_amount_cents=setup_fee_amount_cents,
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

            if agreement_pdf_bytes and agreement_pdf_filename:
                if not sub_ctx.get("attachments"):
                    sub_ctx["attachments"] = []
                sub_ctx["attachments"].append(
                    {
                        "Name": agreement_pdf_filename,
                        "Content": base64.b64encode(agreement_pdf_bytes).decode("utf-8"),
                        "ContentType": "application/pdf",
                    }
                )

            result = await notification_orchestrator.send(
                template_key="SUBSCRIPTION_CONFIRMED",
                client_id=client_id,
                context=sub_ctx,
                idempotency_key=idempotency_key,
                event_type="checkout.session.completed",
            )
            if result.outcome in ("sent", "duplicate_ignored") and sub_ctx.get("attachments"):
                if subscription_invoice_number or agreement_issued_id_for_email:
                    try:
                        att_meta: Dict[str, Any] = {
                            "source": "cvp_subscription_checkout",
                            "template_key": "SUBSCRIPTION_CONFIRMED",
                        }
                        if subscription_invoice_number:
                            att_meta["invoice_number"] = subscription_invoice_number
                        if agreement_issued_id_for_email:
                            att_meta["issued_agreement_id"] = agreement_issued_id_for_email
                        await create_audit_log(
                            action=AuditAction.ORDER_RECEIPT_ATTACHED_TO_EMAIL,
                            client_id=client_id,
                            metadata=att_meta,
                        )
                    except Exception:
                        pass
            if result.outcome in ("sent", "duplicate_ignored") and agreement_issued_id_for_email:
                try:
                    from services.agreement_issuance_service import mark_issued_agreement_email_delivered

                    await mark_issued_agreement_email_delivered(
                        issued_id=agreement_issued_id_for_email,
                        client_id=client_id,
                        template_key="SUBSCRIPTION_CONFIRMED",
                        stripe_event_id=event_id,
                        message_id=getattr(result, "message_id", None),
                    )
                except Exception as mark_em:
                    logger.warning(
                        "mark_issued_agreement_email_delivered failed issued_id=%s client_id=%s: %s",
                        agreement_issued_id_for_email,
                        client_id,
                        mark_em,
                    )
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

        # Paid checkout: persist canonical ledger + last-payment fields when Stripe invoice is confirmed paid.
        try:
            ps_checkout = str(session.get("payment_status") or "").lower()
            if ps_checkout == "paid":
                inv_raw = session.get("invoice")
                inv_ck: Optional[str] = None
                if isinstance(inv_raw, dict):
                    inv_ck = str(inv_raw.get("id") or "").strip()
                elif isinstance(inv_raw, str):
                    inv_ck = inv_raw.strip()
                if not inv_ck:
                    li = subscription.get("latest_invoice") if subscription is not None else None
                    if isinstance(li, dict):
                        inv_ck = str(li.get("id") or "").strip()
                    elif isinstance(li, str):
                        inv_ck = li.strip()
                if inv_ck and inv_ck.startswith("in_"):
                    inv_c = stripe.Invoice.retrieve(
                        inv_ck, expand=["lines.data.price", "payment_intent", "charge"]
                    )
                    inv_c_dict = inv_c.to_dict() if hasattr(inv_c, "to_dict") else dict(inv_c)
                    if str(inv_c_dict.get("status") or "").lower() == "paid":
                        from services.subscription_payment_ledger_service import (
                            upsert_subscription_payment_ledger_row,
                        )

                        evt_id_ck = str((event or {}).get("id") or "").strip()
                        await upsert_subscription_payment_ledger_row(
                            client_id=client_id,
                            stripe_customer_id=str(stripe_customer_id or ""),
                            stripe_subscription_id=str(stripe_subscription_id or ""),
                            invoice_dict=inv_c_dict,
                            source_event_type="checkout.session.completed",
                            source_event_id=evt_id_ck or None,
                        )
                        chk_pay = _extract_successful_invoice_payment_fields(
                            inv_c_dict,
                            source_event_id=(event or {}).get("id"),
                            source_event_type="checkout.session.completed",
                        )
                        if chk_pay:
                            chk_pay["updated_at"] = datetime.now(timezone.utc)
                            await db.client_billing.update_one(
                                {"client_id": client_id},
                                {"$set": chk_pay},
                            )
        except Exception as chk_led_err:
            logger.warning(
                "checkout payment ledger + last_payment mirror failed client_id=%s checkout=%s: %s",
                client_id,
                checkout_session_id,
                chk_led_err,
                exc_info=True,
            )

        return {
            "handled": True,
            "client_id": client_id,
            "subscription_id": stripe_subscription_id,
            "plan_code": plan_code.value,
            "entitlement_status": entitlement_status.value,
            "entitlements_version": entitlements_version,
            "provisioning_triggered": provisioning_triggered,
        }
    
    @staticmethod
    def _subscription_price_fingerprint(subscription: Dict[str, Any]) -> str:
        items = (subscription or {}).get("items") or {}
        data = items.get("data") if isinstance(items, dict) else None
        if not isinstance(data, list):
            return "no_price"
        price_ids: List[str] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            price = item.get("price")
            pid = None
            if isinstance(price, dict):
                pid = price.get("id")
            elif isinstance(price, str):
                pid = price
            if pid:
                price_ids.append(str(pid).strip())
        clean = sorted({p for p in price_ids if p})
        return "|".join(clean) if clean else "no_price"

    def _subscription_transition_key(self, subscription: Dict[str, Any]) -> str:
        stripe_subscription_id = (subscription.get("id") or "").strip()
        sub_status = str(subscription.get("status") or "").strip().lower()
        sub_period_end = subscription.get("current_period_end")
        price_fp = self._subscription_price_fingerprint(subscription)
        return f"sub_change:{stripe_subscription_id}:{sub_status}:{sub_period_end}:{price_fp}"

    async def _handle_subscription_change(self, subscription: Dict, event: Dict) -> Dict:
        """
        Handle customer.subscription.created / updated.
        
        Updates entitlements immediately on plan changes.
        """
        db = database.get_db()
        stripe_customer_id = subscription.get("customer")
        stripe_subscription_id = subscription.get("id")
        event_type = (event or {}).get("type", "customer.subscription.updated")
        transition_key = self._subscription_transition_key(subscription)
        logger.info(
            "HANDLER_START event.type=%s stripe_customer_id=%s subscription_id=%s checkout_session_id=(n/a) metadata.client_id=(from_billing) metadata.plan_code=(from_items) computed_client_id=(lookup)",
            event_type, stripe_customer_id, stripe_subscription_id,
        )

        billing = await db.client_billing.find_one(
            {"stripe_customer_id": stripe_customer_id},
            {"_id": 0},
        )
        if not billing:
            billing = await db.client_billing.find_one(
                {"stripe_subscription_id": stripe_subscription_id},
                {"_id": 0},
            )

        if not billing:
            meta = subscription.get("metadata") or {}
            cid_meta = (meta.get("client_id") or "").strip()
            client_row = None
            if cid_meta:
                client_row = await db.clients.find_one({"client_id": cid_meta}, {"_id": 0, "client_id": 1})
            if not client_row and stripe_customer_id:
                client_row = await db.clients.find_one(
                    {"stripe_customer_id": stripe_customer_id},
                    {"_id": 0, "client_id": 1},
                )
            if not client_row:
                logger.warning(
                    "No billing record and no resolvable client for stripe_customer_id=%s subscription_id=%s",
                    stripe_customer_id,
                    stripe_subscription_id,
                )
                return {"handled": False, "reason": "no_billing_record"}
            seed_client_id = client_row["client_id"]
            now_seed = datetime.now(timezone.utc)
            await db.client_billing.update_one(
                {"client_id": seed_client_id},
                {
                    "$set": {
                        "client_id": seed_client_id,
                        "stripe_customer_id": stripe_customer_id,
                        "stripe_subscription_id": stripe_subscription_id,
                        "updated_at": now_seed,
                    },
                    "$setOnInsert": {"created_at": now_seed},
                },
                upsert=True,
            )
            billing = await db.client_billing.find_one({"client_id": seed_client_id}, {"_id": 0}) or {}

        client_id = billing.get("client_id")
        if not client_id:
            logger.warning(
                "client_billing row missing client_id stripe_customer_id=%s subscription_id=%s",
                stripe_customer_id,
                stripe_subscription_id,
            )
            return {"handled": False, "reason": "no_billing_record"}
        claim = await self._claim_transition_guard(
            client_id=client_id,
            transition_key=transition_key,
            event=event,
            skip_if_seen=True,
        )
        if not claim.get("claimed"):
            logger.info(
                "Skipping duplicate/stale subscription change transition client_id=%s key=%s reason=%s",
                client_id,
                transition_key,
                claim.get("reason"),
            )
            return {"handled": True, "client_id": client_id, "subscription_id": stripe_subscription_id, "duplicate_transition": True}

        old_plan = billing.get("current_plan_code")
        old_status = billing.get("subscription_status")

        try:
            trusted = "live" if event.get("livemode") else "test"
            sub_d = await retrieve_stripe_subscription_dict(
                stripe_subscription_id,
                trusted_mode=trusted,
                client_id=client_id,
                stored_mode=billing.get("stripe_mode"),
                operation="webhook_subscription_updated",
            )
        except Exception as e:
            logger.exception(
                "subscription webhook: Stripe.Subscription.retrieve failed subscription_id=%s: %s",
                stripe_subscription_id,
                e,
            )
            raise

        summary = await persist_subscription_billing_from_stripe(
            client_id,
            sub_d,
            event_source=event_type,
            update_plan=True,
            increment_entitlements_version=1,
        )
        entitlements_version = summary["entitlements_version"]
        subscription_status = sub_d.get("status", "unknown")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(subscription_status)
        sub_status_set = "ACTIVE" if subscription_status in ("active", "trialing") else subscription_status.upper()

        pc_val = summary.get("plan_code")
        if not pc_val:
            bill_row = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0, "current_plan_code": 1})
            pc_val = (bill_row or {}).get("current_plan_code")
        if not pc_val:
            logger.error("Cannot determine plan for subscription %s after API sync", stripe_subscription_id)
            raise ValueError(f"No matching plan for subscription {stripe_subscription_id}")
        new_plan_code = plan_registry.resolve_plan_code(pc_val)
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
            actor_role=UserRole.SYSTEM,
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
            actor_role=UserRole.SYSTEM,
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
        try:
            from services.subscription_operational_bridge import on_subscription_change

            await on_subscription_change(
                client_id=client_id,
                event=event,
                old_plan=old_plan,
                new_plan=new_plan_code.value,
                old_status=old_status,
                new_status=subscription_status,
                is_upgrade=is_upgrade,
                is_downgrade=is_downgrade,
            )
        except Exception as ops_exc:
            logger.warning("subscription operational bridge subscription.change: %s", ops_exc)
        
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
        claim = await self._claim_transition_guard(
            client_id=client_id,
            transition_key=f"sub_deleted:{stripe_subscription_id}",
            event=event,
            skip_if_seen=True,
        )
        if not claim.get("claimed"):
            logger.info(
                "Skipping duplicate/stale subscription deleted transition client_id=%s sub=%s reason=%s",
                client_id,
                stripe_subscription_id,
                claim.get("reason"),
            )
            return {"handled": True, "client_id": client_id, "subscription_id": stripe_subscription_id, "duplicate_transition": True}
        
        # Update to DISABLED - DO NOT DELETE DATA
        now_del = datetime.now(timezone.utc)
        await db.client_billing.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "subscription_status": "CANCELED",
                    "entitlement_status": EntitlementStatus.DISABLED.value,
                    "canonical_entitlement_state": "CANCELLED",
                    "billing_local_change_pending": False,
                    "billing_local_change_type": "subscription_cancel",
                    "billing_sync_state": "ok",
                    "updated_at": now_del,
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
                    "canonical_entitlement_state": "CANCELLED",
                }
            }
        )

        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            await mark_billing_reconciliation_needed(
                client_id=client_id,
                reason="subscription_deleted_lifecycle_sync_failed",
                context={"error": str(lc_err)[:500]},
            )
            logger.warning("sync_subscription_lifecycle after subscription deleted failed: %s", lc_err)

        try:
            from services.pilot_invite_service import maybe_record_pilot_cancelled_before_paid

            await maybe_record_pilot_cancelled_before_paid(
                client_id=client_id,
                stripe_event_id=event.get("id") if event else None,
            )
        except Exception as pilot_cancel_ex:
            logger.warning(
                "Pilot cancelled-before-paid recording failed client_id=%s: %s",
                client_id,
                pilot_cancel_ex,
            )
        
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
            actor_role=UserRole.SYSTEM,
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_EVENT_PROCESSED",
                "event_type": "customer.subscription.deleted",
                "final_status": "CANCELED",
                "entitlement_status": EntitlementStatus.DISABLED.value,
            }
        )
        await clear_billing_reconciliation_needed(client_id=client_id, reason="subscription_deleted_synced")
        
        logger.info(
            "HANDLER_END event.type=customer.subscription.deleted client_id=%s db_updated=subscription_status=CANCELED entitlement_status=DISABLED",
            client_id,
        )
        try:
            from services.subscription_operational_bridge import on_subscription_deleted

            await on_subscription_deleted(
                client_id=client_id,
                event=event,
                stripe_subscription_id=stripe_subscription_id,
            )
        except Exception as ops_exc:
            logger.warning("subscription operational bridge subscription.deleted: %s", ops_exc)
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
        billing = await db.client_billing.find_one(
            {"stripe_customer_id": stripe_customer_id},
            {"_id": 0},
        )
        if not billing:
            billing = await db.client_billing.find_one(
                {"stripe_subscription_id": subscription_id},
                {"_id": 0},
            )
        if not billing:
            logger.warning(
                "invoice.paid: no billing record stripe_customer_id=%s subscription_id=%s",
                stripe_customer_id,
                subscription_id,
            )
            return {"handled": False, "reason": "no_billing_record"}

        client_id = billing.get("client_id")
        inv_id = (invoice.get("id") or "").strip()
        if inv_id:
            claim = await self._claim_transition_guard(
                client_id=client_id,
                transition_key=f"invoice_paid:{inv_id}",
                event=event,
                skip_if_seen=True,
            )
            if not claim.get("claimed"):
                logger.info(
                    "Skipping duplicate/stale invoice paid transition client_id=%s invoice_id=%s reason=%s",
                    client_id,
                    inv_id,
                    claim.get("reason"),
                )
                return {"handled": True, "client_id": client_id, "subscription_id": subscription_id, "duplicate_transition": True}
        old_status = billing.get("subscription_status")
        if str(old_status or "").upper() in ("CANCELED", "CANCELLED"):
            logger.info(
                "Ignoring invoice paid for cancelled subscription client_id=%s subscription_id=%s",
                client_id,
                subscription_id,
            )
            return {"handled": True, "client_id": client_id, "subscription_id": subscription_id, "ignored_cancelled": True}
        had_dunning = bool(billing.get("payment_failed_at") or billing.get("grace_period_ends_at"))

        try:
            trusted = "live" if event.get("livemode") else "test"
            sub_d = await retrieve_stripe_subscription_dict(
                subscription_id,
                trusted_mode=trusted,
                client_id=client_id,
                stored_mode=billing.get("stripe_mode") if billing else None,
                operation="webhook_invoice_paid",
            )
        except Exception as e:
            logger.exception(
                "invoice.paid: Stripe.Subscription.retrieve failed subscription_id=%s err=%s",
                subscription_id,
                e,
            )
            raise

        inv_latest = invoice.get("id")
        extra_inv: Dict[str, Any] = {}
        if inv_latest:
            extra_inv["latest_invoice_id"] = inv_latest

        await persist_subscription_billing_from_stripe(
            client_id,
            sub_d,
            event_source=event_type,
            update_plan=True,
            additional_billing_set=extra_inv if extra_inv else None,
            increment_entitlements_version=1 if had_dunning else 0,
        )

        if had_dunning:
            await db.client_billing.update_one(
                {"client_id": client_id},
                {
                    "$unset": {
                        "payment_failed_at": "",
                        "grace_period_ends_at": "",
                        "dunning_stripe_invoice_id": "",
                        "grace_mid_reminder_sent_at": "",
                        "renewal_reminder_period_key_7d": "",
                        "renewal_reminder_period_key_3d": "",
                    },
                },
            )

        new_status = sub_d.get("status", "unknown")
        entitlement_status = plan_registry.get_entitlement_status_from_subscription(new_status)
        period_end_dt = period_end_from_stripe_subscription_dict(sub_d)

        inv_d: Optional[Dict[str, Any]] = None
        renewal_breakdown: List[Dict[str, Any]] = []
        try:
            inv_id = invoice.get("id")
            if inv_id:
                inv_full = stripe.Invoice.retrieve(
                    inv_id, expand=["lines.data.price", "payment_intent", "charge"]
                )
                inv_d = inv_full.to_dict() if hasattr(inv_full, "to_dict") else dict(inv_full)
                from services.billing_line_normalization import breakdown_from_invoice_lines

                bill_pc = await db.client_billing.find_one(
                    {"client_id": client_id},
                    {"_id": 0, "current_plan_code": 1},
                )
                pc = (bill_pc or {}).get("current_plan_code")
                plan_enum = plan_registry.resolve_plan_code(pc) if pc else None
                br = breakdown_from_invoice_lines(inv_d, plan_enum)
                renewal_breakdown = br
                bset: Dict[str, Any] = {
                    "last_invoice_billing_breakdown": br,
                    "updated_at": datetime.now(timezone.utc),
                }
                sub_part = sum(x["amount"] for x in br if x.get("type") == "subscription")
                if sub_part:
                    bset["subscription_amount_pence"] = sub_part
                inv_num_stripe = (inv_d.get("number") or "").strip()
                if inv_num_stripe:
                    bset["last_payment_invoice_number"] = inv_num_stripe
                await db.client_billing.update_one({"client_id": client_id}, {"$set": bset})
        except Exception as inv_err:
            logger.warning("invoice paid: persist line breakdown failed: %s", inv_err)

        lifecycle_sync_failed = False
        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as lc_err:
            lifecycle_sync_failed = True
            await mark_billing_reconciliation_needed(
                client_id=client_id,
                reason="invoice_paid_lifecycle_sync_failed",
                context={"error": str(lc_err)[:500], "invoice_id": invoice.get("id")},
            )
            logger.warning("sync_subscription_lifecycle after invoice.paid failed: %s", lc_err)

        try:
            from services.pilot_invite_service import maybe_record_pilot_paid_transition

            await maybe_record_pilot_paid_transition(
                client_id=client_id,
                invoice=invoice,
                stripe_event_id=event.get("id") if event else None,
            )
        except Exception as pilot_paid_ex:
            logger.warning("Pilot paid transition recording failed client_id=%s: %s", client_id, pilot_paid_ex)

        merged_invoice: Dict[str, Any] = dict(invoice)
        if inv_d:
            merged_invoice = {**merged_invoice, **inv_d}
        try:
            from services.subscription_payment_ledger_service import upsert_subscription_payment_ledger_row

            await upsert_subscription_payment_ledger_row(
                client_id=client_id,
                stripe_customer_id=str(stripe_customer_id or ""),
                stripe_subscription_id=str(subscription_id or ""),
                invoice_dict=merged_invoice,
                source_event_type=event_type,
                source_event_id=str((event or {}).get("id") or ""),
            )
        except Exception as ledger_ex:
            logger.warning(
                "subscription_payment_ledger upsert failed client_id=%s invoice_id=%s: %s",
                client_id,
                merged_invoice.get("id"),
                ledger_ex,
                exc_info=True,
            )

        pay_set = _extract_successful_invoice_payment_fields(
            merged_invoice,
            source_event_id=(event or {}).get("id"),
            source_event_type=event_type,
        )
        now_p = datetime.now(timezone.utc)
        if pay_set:
            pay_set["updated_at"] = now_p
            if inv_d:
                num_iv = (inv_d.get("number") or "").strip()
                if num_iv and not pay_set.get("last_payment_invoice_number"):
                    pay_set["last_payment_invoice_number"] = num_iv
        inv_unset = {"open_invoice_id": "", "open_invoice_status": "", "last_invoice_failure_message": ""}
        inv_upd: Dict[str, Any] = {"$unset": inv_unset}
        if pay_set:
            inv_upd["$set"] = pay_set
        await db.client_billing.update_one({"client_id": client_id}, inv_upd)

        billing_final = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0, "entitlement_status": 1})
        final_ent = (billing_final or {}).get("entitlement_status") or entitlement_status.value

        recovered = old_status in ("PAST_DUE", "UNPAID") and new_status == "active"

        inv_stable = (invoice.get("id") or "").strip()
        billing_reason = (invoice.get("billing_reason") or "").strip()
        amount_pence = int(invoice.get("amount_paid") or 0)
        if (
            new_status == "active"
            and billing_reason in SUBSCRIPTION_RENEWAL_RECEIPT_BILLING_REASONS
            and amount_pence > 0
            and inv_stable
        ):
            try:
                import base64

                from services.notification_orchestrator import notification_orchestrator
                from services.order_receipt_service import (
                    CVP_SUBSCRIPTION_RENEWAL_RECEIPTS,
                    persist_cvp_subscription_renewal_receipt,
                    read_receipt_pdf_bytes,
                )
                from utils.public_app_url import get_public_app_url

                src_inv: Dict[str, Any] = inv_d if inv_d else dict(invoice)
                bp_start, bp_end = billing_period_from_stripe_invoice_dict(src_inv)
                st_tr = (src_inv.get("status_transitions") or {}) or {}
                paid_raw = st_tr.get("paid_at") or (invoice.get("status_transitions") or {}).get("paid_at")
                if paid_raw:
                    try:
                        paid_at_dt = datetime.fromtimestamp(int(paid_raw), tz=timezone.utc)
                    except (TypeError, ValueError, OSError):
                        paid_at_dt = now_p
                else:
                    paid_at_dt = now_p

                bill_pc2 = await db.client_billing.find_one(
                    {"client_id": client_id},
                    {"_id": 0, "current_plan_code": 1},
                )
                pc2 = (bill_pc2 or {}).get("current_plan_code")
                plan_enum2 = plan_registry.resolve_plan_code(pc2) if pc2 else None
                plan_def2 = plan_registry.get_plan(plan_enum2) if plan_enum2 else {}
                plan_display = plan_def2.get("name") or (plan_enum2.value if plan_enum2 else "Compliance Vault Pro")

                client_row_em = await db.clients.find_one(
                    {"client_id": client_id},
                    {
                        "_id": 0,
                        "contact_name": 1,
                        "full_name": 1,
                        "email": 1,
                        "contact_email": 1,
                        "customer_reference": 1,
                    },
                )
                client_name = (
                    (client_row_em or {}).get("contact_name")
                    or (client_row_em or {}).get("full_name")
                    or "Valued Customer"
                )
                client_email_pdf = (
                    (client_row_em or {}).get("email") or (client_row_em or {}).get("contact_email") or ""
                ).strip()

                cur_l = (invoice.get("currency") or "gbp").lower()
                sym = "£" if cur_l == "gbp" else ""
                amt_display = f"{sym}{amount_pence / 100:.2f}" + ("" if sym else f" {cur_l.upper()}")
                hosted = (src_inv.get("hosted_invoice_url") or "").strip()

                ok_p, p_err, _gfs = await persist_cvp_subscription_renewal_receipt(
                    client_id=client_id,
                    stripe_invoice_id=inv_stable,
                    stripe_invoice_dict=src_inv,
                    pleerity_invoice_number=None,
                    paid_at=paid_at_dt,
                    billing_period_start=bp_start,
                    billing_period_end=bp_end,
                    amount_total_pence=amount_pence,
                    currency=cur_l,
                    hosted_invoice_url=hosted or None,
                    billing_breakdown=renewal_breakdown,
                    plan_code=plan_enum2,
                    customer_name=str(client_name),
                    customer_email=client_email_pdf,
                    billing_reason=billing_reason,
                )
                if not ok_p:
                    logger.warning(
                        "renewal receipt persist failed client_id=%s inv=%s: %s",
                        client_id,
                        inv_stable,
                        p_err,
                    )

                doc_after = await db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS].find_one({"_id": inv_stable})
                inv_no_out = (doc_after or {}).get("invoice_number") or ""

                period_fmt = "%d %b %Y"
                bp_display = ""
                if bp_start and bp_end:
                    bp_display = f"{bp_start.strftime(period_fmt)} – {bp_end.strftime(period_fmt)}"

                cpe_next = period_end_dt or normalize_stored_period_end_for_api(billing.get("current_period_end"))
                next_ren_display = ""
                if cpe_next:
                    if hasattr(cpe_next, "strftime"):
                        next_ren_display = cpe_next.strftime("%d %B %Y")
                    else:
                        next_ren_display = str(cpe_next)[:10]

                base_url = get_public_app_url(for_email_links=False)
                support_email = (os.getenv("SUPPORT_EMAIL") or "info@pleerityenterprise.co.uk").strip()
                event_id = (event or {}).get("id", "")
                idempotency_key = (
                    f"{inv_stable}_SUBSCRIPTION_RENEWAL_PAID"
                    if inv_stable
                    else (f"{event_id}_SUBSCRIPTION_RENEWAL_PAID" if event_id else None)
                )

                stripe_num = (src_inv.get("number") or invoice.get("number") or "").strip()
                ref_lines = f"{inv_stable} · #{stripe_num}" if stripe_num else inv_stable

                pdf_attach: List[Dict[str, str]] = []
                pdf_bytes_out = None
                if doc_after and doc_after.get("gridfs_id"):
                    pdf_bytes_out = await read_receipt_pdf_bytes(str(doc_after["gridfs_id"]))
                if pdf_bytes_out and inv_no_out:
                    pdf_attach = [
                        {
                            "Name": f"{inv_no_out}.pdf",
                            "Content": base64.b64encode(pdf_bytes_out).decode("utf-8"),
                            "ContentType": "application/pdf",
                        }
                    ]

                next_steps_parts = [
                    "<p>Your subscription remains active. Next billing date: "
                    f"<strong>{html.escape(next_ren_display or 'see Billing')}</strong>.</p>"
                ]
                if hosted:
                    next_steps_parts.append(
                        "<p>Official Stripe invoice / PDF: "
                        f"<a href=\"{html.escape(hosted)}\" style=\"color:#00B8A9;\">View hosted invoice</a></p>"
                    )
                if not pdf_bytes_out and not hosted:
                    next_steps_parts.append(
                        "<p>Your Pleerity receipt is on file in Billing; PDF generation will retry if it is not ready yet.</p>"
                    )
                next_steps_parts.append(
                    "<p>You can review invoices and payment methods any time from Billing.</p>"
                )
                next_steps_html = "".join(next_steps_parts)
                next_steps_text = (
                    f"Your subscription remains active. Next billing date: {next_ren_display or 'see Billing'}."
                )
                if hosted:
                    next_steps_text += f" Official Stripe invoice: {hosted}"
                next_steps_text += " You can review invoices and payment methods from Billing in the portal."

                ctx: Dict[str, Any] = {
                    "payment_receipt_layout": "structured",
                    "receipt_kind": "subscription_renewal",
                    "client_name": client_name,
                    "plan_name": plan_display,
                    "amount_display": amt_display,
                    "payment_date_display": paid_at_dt.strftime("%d %B %Y %H:%M UTC"),
                    "reference_display": ref_lines[:220],
                    "stripe_invoice_id_display": inv_stable,
                    "stripe_invoice_number_display": stripe_num or None,
                    "payment_status_display": "Paid",
                    "billing_period_display": bp_display or None,
                    "next_renewal_display": next_ren_display or None,
                    "hosted_invoice_url": hosted or None,
                    "next_steps_html": next_steps_html,
                    "next_steps_text": next_steps_text,
                    "receipt_cta_label": "Open Billing",
                    "receipt_cta_url": f"{base_url}/settings/billing",
                    "support_email": support_email,
                    "customer_reference": (client_row_em or {}).get("customer_reference") or "",
                    "subject": "Subscription renewed — payment confirmation",
                }
                if pdf_attach:
                    ctx["attachments"] = pdf_attach

                result_re = await notification_orchestrator.send(
                    template_key="SUBSCRIPTION_RENEWAL_PAID",
                    client_id=client_id,
                    context=ctx,
                    idempotency_key=idempotency_key,
                    event_type=event_type,
                )
                if result_re.outcome in ("sent", "duplicate_ignored") and doc_after:
                    await db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS].update_one(
                        {"_id": inv_stable},
                        {"$set": {"receipt_email_sent_at": now_p}},
                    )
            except Exception as mail_err:
                logger.warning(
                    "SUBSCRIPTION_RENEWAL_PAID pipeline failed (non-blocking): %s",
                    mail_err,
                    exc_info=True,
                )

        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.SYSTEM,
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
            charge_raw = merged_invoice.get("charge")
            charge_id = charge_raw.get("id") if isinstance(charge_raw, dict) else charge_raw
            pi_raw = merged_invoice.get("payment_intent")
            pi_resolve = pi_raw.get("id") if isinstance(pi_raw, dict) else pi_raw
            stripe_pi = str(pi_resolve).strip() if isinstance(pi_resolve, str) and pi_resolve.strip() else None
            await self._insert_payment(
                client_id=client_id,
                stripe_event_id=payment_row_key,
                amount=merged_invoice.get("amount_paid") or 0,
                currency=(merged_invoice.get("currency") or "gbp").lower(),
                type="subscription",
                status="paid",
                stripe_invoice_id=merged_invoice.get("id"),
                stripe_charge_id=charge_id,
                stripe_payment_intent_id=stripe_pi,
            )
        billing_ops_row = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_reconciliation_needed": 1},
        )
        if (billing_ops_row or {}).get("billing_reconciliation_needed"):
            lifecycle_sync_failed = True
        try:
            from services.subscription_operational_bridge import on_invoice_paid

            await on_invoice_paid(
                client_id=client_id,
                invoice=merged_invoice if merged_invoice else invoice,
                event=event,
                old_status=old_status,
                new_status=new_status,
                recovered=recovered,
                lifecycle_sync_failed=lifecycle_sync_failed,
            )
        except Exception as ops_exc:
            logger.warning("subscription operational bridge invoice.paid: %s", ops_exc)
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
            billing = await db.client_billing.find_one(
                {"stripe_subscription_id": subscription_id},
                {"_id": 0}
            )
        if not billing:
            logger.warning(
                "No billing record for payment_failed customer=%s subscription=%s",
                stripe_customer_id,
                subscription_id,
            )
            return {"handled": False, "reason": "no_billing_record"}
        client_id = billing.get("client_id")
        if str(billing.get("subscription_status") or "").upper() in ("CANCELED", "CANCELLED"):
            logger.info(
                "Ignoring payment_failed for cancelled subscription client_id=%s subscription_id=%s",
                client_id,
                subscription_id,
            )
            return {"handled": True, "client_id": client_id, "subscription_id": subscription_id, "ignored_cancelled": True}
        inv_id = (invoice.get("id") or "").strip()
        if inv_id:
            paid_invoice_id = (billing.get("last_payment_stripe_invoice_id") or "").strip()
            if paid_invoice_id and paid_invoice_id == inv_id:
                logger.info(
                    "Ignoring out-of-order payment_failed for already-paid invoice client_id=%s invoice_id=%s",
                    client_id,
                    inv_id,
                )
                return {"handled": True, "client_id": client_id, "subscription_id": subscription_id, "stale_transition": True}
            claim = await self._claim_transition_guard(
                client_id=client_id,
                transition_key=f"invoice_failed:{inv_id}",
                event=event,
                skip_if_seen=True,
            )
            if not claim.get("claimed"):
                logger.info(
                    "Skipping duplicate/stale payment_failed transition client_id=%s invoice_id=%s reason=%s",
                    client_id,
                    inv_id,
                    claim.get("reason"),
                )
                return {"handled": True, "client_id": client_id, "subscription_id": subscription_id, "duplicate_transition": True}
        
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
        npt = invoice.get("next_payment_attempt")
        npt_dt = coerce_any_timestamp_to_utc_datetime(npt)
        if npt_dt:
            billing_set["stripe_next_payment_attempt_at"] = npt_dt
        lf = invoice.get("last_finalization_error")
        if isinstance(lf, dict) and lf.get("message"):
            billing_set["last_invoice_failure_message"] = str(lf.get("message"))[:2000]
        inv_st = (invoice.get("status") or "").strip().lower()
        if inv_id:
            billing_set["open_invoice_id"] = inv_id
        if inv_st:
            billing_set["open_invoice_status"] = inv_st
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
            await mark_billing_reconciliation_needed(
                client_id=client_id,
                reason="payment_failed_lifecycle_sync_failed",
                context={"error": str(lc_err)[:500], "invoice_id": invoice.get("id")},
            )
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
            retry_dt = coerce_any_timestamp_to_utc_datetime(invoice.get("next_payment_attempt"))
            if retry_dt:
                retry_date = retry_dt.strftime("%B %d, %Y")
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
            actor_role=UserRole.SYSTEM,
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
        try:
            from services.subscription_operational_bridge import on_payment_failed

            await on_payment_failed(
                client_id=client_id,
                invoice=invoice,
                event=event,
                lifecycle_sync_failed=payment_failed_lifecycle_sync_failed,
            )
        except Exception as ops_exc:
            logger.warning("subscription operational bridge payment_failed: %s", ops_exc)
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

    @staticmethod
    def _transition_guard_field(transition_key: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in ("_", "-", ":") else "_" for ch in str(transition_key))
        return f"transition_guards.{safe}"

    async def _claim_transition_guard(
        self,
        *,
        client_id: str,
        transition_key: str,
        event: Dict,
        skip_if_seen: bool = True,
    ) -> Dict[str, Any]:
        """
        Transition-level replay guard on client_billing document.

        Used for sibling-event dedupe and out-of-order safety for identical business transitions.
        """
        db = database.get_db()
        event_id = (event or {}).get("id")
        event_type = (event or {}).get("type")
        event_created_raw = (event or {}).get("created")
        event_created_dt = coerce_any_timestamp_to_utc_datetime(event_created_raw) or datetime.now(timezone.utc)
        field = self._transition_guard_field(transition_key)
        payload = {
            "transition_key": transition_key,
            "last_event_id": event_id,
            "last_event_type": event_type,
            "last_event_created": event_created_dt,
            "updated_at": datetime.now(timezone.utc),
        }

        # First-writer wins atomically when key is absent.
        claimed_absent = await db.client_billing.update_one(
            {"client_id": client_id, field: {"$exists": False}},
            {"$set": {field: payload}},
        )
        if getattr(claimed_absent, "modified_count", 0):
            return {"claimed": True, "reason": "claimed_absent"}

        projection = {"_id": 0, field: 1}
        row = await db.client_billing.find_one({"client_id": client_id}, projection) or {}
        guard = row.get("transition_guards", {}).get(field.split(".", 1)[1]) if isinstance(row.get("transition_guards"), dict) else None
        if not isinstance(guard, dict):
            return {"claimed": False, "reason": "guard_unreadable"}

        prev_id = (guard.get("last_event_id") or "").strip()
        prev_created = coerce_any_timestamp_to_utc_datetime(guard.get("last_event_created"))
        if prev_id and event_id and prev_id == event_id:
            return {"claimed": False, "reason": "same_event_id"}
        if prev_created and event_created_dt < prev_created:
            return {"claimed": False, "reason": "older_event"}
        if skip_if_seen and prev_created and event_created_dt <= prev_created:
            return {"claimed": False, "reason": "already_seen_transition"}

        # CAS-style update: only claim if state still matches what we read.
        match_filter: Dict[str, Any] = {"client_id": client_id}
        if prev_created:
            match_filter[f"{field}.last_event_created"] = prev_created
        if prev_id:
            match_filter[f"{field}.last_event_id"] = prev_id
        claimed_newer = await db.client_billing.update_one(
            match_filter,
            {"$set": {field: payload}},
        )
        if getattr(claimed_newer, "modified_count", 0):
            return {"claimed": True, "reason": "claimed_newer_event"}
        return {"claimed": False, "reason": "race_lost"}
    
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
        if db is None:
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
