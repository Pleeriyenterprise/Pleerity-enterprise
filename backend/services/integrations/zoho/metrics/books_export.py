"""Build Stripe/Pleerity finance summary for Books export — read-only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from database import database


async def build_books_export() -> Dict[str, Any]:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    period_start = (now - timedelta(days=30)).isoformat()
    period_end = now.isoformat()

    active_count = await db.client_billing.count_documents({"subscription_status": "active"})
    mrr_total = 0.0
    try:
        pipeline = [
            {"$match": {"subscription_status": "active"}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$mrr_gbp", 0]}}}},
        ]
        agg = await db.client_billing.aggregate(pipeline).to_list(1)
        if agg:
            mrr_total = float(agg[0].get("total") or 0)
    except Exception:
        pass

    return {
        "export_type": "stripe_revenue_summary",
        "period_start": period_start,
        "period_end": period_end,
        "line_items": [
            {
                "type": "subscription_revenue_summary",
                "description": "Pleerity Stripe subscription MRR summary (read-only export)",
                "amount_gbp": mrr_total,
                "active_subscriptions": active_count,
            },
        ],
        "note": "Stripe remains payment SoR. This export is for Pleerity Ltd recognition only.",
    }
