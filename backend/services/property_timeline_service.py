"""
Property Timeline Service - Unified chronological event stream for a property.

Merges: score_ledger_events, score_change_log, work_orders (synthetic "created" events).
Used by GET /api/portfolio/properties/:propertyId/timeline.
"""
from database import database
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Ledger trigger_type -> timeline category
TRIGGER_TO_CATEGORY = {
    "DOCUMENT_UPLOADED": "EVIDENCE",
    "DOCUMENT_REMOVED": "EVIDENCE",
    "DOCUMENT_STATUS_CHANGED": "EVIDENCE",
    "CERT_DETAILS_CONFIRMED": "EVIDENCE",
    "REQUIREMENT_STATUS_CHANGED": "COMPLIANCE",
    "SCHEDULED_RECALC": "COMPLIANCE",
    "PROPERTY_ADDED": "SYSTEM",
    "PROPERTY_UPDATED": "SYSTEM",
}
DEFAULT_CATEGORY = "SCORE_RISK"

# Categories that can be filtered
VALID_CATEGORIES = {"EVIDENCE", "COMPLIANCE", "MAINTENANCE", "SCORE_RISK", "SYSTEM"}
VALID_ACTORS = {"user", "admin", "system"}


def _parse_iso(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if hasattr(ts, "timestamp"):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _ledger_to_item(e: Dict[str, Any], index: int) -> Dict[str, Any]:
    created = e.get("created_at")
    ts = _parse_iso(created)
    ts_str = created if isinstance(created, str) else (ts.isoformat() if ts else None)
    trigger_type = e.get("trigger_type") or "SCHEDULED_RECALC"
    trigger_label = e.get("trigger_label") or "Score recalculated"
    category = TRIGGER_TO_CATEGORY.get(trigger_type, DEFAULT_CATEGORY)
    actor_type = (e.get("actor_type") or "system").lower()
    delta = e.get("delta")
    return {
        "id": f"ledger:{ts_str}:{index}" if ts_str else f"ledger:{index}",
        "timestamp": ts_str,
        "category": category,
        "eventType": trigger_type,
        "title": trigger_label,
        "description": _ledger_description(e),
        "actorType": actor_type if actor_type in VALID_ACTORS else "system",
        "actorLabel": _actor_label(actor_type),
        "linkedEntityType": _ledger_linked_type(e),
        "linkedEntityId": e.get("document_id") or e.get("requirement_id"),
        "linkedEntityLabel": trigger_label,
        "impact": {"scoreDelta": delta, "riskChange": None} if delta is not None else None,
        "source": "ledger",
    }


def _ledger_description(e: Dict[str, Any]) -> str:
    trigger_type = e.get("trigger_type")
    if trigger_type in ("CERT_DETAILS_CONFIRMED", "DOCUMENT_UPLOADED", "DOCUMENT_REMOVED", "DOCUMENT_STATUS_CHANGED"):
        delta = e.get("delta")
        if delta is not None and delta != 0:
            return f"Score {'+' if delta > 0 else ''}{int(delta)}."
        return e.get("trigger_label") or "Evidence or certificate updated."
    if trigger_type in ("REQUIREMENT_STATUS_CHANGED", "SCHEDULED_RECALC"):
        return e.get("trigger_label") or "Compliance status or expiry updated."
    if trigger_type in ("PROPERTY_ADDED", "PROPERTY_UPDATED"):
        return e.get("trigger_label") or "Property updated."
    delta = e.get("delta")
    if delta is not None and delta != 0:
        return f"Score {'+' if delta > 0 else ''}{int(delta)}."
    return e.get("trigger_label") or "Score recalculated."


def _actor_label(actor_type: str) -> str:
    if actor_type == "user":
        return "You"
    if actor_type == "admin":
        return "Admin"
    return "System"


def _ledger_linked_type(e: Dict[str, Any]) -> Optional[str]:
    if e.get("document_id"):
        return "DOCUMENT"
    if e.get("requirement_id"):
        return "REQUIREMENT"
    return None


def _score_change_to_item(e: Dict[str, Any], index: int) -> Dict[str, Any]:
    created = e.get("created_at")
    ts = _parse_iso(created)
    ts_str = created if isinstance(created, str) else (ts.isoformat() if ts else None)
    reason = e.get("reason") or "Score recalculated"
    delta = e.get("delta")
    return {
        "id": f"score_log:{ts_str}:{index}" if ts_str else f"score_log:{index}",
        "timestamp": ts_str,
        "category": "SCORE_RISK",
        "eventType": "SCORE_RECALCULATED",
        "title": "Score changed",
        "description": reason,
        "actorType": "system",
        "actorLabel": "System",
        "linkedEntityType": None,
        "linkedEntityId": None,
        "linkedEntityLabel": None,
        "impact": {"scoreDelta": delta, "riskChange": None} if delta is not None else None,
        "source": "score_change_log",
    }


def _work_order_to_item(wo: Dict[str, Any]) -> Dict[str, Any]:
    created = wo.get("created_at")
    ts_str = created if isinstance(created, str) else None
    desc = (wo.get("description") or "Issue reported").strip()[:200]
    wo_id = wo.get("work_order_id")
    return {
        "id": f"wo:{wo_id}" if wo_id else f"wo:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": "WORK_ORDER_CREATED",
        "title": "Issue reported",
        "description": desc or "Work order created.",
        "actorType": "user",
        "actorLabel": "You",
        "linkedEntityType": "WORK_ORDER",
        "linkedEntityId": wo_id,
        "linkedEntityLabel": f"Work Order #{str(wo_id)[:8]}" if wo_id else "Work order",
        "impact": None,
        "source": "work_orders",
    }


def _work_order_completed_to_item(wo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Timeline item for work order completion (when completed_at is set)."""
    completed_at = wo.get("completed_at")
    if not completed_at:
        return None
    ts_str = completed_at if isinstance(completed_at, str) else None
    wo_id = wo.get("work_order_id")
    desc = (wo.get("description") or "Work completed").strip()[:200]
    return {
        "id": f"wo_done:{wo_id}" if wo_id else f"wo_done:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": "WORK_ORDER_COMPLETED",
        "title": "Work order completed",
        "description": desc or "Work order completed.",
        "actorType": "user",
        "actorLabel": "You",
        "linkedEntityType": "WORK_ORDER",
        "linkedEntityId": wo_id,
        "linkedEntityLabel": f"Work Order #{str(wo_id)[:8]}" if wo_id else "Work order",
        "impact": None,
        "source": "work_orders",
    }


def _work_order_assigned_to_item(wo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Timeline item for contractor assigned (when contractor_id and assigned_at are set)."""
    assigned_at = wo.get("assigned_at")
    if not assigned_at or not wo.get("contractor_id"):
        return None
    ts_str = assigned_at if isinstance(assigned_at, str) else None
    wo_id = wo.get("work_order_id")
    return {
        "id": f"wo_assigned:{wo_id}" if wo_id else f"wo_assigned:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": "WORK_ORDER_ASSIGNED",
        "title": "Contractor assigned",
        "description": "A contractor was assigned to this work order.",
        "actorType": "user",
        "actorLabel": "You",
        "linkedEntityType": "WORK_ORDER",
        "linkedEntityId": wo_id,
        "linkedEntityLabel": f"Work Order #{str(wo_id)[:8]}" if wo_id else "Work order",
        "impact": None,
        "source": "work_orders",
    }


def _asset_event_to_item(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Timeline item from asset_events (issue_created, repair_completed, document_linked, etc.)."""
    ts = ev.get("timestamp")
    ts_str = ts if isinstance(ts, str) else None
    event_type = (ev.get("event_type") or "").replace("_", " ").title()
    desc = (ev.get("description") or event_type or "Asset activity").strip()[:200]
    ev_id = ev.get("event_id")
    return {
        "id": f"asset_ev:{ev_id}" if ev_id else f"asset_ev:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": (ev.get("event_type") or "ASSET_EVENT").upper(),
        "title": event_type or "Asset activity",
        "description": desc or "Asset event.",
        "actorType": "system",
        "actorLabel": "System",
        "linkedEntityType": "ASSET",
        "linkedEntityId": ev.get("asset_id"),
        "linkedEntityLabel": desc or event_type,
        "impact": None,
        "source": "asset_events",
    }


async def get_property_timeline(
    client_id: str,
    property_id: str,
    *,
    category: Optional[str] = None,
    actor_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return a unified timeline for the property: ledger + score_change_log + work_orders.
    Sorted by timestamp descending. Filters applied after merge.
    """
    from services.score_ledger_service import list_ledger_export

    def _normalize_date_range(from_d: Optional[str], to_d: Optional[str]):
        start, end = None, None
        if from_d and from_d.strip() and len(from_d.strip()) >= 10 and from_d.strip()[4] == "-":
            start = from_d.strip()[:10] + "T00:00:00.000Z"
        if to_d and to_d.strip() and len(to_d.strip()) >= 10 and to_d.strip()[4] == "-":
            end = to_d.strip()[:10] + "T23:59:59.999Z"
        return start, end

    db = database.get_db()

    # 1) Ledger entries for this property (no pagination on export; we cap limit)
    ledger_items = await list_ledger_export(
        client_id=client_id,
        property_id=property_id,
        from_date=from_date,
        to_date=to_date,
        limit=500,
    )
    # 2) Score change log (simpler entries; may overlap with ledger - we include both and sort)
    start, end = _normalize_date_range(from_date, to_date)
    score_query = {"property_id": property_id, "client_id": client_id}
    if start or end:
        score_query["created_at"] = {}
        if start:
            score_query["created_at"]["$gte"] = start
        if end:
            score_query["created_at"]["$lte"] = end
    score_log = await db.score_change_log.find(
        score_query,
        {"_id": 0, "created_at": 1, "previous_score": 1, "new_score": 1, "delta": 1, "reason": 1},
    ).sort("created_at", -1).limit(100).to_list(100)

    # 3) Work orders for this property (synthetic "created" + "completed" + "assigned" events)
    wo_list = await db.work_orders.find(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "work_order_id": 1, "description": 1, "created_at": 1, "completed_at": 1, "contractor_id": 1, "assigned_at": 1},
    ).sort("created_at", -1).limit(100).to_list(100)

    # Build normalized items
    items: List[Dict[str, Any]] = []
    for i, e in enumerate(ledger_items):
        item = _ledger_to_item(e, i)
        if category and item["category"] != category:
            continue
        if actor_type and item["actorType"] != actor_type.lower():
            continue
        items.append(item)

    for i, e in enumerate(score_log):
        item = _score_change_to_item(e, i)
        if category and item["category"] != category:
            continue
        if actor_type and item["actorType"] != actor_type.lower():
            continue
        items.append(item)

    for wo in wo_list:
        item = _work_order_to_item(wo)
        if category and item["category"] != category:
            pass
        elif actor_type and item["actorType"] != actor_type.lower():
            pass
        else:
            items.append(item)
        completed_item = _work_order_completed_to_item(wo)
        if completed_item:
            if category and completed_item["category"] != category:
                pass
            elif actor_type and completed_item["actorType"] != actor_type.lower():
                pass
            else:
                items.append(completed_item)
        assigned_item = _work_order_assigned_to_item(wo)
        if assigned_item:
            if category and assigned_item["category"] != category:
                pass
            elif actor_type and assigned_item["actorType"] != actor_type.lower():
                pass
            else:
                items.append(assigned_item)

    # 4) Asset events for this property (issue_created, repair_completed, document_linked, etc.)
    try:
        from services.property_assets_service import list_asset_events_for_property
        asset_ev_list = await list_asset_events_for_property(
            property_id=property_id,
            client_id=client_id,
            limit=100,
            from_date=start,
            to_date=end,
        )
        for ev in asset_ev_list:
            item = _asset_event_to_item(ev)
            if category and item["category"] != category:
                continue
            if actor_type and item["actorType"] != actor_type.lower():
                continue
            items.append(item)
    except Exception as e:
        logger.debug("Timeline asset_events skip: %s", e)

    # Sort by timestamp descending
    def sort_key(x):
        t = x.get("timestamp") or ""
        return t

    items.sort(key=sort_key, reverse=True)

    # Cursor pagination: cursor is the last timestamp seen
    if cursor:
        items = [x for x in items if (x.get("timestamp") or "") < cursor]
    items = items[: limit + 1]
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    next_cursor = items[-1]["timestamp"] if items and has_more else None

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": len(items) if not cursor else None,
    }
