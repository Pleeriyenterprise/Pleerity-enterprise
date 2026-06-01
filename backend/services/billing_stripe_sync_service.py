"""
Centralized persistence of Stripe Subscription data into ``client_billing`` / ``clients``.

Webhooks must pass a full subscription object from Stripe API (retrieve), not only the
event payload fragment, so ``current_period_end`` and plan items are always authoritative.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from database import database
from services.billing_period_utils import (
    period_end_from_stripe_subscription_dict,
    period_end_from_stripe_unix,
    period_start_from_stripe_subscription_dict,
    period_start_from_stripe_unix,
)
from services.plan_registry import plan_registry
from services.billing_reconciliation_service import (
    clear_billing_reconciliation_needed,
    mark_billing_reconciliation_needed,
)
from services.stripe_mode_containment_service import (
    StripeModeDriftError,
    billing_mode_fields_for_write,
    resolve_stripe_context,
    validate_stripe_subscription_mode,
)

logger = logging.getLogger(__name__)


def stripe_subscription_to_dict(subscription: Any) -> Dict[str, Any]:
    if subscription is None:
        return {}
    if isinstance(subscription, dict):
        return dict(subscription)
    if hasattr(subscription, "to_dict"):
        return dict(subscription.to_dict())
    return dict(subscription)


async def retrieve_stripe_subscription_dict(
    subscription_id: str,
    *,
    stored_mode: Optional[str] = None,
    trusted_mode: Optional[str] = None,
    client_id: Optional[str] = None,
    operation: str = "subscription_sync",
) -> Dict[str, Any]:
    """Fetch full subscription from Stripe API (preflight on persisted mode first)."""
    ctx = await resolve_stripe_context(
        client_id=client_id,
        operation=operation,
        legacy_caller="billing_stripe_sync_service.retrieve_stripe_subscription_dict",
    )
    deployment_mode = ctx["deployment_mode"]
    validate_stripe_subscription_mode(
        subscription_id,
        deployment_mode,
        stored_mode=stored_mode,
        trusted_mode=trusted_mode,
        client_id=client_id,
        operation=operation,
    )
    sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
    return stripe_subscription_to_dict(sub)


async def resolve_client_id_for_stripe_customer(
    stripe_customer_id: Optional[str],
    stripe_subscription_id: Optional[str],
    subscription_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Map Stripe customer/subscription to internal client_id.
    Order: client_billing by customer → by subscription → clients by customer → metadata.client_id.
    """
    db = database.get_db()
    meta = subscription_metadata or {}

    if stripe_customer_id:
        row = await db.client_billing.find_one(
            {"stripe_customer_id": stripe_customer_id},
            {"_id": 0, "client_id": 1},
        )
        if row and row.get("client_id"):
            return row["client_id"]

    if stripe_subscription_id:
        row = await db.client_billing.find_one(
            {"stripe_subscription_id": stripe_subscription_id},
            {"_id": 0, "client_id": 1},
        )
        if row and row.get("client_id"):
            return row["client_id"]

    cid_meta = (meta.get("client_id") or "").strip()
    if cid_meta:
        exists = await db.clients.find_one({"client_id": cid_meta}, {"_id": 0, "client_id": 1})
        if exists:
            return cid_meta

    if stripe_customer_id:
        crow = await db.clients.find_one(
            {"stripe_customer_id": stripe_customer_id},
            {"_id": 0, "client_id": 1},
        )
        if crow and crow.get("client_id"):
            return crow["client_id"]

    logger.warning(
        "billing_sync: could not map Stripe customer to client stripe_customer_id=%s subscription_id=%s metadata.client_id=%s",
        stripe_customer_id,
        stripe_subscription_id,
        cid_meta or None,
    )
    return None


async def persist_subscription_billing_from_stripe(
    client_id: str,
    subscription: Any,
    *,
    event_source: str,
    update_plan: bool = True,
    additional_billing_set: Optional[Dict[str, Any]] = None,
    increment_entitlements_version: int = 0,
) -> Dict[str, Any]:
    """
    Persist subscription period, status, Stripe ids, and optionally plan code from a full Stripe subscription.

    ``additional_billing_set`` is merged into the same $set (e.g. checkout breakdown fields).
    """
    db = database.get_db()
    sub_d = stripe_subscription_to_dict(subscription)

    stripe_customer_id = sub_d.get("customer")
    if isinstance(stripe_customer_id, dict):
        stripe_customer_id = stripe_customer_id.get("id")
    stripe_subscription_id = sub_d.get("id")

    raw_top_cpe = sub_d.get("current_period_end")
    period_end_dt = period_end_from_stripe_subscription_dict(sub_d)
    period_start_dt = period_start_from_stripe_subscription_dict(sub_d)
    anchor_dt = period_start_from_stripe_unix(sub_d.get("billing_cycle_anchor"))

    if not period_end_dt:
        logger.warning(
            "billing_sync: current_period_end missing or invalid after Stripe retrieve client_id=%s subscription_id=%s source=%s raw_top_cpe=%r",
            client_id,
            stripe_subscription_id,
            event_source,
            raw_top_cpe,
        )
    elif not period_end_from_stripe_unix(raw_top_cpe):
        logger.info(
            "billing_sync: current_period_end derived from subscription items (top-level missing/invalid) client_id=%s subscription_id=%s source=%s",
            client_id,
            stripe_subscription_id,
            event_source,
        )

    sync_state = "ok" if period_end_dt else "missing_period_end"

    new_plan_code = None
    if update_plan:
        for item in (sub_d.get("items") or {}).get("data") or []:
            price = item.get("price") or {}
            price_id = price.get("id") if isinstance(price, dict) else item.get("price")
            new_plan_code = plan_registry.get_plan_from_subscription_price_id(price_id)
            if new_plan_code:
                break
        if not new_plan_code:
            logger.warning(
                "billing_sync: could not resolve plan from subscription items client_id=%s subscription_id=%s source=%s",
                client_id,
                stripe_subscription_id,
                event_source,
            )

    subscription_status = sub_d.get("status") or "unknown"
    entitlement_status = plan_registry.get_entitlement_status_from_subscription(subscription_status)

    now_sync = datetime.now(timezone.utc)
    billing_update: Dict[str, Any] = {
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        **billing_mode_fields_for_write(),
        "subscription_status": subscription_status.upper(),
        "entitlement_status": entitlement_status.value,
        "cancel_at_period_end": sub_d.get("cancel_at_period_end", False),
        "latest_invoice_id": sub_d.get("latest_invoice"),
        "updated_at": now_sync,
        "billing_last_synced_at": now_sync,
        "billing_sync_state": sync_state,
    }
    if new_plan_code:
        billing_update["current_plan_code"] = new_plan_code.value
    if period_end_dt:
        billing_update["current_period_end"] = period_end_dt
    if period_start_dt:
        billing_update["current_period_start"] = period_start_dt
    if anchor_dt:
        billing_update["billing_cycle_anchor"] = anchor_dt

    for item in (sub_d.get("items") or {}).get("data") or []:
        price = item.get("price") or {}
        if isinstance(price, dict) and price.get("recurring") is not None and price.get("unit_amount") is not None:
            billing_update["subscription_recurring_amount_pence"] = int(price["unit_amount"])
            break

    if additional_billing_set:
        billing_update.update(additional_billing_set)

    update_doc: Dict[str, Any] = {"$set": billing_update}
    if increment_entitlements_version:
        update_doc["$inc"] = {"entitlements_version": increment_entitlements_version}

    await db.client_billing.update_one({"client_id": client_id}, update_doc)

    billing_after = await db.client_billing.find_one(
        {"client_id": client_id},
        {"_id": 0, "entitlements_version": 1},
    )
    entitlements_version = (billing_after or {}).get("entitlements_version", 1)

    sub_status_set = (
        "ACTIVE" if subscription_status in ("active", "trialing") else str(subscription_status).upper()
    )
    clients_set: Dict[str, Any] = {
        "subscription_status": sub_status_set,
        "entitlement_status": entitlement_status.value,
        "entitlements_version": entitlements_version,
    }
    if stripe_customer_id:
        clients_set["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id:
        clients_set["stripe_subscription_id"] = stripe_subscription_id
    if new_plan_code:
        clients_set["billing_plan"] = new_plan_code.value

    try:
        await db.clients.update_one({"client_id": client_id}, {"$set": clients_set})
    except Exception as clients_err:
        await mark_billing_reconciliation_needed(
            client_id=client_id,
            reason="clients_update_failed_after_billing_sync",
            context={
                "event_source": event_source,
                "stripe_subscription_id": stripe_subscription_id,
                "error": str(clients_err)[:500],
            },
        )
        raise
    await clear_billing_reconciliation_needed(client_id=client_id, reason="billing_sync_completed")
    try:
        from services.client_lifecycle_service import persist_operational_client_lifecycle_if_needed

        await persist_operational_client_lifecycle_if_needed(db, client_id)
    except Exception as lc_err:
        logger.warning(
            "persist client lifecycle after billing_sync failed client_id=%s: %s",
            client_id,
            lc_err,
        )

    logger.info(
        "billing_sync: persisted subscription client_id=%s subscription_id=%s source=%s period_end=%s sync_state=%s",
        client_id,
        stripe_subscription_id,
        event_source,
        period_end_dt.isoformat() if period_end_dt else None,
        sync_state,
    )

    return {
        "client_id": client_id,
        "stripe_subscription_id": stripe_subscription_id,
        "current_period_end": period_end_dt,
        "billing_sync_state": sync_state,
        "entitlements_version": entitlements_version,
        "plan_code": new_plan_code.value if new_plan_code else None,
    }


async def sync_client_billing_from_stripe_subscription_id(
    client_id: str,
    stripe_subscription_id: str,
    *,
    event_source: str,
    update_plan: bool = True,
    additional_billing_set: Optional[Dict[str, Any]] = None,
    increment_entitlements_version: int = 0,
) -> Dict[str, Any]:
    """Retrieve subscription from Stripe API and persist (for admin backfill / repair)."""
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0, "stripe_mode": 1})
    stored_mode = (billing or {}).get("stripe_mode")
    sub_d = await retrieve_stripe_subscription_dict(
        stripe_subscription_id,
        stored_mode=stored_mode,
        client_id=client_id,
        operation="admin_subscription_sync",
    )
    return await persist_subscription_billing_from_stripe(
        client_id,
        sub_d,
        event_source=event_source,
        update_plan=update_plan,
        additional_billing_set=additional_billing_set,
        increment_entitlements_version=increment_entitlements_version,
    )
