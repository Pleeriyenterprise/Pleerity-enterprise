"""
Predictive maintenance: property assets, maintenance events, risk insights.
Read-only insights based on asset age, last service, and event history.
Gated by PREDICTIVE_MAINTENANCE feature flag.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid
from database import database
import logging

logger = logging.getLogger(__name__)

# Asset types we can reason about
ASSET_TYPE_BOILER = "boiler"
ASSET_TYPE_ELECTRICAL = "electrical"
ASSET_TYPE_HEATING = "heating"
ASSET_TYPE_GENERAL = "general"

# Risk levels for insights
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_URGENT = "urgent"


async def get_insights_for_property(property_id: str, client_id: str) -> List[Dict[str, Any]]:
    """
    Return list of predictive insights for a property: e.g. boiler age, last service, suggested action.
    Uses property_assets and maintenance_events; falls back to property.building_age_years if no assets.
    """
    db = database.get_db()
    insights = []

    # Load assets for this property
    assets = await db.property_assets.find({"property_id": property_id}).to_list(100)
    for a in assets:
        a.pop("_id", None)

    # If no assets, use building_age_years from property for a single generic insight
    if not assets:
        prop = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0, "building_age_years": 1},
        )
        if prop and prop.get("building_age_years") is not None:
            age = prop["building_age_years"]
            if age and age > 40:
                insights.append({
                    "asset_id": None,
                    "asset_type": "building",
                    "title": "Older building",
                    "message": f"Property age {age} years. Consider periodic electrical and gas checks.",
                    "risk": RISK_MEDIUM if age < 60 else RISK_HIGH,
                    "suggested_action": "Schedule EICR and gas safety if not done recently.",
                })
        return insights

    now = datetime.now(timezone.utc)
    for asset in assets:
        asset_type = asset.get("asset_type") or ASSET_TYPE_GENERAL
        install_date = asset.get("install_date")
        last_service = asset.get("last_service_date")
        name = asset.get("name") or asset_type

        # Boiler: suggest service if > 12 months since last service or install > 15 years
        if asset_type in (ASSET_TYPE_BOILER, ASSET_TYPE_HEATING):
            last_dt = None
            if last_service:
                try:
                    last_dt = last_service if isinstance(last_service, datetime) else datetime.fromisoformat(str(last_service).replace("Z", "+00:00"))
                except Exception:
                    pass
            install_dt = None
            if install_date:
                try:
                    install_dt = install_date if isinstance(install_date, datetime) else datetime.fromisoformat(str(install_date).replace("Z", "+00:00"))
                except Exception:
                    pass

            if last_dt:
                months_since = (now - last_dt).days / 30.44
                if months_since > 12:
                    insights.append({
                        "asset_id": asset.get("asset_id"),
                        "asset_type": asset_type,
                        "title": f"{name}: service overdue",
                        "message": f"Last service {int(months_since)} months ago. Annual service recommended.",
                        "risk": RISK_HIGH if months_since > 18 else RISK_MEDIUM,
                        "suggested_action": "Schedule boiler service.",
                    })
            if install_dt:
                years_old = (now - install_dt).days / 365.25
                if years_old > 15 and not any(i.get("asset_id") == asset.get("asset_id") and "service" in (i.get("message") or "").lower() for i in insights):
                    insights.append({
                        "asset_id": asset.get("asset_id"),
                        "asset_type": asset_type,
                        "title": f"{name}: age",
                        "message": f"Installed {int(years_old)} years ago. Consider efficiency check or replacement planning.",
                        "risk": RISK_MEDIUM if years_old < 20 else RISK_HIGH,
                        "suggested_action": "Arrange inspection or quote for replacement.",
                    })

        # Electrical: generic if no recent event
        if asset_type == ASSET_TYPE_ELECTRICAL and install_date:
            try:
                install_dt = install_date if isinstance(install_date, datetime) else datetime.fromisoformat(str(install_date).replace("Z", "+00:00"))
                years_old = (now - install_dt).days / 365.25
                if years_old > 5:
                    insights.append({
                        "asset_id": asset.get("asset_id"),
                        "asset_type": asset_type,
                        "title": f"{name}: periodic check",
                        "message": f"Electrical installation age {int(years_old)} years. EICR every 5 years recommended.",
                        "risk": RISK_MEDIUM,
                        "suggested_action": "Book EICR if not done in last 5 years.",
                    })
            except Exception:
                pass

    return insights


async def get_insights_for_client(client_id: str, limit: int = 50) -> Dict[str, Any]:
    """Aggregate insights for all properties of a client. Gate by PREDICTIVE_MAINTENANCE in route."""
    db = database.get_db()
    props = await db.properties.find({"client_id": client_id}, {"_id": 0, "property_id": 1}).to_list(500)
    all_insights = []
    for p in props:
        pid = p.get("property_id")
        if not pid:
            continue
        insights = await get_insights_for_property(pid, client_id)
        for i in insights:
            i["property_id"] = pid
            all_insights.append(i)
    # Sort by risk (urgent first) then take limit
    risk_order = {RISK_URGENT: 0, RISK_HIGH: 1, RISK_MEDIUM: 2, RISK_LOW: 3}
    all_insights.sort(key=lambda x: (risk_order.get(x.get("risk"), 4), x.get("title", "")))
    return {"insights": all_insights[:limit], "total": len(all_insights)}


async def record_maintenance_event(
    client_id: str,
    property_id: str,
    event_type: str,
    asset_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a maintenance event (repair, inspection, service) for predictive history."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    event_id = str(uuid.uuid4())
    doc = {
        "event_id": event_id,
        "client_id": client_id,
        "property_id": property_id,
        "asset_id": asset_id,
        "event_type": event_type,
        "notes": notes,
        "occurred_at": now,
        "created_at": now,
    }
    await db.maintenance_events.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def upsert_property_asset(
    property_id: str,
    client_id: str,
    asset_type: str,
    name: Optional[str] = None,
    install_date: Optional[str] = None,
    last_service_date: Optional[str] = None,
    asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update a property asset for predictive insights."""
    db = database.get_db()
    aid = asset_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "property_id": property_id,
        "client_id": client_id,
        "asset_id": aid,
        "asset_type": asset_type,
        "name": name or asset_type,
        "install_date": install_date,
        "last_service_date": last_service_date,
        "updated_at": now,
    }
    await db.property_assets.update_one(
        {"property_id": property_id, "asset_id": aid},
        {"$set": doc},
        upsert=True,
    )
    doc.pop("_id", None)
    return doc
