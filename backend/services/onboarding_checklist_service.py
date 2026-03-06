"""
Server-side onboarding checklist: items derived from plan + feature flags.
Completion state stored on client; server validates completion (e.g. "Add properties" only when client has >=1 property).
"""
from typing import Dict, List, Any, Optional
from database import database
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Checklist item ids (used in client.onboarding_checklist.items[].id)
ITEM_ADD_PROPERTIES = "add_properties"
ITEM_SET_JURISDICTIONS = "set_jurisdictions"
ITEM_CONFIRM_PROPERTY_ATTRIBUTES = "confirm_property_attributes"
ITEM_INVITE_TEAM = "invite_team"
ITEM_UPLOAD_CERTIFICATES = "upload_certificates"
ITEM_ENABLE_MAINTENANCE = "enable_maintenance"

UK_JURISDICTIONS = ["Scotland", "England", "Wales", "Northern Ireland"]


def _default_jurisdiction_settings() -> Dict[str, Any]:
    return {
        "default_jurisdiction": "Scotland",
        "enabled_jurisdictions": UK_JURISDICTIONS.copy(),
    }


async def get_checklist_items_for_client(client_id: str) -> List[Dict[str, Any]]:
    """
    Build checklist items for this client based on plan and feature flags.
    Returns list of { id, label, required, deep_link, completed_at? }.
    """
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "billing_plan": 1, "onboarding_checklist": 1, "default_jurisdiction": 1, "enabled_jurisdictions": 1},
    )
    if not client:
        return []

    plan = client.get("billing_plan") or "PLAN_1_SOLO"
    from services.ops_compliance_feature_flags import get_effective_flags
    flags = await get_effective_flags(client_id, plan)
    existing = (client.get("onboarding_checklist") or {}).get("items") or []
    completed_map = {item["id"]: item.get("completed_at") for item in existing if item.get("id")}

    items = []

    # Required: Add properties (or import)
    items.append({
        "id": ITEM_ADD_PROPERTIES,
        "label": "Add properties (or import)",
        "required": True,
        "deep_link": "/properties",
        "completed_at": completed_map.get(ITEM_ADD_PROPERTIES),
    })

    # Required: Set jurisdictions defaults
    items.append({
        "id": ITEM_SET_JURISDICTIONS,
        "label": "Set jurisdiction defaults (Scotland, England, Wales, Northern Ireland)",
        "required": True,
        "deep_link": "/settings",
        "completed_at": completed_map.get(ITEM_SET_JURISDICTIONS),
    })

    # Recommended: Confirm property attributes
    items.append({
        "id": ITEM_CONFIRM_PROPERTY_ATTRIBUTES,
        "label": "Confirm property attributes (hasGas, floors, property type)",
        "required": False,
        "deep_link": "/properties",
        "completed_at": completed_map.get(ITEM_CONFIRM_PROPERTY_ATTRIBUTES),
    })

    # Recommended: Invite team (Portfolio/Pro)
    if plan in ("PLAN_2_PORTFOLIO", "PLAN_3_PRO", "PLAN_2_5", "PLAN_6_15"):
        items.append({
            "id": ITEM_INVITE_TEAM,
            "label": "Invite team members",
            "required": False,
            "deep_link": "/settings",
            "completed_at": completed_map.get(ITEM_INVITE_TEAM),
        })

    # If compliance flags on: Upload existing certificates
    if flags.get("COMPLIANCE_ENGINE") or flags.get("COMPLIANCE_PACKS"):
        items.append({
            "id": ITEM_UPLOAD_CERTIFICATES,
            "label": "Upload existing certificates",
            "required": False,
            "deep_link": "/documents",
            "completed_at": completed_map.get(ITEM_UPLOAD_CERTIFICATES),
        })

    # If maintenance available: Enable maintenance workflows
    if flags.get("MAINTENANCE_WORKFLOWS"):
        items.append({
            "id": ITEM_ENABLE_MAINTENANCE,
            "label": "Enable maintenance workflows",
            "required": False,
            "deep_link": "/settings",
            "completed_at": completed_map.get(ITEM_ENABLE_MAINTENANCE),
        })

    return items


async def validate_item_completion(client_id: str, item_id: str) -> bool:
    """Server-side validation: return True if the item can be considered complete."""
    db = database.get_db()
    if item_id == ITEM_ADD_PROPERTIES:
        count = await db.properties.count_documents({"client_id": client_id})
        return count >= 1
    if item_id == ITEM_SET_JURISDICTIONS:
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "default_jurisdiction": 1, "enabled_jurisdictions": 1},
        )
        if not client:
            return False
        return bool(client.get("default_jurisdiction") and client.get("enabled_jurisdictions"))
    # Other items: allow mark complete (recommended/optional)
    return True


async def mark_item_complete(
    client_id: str,
    item_id: str,
    *,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mark a checklist item complete. Validates server-side where applicable.
    Updates client.onboarding_checklist; returns updated checklist state.
    """
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "onboarding_checklist": 1})
    if not client:
        return {"ok": False, "error": "Client not found"}

    if not await validate_item_completion(client_id, item_id):
        return {"ok": False, "error": "Validation failed", "item_id": item_id}

    now = datetime.now(timezone.utc).isoformat()
    existing = (client.get("onboarding_checklist") or {}).get("items") or []
    items_by_id = {item["id"]: item for item in existing}
    items_by_id[item_id] = {**items_by_id.get(item_id, {"id": item_id}), "completed_at": now}
    new_items = list(items_by_id.values())

    all_required_ids = {ITEM_ADD_PROPERTIES, ITEM_SET_JURISDICTIONS}
    required_done = all(
        items_by_id.get(rid, {}).get("completed_at")
        for rid in all_required_ids
    )
    completed_at = now if required_done else None

    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "onboarding_checklist.items": new_items,
                "onboarding_checklist.completed_at": completed_at,
                "onboarding_checklist.updated_at": now,
            }
        },
    )
    logger.info("Onboarding checklist item completed client_id=%s item_id=%s", client_id, item_id)
    return {
        "ok": True,
        "item_id": item_id,
        "completed_at": now,
        "checklist_completed": bool(completed_at),
    }


async def get_checklist_state(client_id: str) -> Dict[str, Any]:
    """Full checklist state for client dashboard: items (with completion) + overall completed_at."""
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "onboarding_checklist": 1},
    )
    if not client:
        return {"items": [], "completed_at": None}
    items = await get_checklist_items_for_client(client_id)
    o = client.get("onboarding_checklist") or {}
    return {
        "items": items,
        "completed_at": o.get("completed_at"),
    }


async def get_checklist_for_client(client_id: str) -> Dict[str, Any]:
    """Alias for client API: returns same shape as get_checklist_state. Returns error key if client not found."""
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 1}):
        return {"error": "Client not found"}
    return await get_checklist_state(client_id)
