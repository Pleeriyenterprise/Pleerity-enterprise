"""
Contractor job link API: access a single work order via secure token (no login).
Token is created when contractor is assigned; link is sent in assignment email.
All routes require a valid job token (query ?token= or header X-Job-Token).

Security model:
- Opaque random token; only a hash is stored server-side.
- Bound to exactly one work_order_id and contractor_id; reassignment revokes old tokens.
- Expires after CONTRACTOR_JOB_TOKEN_TTL_DAYS (default 30, max 365; increase via env for long jobs).
- No public listing; guessing tokens is infeasible.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Request, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

from database import database
from services import maintenance_service
from services import invoice_service
from services import contractor_service
from services import contractor_evidence_service
from services.work_order_execution_constants import (
    COMPLIANCE_BOOKING_AWAITING_CONTRACTOR_RESPONSE,
    COMPLIANCE_BOOKING_BOOKING_REQUESTED,
    COMPLIANCE_BOOKING_CONTRACTOR_NOTIFIED,
    COMPLIANCE_BOOKING_IN_PROGRESS,
    COMPLIANCE_BOOKING_OPERATIONALLY_COMPLETE,
    COMPLIANCE_BOOKING_PENDING_CLIENT_CONFIRMATION,
    COMPLIANCE_BOOKING_SCHEDULED,
    COMPLIANCE_PROOF_NOT_SUBMITTED,
    COMPLIANCE_PROOF_SUBMITTED,
    COMPLIANCE_PROOF_VERIFIED,
)
from models import AuditAction
from utils.audit import create_audit_log
from utils.api_errors import log_api_error, structured_error
from auth import hash_token
from services import work_order_schedule_service as wo_schedule
from services.work_order_schedule_constants import SCHEDULE_ACTOR_CONTRACTOR
from services.contractor_work_order_status_policy import validate_contractor_status_patch
from services.compliance_workflow_service import apply_contractor_job_enrichment
from services.work_order_pricing_service import mark_inspection_complete_for_work_order, submit_quote_for_work_order
from services.contractor_workflow_usage_service import WORKFLOW_USAGE_EVENT_TO_ACTION, log_contractor_workflow_usage
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/job", tags=["contractor-job-link"])


def _job_link_error(status_code: int, error_code: str, message: str, *, retry_suggested: bool = False) -> None:
    log_api_error(
        logger,
        endpoint="GET/POST /api/job/*",
        error_type=error_code,
        message=message,
    )
    raise HTTPException(
        status_code=status_code,
        detail=structured_error(error_code, message, retry_suggested=retry_suggested),
    )


def _raise_job_work_order_not_found() -> None:
    """Consistent 404 when the work order document is missing (deleted / wrong id)."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=structured_error(
            "JOB_WORK_ORDER_NOT_FOUND",
            "This job is no longer available — it may have been removed. Contact the client if you still need access.",
        ),
    )


def _raise_job_not_assigned_to_token_contractor() -> None:
    """Consistent 404 when the token's contractor no longer matches the work order (reassignment, etc.)."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=structured_error(
            "JOB_NOT_ASSIGNED_TO_YOU",
            "This link no longer matches the current assignment (the job may have been reassigned). Ask the client to send you a new assignment link.",
        ),
    )


def _compliance_booking_status_contractor_hint(status: Optional[str]) -> str:
    s = (status or "").strip().upper()
    if s == COMPLIANCE_BOOKING_AWAITING_CONTRACTOR_RESPONSE:
        return (
            "The client confirmed you for this compliance job. Add a visit time (scheduled date/time) or update "
            "status as you progress."
        )
    if s == COMPLIANCE_BOOKING_CONTRACTOR_NOTIFIED:
        return "You have been assigned; add a proposed visit time or update the job status when you start."
    if s == COMPLIANCE_BOOKING_PENDING_CLIENT_CONFIRMATION:
        return "The client is still confirming a contractor — you may receive this link after they confirm."
    if s == COMPLIANCE_BOOKING_BOOKING_REQUESTED:
        return "This compliance job is being set up."
    if s == COMPLIANCE_BOOKING_SCHEDULED:
        return "A visit time is on file. Update status when work is underway or complete."
    if s == COMPLIANCE_BOOKING_IN_PROGRESS:
        return "Work is in progress. Upload the required certificate or evidence when finished."
    if s == COMPLIANCE_BOOKING_OPERATIONALLY_COMPLETE:
        return "Operational work is marked complete; the client or platform may still verify evidence."
    return "Use the job actions to schedule, progress, and complete this compliance work."


def _compliance_proof_status_contractor_hint(status: Optional[str]) -> str:
    s = (status or "").strip().upper()
    if s == COMPLIANCE_PROOF_VERIFIED:
        return (
            "Certificate or evidence for this job has been verified. The client’s regulatory obligation can show as satisfied."
        )
    if s == COMPLIANCE_PROOF_SUBMITTED:
        return (
            "Evidence is on file but may still need client or platform verification before the obligation is fully satisfied."
        )
    if s == COMPLIANCE_PROOF_NOT_SUBMITTED:
        return "Required certificate or evidence has not been submitted yet."
    return "Proof status is being tracked; upload the expected certificate when the work is done."


async def get_job_context(
    token: Optional[str] = None,
    x_job_token: Optional[str] = None,
) -> dict:
    """Validate job token and return work_order_id, contractor_id. Raises 401 if invalid."""
    raw = (token or x_job_token or "").strip()
    if not raw:
        _job_link_error(
            status.HTTP_401_UNAUTHORIZED,
            "JOB_TOKEN_MISSING",
            "A secure job link token is required. Open the link from your assignment email or paste the full URL.",
            retry_suggested=False,
        )
    token_hash = hash_token(raw)
    db = database.get_db()
    doc = await db.contractor_job_tokens.find_one({"token_hash": token_hash})
    if not doc:
        _job_link_error(
            status.HTTP_401_UNAUTHORIZED,
            "JOB_TOKEN_INVALID",
            "This job link is not valid. Request a new assignment email from the client.",
            retry_suggested=False,
        )
    if doc.get("revoked_at"):
        _job_link_error(
            status.HTTP_401_UNAUTHORIZED,
            "JOB_TOKEN_REVOKED",
            "This job link is no longer valid. Ask the client to resend the assignment.",
            retry_suggested=False,
        )
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
                _job_link_error(
                    status.HTTP_401_UNAUTHORIZED,
                    "JOB_TOKEN_EXPIRED",
                    "This job link has expired. Ask the client to send a fresh assignment link.",
                    retry_suggested=False,
                )
        except (ValueError, TypeError):
            pass
    contractor = await db.contractors.find_one(
        {"contractor_id": doc["contractor_id"]},
        {"_id": 0, "status": 1, "portal_access_status": 1},
    )
    if not contractor:
        _job_link_error(
            status.HTTP_401_UNAUTHORIZED,
            "JOB_TOKEN_CONTRACTOR_MISSING",
            "This link is no longer valid — the contractor record is missing. Contact the client.",
            retry_suggested=False,
        )
    if (contractor.get("status") or "").lower() != contractor_service.STATUS_ACTIVE:
        _job_link_error(
            status.HTTP_401_UNAUTHORIZED,
            "CONTRACTOR_NOT_ACTIVE",
            "Your contractor profile is not active, so this job link cannot be used. Contact the client.",
            retry_suggested=False,
        )
    if (contractor.get("portal_access_status") or "").lower() == contractor_service.PORTAL_ACCESS_DISABLED:
        _job_link_error(
            status.HTTP_401_UNAUTHORIZED,
            "CONTRACTOR_PORTAL_DISABLED",
            "Portal access is disabled for this contractor account. Ask the client to re-enable access.",
            retry_suggested=False,
        )
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
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
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
    if (wo.get("work_order_kind") or "").strip().upper() == "COMPLIANCE":
        proof_st = wo.get("compliance_proof_status")
        booking_st = wo.get("compliance_booking_status")
        wo["compliance_execution"] = {
            "requirement_code": wo.get("requirement_code"),
            "compliance_purpose": wo.get("compliance_purpose"),
            "expected_output_document_type": wo.get("expected_output_document_type"),
            "compliance_booking_status": booking_st,
            "compliance_booking_status_hint": _compliance_booking_status_contractor_hint(
                booking_st if isinstance(booking_st, str) else None
            ),
            "compliance_proof_status": proof_st,
            "compliance_proof_status_hint": _compliance_proof_status_contractor_hint(
                proof_st if isinstance(proof_st, str) else None
            ),
            "scheduled_at": wo.get("scheduled_at"),
            "linked_property_requirement_id": wo.get("linked_property_requirement_id"),
        }
    inv = await invoice_service.contractor_best_invoice_for_work_order(contractor_id, work_order_id)
    apply_contractor_job_enrichment(wo, invoice=inv)
    return wo


def _job_link_client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


class JobWorkflowUsageBody(BaseModel):
    """Usage beacons from the secure job link UI (same semantics as contractor portal)."""

    event_type: Literal["job_opened", "action_taken", "proof_uploaded", "job_completed"]
    action_id: Optional[str] = Field(None, max_length=160)


@router.post("/workflow-usage", status_code=status.HTTP_204_NO_CONTENT)
async def post_job_workflow_usage(
    request: Request,
    background_tasks: BackgroundTasks,
    body: JobWorkflowUsageBody,
    ctx: dict = Depends(job_context_dep),
):
    """Record job-link engagement; returns immediately while audit write runs in the background.

    Semantics: see ``services.contractor_workflow_usage_service`` module docstring (usage vs operational audit).
    """

    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    if body.event_type == "action_taken" and not (body.action_id or "").strip():
        raise HTTPException(status_code=400, detail="action_id is required for action_taken")
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
    action = WORKFLOW_USAGE_EVENT_TO_ACTION[body.event_type]
    meta = {}
    if body.action_id and body.event_type == "action_taken":
        meta["action_id"] = (body.action_id or "").strip()
    background_tasks.add_task(
        log_contractor_workflow_usage,
        action=action,
        contractor_id=contractor_id,
        work_order_id=work_order_id,
        client_id=wo.get("client_id"),
        metadata=meta or None,
        ip_address=_job_link_client_ip(request),
        source="job_link",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class UpdateWorkOrderBody(BaseModel):
    status: Optional[str] = None
    contractor_notes: Optional[str] = None
    completion_notes: Optional[str] = None
    evidence_keys: Optional[List[str]] = None
    scheduled_at: Optional[str] = None


@router.patch("/work-order")
async def update_work_order(request: Request, body: UpdateWorkOrderBody, ctx: dict = Depends(job_context_dep)):
    """Update status, notes, or append evidence for the job."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
    status_val = (body.status or "").strip().upper() if body.status else None
    if status_val:
        ok, policy_err = validate_contractor_status_patch(wo.get("status"), status_val)
        if not ok:
            raise HTTPException(status_code=400, detail=policy_err or "Invalid status transition")
    try:
        updated = await maintenance_service.update_work_order(
            work_order_id=work_order_id,
            status=body.status,
            contractor_notes=body.contractor_notes,
            completion_notes=body.completion_notes,
            evidence_keys_append=body.evidence_keys or [],
            scheduled_at=body.scheduled_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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


class JobScheduleProposeBody(BaseModel):
    scheduled_at: str
    timezone: str = Field(..., description="IANA timezone e.g. Europe/London")
    notes: Optional[str] = Field(None, max_length=4000)


class JobScheduleRescheduleBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


@router.post("/work-order/schedule/propose")
async def job_schedule_propose(request: Request, body: JobScheduleProposeBody, ctx: dict = Depends(job_context_dep)):
    actor_id = ctx["contractor_id"]
    try:
        return await wo_schedule.propose_schedule(
            ctx["work_order_id"],
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role="job_token",
            scheduled_at_raw=body.scheduled_at,
            timezone_name=body.timezone,
            notes=body.notes,
            contractor_id=ctx["contractor_id"],
        )
    except LookupError:
        _raise_job_work_order_not_found()
    except PermissionError:
        _raise_job_work_order_not_found()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work-order/schedule/confirm")
async def job_schedule_confirm(request: Request, ctx: dict = Depends(job_context_dep)):
    actor_id = ctx["contractor_id"]
    try:
        return await wo_schedule.confirm_schedule(
            ctx["work_order_id"],
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role="job_token",
            contractor_id=ctx["contractor_id"],
        )
    except LookupError:
        _raise_job_work_order_not_found()
    except PermissionError:
        _raise_job_work_order_not_found()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work-order/schedule/reschedule-request")
async def job_schedule_reschedule_request(request: Request, body: JobScheduleRescheduleBody, ctx: dict = Depends(job_context_dep)):
    actor_id = ctx["contractor_id"]
    try:
        return await wo_schedule.request_reschedule(
            ctx["work_order_id"],
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role="job_token",
            reason=body.reason,
            contractor_id=ctx["contractor_id"],
        )
    except LookupError:
        _raise_job_work_order_not_found()
    except PermissionError:
        _raise_job_work_order_not_found()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work-order/schedule/cancel")
async def job_schedule_cancel(request: Request, ctx: dict = Depends(job_context_dep)):
    actor_id = ctx["contractor_id"]
    try:
        return await wo_schedule.cancel_schedule(
            ctx["work_order_id"],
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id=actor_id,
            actor_role="job_token",
            contractor_id=ctx["contractor_id"],
        )
    except LookupError:
        _raise_job_work_order_not_found()
    except PermissionError:
        _raise_job_work_order_not_found()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class JobMarkNoAccessBody(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


_JOB_LINK_TERMINAL_OE = frozenset(
    {
        maintenance_service.STATUS_CANCELLED,
        maintenance_service.STATUS_COMPLETED,
        maintenance_service.STATUS_CLOSED,
        maintenance_service.STATUS_VERIFIED,
    }
)


@router.post("/work-order/mark-no-access")
async def job_mark_no_access(
    request: Request,
    body: JobMarkNoAccessBody = Body(default_factory=JobMarkNoAccessBody),
    ctx: dict = Depends(job_context_dep),
):
    """Job token: record no-access operational hold (aligned with contractor portal)."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
    st = (wo.get("status") or "").strip().upper()
    if st in (maintenance_service.STATUS_OPEN, maintenance_service.STATUS_ASSIGNED):
        raise HTTPException(status_code=400, detail="Accept the assignment before reporting access issues")
    if st in _JOB_LINK_TERMINAL_OE:
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
        metadata={
            "operational_exception": maintenance_service.OPERATIONAL_EXCEPTION_NO_ACCESS,
            "via": "job_link",
        },
    )
    return updated


@router.get("/work-order/schedule/ics")
async def job_schedule_ics(request: Request, ctx: dict = Depends(job_context_dep)):
    try:
        data, filename = await wo_schedule.get_schedule_ics_payload(
            ctx["work_order_id"],
            contractor_id=ctx["contractor_id"],
        )
    except LookupError:
        _raise_job_work_order_not_found()
    except PermissionError:
        _raise_job_work_order_not_found()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=data,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/work-order/accept")
async def accept_assignment(request: Request, ctx: dict = Depends(job_context_dep)):
    """Accept the assignment. Sets status to SCHEDULED."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _job_link_error(
            status.HTTP_404_NOT_FOUND,
            "WORK_ORDER_NOT_FOUND",
            "This work order was not found. The link may be out of date.",
            retry_suggested=False,
        )
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _job_link_error(
            status.HTTP_404_NOT_FOUND,
            "WORK_ORDER_NOT_ASSIGNED",
            "This job is not assigned to you. Use the link from your latest assignment email.",
            retry_suggested=False,
        )
    if (wo.get("status") or "").upper() not in (maintenance_service.STATUS_ASSIGNED, maintenance_service.STATUS_OPEN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "ASSIGNMENT_WRONG_STATE",
                "This job cannot be accepted in its current state. Refresh the page, or contact the client if the job was updated.",
                retry_suggested=True,
                current_status=(wo.get("status") or ""),
            ),
        )
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
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
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
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
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
    evidence_semantics = maintenance_service.derive_work_order_evidence_semantics(updated)
    return {
        "storage_key": storage_key,
        "work_order": updated,
        "message": "Evidence uploaded. It still needs landlord/admin review before it counts as verified.",
        "verification_status": "PENDING_REVIEW",
        "uploaded_is_verified": evidence_semantics.get("uploaded_is_verified", False),
        "evidence_review_state": evidence_semantics.get("evidence_review_state", "pending_review"),
        "evidence_requires_review": evidence_semantics.get("evidence_requires_review", True),
        "evidence_authority_note": evidence_semantics.get("evidence_authority_note"),
        "completed_work_is_compliant": evidence_semantics.get("completed_work_is_compliant", False),
        "evidence_count": evidence_semantics.get("evidence_count", len(updated.get("evidence_keys") or [])),
    }


@router.post("/work-order/decline")
async def decline_assignment(request: Request, ctx: dict = Depends(job_context_dep)):
    """Decline the assignment. Clears contractor_id and sets status to OPEN."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
    result = await maintenance_service.contractor_decline_assignment(work_order_id, contractor_id)
    if not result:
        _raise_job_not_assigned_to_token_contractor()
    await create_audit_log(
        action=AuditAction.CONTRACTOR_DECLINED_ASSIGNMENT,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"via": "job_link"},
    )
    return result


@router.post("/work-order/reject")
async def reject_assignment_alias(request: Request, ctx: dict = Depends(job_context_dep)):
    """Alias for decline assignment to preserve contractor action semantics."""
    return await decline_assignment(request, ctx)


class SubmitInvoiceBody(BaseModel):
    reference: Optional[str] = Field(None, max_length=500)
    contractor_reference: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    submitted_amount: float = Field(..., gt=0)
    currency: Optional[str] = "GBP"
    attachment_storage_key: Optional[str] = None


class JobLinkSubmitQuoteBody(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GBP", max_length=12)
    notes: Optional[str] = Field(None, max_length=4000)


@router.post("/submit-quote")
async def job_link_submit_quote(request: Request, body: JobLinkSubmitQuoteBody, ctx: dict = Depends(job_context_dep)):
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    try:
        await submit_quote_for_work_order(
            work_order_id,
            contractor_id,
            amount=body.amount,
            currency=body.currency or "GBP",
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _raise_job_work_order_not_found()
    inv = await invoice_service.contractor_best_invoice_for_work_order(contractor_id, work_order_id)
    apply_contractor_job_enrichment(wo, invoice=inv)
    return wo


@router.post("/mark-inspection-complete")
async def job_link_mark_inspection_complete(request: Request, ctx: dict = Depends(job_context_dep)):
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    try:
        await mark_inspection_complete_for_work_order(work_order_id, contractor_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _raise_job_work_order_not_found()
    inv = await invoice_service.contractor_best_invoice_for_work_order(contractor_id, work_order_id)
    apply_contractor_job_enrichment(wo, invoice=inv)
    return wo


@router.post("/invoices")
async def submit_invoice(request: Request, body: SubmitInvoiceBody, ctx: dict = Depends(job_context_dep)):
    """Submit an invoice for this job's work order. work_order_id is taken from the token."""
    work_order_id = ctx["work_order_id"]
    contractor_id = ctx["contractor_id"]
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        _raise_job_work_order_not_found()
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        _raise_job_not_assigned_to_token_contractor()
    if not wo.get("property_id") or not wo.get("client_id"):
        raise HTTPException(status_code=400, detail="Work order missing property or client")
    try:
        doc, kind = await invoice_service.contractor_submit_or_resubmit_for_work_order(
            wo,
            contractor_id,
            reference=body.reference,
            contractor_reference=body.contractor_reference,
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
            metadata={"work_order_id": work_order_id, "submitted_amount": body.submitted_amount, "via": "job_link"},
        )
    return doc
