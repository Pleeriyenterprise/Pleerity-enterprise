"""
Portfolio-scoped operational evidence view — tenant-wide investigation surface.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from database import database

from services.operational_evidence.constants import (
    ARCHIVED_RETENTION_TIER_EXCLUSION,
    COLLECTION_EVENTS,
)
from services.operational_evidence.query_service import list_evidence_events
from services.operational_evidence.story_service import build_operational_story


async def get_portfolio_evidence_view(
    client_id: str,
    *,
    hours: int = 168,
    limit: int = 50,
    include_archived: bool = False,
) -> Dict[str, Any]:
    since_dt = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 720)))
    since_iso = since_dt.isoformat()
    db = database.get_db()

    match: Dict[str, Any] = {
        "client_id": client_id,
        "occurred_at": {"$gte": since_iso},
    }
    if not include_archived:
        match["retention.tier"] = {"$nin": list(ARCHIVED_RETENTION_TIER_EXCLUSION)}

    by_category = await db[COLLECTION_EVENTS].aggregate(
        [
            {"$match": match},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 15},
        ]
    ).to_list(15)

    by_impact = await db[COLLECTION_EVENTS].aggregate(
        [
            {
                "$match": {
                    **match,
                    "customer_impact.classification": {"$nin": ["no_impact", "operational_only"]},
                }
            },
            {"$group": {"_id": "$customer_impact.classification", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
    ).to_list(20)

    high_impact = (
        await db[COLLECTION_EVENTS]
        .find(
            {
                **match,
                "customer_impact.classification": {"$nin": ["no_impact", "operational_only"]},
            },
            {
                "_id": 0,
                "event_id": 1,
                "event_type": 1,
                "occurred_at": 1,
                "severity": 1,
                "status": 1,
                "category": 1,
                "evidence.summary": 1,
                "customer_impact": 1,
                "property_id": 1,
            },
        )
        .sort("occurred_at", -1)
        .limit(10)
        .to_list(10)
    )

    timeline = await list_evidence_events(
        limit=limit,
        client_id=client_id,
        since=since_iso,
        include_archived=include_archived,
    )
    story = build_operational_story(timeline.get("items") or [])

    properties_touched = await db[COLLECTION_EVENTS].aggregate(
        [
            {"$match": {**match, "property_id": {"$exists": True, "$nin": [None, ""]}}},
            {"$group": {"_id": "$property_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 20},
        ]
    ).to_list(20)

    return {
        "client_id": client_id,
        "window_hours": hours,
        "since": since_iso,
        "summary": {
            "event_count": timeline.get("total", 0),
            "properties_with_evidence": len(properties_touched),
            "high_impact_count": len(high_impact),
        },
        "by_category": [{"category": r["_id"], "count": r["count"]} for r in by_category],
        "customer_impact_breakdown": [
            {"classification": r["_id"], "count": r["count"]} for r in by_impact
        ],
        "properties_touched": [
            {"property_id": r["_id"], "event_count": r["count"]} for r in properties_touched
        ],
        "high_impact_events": high_impact,
        "timeline": timeline,
        "story": story,
    }
