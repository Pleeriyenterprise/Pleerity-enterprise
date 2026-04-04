"""
Subscription billing lifecycle — grace period, dunning, renewal windows, and UI/API state.

Stripe remains the payment source of truth; this module derives `billing_lifecycle_state`
and entitlement overrides from stored billing fields + time.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from database import database
from services.plan_registry import EntitlementStatus, plan_registry
from services.billing_period_utils import normalize_stored_period_end_for_api, period_end_from_stripe_unix

logger = logging.getLogger(__name__)


def grace_period_days() -> int:
    raw = (os.getenv("SUBSCRIPTION_GRACE_PERIOD_DAYS") or "7").strip()
    try:
        n = int(raw)
        return max(1, min(n, 30))
    except ValueError:
        return 7


def renewal_reminder_days() -> Tuple[int, int]:
    """(first_reminder_days_before, second_reminder_days_before) — e.g. 7 and 3."""
    return (7, 3)


class BillingLifecycleState(str, Enum):
    ACTIVE = "active"
    RENEWING = "renewing"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
    LIMITED = "limited"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_billing_lifecycle_state(
    *,
    subscription_status_upper: str,
    cancel_at_period_end: bool,
    grace_period_ends_at: Optional[datetime],
    current_period_end: Optional[datetime],
    now: datetime,
) -> str:
    """
    Derive canonical lifecycle label for API/UI.
    `subscription_status_upper` mirrors Stripe (e.g. ACTIVE, PAST_DUE).
    """
    st = (subscription_status_upper or "").upper()
    now = _ensure_utc(now) or datetime.now(timezone.utc)
    g_end = _ensure_utc(grace_period_ends_at)
    cpe = normalize_stored_period_end_for_api(current_period_end)

    if st in ("CANCELED", "CANCELLED"):
        return BillingLifecycleState.CANCELLED.value
    if st == "UNPAID":
        return BillingLifecycleState.EXPIRED.value
    if st in ("INCOMPLETE_EXPIRED",):
        return BillingLifecycleState.EXPIRED.value

    if st in ("ACTIVE", "TRIALING"):
        if cpe:
            delta = cpe - now
            if timedelta(0) < delta <= timedelta(days=7):
                return BillingLifecycleState.RENEWING.value
        return BillingLifecycleState.ACTIVE.value

    if st == "PAST_DUE":
        if g_end is None:
            return BillingLifecycleState.PAST_DUE.value
        if now < g_end:
            return BillingLifecycleState.GRACE_PERIOD.value
        return BillingLifecycleState.LIMITED.value

    return BillingLifecycleState.ACTIVE.value


def compute_entitlement_for_lifecycle(
    lifecycle: str,
    subscription_status_upper: str,
) -> EntitlementStatus:
    """Entitlement enforcement layer on top of Stripe status."""
    lc = (lifecycle or "").lower()
    st = (subscription_status_upper or "").upper()

    if st in ("ACTIVE", "TRIALING"):
        return EntitlementStatus.ENABLED

    if lc == BillingLifecycleState.RENEWING.value:
        return EntitlementStatus.ENABLED

    if lc == BillingLifecycleState.PAST_DUE.value:
        return EntitlementStatus.LIMITED

    if lc == BillingLifecycleState.GRACE_PERIOD.value:
        return EntitlementStatus.LIMITED

    if lc == BillingLifecycleState.LIMITED.value:
        return EntitlementStatus.DISABLED

    if lc in (BillingLifecycleState.EXPIRED.value, BillingLifecycleState.CANCELLED.value):
        return EntitlementStatus.DISABLED

    return plan_registry.get_entitlement_status_from_subscription(st.lower())


async def _persist_client_lifecycle_after_subscription_sync(db, client_id: str) -> None:
    try:
        from services.client_lifecycle_service import persist_operational_client_lifecycle_if_needed

        await persist_operational_client_lifecycle_if_needed(db, client_id)
    except Exception as persist_err:
        logger.warning(
            "persist_operational_client_lifecycle after sync_subscription_lifecycle failed client_id=%s: %s",
            client_id,
            persist_err,
        )


async def sync_subscription_lifecycle(client_id: str, bump_version: bool = True) -> Dict[str, Any]:
    """
    Recompute `billing_lifecycle_state` and effective `entitlement_status` from `client_billing`.
    Updates `client_billing` and `clients` when values change.
    """
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    if not billing:
        return {"updated": False, "reason": "no_billing"}

    now = datetime.now(timezone.utc)
    sub_upper = (billing.get("subscription_status") or "").upper()
    cancel_at = bool(billing.get("cancel_at_period_end"))
    g_end = _ensure_utc(billing.get("grace_period_ends_at"))
    cpe = billing.get("current_period_end")

    lifecycle = compute_billing_lifecycle_state(
        subscription_status_upper=sub_upper,
        cancel_at_period_end=cancel_at,
        grace_period_ends_at=g_end,
        current_period_end=cpe,
        now=now,
    )
    new_entitlement = compute_entitlement_for_lifecycle(lifecycle, sub_upper)

    prev_lc = (billing.get("billing_lifecycle_state") or "").lower()
    prev_ent = (billing.get("entitlement_status") or "").upper()
    target_ent = new_entitlement.value

    if sub_upper in ("ACTIVE", "TRIALING"):
        sub_for_client = "ACTIVE"
    else:
        sub_for_client = sub_upper or "NONE"

    if prev_lc == lifecycle and prev_ent == target_ent:
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": {"billing_lifecycle_state": lifecycle, "subscription_status": sub_for_client}},
        )
        await _persist_client_lifecycle_after_subscription_sync(db, client_id)
        return {"updated": False, "billing_lifecycle_state": lifecycle, "entitlement_status": target_ent}

    set_doc: Dict[str, Any] = {
        "billing_lifecycle_state": lifecycle,
        "entitlement_status": target_ent,
        "updated_at": now,
    }
    update: Dict[str, Any] = {"$set": set_doc}
    if bump_version:
        update["$inc"] = {"entitlements_version": 1}

    await db.client_billing.update_one({"client_id": client_id}, update)

    billing_after = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0, "entitlements_version": 1})
    ent_ver = (billing_after or {}).get("entitlements_version", 1)

    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "billing_lifecycle_state": lifecycle,
                "entitlement_status": target_ent,
                "entitlements_version": ent_ver,
                "subscription_status": sub_for_client,
            }
        },
    )

    logger.info(
        "sync_subscription_lifecycle client_id=%s lifecycle=%s entitlement=%s (was %s/%s)",
        client_id,
        lifecycle,
        target_ent,
        prev_lc,
        prev_ent,
    )
    await _persist_client_lifecycle_after_subscription_sync(db, client_id)
    return {
        "updated": True,
        "billing_lifecycle_state": lifecycle,
        "entitlement_status": target_ent,
    }


async def apply_post_grace_transitions(now: Optional[datetime] = None) -> int:
    """
    For subscriptions still in PAST_DUE after grace end, ensure lifecycle is LIMITED and entitlement DISABLED.
    Returns count of clients updated.
    """
    now = now or datetime.now(timezone.utc)
    db = database.get_db()
    cursor = db.client_billing.find(
        {
            "subscription_status": "PAST_DUE",
            "grace_period_ends_at": {"$lte": now},
        },
        {"_id": 0, "client_id": 1},
    )
    rows = await cursor.to_list(500)
    n = 0
    for row in rows:
        cid = row.get("client_id")
        if cid:
            r = await sync_subscription_lifecycle(cid, bump_version=True)
            if r.get("updated"):
                n += 1
    return n


def build_renewal_email_context(
    *,
    client_name: str,
    renewal_date_display: str,
    days_until: int,
    charge_automatically: bool,
    billing_url: str,
) -> Dict[str, str]:
    if charge_automatically:
        body_framing = (
            f"Your subscription renews in about {days_until} day(s) on {renewal_date_display}. "
            "Payment is set to run automatically — please ensure your card on file is valid so renewal succeeds."
        )
    else:
        body_framing = (
            f"Your billing period renews in about {days_until} day(s) on {renewal_date_display}. "
            "Please complete payment when invoiced to avoid interruption."
        )
    return {
        "client_name": client_name,
        "renewal_date_display": renewal_date_display,
        "days_until": str(days_until),
        "billing_portal_link": billing_url,
        "body_framing": body_framing,
        "charge_automatically": "true" if charge_automatically else "false",
    }
