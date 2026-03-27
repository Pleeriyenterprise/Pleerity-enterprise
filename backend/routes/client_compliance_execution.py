"""
Client API: compliance execution booking (compliance work orders + contractor confirmation flow).

This is not maintenance repair: work orders are work_order_kind=COMPLIANCE (inspection / renewal / certification).
Requires COMPLIANCE_ENGINE and MAINTENANCE_WORKFLOWS. Contractor recommendation actions require CONTRACTOR_NETWORK.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field

from middleware import client_route_guard
from services import contractor_service
from services import maintenance_service
from services import work_order_contractor_routing_service as wo_contractor_routing
from services.compliance_booking_service import create_compliance_execution_work_order, describe_compliance_booking_action
from services.ops_compliance_feature_flags import (
    get_effective_flags,
    COMPLIANCE_ENGINE,
    MAINTENANCE_WORKFLOWS,
    CONTRACTOR_NETWORK,
)
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE

router = APIRouter(
    prefix="/api/client",
    tags=["client-compliance-execution"],
    dependencies=[Depends(client_route_guard)],
)


async def _require_compliance_execution(request: Request):
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(COMPLIANCE_ENGINE):
        raise HTTPException(
            status_code=403,
            detail="Compliance engine is not enabled for your account",
        )
    if not flags.get(MAINTENANCE_WORKFLOWS):
        raise HTTPException(
            status_code=403,
            detail="Work order workflows are not enabled for your account",
        )
    return user


class ComplianceBookingBody(BaseModel):
    property_id: str
    requirement_code: str = Field(..., description="Canonical or legacy requirement code (normalized server-side)")
    compliance_purpose: str = Field(..., description="inspection | renewal | certification | remedial")
    compliance_generated_from: str = Field(
        ...,
        description="requirement | risk_signal | manual",
    )
    description_override: Optional[str] = None
    compliance_due_at: Optional[str] = None
    linked_property_requirement_id: Optional[str] = None
    risk_signal_id: Optional[str] = None
    issue_id: Optional[str] = None


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


@router.post("/compliance-execution/work-orders/book")
async def book_compliance_execution_work_order(request: Request, body: ComplianceBookingBody):
    """
    Create a compliance execution work order (v1: no external calendar; real persisted WO + audit).
    Next: POST .../contractor-routing/generate to recommend a qualified compliance contractor.
    """
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        wo = await create_compliance_execution_work_order(
            client_id=client_id,
            property_id=body.property_id.strip(),
            requirement_code_raw=body.requirement_code,
            compliance_purpose=body.compliance_purpose,
            compliance_generated_from=body.compliance_generated_from,
            actor_portal_user_id=actor,
            description_override=body.description_override,
            compliance_due_at=body.compliance_due_at,
            linked_property_requirement_id=body.linked_property_requirement_id,
            risk_signal_id=body.risk_signal_id,
            issue_id=body.issue_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "work_order": wo,
        "action": describe_compliance_booking_action(body.compliance_purpose),
        "next_steps": {
            "recommend_contractor": f"POST /api/client/compliance-execution/work-orders/{wo['work_order_id']}/contractor-routing/generate",
        },
    }


@router.get("/compliance-execution/work-orders/{work_order_id}/contractor-routing")
async def get_compliance_work_order_contractor_routing(request: Request, work_order_id: str):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo or wo.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(
            status_code=400,
            detail="This endpoint applies to compliance execution work orders only; use maintenance contractor routing for repair work orders.",
        )
    data = await wo_contractor_routing.get_contractor_routing_state(work_order_id, client_id)
    if not data.get("ok"):
        raise HTTPException(status_code=404, detail="Work order not found")
    data["execution_context"] = "compliance_inspection_or_renewal"
    return data


@router.post("/compliance-execution/work-orders/{work_order_id}/contractor-routing/generate")
async def generate_compliance_contractor_recommendation(request: Request, work_order_id: str):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo or wo.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(
            status_code=400,
            detail="Compliance routing applies only to compliance execution work orders.",
        )
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.generate_and_notify_recommendation(
            work_order_id, client_id, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compliance-execution/work-orders/{work_order_id}/contractor-routing/confirm")
async def confirm_compliance_recommended_contractor(request: Request, work_order_id: str):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    _assert_compliance_wo(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.confirm_recommended_contractor(
            work_order_id, client_id, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compliance-execution/work-orders/{work_order_id}/contractor-routing/decline")
async def decline_compliance_recommendation(request: Request, work_order_id: str, body: DeclineRecommendationBody):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    _assert_compliance_wo(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.decline_recommendation(
            work_order_id, client_id, note=body.note, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compliance-execution/work-orders/{work_order_id}/contractor-routing/confirm-alternate")
async def confirm_compliance_alternate_contractor(request: Request, work_order_id: str, body: ConfirmAlternateBody):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    _assert_compliance_wo(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.confirm_alternate_contractor(
            work_order_id, client_id, body.contractor_id.strip(), actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compliance-execution/work-orders/{work_order_id}/contractor-routing/request-admin")
async def request_admin_compliance_routing(request: Request, work_order_id: str, body: RequestAdminRoutingBody):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    _assert_compliance_wo(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.request_admin_for_routing(
            work_order_id, client_id, note=body.note, actor_portal_user_id=actor
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compliance-execution/work-orders/{work_order_id}/contractor-routing/personal-contractor")
async def add_compliance_personal_contractor_and_assign(request: Request, work_order_id: str, body: PersonalContractorBody):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    _assert_compliance_wo(work_order_id, client_id)
    actor = user.get("portal_user_id") or user.get("email") or user.get("user_id")
    try:
        return await wo_contractor_routing.add_personal_contractor_and_assign(
            work_order_id,
            client_id,
            name=body.name,
            email=body.email,
            phone=body.phone,
            trade_types=body.trade_types,
            actor_portal_user_id=actor,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/compliance-execution/work-orders/{work_order_id}/recommend-contractors")
async def recommend_compliance_contractors(
    request: Request,
    work_order_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo or wo.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(
            status_code=400,
            detail="Ranked list applies to compliance execution work orders only.",
        )
    return await contractor_service.recommend_contractors_for_work_order(
        work_order_id=work_order_id,
        client_id=client_id,
        limit=limit,
    )


@router.get("/compliance-execution/work-orders/{work_order_id}/assignable-contractors")
async def list_compliance_assignable_contractors(
    request: Request,
    work_order_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    user = await _require_compliance_execution(request)
    client_id = user["client_id"]
    flags = await get_effective_flags(client_id)
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo or wo.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(status_code=400, detail="Assignable list applies to compliance execution work orders only.")
    return await contractor_service.list_assignable_contractors_for_work_order(
        client_id=client_id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
    )


async def _assert_compliance_wo(work_order_id: str, client_id: str) -> None:
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo or wo.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(
            status_code=400,
            detail="This action applies to compliance execution work orders only.",
        )
