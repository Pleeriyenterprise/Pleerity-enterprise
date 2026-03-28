"""
Contractor portal API: work orders assigned to the contractor, status updates, evidence, invoice submission.
All routes require contractor_route_guard (JWT with role=ROLE_CONTRACTOR and contractor_id).
Contractors only see and act on work orders where contractor_id matches their own.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from database import database
from middleware import contractor_route_guard
from services import maintenance_service
from services import invoice_service
from services import contractor_service
from services import contractor_evidence_service
from models import AuditAction
from utils.audit import create_audit_log

router = APIRouter(prefix="/api/contractor", tags=["contractor-portal"], dependencies=[Depends(contractor_route_guard)])


def _ensure_assigned_to_me(work_order: dict, contractor_id: str) -> None:
    if (work_order.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found or not assigned to you")


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
    return wo


class UpdateWorkOrderBody(BaseModel):
    status: Optional[str] = None
    contractor_notes: Optional[str] = None
    completion_notes: Optional[str] = None
    evidence_keys: Optional[List[str]] = None  # append these storage keys


@router.patch("/work-orders/{work_order_id}")
async def update_my_work_order(request: Request, work_order_id: str, body: UpdateWorkOrderBody):
    """Update status, notes, or append evidence. Only work orders assigned to this contractor."""
    user = await contractor_route_guard(request)
    contractor_id = user.get("contractor_id")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _ensure_assigned_to_me(wo, contractor_id)
    # Contractor may set status to SCHEDULED, IN_PROGRESS, AWAITING_PARTS, COMPLETED (not OPEN/ASSIGNED or unassign)
    allowed_statuses = (
        maintenance_service.STATUS_SCHEDULED,
        maintenance_service.STATUS_IN_PROGRESS,
        maintenance_service.STATUS_AWAITING_PARTS,
        maintenance_service.STATUS_COMPLETED,
    )
    status_val = (body.status or "").strip().upper() if body.status else None
    if status_val and status_val not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Contractors can only set status to SCHEDULED, IN_PROGRESS, AWAITING_PARTS, or COMPLETED")
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
    return updated


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
    return updated or wo


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
    reference: Optional[str] = None
    description: Optional[str] = None
    submitted_amount: Optional[float] = None
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
        doc = await invoice_service.create_invoice(
            client_id=wo["client_id"],
            property_id=wo["property_id"],
            contractor_id=contractor_id,
            work_order_id=body.work_order_id,
            reference=(body.reference or "").strip() or None,
            description=body.description,
            submitted_amount=body.submitted_amount,
            currency=body.currency or "GBP",
            attachment_storage_key=body.attachment_storage_key,
            source=invoice_service.SOURCE_CONTRACTOR,
            created_by_id=contractor_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await create_audit_log(
        action=AuditAction.CONTRACTOR_INVOICE_SUBMITTED,
        actor_id=contractor_id,
        client_id=wo["client_id"],
        resource_type="invoice",
        resource_id=doc.get("invoice_id"),
        metadata={"work_order_id": body.work_order_id, "submitted_amount": body.submitted_amount},
    )
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
    }
