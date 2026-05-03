"""
Client-facing billing copy and enums — no internal lifecycle / entitlement labels in portal payloads.

Operational-truth rules (see billing governance slices S3–S5):
* Do not imply successful renewal or guaranteed auto-renewal when cancellation, retry, grace, or sync error applies.
* Disambiguate generic “Active” from paid vs grace vs limited vs cancelling.
* Surface sync freshness using existing fields only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _upper(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def _open_invoice_payment_pending(open_invoice_status: Optional[str]) -> bool:
    o = (open_invoice_status or "").strip().lower()
    return o in ("open", "past_due", "unpaid")


def plan_status_display(
    *,
    has_subscription: bool,
    subscription_status: Optional[str],
    billing_lifecycle_state: Optional[str] = None,
    cancel_at_period_end: bool = False,
    open_invoice_status: Optional[str] = None,
) -> str:
    """Short plan column — qualified so it does not contradict grace, retry, or cancellation."""
    if not has_subscription:
        return "No active subscription"
    u = _upper(subscription_status)
    lc = (billing_lifecycle_state or "active").lower()
    if u == "CANCELED":
        return "Cancelled"
    if cancel_at_period_end and u in ("ACTIVE", "TRIALING"):
        return "Cancelling — access for current period"
    if _open_invoice_payment_pending(open_invoice_status) and u in ("ACTIVE", "TRIALING", "PAST_DUE", "UNPAID"):
        return "Payment retry pending"
    if lc == "grace_period":
        return "Grace-period access"
    if lc == "limited":
        return "Limited access"
    if lc == "past_due":
        return "Payment past due"
    if u in ("PAST_DUE", "UNPAID"):
        return "Past due"
    if u in ("ACTIVE", "TRIALING"):
        return "Paid subscription active"
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
    cancel_at_period_end: bool = False,
) -> str:
    """Billing column — distinct from plan column; encodes payment path and cancellation."""
    if not has_subscription:
        return "No active subscription"
    u = _upper(subscription_status)
    lc = (billing_lifecycle_state or "active").lower()
    if u == "CANCELED":
        return "Cancelled"
    if cancel_at_period_end and u in ("ACTIVE", "TRIALING"):
        return "Cancelling — paid until period end"
    if lc == "grace_period":
        return "Grace-period access"
    if lc == "limited":
        return "Limited access"
    if lc == "past_due":
        return "Payment past due"
    if u in ("PAST_DUE", "UNPAID"):
        return "Payment issue"
    if lc == "renewing":
        return "Paid — renewal billing due soon"
    if u in ("ACTIVE", "TRIALING"):
        return "Paid subscription active"
    if u in ("INCOMPLETE", "INCOMPLETE_EXPIRED", "PAUSED"):
        return "Pending"
    if u:
        return "Pending"
    return "No active subscription"


def lifecycle_status_label(
    *,
    has_subscription: bool,
    cancel_at_period_end: bool,
    billing_lifecycle_state: Optional[str],
) -> str:
    if not has_subscription:
        return "No active subscription"
    if cancel_at_period_end:
        return "Cancelling at period end"
    lc = (billing_lifecycle_state or "active").lower()
    if lc == "grace_period":
        return "Payment retry (grace period)"
    if lc == "limited":
        return "Restricted — payment overdue"
    if lc == "past_due":
        return "Payment past due"
    if lc == "expired":
        return "Subscription expired"
    if lc == "cancelled":
        return "Subscription cancelled"
    if lc == "renewing":
        return "Paid subscription — renewal date approaching"
    if lc == "cancel_at_period_end":
        return "Cancelling at period end"
    return "Paid subscription active"


def renewal_customer_copy(
    *,
    has_subscription: bool,
    subscription_status: Optional[str],
    cancel_at_period_end: bool,
    next_renewal_display: Optional[str],
    billing_sync_state: str = "unknown",
    billing_lifecycle_state: Optional[str] = None,
    open_invoice_status: Optional[str] = None,
    stripe_next_payment_attempt_iso: Optional[str] = None,
    charge_automatically: Optional[bool] = None,
) -> str:
    if not has_subscription:
        return "No active subscription is on file."
    u = _upper(subscription_status)
    lc = (billing_lifecycle_state or "active").lower()
    if u not in ("ACTIVE", "TRIALING", "PAST_DUE", "UNPAID"):
        if u == "CANCELED":
            return "This subscription has ended."
        return "Renewal information is not available for this subscription state."

    bss = (billing_sync_state or "unknown").lower()

    if cancel_at_period_end:
        if next_renewal_display:
            return (
                f"Access continues until {next_renewal_display}. After that date your subscription ends — "
                "it will not renew automatically."
            )
        return (
            "Cancellation is scheduled. You keep access until the end of the current billing period; "
            "exact dates appear here after the next successful billing sync."
        )

    if _open_invoice_payment_pending(open_invoice_status):
        tail = ""
        if stripe_next_payment_attempt_iso:
            tail = f" Next collection attempt on record: {stripe_next_payment_attempt_iso}."
        return (
            "Payment or invoice retry is in progress with Stripe. "
            "Do not treat the next date as confirmed until the invoice is paid — use the billing portal to update your card."
            + tail
        )

    if bss == "stripe_error":
        return (
            "We could not reach Stripe to refresh billing dates. What you see reflects our last stored data — "
            "use the billing portal to confirm payment status and access."
        )
    if bss in ("missing_period_end", "stale"):
        return (
            "Your next billing date is not on file yet. "
            "If this continues, contact support or ask an admin to run a billing sync from Stripe."
        )

    if lc == "grace_period":
        if next_renewal_display:
            return (
                f"You are in a payment grace period. Resolve payment before access is further limited. "
                f"The period boundary shown ({next_renewal_display}) assumes successful collection."
            )
        return "You are in a payment grace period — resolve payment in the billing portal before access is further limited."

    if lc == "limited":
        return "Full access is restricted after overdue payment. A renewal is not complete until a successful charge posts in Stripe."

    if lc == "past_due" or u in ("PAST_DUE", "UNPAID"):
        return (
            "Payment is overdue or being retried. Dates below reflect our last stored billing data — "
            "confirm the latest invoice state in the billing portal."
        )

    if not next_renewal_display:
        return "We are syncing your next billing date from Stripe; refresh in a moment."

    if charge_automatically is False:
        return (
            f"Your plan continues with an upcoming invoicing date of {next_renewal_display}. "
            "Pay the invoice when issued — automatic card charge is not enabled for this subscription."
        )
    return (
        f"If your payment method succeeds, the next billing cycle is scheduled for {next_renewal_display}. "
        "This is not a receipt — confirm payment in history or Stripe if needed."
    )


def renewal_date_display_from_period_end_iso(cpe_iso: Optional[str]) -> Optional[str]:
    """Human next-period label for portal/admin copy (same rules as billing status)."""
    if not cpe_iso:
        return None
    try:
        period_end_dt = datetime.fromisoformat(cpe_iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    try:
        if period_end_dt.timestamp() >= 946684800:
            return f"{period_end_dt.day} {period_end_dt.strftime('%B %Y')}"
    except (OSError, OverflowError, ValueError):
        return None
    return None


def payment_grace_display_bundle(
    *,
    grace_period_ends_at_iso: Optional[str],
    last_payment_at_iso: Optional[str],
    last_payment_amount_pence: Optional[int],
    currency: str = "gbp",
) -> tuple[Optional[str], Optional[str]]:
    """Grace summary + last payment one-liner for narrative and portal (existing fields only)."""
    cur = (currency or "gbp").upper()
    sym = "£" if cur in ("GBP", "GB") else f"{cur} "

    def money_pence(p: Optional[int]) -> Optional[str]:
        if p is None:
            return None
        return f"{sym}{p / 100:.2f}" + ("" if sym == "£" else f" {cur}")

    grace_period_summary: Optional[str] = None
    if grace_period_ends_at_iso:
        try:
            gdt = datetime.fromisoformat(grace_period_ends_at_iso.replace("Z", "+00:00"))
            grace_period_summary = (
                f"Payment grace active — resolve billing by {gdt.strftime('%d %B %Y, %H:%M')} UTC "
                f"to avoid losing full access."
            )
        except (ValueError, TypeError, OSError):
            grace_period_summary = "Payment grace active — update your payment method in Billing."

    last_payment_display: Optional[str] = None
    if last_payment_at_iso:
        try:
            pdt = datetime.fromisoformat(last_payment_at_iso.replace("Z", "+00:00"))
            tpart = pdt.strftime("%d %B %Y, %H:%M UTC")
        except (ValueError, TypeError, OSError):
            tpart = last_payment_at_iso[:19]
        if last_payment_amount_pence is not None:
            last_payment_display = f"{tpart} · {money_pence(last_payment_amount_pence) or '—'}"
        else:
            last_payment_display = tpart

    return grace_period_summary, last_payment_display


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


def billing_sync_visibility_note(
    *,
    billing_sync_state: str,
    billing_last_synced_at_iso: Optional[str],
) -> Optional[str]:
    """Single-line sync freshness for UI (existing fields only)."""
    bss = (billing_sync_state or "unknown").lower()
    last = billing_last_synced_at_iso or "not recorded"
    if bss in ("stripe_error", "missing_period_end", "unknown", "stale"):
        return f"Billing data may be incomplete ({bss}). Last refresh in our records: {last}."
    if bss == "no_subscription":
        return None
    if bss == "ok" and billing_last_synced_at_iso:
        return f"Last billing refresh: {last}."
    return f"Billing sync: {bss}. Last refresh: {last}."


def build_operational_billing_narrative_lines(
    *,
    lifecycle_status_label: str,
    plan_status_display_str: str,
    billing_status_display_str: str,
    billing_lifecycle_state: Optional[str],
    last_payment_summary: Optional[str],
    open_invoice_status: Optional[str],
    stripe_next_payment_attempt_iso: Optional[str],
    cancel_at_period_end: bool,
    next_renewal_date_display: Optional[str],
    grace_period_summary: Optional[str],
    billing_last_synced_at_iso: Optional[str],
    billing_sync_state: str,
) -> List[str]:
    """Ordered read-only narrative from existing billing fields — not a second billing authority."""
    lines: List[str] = []
    lines.append(f"Access: {lifecycle_status_label}")
    lines.append(f"Plan: {plan_status_display_str} · Billing: {billing_status_display_str}")
    if cancel_at_period_end:
        lines.append("Cancellation at period end is scheduled — no automatic renewal after the current period.")
    if grace_period_summary:
        lines.append(grace_period_summary)
    if last_payment_summary:
        lines.append(f"Last successful payment (on record): {last_payment_summary}")
    else:
        lines.append("No last successful payment line in this view.")
    if _open_invoice_payment_pending(open_invoice_status):
        tail = ""
        if stripe_next_payment_attempt_iso:
            tail = f" Next collection attempt (on record): {stripe_next_payment_attempt_iso}."
        lines.append(f"Invoice / retry: {open_invoice_status}.{tail}")
    else:
        lc = (billing_lifecycle_state or "active").lower()
        if lc in ("grace_period", "past_due", "limited"):
            lines.append("Payment path needs attention — confirm in the Stripe billing portal if unsure.")
    if next_renewal_date_display:
        lines.append(f"Next period on record: {next_renewal_date_display} (depends on successful payment).")
    sn = billing_sync_visibility_note(
        billing_sync_state=billing_sync_state,
        billing_last_synced_at_iso=billing_last_synced_at_iso,
    )
    if sn:
        lines.append(sn)
    return lines


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
    current_period_end_iso: Optional[str] = None,
    monthly_price_pence: Optional[int],
    setup_fee_pence: Optional[int],
    setup_fee_paid: bool,
    first_billing_cycle: bool,
    properties_used: int,
    properties_limit: int,
    grace_period_ends_at_iso: Optional[str],
    payment_failed_at_iso: Optional[str],
    charge_automatically: Optional[bool],
    billing_last_synced_at_iso: Optional[str] = None,
    billing_sync_state: str = "unknown",
    currency: str = "gbp",
    canonical_entitlement_state: Optional[str] = None,
    last_payment_at_iso: Optional[str] = None,
    last_payment_amount_pence: Optional[int] = None,
    last_payment_stripe_invoice_id: Optional[str] = None,
    last_payment_invoice_number: Optional[str] = None,
    last_payment_status: Optional[str] = None,
    open_invoice_status: Optional[str] = None,
    stripe_next_payment_attempt_iso: Optional[str] = None,
    last_invoice_failure_message: Optional[str] = None,
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
            "subscription_status": None,
            "current_period_end": None,
            "billing_last_synced_at": None,
            "billing_sync_state": "no_subscription",
            "billing_sync_visibility_note": None,
            "billing_operational_narrative_lines": [],
            "renewal_customer_copy": renewal_customer_copy(
                has_subscription=False,
                subscription_status=None,
                cancel_at_period_end=False,
                next_renewal_display=None,
                billing_sync_state="no_subscription",
            ),
            "renewal_soon": False,
            "currency": cur,
            "canonical_entitlement_state": None,
            "grace_period_summary": None,
            "last_payment_at": None,
            "last_payment_display": None,
            "last_payment_amount_pence": None,
            "last_payment_stripe_invoice_id": None,
            "last_payment_invoice_number": None,
            "last_payment_status": None,
            "open_invoice_status": None,
            "stripe_next_payment_attempt_at": None,
            "last_invoice_failure_message": None,
        }

    cpe_iso = current_period_end_iso if current_period_end_iso is not None else next_renewal_date_iso

    period_end_dt: Optional[datetime] = None
    if cpe_iso:
        try:
            period_end_dt = datetime.fromisoformat(cpe_iso.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            period_end_dt = None

    renewal_display = renewal_date_display_from_period_end_iso(cpe_iso)

    setup_state = "not_applicable"
    if has_subscription and setup_fee_pence and setup_fee_pence > 0:
        if setup_fee_paid or not first_billing_cycle:
            setup_state = "paid"
        else:
            setup_state = "applies_first_cycle"

    grace_period_summary, last_payment_display = payment_grace_display_bundle(
        grace_period_ends_at_iso=grace_period_ends_at_iso,
        last_payment_at_iso=last_payment_at_iso,
        last_payment_amount_pence=last_payment_amount_pence,
        currency=currency,
    )

    psd = plan_status_display(
        has_subscription=has_subscription,
        subscription_status=subscription_status,
        billing_lifecycle_state=billing_lifecycle_state,
        cancel_at_period_end=cancel_at_period_end,
        open_invoice_status=open_invoice_status,
    )
    bsd = billing_status_display(
        has_subscription=has_subscription,
        subscription_status=subscription_status,
        billing_lifecycle_state=billing_lifecycle_state,
        cancel_at_period_end=cancel_at_period_end,
    )
    lsl = lifecycle_status_label(
        has_subscription=has_subscription,
        cancel_at_period_end=cancel_at_period_end,
        billing_lifecycle_state=billing_lifecycle_state,
    )
    sync_note = billing_sync_visibility_note(
        billing_sync_state=billing_sync_state,
        billing_last_synced_at_iso=billing_last_synced_at_iso,
    )
    narrative = build_operational_billing_narrative_lines(
        lifecycle_status_label=lsl,
        plan_status_display_str=psd,
        billing_status_display_str=bsd,
        billing_lifecycle_state=billing_lifecycle_state,
        last_payment_summary=last_payment_display,
        open_invoice_status=open_invoice_status,
        stripe_next_payment_attempt_iso=stripe_next_payment_attempt_iso,
        cancel_at_period_end=cancel_at_period_end,
        next_renewal_date_display=renewal_display,
        grace_period_summary=grace_period_summary,
        billing_last_synced_at_iso=billing_last_synced_at_iso,
        billing_sync_state=billing_sync_state,
    )

    payload: Dict[str, Any] = {
        "has_subscription": has_subscription,
        "current_plan_code": current_plan_code,
        "plan_name": plan_name,
        "plan_display_name": plan_display_name,
        "plan_status_display": psd,
        "billing_status_display": bsd,
        "lifecycle_status_label": lsl,
        "subscription_status": _upper(subscription_status) or None,
        "next_renewal_date": cpe_iso,
        "next_renewal_date_display": renewal_display,
        "current_period_start": current_period_start_iso,
        "current_period_end": cpe_iso,
        "cancel_at_period_end": cancel_at_period_end,
        "billing_last_synced_at": billing_last_synced_at_iso,
        "billing_sync_state": billing_sync_state,
        "billing_sync_visibility_note": sync_note,
        "billing_operational_narrative_lines": narrative,
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
            billing_sync_state=billing_sync_state,
            billing_lifecycle_state=billing_lifecycle_state,
            open_invoice_status=open_invoice_status,
            stripe_next_payment_attempt_iso=stripe_next_payment_attempt_iso,
            charge_automatically=charge_automatically,
        ),
        "renewal_soon": renewal_soon_flag(
            has_subscription=has_subscription,
            cancel_at_period_end=cancel_at_period_end,
            subscription_status=subscription_status,
            period_end=period_end_dt,
        ),
        "currency": cur,
        "canonical_entitlement_state": canonical_entitlement_state,
        "grace_period_summary": grace_period_summary,
        "last_payment_at": last_payment_at_iso,
        "last_payment_display": last_payment_display,
        "last_payment_amount_pence": last_payment_amount_pence,
        "last_payment_stripe_invoice_id": last_payment_stripe_invoice_id,
        "last_payment_invoice_number": last_payment_invoice_number,
        "last_payment_status": last_payment_status,
        "open_invoice_status": open_invoice_status,
        "stripe_next_payment_attempt_at": stripe_next_payment_attempt_iso,
        "last_invoice_failure_message": last_invoice_failure_message,
    }
    return payload
