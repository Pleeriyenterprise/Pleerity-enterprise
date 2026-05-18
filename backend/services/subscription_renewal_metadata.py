"""Additive subscription renewal / retention metadata on client_billing (not Stripe canonical)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _months_between(start: datetime, end: datetime) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


async def record_successful_renewal_metadata(
    db,
    *,
    client_id: str,
    amount_pence: int,
    paid_at: datetime,
    recovered_after_failure: bool = False,
) -> Dict[str, Any]:
    """Increment renewal counters after a successful paid cycle invoice."""
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    now = paid_at if paid_at.tzinfo else paid_at.replace(tzinfo=timezone.utc)
    first_paid = billing.get("subscription_ops_first_paid_at")
    if isinstance(first_paid, str):
        try:
            first_paid = datetime.fromisoformat(first_paid.replace("Z", "+00:00"))
        except ValueError:
            first_paid = None
    if not first_paid:
        first_paid = now

    renewal_number = int(billing.get("subscription_ops_renewal_number") or 0) + 1
    total_ok = int(billing.get("subscription_ops_total_successful_payments") or 0) + 1
    clv = int(billing.get("subscription_ops_customer_lifetime_value_pence") or 0) + max(0, amount_pence)
    months_active = _months_between(first_paid, now)
    consecutive = int(billing.get("subscription_ops_consecutive_successful_renewals") or 0) + 1

    patch = {
        "subscription_ops_renewal_number": renewal_number,
        "subscription_ops_first_paid_at": first_paid.isoformat(),
        "subscription_ops_last_renewed_at": now.isoformat(),
        "subscription_ops_months_active": months_active,
        "subscription_ops_customer_lifetime_value_pence": clv,
        "subscription_ops_total_successful_payments": total_ok,
        "subscription_ops_consecutive_successful_renewals": consecutive,
        "subscription_ops_recovered_after_failure": bool(recovered_after_failure),
        "updated_at": datetime.now(timezone.utc),
    }
    if recovered_after_failure:
        patch["subscription_ops_open_failure_incident_key"] = None
        patch["subscription_ops_open_failure_since"] = None

    await db.client_billing.update_one({"client_id": client_id}, {"$set": patch})
    return {
        "renewal_number": renewal_number,
        "months_active": months_active,
        "customer_lifetime_value_pence": clv,
        "recovered_after_failure": recovered_after_failure,
        "consecutive_successful_renewals": consecutive,
    }


async def record_failed_payment_metadata(db, *, client_id: str, failed_at: datetime) -> Dict[str, Any]:
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    total_fail = int(billing.get("subscription_ops_total_failed_payments") or 0) + 1
    consecutive = 0
    incident_key = f"renewal_fail:{client_id}"
    patch = {
        "subscription_ops_total_failed_payments": total_fail,
        "subscription_ops_last_failed_payment_at": failed_at.isoformat(),
        "subscription_ops_consecutive_successful_renewals": consecutive,
        "subscription_ops_open_failure_incident_key": incident_key,
        "subscription_ops_open_failure_since": failed_at.isoformat(),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.client_billing.update_one({"client_id": client_id}, {"$set": patch})
    return {"total_failed_payments": total_fail, "incident_key": incident_key}


async def load_renewal_metadata(db, *, client_id: str) -> Dict[str, Any]:
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    return {
        "renewal_number": billing.get("subscription_ops_renewal_number"),
        "first_paid_at": billing.get("subscription_ops_first_paid_at"),
        "last_renewed_at": billing.get("subscription_ops_last_renewed_at"),
        "months_active": billing.get("subscription_ops_months_active"),
        "customer_lifetime_value_pence": billing.get("subscription_ops_customer_lifetime_value_pence"),
        "total_successful_payments": billing.get("subscription_ops_total_successful_payments"),
        "total_failed_payments": billing.get("subscription_ops_total_failed_payments"),
        "last_failed_payment_at": billing.get("subscription_ops_last_failed_payment_at"),
        "consecutive_successful_renewals": billing.get("subscription_ops_consecutive_successful_renewals"),
        "open_failure_incident_key": billing.get("subscription_ops_open_failure_incident_key"),
    }
