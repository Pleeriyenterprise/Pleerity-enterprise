"""
Canonical subscription entitlement for API enforcement and UI.

``canonical_entitlement_state`` is the single portal-facing access band:
ENABLED, GRACE, SUSPENDED, CANCELLED.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.plan_registry import (
    FEATURES_BLOCKED_DURING_GRACE_PERIOD,
    LIMITED_RECOVERY_FEATURES,
    plan_registry,
    subscription_allows_feature_access,
)


def compute_canonical_entitlement_state(
    *,
    billing_lifecycle_state: Optional[str],
    subscription_status_upper: Optional[str],
) -> str:
    """
    ENABLED — paid and in good standing (including renewal window).
    GRACE — payment retry / past due within grace rules (side effects may be blocked).
    SUSPENDED — post-grace restriction, unpaid, or other blocked states.
    CANCELLED — subscription ended in Stripe.
    """
    lc = (billing_lifecycle_state or "active").lower()
    st = (subscription_status_upper or "").upper()

    if lc == "cancelled" or st in ("CANCELED", "CANCELLED"):
        return "CANCELLED"
    if lc == "expired" or st == "UNPAID":
        return "SUSPENDED"
    if lc == "limited":
        return "SUSPENDED"
    if lc in ("grace_period", "past_due") or st == "PAST_DUE":
        return "GRACE"
    if lc in ("active", "renewing") and st in ("ACTIVE", "TRIALING"):
        return "ENABLED"
    if st in ("ACTIVE", "TRIALING"):
        return "ENABLED"
    if st in ("INCOMPLETE", "PAUSED"):
        return "GRACE"
    return "SUSPENDED"


def evaluate_subscription_feature_access(
    *,
    client: Dict[str, Any],
    billing: Optional[Dict[str, Any]],
    feature_key: str,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Return (error_message, error_details) if access must be denied; otherwise None.

    Shared by ``plan_registry.enforce_feature`` and ``middleware.feature_gating.require_feature``.
    """
    subscription_status = (billing or {}).get("subscription_status") or client.get("subscription_status")
    lifecycle = (billing or {}).get("billing_lifecycle_state") or client.get("billing_lifecycle_state") or "active"
    lc = (lifecycle or "active").lower()

    canon = (billing or {}).get("canonical_entitlement_state") or client.get("canonical_entitlement_state")
    if not canon:
        canon = compute_canonical_entitlement_state(
            billing_lifecycle_state=lc,
            subscription_status_upper=subscription_status,
        )

    try:
        from services.pilot_lifecycle_service import evaluate_pilot_governance_access, is_pilot_comped_entitled

        if is_pilot_comped_entitled(client):
            return None
        pilot_denial = evaluate_pilot_governance_access(client)
        if pilot_denial:
            return pilot_denial
    except Exception as pilot_gov_err:
        import logging

        logging.getLogger(__name__).warning(
            "Pilot governance check failed (continuing with Stripe entitlement): %s",
            pilot_gov_err,
        )

    if canon == "CANCELLED" or lc == "cancelled":
        return "This subscription is cancelled. Open Billing if you need to resubscribe.", {
            "error_code": "SUBSCRIPTION_CANCELLED",
            "billing_lifecycle_state": lc,
            "canonical_entitlement_state": canon,
        }

    if canon == "SUSPENDED" or lc == "expired":
        if lc == "expired":
            return "Your subscription has ended. Open Billing to renew and restore access.", {
                "error_code": "SUBSCRIPTION_EXPIRED",
                "billing_lifecycle_state": lc,
                "canonical_entitlement_state": canon,
            }
        if feature_key not in LIMITED_RECOVERY_FEATURES:
            return (
                "Your account is restricted after the payment grace period. "
                "Update your payment method in Billing to restore full access.",
                {
                    "error_code": "SUBSCRIPTION_SUSPENDED",
                    "billing_lifecycle_state": lc,
                    "canonical_entitlement_state": canon,
                    "feature": feature_key,
                },
            )
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = plan_registry.resolve_plan_code(plan_str)
        is_allowed, message, upgrade_info = plan_registry.check_feature_access(plan_code, feature_key)
        if not is_allowed:
            return message, {
                "error_code": "PLAN_NOT_ELIGIBLE",
                "feature": feature_key,
                "upgrade_required": True,
                "current_plan": plan_str,
                **(upgrade_info or {}),
            }
        return None

    if canon == "GRACE" or lc == "grace_period":
        if feature_key in FEATURES_BLOCKED_DURING_GRACE_PERIOD:
            return (
                "This action is paused while we retry your payment. "
                "Update your payment method in Billing to restore it.",
                {
                    "error_code": "SUBSCRIPTION_GRACE_PAYMENT",
                    "billing_lifecycle_state": lc,
                    "canonical_entitlement_state": canon,
                    "feature": feature_key,
                },
            )
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = plan_registry.resolve_plan_code(plan_str)
        is_allowed, message, upgrade_info = plan_registry.check_feature_access(plan_code, feature_key)
        if not is_allowed:
            return message, {
                "error_code": "PLAN_NOT_ELIGIBLE",
                "feature": feature_key,
                "upgrade_required": True,
                "current_plan": plan_str,
                **(upgrade_info or {}),
            }
        return None

    # Legacy lifecycle labels (before canonical backfill)
    if lc == "limited":
        if feature_key not in LIMITED_RECOVERY_FEATURES:
            return (
                "Your account is restricted after the payment grace period. "
                "Update your payment method in Billing to restore full access.",
                {
                    "error_code": "SUBSCRIPTION_LIMITED",
                    "billing_lifecycle_state": lc,
                    "canonical_entitlement_state": canon,
                    "feature": feature_key,
                },
            )
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = plan_registry.resolve_plan_code(plan_str)
        is_allowed, message, upgrade_info = plan_registry.check_feature_access(plan_code, feature_key)
        if not is_allowed:
            return message, {
                "error_code": "PLAN_NOT_ELIGIBLE",
                "feature": feature_key,
                "upgrade_required": True,
                "current_plan": plan_str,
                **(upgrade_info or {}),
            }
        return None

    if not subscription_allows_feature_access(subscription_status):
        return f"Subscription is {subscription_status}. Active or trialing subscription required.", {
            "error_code": "SUBSCRIPTION_INACTIVE",
            "subscription_status": subscription_status,
            "billing_lifecycle_state": lc,
            "canonical_entitlement_state": canon,
        }

    plan_str = client.get("billing_plan", "PLAN_1_SOLO")
    plan_code = plan_registry.resolve_plan_code(plan_str)
    is_allowed, message, upgrade_info = plan_registry.check_feature_access(plan_code, feature_key)
    if not is_allowed:
        return message, {
            "error_code": "PLAN_NOT_ELIGIBLE",
            "feature": feature_key,
            "upgrade_required": True,
            "current_plan": plan_str,
            **(upgrade_info or {}),
        }
    return None
