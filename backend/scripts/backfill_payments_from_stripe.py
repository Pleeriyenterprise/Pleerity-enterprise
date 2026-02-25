"""
Backfill payments collection from Stripe for Revenue Analytics.

Use when the payments collection was introduced after live Stripe usage:
historical invoice.paid events were not written to payments. This script
pulls paid subscription invoices from Stripe and inserts normalized payment
records (idempotent by stripe_event_id = "backfill-inv-{invoice_id}").

Requirements:
- STRIPE_SECRET_KEY or STRIPE_API_KEY in env
- MONGO_URL, DB_NAME in env
- Run from backend directory: python scripts/backfill_payments_from_stripe.py

Idempotent: re-running skips invoices already present (duplicate stripe_event_id).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import stripe
from pymongo.errors import DuplicateKeyError

from database import database

logging = __import__("logging")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Stripe key (same as stripe_webhook_service / stripe_service)
stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY") or "").strip()


async def backfill_subscription_payments(limit: int = 500) -> dict:
    """
    List paid subscription invoices from Stripe and insert into payments.
    Returns {"inserted": n, "skipped_no_client": m, "skipped_duplicate": k, "errors": [...]}.
    """
    if not stripe.api_key:
        return {"inserted": 0, "skipped_no_client": 0, "skipped_duplicate": 0, "errors": ["STRIPE_SECRET_KEY/STRIPE_API_KEY not set"]}

    db = database.get_db()
    if not db:
        return {"inserted": 0, "skipped_no_client": 0, "skipped_duplicate": 0, "errors": ["Database not available"]}

    inserted = 0
    skipped_no_client = 0
    skipped_duplicate = 0
    errors = []

    try:
        # List paid invoices (subscription invoices have subscription set)
        invoices = stripe.Invoice.list(status="paid", limit=min(100, limit))
        count = 0
        for inv in invoices.auto_paging_iterate():
            if count >= limit:
                break
            count += 1
            inv_id = inv.get("id")
            if not inv_id:
                continue
            subscription_id = inv.get("subscription")
            if not subscription_id:
                continue  # one-time invoice; optional: could map via metadata later
            customer_id = inv.get("customer")
            if isinstance(customer_id, dict):
                customer_id = customer_id.get("id") if customer_id else None
            if not customer_id:
                continue
            # Resolve client_id from our billing record
            billing = await db.client_billing.find_one(
                {"stripe_customer_id": customer_id},
                {"_id": 0, "client_id": 1},
            )
            if not billing or not billing.get("client_id"):
                skipped_no_client += 1
                continue
            client_id = billing["client_id"]
            amount = int(inv.get("amount_paid") or 0)
            currency = (inv.get("currency") or "gbp").lower()
            charge_id = inv.get("charge")
            if isinstance(charge_id, dict):
                charge_id = charge_id.get("id") if charge_id else None
            created_ts = inv.get("created")
            created_at = datetime.fromtimestamp(created_ts, tz=timezone.utc) if created_ts else datetime.now(timezone.utc)
            stripe_event_id = f"backfill-inv-{inv_id}"
            doc = {
                "client_id": client_id,
                "stripe_event_id": stripe_event_id,
                "amount": amount,
                "currency": currency,
                "type": "subscription",
                "status": "paid",
                "created_at": created_at,
                "stripe_invoice_id": inv_id,
            }
            if charge_id:
                doc["stripe_charge_id"] = charge_id
            try:
                await db.payments.insert_one(doc)
                inserted += 1
            except DuplicateKeyError:
                skipped_duplicate += 1
    except Exception as e:
        errors.append(str(e))
        logger.exception("Backfill iteration failed")

    return {
        "inserted": inserted,
        "skipped_no_client": skipped_no_client,
        "skipped_duplicate": skipped_duplicate,
        "errors": errors,
    }


async def main():
    await database.connect()
    logger.info("Backfill payments from Stripe (subscription invoices only)")
    if not stripe.api_key:
        logger.error("STRIPE_SECRET_KEY or STRIPE_API_KEY not set. Exiting.")
        await database.close()
        return
    limit = 500
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
    result = await backfill_subscription_payments(limit=limit)
    logger.info("Result: inserted=%s skipped_no_client=%s skipped_duplicate=%s errors=%s",
                result["inserted"], result["skipped_no_client"], result["skipped_duplicate"], result["errors"])
    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
