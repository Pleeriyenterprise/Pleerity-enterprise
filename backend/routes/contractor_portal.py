"""
Contractor portal API: work orders assigned to the contractor, status updates, evidence, invoice submission.
All routes require contractor_route_guard (JWT with role=ROLE_CONTRACTOR and contractor_id).
Contractors only see and act on work orders where contractor_id matches their own.
"""
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

from database import database
from middleware import contractor_route_guard
from services import maintenance_service
from services import invoice_service
from services import contractor_service
from services import contractor_evidence_service
from models import AuditAction
from utils.audit import create_audit_log
from services import work_order_schedule_service as wo_schedule
from services.work_order_schedule_constants import SCHEDULE_ACTOR_CONTRACTOR
from routes.contractor_dashboard_summary import build_contractor_dashboard_summary
from services.contractor_work_order_status_policy import validate_contractor_status_patch
from services.compliance_workflow_service import apply_contractor_job_enrichment
from services.contractor_workflow_usage_service import WORKFLOW_USAGE_EVENT_TO_ACTION, log_contractor_workflow_usage

router = APIRouter(prefix="/api/contractor", tags=["contractor-portal"], dependencies=[Depends(contractor_route_guard)])


def _request_client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


class ContractorWorkflowUsageBody(BaseModel):
    """Fire-and-forget usage beacons from the contractor portal (non-blocking for the UI)."""

    event_type: Literal["job_opened", "action_taken", "proof_uploaded", "job_completed"]
    work_order_id: str = Field(..., min_length=1, max_length=120)
    action_id: Optional[str] = Field(None, max_length=160)


@router.post("/workflow-usage", status_code=status.HTTP_204_NO_CONTENT)
async def post_contractor_workflow_usage(
    request: Request,
    body: ContractorWorkflowUsageBody,
    background_tasks: BackgroundTasks,
):
    """Record contractor workflow engagement; returns immediately while audit write runs in the background.

    Semantics: see ``services.contractor_workflow_usage_service`` module docstring (usage vs operational audit).
    """

    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    if not contractor_id:
        raise HTTPException(status_code=403, detail="Contractor context required")
    if body.event_type == "action_taken" and not (body.action_id or "").strip():
        raise HTTPException(status_code=400, detail="action_id is required for action_taken")
    wo = await maintenance_service.get_work_order(body.work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    action = WORKFLOW_USAGE_EVENT_TO_ACTION[body.event_type]
    meta = {}
    if body.action_id and body.event_type == "action_taken":
        meta["action_id"] = (body.action_id or "").strip()
    background_tasks.add_task(
        log_contractor_workflow_usage,
        action=action,
        contractor_id=contractor_id,
        work_order_id=body.work_order_id,
        client_id=wo.get("client_id"),
        metadata=meta or None,
        ip_address=_request_client_ip(request),
        source="contractor_portal",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _invoice_rank(inv: dict) -> int:
    s = (inv.get("status") or "").lower()
    return {"paid": 5, "approved": 4, "pending": 3, "needs_info": 2, "rejected": 1}.get(s, 0)


async def _best_invoices_by_work_order(db, contractor_id: str, work_order_ids: list) -> dict:
    ids = [w for w in work_order_ids if w]
    if not ids or not contractor_id:
        return {}
    cursor = db.invoices.find(
        {"contractor_id": contractor_id, "work_order_id": {"$in": list(set(ids))}},
        {"_id": 0},
    )
    items = await cursor.to_list(length=1000)
    best: dict = {}
    for inv in items:
        w = inv.get("work_order_id")
        if not w:
            continue
        prev = best.get(w)
        if not prev or _invoice_rank(inv) > _invoice_rank(prev):
            best[w] = inv
    return best


async def _enrich_contractor_work_order(db, wo: dict, contractor_id: str) -> None:
    wid = wo.get("work_order_id")
    inv_map = await _best_invoices_by_work_order(db, contractor_id, [wid] if wid else [])
    apply_contractor_job_enrichment(wo, invoice=inv_map.get(wid))


_TERMINAL_FOR_CONTRACTOR_OE = frozenset(
    {
        maintenance_service.STATUS_CANCELLED,
        maintenance_service.STATUS_COMPLETED,
        maintenance_service.STATUS_CLOSED,
        maintenance_service.STATUS_VERIFIED,
    }
)


def _ensure_assigned_to_me(work_order: dict, contractor_id: str) -> None:
    if (work_order.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found or not assigned to you")


@router.get("/dashboard-summary")
async def contractor_dashboard_summary(request: Request):
    """Aggregated queue counts and earnings for the contractor home dashboard."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    if not contractor_id:
        raise HTTPException(status_code=403, detail="Contractor context required")
    return await build_contractor_dashboard_summary(contractor_id)


@router.get("/work-orders")
async def list_my_work_orders(request: Request, status_filter: Optional[str] = None, limit: int = 100):
    """List work orders assigned to the authenticated contractor."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    if not contractor_id:
        raise HTTPException(status_code=403, detail="Contractor context required")
    result = await maintenance_service.list_work_orders(
        contractor_id=contractor_id,
        status=status_filter,
        limit=limit,
    )
    # Enrich with property address for display (no sensitive client data beyond address)
    db = database.get_db()
    for wo in result.get("work_orders") or []:
        if wo.get("property_id") and wo.get("client_id"):
            prop = await db.properties.find_one(
                {"property_id": wo["property_id"], "client_id": wo["client_id"]},
                {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1, "nickname": 1},
            )
            if prop:
                wo["property_address"] = prop.get("nickname") or ", ".join(
                    p for p in [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")] if p
                ) or wo["property_id"]
    woids = [w.get("work_order_id") for w in result.get("work_orders") or [] if w.get("work_order_id")]
    inv_map = await _best_invoices_by_work_order(db, contractor_id, woids)
    for wo in result.get("work_orders") or []:
        apply_contractor_job_enrichment(wo, invoice=inv_map.get(wo.get("work_order_id")))
    return result


@router.get("/work-orders/{work_order_id}")
async def get_my_work_order(request: Request, work_order_id: str):
    """Get one work order detail. Only if assigned to this contractor."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    db = database.get_db()
    if wo.get("property_id") and wo.get("client_id"):
        prop = await db.properties.find_one(
            {"property_id": wo["property_id"], "client_id": wo["client_id"]},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1, "nickname": 1},
        )
        if prop:
            wo["property_address"] = prop.get("nickname") or ", ".join(
                p for p in [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")] if p
            ) or wo["property_id"]
    await _enrich_contractor_work_order(db, wo, contractor_id)
    return wo


class UpdateWorkOrderBody(BaseModel):
    status: Optional[str] = None
    contractor_notes: Optional[str] = None
    completion_notes: Optional[str] = None
    evidence_keys: Optional[List[str]] = None  # append these storage keys


class ContractorMarkNoAccessBody(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


@router.post("/work-orders/{work_order_id}/mark-no-access")
async def contractor_mark_no_access(
    request: Request,
    work_order_id: str,
    body: ContractorMarkNoAccessBody = Body(default_factory=ContractorMarkNoAccessBody),
):
    """Record a no-access operational hold (same semantics as client mark-no-access)."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    st = (wo.get("status") or "").strip().upper()
    if st in (maintenance_service.STATUS_OPEN, maintenance_service.STATUS_ASSIGNED):
        raise HTTPException(status_code=400, detail="Accept the assignment before reporting access issues")
    if st in _TERMINAL_FOR_CONTRACTOR_OE:
        raise HTTPException(status_code=400, detail="This job cannot be put on hold in its current state")
    if (wo.get("operational_exception") or "").strip():
        raise HTTPException(status_code=400, detail="This job is already on an operational hold")
    note = (body.notes or "").strip()
    merged_notes = None
    if note:
        prev = (wo.get("contractor_notes") or "").strip()
        line = f"[No access] {note}"
        merged_notes = f"{prev}\n{line}".strip() if prev else line
    try:
        updated = await maintenance_service.update_work_order(
            work_order_id,
            operational_exception=maintenance_service.OPERATIONAL_EXCEPTION_NO_ACCESS,
            assigned_by=contractor_id,
            contractor_notes=merged_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not updated:
        raise HTTPException(status_code=500, detail="Update failed")
    await create_audit_log(
        action=AuditAction.CONTRACTOR_WORK_ORDER_STATUS_CHANGED,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"operational_exception": maintenance_service.OPERATIONAL_EXCEPTION_NO_ACCESS, "via": "contractor_portal"},
    )
    db = database.get_db()
    await _enrich_contractor_work_order(db, updated, contractor_id)
    return updated


@router.patch("/work-orders/{work_order_id}")
async def update_my_work_order(request: Request, work_order_id: str, body: UpdateWorkOrderBody):
    """Update status, notes, or append evidence. Only work orders assigned to this contractor."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    status_val = (body.status or "").strip().upper() if body.status else None
    if status_val:
        ok, policy_err = validate_contractor_status_patch(wo.get("status"), status_val)
        if not ok:
            raise HTTPException(status_code=400, detail=policy_err or "Invalid status transition")
    updated = await maintenance_service.update_work_order(
        work_order_id=work_order_id,
        status=body.status,
        contractor_notes=body.contractor_notes,
        completion_notes=body.completion_notes,
        evidence_keys_append=body.evidence_keys or [],
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Update failed")
    if body.status:
        await create_audit_log(
            action=AuditAction.CONTRACTOR_WORK_ORDER_STATUS_CHANGED,
            actor_id=contractor_id,
            client_id=wo.get("client_id"),
            resource_type="work_order",
            resource_id=work_order_id,
            metadata={"old_status": wo.get("status"), "new_status": status_val},
        )
    if body.evidence_keys:
        await create_audit_log(
            action=AuditAction.CONTRACTOR_EVIDENCE_UPLOADED,
            actor_id=contractor_id,
            client_id=wo.get("client_id"),
            resource_type="work_order",
            resource_id=work_order_id,
            metadata={"keys_count": len(body.evidence_keys)},
        )
    db = database.get_db()
    await _enrich_contractor_work_order(db, updated, contractor_id)
    return updated


class ContractorScheduleProposeBody(BaseModel):
    scheduled_at: str
    timezone: str = Field(..., description="IANA timezone e.g. Europe/London")
    notes: Optional[str] = Field(None, max_length=4000)


class ContractorScheduleRescheduleBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


@router.post("/work-orders/{work_order_id}/schedule/propose")
async def contractor_schedule_propose(request: Request, work_order_id: str, body: ContractorScheduleProposeBody):
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    role = user.get("role")
    actor_id = user.get("portal_user_id") or user.get("email") or user.get("user_id") or contractor_id
    db = database.get_db()
    try:
        res = await wo_schedule.propose_schedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role=role,
            scheduled_at_raw=body.scheduled_at,
            timezone_name=body.timezone,
            notes=body.notes,
            contractor_id=contractor_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _enrich_contractor_work_order(db, res, contractor_id)
    return res


@router.post("/work-orders/{work_order_id}/schedule/confirm")
async def contractor_schedule_confirm(request: Request, work_order_id: str):
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    role = user.get("role")
    actor_id = user.get("portal_user_id") or user.get("email") or user.get("user_id") or contractor_id
    db = database.get_db()
    try:
        res = await wo_schedule.confirm_schedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role=role,
            contractor_id=contractor_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _enrich_contractor_work_order(db, res, contractor_id)
    return res


@router.post("/work-orders/{work_order_id}/schedule/reschedule-request")
async def contractor_schedule_reschedule_request(request: Request, work_order_id: str, body: ContractorScheduleRescheduleBody):
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    role = user.get("role")
    actor_id = user.get("portal_user_id") or user.get("email") or user.get("user_id") or contractor_id
    db = database.get_db()
    try:
        res = await wo_schedule.request_reschedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role=role,
            reason=body.reason,
            contractor_id=contractor_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _enrich_contractor_work_order(db, res, contractor_id)
    return res


@router.post("/work-orders/{work_order_id}/schedule/cancel")
async def contractor_schedule_cancel(request: Request, work_order_id: str):
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    role = user.get("role")
    actor_id = user.get("portal_user_id") or user.get("email") or user.get("user_id") or contractor_id
    db = database.get_db()
    try:
        res = await wo_schedule.cancel_schedule(
            work_order_id,
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role=role,
            contractor_id=contractor_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _enrich_contractor_work_order(db, res, contractor_id)
    return res


@router.get("/work-orders/{work_order_id}/schedule/ics")
async def contractor_schedule_ics(request: Request, work_order_id: str):
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    try:
        data, filename = await wo_schedule.get_schedule_ics_payload(work_order_id, contractor_id=contractor_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Work order not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=data,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/work-orders/{work_order_id}/accept")
async def accept_assignment(request: Request, work_order_id: str):
    """Mark assignment as accepted. Sets status to SCHEDULED."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    if (wo.get("status") or "").upper() not in (maintenance_service.STATUS_ASSIGNED, maintenance_service.STATUS_OPEN):
        raise HTTPException(status_code=400, detail="Work order is not in a state that can be accepted")
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = await maintenance_service.update_work_order(
        work_order_id=work_order_id,
        status=maintenance_service.STATUS_SCHEDULED,
        accepted_at=now_iso,
    )
    await create_audit_log(
        action=AuditAction.CONTRACTOR_ACCEPTED_ASSIGNMENT,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={},
    )
    out = updated if updated is not None else wo
    db = database.get_db()
    await _enrich_contractor_work_order(db, out, contractor_id)
    return out


@router.get("/work-orders/{work_order_id}/evidence/file")
async def download_work_order_evidence_file(
    request: Request,
    work_order_id: str,
    storage_key: str = Query(..., min_length=3),
    download: bool = Query(False),
):
    """View or download an evidence file for an assigned work order."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
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
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={
            "storage_key": contractor_evidence_service.normalize_evidence_storage_key(storage_key),
            "download": download,
            "via": "contractor_portal",
        },
    )
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(path),
        media_type=media,
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.post("/work-orders/{work_order_id}/evidence")
async def upload_work_order_evidence(request: Request, work_order_id: str, file: UploadFile = File(...)):
    """Multipart upload: stores file and appends a storage key to work order evidence_keys."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    try:
        content = await file.read()
        storage_key, updated = await contractor_evidence_service.save_contractor_work_order_evidence(
            work_order_id=work_order_id,
            contractor_id=contractor_id,
            filename=file.filename,
            content=content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to save evidence") from None
    await create_audit_log(
        action=AuditAction.CONTRACTOR_EVIDENCE_UPLOADED,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"storage_key": storage_key, "via": "multipart"},
    )
    db = database.get_db()
    await _enrich_contractor_work_order(db, updated, contractor_id)
    return {"storage_key": storage_key, "work_order": updated}


@router.post("/work-orders/{work_order_id}/decline")
async def decline_assignment(request: Request, work_order_id: str):
    """Decline assignment. Clears contractor_id and sets status back to OPEN."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    result = await maintenance_service.contractor_decline_assignment(work_order_id, contractor_id)
    if not result:
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
    await create_audit_log(
        action=AuditAction.CONTRACTOR_DECLINED_ASSIGNMENT,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={},
    )
    return result


class SubmitInvoiceBody(BaseModel):
    work_order_id: str
    reference: str = Field(..., min_length=1)
    description: Optional[str] = None
    submitted_amount: float = Field(..., gt=0)
    currency: Optional[str] = "GBP"
    attachment_storage_key: Optional[str] = None


class ResubmitInvoiceBody(BaseModel):
    reference: str = Field(..., min_length=1)
    description: Optional[str] = None
    submitted_amount: float = Field(..., gt=0)
    currency: Optional[str] = "GBP"
    attachment_storage_key: Optional[str] = None


@router.post("/invoices")
async def submit_invoice(request: Request, body: SubmitInvoiceBody):
    """Submit an invoice for a work order assigned to this contractor. Flows to client Approvals."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(body.work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    if not wo.get("property_id") or not wo.get("client_id"):
        raise HTTPException(status_code=400, detail="Work order missing property or client")
    try:
        doc, kind = await invoice_service.contractor_submit_or_resubmit_for_work_order(
            wo,
            contractor_id,
            reference=body.reference,
            description=body.description,
            submitted_amount=body.submitted_amount,
            currency=body.currency or "GBP",
            attachment_storage_key=body.attachment_storage_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if kind == "created":
        await create_audit_log(
            action=AuditAction.CONTRACTOR_INVOICE_SUBMITTED,
            actor_id=contractor_id,
            client_id=wo["client_id"],
            resource_type="invoice",
            resource_id=doc.get("invoice_id"),
            metadata={"work_order_id": body.work_order_id, "submitted_amount": body.submitted_amount},
        )
    return doc


@router.patch("/invoices/{invoice_id}/resubmit")
async def resubmit_invoice(request: Request, invoice_id: str, body: ResubmitInvoiceBody):
    """Resubmit an invoice after client needs_info or rejected (same contractor only)."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    if not contractor_id:
        raise HTTPException(status_code=403, detail="Contractor context required")
    try:
        doc = await invoice_service.contractor_resubmit_invoice(
            invoice_id,
            contractor_id,
            reference=body.reference,
            description=body.description,
            submitted_amount=body.submitted_amount,
            currency=body.currency or "GBP",
            attachment_storage_key=body.attachment_storage_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return doc


@router.get("/invoices")
async def list_my_invoices(request: Request, limit: int = 50):
    """List invoices submitted by this contractor (for portal 'My invoices')."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    if not contractor_id:
        raise HTTPException(status_code=403, detail="Contractor context required")
    db = database.get_db()
    cursor = db.invoices.find({"contractor_id": contractor_id}).sort("submitted_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    for inv in items:
        inv.pop("_id", None)
        if inv.get("submitted_at") and hasattr(inv["submitted_at"], "isoformat"):
            inv["submitted_at"] = inv["submitted_at"].isoformat()
        if inv.get("paid_at") and hasattr(inv["paid_at"], "isoformat"):
            inv["paid_at"] = inv["paid_at"].isoformat()
        if inv.get("reviewed_at") and hasattr(inv["reviewed_at"], "isoformat"):
            inv["reviewed_at"] = inv["reviewed_at"].isoformat()
        invoice_service.enrich_invoice_for_contractor_portal(inv)
    return {"invoices": items, "total": len(items)}


@router.get("/profile")
async def get_my_profile(request: Request):
    """Return the authenticated contractor's profile (safe fields only)."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    doc = await contractor_service.get_contractor(contractor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    # Return only display-safe fields
    return {
        "contractor_id": doc.get("contractor_id"),
        "name": doc.get("name"),
        "company_name": doc.get("company_name"),
        "trade_types": doc.get("trade_types"),
        "email": doc.get("email"),
        "phone": doc.get("phone"),
        "region": doc.get("region"),
        "account_status": doc.get("status"),
        "portal_access": doc.get("portal_access"),
    }
