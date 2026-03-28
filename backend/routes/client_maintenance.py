"""
Client API for maintenance work orders. Gated by MAINTENANCE_WORKFLOWS.
List own work orders, create new (client or property manager).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from database import database
from middleware import client_route_guard
from services import maintenance_service
from services import maintenance_issues_service
from services import contractor_service
from services import work_order_contractor_routing_service as wo_contractor_routing
from services.ops_compliance_feature_flags import get_effective_flags, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE, CONTRACTOR_NETWORK
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE
from services import property_assets_service
from services import risk_signal_service
from services import operational_issue_suggestions_service
from services import contractor_evidence_service
from utils.audit import create_audit_log
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from config.security_limits import security_limits
from models import AuditAction, UserRole

logger = logging.getLogger(__name__)


async def _enforce_maintenance_issue_create_rate_limit(client_id: str) -> None:
    key = f"maintenance_issue_create:{client_id}"
    ok, msg = await rate_limiter.check_rate_limit(
        key,
        security_limits.maintenance_issue_create_per_client_per_hour,
        60,
    )
    if not ok:
        log_rate_limit_event("maintenance_issue_create", client_id, None)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            client_id=client_id,
            metadata={"scope": "maintenance_issue_create", "client_id": client_id},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=msg or "Issue creation limit reached for this hour. Try again later.",
        )


async def _enforce_maintenance_work_order_create_rate_limit(client_id: str) -> None:
    key = f"maintenance_work_order_create:{client_id}"
    ok, msg = await rate_limiter.check_rate_limit(
        key,
        security_limits.maintenance_work_order_create_per_client_per_hour,
        60,
    )
    if not ok:
        log_rate_limit_event("maintenance_work_order_create", client_id, None)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            client_id=client_id,
            metadata={"scope": "maintenance_work_order_create", "client_id": client_id},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=msg or "Work order creation limit reached for this hour. Try again later.",
        )

router = APIRouter(prefix="/api/client", tags=["client-maintenance"], dependencies=[Depends(client_route_guard)])


class CreateWorkOrderBody(BaseModel):
    property_id: str
    description: str
    category: Optional[str] = None
    severity: Optional[str] = None
    asset_id: Optional[str] = None
    issue_id: Optional[str] = None
    risk_signal_id: Optional[str] = None
    cost_estimate_min: Optional[float] = None
    cost_estimate_max: Optional[float] = None


async def _require_maintenance_work_order_not_compliance(work_order_id: str, client_id: str) -> None:
    """Maintenance repair routing must not be used for compliance execution work orders."""
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo or wo.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(
            status_code=400,
            detail=(
                "This work order is a compliance execution job (inspection/renewal/certification). "
                "Use /api/client/compliance-execution/work-orders/{id}/contractor-routing instead of maintenance routing."
            ),
        )


async def _require_maintenance_enabled(request: Request):
    """Ensure client has MAINTENANCE_WORKFLOWS enabled."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS):
        raise HTTPException(
            status_code=403,
            detail="Maintenance workflows are not enabled for your account",
        )
    return user


async def _require_maintenance_and_predictive(request: Request):
    """Maintenance + predictive (operational suggestions and risk-backed flows)."""
    user = await _require_maintenance_enabled(request)
    flags = await get_effective_flags(user["client_id"])
    if not flags.get(PREDICTIVE_MAINTENANCE):
        raise HTTPException(
            status_code=403,
            detail="Predictive maintenance is not enabled for your account",
        )
    return user


@router.get("/maintenance/work-orders")
async def list_my_work_orders(
    request: Request,
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    contractor_id: Optional[str] = Query(None),
    asset_id: Optional[str] = Query(None),
    work_order_kind: Optional[str] = Query(
        None, description="MAINTENANCE | COMPLIANCE (filters list when set)"
    ),
    from_date: Optional[str] = Query(None, description="Filter by created_at >= date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter by created_at <= date (YYYY-MM-DD)"),
    sla_state: Optional[str] = Query(None, description="breached | near_breach | on_track"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List work orders for the authenticated client. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    db = database.get_db()
    if property_id:
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
    result = await maintenance_service.list_work_orders(
        client_id=client_id,
        property_id=property_id,
        status=status,
        contractor_id=contractor_id,
        asset_id=asset_id,
        work_order_kind=work_order_kind,
        from_date=from_date,
        to_date=to_date,
        sla_state=sla_state,
        skip=skip,
        limit=limit,
    )
    return result


@router.post("/maintenance/work-orders")
async def create_work_order(request: Request, body: CreateWorkOrderBody):
    """Create a work order for a property. Requires MAINTENANCE_WORKFLOWS.
    Optional risk_signal_id must belong to this client and property; provenance is stored server-side.
    """
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _enforce_maintenance_work_order_create_rate_limit(client_id)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": body.property_id, "client_id": client_id},
        {"_id": 1, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    wo_created_from = "manual"
    wo_triggering = "client_api_work_order"
    wo_root: Optional[str] = None
    wo_risk_id: Optional[str] = None

    effective_asset_id = body.asset_id
    if body.risk_signal_id:
        sig = await risk_signal_service.get_risk_signal_by_id(body.risk_signal_id.strip(), client_id)
        if not sig or sig.get("property_id") != body.property_id:
            raise HTTPException(status_code=404, detail="Risk signal not found for this property")
        wo_risk_id = body.risk_signal_id.strip()
        wo_created_from = "risk_signal"
        wo_triggering = "client_api_work_order_risk_signal"
        rt = sig.get("risk_type") or ""
        aid = sig.get("asset_id")
        wo_root = f"risk:{rt}:{(aid or '').strip() or 'none'}"
        if effective_asset_id is None and aid:
            effective_asset_id = aid

    doc = await maintenance_service.create_work_order(
        client_id=client_id,
        property_id=body.property_id,
        description=body.description,
        source=maintenance_service.SOURCE_CLIENT,
        reporter_id=user.get("portal_user_id"),
        category=body.category,
        severity=body.severity,
        asset_id=effective_asset_id,
        issue_id=body.issue_id,
        risk_signal_id=wo_risk_id,
        cost_estimate_min=body.cost_estimate_min,
        cost_estimate_max=body.cost_estimate_max,
        created_from=wo_created_from,
        triggering_rule=wo_triggering,
        operational_root_key=wo_root,
    )
    return doc


class CreateIssueBody(BaseModel):
    property_id: str
    description: str
    category: Optional[str] = None
    asset_id: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_contact: Optional[str] = None
    reported_urgency: Optional[str] = None
    photos: Optional[List[str]] = None


@router.post("/maintenance/issues")
async def create_issue(request: Request, body: CreateIssueBody):
    """Create a maintenance issue (triage runs automatically). Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _enforce_maintenance_issue_create_rate_limit(client_id)
    try:
        doc = await maintenance_issues_service.create_issue(
            client_id=client_id,
            property_id=body.property_id,
            description=body.description,
            source=maintenance_issues_service.SOURCE_CLIENT,
            category=body.category,
            asset_id=body.asset_id,
            reporter_name=body.reporter_name,
            reporter_contact=body.reporter_contact,
            reported_urgency=body.reported_urgency,
            photos=body.photos,
        )
        try:
            actor_role = UserRole(user["role"]) if user.get("role") else None
        except Exception:
            actor_role = None
        await create_audit_log(
            action=AuditAction.MAINTENANCE_ISSUE_CREATED,
            actor_role=actor_role,
            actor_id=user.get("portal_user_id"),
            client_id=client_id,
            resource_type="maintenance_issue",
            resource_id=doc.get("issue_id"),
            metadata={"property_id": body.property_id, "source": maintenance_issues_service.SOURCE_CLIENT},
            ip_address=request.client.host if request.client else None,
        )
        return doc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/maintenance/issues")
async def list_my_issues(
    request: Request,
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    asset_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, description="Filter by created_at >= (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter by created_at <= (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List maintenance issues for the authenticated client. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    if property_id:
        db = database.get_db()
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
    result = await maintenance_issues_service.list_issues(
        client_id=client_id,
        property_id=property_id,
        status=status,
        category=category,
        severity=severity,
        source=source,
        asset_id=asset_id,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )
    return result


@router.get("/maintenance/issues/open-count")
async def get_open_issues_count(request: Request):
    """Count non-terminal maintenance issues for dashboard KPIs. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    n = await maintenance_issues_service.count_open_issues(user["client_id"])
    return {"open_issues_count": n}


@router.get("/maintenance/operational-issue-suggestions")
async def list_operational_issue_suggestions(
    request: Request,
    property_id: Optional[str] = Query(None, description="Scope to one property (must belong to client)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Read-only list of backend **suggested** follow-ups (tier B automation — not auto-created issues).
    Requires MAINTENANCE_WORKFLOWS and PREDICTIVE_MAINTENANCE.
    """
    user = await _require_maintenance_and_predictive(request)
    client_id = user["client_id"]
    if property_id:
        db = database.get_db()
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
    return await operational_issue_suggestions_service.list_pending_issue_suggestions(
        client_id=client_id,
        property_id=property_id,
        skip=skip,
        limit=limit,
    )


class DismissOperationalSuggestionBody(BaseModel):
    note: Optional[str] = None


class ConvertOperationalSuggestionBody(BaseModel):
    issue_id: str


@router.post("/maintenance/operational-issue-suggestions/{suggestion_id}/dismiss")
async def dismiss_operational_issue_suggestion(
    request: Request,
    suggestion_id: str,
    body: DismissOperationalSuggestionBody,
):
    """
    Dismiss a pending suggestion (tier B — user declines the suggested follow-up).
    Requires MAINTENANCE_WORKFLOWS and PREDICTIVE_MAINTENANCE.
    """
    user = await _require_maintenance_and_predictive(request)
    client_id = user["client_id"]
    try:
        doc = await operational_issue_suggestions_service.dismiss_issue_suggestion(
            client_id=client_id,
            suggestion_id=suggestion_id.strip(),
            actor_id=user.get("portal_user_id"),
            note=body.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return doc


@router.post("/maintenance/operational-issue-suggestions/{suggestion_id}/convert")
async def convert_operational_issue_suggestion(
    request: Request,
    suggestion_id: str,
    body: ConvertOperationalSuggestionBody,
):
    """
    Mark a suggestion as acted on by linking an issue you created for the same property.
    Requires MAINTENANCE_WORKFLOWS and PREDICTIVE_MAINTENANCE.
    """
    user = await _require_maintenance_and_predictive(request)
    client_id = user["client_id"]
    if not (body.issue_id or "").strip():
        raise HTTPException(status_code=400, detail="issue_id is required")
    try:
        doc = await operational_issue_suggestions_service.convert_issue_suggestion(
            client_id=client_id,
            suggestion_id=suggestion_id.strip(),
            issue_id=body.issue_id.strip(),
            actor_id=user.get("portal_user_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return doc


@router.get("/maintenance/issues/{issue_id}/timeline")
async def get_issue_timeline(
    request: Request,
    issue_id: str,
    limit: int = Query(120, ge=10, le=200),
):
    """Read-only merged timeline for one issue (audit, work orders, asset events). Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    from services.maintenance_issue_timeline_service import get_issue_timeline as build_timeline

    data = await build_timeline(user["client_id"], issue_id, limit=limit)
    if not data:
        raise HTTPException(status_code=404, detail="Issue not found")
    return data


@router.get("/maintenance/issues/{issue_id}")
async def get_issue(request: Request, issue_id: str):
    """Get a single maintenance issue with triage result. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    doc = await maintenance_issues_service.get_issue(issue_id, client_id=user["client_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Issue not found")
    return doc


class UpdateIssueBody(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None


@router.patch("/maintenance/issues/{issue_id}")
async def update_issue(request: Request, issue_id: str, body: UpdateIssueBody):
    """Update issue status and/or description, category. Requires MAINTENANCE_WORKFLOWS. Audits status changes."""
    user = await _require_maintenance_enabled(request)
    doc = await maintenance_issues_service.update_issue(
        issue_id=issue_id,
        client_id=user["client_id"],
        status=body.status,
        description=body.description,
        category=body.category,
        updated_by_id=user.get("portal_user_id"),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Issue not found")
    return doc


@router.post("/maintenance/issues/{issue_id}/create-work-order")
async def create_work_order_from_issue(request: Request, issue_id: str):
    """Create a work order from an issue; links issue_id to the work order. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    try:
        doc = await maintenance_issues_service.create_work_order_from_issue(
            issue_id=issue_id,
            client_id=user["client_id"],
            reporter_id=user.get("portal_user_id"),
        )
        return doc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/maintenance/work-orders/{work_order_id}")
async def get_my_work_order(request: Request, work_order_id: str):
    """Get a single work order by id (own client only). Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    doc = await maintenance_service.get_work_order(work_order_id)
    if not doc or doc.get("client_id") != user["client_id"]:
        raise HTTPException(status_code=404, detail="Work order not found")
    return doc


@router.get("/maintenance/work-orders/{work_order_id}/contractor-evidence/file")
async def download_contractor_evidence_file(
    request: Request,
    work_order_id: str,
    storage_key: str = Query(..., min_length=3, description="Evidence storage key from work order evidence_keys"),
    download: bool = Query(False),
):
    """Download or inline-view a contractor-uploaded evidence file (own client’s work order only)."""
    user = await _require_maintenance_enabled(request)
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo or wo.get("client_id") != user["client_id"]:
        raise HTTPException(status_code=404, detail="Work order not found")
    wo_client_id = (wo.get("client_id") or "").strip()
    try:
        path, media, filename = await contractor_evidence_service.resolve_contractor_evidence_file(
            work_order_id=work_order_id,
            wo_client_id=wo_client_id,
            evidence_keys=wo.get("evidence_keys"),
            storage_key=storage_key,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Evidence not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evidence file missing")
    await create_audit_log(
        action=AuditAction.CONTRACTOR_EVIDENCE_DOWNLOADED,
        actor_id=user.get("portal_user_id"),
        client_id=user["client_id"],
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={
            "storage_key": contractor_evidence_service.normalize_evidence_storage_key(storage_key),
            "download": download,
            "via": "client_portal",
        },
    )
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(path),
        media_type=media,
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


class UpdateWorkOrderBody(BaseModel):
    status: Optional[str] = None
    contractor_id: Optional[str] = None
    resolution_outcome: Optional[str] = None
    cost_estimate_min: Optional[float] = None
    cost_estimate_max: Optional[float] = None


@router.patch("/maintenance/work-orders/{work_order_id}")
async def update_my_work_order(request: Request, work_order_id: str, body: UpdateWorkOrderBody):
    """Update work order status and/or assign contractor (own client only). Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    existing = await maintenance_service.get_work_order(work_order_id)
    if not existing or existing.get("client_id") != user["client_id"]:
        raise HTTPException(status_code=404, detail="Work order not found")
    assigned_by = (user.get("email") or user.get("portal_user_id") or user.get("user_id")) if body.contractor_id else None
    try:
        doc = await maintenance_service.update_work_order(
            work_order_id,
            status=body.status,
            contractor_id=body.contractor_id,
            resolution_outcome=body.resolution_outcome,
            cost_estimate_min=body.cost_estimate_min,
            cost_estimate_max=body.cost_estimate_max,
            assigned_by=assigned_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    return doc


@router.get("/maintenance/work-orders/{work_order_id}/recommend-contractors")
async def recommend_contractors_for_work_order(
    request: Request,
    work_order_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    """
    Ranked recommendations (same engine as admin): eligible contractors only, workload/SLA-aware routing metadata,
    explainable scores. Requires MAINTENANCE_WORKFLOWS and CONTRACTOR_NETWORK.
    """
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    result = await contractor_service.recommend_contractors_for_work_order(
        work_order_id=work_order_id,
        client_id=client_id,
        limit=limit,
    )
    return result


@router.get("/maintenance/work-orders/{work_order_id}/assignable-contractors")
async def list_assignable_contractors_for_work_order(
    request: Request,
    work_order_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List contractors ready for assignment (vetted, portal activated, trade/location/property filters). Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    return await contractor_service.list_assignable_contractors_for_work_order(
        client_id=client_id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
    )


class DeclineRecommendationBody(BaseModel):
    note: Optional[str] = None


class ConfirmAlternateBody(BaseModel):
    contractor_id: str


class PersonalContractorBody(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    trade_types: List[str]


class RequestAdminRoutingBody(BaseModel):
    note: Optional[str] = None


@router.get("/maintenance/work-orders/{work_order_id}/contractor-routing")
async def get_work_order_contractor_routing(request: Request, work_order_id: str):
    """Current recommendation state, SLA context preview, and allowed actions. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    data = await wo_contractor_routing.get_contractor_routing_state(work_order_id, client_id)
    if not data.get("ok"):
        raise HTTPException(status_code=404, detail="Work order not found")
    return data


@router.post("/maintenance/work-orders/{work_order_id}/contractor-routing/generate")
async def generate_work_order_contractor_recommendation(request: Request, work_order_id: str):
    """Run routing engine, set pending recommendation, notify client (not contractor). Requires CONTRACTOR_NETWORK."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.generate_and_notify_recommendation(
            work_order_id, client_id, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance/work-orders/{work_order_id}/contractor-routing/confirm")
async def confirm_work_order_recommended_contractor(request: Request, work_order_id: str):
    """Confirm the pending recommendation; assigns contractor and sends contractor notification."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.confirm_recommended_contractor(
            work_order_id, client_id, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance/work-orders/{work_order_id}/contractor-routing/decline")
async def decline_work_order_recommendation(request: Request, work_order_id: str, body: DeclineRecommendationBody):
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.decline_recommendation(
            work_order_id, client_id, note=body.note, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance/work-orders/{work_order_id}/contractor-routing/confirm-alternate")
async def confirm_alternate_work_order_contractor(request: Request, work_order_id: str, body: ConfirmAlternateBody):
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.confirm_alternate_contractor(
            work_order_id, client_id, body.contractor_id.strip(), actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance/work-orders/{work_order_id}/contractor-routing/request-admin")
async def request_admin_contractor_routing(request: Request, work_order_id: str, body: RequestAdminRoutingBody):
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.request_admin_for_routing(
            work_order_id, client_id, note=body.note, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance/work-orders/{work_order_id}/contractor-routing/personal-contractor")
async def add_personal_contractor_and_assign_work_order(request: Request, work_order_id: str, body: PersonalContractorBody):
    """Create client-supplied contractor record and assign (portal optional)."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    await _require_maintenance_work_order_not_compliance(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.add_personal_contractor_and_assign(
            work_order_id,
            client_id,
            name=body.name,
            email=body.email,
            phone=body.phone,
            trade_types=body.trade_types or ["general"],
            actor_portal_user_id=actor,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/maintenance/predictive-insights")
async def get_my_predictive_insights(request: Request):
    """Get predictive maintenance insights for the authenticated client's properties. Requires PREDICTIVE_MAINTENANCE."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(PREDICTIVE_MAINTENANCE):
        raise HTTPException(
            status_code=403,
            detail="Predictive maintenance is not enabled for your account",
        )
    from services.predictive_service import get_insights_for_client
    result = await get_insights_for_client(client_id)
    return result


async def _require_predictive_enabled(request: Request):
    """Ensure client has PREDICTIVE_MAINTENANCE enabled."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(PREDICTIVE_MAINTENANCE):
        raise HTTPException(
            status_code=403,
            detail="Predictive maintenance is not enabled for your account",
        )
    return user


async def _require_assets_enabled(request: Request):
    """Allow assets when MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE (Assets tab visible with maintenance)."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS) and not flags.get(PREDICTIVE_MAINTENANCE):
        raise HTTPException(
            status_code=403,
            detail="Maintenance or predictive maintenance is required to access assets",
        )
    return user


@router.get("/maintenance/properties/{property_id}/assets")
async def list_property_assets(request: Request, property_id: str):
    """List assets for a property with summary. Requires MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE."""
    user = await _require_assets_enabled(request)
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": user["client_id"]}, {"_id": 1})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    items = await property_assets_service.list_assets(property_id, user["client_id"])
    summary = await property_assets_service.get_assets_summary(property_id, user["client_id"], items)
    return {"assets": items, "summary": summary}


class AddAssetBody(BaseModel):
    asset_type: str
    name: Optional[str] = None
    status: Optional[str] = None
    install_date: Optional[str] = None
    last_service_date: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    installed_year: Optional[int] = None
    age_estimate: Optional[int] = None
    notes: Optional[str] = None


@router.post("/maintenance/properties/{property_id}/assets")
async def add_property_asset(request: Request, property_id: str, body: AddAssetBody):
    """Add an asset for a property. Requires MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE."""
    user = await _require_assets_enabled(request)
    doc = await property_assets_service.add_asset(
        property_id=property_id,
        client_id=user["client_id"],
        asset_type=body.asset_type,
        install_date=body.install_date,
        last_service_date=body.last_service_date,
        notes=body.notes,
        name=body.name,
        status=body.status,
        make=body.make,
        model=body.model,
        installed_year=body.installed_year,
        age_estimate=body.age_estimate,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    return doc


@router.post("/maintenance/properties/{property_id}/assets/ensure-defaults")
async def ensure_default_assets_route(request: Request, property_id: str):
    """Create default assets for the property if missing (idempotent). For backfill / Initialise Assets. Requires MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE."""
    user = await _require_assets_enabled(request)
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": user["client_id"]}, {"_id": 1})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    created = await property_assets_service.ensure_default_assets_for_property(user["client_id"], property_id)
    items = await property_assets_service.list_assets(property_id, user["client_id"])
    summary = await property_assets_service.get_assets_summary(property_id, user["client_id"], items)
    return {"created": created, "assets": items, "summary": summary}


@router.get("/maintenance/properties/{property_id}/assets/{asset_id}")
async def get_property_asset(request: Request, property_id: str, asset_id: str):
    """Get a single asset with recent events. Requires MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE."""
    user = await _require_assets_enabled(request)
    asset = await property_assets_service.get_asset(property_id, asset_id, user["client_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    events = await property_assets_service.list_asset_events(
        asset_id, property_id, user["client_id"], limit=20
    )
    return {"asset": asset, "events": events}


class UpdateAssetBody(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    last_service_date: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    installed_year: Optional[int] = None
    age_estimate: Optional[int] = None
    notes: Optional[str] = None


@router.patch("/maintenance/properties/{property_id}/assets/{asset_id}")
async def update_property_asset(request: Request, property_id: str, asset_id: str, body: UpdateAssetBody):
    """Update an asset. Requires MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE."""
    user = await _require_assets_enabled(request)
    doc = await property_assets_service.update_asset(
        property_id=property_id,
        asset_id=asset_id,
        client_id=user["client_id"],
        name=body.name,
        status=body.status,
        last_service_date=body.last_service_date,
        make=body.make,
        model=body.model,
        installed_year=body.installed_year,
        age_estimate=body.age_estimate,
        notes=body.notes,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Asset not found")
    return doc


@router.get("/maintenance/properties/{property_id}/assets/{asset_id}/events")
async def list_asset_events_route(
    request: Request, property_id: str, asset_id: str, limit: int = Query(50, ge=1, le=100)
):
    """List events for an asset. Requires MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE."""
    user = await _require_assets_enabled(request)
    prop = await database.get_db().properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]}, {"_id": 1}
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    items = await property_assets_service.list_asset_events(
        asset_id, property_id, user["client_id"], limit=limit
    )
    return {"events": items}


@router.get("/maintenance/properties/{property_id}/events")
async def list_property_events(request: Request, property_id: str, limit: int = 50):
    """List maintenance events for a property. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": user["client_id"]}, {"_id": 1})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    items = await property_assets_service.list_events(property_id, user["client_id"], limit=limit)
    return {"events": items}


class AddEventBody(BaseModel):
    event_type: str
    occurred_at: Optional[str] = None
    outcome: Optional[str] = None
    asset_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("/maintenance/properties/{property_id}/events")
async def add_property_event(request: Request, property_id: str, body: AddEventBody):
    """Add a maintenance event (e.g. boiler service). Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    doc = await property_assets_service.add_event(
        property_id=property_id,
        client_id=user["client_id"],
        event_type=body.event_type,
        occurred_at=body.occurred_at,
        outcome=body.outcome,
        asset_id=body.asset_id,
        notes=body.notes,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    return doc


# ---------- Risk Signals (stored, rule-based risk intelligence) ----------

@router.get("/maintenance/properties/{property_id}/risk-signals")
async def get_property_risk_signals(request: Request, property_id: str, status: Optional[str] = Query(None)):
    """Get stored risk signals for a property with summary. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    client_id = user["client_id"]
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    result = await risk_signal_service.get_risk_signals_for_property(
        property_id=property_id, client_id=client_id, status_filter=status
    )
    return result


@router.get("/maintenance/risk-signals")
async def get_portfolio_risk_signals(
    request: Request,
    property_id: Optional[str] = Query(None, description="Filter by property"),
    status: Optional[str] = Query(None, description="active | acknowledged | resolved"),
    risk_level: Optional[str] = Query(None, description="low | medium | high | critical"),
    risk_type: Optional[str] = Query(None, description="e.g. Boiler Failure Risk"),
    trend: Optional[str] = Query(None, description="rising | stable | improving"),
    q: Optional[str] = Query(None, description="Search risk type, action, reasons"),
    from_date: Optional[str] = Query(None, alias="from", description="From date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="To date YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=500),
):
    """Get stored risk signals for the client (portfolio) with summary and highPriority. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    result = await risk_signal_service.get_risk_signals_for_client(
        client_id=user["client_id"],
        property_id_filter=property_id,
        status_filter=status,
        risk_level=risk_level,
        risk_type=risk_type,
        trend=trend,
        q=q,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    return result


@router.get("/maintenance/risk-signals/{signal_id}")
async def get_risk_signal_by_id_route(request: Request, signal_id: str):
    """Get a single risk signal for the detail drawer. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    doc = await risk_signal_service.get_risk_signal_by_id(signal_id=signal_id, client_id=user["client_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Risk signal not found")
    return doc


@router.get("/maintenance/risk-signals/{signal_id}/suggested-actions")
async def get_risk_signal_suggested_actions_route(request: Request, signal_id: str):
    """Read-only recommended_action + alternatives (same semantics as create-issue / create-work-order buttons). Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    data = await risk_signal_service.get_risk_signal_suggested_actions_view(
        signal_id=signal_id, client_id=user["client_id"]
    )
    if not data:
        raise HTTPException(status_code=404, detail="Risk signal not found")
    return data


@router.get("/maintenance/risk-signals/{signal_id}/explanation")
async def get_risk_signal_explanation_route(request: Request, signal_id: str):
    """Get contextual explanation for a risk signal (why it matters, recommended action). Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    doc = await risk_signal_service.get_risk_signal_by_id(signal_id=signal_id, client_id=user["client_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Risk signal not found")
    from services.explanation_engine import explain_risk_signal
    return explain_risk_signal(doc)


@router.post("/maintenance/risk-signals/recalculate/{property_id}")
async def recalculate_property_risk_signals(request: Request, property_id: str):
    """Regenerate risk signals for a property. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    client_id = user["client_id"]
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    out = await risk_signal_service.generate_risk_signals_for_property(property_id=property_id, client_id=client_id)
    removed = int(out.get("previous_active_removed") or 0)
    generated = int(out.get("generated") or 0)
    outcome_status = "conditional_no_output" if generated == 0 else "success"
    try:
        await create_audit_log(
            action=AuditAction.RISK_SIGNAL_UPDATED,
            actor_id=user.get("portal_user_id"),
            client_id=client_id,
            resource_type="property",
            resource_id=property_id,
            metadata={
                "operation": "risk_signals_property_recalculate",
                "property_id": property_id,
                "generated": generated,
                "previous_active_removed": removed,
                "outcome_status": outcome_status,
            },
        )
    except Exception as e:
        logger.warning("Audit log for risk signal recalc failed: %s", e)
    return {
        "ok": True,
        "property_id": property_id,
        "generated": generated,
        "previous_active_removed": removed,
        "outcome_status": outcome_status,
        "signals": out.get("signals") or [],
    }


class UpdateRiskSignalStatusBody(BaseModel):
    status: str  # "acknowledged" | "resolved"


@router.patch("/maintenance/risk-signals/{signal_id}")
async def update_risk_signal_status(request: Request, signal_id: str, body: UpdateRiskSignalStatusBody):
    """Set risk signal status to acknowledged or resolved. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    updated = await risk_signal_service.update_signal_status(
        signal_id=signal_id, client_id=user["client_id"], new_status=body.status.strip().lower()
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Risk signal not found or invalid status")
    return updated


class CreateFromRiskSignalBody(BaseModel):
    description_override: Optional[str] = None


@router.post("/maintenance/risk-signals/{signal_id}/create-issue")
async def create_issue_from_risk_signal_route(request: Request, signal_id: str, body: Optional[CreateFromRiskSignalBody] = None):
    """Create a maintenance issue from this risk signal (user-confirmed). Requires PREDICTIVE_MAINTENANCE and MAINTENANCE_WORKFLOWS."""
    user = await _require_predictive_enabled(request)
    await _require_maintenance_enabled(request)
    try:
        issue = await risk_signal_service.create_issue_from_risk_signal(
            signal_id=signal_id,
            client_id=user["client_id"],
            description_override=body.description_override if body else None,
            reporter_id=user.get("portal_user_id"),
        )
        return issue
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance/risk-signals/{signal_id}/create-work-order")
async def create_work_order_from_risk_signal_route(request: Request, signal_id: str, body: Optional[CreateFromRiskSignalBody] = None):
    """Create a work order from this risk signal (user-confirmed). Requires PREDICTIVE_MAINTENANCE and MAINTENANCE_WORKFLOWS."""
    user = await _require_predictive_enabled(request)
    await _require_maintenance_enabled(request)
    try:
        wo = await risk_signal_service.create_work_order_from_risk_signal(
            signal_id=signal_id,
            client_id=user["client_id"],
            description_override=body.description_override if body else None,
            reporter_id=user.get("portal_user_id"),
        )
        return wo
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maintenance/risk-signals/{signal_id}/schedule-inspection")
async def schedule_inspection_from_risk_signal_route(request: Request, signal_id: str, body: Optional[CreateFromRiskSignalBody] = None):
    """Create an inspection issue from this risk signal (schedule_inspection action). Requires PREDICTIVE_MAINTENANCE and MAINTENANCE_WORKFLOWS."""
    user = await _require_predictive_enabled(request)
    await _require_maintenance_enabled(request)
    try:
        issue = await risk_signal_service.create_inspection_issue_from_risk_signal(
            signal_id=signal_id,
            client_id=user["client_id"],
            description_override=body.description_override if body else None,
            reporter_id=user.get("portal_user_id"),
        )
        return issue
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
