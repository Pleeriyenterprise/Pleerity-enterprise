"""
Contractor job link API: access a single work order via secure token (no login).
Token is created when contractor is assigned; link is sent in assignment email.
All routes require a valid job token (query ?token= or header X-Job-Token).
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, HTTPException, Request, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from database import database
from services import maintenance_service
from services import invoice_service
from services import contractor_service
from services import contractor_evidence_service
from models import AuditAction
from utils.audit import create_audit_log
from auth import hash_token

router = APIRouter(prefix="/api/job", tags=["contractor-job-link"])


async def get_job_context(
    token: Optional[str] = None,
    x_job_token: Optional[str] = None,
) -> dict:
    """Validate job token and return work_order_id, contractor_id. Raises 401 if invalid."""
    raw = (token or x_job_token or "").strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Job token required (query ?token= or header X-Job-Token)")
    token_hash = hash_token(raw)
    db = database.get_db()
    doc = await db.contractor_job_tokens.find_one({"token_hash": token_hash})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired job link")
    if doc.get("revoked_at"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Job link is no longer valid")
    expires_at = doc.get("expires_at")
    if expires_at:
        try:
            if isinstance(expires_at, str):
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                exp_dt = expires_at
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Job link has expired")
        except (ValueError, TypeError):
            pass
    contractor = await db.contractors.find_one(
        {"contractor_id": doc["contractor_id"]},
        {"_id": 0, "status": 1, "portal_access_status": 1},
    )
    if not contractor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired job link")
    if (contractor.get("status") or "").lower() != contractor_service.STATUS_ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contractor access is no longer active")
    if (contractor.get("portal_access_status") or "").lower() == contractor_service.PORTAL_ACCESS_DISABLED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contractor access is no longer active")
    return {"work_order_id": doc["work_order_id"], "contractor_id": doc["contractor_id"]}


async def job_context_dep(request: Request, token: Optional[str] = Query(None, alias="token")):
    x_job_token = (request.headers.get("X-Job-Token") or "").strip() or None
    return await get_job_context(token=token, x_job_token=x_job_token)


@router.get("/work-order")
async def get_work_order(request: Request, ctx: dict = Depends(job_context_dep)):
    """Get the single work order for this job token."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
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
    evidence_keys: Optional[List[str]] = None


@router.patch("/work-order")
async def update_work_order(request: Request, body: UpdateWorkOrderBody, ctx: dict = Depends(job_context_dep)):
    """Update status, notes, or append evidence for the job."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
    allowed = (
        maintenance_service.STATUS_SCHEDULED,
        maintenance_service.STATUS_IN_PROGRESS,
        maintenance_service.STATUS_AWAITING_PARTS,
        maintenance_service.STATUS_COMPLETED,
    )
    status_val = (body.status or "").strip().upper() if body.status else None
    if status_val and status_val not in allowed:
        raise HTTPException(status_code=400, detail="Status must be one of: SCHEDULED, IN_PROGRESS, AWAITING_PARTS, COMPLETED")
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
            metadata={"old_status": wo.get("status"), "new_status": status_val, "via": "job_link"},
        )
    if body.evidence_keys:
        await create_audit_log(
            action=AuditAction.CONTRACTOR_EVIDENCE_UPLOADED,
            actor_id=contractor_id,
            client_id=wo.get("client_id"),
            resource_type="work_order",
            resource_id=work_order_id,
            metadata={"keys_count": len(body.evidence_keys), "via": "job_link"},
        )
    return updated


@router.post("/work-order/accept")
async def accept_assignment(request: Request, ctx: dict = Depends(job_context_dep)):
    """Accept the assignment. Sets status to SCHEDULED."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
    if (wo.get("status") or "").upper() not in (maintenance_service.STATUS_ASSIGNED, maintenance_service.STATUS_OPEN):
        raise HTTPException(status_code=400, detail="Work order is not in a state that can be accepted")
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
        metadata={"via": "job_link"},
    )
    return updated or wo


@router.get("/work-order/evidence/file")
async def download_work_order_evidence_file(
    request: Request,
    storage_key: str = Query(..., min_length=3),
    download: bool = Query(False),
    ctx: dict = Depends(job_context_dep),
):
    """Job token: view or download an evidence file for this work order."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
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
            "via": "job_link",
        },
    )
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(path),
        media_type=media,
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.post("/work-order/evidence")
async def upload_work_order_evidence(request: Request, file: UploadFile = File(...), ctx: dict = Depends(job_context_dep)):
    """Multipart evidence upload for the job token’s work order."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
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
        metadata={"storage_key": storage_key, "via": "job_link_multipart"},
    )
    return {"storage_key": storage_key, "work_order": updated}


@router.post("/work-order/decline")
async def decline_assignment(request: Request, ctx: dict = Depends(job_context_dep)):
    """Decline the assignment. Clears contractor_id and sets status to OPEN."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
    result = await maintenance_service.contractor_decline_assignment(work_order_id, contractor_id)
    if not result:
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
    await create_audit_log(
        action=AuditAction.CONTRACTOR_DECLINED_ASSIGNMENT,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"via": "job_link"},
    )
    return result


class SubmitInvoiceBody(BaseModel):
    reference: Optional[str] = None
    description: Optional[str] = None
    submitted_amount: Optional[float] = None
    currency: Optional[str] = "GBP"
    attachment_storage_key: Optional[str] = None


@router.post("/invoices")
async def submit_invoice(request: Request, body: SubmitInvoiceBody, ctx: dict = Depends(job_context_dep)):
    """Submit an invoice for this job's work order. work_order_id is taken from the token."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise HTTPException(status_code=404, detail="Work order not found or not assigned to you")
    if not wo.get("property_id") or not wo.get("client_id"):
        raise HTTPException(status_code=400, detail="Work order missing property or client")
    try:
        doc = await invoice_service.create_invoice(
            client_id=wo["client_id"],
            property_id=wo["property_id"],
            contractor_id=contractor_id,
            work_order_id=work_order_id,
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
        metadata={"work_order_id": work_order_id, "submitted_amount": body.submitted_amount, "via": "job_link"},
    )
    return doc
