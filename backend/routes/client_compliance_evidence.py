"""
Client API: guided compliance evidence (non-document modes) for visible runtime requirements.

Complement to documents routes — does not replace document upload.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from database import database
from middleware import client_route_guard
from models import AuditAction
from services.compliance_evidence_record_service import (
    ALL_EVIDENCE_MODES,
    DEPOSIT_STRUCTURED_DECLARATION_INVALID,
    TENANCY_AGREEMENT_STRUCTURED_DECLARATION_INVALID,
    validate_lead_testing_structured_declaration_fields,
    validate_legionella_structured_declaration_fields,
    WALES_OCCUPATION_CONTRACT_STRUCTURED_DECLARATION_INVALID,
    apply_verification_decision,
    checklist_schema_for_mode,
    create_compliance_evidence_record,
    effective_evidence_resolution,
    guided_method_ui_rows_for_modes,
    validate_deposit_structured_declaration_fields,
    validate_right_to_rent_structured_declaration_fields,
    validate_wales_occupation_contract_structured_declaration_fields,
    validate_tenancy_agreement_structured_declaration_fields,
)
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_action_orchestration import propagate_requirement_evidence_outcome
from utils.audit import create_audit_log
from utils.request_ip import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/client", tags=["client-compliance-evidence"])


def _is_wales_context_requirement(req_row: Dict[str, Any]) -> bool:
    return str(req_row.get("jurisdiction") or req_row.get("property_jurisdiction") or "").strip().lower() == "wales"


async def _require_user(request: Request) -> Dict[str, Any]:
    return await client_route_guard(request)


class StructuredDeclarationBody(BaseModel):
    declaration_statement: str = Field(..., min_length=1)
    structured_fields: Dict[str, Any] = Field(default_factory=dict)


class ContractorConfirmationBody(BaseModel):
    contractor_name: str
    completion_date: str
    work_summary: str
    contractor_email: Optional[str] = None
    contractor_phone: Optional[str] = None
    company_name: Optional[str] = None
    trade_type: Optional[str] = None
    accreditation_number: Optional[str] = None
    optional_attachment_document_id: Optional[str] = None


class InspectionChecklistBody(BaseModel):
    inspection_date: str
    checklist_answers: Dict[str, Any]
    responsible_person: str
    optional_notes: Optional[str] = None
    optional_attachment_document_id: Optional[str] = None


class CreateEvidenceRequest(BaseModel):
    evidence_mode: str
    structured_declaration: Optional[StructuredDeclarationBody] = None
    contractor_confirmation: Optional[ContractorConfirmationBody] = None
    inspection_checklist: Optional[InspectionChecklistBody] = None
    supporting_attachment_document_ids: Optional[List[str]] = None


class VerifyEvidenceRequest(BaseModel):
    decision: str  # VERIFY | REJECT


def _admin_like(role: str) -> bool:
    r = (role or "").strip().upper()
    return r in {"ROLE_CLIENT_ADMIN", "ROLE_OWNER", "ROLE_PROPERTY_MANAGER"}


def _org_reviewer(role: str) -> bool:
    from services.review_queue_service import is_org_reviewer_role

    return is_org_reviewer_role(role)


@router.get("/compliance-evidence/org-review-queue")
async def get_org_review_queue(
    request: Request,
    property_id: Optional[str] = None,
    limit: int = 100,
    user: Dict[str, Any] = Depends(_require_user),
) -> Dict[str, Any]:
    """
    Org-admin review queue — discovery only. Inclusion from governance truth, not lifecycle alone.
    Creator/reviewer separation: only ROLE_CLIENT_ADMIN may list org review work.
    """
    if not _org_reviewer(str(user.get("role") or "")):
        raise HTTPException(status_code=403, detail="Organisation admin role required for review queue")
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client required")
    from services.review_queue_service import list_org_review_queue

    db = database.get_db()
    return await list_org_review_queue(
        db,
        client_id=str(client_id),
        property_id=property_id,
        limit=min(max(limit, 1), 200),
    )


async def _reject_with_attachment_audit(
    *,
    reason_code: str,
    client_id: str,
    user_id: str,
    property_id: str,
    requirement_id: str,
    evidence_mode: str,
    attachment_id: Optional[str],
    request: Request,
) -> None:
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user_id,
        client_id=client_id,
        resource_type="compliance_evidence_submission",
        resource_id=requirement_id,
        metadata={
            "action_type": "GUIDED_EVIDENCE_ATTACHMENT_VALIDATION_REJECTED",
            "reason_code": reason_code,
            "property_id": property_id,
            "requirement_id": requirement_id,
            "evidence_mode": evidence_mode,
            "attachment_id": attachment_id,
        },
        ip_address=get_client_ip(request),
    )
    raise HTTPException(
        status_code=400,
        detail={
            "code": "SUPPORTING_ATTACHMENT_INVALID",
            "message": "One or more supporting uploads are invalid for this requirement.",
        },
    )


@router.get("/properties/{property_id}/requirements/{requirement_id}/evidence-resolution")
async def get_evidence_resolution(
    property_id: str,
    requirement_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(_require_user),
) -> Dict[str, Any]:
    db = database.get_db()
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client required")
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "client_id": client_id, "property_id": property_id},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
    from services.requirement_truth import enrich_requirements_for_client

    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db, client_id=client_id, requirements=[req]
    )
    if not filtered:
        raise HTTPException(status_code=404, detail="Requirement not found")
    enriched_rows, _presentation = await enrich_requirements_for_client(db, client_id, filtered)
    enriched = enriched_rows[0] if enriched_rows else filtered[0]

    policy = effective_evidence_resolution(enriched)
    modes = list(policy.get("allowed_evidence_modes") or [])
    methods = guided_method_ui_rows_for_modes(modes)
    for row in methods:
        mode = str(row.get("evidence_mode") or "")
        schema = checklist_schema_for_mode(enriched, mode)
        row["checklist_schema"] = schema.get("items") or []
        row["checklist_schema_fallback_used"] = bool(schema.get("fallback_used"))
    guided_label = str(policy.get("guided_primary_cta_label") or "").strip() or "Add compliance evidence"
    component_guidance: List[str] = []
    existing_submission_banner = None
    try:
        from services.cer_actionability_presentation import (
            component_guidance_lines,
            resolve_actionability_primary_cta_label,
            resolve_existing_submission_banner_copy,
            build_reopen_prefill_from_record,
        )

        specific_cta = resolve_actionability_primary_cta_label(enriched, fallback=guided_label)
        if specific_cta:
            guided_label = specific_cta
        component_guidance = component_guidance_lines(enriched)
        existing_submission_banner = resolve_existing_submission_banner_copy(enriched)
    except Exception:
        pass

    modal_title = str(policy.get("modal_title") or "").strip() or guided_label
    if not modal_title:
        modal_title = "Add compliance evidence"
    ced = str(policy.get("client_evidence_disclosure") or "").strip() or None

    from services.operational_cognition_service import build_envelope_for_requirement

    cognition = build_envelope_for_requirement(enriched)
    guidance = cognition.get("requirement_guidance_v1") if isinstance(cognition, dict) else None

    reopen_context = None
    try:
        from services.cer_actionability_presentation import build_reopen_prefill_from_record

        stage = str(enriched.get("truth_presentation_stage") or "").strip()
        ea = enriched.get("evidence_authority") if isinstance(enriched.get("evidence_authority"), dict) else {}
        eid = str(ea.get("primary_evidence_record_id") or "").strip()
        if eid and stage in ("followup_required", "operational_incomplete"):
            rec = await db.compliance_evidence_records.find_one(
                {"evidence_record_id": eid, "client_id": client_id},
                {"_id": 0},
            )
            if rec:
                reopen_context = build_reopen_prefill_from_record(rec)
                reopen_context["truth_presentation_stage"] = stage
    except Exception:
        reopen_context = None

    return {
        "requirement_id": requirement_id,
        "property_id": property_id,
        "modal_title": modal_title,
        "primary_client_cta": guided_label,
        "client_evidence_disclosure": ced,
        "primary_resolution_workflow": policy.get("primary_resolution_workflow"),
        "allowed_evidence_modes": modes,
        "guided_methods": methods,
        "supporting_upload_required": bool(policy.get("supporting_upload_required")),
        "supporting_upload_recommended": bool(policy.get("supporting_upload_recommended")),
        "allowed_upload_types": list(policy.get("allowed_upload_types") or []),
        "policy": policy,
        "operational_cognition": cognition,
        "requirement_guidance_v1": guidance,
        "component_guidance_lines": component_guidance,
        "existing_submission_banner": existing_submission_banner,
        "reopen_context": reopen_context,
        "requirement": {
            "requirement_id": enriched.get("requirement_id"),
            "client_lifecycle_state": enriched.get("client_lifecycle_state"),
            "evidence_authority": enriched.get("evidence_authority"),
            "take_action": enriched.get("take_action"),
            "truth_presentation_stage": enriched.get("truth_presentation_stage"),
            "queue_backed_review": enriched.get("queue_backed_review"),
            "review_owner": enriched.get("review_owner"),
            "evidence_completeness": enriched.get("evidence_completeness"),
        },
    }


@router.post("/properties/{property_id}/requirements/{requirement_id}/compliance-evidence")
async def post_compliance_evidence(
    property_id: str,
    requirement_id: str,
    body: CreateEvidenceRequest,
    request: Request,
    user: Dict[str, Any] = Depends(_require_user),
) -> Dict[str, Any]:
    db = database.get_db()
    client_id = user.get("client_id")
    uid = user.get("portal_user_id") or user.get("user_id")
    if not client_id or not uid:
        raise HTTPException(status_code=403, detail="Client context required")
    mode = str(body.evidence_mode or "").strip().upper()
    if mode not in ALL_EVIDENCE_MODES or mode == "DOCUMENT_UPLOAD":
        raise HTTPException(status_code=400, detail="Unsupported evidence_mode for this endpoint")

    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "client_id": client_id, "property_id": property_id},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    payload: Dict[str, Any]
    if mode == "STRUCTURED_DECLARATION":
        if not body.structured_declaration:
            raise HTTPException(status_code=400, detail="structured_declaration required")
        sd = body.structured_declaration
        payload = {
            "declaration_statement": sd.declaration_statement,
            "structured_fields": sd.structured_fields or {},
        }
        raw_code = str(req.get("requirement_type") or req.get("requirement_code") or "").strip()
        canon_code = normalize_requirement_code(raw_code)
        if canon_code == "right_to_rent":
            r2r_err = validate_right_to_rent_structured_declaration_fields(payload.get("structured_fields") or {})
            if r2r_err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED",
                        "message": r2r_err,
                    },
                )
        elif canon_code == "deposit_pi":
            dep_err = validate_deposit_structured_declaration_fields(payload.get("structured_fields") or {})
            if dep_err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": DEPOSIT_STRUCTURED_DECLARATION_INVALID,
                        "message": dep_err,
                    },
                )
        elif canon_code == "wales_occupation_contract" or (
            canon_code == "occupation_contract" and _is_wales_context_requirement(req)
        ):
            wal_err = validate_wales_occupation_contract_structured_declaration_fields(payload.get("structured_fields") or {})
            if wal_err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": WALES_OCCUPATION_CONTRACT_STRUCTURED_DECLARATION_INVALID,
                        "message": wal_err,
                    },
                )
        elif canon_code == "tenancy_agreement":
            ta_err = validate_tenancy_agreement_structured_declaration_fields(payload.get("structured_fields") or {})
            if ta_err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": TENANCY_AGREEMENT_STRUCTURED_DECLARATION_INVALID,
                        "message": ta_err,
                    },
                )
        elif canon_code == "legionella":
            leg_err = validate_legionella_structured_declaration_fields(payload.get("structured_fields") or {})
            if leg_err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": str(leg_err.get("code") or "LEGIONELLA_DECLARATION_REQUIRED"),
                        "message": str(leg_err.get("message") or "Legionella structured declaration is incomplete."),
                    },
                )
        elif canon_code == "lead_testing":
            lead_err = validate_lead_testing_structured_declaration_fields(payload.get("structured_fields") or {})
            if lead_err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": str(lead_err.get("code") or "LEAD_TESTING_DECLARATION_REQUIRED"),
                        "message": str(lead_err.get("message") or "Lead testing structured declaration is incomplete."),
                    },
                )
    elif mode == "CONTRACTOR_CONFIRMATION":
        if not body.contractor_confirmation:
            raise HTTPException(status_code=400, detail="contractor_confirmation required")
        cc = body.contractor_confirmation
        payload = {
            "contractor_name": cc.contractor_name,
            "completion_date": cc.completion_date,
            "work_summary": cc.work_summary,
            "contractor_email": cc.contractor_email,
            "contractor_phone": cc.contractor_phone,
            "company_name": cc.company_name,
            "trade_type": cc.trade_type,
            "accreditation_number": cc.accreditation_number,
            "optional_attachment_document_id": cc.optional_attachment_document_id,
        }
    elif mode == "INSPECTION_CHECKLIST":
        if not body.inspection_checklist:
            raise HTTPException(status_code=400, detail="inspection_checklist required")
        ic = body.inspection_checklist
        payload = {
            "inspection_date": ic.inspection_date,
            "checklist_answers": ic.checklist_answers or {},
            "responsible_person": ic.responsible_person,
            "optional_notes": ic.optional_notes,
            "optional_attachment_document_id": ic.optional_attachment_document_id,
        }
    else:
        raise HTTPException(status_code=400, detail="Unsupported mode")

    linked: List[str] = []
    att = payload.get("optional_attachment_document_id")
    if att:
        linked.append(str(att))
    for x in body.supporting_attachment_document_ids or []:
        tok = str(x or "").strip()
        if tok:
            linked.append(tok)
    linked = list(dict.fromkeys(linked))

    policy = effective_evidence_resolution(req)
    if policy.get("supporting_upload_required") and not linked:
        await _reject_with_attachment_audit(
            reason_code="supporting_upload_required",
            client_id=str(client_id),
            user_id=str(uid),
            property_id=property_id,
            requirement_id=requirement_id,
            evidence_mode=mode,
            attachment_id=None,
            request=request,
        )
    allowed_upload_types = set(
        str(x).strip().lower() for x in (policy.get("allowed_upload_types") or []) if str(x).strip()
    )
    if linked:
        docs = await db.documents.find(
            {"document_id": {"$in": linked}, "client_id": client_id},
            {"_id": 0, "document_id": 1, "content_type": 1},
        ).to_list(200)
        by_id = {str(d.get("document_id")): d for d in docs if d.get("document_id")}
        for lid in linked:
            doc = by_id.get(str(lid))
            if not doc:
                await _reject_with_attachment_audit(
                    reason_code="supporting_attachment_not_found",
                    client_id=str(client_id),
                    user_id=str(uid),
                    property_id=property_id,
                    requirement_id=requirement_id,
                    evidence_mode=mode,
                    attachment_id=str(lid),
                    request=request,
                )
            if allowed_upload_types:
                ctype = str(doc.get("content_type") or "").strip().lower()
                if ctype and ctype not in allowed_upload_types:
                    await _reject_with_attachment_audit(
                        reason_code="unsupported_supporting_upload_type",
                        client_id=str(client_id),
                        user_id=str(uid),
                        property_id=property_id,
                        requirement_id=requirement_id,
                        evidence_mode=mode,
                        attachment_id=str(lid),
                        request=request,
                    )

    try:
        rec = await create_compliance_evidence_record(
            db,
            requirement=req,
            evidence_mode=mode,
            created_by_user_id=str(uid),
            evidence_payload=payload,
            linked_document_ids=linked,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "requirement_not_eligible_for_runtime_evidence":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This requirement is not eligible for evidence submission (hidden, not visible on your portal, or out of scope).",
            ) from e
        raise HTTPException(status_code=400, detail=msg) from e

    eid = str((rec or {}).get("evidence_record_id") or "").strip() or "new"
    correlation_base = f"GUIDED_EVIDENCE_AUTHORITY:{property_id}:{requirement_id}:{eid}"
    outcome = await propagate_requirement_evidence_outcome(
        db,
        requirement_id=requirement_id,
        property_id=property_id,
        client_id=str(client_id),
        actor_user_id=str(uid),
        correlation_base=correlation_base,
        transition_origin="client_compliance_evidence.post_compliance_evidence",
    )
    return {**outcome, "evidence_record": rec}


@router.post("/properties/{property_id}/requirements/{requirement_id}/compliance-evidence/{evidence_record_id}/verification")
async def post_evidence_verification(
    property_id: str,
    requirement_id: str,
    evidence_record_id: str,
    body: VerifyEvidenceRequest,
    request: Request,
    user: Dict[str, Any] = Depends(_require_user),
) -> Dict[str, Any]:
    if not _admin_like(str(user.get("role") or "")):
        raise HTTPException(status_code=403, detail="Admin-like role required to verify evidence")
    db = database.get_db()
    client_id = user.get("client_id")
    uid = user.get("portal_user_id") or user.get("user_id")
    if not client_id or not uid:
        raise HTTPException(status_code=403, detail="Client context required")
    rec = await db.compliance_evidence_records.find_one(
        {
            "evidence_record_id": evidence_record_id,
            "client_id": client_id,
            "property_id": property_id,
            "requirement_id": requirement_id,
        },
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    try:
        updated = await apply_verification_decision(
            db,
            evidence_record_id=evidence_record_id,
            client_id=str(client_id),
            decision=body.decision,
            actor_user_id=str(uid),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not updated:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    correlation_base = f"GUIDED_EVIDENCE_VERIFY:{property_id}:{requirement_id}:{evidence_record_id}"
    outcome = await propagate_requirement_evidence_outcome(
        db,
        requirement_id=requirement_id,
        property_id=property_id,
        client_id=str(client_id),
        actor_user_id=str(uid),
        correlation_base=correlation_base,
        transition_origin="client_compliance_evidence.post_evidence_verification",
    )
    return {**outcome, "evidence_record": updated}


@router.get("/properties/{property_id}/requirements/{requirement_id}/compliance-evidence")
async def list_compliance_evidence(
    property_id: str,
    requirement_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(_require_user),
) -> Dict[str, Any]:
    db = database.get_db()
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client required")
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "client_id": client_id, "property_id": property_id},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    cur = (
        db.compliance_evidence_records.find(
            {"requirement_id": requirement_id, "client_id": client_id, "archived": {"$ne": True}},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .limit(200)
    )
    items = await cur.to_list(200)
    return {"requirement_id": requirement_id, "evidence_records": items}
