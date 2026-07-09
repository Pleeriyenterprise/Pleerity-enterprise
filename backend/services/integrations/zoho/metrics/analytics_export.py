"""Build aggregated analytics export — no row-level PII."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from database import database


async def build_analytics_export() -> Dict[str, Any]:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    period_end = now.isoformat()
    period_start = (now - timedelta(days=1)).isoformat()

    leads_created = await db.leads.count_documents(
        {"created_at": {"$gte": period_start, "$lte": period_end}}
    )
    leads_converted = await db.leads.count_documents(
        {"converted_at": {"$gte": period_start, "$lte": period_end}}
    )
    total_leads = await db.leads.count_documents({})
    conversion_rate = round((leads_converted / leads_created * 100), 2) if leads_created else 0.0

    active_subs = await db.client_billing.count_documents({"subscription_status": "active"})
    mrr_summary = 0.0
    try:
        pipeline = [
            {"$match": {"subscription_status": "active"}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$mrr_gbp", 0]}}}},
        ]
        agg = await db.client_billing.aggregate(pipeline).to_list(1)
        if agg:
            mrr_summary = float(agg[0].get("total") or 0)
    except Exception:
        mrr_summary = 0.0

    open_tickets = await db.support_tickets.count_documents({"status": {"$in": ["open", "pending"]}})
    closed_tickets = await db.support_tickets.count_documents(
        {"status": "closed", "updated_at": {"$gte": period_start}}
    )

    return {
        "period_start": period_start,
        "period_end": period_end,
        "leads_created_count": leads_created,
        "leads_converted_count": leads_converted,
        "total_leads_count": total_leads,
        "conversion_rate_pct": conversion_rate,
        "active_subscriptions_count": active_subs,
        "mrr_summary_gbp": mrr_summary,
        "support_tickets_open_count": open_tickets,
        "support_tickets_closed_count": closed_tickets,
        "export_type": "aggregated_daily",
    }
