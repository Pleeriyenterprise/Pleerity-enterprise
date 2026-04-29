"""
Client API: guided compliance evidence (non-document modes) for visible runtime requirements.

Complement to documents routes — does not replace document upload.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from database import database
from middleware import client_route_guard
from models import AuditAction
from services.compliance_evidence_record_service import (
    ALL_EVIDENCE_MODES,
    apply_verification_decision,
    checklist_schema_for_mode,
    create_compliance_evidence_record,
    effective_evidence_resolution,
    guided_method_ui_rows_for_modes,
)
from services.requirement_evidence_authority import sync_requirement_evidence_authority
from utils.audit import create_audit_log
from utils.request_ip import get_client_ip

router = APIRouter(prefix="/api/client", tags=["client-compliance-evidence"])


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
    policy = effective_evidence_resolution(req)
    modes = list(policy.get("allowed_evidence_modes") or [])
    methods = guided_method_ui_rows_for_modes(modes)
    for row in methods:
        mode = str(row.get("evidence_mode") or "")
        schema = checklist_schema_for_mode(req, mode)
        row["checklist_schema"] = schema.get("items") or []
        row["checklist_schema_fallback_used"] = bool(schema.get("fallback_used"))
    guided_label = str(policy.get("guided_primary_cta_label") or "").strip() or "Add compliance evidence"
    return {
        "requirement_id": requirement_id,
        "property_id": property_id,
        "modal_title": "Add compliance evidence",
        "primary_client_cta": guided_label,
        "primary_resolution_workflow": policy.get("primary_resolution_workflow"),
        "allowed_evidence_modes": modes,
        "guided_methods": methods,
        "supporting_upload_required": bool(policy.get("supporting_upload_required")),
        "supporting_upload_recommended": bool(policy.get("supporting_upload_recommended")),
        "allowed_upload_types": list(policy.get("allowed_upload_types") or []),
        "policy": policy,
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

    await sync_requirement_evidence_authority(db, requirement_id, property_id_hint=property_id)
    return {"ok": True, "evidence_record": rec}


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
    await sync_requirement_evidence_authority(db, requirement_id, property_id_hint=property_id)
    return {"ok": True, "evidence_record": updated}


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
