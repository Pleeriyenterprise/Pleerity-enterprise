"""
Backfill client_billing from Stripe for existing CVP customers.

Populates: current_period_end, current_period_start, billing_cycle_anchor,
subscription_recurring_amount_pence, last_invoice_billing_breakdown (latest paid invoice).

Requires STRIPE_SECRET_KEY (or STRIPE_API_KEY). Run from repo with PYTHONPATH including backend:

  cd Pleerity-enterprise/backend && python scripts/backfill_cvp_billing_from_stripe.py

Dry-run: set DRY_RUN=1
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Ensure backend package root is importable
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import stripe  # noqa: E402

from database import database  # noqa: E402
from services.billing_line_normalization import breakdown_from_invoice_lines  # noqa: E402
from services.billing_stripe_sync_service import sync_client_billing_from_stripe_subscription_id  # noqa: E402
from services.plan_registry import plan_registry  # noqa: E402


async def backfill_one(client_id: str, stripe_sub_id: str, plan_code_str: Optional[str]) -> Dict[str, Any]:
    stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY") or "").strip()
    if not stripe.api_key:
        raise RuntimeError("STRIPE_SECRET_KEY or STRIPE_API_KEY is not set")

    dry = (os.getenv("DRY_RUN") or "").strip() in ("1", "true", "yes")
    summary: Dict[str, Any] = {}
    if not dry:
        summary = await sync_client_billing_from_stripe_subscription_id(
            client_id,
            stripe_sub_id,
            event_source="backfill_cvp_billing_from_stripe",
            update_plan=True,
        )

    set_doc: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    sub = stripe.Subscription.retrieve(stripe_sub_id, expand=["items.data.price"])
    sub_d = sub.to_dict() if hasattr(sub, "to_dict") else dict(sub)
    cust_id = sub_d.get("customer")
    if isinstance(cust_id, dict):
        cust_id = cust_id.get("id")
    if cust_id and plan_code_str and not dry:
        try:
            plan_enum = plan_registry.resolve_plan_code(plan_code_str)
            invs = stripe.Invoice.list(customer=cust_id, status="paid", limit=1, expand=["data.lines.data.price"])
            data = invs.get("data") or []
            if data:
                inv_d = data[0].to_dict() if hasattr(data[0], "to_dict") else dict(data[0])
                br = breakdown_from_invoice_lines(inv_d, plan_enum)
                if br:
                    set_doc["last_invoice_billing_breakdown"] = br
                    sp = sum(x["amount"] for x in br if x.get("type") == "subscription")
                    if sp:
                        set_doc["subscription_amount_pence"] = sp
                    await database.get_db().client_billing.update_one({"client_id": client_id}, {"$set": set_doc})
        except Exception:
            pass

    return {"client_id": client_id, "dry_run": dry, "sync_summary": summary, "invoice_enriched": bool(set_doc.get("last_invoice_billing_breakdown"))}


async def main() -> None:
    await database.connect()
    try:
        cursor = database.get_db().client_billing.find(
            {"stripe_subscription_id": {"$exists": True, "$nin": [None, ""]}},
            {"_id": 0, "client_id": 1, "stripe_subscription_id": 1, "current_plan_code": 1},
        )
        rows = await cursor.to_list(5000)
        print(f"Found {len(rows)} billing rows with stripe_subscription_id")
        for row in rows:
            cid = row.get("client_id")
            sid = row.get("stripe_subscription_id")
            pc = row.get("current_plan_code")
            if not cid or not sid:
                continue
            try:
                r = await backfill_one(cid, sid, pc)
                print(r)
            except Exception as e:
                print(f"FAIL client_id={cid} sub={sid}: {e}")
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
