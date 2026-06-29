"""
Operational Evidence Platform — read model: timeline, execution trees, filtered views.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database

from services.operational_evidence.constants import (
    ARCHIVED_RETENTION_TIER_EXCLUSION,
    COLLECTION_EVENTS,
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    return out


def _build_filter_query(
    *,
    category: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    job_run_id: Optional[str] = None,
    incident_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    root_execution_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    document_id: Optional[str] = None,
    notification_id: Optional[str] = None,
    environment: Optional[str] = None,
    customer_impact_classification: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if category:
        q["category"] = category
    if event_type:
        q["event_type"] = event_type
    if severity:
        q["severity"] = severity
    if status:
        q["status"] = status
    if client_id:
        q["client_id"] = client_id
    if property_id:
        q["property_id"] = property_id
    if requirement_id:
        q["requirement_id"] = requirement_id
    if job_run_id:
        q["job_run_id"] = job_run_id
    if incident_id:
        q["incident_id"] = incident_id
    if correlation_id:
        q["correlation_id"] = correlation_id
    if root_execution_id:
        q["root_execution_id"] = root_execution_id
    if execution_id:
        q["execution_id"] = execution_id
    if document_id:
        q["document_id"] = document_id
    if notification_id:
        q["notification_id"] = notification_id
    if environment:
        q["environment"] = environment
    if customer_impact_classification:
        q["customer_impact.classification"] = customer_impact_classification
    if since or until:
        q["occurred_at"] = {}
        if since:
            q["occurred_at"]["$gte"] = since
        if until:
            q["occurred_at"]["$lte"] = until
    if search:
        q["$or"] = [
            {"evidence.summary": {"$regex": search, "$options": "i"}},
            {"event_type": {"$regex": search, "$options": "i"}},
            {"correlation_id": search},
            {"root_execution_id": search},
        ]
    if not include_archived:
        q["retention.tier"] = {"$nin": list(ARCHIVED_RETENTION_TIER_EXCLUSION)}
    return q


async def list_evidence_events(
    *,
    limit: int = DEFAULT_LIMIT,
    cursor_occurred_at: Optional[str] = None,
    cursor_event_id: Optional[str] = None,
    **filters: Any,
) -> Dict[str, Any]:
    db = database.get_db()
    limit = min(max(1, limit), MAX_LIMIT)
    query = _build_filter_query(**filters)
    if cursor_occurred_at:
        if cursor_event_id:
            query["$or"] = [
                {"occurred_at": {"$lt": cursor_occurred_at}},
                {"occurred_at": cursor_occurred_at, "event_id": {"$lt": cursor_event_id}},
            ]
        else:
            query.setdefault("occurred_at", {})
            query["occurred_at"]["$lt"] = cursor_occurred_at

    total = await db[COLLECTION_EVENTS].count_documents(_build_filter_query(**filters))
    docs = (
        await db[COLLECTION_EVENTS]
        .find(query)
        .sort([("occurred_at", -1), ("event_id", -1)])
        .limit(limit)
        .to_list(limit)
    )
    items = [_serialize(d) for d in docs]
    next_cursor = None
    if len(items) == limit:
        last = items[-1]
        next_cursor = {"occurred_at": last.get("occurred_at"), "event_id": last.get("event_id")}
    return {"items": items, "total": total, "next_cursor": next_cursor}


async def get_evidence_event(event_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db[COLLECTION_EVENTS].find_one({"event_id": event_id})
    return _serialize(doc) if doc else None


async def get_execution_chain(
    *,
    root_execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    if not root_execution_id and not correlation_id:
        return {"items": [], "tree": None}
    db = database.get_db()
    filt: Dict[str, Any] = {}
    if root_execution_id:
        filt["root_execution_id"] = root_execution_id
    elif correlation_id:
        filt["correlation_id"] = correlation_id

    docs = (
        await db[COLLECTION_EVENTS]
        .find(filt)
        .sort([("execution.execution_sequence", 1), ("occurred_at", 1)])
        .limit(min(limit, 1000))
        .to_list(min(limit, 1000))
    )
    items = [_serialize(d) for d in docs]
    tree = _build_execution_tree(items)
    return {
        "items": items,
        "tree": tree,
        "root_execution_id": root_execution_id or (items[0].get("root_execution_id") if items else None),
        "correlation_id": correlation_id or (items[0].get("correlation_id") if items else None),
        "event_count": len(items),
    }


def _build_execution_tree(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {"nodes": [], "edges": [], "root_event_id": None}

    nodes = []
    edges = []
    by_id = {it["event_id"]: it for it in items if it.get("event_id")}

    for it in items:
        eid = it.get("event_id")
        rel = it.get("relationships") or {}
        nodes.append(
            {
                "event_id": eid,
                "event_type": it.get("event_type"),
                "summary": (it.get("evidence") or {}).get("summary"),
                "occurred_at": it.get("occurred_at"),
                "status": it.get("status"),
                "severity": it.get("severity"),
                "execution_depth": (it.get("execution") or {}).get("execution_depth", 0),
                "execution_sequence": (it.get("execution") or {}).get("execution_sequence", 0),
                "deep_link": (it.get("evidence") or {}).get("deep_link"),
                "child_count": sum(
                    1
                    for o in items
                    if (o.get("relationships") or {}).get("parent_event_id") == eid
                    or (o.get("relationships") or {}).get("caused_by_event_id") == eid
                ),
            }
        )
        for edge_type, target_key in (
            ("parent", "parent_event_id"),
            ("caused_by", "caused_by_event_id"),
            ("previous", "previous_event_id"),
        ):
            target = rel.get(target_key)
            if target and target in by_id:
                edges.append({"from": target, "to": eid, "type": edge_type})

    root = items[0].get("event_id")
    for it in items:
        rel = it.get("relationships") or {}
        if not rel.get("parent_event_id") and not rel.get("caused_by_event_id"):
            root = it.get("event_id")
            break

    return {"nodes": nodes, "edges": edges, "root_event_id": root}


async def get_event_chain_from_event(event_id: str) -> Dict[str, Any]:
    event = await get_evidence_event(event_id)
    if not event:
        return {"items": [], "tree": None, "event": None}
    root = event.get("root_execution_id")
    corr = event.get("correlation_id")
    chain = await get_execution_chain(root_execution_id=root, correlation_id=corr if not root else None)
    chain["selected_event_id"] = event_id
    chain["event"] = event
    return chain


async def get_intelligence_shortcuts(hours: int = 24) -> Dict[str, Any]:
    """Foundation for operational intelligence — lightweight aggregations."""
    db = database.get_db()
    since = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    # Approximate window via string compare on ISO timestamps
    from datetime import timedelta

    since_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    since_iso = since_dt.isoformat()
    active_retention = {"retention.tier": {"$nin": list(ARCHIVED_RETENTION_TIER_EXCLUSION)}}

    failed_by_type = await db[COLLECTION_EVENTS].aggregate(
        [
            {"$match": {"occurred_at": {"$gte": since_iso}, "status": "failed", **active_retention}},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
    ).to_list(10)

    retry_loops = await db[COLLECTION_EVENTS].aggregate(
        [
            {
                "$match": {
                    "occurred_at": {"$gte": since_iso},
                    "event_type": {"$in": ["NOTIFICATION_RETRY_SCHEDULED", "QUEUE_ITEM_FAILED"]},
                    **active_retention,
                }
            },
            {"$group": {"_id": "$correlation_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": 3}, "_id": {"$ne": None}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
    ).to_list(10)

    customer_impact = await db[COLLECTION_EVENTS].aggregate(
        [
            {
                "$match": {
                    "occurred_at": {"$gte": since_iso},
                    "customer_impact.classification": {"$nin": ["no_impact", "operational_only"]},
                    **active_retention,
                }
            },
            {"$group": {"_id": "$customer_impact.classification", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
    ).to_list(20)

    return {
        "window_hours": hours,
        "since": since_iso,
        "top_failure_event_types": [{"event_type": r["_id"], "count": r["count"]} for r in failed_by_type],
        "retry_loop_correlations": [{"correlation_id": r["_id"], "count": r["count"]} for r in retry_loops],
        "customer_impact_breakdown": [{"classification": r["_id"], "count": r["count"]} for r in customer_impact],
    }
