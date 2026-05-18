"""Non-blocking bridge from Stripe webhook handlers to subscription operational events."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SUBSCRIPTION_RENEWAL_BILLING_REASONS = frozenset({"subscription_cycle", "subscription_update"})


async def on_invoice_paid(
    *,
    client_id: str,
    invoice: Dict[str, Any],
    event: Dict[str, Any],
    old_status: Optional[str],
    new_status: str,
    recovered: bool,
    lifecycle_sync_failed: bool = False,
) -> None:
    try:
        billing_reason = (invoice.get("billing_reason") or "").strip()
        amount_pence = int(invoice.get("amount_paid") or 0)
        if (
            new_status == "active"
            and billing_reason in SUBSCRIPTION_RENEWAL_BILLING_REASONS
            and amount_pence > 0
        ):
            from services.subscription_operational_events import record_subscription_renewed

            await record_subscription_renewed(
                client_id=client_id,
                invoice=invoice,
                event=event,
                recovered=recovered,
                lifecycle_sync_failed=lifecycle_sync_failed,
                old_status=old_status,
            )
    except Exception as exc:
        logger.warning("subscription ops on_invoice_paid failed client_id=%s: %s", client_id, exc, exc_info=True)


async def on_payment_failed(
    *,
    client_id: str,
    invoice: Dict[str, Any],
    event: Dict[str, Any],
    lifecycle_sync_failed: bool = False,
) -> None:
    try:
        from services.subscription_operational_events import record_subscription_renewal_failed

        await record_subscription_renewal_failed(
            client_id=client_id,
            invoice=invoice,
            event=event,
            lifecycle_sync_failed=lifecycle_sync_failed,
        )
    except Exception as exc:
        logger.warning("subscription ops on_payment_failed failed client_id=%s: %s", client_id, exc, exc_info=True)


async def on_subscription_deleted(
    *,
    client_id: str,
    event: Dict[str, Any],
    stripe_subscription_id: Optional[str],
) -> None:
    try:
        from services.subscription_operational_events import record_subscription_cancelled

        await record_subscription_cancelled(
            client_id=client_id,
            event=event,
            stripe_subscription_id=stripe_subscription_id,
        )
    except Exception as exc:
        logger.warning("subscription ops on_subscription_deleted failed client_id=%s: %s", client_id, exc, exc_info=True)


async def on_subscription_change(
    *,
    client_id: str,
    event: Dict[str, Any],
    old_plan: Optional[str],
    new_plan: Optional[str],
    old_status: Optional[str],
    new_status: str,
    is_upgrade: bool,
    is_downgrade: bool,
    invoice: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from services.subscription_operational_events import (
            record_plan_change,
            record_subscription_reactivated,
            record_trial_converted,
        )

        if is_upgrade or is_downgrade:
            await record_plan_change(
                client_id=client_id,
                event=event,
                is_upgrade=is_upgrade,
                is_downgrade=is_downgrade,
                old_plan=old_plan,
                new_plan=new_plan,
            )

        old_s = str(old_status or "").lower()
        new_s = str(new_status or "").lower()
        if old_s == "trialing" and new_s == "active":
            amt = int((invoice or {}).get("amount_paid") or 0)
            cur = (invoice or {}).get("currency") or "gbp"
            await record_trial_converted(
                client_id=client_id,
                event=event,
                amount_pence=amt,
                currency=cur,
            )

        if str(old_status or "").upper() in ("CANCELED", "CANCELLED") and new_s == "active":
            await record_subscription_reactivated(client_id=client_id, event=event)
    except Exception as exc:
        logger.warning("subscription ops on_subscription_change failed client_id=%s: %s", client_id, exc, exc_info=True)


async def on_charge_refunded(
    *,
    charge: Dict[str, Any],
    event: Dict[str, Any],
) -> None:
    try:
        from database import database

        db = database.get_db()
        charge_id = charge.get("id")
        invoice_id = charge.get("invoice")
        if isinstance(invoice_id, dict):
            invoice_id = invoice_id.get("id")
        payment = await db.payments.find_one(
            {"$or": [{"stripe_charge_id": charge_id}, {"stripe_invoice_id": invoice_id}]},
            {"_id": 0, "client_id": 1, "amount": 1, "currency": 1},
        )
        if not payment or not payment.get("client_id"):
            return
        amount = int(charge.get("amount_refunded") or payment.get("amount") or 0)
        currency = (charge.get("currency") or payment.get("currency") or "gbp").lower()
        from services.subscription_operational_events import record_refund_issued

        await record_refund_issued(
            client_id=payment["client_id"],
            event=event,
            amount_pence=amount,
            currency=currency,
            charge_id=str(charge_id) if charge_id else None,
        )
    except Exception as exc:
        logger.warning("subscription ops on_charge_refunded failed: %s", exc, exc_info=True)
