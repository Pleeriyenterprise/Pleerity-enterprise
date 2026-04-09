"""
Admin API for maintenance work orders (Ops & Compliance).
List, get, update, assign contractor. Owner/Admin for write.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from typing import Optional, List

from database import database
from middleware import admin_route_guard, require_owner_or_admin
from services import maintenance_service
from services.compliance_rules_registry import jurisdiction_attribution_for_property
from services import contractor_service
from services import contractor_evidence_service
from services import work_order_schedule_service as wo_schedule
from services.work_order_schedule_constants import SCHEDULE_ACTOR_ADMIN
from services.risk_signal_regen_queue import get_regen_queue_summary
from utils.audit import create_audit_log
from models import AuditAction

router = APIRouter(prefix="/api/admin/ops", tags=["ops-maintenance"], dependencies=[Depends(admin_route_guard)])


class WorkOrderCreateBody(BaseModel):
    client_id: str
    property_id: str
    description: str
    category: Optional[str] = None
    severity: Optional[str] = None
    asset_id: Optional[str] = None
    issue_id: Optional[str] = None
    risk_signal_id: Optional[str] = None
    cost_estimate_min: Optional[float] = None
    cost_estimate_max: Optional[float] = None
    created_from: Optional[str] = None
    triggering_rule: Optional[str] = None
    operational_root_key: Optional[str] = None
    work_order_kind: Optional[str] = None
    requirement_code: Optional[str] = None
    compliance_purpose: Optional[str] = None
    compliance_due_at: Optional[str] = None
    compliance_generated_from: Optional[str] = None
    expected_output_document_type: Optional[str] = None
    linked_property_requirement_id: Optional[str] = None


class WorkOrderUpdateBody(BaseModel):
    status: Optional[str] = None
    contractor_id: Optional[str] = None
    resolution_outcome: Optional[str] = None
    cost_estimate_min: Optional[float] = None
    cost_estimate_max: Optional[float] = None


@router.post("/work-orders", dependencies=[Depends(require_owner_or_admin)])
async def create_work_order(request: Request, body: WorkOrderCreateBody):
    """Create a work order (admin). Owner or Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": body.property_id, "client_id": body.client_id},
        {"_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found for this client")
    wk = (body.work_order_kind or "MAINTENANCE").strip().upper()
    doc = await maintenance_service.create_work_order(
        client_id=body.client_id,
        property_id=body.property_id,
        description=body.description,
        source=maintenance_service.SOURCE_ADMIN,
        reporter_id=None,
        category=body.category,
        severity=body.severity,
        asset_id=body.asset_id,
        issue_id=body.issue_id,
        risk_signal_id=body.risk_signal_id,
        cost_estimate_min=body.cost_estimate_min,
        cost_estimate_max=body.cost_estimate_max,
        created_from=body.created_from or "admin",
        triggering_rule=body.triggering_rule,
        operational_root_key=body.operational_root_key,
        use_triage=wk != "COMPLIANCE",
        work_order_kind=wk,
        requirement_code=body.requirement_code,
        compliance_purpose=body.compliance_purpose,
        compliance_due_at=body.compliance_due_at,
        compliance_generated_from=body.compliance_generated_from,
        expected_output_document_type=body.expected_output_document_type,
        linked_property_requirement_id=body.linked_property_requirement_id,
    )
    return doc


@router.get("/risk-signal-regen-queue-summary")
async def risk_signal_regen_queue_summary(
    request: Request,
    sample_limit: int = Query(25, ge=1, le=100, description="Max recent DEAD/FAILED rows to return"),
):
    """
    Ops visibility: risk regen queue counts, oldest pending job, recent failures.
    Use for dashboards/alerts; pair with audit_logs (RISK_SIGNAL_REGEN_FAILED) for investigation.
    """
    await admin_route_guard(request)
    return await get_regen_queue_summary(sample_limit=sample_limit)


@router.get("/work-orders")
async def list_work_orders(
    request: Request,
    client_id: Optional[str] = Query(None),
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    contractor_id: Optional[str] = Query(None),
    work_order_kind: Optional[str] = Query(
        None, description="MAINTENANCE | COMPLIANCE (filters list when set)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List work orders. Admin only."""
    await admin_route_guard(request)
    result = await maintenance_service.list_work_orders(
        client_id=client_id,
        property_id=property_id,
        status=status,
        contractor_id=contractor_id,
        work_order_kind=work_order_kind,
        skip=skip,
        limit=limit,
    )
    return result


@router.get("/work-orders/{work_order_id}")
async def get_work_order(request: Request, work_order_id: str):
    """Get one work order by id."""
    await admin_route_guard(request)
    doc = await maintenance_service.get_work_order(work_order_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    pid = doc.get("property_id")
    cid = doc.get("client_id")
    if pid and cid:
        db = database.get_db()
        prop = await db.properties.find_one(
            {"property_id": pid, "client_id": cid},
            {"_id": 0, "jurisdiction": 1},
        )
        client_row = await db.clients.find_one(
            {"client_id": cid},
            {"_id": 0, "default_jurisdiction": 1},
        )
        if prop is not None:
            att = jurisdiction_attribution_for_property(prop, client_row or {})
            doc = dict(doc)
            doc["property_effective_jurisdiction_label"] = att.get("effective_jurisdiction_label")
            doc["property_jurisdiction_source"] = att.get("jurisdiction_source")
    return doc


@router.get("/work-orders/{work_order_id}/contractor-evidence/file")
async def download_contractor_evidence_file(
    request: Request,
    work_order_id: str,
    storage_key: str = Query(..., min_length=3),
    download: bool = Query(False),
):
    """Admin: view or download contractor evidence file for a work order."""
    await admin_route_guard(request)
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
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
    user = getattr(request.state, "user", None) or {}
    actor_id = user.get("portal_user_id") or user.get("email") or user.get("user_id") or "admin"
    await create_audit_log(
        action=AuditAction.CONTRACTOR_EVIDENCE_DOWNLOADED,
        actor_id=actor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={
            "storage_key": contractor_evidence_service.normalize_evidence_storage_key(storage_key),
            "download": download,
            "via": "admin_ops",
        },
    )
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(path),
        media_type=media,
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/work-orders/{work_order_id}/recommend-contractors")
async def recommend_contractors(request: Request, work_order_id: str, limit: int = Query(10, ge=1, le=50)):
    """
    Ranked contractor recommendations: eligibility-gated (active, vetted, portal activated), trade/location,
    workload, performance, SLA history, client preference. Returns score_breakdown, reasons, and routing
    (assignment_urgency, SLA flags). Advisory only — admin confirms assignment unless auto-assign env policy is on.
    """
    await admin_route_guard(request)
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    result = await contractor_service.recommend_contractors_for_work_order(
        work_order_id=work_order_id,
        client_id=wo.get("client_id"),
        limit=limit,
    )
    return result


@router.patch("/work-orders/{work_order_id}", dependencies=[Depends(require_owner_or_admin)])
async def update_work_order(request: Request, work_order_id: str, body: WorkOrderUpdateBody):
    """Update work order status and/or assign contractor. Owner or Admin only."""
    await admin_route_guard(request)
    user = getattr(request.state, "user", None) or {}
    assigned_by = (body.contractor_id and (user.get("email") or user.get("portal_user_id") or user.get("user_id"))) or None
    try:
        doc = await maintenance_service.update_work_order(
            work_order_id,
            status=body.status,
            contractor_id=body.contractor_id,
            resolution_outcome=body.resolution_outcome,
            cost_estimate_min=body.cost_estimate_min,
            cost_estimate_max=body.cost_estimate_max,
            assigned_by=assigned_by,
            allow_direct_contractor_assignment=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    return doc


class AdminScheduleProposeBody(BaseModel):
    scheduled_at: str
    timezone: str = Field(..., description="IANA timezone e.g. Europe/London")
    notes: Optional[str] = Field(None, max_length=4000)


class AdminScheduleRescheduleBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


def _admin_schedule_actor(request: Request) -> tuple[Optional[str], Optional[str]]:
    user = getattr(request.state, "user", None) or {}
    return user.get("portal_user_id") or user.get("email") or user.get("user_id"), user.get("role")


@router.post("/work-orders/{work_order_id}/schedule/propose", dependencies=[Depends(require_owner_or_admin)])
async def admin_schedule_propose(request: Request, work_order_id: str, body: AdminScheduleProposeBody):
    await admin_route_guard(request)
    actor_id, role = _admin_schedule_actor(request)
    try:
        return await wo_schedule.propose_schedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_ADMIN,
            actor_id=actor_id,
            actor_role=role,
            scheduled_at_raw=body.scheduled_at,
            timezone_name=body.timezone,
            notes=body.notes,
            admin=True,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work-orders/{work_order_id}/schedule/confirm", dependencies=[Depends(require_owner_or_admin)])
async def admin_schedule_confirm(request: Request, work_order_id: str):
    await admin_route_guard(request)
    actor_id, role = _admin_schedule_actor(request)
    try:
        return await wo_schedule.confirm_schedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_ADMIN,
            actor_id=actor_id,
            actor_role=role,
            admin=True,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work-orders/{work_order_id}/schedule/reschedule-request", dependencies=[Depends(require_owner_or_admin)])
async def admin_schedule_reschedule_request(request: Request, work_order_id: str, body: AdminScheduleRescheduleBody):
    await admin_route_guard(request)
    actor_id, role = _admin_schedule_actor(request)
    try:
        return await wo_schedule.request_reschedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_ADMIN,
            actor_id=actor_id,
            actor_role=role,
            reason=body.reason,
            admin=True,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work-orders/{work_order_id}/schedule/cancel", dependencies=[Depends(require_owner_or_admin)])
async def admin_schedule_cancel(request: Request, work_order_id: str):
    await admin_route_guard(request)
    actor_id, role = _admin_schedule_actor(request)
    try:
        return await wo_schedule.cancel_schedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_ADMIN,
            actor_id=actor_id,
            actor_role=role,
            admin=True,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/work-orders/{work_order_id}/schedule/ics")
async def admin_schedule_ics(request: Request, work_order_id: str):
    await admin_route_guard(request)
    try:
        data, filename = await wo_schedule.get_schedule_ics_payload(work_order_id, admin=True)
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=data,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
