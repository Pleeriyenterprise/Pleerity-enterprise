"""Governed detection and reconciliation for stale scheduled-cancellation billing mirrors."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

from database import database
from services.billing_period_utils import normalize_stored_period_end_for_api
from services.billing_reconciliation_service import (
    clear_billing_reconciliation_needed,
    mark_billing_reconciliation_needed,
)
from services.billing_stripe_sync_service import sync_client_billing_from_stripe_subscription_id
from services.stripe_mode_authority import configure_stripe_sdk
from services.subscription_lifecycle_service import sync_subscription_lifecycle

logger = logging.getLogger(__name__)

_STALE_SYNC_COOLDOWN = timedelta(minutes=5)


def _utc_now(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def is_stale_scheduled_cancellation_mirror(
    billing: Optional[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> bool:
    """True when cancel-at-period-end is scheduled but period end is in the past while mirror still grants access."""
    if not billing:
        return False
    if not billing.get("cancel_at_period_end"):
        return False
    sub_status = (billing.get("subscription_status") or "").upper()
    if sub_status not in ("ACTIVE", "TRIALING"):
        return False
    period_end = normalize_stored_period_end_for_api(billing.get("current_period_end"))
    if not period_end:
        return False
    return period_end < _utc_now(now)


def stale_scheduled_cancellation_mongo_filter(*, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Mongo filter for scheduled cancellations past period end with active mirror."""
    return {
        "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
        "cancel_at_period_end": True,
        "subscription_status": {"$in": ["ACTIVE", "TRIALING"]},
        "current_period_end": {"$lt": _utc_now(now)},
    }


def _cooldown_elapsed(billing: Dict[str, Any], *, now: datetime) -> bool:
    last = billing.get("stale_scheduled_cancellation_sync_at")
    if not last:
        return True
    parsed = normalize_stored_period_end_for_api(last)
    if not parsed:
        return True
    return (now - parsed) >= _STALE_SYNC_COOLDOWN


async def reconcile_stale_scheduled_cancellation_if_needed(
    client_id: str,
    billing: Optional[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    event_source: str = "stale_scheduled_cancellation_reconcile",
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    When mirror is stale, flag reconciliation and pull Stripe authority (rate-limited).

    Returns (billing_after, reconciled).
    """
    now = _utc_now(now)
    if not client_id or not billing or not is_stale_scheduled_cancellation_mirror(billing, now=now):
        return billing, False

    await mark_billing_reconciliation_needed(
        client_id=client_id,
        reason="stale_scheduled_cancellation_period_end",
        context={
            "current_period_end": str(billing.get("current_period_end")),
            "subscription_status": billing.get("subscription_status"),
            "event_source": event_source,
        },
    )

    sid = (billing.get("stripe_subscription_id") or "").strip()
    if not sid or not _cooldown_elapsed(billing, now=now):
        return billing, False

    if not configure_stripe_sdk():
        return billing, False

    db = database.get_db()
    try:
        await sync_client_billing_from_stripe_subscription_id(
            client_id,
            sid,
            event_source=event_source,
            update_plan=True,
            increment_entitlements_version=0,
        )
        await sync_subscription_lifecycle(client_id, bump_version=True)
        await clear_billing_reconciliation_needed(
            client_id=client_id,
            reason="stale_scheduled_cancellation_reconciled",
        )
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": {"stale_scheduled_cancellation_sync_at": now, "updated_at": now}},
        )
        refreshed = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
        return refreshed, True
    except Exception as exc:
        logger.warning(
            "stale scheduled cancellation reconcile failed client_id=%s subscription_id=%s: %s",
            client_id,
            sid,
            exc,
        )
        return billing, False
