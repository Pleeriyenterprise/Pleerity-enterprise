"""
First-party product analytics (Mongo). No third-party SDK; events drive retention funnels.

Inserts are non-blocking for callers (failures logged, do not raise).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database

logger = logging.getLogger(__name__)

COLLECTION = "product_analytics_events"

ALLOWED_EVENTS = frozenset(
    {
        "today_opened",
        "priority_viewed",
        "dashboard_viewed",
        "reports_opened",
        "evidence_pack_requested",
        "evidence_pack_downloaded",
        "activity_since_viewed",
        "today_task_snoozed",
        "today_task_dismissed",
        "today_task_marked_reviewed",
        "today_task_restored",
        "today_primary_cta_clicked",
        "today_secondary_nav_clicked",
        "today_risk_follow_up_started",
        "today_compliance_job_started",
    }
)


def _sanitize_props(raw: Optional[Dict[str, Any]], max_keys: int = 12) -> Dict[str, Any]:
    if not raw or not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for i, (k, v) in enumerate(raw.items()):
        if i >= max_keys:
            break
        if not isinstance(k, str) or len(k) > 64:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict):
            out[k] = _sanitize_props(v, max_keys=4)
        else:
            out[k] = str(v)[:500]
    return out


async def record_event(
    client_id: str,
    portal_user_id: Optional[str],
    event: str,
    properties: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
) -> None:
    if event not in ALLOWED_EVENTS:
        logger.debug("analytics: ignored unknown event %s", event)
        return
    try:
        db = database.get_db()
        doc = {
            "client_id": client_id,
            "portal_user_id": portal_user_id,
            "event": event,
            "properties": _sanitize_props(properties),
            "path": (path or "")[:500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db[COLLECTION].insert_one(doc)
    except Exception as e:
        logger.warning("analytics insert failed: %s", e)


async def summarize_client_events(client_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Aggregate allowlisted first-party events for the client (dashboard-style, not a warehouse).
    """
    days = max(1, min(int(days), 90))
    db = database.get_db()
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since_dt.isoformat()
    try:
        pipeline: List[Dict[str, Any]] = [
            {"$match": {"client_id": client_id, "created_at": {"$gte": since_iso}}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        rows = await db[COLLECTION].aggregate(pipeline).to_list(length=50)
    except Exception as e:
        logger.warning("analytics summarize failed: %s", e)
        rows = []
    total = sum(int(r.get("count") or 0) for r in rows)
    return {
        "period_days": days,
        "since": since_iso,
        "total_events": total,
        "by_event": [{"event": r.get("_id"), "count": int(r.get("count") or 0)} for r in rows if r.get("_id")],
        "allowed_events": sorted(ALLOWED_EVENTS),
    }
