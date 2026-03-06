"""
Predictive maintenance: simple heuristics from property_assets, maintenance_events, and property age.
Outputs risk and recommended actions per property. Gated by PREDICTIVE_MAINTENANCE.
Optional cache: scheduled job precomputes; get_insights_for_client returns cache if fresh.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from database import database
import logging

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24

ASSET_TYPE_BOILER = "boiler"
ASSET_TYPE_ELECTRICAL = "electrical"
ASSET_TYPE_GENERAL = "general"
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_URGENT = "urgent"


async def get_insights_for_client(
    client_id: str,
    property_ids: Optional[List[str]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Return predictive insights for all properties of a client (or subset).
    If use_cache is True and predictive_insights_cache has fresh data (within CACHE_TTL_HOURS), return it.
    """
    db = database.get_db()
    if use_cache and property_ids is None:
        cached = await db.predictive_insights_cache.find_one({"client_id": client_id})
        if cached and cached.get("data") and cached.get("updated_at"):
            try:
                updated = cached["updated_at"]
                if isinstance(updated, str):
                    updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - (updated.replace(tzinfo=timezone.utc) if updated.tzinfo is None else updated)).total_seconds() < CACHE_TTL_HOURS * 3600:
                    return cached["data"]
            except Exception as e:
                logger.debug("Predictive cache read skip: %s", e)
    if property_ids is not None:
        props_cursor = db.properties.find(
            {"client_id": client_id, "property_id": {"$in": property_ids}, "is_active": {"$ne": False}},
            {"_id": 0, "property_id": 1, "building_age_years": 1, "address_line_1": 1, "postcode": 1, "nickname": 1},
        )
    else:
        props_cursor = db.properties.find(
            {"client_id": client_id, "is_active": {"$ne": False}},
            {"_id": 0, "property_id": 1, "building_age_years": 1, "address_line_1": 1, "postcode": 1, "nickname": 1},
        )
    properties = await props_cursor.to_list(500)
    now = datetime.now(timezone.utc)
    results = []

    for prop in properties:
        pid = prop.get("property_id")
        building_age = prop.get("building_age_years")
        assets = await db.property_assets.find({"property_id": pid}).to_list(50)
        events = await db.maintenance_events.find(
            {"property_id": pid}
        ).sort("occurred_at", -1).limit(20).to_list(20)

        insights = []
        # Heuristic: building age > 50 → suggest electrical survey
        if building_age is not None and building_age > 50:
            insights.append({
                "type": "building_age",
                "asset_type": ASSET_TYPE_ELECTRICAL,
                "risk": RISK_MEDIUM,
                "recommendation": "Property over 50 years old; consider periodic electrical survey.",
                "detail": f"Building age: {building_age} years",
            })

        # Heuristic: boiler assets without service in last 12 months
        for a in assets:
            if (a.get("asset_type") or "").lower() in ("boiler", "heating"):
                last_service = a.get("last_service_date")
                install_date = a.get("install_date")
                if last_service:
                    try:
                        if isinstance(last_service, str):
                            dt = datetime.fromisoformat(last_service.replace("Z", "+00:00"))
                        else:
                            dt = last_service
                        if (now - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).days > 365:
                            insights.append({
                                "type": "asset_service_due",
                                "asset_id": a.get("asset_id"),
                                "asset_type": ASSET_TYPE_BOILER,
                                "risk": RISK_MEDIUM,
                                "recommendation": "Boiler/heating service overdue (12+ months).",
                                "detail": f"Last service: {last_service}",
                            })
                    except Exception:
                        pass
                elif install_date:
                    try:
                        if isinstance(install_date, str):
                            dt = datetime.fromisoformat(install_date.replace("Z", "+00:00"))
                        else:
                            dt = install_date
                        age_years = (now - (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt)).days / 365
                        if age_years > 15:
                            insights.append({
                                "type": "asset_age",
                                "asset_id": a.get("asset_id"),
                                "asset_type": ASSET_TYPE_BOILER,
                                "risk": RISK_HIGH,
                                "recommendation": "Boiler over 15 years old; consider service or replacement assessment.",
                                "detail": f"Approx. {int(age_years)} years old",
                            })
                    except Exception:
                        pass

        # Recent repair events: if many in short time, flag for review
        if len(events) >= 3:
            recent = [e for e in events if e.get("occurred_at")]
            if recent:
                try:
                    latest = recent[0].get("occurred_at")
                    if isinstance(latest, str):
                        latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                    else:
                        latest_dt = latest
                    if (now - (latest_dt.replace(tzinfo=timezone.utc) if latest_dt.tzinfo is None else latest_dt)).days < 90:
                        insights.append({
                            "type": "recent_activity",
                            "asset_type": ASSET_TYPE_GENERAL,
                            "risk": RISK_LOW,
                            "recommendation": "Multiple maintenance events recently; review pattern for recurring issues.",
                            "detail": f"{len(recent)} events in history",
                        })
                except Exception:
                    pass

        results.append({
            "property_id": pid,
            "nickname": prop.get("nickname"),
            "address_line_1": prop.get("address_line_1"),
            "postcode": prop.get("postcode"),
            "building_age_years": building_age,
            "insights": insights,
            "assets_count": len(assets),
            "events_count": len(events),
        })

    out = {"client_id": client_id, "properties": results}
    if property_ids is None:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.predictive_insights_cache.update_one(
                {"client_id": client_id},
                {"$set": {"data": out, "updated_at": now_iso}},
                upsert=True,
            )
        except Exception as e:
            logger.debug("Predictive cache write skip: %s", e)
    return out
