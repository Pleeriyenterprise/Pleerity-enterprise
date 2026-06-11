"""Admin manual job execution governance — scope matrix and impact preview."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from database import database
from job_runner import JOB_RUNNERS
from middleware import admin_route_guard
from services.job_execution_governance import (
    ExecutionRequest,
    ExecutionScopeType,
    estimate_execution_impact,
    get_governance_matrix,
    get_job_governance,
    infer_scope_type,
    validate_execution_request,
)

router = APIRouter(prefix="/api/admin/jobs", tags=["admin-job-execution"])


class JobExecutionPreviewBody(BaseModel):
    job: str
    scope_type: Optional[str] = None
    client_id: Optional[str] = None
    client_ids: Optional[List[str]] = None
    property_id: Optional[str] = None
    property_ids: Optional[List[str]] = None
    plan_code: Optional[str] = None
    jurisdiction: Optional[str] = None
    cohort_filter: Optional[str] = None
    portfolio_wide: bool = False
    portfolio_wide_confirmed: bool = False


def _body_to_request(body: JobExecutionPreviewBody, reason: str = "preview") -> ExecutionRequest:
    try:
        scope = infer_scope_type(
            scope_type=body.scope_type,
            client_id=body.client_id,
            property_id=body.property_id,
            client_ids=body.client_ids,
            plan_code=body.plan_code,
            jurisdiction=body.jurisdiction,
            cohort_filter=body.cohort_filter,
            portfolio_wide=body.portfolio_wide,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExecutionRequest(
        scope_type=scope,
        client_id=body.client_id,
        client_ids=body.client_ids,
        property_id=body.property_id,
        property_ids=body.property_ids,
        plan_code=body.plan_code,
        jurisdiction=body.jurisdiction,
        cohort_filter=body.cohort_filter,
        portfolio_wide=body.portfolio_wide or scope == ExecutionScopeType.PORTFOLIO_WIDE,
        portfolio_wide_confirmed=body.portfolio_wide_confirmed,
        reason=reason,
    )


@router.get("/execution-governance")
async def list_job_execution_governance(current_user: dict = Depends(admin_route_guard)):
    _ = current_user
    return get_governance_matrix()


@router.get("/{job_id}/execution-governance")
async def get_job_execution_governance(job_id: str, current_user: dict = Depends(admin_route_guard)):
    _ = current_user
    jid = (job_id or "").strip()
    if jid not in JOB_RUNNERS:
        raise HTTPException(status_code=404, detail=f"Unknown job: {jid}")
    return get_job_governance(jid)


@router.post("/execution-preview")
async def preview_job_execution(body: JobExecutionPreviewBody, current_user: dict = Depends(admin_route_guard)):
    _ = current_user
    job_id = (body.job or "").strip()
    if not job_id or job_id not in JOB_RUNNERS:
        raise HTTPException(status_code=400, detail="Invalid job id")
    req = _body_to_request(body, reason="impact preview")
    # Preview skips reason length for non-portfolio scopes
    if req.scope_type != ExecutionScopeType.PORTFOLIO_WIDE:
        req.reason = "preview only"
    scope_err = validate_execution_request(job_id, req)
    if scope_err and req.scope_type != ExecutionScopeType.PORTFOLIO_WIDE:
        # Allow preview even before reason entered (except portfolio-wide)
        partial_err = validate_scope_for_job_preview(job_id, req)
        if partial_err:
            raise HTTPException(status_code=400, detail=partial_err)
    elif scope_err:
        raise HTTPException(status_code=400, detail=scope_err)
    db = database.get_db()
    return await estimate_execution_impact(db, job_id, req)


def validate_scope_for_job_preview(job_id: str, req: ExecutionRequest) -> Optional[str]:
    from services.job_execution_governance import validate_scope_for_job

    err = validate_scope_for_job(job_id, req.scope_type)
    if err:
        return err
    if req.scope_type == ExecutionScopeType.CLIENT and not (req.client_id or "").strip():
        return "CLIENT scope requires client_id"
    if req.scope_type == ExecutionScopeType.PROPERTY and not (req.property_id or "").strip():
        return "PROPERTY scope requires property_id"
    if req.scope_type == ExecutionScopeType.CLIENT_GROUP and not req.client_ids:
        return "CLIENT_GROUP scope requires client_ids"
    if req.scope_type == ExecutionScopeType.PLAN and not (req.plan_code or "").strip():
        return "PLAN scope requires plan_code"
    if req.scope_type == ExecutionScopeType.JURISDICTION and not (req.jurisdiction or "").strip():
        return "JURISDICTION scope requires jurisdiction"
    if req.scope_type == ExecutionScopeType.FILTERED_COHORT and not (req.cohort_filter or "").strip():
        return "FILTERED_COHORT scope requires cohort_filter"
    return None
