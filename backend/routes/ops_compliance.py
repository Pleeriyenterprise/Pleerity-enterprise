"""
Operations & Compliance admin API: feature flags, plan usage, provisioning status.
All endpoints require admin auth; feature-flag changes require Owner or Admin and are audited.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from database import database
from middleware import admin_route_guard, require_owner_or_admin
from models import AuditAction
from utils.audit import create_audit_log
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/ops", tags=["ops-compliance"], dependencies=[Depends(admin_route_guard)])


class FeatureFlagUpdate(BaseModel):
    flag_key: str
    enabled: bool


class FeatureFlagsBulkUpdate(BaseModel):
    updates: List[FeatureFlagUpdate]


@router.get("/clients/{client_id}/feature-flags")
async def get_client_feature_flags(request: Request, client_id: str):
    """Get effective feature flags for a client (with source: plan_default | override)."""
    await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "billing_plan": 1, "client_id": 1},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    plan_code = client.get("billing_plan")
    from services.ops_compliance_feature_flags import get_effective_flags_with_meta
    result = await get_effective_flags_with_meta(client_id, plan_code)
    return result


@router.patch("/clients/{client_id}/feature-flags", dependencies=[Depends(require_owner_or_admin)])
async def update_client_feature_flags(
    request: Request,
    client_id: str,
    body: FeatureFlagsBulkUpdate,
):
    """Update feature flag overrides for a client. Owner or Admin only. Audited."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can change feature flags")
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    from services.ops_compliance_feature_flags import set_flag, ALL_FLAG_KEYS
    actor_id = user.get("portal_user_id") or user.get("id") or "unknown"
    for u in body.updates:
        if u.flag_key not in ALL_FLAG_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown flag_key: {u.flag_key}")
        await set_flag(client_id, u.flag_key, u.enabled, actor_id, source="manual")
        await create_audit_log(
            action=AuditAction.FEATURE_FLAG_CHANGED,
            actor_id=actor_id,
            actor_role=user.get("role"),
            client_id=client_id,
            resource_type="feature_flag",
            resource_id=u.flag_key,
            metadata={"flag_key": u.flag_key, "enabled": u.enabled},
        )
    return {"ok": True, "client_id": client_id}


@router.get("/clients/{client_id}/plan-usage")
async def get_client_plan_usage(request: Request, client_id: str):
    """Get plan usage for admin: properties count vs limit, seats placeholder."""
    await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "client_id": 1, "billing_plan": 1},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    from services.plan_registry import plan_registry, PlanCode
    plan_code_str = client.get("billing_plan")
    try:
        plan_code = PlanCode(plan_code_str) if plan_code_str else PlanCode.PLAN_1_SOLO
    except ValueError:
        plan_code = PlanCode.PLAN_1_SOLO
    defn = plan_registry.get_plan(plan_code)
    if not defn:
        defn = {"max_properties": 2, "name": "Solo Landlord"}
    prop_count = await db.properties.count_documents({"client_id": client_id})
    max_props = defn.get("max_properties", 2)
    # Seats: count portal_users linked to this client (placeholder until seat limits exist)
    seats_used = await db.portal_users.count_documents({"client_id": client_id})
    seats_allowed = None  # plan could define later
    return {
        "client_id": client_id,
        "billing_plan": plan_code_str,
        "plan_name": defn.get("name"),
        "properties_used": prop_count,
        "properties_allowed": max_props,
        "properties_at_limit": prop_count >= max_props,
        "seats_used": seats_used,
        "seats_allowed": seats_allowed,
    }


@router.get("/clients/{client_id}/checklist")
async def get_client_checklist(request: Request, client_id: str):
    """Get onboarding checklist state for a client (admin view)."""
    await admin_route_guard(request)
    from services.onboarding_checklist_service import get_checklist_state
    result = await get_checklist_state(client_id)
    return result


@router.get("/overview")
async def get_ops_overview(request: Request):
    """Placeholder overview for Operations & Compliance dashboard: counts by module flag."""
    await admin_route_guard(request)
    db = database.get_db()
    from services.ops_compliance_feature_flags import get_effective_flags, ALL_FLAG_KEYS
    clients = await db.clients.find(
        {},
        {"_id": 0, "client_id": 1, "billing_plan": 1},
    ).to_list(5000)
    counts = {k: 0 for k in ALL_FLAG_KEYS}
    for c in clients:
        flags = await get_effective_flags(c["client_id"], c.get("billing_plan"))
        for k, v in flags.items():
            if v:
                counts[k] = counts.get(k, 0) + 1
    return {
        "clients_total": len(clients),
        "modules_enabled_counts": counts,
    }


@router.get("/clients/{client_id}/predictive-insights")
async def get_client_predictive_insights(request: Request, client_id: str):
    """Get predictive maintenance insights for a client's properties. Admin only. Uses property_assets, maintenance_events, and building_age_years."""
    await admin_route_guard(request)
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")
    from services.predictive_service import get_insights_for_client
    result = await get_insights_for_client(client_id)
    return result
