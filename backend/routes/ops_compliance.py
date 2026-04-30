"""
Operations & Compliance admin API: feature flags, plan usage, provisioning status.
All endpoints require admin auth; feature-flag changes require Owner or Admin and are audited.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
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


class ApplicabilityOperatorCommandBody(BaseModel):
    command: Literal["MARK_REQUIRED", "MARK_NOT_REQUIRED", "REVOKE_OVERRIDE"]
    resolution_reason_code: str = Field(..., min_length=1)
    notes: Optional[str] = None


@router.post(
    "/clients/{client_id}/requirements/{requirement_id}/applicability-operator",
    dependencies=[Depends(require_owner_or_admin)],
)
async def post_applicability_operator_command(
    request: Request,
    client_id: str,
    requirement_id: str,
    body: ApplicabilityOperatorCommandBody,
):
    """
    Internal admin: operator applicability override (PR4). Tenant-scoped; audited; no client API.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    from services.applicability_operator_actions import ApplicabilityOperatorActionError, execute_applicability_operator_command

    actor = {
        "type": "user",
        "id": str(user.get("portal_user_id") or user.get("id") or user.get("sub") or "").strip(),
        "email": user.get("email"),
    }
    if not actor["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authenticated admin user id is required")
    try:
        return await execute_applicability_operator_command(
            db,
            client_id=client_id,
            requirement_id=requirement_id,
            command=body.command,
            resolution_reason_code=body.resolution_reason_code,
            actor=actor,
            notes=body.notes,
        )
    except ApplicabilityOperatorActionError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e


@router.get("/clients/{client_id}/applicability-resolution-queue")
async def get_applicability_resolution_queue(
    request: Request,
    client_id: str,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(
        None,
        description="Pagination: pass next_cursor (requirement_id) from the previous response",
    ),
):
    """
    Internal admin: queue of high-impact requirements with **pipeline** applicability UNKNOWN,
    showing pipeline / effective / resolution_source plus deterministic root-cause codes.
    Each item includes ``operator_action_wiring`` (PR4 POST path, per-command availability, and
    ``resolution_reason_code_options`` aligned with ``execute_applicability_operator_command``).
    """
    await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    from services.applicability_resolution_queue import list_applicability_resolution_queue_page

    return await list_applicability_resolution_queue_page(
        db,
        client_id=client_id,
        limit=limit,
        after_requirement_id=cursor,
    )


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


@router.get("/clients/{client_id}/dashboard-roi-diagnostics")
async def get_client_dashboard_roi_diagnostics(request: Request, client_id: str):
    """
    Read-only: client dashboard ROI summary plus diagnostics (scan health, no-SLA job counts).
    Same computation as GET /api/client/dashboard/roi-summary; for support/ops only.
    """
    await admin_route_guard(request)
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")
    from services.client_roi_summary_service import get_roi_summary_month_to_date

    data = await get_roi_summary_month_to_date(client_id, db)
    return {"client_id": client_id, **data}


@router.get("/compliance-clients-summary")
async def get_compliance_clients_summary(
    request: Request,
    client_id: Optional[str] = Query(None, description="Filter to one client"),
    limit: int = Query(200, ge=1, le=500),
):
    """
    Cross-client compliance snapshot for ops: requirement counts per client (overdue, expiring soon).
    Optional portfolio score when filtering to a single client (reuses compliance_score service).
    """
    await admin_route_guard(request)
    db = database.get_db()
    match: Dict[str, Any] = {}
    if client_id:
        match["client_id"] = client_id

    pipeline: List[Dict[str, Any]] = []
    if match:
        pipeline.append({"$match": match})
    pipeline.extend(
        [
            {
                "$group": {
                    "_id": "$client_id",
                    "overdue_count": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", ["OVERDUE", "EXPIRED"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "expiring_soon_count": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "EXPIRING_SOON"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "requirements_last_updated": {"$max": "$updated_at"},
                }
            },
            {"$sort": {"overdue_count": -1, "expiring_soon_count": -1, "_id": 1}},
            {"$limit": limit},
        ]
    )
    rows_raw = await db.requirements.aggregate(pipeline).to_list(limit)
    cids = [r["_id"] for r in rows_raw if r.get("_id")]
    name_by_cid: Dict[str, str] = {}
    if cids:
        async for doc in db.clients.find(
            {"client_id": {"$in": cids}},
            {"_id": 0, "client_id": 1, "full_name": 1, "company_name": 1},
        ):
            cid = doc.get("client_id")
            if not cid:
                continue
            name_by_cid[cid] = (doc.get("company_name") or doc.get("full_name") or cid) or cid

    rows: List[Dict[str, Any]] = []
    for r in rows_raw:
        cid = r.get("_id")
        if not cid:
            continue
        row = {
            "client_id": cid,
            "client_name": name_by_cid.get(cid, cid),
            "overdue_count": int(r.get("overdue_count") or 0),
            "expiring_soon_count": int(r.get("expiring_soon_count") or 0),
            "requirements_last_updated": r.get("requirements_last_updated"),
            "portfolio_score": None,
            "portfolio_grade": None,
            "score_status": None,
            "score_updated_at": None,
        }
        rows.append(row)

    if client_id and not rows:
        doc = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "client_id": 1, "full_name": 1, "company_name": 1},
        )
        if doc:
            cid = doc["client_id"]
            rows.append(
                {
                    "client_id": cid,
                    "client_name": doc.get("company_name") or doc.get("full_name") or cid,
                    "overdue_count": 0,
                    "expiring_soon_count": 0,
                    "requirements_last_updated": None,
                    "portfolio_score": None,
                    "portfolio_grade": None,
                    "score_status": None,
                    "score_updated_at": None,
                }
            )

    if client_id and len(rows) == 1:
        try:
            from services.compliance_score import calculate_compliance_score

            cs = await calculate_compliance_score(client_id)
            rows[0]["portfolio_score"] = cs.get("score")
            rows[0]["portfolio_grade"] = cs.get("grade")
            rows[0]["score_status"] = cs.get("score_status")
            rows[0]["score_updated_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.warning("compliance-clients-summary score for %s: %s", client_id, e)

    return {"rows": rows, "total": len(rows)}


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


@router.get("/risk-signals/summary")
async def get_risk_signals_admin_summary_route(
    request: Request,
    client_id: Optional[str] = Query(None, description="Filter by client"),
    risk_level: Optional[str] = Query(None, description="low | medium | high | critical"),
    risk_type: Optional[str] = Query(None, description="e.g. Boiler Failure Risk"),
    status: Optional[str] = Query(None, description="active | acknowledged | resolved"),
    limit: int = Query(200, ge=1, le=500),
):
    """Admin risk dashboard: aggregate risk signals across clients. Top properties, top clients, counts by level/type, recent signals."""
    await admin_route_guard(request)
    from services import risk_signal_service
    result = await risk_signal_service.get_risk_signals_admin_summary(
        client_id_filter=client_id,
        risk_level=risk_level,
        risk_type=risk_type,
        status_filter=status,
        limit_signals=limit,
    )
    return result


@router.get("/priority-actions")
async def get_admin_priority_actions(
    request: Request,
    client_id: Optional[str] = Query(None, description="Filter by client"),
    limit: int = Query(30, ge=1, le=100),
):
    """Get ranked priority actions for admin (action queue / operational priorities)."""
    await admin_route_guard(request)
    try:
        from services.priority_actions import get_priority_actions_for_admin
        result = await get_priority_actions_for_admin(
            client_id_filter=client_id,
            limit=limit,
        )
        return result
    except Exception as e:
        logger.error("Admin priority actions error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load priority actions",
        )
