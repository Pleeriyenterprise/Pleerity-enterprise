"""
Server-side onboarding checklist: items derived from plan + feature flags.
Completion state stored on client; server validates completion (e.g. "Add properties" only when client has >=1 property).
"""
from typing import Dict, List, Any, Optional
from database import database
from datetime import datetime, timezone
import logging

from services.compliance_rules_registry import (
    build_portfolio_jurisdiction_attestation,
    property_has_explicit_portfolio_jurisdiction,
)

logger = logging.getLogger(__name__)

# Checklist item ids (used in client.onboarding_checklist.items[].id)
ITEM_ADD_PROPERTIES = "add_properties"
ITEM_SET_JURISDICTIONS = "set_jurisdictions"
ITEM_CONFIRM_PROPERTY_ATTRIBUTES = "confirm_property_attributes"
ITEM_INVITE_TEAM = "invite_team"
ITEM_UPLOAD_CERTIFICATES = "upload_certificates"
ITEM_ENABLE_MAINTENANCE = "enable_maintenance"
ITEM_REVIEW_REQUIREMENTS = "review_requirements"
ITEM_UPLOAD_OR_COMPLIANCE_ACTION = "upload_or_compliance_action"

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
    # Use `is None`: projection can yield {} when the doc exists but every included field is absent; `not {}` is True in Python.
    if client is None:
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

    # Required: Set jurisdictions defaults + each property’s jurisdiction (or acknowledge default assumptions)
    items.append({
        "id": ITEM_SET_JURISDICTIONS,
        "label": "Set jurisdictions — defaults and each property (or acknowledge continuing with default assumptions)",
        "required": True,
        "deep_link": "/settings/jurisdiction",
        "completed_at": completed_map.get(ITEM_SET_JURISDICTIONS),
    })

    # Recommended: Confirm property attributes
    items.append({
        "id": ITEM_CONFIRM_PROPERTY_ATTRIBUTES,
        "label": "Confirm property details (type, gas, occupancy)",
        "required": False,
        "deep_link": "/properties",
        "completed_at": completed_map.get(ITEM_CONFIRM_PROPERTY_ATTRIBUTES),
    })

    # Review requirements (once portfolio exists)
    items.append({
        "id": ITEM_REVIEW_REQUIREMENTS,
        "label": "Review compliance requirements for your properties",
        "required": False,
        "deep_link": "/requirements",
        "completed_at": completed_map.get(ITEM_REVIEW_REQUIREMENTS),
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

    # If compliance flags on: first evidence or compliance job
    if flags.get("COMPLIANCE_ENGINE") or flags.get("COMPLIANCE_PACKS"):
        items.append({
            "id": ITEM_UPLOAD_OR_COMPLIANCE_ACTION,
            "label": "Upload your first document or start a compliance / maintenance job",
            "required": False,
            "deep_link": "/documents",
            "completed_at": completed_map.get(ITEM_UPLOAD_OR_COMPLIANCE_ACTION) or completed_map.get(ITEM_UPLOAD_CERTIFICATES),
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
        # Client-level ack is onboarding gating only; per-property jurisdiction remains the compliance source of truth.
        client = await db.clients.find_one(
            {"client_id": client_id},
            {
                "_id": 0,
                "default_jurisdiction": 1,
                "enabled_jurisdictions": 1,
                "jurisdiction_fallback_acknowledged_at": 1,
            },
        )
        if client is None:
            return False
        if not client.get("default_jurisdiction") or not client.get("enabled_jurisdictions"):
            return False
        props = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0, "jurisdiction": 1},
        ).to_list(10000)
        for p in props:
            if not property_has_explicit_portfolio_jurisdiction(p):
                return bool(client.get("jurisdiction_fallback_acknowledged_at"))
        return True
    if item_id == ITEM_REVIEW_REQUIREMENTS:
        n = await db.requirements.count_documents({"client_id": client_id})
        return n >= 1
    if item_id in (ITEM_UPLOAD_OR_COMPLIANCE_ACTION, ITEM_UPLOAD_CERTIFICATES):
        doc_n = await db.documents.count_documents({"client_id": client_id})
        if doc_n >= 1:
            return True
        wo_n = await db.work_orders.count_documents({"client_id": client_id})
        return wo_n >= 1
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
    if client is None:
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

    phase = _derive_onboarding_status(
        [{"id": x["id"], "completed_at": x.get("completed_at")} for x in new_items if x.get("id")],
        completed_at,
    )
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "onboarding_checklist.items": new_items,
                "onboarding_checklist.completed_at": completed_at,
                "onboarding_checklist.updated_at": now,
                "onboarding_checklist.phase_status": phase,
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


async def sync_auto_completed_items(client_id: str, *, portal_user_id: Optional[str] = None) -> List[str]:
    """
    Mark checklist steps complete when server-side validation already passes (e.g. user added a property
    but never clicked Mark done). Audited as a single sync event with the list of item ids updated.
    """
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "onboarding_checklist": 1})
    if client is None:
        return []
    o_prev = client.get("onboarding_checklist") or {}
    existing_items = o_prev.get("items") or []
    items_by_id: Dict[str, Any] = {item["id"]: dict(item) for item in existing_items if item.get("id")}
    checklist_defs = await get_checklist_items_for_client(client_id)
    now = datetime.now(timezone.utc).isoformat()
    updated_ids: List[str] = []
    for defn in checklist_defs:
        iid = defn["id"]
        if items_by_id.get(iid, {}).get("completed_at"):
            continue
        try:
            ok = await validate_item_completion(client_id, iid)
        except Exception as e:
            logger.warning("sync_auto_completed_items validate failed client=%s item=%s: %s", client_id, iid, e)
            continue
        if ok:
            row = {**items_by_id.get(iid, {"id": iid}), "id": iid, "completed_at": now, "completed_via": "auto_sync"}
            items_by_id[iid] = row
            updated_ids.append(iid)
    if not updated_ids:
        return []

    new_items = list(items_by_id.values())
    all_required_ids = {ITEM_ADD_PROPERTIES, ITEM_SET_JURISDICTIONS}
    required_done = all(items_by_id.get(rid, {}).get("completed_at") for rid in all_required_ids)
    checklist_completed_at = now if required_done else None

    phase = _derive_onboarding_status(
        [{"id": x["id"], "completed_at": x.get("completed_at")} for x in new_items if x.get("id")],
        checklist_completed_at,
    )
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "onboarding_checklist.items": new_items,
                "onboarding_checklist.completed_at": checklist_completed_at,
                "onboarding_checklist.updated_at": now,
                "onboarding_checklist.phase_status": phase,
                "onboarding_progress": {
                    "last_auto_sync_at": now,
                    "auto_completed_item_ids": updated_ids,
                    "checklist_phase_status": phase,
                },
            }
        },
    )
    try:
        from utils.audit import create_audit_log
        from models import AuditAction

        await create_audit_log(
            action=AuditAction.ONBOARDING_CHECKLIST_PROGRESS_SYNCED,
            actor_id=portal_user_id,
            client_id=client_id,
            resource_type="onboarding_checklist",
            resource_id=client_id,
            metadata={"item_ids": updated_ids, "required_complete": bool(required_done)},
        )
    except Exception as e:
        logger.warning("onboarding sync audit failed: %s", e)
    logger.info("Onboarding auto-sync client_id=%s items=%s", client_id, updated_ids)
    return updated_ids


def _derive_onboarding_status(items: List[Dict[str, Any]], completed_at: Optional[str]) -> str:
    if completed_at:
        return "completed"
    if not items:
        return "not_started"
    prop_done = any(i.get("id") == ITEM_ADD_PROPERTIES and i.get("completed_at") for i in items)
    if not prop_done:
        return "not_started"
    return "in_progress"


async def get_checklist_state(client_id: str, *, portal_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Full checklist state: items, completed_at, progress, onboarding_status. Auto-syncs validated steps first."""
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 1}):
        return {
            "items": [],
            "completed_at": None,
            "progress": None,
            "onboarding_status": "not_started",
            "next_step": None,
            "phase_status": "not_started",
            "onboarding_progress": None,
            "jurisdiction_onboarding": None,
        }
    await sync_auto_completed_items(client_id, portal_user_id=portal_user_id)
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "onboarding_checklist": 1, "onboarding_progress": 1, "jurisdiction_fallback_acknowledged_at": 1},
    )
    items = await get_checklist_items_for_client(client_id)
    o = (client or {}).get("onboarding_checklist") or {}
    completed_at = o.get("completed_at")
    done = sum(1 for i in items if i.get("completed_at"))
    total = len(items)
    pct = int(round(100 * done / total)) if total else 0
    status = _derive_onboarding_status(items, completed_at)
    next_step = None
    for i in items:
        if not i.get("completed_at"):
            next_step = {
                "id": i.get("id"),
                "label": i.get("label"),
                "deep_link": i.get("deep_link"),
                "required": bool(i.get("required")),
            }
            break
    props_min = await db.properties.find(
        {"client_id": client_id},
        {"_id": 0, "property_id": 1, "jurisdiction": 1},
    ).to_list(10000)
    att = build_portfolio_jurisdiction_attestation({}, props_min)
    jurisdiction_onboarding = {
        **att,
        "jurisdiction_fallback_acknowledged": bool((client or {}).get("jurisdiction_fallback_acknowledged_at")),
    }
    return {
        "items": items,
        "completed_at": completed_at,
        "onboarding_status": status,
        "progress": {
            "completed": done,
            "total": total,
            "percent": pct,
        },
        "onboarding_progress": (client or {}).get("onboarding_progress"),
        "next_step": next_step,
        "phase_status": (o or {}).get("phase_status") or status,
        "jurisdiction_onboarding": jurisdiction_onboarding,
    }


async def get_checklist_for_client(client_id: str) -> Dict[str, Any]:
    """Alias for client API: returns same shape as get_checklist_state. Returns error key if client not found."""
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 1}):
        return {"error": "Client not found"}
    return await get_checklist_state(client_id)
