"""
First-party product analytics (Mongo). No third-party SDK; events drive retention funnels.

Inserts are non-blocking for callers (failures logged, do not raise).

Today page — canonical event semantics (avoid mixing inbox visibility with domain completion):

- TODAY_PAGE_VIEWED: Successful Today payload rendered (client received 200 + usable body).
- TODAY_PAGE_REQUESTED: Client started a Today fetch (diagnostic; use with LOAD_FAILED to spot errors).
- TODAY_PAGE_LOAD_FAILED: Today fetch failed before VIEWED (e.g. network/5xx); not “no tasks”.
- TODAY_TASK_CLICKED: User engaged the task title (exploration), not necessarily workflow.
- TODAY_TASK_COMPLETED: **Inbox-only** — user marked the item reviewed/hidden from open lists via Today
  visibility (e.g. mark-reviewed). Does **not** mean the underlying requirement, work order, or approval
  is satisfied or closed. Do not treat as business-object resolution.
- TODAY_TASK_SNOOZED / TODAY_TASK_DISMISSED: Inbox visibility only (same caveat as COMPLETED).
- TODAY_PRIMARY_ACTION_TRIGGERED: User invoked a **workflow-oriented** control on Today (business action
  button, implicit “Next step” primary CTA, or risk follow-up). Pair with domain audit logs / outcomes
  for true completion metrics.

Dashboard cutover: legacy names ``today_*`` below remain allowlisted for **historical** aggregates only.
Cutover to canonical ``TODAY_*`` names for new client emissions: **2026-04-02**. Do not dual-emit legacy
and canonical for the same user gesture unless a specific report still depends on the old series.
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
        # Today page (canonical names)
        "TODAY_PAGE_VIEWED",
        "TODAY_PAGE_REQUESTED",
        "TODAY_PAGE_LOAD_FAILED",
        "TODAY_TASK_CLICKED",
        "TODAY_TASK_COMPLETED",
        "TODAY_TASK_SNOOZED",
        "TODAY_TASK_DISMISSED",
        "TODAY_PRIMARY_ACTION_TRIGGERED",
        # Legacy Today / product events (retain for historical aggregates)
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
        # Portal loading UX telemetry
        "portal_loading_started",
        "portal_loading_completed",
    }
)


def _sanitize_props(raw: Optional[Dict[str, Any]], max_keys: int = 16) -> Dict[str, Any]:
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
    *,
    role: Optional[str] = None,
) -> None:
    if event not in ALLOWED_EVENTS:
        logger.debug("analytics: ignored unknown event %s", event)
        return
    try:
        db = database.get_db()
        ts = datetime.now(timezone.utc).isoformat()
        doc = {
            "client_id": client_id,
            "portal_user_id": portal_user_id,
            "user_id": portal_user_id,
            "role": (role or "client")[:32],
            "event": event,
            "properties": _sanitize_props(properties),
            "path": (path or "")[:500],
            "timestamp": ts,
            "created_at": ts,
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
