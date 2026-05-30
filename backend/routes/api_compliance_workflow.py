"""
Top-level /api compliance workflow routes (client-authenticated).

These mirror the contract surface for requirements, compliance jobs (work orders), Today inbox,
and document validation. Property-scoped requirement listing lives on routes/properties.py
(GET /api/properties/{property_id}/requirements).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field

from database import database
from middleware import client_route_guard, contractor_route_guard
from models import AuditAction
from routes.documents import _enforce_document_upload_rate_limit, perform_client_document_upload
from services import contractor_service
from services import invoice_service
from services import maintenance_service
from services.compliance_booking_service import create_compliance_execution_work_order
from services.compliance_workflow_service import (
    apply_contractor_job_enrichment,
    derive_requirement_workflow_fields,
    find_active_compliance_job_for_requirement,
    load_client_work_order,
    load_compliance_work_order_for_client,
    maintenance_has_completion_evidence,
    serialize_client_job,
    serialize_compliance_job,
    work_order_has_proof_document,
)
from services import work_order_schedule_service as wo_schedule
from services.client_task_state_service import ACTION_DISMISS, ACTION_RESTORE, ACTION_REVIEWED, ACTION_SNOOZE, apply_task_action
from services.ops_compliance_feature_flags import COMPLIANCE_ENGINE, CONTRACTOR_NETWORK, MAINTENANCE_WORKFLOWS, get_effective_flags
from services.today_projection_service import build_today_payload_from_unified
from services.unified_tasks_service import get_unified_tasks_for_client
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE, WORK_ORDER_KIND_MAINTENANCE
from services.work_order_schedule_constants import SCHEDULE_ACTOR_CLIENT
from routes.contractor_job import get_job_context
from services.work_order_pricing_service import (
    approve_quote_for_work_order,
    mark_inspection_complete_for_work_order,
    reject_quote_final_for_work_order,
    reject_quote_for_work_order,
    request_quote_revision_for_work_order,
    submit_quote_for_work_order,
)
from services.requirement_evidence_authority import sync_requirement_evidence_authority
from services.requirement_transition_observability import (
    attach_downstream_trigger_observation,
    ensure_requirement_transition_correlation_id,
)
from utils.audit import create_audit_log
from utils.expiry_utils import get_computed_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["compliance-workflow"])


async def _require_client(request: Request) -> Dict[str, Any]:
    return await client_route_guard(request)


async def _require_compliance_jobs(request: Request) -> Dict[str, Any]:
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(COMPLIANCE_ENGINE) or not flags.get(MAINTENANCE_WORKFLOWS):
        raise HTTPException(
            status_code=403,
            detail="Compliance jobs require compliance engine and maintenance workflows for your account",
        )
    return user


async def _require_maintenance_workflows(request: Request) -> Dict[str, Any]:
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS):
        raise HTTPException(status_code=403, detail="Maintenance workflows are not enabled for your account")
    return user


def _actor_id(user: Dict[str, Any]) -> Optional[str]:
    return user.get("portal_user_id") or user.get("email") or user.get("user_id")


async def _client_requirement_row_eligible(db, user: Dict[str, Any], req: Optional[Dict[str, Any]]) -> bool:
    if not req:
        return False
    from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

    return await requirement_row_eligible_on_client_runtime_surfaces(
        db, client_id=str(user.get("client_id") or ""), row=req
    )


async def _resolve_contractor_for_job_pricing(request: Request, job_id: str) -> Dict[str, str]:
    """Contractor JWT or job token (?token= / X-Job-Token); validates assignment to job_id."""
    raw_q = (request.query_params.get("token") or "").strip()
    raw_h = (request.headers.get("X-Job-Token") or "").strip()
    if raw_q or raw_h:
        ctx = await get_job_context(token=raw_q or None, x_job_token=raw_h or None)
        if (ctx.get("work_order_id") or "").strip() != job_id.strip():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Job link does not match this job")
        return {"contractor_id": ctx["contractor_id"], "work_order_id": ctx["work_order_id"]}
    user = await contractor_route_guard(request)
    cid = (user.get("contractor_id") or "").strip()
    if not cid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractor access required")
    wo = await maintenance_service.get_work_order(job_id.strip())
    if not wo or (wo.get("contractor_id") or "").strip() != cid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {"contractor_id": cid, "work_order_id": job_id.strip()}


def _assignment_profile_for_work_order(wo: Dict[str, Any]) -> str:
    kind = (wo.get("work_order_kind") or "").strip().upper()
    return "compliance" if kind == WORK_ORDER_KIND_COMPLIANCE else "standard"


async def _resolve_portal_job_assignment_profile(contractor_id: str, client_id: str, wo: Dict[str, Any]) -> str:
    """Vetted network contractors use strict profile; portal-supplied rows use relaxed profiles."""
    doc = await contractor_service.get_contractor((contractor_id or "").strip())
    if not doc:
        return _assignment_profile_for_work_order(wo)
    src = (doc.get("source_type") or "").strip().lower()
    if src == contractor_service.SOURCE_CLIENT_SUPPLIED_PERSONAL:
        return "client_supplied_personal"
    if src == contractor_service.SOURCE_LANDLORD_ADDED and str(doc.get("client_id") or "").strip() == str(
        client_id
    ).strip():
        return contractor_service.ASSIGNMENT_PROFILE_CLIENT_PORTAL_LANDLORD
    return _assignment_profile_for_work_order(wo)


@router.get("/requirements/{requirement_id}")
async def get_requirement_by_id(request: Request, requirement_id: str, user: Dict[str, Any] = Depends(_require_client)):
    db = database.get_db()
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id.strip(), "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not req or not await _client_requirement_row_eligible(db, user, req):
        raise HTTPException(status_code=404, detail="Requirement not found")
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
    from services.requirement_truth import enrich_requirements_for_client

    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db, client_id=user["client_id"], requirements=[req]
    )
    if not filtered:
        raise HTTPException(status_code=404, detail="Requirement not found")
    req_for_enrich = filtered[0]
    enriched, presentation = await enrich_requirements_for_client(db, user["client_id"], [req_for_enrich])
    row = enriched[0] if enriched else req
    active = await find_active_compliance_job_for_requirement(
        client_id=user["client_id"],
        property_id=str(row.get("property_id") or ""),
        linked_property_requirement_id=requirement_id.strip(),
    )
    wf = derive_requirement_workflow_fields(row, active_compliance_job=active)
    return {
        "requirement": {**row, **wf},
        "presentation": presentation,
        "active_compliance_job": serialize_compliance_job(active) if active else None,
    }


class CreateComplianceJobBody(BaseModel):
    compliance_purpose: str = Field(default="inspection", description="inspection | renewal | certification | remedial")
    compliance_generated_from: str = Field(default="requirement")
    description_override: Optional[str] = None


@router.post("/requirements/{requirement_id}/jobs")
async def create_requirement_compliance_job(
    request: Request,
    requirement_id: str,
    body: CreateComplianceJobBody,
    user: Dict[str, Any] = Depends(_require_compliance_jobs),
):
    db = database.get_db()
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id.strip(), "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not req or not await _client_requirement_row_eligible(db, user, req):
        raise HTTPException(status_code=404, detail="Requirement not found")
    code = (req.get("requirement_code") or req.get("requirement_type") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Requirement has no requirement code")
    prop_id = str(req.get("property_id") or "").strip()
    if not prop_id:
        raise HTTPException(status_code=400, detail="Requirement has no property_id")
    actor = _actor_id(user)
    try:
        wo = await create_compliance_execution_work_order(
            client_id=user["client_id"],
            property_id=prop_id,
            requirement_code_raw=code,
            compliance_purpose=body.compliance_purpose,
            compliance_generated_from=body.compliance_generated_from,
            actor_portal_user_id=actor,
            description_override=body.description_override,
            linked_property_requirement_id=requirement_id.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_compliance_work_order_for_client(work_order_id=wo["work_order_id"], client_id=user["client_id"])
    return {"work_order": wo, "job": serialize_compliance_job(fresh) if fresh else None}


class MarkNotApplicableBody(BaseModel):
    reason: str = Field(..., min_length=10, description="Mandatory audit reason (free text)")
    reason_code: Optional[str] = Field(None, description="Optional preset: no_gas_supply | exempt | not_applicable | other")
    confirm_close_active_job: bool = Field(
        False,
        description="Required when an active compliance job exists: cancel that job with audit trail.",
    )


@router.post("/requirements/{requirement_id}/mark-not-applicable")
async def mark_requirement_not_applicable_by_id(
    request: Request,
    requirement_id: str,
    body: MarkNotApplicableBody,
    user: Dict[str, Any] = Depends(_require_client),
):
    db = database.get_db()
    rid = requirement_id.strip()
    req = await db.requirements.find_one(
        {"requirement_id": rid, "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not req or not await _client_requirement_row_eligible(db, user, req):
        raise HTTPException(status_code=404, detail="Requirement not found")
    prop_id = str(req.get("property_id") or "").strip()
    from datetime import datetime, timezone

    active = await find_active_compliance_job_for_requirement(
        client_id=user["client_id"],
        property_id=prop_id,
        linked_property_requirement_id=rid,
    )
    if active and not body.confirm_close_active_job:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ACTIVE_COMPLIANCE_JOB_EXISTS",
                "message": "An active compliance job is open for this requirement. Confirm to cancel it when marking not applicable.",
                "work_order_id": active.get("work_order_id"),
            },
        )
    now = datetime.now(timezone.utc).isoformat()
    actor = _actor_id(user)
    if active and body.confirm_close_active_job:
        wid = str(active.get("work_order_id") or "").strip()
        if wid:
            try:
                await maintenance_service.update_work_order(
                    wid,
                    status=maintenance_service.STATUS_CANCELLED,
                    assigned_by=actor,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            await create_audit_log(
                action=AuditAction.REQUIREMENT_ACTION_TRIGGERED,
                actor_id=actor,
                client_id=user["client_id"],
                resource_type="work_order",
                resource_id=wid,
                metadata={
                    "event": "cancelled_due_to_requirement_not_applicable",
                    "requirement_id": rid,
                    "reason_excerpt": body.reason.strip()[:500],
                },
            )
    preset = (body.reason_code or "other").strip().lower()
    await db.requirements.update_one(
        {"requirement_id": rid, "client_id": user["client_id"]},
        {
            "$set": {
                "applicability": "NOT_REQUIRED",
                "not_required_reason": preset if preset in ("no_gas_supply", "exempt", "not_applicable", "other") else "other",
                "not_applicable_audit_reason": body.reason.strip(),
                "status": "NOT_REQUIRED",
                "updated_at": now,
            }
        },
    )
    transition_fanout: Dict[str, Any] = {}
    recalc_correlation_id = f"MARK_NOT_APPLICABLE:{rid}"
    sync_correlation_id = ensure_requirement_transition_correlation_id(
        requirement_id=str(rid),
        property_id=str(prop_id or "") or None,
        client_id=str(user.get("client_id") or ""),
        correlation_id=recalc_correlation_id,
    )
    await sync_requirement_evidence_authority(
        db,
        rid,
        property_id_hint=prop_id or None,
        correlation_id=sync_correlation_id,
        transition_origin="api_compliance_workflow.mark_not_applicable",
        transition_observability_out=transition_fanout,
    )
    await create_audit_log(
        action=AuditAction.REQUIREMENT_ACTION_TRIGGERED,
        actor_id=_actor_id(user),
        client_id=user["client_id"],
        resource_type="requirement",
        resource_id=rid,
        metadata={"event": "mark_not_applicable", "reason_code": preset, "reason": body.reason.strip()[:2000]},
    )
    from services.compliance_recalc_queue import ACTOR_CLIENT, TRIGGER_PROPERTY_UPDATED, enqueue_compliance_recalc

    recalc_result = None
    recalc_exc: Optional[Exception] = None
    try:
        recalc_result = await enqueue_compliance_recalc(
            property_id=prop_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=recalc_correlation_id,
        )
    except Exception as exc:
        recalc_exc = exc
        logger.warning("enqueue_compliance_recalc after mark_not_applicable failed: %s", exc)
    if transition_fanout:
        attach_downstream_trigger_observation(
            transition_fanout,
            downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
            trigger_mode="async_queue",
            propagation_stage="post_authority_sync",
            downstream_correlation_id=getattr(recalc_result, "correlation_id", None) if recalc_result is not None else recalc_correlation_id,
            trigger_origin="api_compliance_workflow.mark_not_applicable",
            enqueue_result=recalc_result,
            enqueue_exc=recalc_exc,
        )
    return {"ok": True, "requirement_id": rid}


@router.post("/requirements/{requirement_id}/reopen")
async def reopen_requirement(request: Request, requirement_id: str, user: Dict[str, Any] = Depends(_require_client)):
    db = database.get_db()
    rid = requirement_id.strip()
    req = await db.requirements.find_one(
        {"requirement_id": rid, "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not req or not await _client_requirement_row_eligible(db, user, req):
        raise HTTPException(status_code=404, detail="Requirement not found")
    prop_id = str(req.get("property_id") or "").strip()
    from datetime import datetime, timezone

    prop_row = (
        await db.properties.find_one(
            {"property_id": prop_id, "client_id": user["client_id"]},
            {"_id": 0, "jurisdiction": 1},
        )
        if prop_id
        else None
    ) or {}
    client_row = await db.clients.find_one(
        {"client_id": user["client_id"]},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}

    now = datetime.now(timezone.utc).isoformat()
    merged = {**req, "applicability": "REQUIRED", "not_required_reason": None, "not_applicable_audit_reason": None}
    new_status = get_computed_status(merged, property_doc=prop_row, client_doc=client_row)
    await db.requirements.update_one(
        {"requirement_id": rid, "client_id": user["client_id"]},
        {
            "$set": {
                "applicability": "REQUIRED",
                "not_required_reason": None,
                "not_applicable_audit_reason": None,
                "status": new_status,
                "updated_at": now,
            }
        },
    )
    transition_fanout: Dict[str, Any] = {}
    recalc_correlation_id = f"REOPEN_REQUIREMENT:{rid}"
    sync_correlation_id = ensure_requirement_transition_correlation_id(
        requirement_id=str(rid),
        property_id=str(prop_id or "") or None,
        client_id=str(user.get("client_id") or ""),
        correlation_id=recalc_correlation_id,
    )
    await sync_requirement_evidence_authority(
        db,
        rid,
        property_id_hint=prop_id or None,
        correlation_id=sync_correlation_id,
        transition_origin="api_compliance_workflow.reopen_requirement",
        transition_observability_out=transition_fanout,
    )
    await create_audit_log(
        action=AuditAction.REQUIREMENT_ACTION_TRIGGERED,
        actor_id=_actor_id(user),
        client_id=user["client_id"],
        resource_type="requirement",
        resource_id=rid,
        metadata={
            "event": "reopen_requirement",
            "property_id": prop_id,
            "correlation_id": recalc_correlation_id,
            "prior_applicability": req.get("applicability"),
        },
    )
    from services.compliance_recalc_queue import ACTOR_CLIENT, TRIGGER_PROPERTY_UPDATED, enqueue_compliance_recalc

    recalc_result = None
    recalc_exc: Optional[Exception] = None
    try:
        recalc_result = await enqueue_compliance_recalc(
            property_id=prop_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=recalc_correlation_id,
        )
    except Exception as exc:
        recalc_exc = exc
        logger.warning("enqueue_compliance_recalc after reopen_requirement failed: %s", exc)
    if transition_fanout:
        attach_downstream_trigger_observation(
            transition_fanout,
            downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
            trigger_mode="async_queue",
            propagation_stage="post_authority_sync",
            downstream_correlation_id=getattr(recalc_result, "correlation_id", None) if recalc_result is not None else recalc_correlation_id,
            trigger_origin="api_compliance_workflow.reopen_requirement",
            enqueue_result=recalc_result,
            enqueue_exc=recalc_exc,
        )
    return {"ok": True, "requirement_id": rid, "status": new_status}


@router.post("/requirements/{requirement_id}/documents")
async def upload_document_for_requirement(
    requirement_id: str,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    work_order_id: Optional[str] = Form(None),
    document_metadata: Optional[str] = Form(
        None,
        description='Optional JSON object for jurisdiction-aware validation, e.g. {"issue_date":"2024-06-01","engineer_id":"GAS123"}',
    ),
    user: Dict[str, Any] = Depends(_require_client),
):
    await _enforce_document_upload_rate_limit(user["client_id"])
    db = database.get_db()
    rid = requirement_id.strip()
    req = await db.requirements.find_one(
        {"requirement_id": rid, "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not req or not await _client_requirement_row_eligible(db, user, req):
        raise HTTPException(status_code=404, detail="Requirement not found")
    prop_id = str(req.get("property_id") or "").strip()
    try:
        return await perform_client_document_upload(
            user=user,
            file=file,
            property_id=prop_id,
            requirement_id=rid,
            work_order_id=work_order_id,
            document_type=document_type,
            notes=notes,
            source="portal_requirement_upload",
            document_metadata=document_metadata,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Requirement-scoped document upload failed: %s", e)
        raise HTTPException(status_code=500, detail="Document upload failed")


@router.get("/jobs/{job_id}")
async def get_job_detail(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    from services.operational_cognition_service import attach_cognition_to_job_payload

    payload = serialize_client_job(wo)
    return await attach_cognition_to_job_payload(payload)


class DecisionLogAppendBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


@router.post("/jobs/{job_id}/decision-log")
async def post_job_decision_log(
    request: Request,
    job_id: str,
    body: DecisionLogAppendBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    """
    Append a lightweight decision note (no threading). Actor is client for portal-authenticated calls.
    """
    db = database.get_db()
    wid = job_id.strip()
    wo = await load_client_work_order(work_order_id=wid, client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    msg = body.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")
    now = datetime.now(timezone.utc).isoformat()
    # Portal route: actor is always client; admin/contractor surfaces may append with other actors later.
    entry = {"message": msg[:2000], "actor": "client", "timestamp": now}
    r = await db.work_orders.update_one(
        {"work_order_id": wid, "client_id": user["client_id"]},
        {"$push": {"decision_log": {"$each": [entry], "$slice": -150}}, "$set": {"updated_at": now}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    fresh = await load_client_work_order(work_order_id=wid, client_id=user["client_id"])
    if not fresh:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_client_job(fresh)


@router.get("/jobs/{job_id}/assignable-contractors")
async def get_job_assignable_contractors(
    request: Request,
    job_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    """Contractors visible to the client who pass assignment gates for this work order (trade, location, execution)."""
    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account.")
    return await contractor_service.list_assignable_contractors_for_work_order(
        client_id=user["client_id"],
        work_order_id=job_id.strip(),
        skip=skip,
        limit=limit,
    )


class WorkflowCreateContractorBody(BaseModel):
    """Client creates a landlord-added contractor; optional work_order_id aligns compliance execution stamps."""

    company_name: str = Field(..., min_length=1, max_length=300)
    trade_types: List[str] = Field(..., min_length=1)
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_name: Optional[str] = None
    region: Optional[str] = None
    areas_served: Optional[List[str]] = None
    credentials: Optional[List[str]] = None
    accreditation_certification: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    insurance_details: Optional[str] = None
    work_order_id: Optional[str] = Field(
        None,
        description="When set, must be a job owned by the client; compliance jobs get compliance execution capability.",
    )
    service_regions: Optional[List[str]] = Field(
        None,
        description="UK portfolio regions (Scotland, England, Wales, Northern Ireland). Omit on compliance jobs to default to the job's jurisdiction.",
    )


@router.post("/contractors")
async def post_workflow_contractor(
    request: Request,
    body: WorkflowCreateContractorBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account.")
    if not (body.phone or "").strip() and not (body.email or "").strip():
        raise HTTPException(status_code=400, detail="phone or email is required")
    wid = (body.work_order_id or "").strip()
    wo_ctx: Optional[Dict[str, Any]] = None
    if wid:
        wo_ctx = await load_client_work_order(work_order_id=wid, client_id=user["client_id"])
        if not wo_ctx:
            raise HTTPException(status_code=404, detail="Job not found for work_order_id context")
    creds = [c.strip() for c in (body.credentials or []) if c and str(c).strip()]
    try:
        doc = await contractor_service.create_contractor_for_client_job_portal(
            client_id=user["client_id"],
            portal_user_role_upper=user.get("role") or "",
            company_name=body.company_name.strip(),
            trade_types=[t.strip() for t in body.trade_types if t and str(t).strip()] or ["general"],
            phone=body.phone.strip() if body.phone else None,
            email=body.email.strip() if body.email else None,
            contact_name=body.contact_name.strip() if body.contact_name else None,
            region=body.region.strip() if body.region else None,
            areas_served=body.areas_served,
            credentials=creds or None,
            insurance_details=body.insurance_details.strip() if body.insurance_details else None,
            accreditation_certification=body.accreditation_certification.strip() if body.accreditation_certification else None,
            notes=body.notes.strip() if body.notes else None,
            work_order=wo_ctx,
            service_regions=body.service_regions,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await create_audit_log(
        action=AuditAction.CONTRACTOR_CREATED,
        client_id=user["client_id"],
        resource_type="contractor",
        resource_id=doc.get("contractor_id"),
        actor_id=_actor_id(user),
        metadata={
            "source_type": doc.get("source_type"),
            "via": "POST /api/contractors",
            "work_order_id": wid or None,
        },
    )
    return doc


class AssignContractorBody(BaseModel):
    contractor_id: str


@router.post("/jobs/{job_id}/assign-contractor")
async def job_assign_contractor(
    request: Request,
    job_id: str,
    body: AssignContractorBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = await _resolve_portal_job_assignment_profile(body.contractor_id, user["client_id"], wo)
    try:
        updated = await maintenance_service.update_work_order(
            job_id.strip(),
            contractor_id=body.contractor_id.strip(),
            assigned_by=_actor_id(user),
            allow_direct_contractor_assignment=True,
            assignment_profile=profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else updated


class CreatePersonalContractorAndAssignBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3)
    phone: Optional[str] = None
    trade_types: List[str] = Field(default_factory=lambda: ["general"])


@router.post(
    "/jobs/{job_id}/create-personal-contractor-and-assign",
    deprecated=True,
    summary="Deprecated — use POST /api/contractors then POST /api/jobs/{job_id}/assign-contractor",
)
async def job_create_personal_contractor_and_assign(
    request: Request,
    job_id: str,
    body: CreatePersonalContractorAndAssignBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    """
    Deprecated. Semantics are delegated to `create_contractor_for_client_job_portal` + the same assignment
    profile resolver as `assign-contractor`, so behaviour matches the canonical two-step flow.
    """
    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network is not enabled for your account.")
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    role_u = (user.get("role") or "").strip().upper()
    pending_admin_review = role_u == "ROLE_CLIENT"
    try:
        cdoc = await contractor_service.create_contractor_for_client_job_portal(
            client_id=user["client_id"],
            portal_user_role_upper=user.get("role") or "",
            company_name=body.name.strip(),
            trade_types=body.trade_types or ["general"],
            phone=body.phone.strip() if body.phone else None,
            email=body.email.strip(),
            work_order=wo,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cid = (cdoc or {}).get("contractor_id")
    if not cid:
        raise HTTPException(status_code=500, detail="Contractor creation failed")
    profile = await _resolve_portal_job_assignment_profile(str(cid), user["client_id"], wo)
    try:
        updated = await maintenance_service.update_work_order(
            job_id.strip(),
            contractor_id=str(cid),
            assigned_by=_actor_id(user),
            allow_direct_contractor_assignment=True,
            assignment_profile=profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    out = {"contractor": cdoc, "job": serialize_client_job(fresh) if fresh else updated}
    if pending_admin_review:
        out["contractor_pending_admin_review"] = True
    return out


class OperationalExceptionBody(BaseModel):
    """NO_ACCESS | RESCHEDULE_REQUIRED | FOLLOW_UP_REQUIRED | empty string to clear."""

    exception: str = Field("", description="Exception code or empty to clear")


@router.post("/jobs/{job_id}/operational-exception")
async def job_set_operational_exception(
    request: Request,
    job_id: str,
    body: OperationalExceptionBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            operational_exception=body.exception,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/resume-after-parts")
async def job_resume_after_parts(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    if (wo.get("status") or "").strip().upper() != maintenance_service.STATUS_AWAITING_PARTS:
        raise HTTPException(status_code=400, detail="Job is not in AWAITING_PARTS status")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            status=maintenance_service.STATUS_IN_PROGRESS,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


class RequestBookingBody(BaseModel):
    scheduled_at: str
    timezone: str = Field(..., description="IANA timezone e.g. Europe/London")
    notes: Optional[str] = Field(None, max_length=4000)


@router.post("/jobs/{job_id}/request-booking")
async def job_request_booking(
    request: Request,
    job_id: str,
    body: RequestBookingBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    if not (wo.get("contractor_id") or "").strip():
        raise HTTPException(status_code=400, detail="Assign a contractor before requesting a booking")
    actor_type, actor_id, role = SCHEDULE_ACTOR_CLIENT, _actor_id(user), user.get("role")
    try:
        await wo_schedule.propose_schedule(
            job_id.strip(),
            actor_type=actor_type,
            actor_id=actor_id,
            actor_role=role,
            scheduled_at_raw=body.scheduled_at,
            timezone_name=body.timezone,
            notes=body.notes,
            client_id=user["client_id"],
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/confirm-booking")
async def job_confirm_booking(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    if not (wo.get("scheduled_at") or "").strip():
        raise HTTPException(status_code=400, detail="No proposed visit window to confirm")
    actor_type, actor_id, role = SCHEDULE_ACTOR_CLIENT, _actor_id(user), user.get("role")
    try:
        await wo_schedule.confirm_schedule(
            job_id.strip(),
            actor_type=actor_type,
            actor_id=actor_id,
            actor_role=role,
            client_id=user["client_id"],
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/reschedule")
async def job_reschedule(
    request: Request,
    job_id: str,
    body: RequestBookingBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    """Propose a new visit time (booking sub-flow). Same behaviour as request-booking."""
    return await job_request_booking(request, job_id, body, user)


class RequestVisitRescheduleBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


@router.post("/jobs/{job_id}/request-visit-reschedule")
async def job_request_visit_reschedule(
    request: Request,
    job_id: str,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
    body: RequestVisitRescheduleBody = Body(default_factory=RequestVisitRescheduleBody),
):
    """Ask the other party to propose a new visit time (preserves schedule history)."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        await wo_schedule.request_reschedule(
            job_id.strip(),
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id=_actor_id(user),
            actor_role=user.get("role"),
            reason=body.reason,
            client_id=user["client_id"],
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/cancel-booking")
async def job_cancel_booking(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    """Cancel the current schedule on the job without cancelling the whole job."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    actor_type, actor_id, role = SCHEDULE_ACTOR_CLIENT, _actor_id(user), user.get("role")
    try:
        await wo_schedule.cancel_schedule(
            job_id.strip(),
            actor_type=actor_type,
            actor_id=actor_id,
            actor_role=role,
            client_id=user["client_id"],
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


class MarkNoAccessBody(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


@router.post("/jobs/{job_id}/mark-no-access")
async def job_mark_no_access(
    request: Request,
    job_id: str,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
    body: MarkNoAccessBody = Body(default_factory=MarkNoAccessBody),
):
    """Record no-access hold (operational exception). Reschedule from the job when resolved."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            operational_exception=maintenance_service.OPERATIONAL_EXCEPTION_NO_ACCESS,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/mark-reschedule-required")
async def job_mark_reschedule_required(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    """Set RESCHEDULE_REQUIRED operational hold (symmetric with mark-no-access). Cleared via operational-exception or clear next_actions."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            operational_exception=maintenance_service.OPERATIONAL_EXCEPTION_RESCHEDULE_REQUIRED,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/start")
async def job_start(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            status=maintenance_service.STATUS_IN_PROGRESS,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/awaiting-parts")
async def job_awaiting_parts(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    """Maintenance only: IN_PROGRESS → AWAITING_PARTS."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_MAINTENANCE:
        raise HTTPException(status_code=400, detail="Awaiting parts applies to maintenance jobs only")
    if (wo.get("status") or "").strip().upper() != maintenance_service.STATUS_IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Job must be in progress to mark awaiting parts")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            status=maintenance_service.STATUS_AWAITING_PARTS,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/complete")
async def job_complete(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            status=maintenance_service.STATUS_COMPLETED,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


class SubmitJobQuoteBody(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GBP", max_length=12)
    notes: Optional[str] = Field(None, max_length=4000)


@router.post("/jobs/{job_id}/submit-quote")
async def job_submit_quote(request: Request, job_id: str, body: SubmitJobQuoteBody):
    """Contractor (portal JWT or secure job link): propose / revise quote after rejection."""
    ctx = await _resolve_contractor_for_job_pricing(request, job_id.strip())
    try:
        await submit_quote_for_work_order(
            ctx["work_order_id"],
            ctx["contractor_id"],
            amount=body.amount,
            currency=body.currency or "GBP",
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    wo = await maintenance_service.get_work_order(ctx["work_order_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    inv = await invoice_service.contractor_best_invoice_for_work_order(ctx["contractor_id"], ctx["work_order_id"])
    apply_contractor_job_enrichment(wo, invoice=inv)
    return wo


class RejectQuoteBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


class RequestQuoteRevisionBody(BaseModel):
    reason_code: str = Field(..., max_length=64)
    message: Optional[str] = Field(None, max_length=2000)
    target_budget: Optional[float] = Field(None, gt=0)
    target_date: Optional[str] = Field(None, max_length=32)


class RejectQuoteFinalBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


@router.post("/jobs/{job_id}/approve-quote")
async def job_approve_quote(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    try:
        await approve_quote_for_work_order(
            job_id.strip(),
            user["client_id"],
            actor_id=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/reject-quote")
async def job_reject_quote(
    request: Request,
    job_id: str,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
    body: RejectQuoteBody = Body(default_factory=RejectQuoteBody),
):
    """Backward-compatible alias: reject-quote requests changes (revision workflow)."""
    try:
        await reject_quote_for_work_order(
            job_id.strip(),
            user["client_id"],
            reason=body.reason,
            actor_id=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/request-quote-revision")
async def job_request_quote_revision(
    request: Request,
    job_id: str,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
    body: RequestQuoteRevisionBody = Body(...),
):
    try:
        await request_quote_revision_for_work_order(
            job_id.strip(),
            user["client_id"],
            reason_code=body.reason_code,
            message=body.message,
            target_budget=body.target_budget,
            target_date=body.target_date,
            actor_id=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/reject-quote-final")
async def job_reject_quote_final(
    request: Request,
    job_id: str,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
    body: RejectQuoteFinalBody = Body(default_factory=RejectQuoteFinalBody),
):
    try:
        await reject_quote_final_for_work_order(
            job_id.strip(),
            user["client_id"],
            reason=body.reason,
            actor_id=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/mark-inspection-complete")
async def job_mark_inspection_complete(request: Request, job_id: str):
    """Maintenance inspection-first jobs: contractor confirms inspection visit is done (then submit quote)."""
    ctx = await _resolve_contractor_for_job_pricing(request, job_id.strip())
    try:
        await mark_inspection_complete_for_work_order(ctx["work_order_id"], ctx["contractor_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    wo = await maintenance_service.get_work_order(ctx["work_order_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    inv = await invoice_service.contractor_best_invoice_for_work_order(ctx["contractor_id"], ctx["work_order_id"])
    apply_contractor_job_enrichment(wo, invoice=inv)
    return wo


class LinkDocumentBody(BaseModel):
    document_id: str


@router.post("/jobs/{job_id}/link-document")
async def job_link_document(
    request: Request,
    job_id: str,
    body: LinkDocumentBody,
    user: Dict[str, Any] = Depends(_require_compliance_jobs),
):
    wo = await load_compliance_work_order_for_client(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    did = body.document_id.strip()
    db = database.get_db()
    doc = await db.documents.find_one(
        {"document_id": did, "client_id": user["client_id"]},
        {"_id": 0, "document_id": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    key = f"document:{did}"
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            evidence_keys_append=[key],
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_compliance_work_order_for_client(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/attach-completion-proof")
async def job_attach_completion_proof(
    request: Request,
    job_id: str,
    body: LinkDocumentBody,
    user: Dict[str, Any] = Depends(_require_maintenance_workflows),
):
    """Maintenance: link a vault document as completion evidence (booking/execution is separate)."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_MAINTENANCE:
        raise HTTPException(
            status_code=400,
            detail="Attach completion proof applies to maintenance jobs; compliance jobs use link-document",
        )
    did = body.document_id.strip()
    db = database.get_db()
    doc = await db.documents.find_one(
        {"document_id": did, "client_id": user["client_id"]},
        {"_id": 0, "document_id": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    key = f"document:{did}"
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            evidence_keys_append=[key],
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/close")
async def job_close_maintenance(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    """Maintenance closeout: from COMPLETED with proof → VERIFIED; from VERIFIED → CLOSED."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_MAINTENANCE:
        raise HTTPException(status_code=400, detail="Use verify to close compliance jobs")
    st = (wo.get("status") or "").strip().upper()
    actor = _actor_id(user)
    try:
        if st == maintenance_service.STATUS_COMPLETED:
            if not maintenance_has_completion_evidence(wo):
                raise HTTPException(
                    status_code=400,
                    detail="Attach completion proof before closing the job",
                )
            await maintenance_service.update_work_order(
                job_id.strip(),
                status=maintenance_service.STATUS_VERIFIED,
                assigned_by=actor,
            )
        elif st == maintenance_service.STATUS_VERIFIED:
            await maintenance_service.update_work_order(
                job_id.strip(),
                status=maintenance_service.STATUS_CLOSED,
                assigned_by=actor,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Mark work complete and attach proof, or close from a verified job",
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/verify")
async def job_verify(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    """Compliance closeout only. Maintenance jobs must use attach-completion-proof + POST .../close (single policy)."""
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    kind = (wo.get("work_order_kind") or "").strip().upper()
    if kind != WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(
            status_code=400,
            detail=(
                "Verify applies to compliance jobs only. For maintenance jobs, attach completion proof "
                "(POST .../attach-completion-proof) then close out with POST .../close (completed+proof→verified, "
                "then verified→closed)."
            ),
        )
    flags = await get_effective_flags(user["client_id"])
    if not flags.get(COMPLIANCE_ENGINE):
        raise HTTPException(status_code=403, detail="Compliance jobs require the compliance engine for your account")
    if not work_order_has_proof_document(wo):
        raise HTTPException(
            status_code=400,
            detail="Link a proof document to this job before verification",
        )
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            status=maintenance_service.STATUS_VERIFIED,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.post("/jobs/{job_id}/cancel")
async def job_cancel(request: Request, job_id: str, user: Dict[str, Any] = Depends(_require_maintenance_workflows)):
    wo = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    if not wo:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        await maintenance_service.update_work_order(
            job_id.strip(),
            status=maintenance_service.STATUS_CANCELLED,
            assigned_by=_actor_id(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await load_client_work_order(work_order_id=job_id.strip(), client_id=user["client_id"])
    return serialize_client_job(fresh) if fresh else {}


@router.get("/today/items")
async def get_today_items(
    request: Request,
    user: Dict[str, Any] = Depends(_require_client),
    property_id: Optional[str] = Query(None, description="Optional scope to one property"),
    include_flat_items: bool = Query(
        False,
        description="Include legacy flat items[] list (slim task refs). Portal uses tasks.* buckets.",
    ),
):
    import asyncio

    prop_filter = property_id.strip() if property_id else None
    from services.rent_attention_projection import (
        list_rent_attention_tasks,
        merge_rent_into_today_payload,
    )

    payload, rent_tasks = await asyncio.gather(
        get_unified_tasks_for_client(
            user["client_id"],
            property_id_filter=prop_filter,
            raw_limit=50,
            portal_user_id=user.get("portal_user_id"),
            surface_profile="today",
        ),
        list_rent_attention_tasks(
            user["client_id"],
            property_id_filter=prop_filter,
        ),
    )
    out = build_today_payload_from_unified(
        payload,
        include_flat_items=include_flat_items,
        compact=not include_flat_items,
    )
    try:
        from services.workflow_stall_priority_service import (
            apply_workflow_stall_escalation_to_today_payload,
            load_stalled_work_orders_for_client,
        )

        stalled = await load_stalled_work_orders_for_client(
            user["client_id"],
            property_id_filter=prop_filter,
        )
        out = apply_workflow_stall_escalation_to_today_payload(
            user["client_id"],
            out,
            stalled_work_orders=stalled,
        )
    except Exception as stall_exc:
        import logging

        logging.getLogger(__name__).warning("Today workflow stall enrichment failed: %s", stall_exc)
    try:
        from services.recovery_priority_service import apply_operational_recovery_to_today_payload

        out = await apply_operational_recovery_to_today_payload(
            user["client_id"],
            out,
            property_id_filter=prop_filter,
        )
    except Exception as recovery_exc:
        import logging

        logging.getLogger(__name__).warning("Today operational recovery enrichment failed: %s", recovery_exc)
    return merge_rent_into_today_payload(out, rent_tasks)


class SnoozeBody(BaseModel):
    days: int = Field(1, ge=1, le=30)


class DismissBody(BaseModel):
    reason: str = Field(..., min_length=3)


@router.post("/today/items/{item_id}/mark-reviewed")
async def today_mark_reviewed(request: Request, item_id: str, user: Dict[str, Any] = Depends(_require_client)):
    try:
        return await apply_task_action(
            user["client_id"],
            item_id.strip(),
            ACTION_REVIEWED,
            portal_user_id=user.get("portal_user_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/today/items/{item_id}/snooze")
async def today_snooze(
    request: Request,
    item_id: str,
    body: SnoozeBody,
    user: Dict[str, Any] = Depends(_require_client),
):
    try:
        return await apply_task_action(
            user["client_id"],
            item_id.strip(),
            ACTION_SNOOZE,
            portal_user_id=user.get("portal_user_id"),
            snooze_days=body.days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/today/items/{item_id}/dismiss")
async def today_dismiss(
    request: Request,
    item_id: str,
    body: DismissBody,
    user: Dict[str, Any] = Depends(_require_client),
):
    try:
        return await apply_task_action(
            user["client_id"],
            item_id.strip(),
            ACTION_DISMISS,
            portal_user_id=user.get("portal_user_id"),
            dismiss_reason=body.reason.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/today/items/{item_id}/restore")
async def today_restore(request: Request, item_id: str, user: Dict[str, Any] = Depends(_require_client)):
    try:
        return await apply_task_action(
            user["client_id"],
            item_id.strip(),
            ACTION_RESTORE,
            portal_user_id=user.get("portal_user_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
