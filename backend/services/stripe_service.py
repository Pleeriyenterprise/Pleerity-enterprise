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
from datetime import datetime, timezone, timedelta

from database import database
from services.billing_period_utils import (
    normalize_stored_period_end_for_api,
    period_end_from_stripe_subscription_dict,
    period_start_from_stripe_subscription_dict,
    period_start_from_stripe_unix,
)
from services.billing_stripe_sync_service import (
    stripe_subscription_to_dict,
    sync_client_billing_from_stripe_subscription_id,
)
from services.subscription_lifecycle_service import sync_subscription_lifecycle
from services.billing_reconciliation_service import mark_billing_reconciliation_needed
from services.billing_presentation import (
    billing_status_display,
    billing_sync_visibility_note,
    build_client_billing_payload,
    build_operational_billing_narrative_lines,
    lifecycle_status_label,
    payment_grace_display_bundle,
    plan_status_display,
    renewal_date_display_from_period_end_iso,
)
from services.billing_line_normalization import normalize_stripe_invoice_lines
from services.plan_registry import (
    plan_registry, PlanCode, EntitlementStatus,
    get_stripe_price_mappings, _get_stripe_mode, StripeModeMismatchError,
)
from services.stripe_mode_authority import (
    StripeModeConfigurationError,
    configure_stripe_sdk,
    get_stripe_mode,
)
from services.stripe_mode_containment_service import (
    StripeModeDriftError,
    billing_mode_fields_for_write,
    handle_stripe_api_drift_safe,
    record_stripe_mode_drift,
    resolve_stripe_context,
    validate_portal_billing_preflight,
    validate_stripe_subscription_mode,
)
from utils.audit import create_audit_log
from models import AuditAction

logger = logging.getLogger(__name__)

CHECKOUT_CONTEXT_ONBOARDING = "onboarding"
CHECKOUT_CONTEXT_PLAN_CHANGE = "plan_change"
CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE = "recovery_plan_change"
PLAN_CHANGE_CHECKOUT_CONTEXTS = frozenset(
    {CHECKOUT_CONTEXT_PLAN_CHANGE, CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE}
)


def checkout_redirect_urls(base: str, checkout_context: str) -> tuple[str, str]:
    """Return (success_url, cancel_url) for Stripe Checkout by customer journey."""
    base = (base or "").strip().rstrip("/")
    if checkout_context in PLAN_CHANGE_CHECKOUT_CONTEXTS:
        success = (
            f"{base}/settings/billing?checkout=success"
            "&session_id={CHECKOUT_SESSION_ID}"
        )
        cancel = f"{base}/settings/billing?checkout=cancelled"
        return success, cancel
    success = f"{base}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel = f"{base}/checkout/cancel"
    return success, cancel


def _verify_checkout_subscription_price(session: Any, expected_price_id: str, plan_code: str) -> None:
    """Ensure Stripe session line item matches the requested plan price (no silent drift)."""
    line_items = getattr(session, "line_items", None) or {}
    data = line_items.get("data") if isinstance(line_items, dict) else getattr(line_items, "data", None)
    if not data:
        return
    first = data[0]
    price_obj = first.get("price") if isinstance(first, dict) else getattr(first, "price", None)
    actual_id = price_obj.get("id") if isinstance(price_obj, dict) else getattr(price_obj, "id", None)
    if actual_id and actual_id != expected_price_id:
        raise ValueError(
            f"Checkout session price mismatch for {plan_code}: "
            f"expected {expected_price_id}, Stripe returned {actual_id}"
        )


# Initialize Stripe from STRIPE_MODE authority (no cross-mode fallback)
try:
    configure_stripe_sdk()
except StripeModeConfigurationError as _stripe_cfg_err:
    logger.warning("Stripe SDK not configured at import: %s", _stripe_cfg_err)
    stripe.api_key = ""


def _billing_timestamp_iso(val: Any) -> Optional[str]:
    """Normalize Mongo-stored billing sync timestamps for JSON."""
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


class StripeService:
    """Stripe billing operations service."""
    
    async def create_checkout_session(
        self,
        client_id: str,
        plan_code: str,
        origin_url: str,
        customer_email: Optional[str] = None,
        customer_reference: Optional[str] = None,
        lead_id: Optional[str] = None,
        acceptance_id: Optional[str] = None,
        agreement_template_id: Optional[str] = None,
        agreement_template_version_id: Optional[str] = None,
        pilot_invite_doc: Optional[Dict[str, Any]] = None,
        checkout_context: str = CHECKOUT_CONTEXT_ONBOARDING,
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
        try:
            configure_stripe_sdk()
        except StripeModeConfigurationError as e:
            raise ValueError(str(e)) from e
        if not (stripe.api_key or "").strip():
            raise ValueError("Stripe secret key is not configured for the active STRIPE_MODE.")

        db = database.get_db()

        mode = get_stripe_mode()
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
        
        # Onboarding (setup) fee — never on existing-customer plan-change checkouts
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {
                "_id": 0,
                "onboarding_fee_paid": 1,
                "onboarding_fee_waived": 1,
                "stripe_subscription_id": 1,
            },
        )
        already_paid = billing and (
            billing.get("onboarding_fee_paid") is True or billing.get("onboarding_fee_waived") is True
        )
        plan_change_checkout = checkout_context in PLAN_CHANGE_CHECKOUT_CONTEXTS
        from services.pilot_onboarding_fee import resolve_checkout_onboarding

        include_onboarding, _onb_policy, onboarding_meta = resolve_checkout_onboarding(
            pilot_invite_doc=pilot_invite_doc,
            plan_code=plan.value,
            already_paid=already_paid or plan_change_checkout,
            onboarding_price_id=onboarding_price_id,
        )
        if include_onboarding and onboarding_price_id:
            line_items.append({"price": onboarding_price_id, "quantity": 1})

        success_url, cancel_url = checkout_redirect_urls(base, checkout_context)
        
        # Founding pilot: live Stripe checkout with configured 100% coupon/promotion (never bypass Stripe).
        pilot_metadata: Dict[str, str] = {}
        pilot_discounts = None
        if pilot_invite_doc:
            from services.pilot_invite_service import (
                build_checkout_pilot_metadata,
                payment_method_collection_for_pilot,
                stripe_session_discounts,
            )

            pilot_metadata = build_checkout_pilot_metadata(pilot_invite_doc, plan_code=plan.value)
            pilot_metadata.update(onboarding_meta)
            pilot_discounts = stripe_session_discounts(pilot_invite_doc)
            if not pilot_discounts:
                raise ValueError("Pilot invite discount is not configured. Contact support.")

        # Create checkout session
        try:
            session_metadata = {
                "client_id": client_id,  # MANDATORY for webhook
                "plan_code": plan.value,
                "requested_plan_code": plan.value,
                "checkout_context": checkout_context,
                "stripe_mode": mode,
                "service": "COMPLIANCE_VAULT_PRO",
                **({"customer_reference": customer_reference} if customer_reference else {}),
                **({"lead_id": (lead_id or "").strip()[:128]} if (lead_id and (lead_id or "").strip()) else {}),
                **({"acceptance_id": (acceptance_id or "").strip()[:128]} if (acceptance_id or "").strip() else {}),
                **(
                    {"agreement_template_id": (agreement_template_id or "").strip()[:128]}
                    if (agreement_template_id or "").strip()
                    else {}
                ),
                **(
                    {
                        "agreement_template_version_id": (agreement_template_version_id or "").strip()[:128],
                    }
                    if (agreement_template_version_id or "").strip()
                    else {}
                ),
                **pilot_metadata,
            }
            if not pilot_invite_doc:
                session_metadata.update(onboarding_meta)
            subscription_metadata = {
                "client_id": client_id,
                "plan_code": plan.value,
                "requested_plan_code": plan.value,
                "checkout_context": checkout_context,
                "stripe_mode": mode,
                **({"customer_reference": customer_reference} if customer_reference else {}),
                **({"lead_id": (lead_id or "").strip()[:128]} if (lead_id and (lead_id or "").strip()) else {}),
                **({"acceptance_id": (acceptance_id or "").strip()[:128]} if (acceptance_id or "").strip() else {}),
                **(
                    {"agreement_template_id": (agreement_template_id or "").strip()[:128]}
                    if (agreement_template_id or "").strip()
                    else {}
                ),
                **(
                    {
                        "agreement_template_version_id": (agreement_template_version_id or "").strip()[:128],
                    }
                    if (agreement_template_version_id or "").strip()
                    else {}
                ),
                **pilot_metadata,
            }
            if not pilot_invite_doc:
                subscription_metadata.update(onboarding_meta)
            session_params = {
                "mode": "subscription",
                "line_items": line_items,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": session_metadata,
                "subscription_data": {"metadata": subscription_metadata},
                "expand": ["line_items"],  # Expand for webhook processing
            }
            if pilot_discounts:
                # Pilot: Stripe coupon/promotion from invite record; PM `always` when repeating (see pilot_invite_service).
                session_params["discounts"] = pilot_discounts
                session_params["payment_method_collection"] = payment_method_collection_for_pilot(
                    pilot_invite_doc
                )

            if customer_email:
                session_params["customer_email"] = customer_email

            session = stripe.checkout.Session.create(**session_params)
            _verify_checkout_subscription_price(session, subscription_price_id, plan.value)

            # Record checkout attempt
            checkout_record = {
                "client_id": client_id,
                "session_id": session.id,
                "plan_code": plan.value,
                "requested_plan_code": plan.value,
                "checkout_context": checkout_context,
                "subscription_price_id": subscription_price_id,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "checkout_url": session.url,
                "amount_total": session.amount_total,
                "currency": session.currency,
                **billing_mode_fields_for_write(mode),
            }
            if pilot_invite_doc:
                from services.pilot_invite_service import discount_config_from_doc

                cfg = discount_config_from_doc(pilot_invite_doc)
                checkout_record["pilot_invite_code"] = pilot_invite_doc.get("code")
                checkout_record["pilot_invite_code_id"] = pilot_invite_doc.get("invite_code_id")
                checkout_record["program_type"] = pilot_invite_doc.get("program_type") or "FOUNDING_PILOT"
                checkout_record["pilot_discount_duration"] = cfg["discount_duration"]
                checkout_record["pilot_discount_months"] = cfg.get("discount_duration_in_months")
            checkout_record.update(onboarding_meta)

            await db.checkout_sessions.insert_one(checkout_record)
            
            logger.info(f"Checkout session created for client {client_id}: {session.id}")
            
            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "plan_code": plan.value,
                "requested_plan_code": plan.value,
                "checkout_context": checkout_context,
                "plan_name": plan_def["name"],
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout error for client {client_id}: {e}")
            raise ValueError(f"Failed to create checkout session: {str(e)}")

    async def expire_checkout_session(self, session_id: Optional[str]) -> None:
        """Best-effort: expire Stripe Checkout after DB linkage failure so the URL is not left usable without acceptance."""
        sid = (session_id or "").strip()
        if not sid:
            return
        try:
            stripe.checkout.Session.expire(sid)
        except Exception as e:
            logger.warning("expire_checkout_session failed session_id=%s: %s", sid, e)

    async def create_upgrade_session(
        self,
        client_id: str,
        new_plan_code: str,
        origin_url: str
    ) -> Dict[str, Any]:
        """
        Create checkout or portal session for plan upgrade.

        - No existing subscription: creates full Checkout session for the new plan.
        - Existing subscription: creates Billing Portal session with subscription_update_confirm
          so the user lands on "Confirm plan change" for the chosen plan, not the generic portal home.
        """
        db = database.get_db()
        deployment_mode = get_stripe_mode()
        configure_stripe_sdk(mode=deployment_mode)

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

        from services.stripe_mode_containment_service import requires_deployment_checkout_for_plan_change

        if requires_deployment_checkout_for_plan_change(billing):
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "email": 1, "contact_email": 1, "customer_reference": 1},
            )
            customer_email = (client or {}).get("email") or (client or {}).get("contact_email")
            result = await self.create_checkout_session(
                client_id=client_id,
                plan_code=new_plan_code,
                origin_url=origin_url,
                customer_email=customer_email,
                customer_reference=(client or {}).get("customer_reference"),
                checkout_context=CHECKOUT_CONTEXT_PLAN_CHANGE,
            )
            result["plan_change_path"] = "deployment_checkout"
            return result

        # Existing customer - send to portal with subscription_update_confirm so they
        # see the plan change confirmation for the requested plan, not the generic portal.
        stripe_customer_id = billing.get("stripe_customer_id")
        stripe_subscription_id = billing.get("stripe_subscription_id")
        if not stripe_subscription_id:
            await resolve_stripe_context(
                client_id=client_id,
                billing=billing,
                operation="billing_portal",
                require_preflight=True,
            )
            portal_session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=f"{origin_url.rstrip('/')}/settings/billing",
            )
            return {
                "portal_url": portal_session.url,
                "type": "billing_portal",
                "current_plan": billing.get("current_plan_code"),
                "target_plan": new_plan_code,
            }

        validate_stripe_subscription_mode(
            stripe_subscription_id,
            deployment_mode,
            stored_mode=billing.get("stripe_mode"),
            client_id=client_id,
            operation="upgrade_downgrade",
        )
        validate_portal_billing_preflight(
            billing, deployment_mode, client_id=client_id, operation="upgrade_downgrade"
        )

        # Resolve new plan and its Stripe price
        mode = _get_stripe_mode()
        try:
            config = get_stripe_price_mappings(mode)
        except StripeModeMismatchError:
            raise
        try:
            plan = PlanCode(new_plan_code)
        except ValueError:
            plan = plan_registry._resolve_plan_code(new_plan_code)
        prices = config["mappings"].get(plan.value, {})
        new_price_id = prices.get("subscription_price_id")
        if not new_price_id:
            raise StripeModeMismatchError(
                f"No {mode} subscription price for plan {new_plan_code}. Set STRIPE_{mode.upper()}_PRICE_{plan.value}_MONTHLY."
            )

        try:
            # Get subscription item id for the recurring line we're updating
            subscription = stripe.Subscription.retrieve(
                stripe_subscription_id,
                expand=["items.data"]
            )
            items = subscription.get("items") or {}
            data = (items.get("data") or []) if isinstance(items, dict) else []
            if not data:
                raise ValueError("Subscription has no items")
            subscription_item_id = data[0]["id"]

            portal_session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=f"{origin_url.rstrip('/')}/settings/billing",
                flow_data={
                    "type": "subscription_update_confirm",
                    "subscription_update_confirm": {
                        "subscription": stripe_subscription_id,
                        "items": [
                            {"id": subscription_item_id, "price": new_price_id}
                        ],
                    },
                },
            )

            logger.info(
                "Upgrade portal session created for client %s -> %s (sub %s)",
                client_id, new_plan_code, stripe_subscription_id
            )

            return {
                "portal_url": portal_session.url,
                "type": "billing_portal",
                "current_plan": billing.get("current_plan_code"),
                "target_plan": new_plan_code,
            }

        except StripeModeDriftError:
            raise
        except stripe.error.StripeError as e:
            from services.stripe_mode_containment_service import classify_stripe_api_error_for_drift

            if classify_stripe_api_error_for_drift(e):
                drift_err = await handle_stripe_api_drift_safe(
                    e, client_id=client_id, operation="upgrade_downgrade"
                )
                raise drift_err from e
            logger.error("Stripe upgrade portal error for client %s: %s", client_id, e)
            err_msg = str(e).strip()
            # Stripe returns this when Customer Portal has "subscription plan changes" disabled
            if "subscription update" in err_msg.lower() and "portal configuration" in err_msg.lower():
                raise ValueError(
                    "Subscription plan changes are not enabled in the billing portal. "
                    "Please contact support to enable upgrades, or we can enable it in Stripe Dashboard: "
                    "Settings → Billing → Customer portal → Subscription plan changes."
                )
            raise ValueError(f"Failed to create upgrade session: {err_msg}")

    async def create_billing_portal_session(
        self,
        client_id: str,
        origin_url: str,
        *,
        runtime_contract: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create Stripe Billing Portal session for payment-method / subscription management.

        When portal preflight is blocked by governed Stripe mode drift (e.g. MODE_UNVERIFIED)
        but Runtime Contract allows billing recovery checkout, falls back to deployment Checkout
        for the client's current plan.
        """
        from services.billing_recovery_authorization import (
            billing_recovery_write_allowed,
            resolve_recovery_plan_code,
        )
        from services.stripe_mode_containment_service import (
            PORTAL_DRIFT_RECOVERY_FALLBACK_ACTIONS,
        )

        db = database.get_db()
        billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})

        if not billing or not billing.get("stripe_customer_id"):
            if not billing_recovery_write_allowed(runtime_contract):
                raise ValueError("No active subscription found")
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "email": 1, "contact_email": 1, "customer_reference": 1, "billing_plan": 1},
            )
            plan_code = resolve_recovery_plan_code(billing, client)
            if not plan_code:
                raise ValueError("No billing plan on file for recovery checkout")
            customer_email = (client or {}).get("email") or (client or {}).get("contact_email")
            result = await self.create_checkout_session(
                client_id=client_id,
                plan_code=plan_code,
                origin_url=origin_url,
                customer_email=customer_email,
                customer_reference=(client or {}).get("customer_reference"),
                checkout_context=CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE,
            )
            result["recovery_path"] = "recovery_checkout"
            return result

        deployment_mode = get_stripe_mode()
        configure_stripe_sdk(mode=deployment_mode)

        try:
            await resolve_stripe_context(
                client_id=client_id,
                billing=billing,
                operation="billing_portal",
                legacy_caller="stripe_service.create_billing_portal_session",
                require_preflight=True,
            )
            portal_session = stripe.billing_portal.Session.create(
                customer=billing.get("stripe_customer_id"),
                return_url=f"{origin_url.rstrip('/')}/settings/billing",
            )
            return {
                "portal_url": portal_session.url,
                "recovery_path": "billing_portal",
            }
        except StripeModeDriftError as drift:
            if (
                drift.recovery_action in PORTAL_DRIFT_RECOVERY_FALLBACK_ACTIONS
                and billing_recovery_write_allowed(runtime_contract)
            ):
                plan_code = resolve_recovery_plan_code(billing)
                if not plan_code:
                    raise ValueError("No billing plan on file for recovery checkout") from drift
                result = await self.create_upgrade_session(
                    client_id=client_id,
                    new_plan_code=plan_code,
                    origin_url=origin_url,
                )
                if result.get("checkout_url"):
                    return {
                        "checkout_url": result["checkout_url"],
                        "session_id": result.get("session_id"),
                        "recovery_path": result.get("plan_change_path", "deployment_checkout"),
                        "recovery_guidance": (
                            "Complete payment in Stripe to restore your subscription."
                        ),
                    }
                if result.get("portal_url"):
                    return {
                        "portal_url": result["portal_url"],
                        "recovery_path": "billing_portal",
                    }
            raise
    
    async def get_subscription_status(
        self, client_id: str, *, client_facing: bool = True
    ) -> Dict[str, Any]:
        """Subscription and billing projection. Portal uses ``client_facing=True`` (no internal enums). Admin uses ``False``."""
        db = database.get_db()

        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0},
        )

        if not billing:
            if client_facing:
                return build_client_billing_payload(
                    has_subscription=False,
                    current_plan_code=None,
                    plan_name=None,
                    plan_display_name=None,
                    subscription_status=None,
                    billing_lifecycle_state=None,
                    cancel_at_period_end=False,
                    next_renewal_date_iso=None,
                    current_period_start_iso=None,
                    monthly_price_pence=None,
                    setup_fee_pence=None,
                    setup_fee_paid=False,
                    first_billing_cycle=False,
                    properties_used=0,
                    properties_limit=0,
                    grace_period_ends_at_iso=None,
                    payment_failed_at_iso=None,
                    charge_automatically=None,
                )
            return {
                "has_subscription": False,
                "status": "NONE",
                "entitlement_status": EntitlementStatus.DISABLED.value,
                "subscription_status": None,
                "current_period_end": None,
                "current_period_start": None,
                "next_renewal_date": None,
                "billing_lifecycle_state": None,
                "cancel_at_period_end": False,
                "grace_period_ends_at": None,
                "payment_failed_at": None,
                "charge_automatically": None,
                "billing_last_synced_at": None,
                "billing_sync_state": "no_subscription",
                "plan_status_display": None,
                "billing_status_display": None,
                "billing_sync_visibility_note": None,
                "billing_operational_narrative_lines": [],
            }

        # Legacy rows without lifecycle: one-time reconcile (no version bump)
        if billing.get("billing_lifecycle_state") is None or billing.get("canonical_entitlement_state") is None:
            try:
                from services.subscription_lifecycle_service import sync_subscription_lifecycle

                await sync_subscription_lifecycle(client_id, bump_version=False)
                billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or billing
            except Exception as sync_err:
                logger.warning(
                    "get_subscription_status: lifecycle backfill skipped client_id=%s: %s",
                    client_id,
                    sync_err,
                )

        cpe = normalize_stored_period_end_for_api(billing.get("current_period_end"))
        cps = normalize_stored_period_end_for_api(billing.get("current_period_start"))
        stripe_sub_id = billing.get("stripe_subscription_id")
        charge_automatically: Optional[bool] = None
        monthly_price_pence: Optional[int] = None
        stripe_refresh_failed = False
        if stripe_sub_id and (stripe.api_key or "").strip():
            try:
                sub = stripe.Subscription.retrieve(
                    stripe_sub_id,
                    expand=["items.data.price"],
                )
                if hasattr(sub, "to_dict"):
                    sub_d = sub.to_dict()
                else:
                    sub_d = dict(sub) if not isinstance(sub, dict) else sub
                charge_automatically = sub_d.get("collection_method") == "charge_automatically"
                fresh_end = period_end_from_stripe_subscription_dict(sub_d)
                fresh_start = period_start_from_stripe_subscription_dict(sub_d)
                anchor_dt = period_start_from_stripe_unix(sub_d.get("billing_cycle_anchor"))
                for item in (sub_d.get("items") or {}).get("data") or []:
                    price = item.get("price") or {}
                    if isinstance(price, dict) and price.get("recurring") is not None:
                        ua = price.get("unit_amount")
                        if ua is not None:
                            monthly_price_pence = int(ua)
                            break
                now_sync = datetime.now(timezone.utc)
                set_fields: Dict[str, Any] = {
                    "updated_at": now_sync,
                    "billing_last_synced_at": now_sync,
                    "billing_sync_state": "ok" if fresh_end else "missing_period_end",
                }
                if fresh_end:
                    set_fields["current_period_end"] = fresh_end
                    cpe = fresh_end
                if fresh_start:
                    set_fields["current_period_start"] = fresh_start
                    cps = fresh_start
                if anchor_dt:
                    set_fields["billing_cycle_anchor"] = anchor_dt
                if monthly_price_pence is not None:
                    set_fields["subscription_recurring_amount_pence"] = monthly_price_pence
                await db.client_billing.update_one(
                    {"client_id": client_id},
                    {"$set": set_fields},
                )
                billing["billing_last_synced_at"] = now_sync
                billing["billing_sync_state"] = "ok" if fresh_end else "missing_period_end"
                if fresh_end is not None:
                    billing["current_period_end"] = fresh_end
                if fresh_start is not None:
                    billing["current_period_start"] = fresh_start
            except stripe.error.StripeError as e:
                stripe_refresh_failed = True
                logger.warning(
                    "get_subscription_status: could not refresh subscription from Stripe client_id=%s: %s",
                    client_id,
                    e,
                )

        if not billing.get("last_payment_at"):
            try:
                from services.subscription_payment_ledger_service import (
                    fetch_latest_paid_ledger_for_client,
                    ledger_row_to_billing_payment_overlay,
                )

                _led = await fetch_latest_paid_ledger_for_client(client_id)
                if _led:
                    billing = dict(billing)
                    billing.update(ledger_row_to_billing_payment_overlay(_led))
            except Exception as _led_err:
                logger.warning(
                    "get_subscription_status: ledger fallback skipped client_id=%s: %s",
                    client_id,
                    _led_err,
                )

        cpe_out = cpe.isoformat() if cpe else None
        cps_out = cps.isoformat() if cps else None
        g_end = billing.get("grace_period_ends_at")
        pfail = billing.get("payment_failed_at")

        lifecycle_out = (billing.get("billing_lifecycle_state") or "active").lower()
        sub_u = (billing.get("subscription_status") or "").upper()
        if (
            lifecycle_out == "active"
            and cpe
            and sub_u in ("ACTIVE", "TRIALING")
            and not billing.get("cancel_at_period_end")
        ):
            delta = cpe - datetime.now(timezone.utc)
            if timedelta(0) < delta <= timedelta(days=7):
                lifecycle_out = "renewing"

        plan_code_str = billing.get("current_plan_code")
        plan_def = plan_registry.get_plan_by_code_string(plan_code_str) if plan_code_str else None
        if monthly_price_pence is None and plan_def:
            mp = plan_def.get("monthly_price")
            if mp is not None:
                monthly_price_pence = int(round(float(mp) * 100))
        setup_cents = billing.get("setup_fee_amount_cents")
        setup_pence: Optional[int] = int(setup_cents) if setup_cents is not None else None
        if setup_pence is None and plan_def and plan_def.get("onboarding_fee"):
            setup_pence = int(round(float(plan_def.get("onboarding_fee")) * 100))
        onboarding_paid = bool(billing.get("onboarding_fee_paid"))
        first_cycle = bool(not onboarding_paid and setup_pence and setup_pence > 0)
        prop_limit = (
            plan_registry.get_property_limit_by_string(plan_code_str) if plan_code_str else 0
        )

        billing_last_iso = _billing_timestamp_iso(billing.get("billing_last_synced_at"))
        if cpe_out:
            api_billing_sync_state = "ok"
        elif not stripe_sub_id:
            api_billing_sync_state = "no_subscription"
        elif stripe_refresh_failed:
            api_billing_sync_state = "stripe_error"
        elif sub_u in ("ACTIVE", "TRIALING", "PAST_DUE", "UNPAID"):
            api_billing_sync_state = "missing_period_end"
        else:
            api_billing_sync_state = "unknown"

        from services.entitlement_access import compute_canonical_entitlement_state

        canon = billing.get("canonical_entitlement_state") or compute_canonical_entitlement_state(
            billing_lifecycle_state=lifecycle_out,
            subscription_status_upper=sub_u,
        )

        display_currency = str((plan_def or {}).get("currency") or "gbp")
        lpc = billing.get("last_payment_currency")
        if lpc:
            display_currency = str(lpc).lower()

        if client_facing:
            return build_client_billing_payload(
                has_subscription=True,
                current_plan_code=plan_code_str,
                plan_name=plan_def.get("name") if plan_def else None,
                plan_display_name=plan_def.get("display_name") if plan_def else None,
                subscription_status=billing.get("subscription_status"),
                billing_lifecycle_state=lifecycle_out,
                cancel_at_period_end=bool(billing.get("cancel_at_period_end", False)),
                next_renewal_date_iso=cpe_out,
                current_period_start_iso=cps_out,
                current_period_end_iso=cpe_out,
                monthly_price_pence=monthly_price_pence,
                setup_fee_pence=setup_pence,
                setup_fee_paid=onboarding_paid,
                first_billing_cycle=first_cycle,
                properties_used=0,
                properties_limit=prop_limit,
                grace_period_ends_at_iso=g_end.isoformat() if g_end else None,
                payment_failed_at_iso=pfail.isoformat() if pfail else None,
                charge_automatically=charge_automatically,
                billing_last_synced_at_iso=billing_last_iso,
                billing_sync_state=api_billing_sync_state,
                currency=display_currency,
                canonical_entitlement_state=canon,
                last_payment_at_iso=_billing_timestamp_iso(billing.get("last_payment_at")),
                last_payment_amount_pence=billing.get("last_payment_amount_pence"),
                last_payment_stripe_invoice_id=billing.get("last_payment_stripe_invoice_id"),
                last_payment_invoice_number=billing.get("last_payment_invoice_number"),
                last_payment_status=billing.get("last_payment_status"),
                open_invoice_status=billing.get("open_invoice_status"),
                stripe_next_payment_attempt_iso=_billing_timestamp_iso(billing.get("stripe_next_payment_attempt_at")),
                last_invoice_failure_message=billing.get("last_invoice_failure_message"),
            )

        g_iso = g_end.isoformat() if g_end else None
        lp_at_iso = _billing_timestamp_iso(billing.get("last_payment_at"))
        lp_pence = billing.get("last_payment_amount_pence")
        grace_period_summary, last_payment_display = payment_grace_display_bundle(
            grace_period_ends_at_iso=g_iso,
            last_payment_at_iso=lp_at_iso,
            last_payment_amount_pence=lp_pence,
            currency=display_currency,
        )
        renewal_display = renewal_date_display_from_period_end_iso(cpe_out)
        open_inv = billing.get("open_invoice_status")
        cancel_flag = bool(billing.get("cancel_at_period_end", False))
        lsl_admin = lifecycle_status_label(
            has_subscription=True,
            cancel_at_period_end=cancel_flag,
            billing_lifecycle_state=lifecycle_out,
        )
        psd_admin = plan_status_display(
            has_subscription=True,
            subscription_status=billing.get("subscription_status"),
            billing_lifecycle_state=lifecycle_out,
            cancel_at_period_end=cancel_flag,
            open_invoice_status=open_inv,
        )
        bsd_admin = billing_status_display(
            has_subscription=True,
            subscription_status=billing.get("subscription_status"),
            billing_lifecycle_state=lifecycle_out,
            cancel_at_period_end=cancel_flag,
            open_invoice_status=open_inv,
        )
        stripe_next_iso = _billing_timestamp_iso(billing.get("stripe_next_payment_attempt_at"))
        sync_note_admin = billing_sync_visibility_note(
            billing_sync_state=api_billing_sync_state,
            billing_last_synced_at_iso=billing_last_iso,
        )
        narrative_admin = build_operational_billing_narrative_lines(
            lifecycle_status_label=lsl_admin,
            plan_status_display_str=psd_admin,
            billing_status_display_str=bsd_admin,
            billing_lifecycle_state=lifecycle_out,
            last_payment_summary=last_payment_display,
            open_invoice_status=open_inv,
            stripe_next_payment_attempt_iso=stripe_next_iso,
            cancel_at_period_end=cancel_flag,
            next_renewal_date_display=renewal_display,
            grace_period_summary=grace_period_summary,
            billing_last_synced_at_iso=billing_last_iso,
            billing_sync_state=api_billing_sync_state,
        )

        return {
            "has_subscription": True,
            "stripe_subscription_id": billing.get("stripe_subscription_id"),
            "stripe_customer_id": billing.get("stripe_customer_id"),
            "current_plan_code": plan_code_str,
            "subscription_status": billing.get("subscription_status"),
            "entitlement_status": billing.get("entitlement_status"),
            "canonical_entitlement_state": canon,
            "billing_lifecycle_state": lifecycle_out,
            "current_period_end": cpe_out,
            "current_period_start": cps_out,
            "next_renewal_date": cpe_out,
            "cancel_at_period_end": billing.get("cancel_at_period_end", False),
            "onboarding_fee_paid": onboarding_paid,
            "grace_period_ends_at": g_end.isoformat() if g_end else None,
            "payment_failed_at": pfail.isoformat() if pfail else None,
            "charge_automatically": charge_automatically,
            "billing_last_synced_at": billing_last_iso,
            "billing_sync_state": api_billing_sync_state,
            "latest_invoice_id": billing.get("latest_invoice_id"),
            "last_payment_at": _billing_timestamp_iso(billing.get("last_payment_at")),
            "last_payment_amount_pence": billing.get("last_payment_amount_pence"),
            "last_payment_status": billing.get("last_payment_status"),
            "last_payment_stripe_invoice_id": billing.get("last_payment_stripe_invoice_id"),
            "last_payment_invoice_number": billing.get("last_payment_invoice_number"),
            "last_payment_currency": billing.get("last_payment_currency"),
            "last_payment_source_event_id": billing.get("last_payment_source_event_id"),
            "open_invoice_id": billing.get("open_invoice_id"),
            "open_invoice_status": billing.get("open_invoice_status"),
            "stripe_next_payment_attempt_at": _billing_timestamp_iso(billing.get("stripe_next_payment_attempt_at")),
            "last_invoice_failure_message": billing.get("last_invoice_failure_message"),
            "stripe_webhook_last_received_at": _billing_timestamp_iso(billing.get("stripe_webhook_last_received_at")),
            "stripe_webhook_last_event_type": billing.get("stripe_webhook_last_event_type"),
            "lifecycle_status_label": lsl_admin,
            "plan_status_display": psd_admin,
            "billing_status_display": bsd_admin,
            "billing_sync_visibility_note": sync_note_admin,
            "billing_operational_narrative_lines": narrative_admin,
            "grace_period_summary": grace_period_summary,
        }
    
    async def cancel_subscription(
        self,
        client_id: str,
        cancel_immediately: bool = False,
        *,
        actor_role: str = "CLIENT",
        actor_id: Optional[str] = None,
        cancellation_source: str = "client_billing_cancel",
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            client_id: Client ID
            cancel_immediately: If True, cancel now. If False, cancel at period end.
            actor_role: Audit actor role (CLIENT or ROLE_ADMIN).
            actor_id: Optional portal user id for audit.
            cancellation_source: Audit source label for convergence tracing.
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

            sub_d_cancel = stripe_subscription_to_dict(subscription)
            stripe_cpe = period_end_from_stripe_subscription_dict(sub_d_cancel)
            cancel_set: Dict[str, Any] = {
                "cancel_at_period_end": not cancel_immediately,
                "subscription_status": "CANCELED" if cancel_immediately else billing.get("subscription_status"),
                "entitlement_status": EntitlementStatus.DISABLED.value if cancel_immediately else billing.get("entitlement_status"),
                "updated_at": datetime.now(timezone.utc),
            }
            if stripe_cpe:
                cancel_set["current_period_end"] = stripe_cpe

            cancel_update: Dict[str, Any] = {"$set": cancel_set}
            if not stripe_cpe:
                cancel_update["$unset"] = {"current_period_end": ""}

            # Update local record (Stripe response is source of truth for period end)
            await db.client_billing.update_one(
                {"client_id": client_id},
                {
                    **cancel_update,
                    "$set": {
                        **cancel_set,
                        "billing_sync_state": "pending_webhook_confirmation",
                        "billing_local_change_pending": True,
                        "billing_local_change_type": "subscription_cancel",
                    },
                },
            )
            try:
                await sync_subscription_lifecycle(client_id, bump_version=False)
            except Exception as sync_err:
                await mark_billing_reconciliation_needed(
                    client_id=client_id,
                    reason="cancel_lifecycle_sync_failed",
                    context={"error": str(sync_err)[:500], "cancel_immediately": bool(cancel_immediately)},
                )
                raise
            
            # Audit log
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=actor_role,
                actor_id=actor_id,
                client_id=client_id,
                metadata={
                    "action": "subscription_cancellation_requested",
                    "immediate": cancel_immediately,
                    "subscription_id": subscription_id,
                    "cancellation_source": cancellation_source,
                },
            )
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                client_id=client_id,
                metadata={
                    "action_type": "BILLING_EMAIL_TRIGGER_HOOK",
                    "trigger_key": "subscription_cancellation_confirmation",
                    "cancel_immediately": bool(cancel_immediately),
                    "source": "stripe_service.cancel_subscription",
                },
            )
            
            logger.info(f"Subscription cancellation requested for client {client_id}, immediate={cancel_immediately}")
            
            return {
                "success": True,
                "cancel_at_period_end": not cancel_immediately,
                "current_period_end": stripe_cpe.isoformat() if stripe_cpe else None,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe cancel error for client {client_id}: {e}")
            raise ValueError(f"Failed to cancel subscription: {str(e)}")

    async def resume_subscription(
        self,
        client_id: str,
        *,
        actor_role: str = "CLIENT",
        actor_id: Optional[str] = None,
        resume_source: str = "client_billing_resume",
    ) -> Dict[str, Any]:
        """Undo cancel-at-period-end (R-003) via Stripe authority and governed billing sync."""
        db = database.get_db()
        billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
        if not billing or not billing.get("stripe_subscription_id"):
            raise ValueError("No active subscription found")

        subscription_id = billing.get("stripe_subscription_id")
        if not billing.get("cancel_at_period_end"):
            return {
                "success": True,
                "already_active": True,
                "cancel_at_period_end": False,
                "subscription_status": billing.get("subscription_status"),
            }

        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False,
            )
            await sync_client_billing_from_stripe_subscription_id(
                client_id,
                subscription_id,
                event_source=resume_source,
                update_plan=True,
                increment_entitlements_version=0,
            )
            await sync_subscription_lifecycle(client_id, bump_version=True)
            sub_d = stripe_subscription_to_dict(subscription)
            stripe_cpe = period_end_from_stripe_subscription_dict(sub_d)
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=actor_role,
                actor_id=actor_id,
                client_id=client_id,
                metadata={
                    "action": "subscription_resume_requested",
                    "subscription_id": subscription_id,
                    "resume_source": resume_source,
                    "cancel_at_period_end": False,
                },
            )
            logger.info("Subscription resume requested for client %s", client_id)
            return {
                "success": True,
                "already_active": False,
                "cancel_at_period_end": False,
                "current_period_end": stripe_cpe.isoformat() if stripe_cpe else None,
                "subscription_status": sub_d.get("status"),
            }
        except stripe.error.StripeError as e:
            logger.error("Stripe resume error for client %s: %s", client_id, e)
            await mark_billing_reconciliation_needed(
                client_id=client_id,
                reason="resume_subscription_stripe_error",
                context={"error": str(e)[:500], "subscription_id": subscription_id},
            )
            raise ValueError(f"Failed to resume subscription: {str(e)}")

    async def list_invoices(self, client_id: str, limit: int = 24) -> Dict[str, Any]:
        """
        List paid invoices for the client (billing history).
        Returns subscription invoices and identifies setup fee line items.
        """
        db = database.get_db()
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "stripe_customer_id": 1, "current_plan_code": 1},
        )
        if not billing or not billing.get("stripe_customer_id"):
            return {"invoices": [], "has_more": False}

        stripe_customer_id = billing["stripe_customer_id"]

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

        pc = (billing or {}).get("current_plan_code")
        plan_enum: Optional[PlanCode] = plan_registry.resolve_plan_code(pc) if pc else None

        result = []
        for inv in invoices.get("data", []):
            inv_d = inv.to_dict() if hasattr(inv, "to_dict") else dict(inv)
            lines = normalize_stripe_invoice_lines(inv_d, plan_enum)
            result.append({
                "id": inv_d.get("id"),
                "number": inv_d.get("number"),
                "created": inv_d.get("created"),
                "amount_paid": inv_d.get("amount_paid", 0),
                "currency": (inv_d.get("currency") or "gbp").upper(),
                "billing_reason": inv_d.get("billing_reason"),
                "lines": lines,
            })
        return {
            "invoices": result,
            "has_more": invoices.get("has_more", False),
        }

    async def get_payment_method_summary(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Read-only card summary for client Billing UI. Does not store PAN; Stripe is source of truth.
        """
        if not (stripe.api_key or "").strip():
            return None
        db = database.get_db()
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "stripe_customer_id": 1},
        )
        cid = (billing or {}).get("stripe_customer_id")
        if not cid:
            row = await db.clients.find_one({"client_id": client_id}, {"stripe_customer_id": 1})
            cid = (row or {}).get("stripe_customer_id")
        if not cid:
            return None
        try:
            cust = stripe.Customer.retrieve(str(cid))
            pm = None
            pm_ref = cust.get("invoice_settings", {}).get("default_payment_method")
            if isinstance(pm_ref, str) and pm_ref:
                pm = stripe.PaymentMethod.retrieve(pm_ref)
            elif isinstance(pm_ref, dict):
                pm = pm_ref
            if not pm:
                pms = stripe.PaymentMethod.list(customer=str(cid), type="card", limit=1)
                if pms.data:
                    pm = pms.data[0]
            if not pm:
                return {
                    "available": True,
                    "managed_in_portal": True,
                    "display": None,
                    "message": "No card on file. Add one in the billing portal.",
                }
            card = pm.get("card") if isinstance(pm, dict) else getattr(pm, "card", None)
            if not card:
                return {
                    "available": True,
                    "managed_in_portal": True,
                    "display": None,
                    "message": "Payment method on file (card details not shown).",
                }
            if isinstance(card, dict):
                brand = (card.get("brand") or "Card").title()
                last4 = card.get("last4") or "••••"
            else:
                brand = (getattr(card, "brand", None) or "Card").title()
                last4 = getattr(card, "last4", None) or "••••"
            return {
                "available": True,
                "managed_in_portal": True,
                "display": f"{brand} •••• {last4}",
                "brand": brand.lower() if isinstance(brand, str) else str(brand),
                "last4": last4,
            }
        except stripe.error.StripeError as e:
            logger.warning("get_payment_method_summary Stripe error for %s: %s", client_id, e)
            return None


# Singleton instance
stripe_service = StripeService()
