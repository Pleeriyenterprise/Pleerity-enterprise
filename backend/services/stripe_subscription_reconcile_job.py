"""
Scheduled reconciliation: pull subscription state from Stripe into ``client_billing`` / lifecycle.

Catches missed webhooks and subscription status drift (e.g. past_due after renewal failure).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from database import database
from services.billing_stripe_sync_service import sync_client_billing_from_stripe_subscription_id
from services.subscription_lifecycle_service import sync_subscription_lifecycle
from services.billing_reconciliation_service import clear_billing_reconciliation_needed

logger = logging.getLogger(__name__)


async def reconcile_all_stripe_subscriptions() -> Dict[str, Any]:
    key = (os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or "").strip()
    if not key:
        return {"reconciled": 0, "errors": 0, "attempted": 0, "skipped": "no_stripe_key"}

    raw = (os.environ.get("STRIPE_SUBSCRIPTION_RECONCILE_BATCH") or "40").strip()
    try:
        lim = max(1, min(int(raw), 200))
    except ValueError:
        lim = 40

    db = database.get_db()
    cursor = (
        db.client_billing.find(
            {
                "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
                "$or": [
                    {"billing_reconciliation_needed": True},
                    {"billing_sync_state": {"$ne": "ok"}},
                    {"billing_sync_state": {"$exists": False}},
                ],
            },
            {"_id": 0, "client_id": 1, "stripe_subscription_id": 1},
        )
        .sort([("billing_last_synced_at", 1), ("updated_at", 1)])
        .limit(lim)
    )
    rows = await cursor.to_list(lim)
    ok = 0
    err = 0
    for row in rows:
        cid = row.get("client_id")
        sid = (row.get("stripe_subscription_id") or "").strip()
        if not cid or not sid:
            continue
        try:
            await sync_client_billing_from_stripe_subscription_id(
                cid,
                sid,
                event_source="scheduled_stripe_subscription_reconcile",
                update_plan=True,
                increment_entitlements_version=0,
            )
            await sync_subscription_lifecycle(cid, bump_version=False)
            await clear_billing_reconciliation_needed(client_id=cid, reason="scheduled_reconcile_completed")
            ok += 1
        except Exception as ex:
            err += 1
            logger.warning(
                "stripe reconcile failed client_id=%s subscription_id=%s: %s",
                cid,
                sid,
                ex,
            )
    logger.info(
        "stripe_subscription_reconcile batch attempted=%s ok=%s err=%s",
        len(rows),
        ok,
        err,
    )
    return {"reconciled": ok, "errors": err, "attempted": len(rows)}
