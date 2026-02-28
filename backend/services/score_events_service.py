"""
Score Events Service - Audit-grade log for score trend and "What Changed" timeline.

Stores every score-affecting event (who/when/what) for:
- GET /api/client/score/timeline (90-day trend from SCORE_RECALCULATED)
- GET /api/client/score/changes (What Changed list with delta, deep-link ids)

Event types: DOCUMENT_UPLOADED, DOCUMENT_CONFIRMED, REQUIREMENT_STATUS_CHANGED,
PROPERTY_ADDED, PROPERTY_UPDATED, REMINDER_SENT, SCORE_RECALCULATED.
"""
from database import database
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Event types (must match task schema)
EVENT_DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
EVENT_DOCUMENT_CONFIRMED = "DOCUMENT_CONFIRMED"
EVENT_REQUIREMENT_STATUS_CHANGED = "REQUIREMENT_STATUS_CHANGED"
EVENT_PROPERTY_ADDED = "PROPERTY_ADDED"
EVENT_PROPERTY_UPDATED = "PROPERTY_UPDATED"
EVENT_REMINDER_SENT = "REMINDER_SENT"
EVENT_SCORE_RECALCULATED = "SCORE_RECALCULATED"

ACTOR_ROLE_CLIENT = "client"
ACTOR_ROLE_ADMIN = "admin"
ACTOR_ROLE_SYSTEM = "system"

# Human-readable titles for "What Changed" list
EVENT_TITLES = {
    EVENT_DOCUMENT_UPLOADED: "Document uploaded",
    EVENT_DOCUMENT_CONFIRMED: "Certificate confirmed",
    EVENT_REQUIREMENT_STATUS_CHANGED: "Requirement updated",
    EVENT_PROPERTY_ADDED: "Property added",
    EVENT_PROPERTY_UPDATED: "Property updated",
    EVENT_REMINDER_SENT: "Reminder sent",
    EVENT_SCORE_RECALCULATED: "Score recalculated",
}


async def write_score_event(
    client_id: str,
    event_type: str,
    *,
    actor_user_id: Optional[str] = None,
    actor_role: str = ACTOR_ROLE_SYSTEM,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    score_before: Optional[int] = None,
    score_after: Optional[int] = None,
    delta: Optional[int] = None,
) -> None:
    """
    Append one score event. Safe to call from routes and job_runner.
    Multi-tenant: always pass client_id; queries filter by it.
    """
    if actor_role not in (ACTOR_ROLE_CLIENT, ACTOR_ROLE_ADMIN, ACTOR_ROLE_SYSTEM):
        actor_role = ACTOR_ROLE_SYSTEM
    now = datetime.now(timezone.utc)
    doc = {
        "client_id": client_id,
        "actor_user_id": actor_user_id,
        "actor_role": actor_role,
        "event_type": event_type,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "document_id": document_id,
        "metadata": metadata or {},
        "score_before": score_before,
        "score_after": score_after,
        "delta": delta,
        "created_at": now,
    }
    db = database.get_db()
    await db.score_events.insert_one(doc)
    logger.debug("score_event written client_id=%s event_type=%s", client_id, event_type)


async def get_timeline(
    client_id: str,
    days: int = 90,
    interval: str = "week",
) -> Dict[str, Any]:
    """
    Build timeline points from SCORE_RECALCULATED events: latest score per bucket.
    If no events, return current score as single point (flat line).
    """
    from services.compliance_score import calculate_compliance_score

    db = database.get_db()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    interval_lower = (interval or "week").lower()
    if interval_lower == "day":
        date_fmt = "%Y-%m-%d"
    else:
        date_fmt = "%Y-%m-%d"

    cursor = db.score_events.find(
        {
            "client_id": client_id,
            "event_type": EVENT_SCORE_RECALCULATED,
            "created_at": {"$gte": start},
            "score_after": {"$ne": None},
        },
        {"_id": 0, "created_at": 1, "score_after": 1},
    ).sort("created_at", 1)
    events = await cursor.to_list(5000)

    # Bucket by date (day or week start)
    buckets: Dict[str, int] = {}
    for e in events:
        ts = e["created_at"]
        if hasattr(ts, "timestamp"):
            t = ts
        else:
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
            except Exception:
                continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if interval_lower == "week":
            weekday = t.weekday()
            start_of_week = t - timedelta(days=weekday)
            key = start_of_week.strftime(date_fmt)
        else:
            key = t.strftime(date_fmt)
        buckets[key] = e["score_after"]

    sorted_dates = sorted(buckets.keys())
    points = [{"date": d, "score": buckets[d]} for d in sorted_dates]

    last_updated_at = None
    if events:
        last_ts = events[-1].get("created_at")
        if last_ts:
            last_updated_at = last_ts.isoformat() if hasattr(last_ts, "isoformat") else str(last_ts)

    if not points:
        try:
            score_data = await calculate_compliance_score(client_id)
            current = score_data.get("score")
            if current is not None:
                today = now.strftime(date_fmt)
                points = [{"date": today, "score": current}]
            last_updated_at = score_data.get("score_last_calculated_at")
            if isinstance(last_updated_at, datetime):
                last_updated_at = last_updated_at.isoformat()
        except Exception as e:
            logger.debug("Timeline fallback score failed: %s", e)

    return {
        "client_id": client_id,
        "days": days,
        "interval": interval_lower,
        "points": points,
        "last_updated_at": last_updated_at,
    }


def _event_to_title(event_type: str, metadata: Optional[Dict] = None) -> str:
    return EVENT_TITLES.get(event_type, event_type.replace("_", " ").title())


# Customer-friendly text for "What Changed" (trigger_reason in SCORE_RECALCULATED)
_TRIGGER_REASON_FRIENDLY = {
    "DOC_DELETED": "Document removed",
    "ADMIN_DELETE": "Document removed",
    "DOC_UPLOADED": "Document uploaded",
    "ADMIN_UPLOAD": "Document uploaded (by admin)",
    "DOC_STATUS_CHANGED": "Document status updated",
    "AI_APPLIED": "Certificate details applied",
    "EXPIRY_JOB": "Expiry dates updated",
    "PROVISIONING": "Portfolio updated",
    "PROPERTY_CREATED": "Property added",
    "PROPERTY_UPDATED": "Property updated",
    "LAZY_BACKFILL": "Score refreshed",
}


def _trigger_reason_to_friendly_detail(trigger_reason: Optional[str]) -> Optional[str]:
    """Return customer-friendly description for SCORE_RECALCULATED trigger_reason."""
    if not trigger_reason or not isinstance(trigger_reason, str):
        return None
    s = trigger_reason.strip()
    return _TRIGGER_REASON_FRIENDLY.get(s) or _TRIGGER_REASON_FRIENDLY.get(s.upper()) or None


async def get_changes(
    client_id: str,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    List recent score events for "What Changed" with human-readable title/details,
    delta and score_after when available.
    """
    db = database.get_db()
    cursor = db.score_events.find(
        {"client_id": client_id},
        {
            "_id": 0,
            "created_at": 1,
            "event_type": 1,
            "property_id": 1,
            "requirement_id": 1,
            "document_id": 1,
            "metadata": 1,
            "delta": 1,
            "score_after": 1,
        },
    ).sort("created_at", -1).limit(max(1, min(limit, 100)))
    events = await cursor.to_list(limit)

    property_ids = list({e["property_id"] for e in events if e.get("property_id")})
    prop_names: Dict[str, str] = {}
    if property_ids:
        props = await db.properties.find(
            {"property_id": {"$in": property_ids}, "client_id": client_id},
            {"_id": 0, "property_id": 1, "nickname": 1, "address_line_1": 1},
        ).to_list(100)
        for p in props:
            prop_names[p["property_id"]] = p.get("nickname") or p.get("address_line_1") or p["property_id"]

    items = []
    for e in events:
        created = e.get("created_at")
        created_at_iso = created.isoformat() if hasattr(created, "isoformat") else str(created) if created else None
        event_type = e.get("event_type", "")
        title = _event_to_title(event_type, e.get("metadata"))
        details = ""
        meta = e.get("metadata") or {}
        prop_id = e.get("property_id")
        prop_name = prop_names.get(prop_id, "") if prop_id else ""
        if event_type == EVENT_DOCUMENT_CONFIRMED:
            req_type = (meta.get("requirement_type") or meta.get("requirement_code") or "Certificate").replace("_", " ")
            expiry = meta.get("expiry_date") or meta.get("due_date")
            if prop_name:
                details = prop_name
                if expiry:
                    details += f" • Expires {expiry[:10]}" if isinstance(expiry, str) and len(expiry) >= 10 else f" • Expires {expiry}"
            else:
                details = req_type + (f" • Expires {expiry}" if expiry else "")
        elif event_type == EVENT_DOCUMENT_UPLOADED:
            req_type = (meta.get("requirement_type") or meta.get("requirement_code") or "Document").replace("_", " ")
            details = (prop_name + " • " if prop_name else "") + req_type
        elif event_type == EVENT_REQUIREMENT_STATUS_CHANGED:
            before = meta.get("status_before") or meta.get("before")
            after = meta.get("status_after") or meta.get("after")
            details = (prop_name + " • " if prop_name else "") + (f"{before or '?'} → {after or '?'}" if before or after else "Status updated")
        elif event_type in (EVENT_PROPERTY_ADDED, EVENT_PROPERTY_UPDATED):
            details = prop_name or prop_id or "Property"
        elif event_type == EVENT_SCORE_RECALCULATED:
            details = _trigger_reason_to_friendly_detail(meta.get("trigger_reason")) or "Recalculation completed"
        else:
            details = prop_name or (prop_id or "")

        items.append({
            "created_at": created_at_iso,
            "event_type": event_type,
            "title": title,
            "details": details or None,
            "delta": e.get("delta"),
            "score_after": e.get("score_after"),
            "property_id": e.get("property_id"),
            "requirement_id": e.get("requirement_id"),
            "document_id": e.get("document_id"),
        })

    return {"items": items}
