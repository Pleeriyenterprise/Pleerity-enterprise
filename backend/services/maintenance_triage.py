"""
Stateless triage for maintenance issues: severity, priority score, SLA hours,
recommended contractor type, and reasoning. Used when creating work orders or issues.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database

# Severity / category constants (align with maintenance_service)
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_URGENT = "urgent"
CATEGORY_HEATING = "heating"
CATEGORY_PLUMBING = "plumbing"
CATEGORY_ELECTRICAL = "electrical"
CATEGORY_GENERAL = "general"

# Contractor type suggestions (e.g. for Gas Safe, qualified electrician)
CONTRACTOR_TYPE_GAS_SAFE = "gas_safe"
CONTRACTOR_TYPE_PLUMBER = "plumber"
CONTRACTOR_TYPE_ELECTRICIAN = "electrician"
CONTRACTOR_TYPE_GENERAL = "general"
CONTRACTOR_TYPE_DAMP_INSPECTION = "damp_inspection"

# SLA defaults (hours)
SLA_URGENT_HOURS = 24
SLA_HIGH_HOURS = 48
SLA_MEDIUM_HOURS = 72
SLA_LOW_HOURS = 120


def _is_heating_season(now: Optional[datetime] = None) -> bool:
    """UK heating season: Oct–Mar (month 10–3)."""
    t = now or datetime.now(timezone.utc)
    return t.month >= 10 or t.month <= 3


async def _recent_work_orders_for_property(
    property_id: str,
    client_id: Optional[str] = None,
    category: Optional[str] = None,
    days: int = 90,
) -> List[Dict[str, Any]]:
    """Work orders for this property in the last `days` (for recurrence)."""
    db = database.get_db()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = {"property_id": property_id, "created_at": {"$gte": since}}
    if client_id:
        q["client_id"] = client_id
    if category:
        q["category"] = category
    cursor = db.work_orders.find(q).sort("created_at", -1).limit(50)
    return await cursor.to_list(50)


def triage_maintenance_issue(
    description: str,
    category: Optional[str] = None,
    source: Optional[str] = None,
    property_doc: Optional[Dict[str, Any]] = None,
    asset_history: Optional[List[Dict[str, Any]]] = None,
    recent_work_orders: Optional[List[Dict[str, Any]]] = None,
    reported_urgency: Optional[str] = None,
    asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Stateless triage: returns severity, priority_score, sla_hours,
    recommended_contractor_type, reasoning[], recurrence_flag.
    Does not require DB if callers pass property_doc, asset_history, recent_work_orders.
    """
    d = (description or "").lower().strip()
    cat = (category or CATEGORY_GENERAL).strip().lower()
    reasoning: List[str] = []
    severity = SEVERITY_MEDIUM
    priority_score = 50
    sla_hours = SLA_MEDIUM_HOURS
    recommended_contractor_type = CONTRACTOR_TYPE_GENERAL
    recurrence_flag = False

    # --- Urgent keywords (leak, no heat, no water, gas, emergency) ---
    if any(w in d for w in ["leak", "leaking", "flood", "water pouring"]):
        severity = SEVERITY_URGENT
        priority_score = 95
        sla_hours = SLA_URGENT_HOURS
        recommended_contractor_type = CONTRACTOR_TYPE_PLUMBER
        reasoning.append("Description indicates leak or water ingress; urgent response applied.")
    elif any(w in d for w in ["gas smell", "gas leak", "gas odor"]):
        severity = SEVERITY_URGENT
        priority_score = 98
        sla_hours = SLA_URGENT_HOURS
        recommended_contractor_type = CONTRACTOR_TYPE_GAS_SAFE
        reasoning.append("Gas-related issue; Gas Safe registered contractor required; urgent SLA.")
    elif any(w in d for w in ["no heat", "no heating", "heating not working", "boiler broken", "boiler not working"]):
        if cat == CATEGORY_HEATING or "heat" in d or "boiler" in d:
            if _is_heating_season():
                severity = SEVERITY_HIGH
                priority_score = 88
                sla_hours = SLA_URGENT_HOURS
                recommended_contractor_type = CONTRACTOR_TYPE_GAS_SAFE
                reasoning.append("Heating issue during heating season (Oct–Mar); 24h response; Gas Safe recommended if gas boiler.")
            else:
                severity = SEVERITY_MEDIUM
                priority_score = 60
                sla_hours = SLA_HIGH_HOURS
                recommended_contractor_type = CONTRACTOR_TYPE_GAS_SAFE
                reasoning.append("Heating issue outside peak season; Gas Safe recommended if gas boiler.")
        else:
            severity = SEVERITY_HIGH
            priority_score = 75
            sla_hours = SLA_HIGH_HOURS
            reasoning.append("Heating-related keywords detected; high priority.")
    elif any(w in d for w in ["no water", "no hot water", "water off"]):
        severity = SEVERITY_HIGH
        priority_score = 82
        sla_hours = SLA_HIGH_HOURS
        recommended_contractor_type = CONTRACTOR_TYPE_PLUMBER
        reasoning.append("No water / no hot water; high priority.")
    elif any(w in d for w in ["emergency", "urgent"]):
        severity = SEVERITY_URGENT
        priority_score = min(priority_score + 20, 99)
        sla_hours = min(sla_hours, SLA_URGENT_HOURS)
        reasoning.append("Reporter indicated emergency/urgent.")

    # --- Category-based defaults if not already set ---
    if severity == SEVERITY_MEDIUM and recommended_contractor_type == CONTRACTOR_TYPE_GENERAL:
        if cat == CATEGORY_PLUMBING:
            recommended_contractor_type = CONTRACTOR_TYPE_PLUMBER
            reasoning.append("Category: plumbing; plumber recommended.")
        elif cat == CATEGORY_ELECTRICAL:
            recommended_contractor_type = CONTRACTOR_TYPE_ELECTRICIAN
            reasoning.append("Category: electrical; qualified electrician recommended.")
        elif cat == CATEGORY_HEATING:
            recommended_contractor_type = CONTRACTOR_TYPE_GAS_SAFE
            reasoning.append("Category: heating; Gas Safe contractor recommended for gas systems.")

    # --- Damp / mould → suggest inspection ---
    if any(w in d for w in ["damp", "mould", "mold", "condensation", "rising damp"]):
        if "inspection" not in d and "survey" not in d:
            reasoning.append("Damp/mould mentioned; consider damp survey or inspection before repair.")
            if recommended_contractor_type == CONTRACTOR_TYPE_GENERAL:
                recommended_contractor_type = CONTRACTOR_TYPE_DAMP_INSPECTION
            priority_score = max(priority_score, 55)

    # --- Recurrence: same property (and optionally category) in last 90 days ---
    if recent_work_orders:
        same_cat = [wo for wo in recent_work_orders if (wo.get("category") or "").lower() == cat]
        if len(same_cat) >= 1:
            recurrence_flag = True
            priority_score = min(100, priority_score + 15)
            reasoning.append(f"Recurrence: {len(same_cat)} related work order(s) in last 90 days; priority boosted.")

    # --- User-reported urgency ---
    if reported_urgency and reported_urgency.strip().lower() in ("high", "urgent"):
        priority_score = min(100, priority_score + 10)
        reasoning.append("Reporter indicated high/urgent urgency.")

    # --- Bounds ---
    priority_score = max(1, min(100, priority_score))
    if not reasoning:
        reasoning.append("Default triage: medium severity, 72h SLA.")

    return {
        "severity": severity,
        "priority_score": priority_score,
        "sla_hours": sla_hours,
        "recommended_contractor_type": recommended_contractor_type,
        "reasoning": reasoning,
        "recurrence_flag": recurrence_flag,
    }


async def triage_maintenance_issue_async(
    description: str,
    category: Optional[str] = None,
    source: Optional[str] = None,
    property_id: Optional[str] = None,
    client_id: Optional[str] = None,
    reported_urgency: Optional[str] = None,
    asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Async triage that fetches property, asset history, and recent work orders
    when property_id (and optionally client_id) are provided.
    """
    property_doc = None
    asset_history = None
    recent_work_orders = None

    if property_id:
        db = database.get_db()
        property_doc = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "postcode": 1, "client_id": 1},
        )
        if client_id:
            from services import property_assets_service
            asset_history = await property_assets_service.list_events(
                property_id, client_id=client_id, limit=30
            )
        recent_work_orders = await _recent_work_orders_for_property(
            property_id, client_id=client_id, category=category, days=90
        )

    return triage_maintenance_issue(
        description=description,
        category=category,
        source=source,
        property_doc=property_doc,
        asset_history=asset_history,
        recent_work_orders=recent_work_orders,
        reported_urgency=reported_urgency,
        asset_id=asset_id,
    )
