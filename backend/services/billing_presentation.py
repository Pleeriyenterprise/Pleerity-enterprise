"""
Client-facing billing copy and enums — no internal lifecycle / entitlement labels in portal payloads.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _upper(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def plan_status_display(
    *,
    has_subscription: bool,
    subscription_status: Optional[str],
) -> str:
    if not has_subscription:
        return "No active subscription"
    u = _upper(subscription_status)
    if u in ("PAST_DUE", "UNPAID"):
        return "Past due"
    if u == "CANCELED":
        return "Cancelled"
    if u in ("ACTIVE", "TRIALING"):
        return "Active"
    if u in ("INCOMPLETE", "INCOMPLETE_EXPIRED", "PAUSED"):
        return "Pending"
    if u:
        return "Pending"
    return "No active subscription"


def billing_status_display(
    *,
    has_subscription: bool,
    subscription_status: Optional[str],
    billing_lifecycle_state: Optional[str],
) -> str:
    if not has_subscription:
        return "No active subscription"
    u = _upper(subscription_status)
    lc = (billing_lifecycle_state or "active").lower()
    if u == "CANCELED":
        return "Cancelled"
    if u in ("PAST_DUE", "UNPAID") or lc in ("grace_period", "limited", "past_due"):
        return "Payment issue"
    return "Active"


def renewal_customer_copy(
    *,
    has_subscription: bool,
    subscription_status: Optional[str],
    cancel_at_period_end: bool,
    next_renewal_display: Optional[str],
) -> str:
    if not has_subscription:
        return "No active subscription is on file."
    u = _upper(subscription_status)
    if u not in ("ACTIVE", "TRIALING", "PAST_DUE", "UNPAID"):
        if u == "CANCELED":
            return "This subscription has ended."
        return "Renewal information is not available for this subscription state."
    if not next_renewal_display:
        return "We are syncing your next renewal date from Stripe; refresh in a moment."
    if cancel_at_period_end:
        return f"Renews until {next_renewal_display}."
    return f"Your subscription renews automatically on {next_renewal_display}."


def renewal_soon_flag(
    *,
    has_subscription: bool,
    cancel_at_period_end: bool,
    subscription_status: Optional[str],
    period_end: Optional[datetime],
) -> bool:
    if not has_subscription or cancel_at_period_end:
        return False
    u = _upper(subscription_status)
    if u not in ("ACTIVE", "TRIALING"):
        return False
    if not period_end:
        return False
    now = datetime.now(timezone.utc)
    delta = period_end - now
    return timedelta(0) < delta <= timedelta(days=7)


def build_client_billing_payload(
    *,
    has_subscription: bool,
    current_plan_code: Optional[str],
    plan_name: Optional[str],
    plan_display_name: Optional[str],
    subscription_status: Optional[str],
    billing_lifecycle_state: Optional[str],
    cancel_at_period_end: bool,
    next_renewal_date_iso: Optional[str],
    current_period_start_iso: Optional[str],
    monthly_price_pence: Optional[int],
    setup_fee_pence: Optional[int],
    setup_fee_paid: bool,
    first_billing_cycle: bool,
    properties_used: int,
    properties_limit: int,
    grace_period_ends_at_iso: Optional[str],
    payment_failed_at_iso: Optional[str],
    charge_automatically: Optional[bool],
    currency: str = "gbp",
) -> Dict[str, Any]:
    """
    Fields returned from GET /api/billing/status for portal users only.
    """
    cur = (currency or "gbp").upper()
    sym = "£" if cur in ("GBP", "GB") else f"{cur} "

    def money_pence(p: Optional[int]) -> Optional[str]:
        if p is None:
            return None
        return f"{sym}{p / 100:.2f}" + ("" if sym == "£" else f" {cur}")

    if not has_subscription:
        return {
            "has_subscription": False,
            "current_plan_code": None,
            "plan_name": None,
            "plan_display_name": None,
            "plan_status_display": "No active subscription",
            "billing_status_display": "No active subscription",
            "next_renewal_date": None,
            "next_renewal_date_display": None,
            "current_period_start": None,
            "cancel_at_period_end": False,
            "monthly_price_pence": None,
            "monthly_price_display": None,
            "setup_fee_pence": None,
            "setup_fee_display": None,
            "setup_fee_state": "not_applicable",
            "properties_used": properties_used,
            "properties_limit": properties_limit,
            "grace_period_ends_at": None,
            "payment_failed_at": None,
            "charge_automatically": None,
            "renewal_customer_copy": renewal_customer_copy(
                has_subscription=False,
                subscription_status=None,
                cancel_at_period_end=False,
                next_renewal_display=None,
            ),
            "renewal_soon": False,
            "currency": cur,
        }

    period_end_dt: Optional[datetime] = None
    if next_renewal_date_iso:
        try:
            period_end_dt = datetime.fromisoformat(next_renewal_date_iso.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            period_end_dt = None

    renewal_display: Optional[str] = None
    if period_end_dt:
        try:
            if period_end_dt.timestamp() >= 946684800:
                renewal_display = f"{period_end_dt.day} {period_end_dt.strftime('%B %Y')}"
        except (OSError, OverflowError, ValueError):
            renewal_display = None

    setup_state = "not_applicable"
    if has_subscription and setup_fee_pence and setup_fee_pence > 0:
        if setup_fee_paid or not first_billing_cycle:
            setup_state = "paid"
        else:
            setup_state = "applies_first_cycle"

    payload: Dict[str, Any] = {
        "has_subscription": has_subscription,
        "current_plan_code": current_plan_code,
        "plan_name": plan_name,
        "plan_display_name": plan_display_name,
        "plan_status_display": plan_status_display(
            has_subscription=has_subscription,
            subscription_status=subscription_status,
        ),
        "billing_status_display": billing_status_display(
            has_subscription=has_subscription,
            subscription_status=subscription_status,
            billing_lifecycle_state=billing_lifecycle_state,
        ),
        "next_renewal_date": next_renewal_date_iso,
        "next_renewal_date_display": renewal_display,
        "current_period_start": current_period_start_iso,
        "cancel_at_period_end": cancel_at_period_end,
        "monthly_price_pence": monthly_price_pence,
        "monthly_price_display": money_pence(monthly_price_pence),
        "setup_fee_pence": setup_fee_pence if setup_fee_pence and setup_fee_pence > 0 else None,
        "setup_fee_display": money_pence(setup_fee_pence) if setup_fee_pence and setup_fee_pence > 0 else None,
        "setup_fee_state": setup_state,
        "properties_used": properties_used,
        "properties_limit": properties_limit,
        "grace_period_ends_at": grace_period_ends_at_iso,
        "payment_failed_at": payment_failed_at_iso,
        "charge_automatically": charge_automatically,
        "renewal_customer_copy": renewal_customer_copy(
            has_subscription=has_subscription,
            subscription_status=subscription_status,
            cancel_at_period_end=cancel_at_period_end,
            next_renewal_display=renewal_display,
        ),
        "renewal_soon": renewal_soon_flag(
            has_subscription=has_subscription,
            cancel_at_period_end=cancel_at_period_end,
            subscription_status=subscription_status,
            period_end=period_end_dt,
        ),
        "currency": cur,
    }
    return payload
