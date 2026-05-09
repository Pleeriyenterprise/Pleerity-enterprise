"""Admin evidence review actions (Evidence Review V2)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from database import database
from middleware import admin_route_guard
from models import DocumentStatus, RequirementStatus
from models.evidence_review import AssuranceTier, EvidenceReviewState
from utils.api_errors import structured_error

from services.evidence_review_actions import correlation_id_new, document_is_calendrically_expired, run_validation_for_document, transition_review_fields
from services.evidence_review_audit import append_evidence_review_event
from services.evidence_review_config import is_feature_evidence_review_v2
from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
from services.evidence_review_policy import promotions_allowed_for_accept_unverified
from services.external_verification_helpers import build_verification_helpers
from services.authority_mutation_fanout import authority_sync_with_transition_observability, enqueue_compliance_recalc_with_fanout
from services.provisioning import provisioning_service
from services.compliance_recalc_queue import TRIGGER_DOC_STATUS_CHANGED, ACTOR_ADMIN
from services.requirement_transition_observability import merge_document_path_lineage_flags, merge_review_admin_lineage_flags

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["evidence-review"])

ALLOWED_EXTERNAL_VERIFICATION_METHODS = {
    "EPC_REGISTER_CHECK",
    "GAS_SAFE_LOOKUP",
    "NICEIC_LOOKUP",
    "NAPIT_LOOKUP",
    "COMPANIES_HOUSE_CHECK",
    "MANUAL_CONFIRMATION",
}


def _v2_guard() -> None:
    if not is_feature_evidence_review_v2():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "EVIDENCE_REVIEW_V2_DISABLED",
                "Set environment variable FEATURE_EVIDENCE_REVIEW_V2=1 to enable this API surface.",
            ),
        )


class ReviewNotesBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    notes: Optional[str] = None
    validation_override_reason: Optional[str] = None
    correlation_id: Optional[str] = None


class NotesRequiredBody(ReviewNotesBody):
    notes: str = Field(..., min_length=1)


class RequestInfoBody(NotesRequiredBody):
    pass


class RejectBody(NotesRequiredBody):
    pass


class AcceptUnverifiedBody(ReviewNotesBody):
    """Parity with POST /api/documents/verify (evidence mismatch + validation override)."""

    evidence_mismatch_override: bool = False
    evidence_mismatch_override_reason: Optional[str] = None


class ExternalVerifyBody(NotesRequiredBody):
    external_verification_reference: str = Field(..., min_length=1)
    external_verification_method: str = Field(..., min_length=1)


class SupersedeBody(ReviewNotesBody):
    """Optional notes when marking a document superseded."""

    superseded_by_document_id: Optional[str] = None


class ApplyAIOverrideBody(NotesRequiredBody):
    accepted_fields: Optional[Dict[str, Any]] = None
    rejected_fields: Optional[List[str]] = None


class AIFieldActionBody(ReviewNotesBody):
    field_name: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)  # ACCEPT | REJECT | OVERRIDE
    override_value: Optional[Any] = None
    override_reason: Optional[str] = None


class RecordExternalVerificationBody(ReviewNotesBody):
    verification_method: str = Field(..., min_length=1)
    verification_reference: Optional[str] = None
    verification_notes: Optional[str] = None
    verified_at: Optional[str] = None


async def _sync_prop_recalc(
    db,
    *,
    property_id: Optional[str],
    client_id: Optional[str],
    actor_id: Optional[str],
    doc_id: str,
    reason: str,
    transition_fanout: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    trigger_origin: str = "routes.evidence_review._sync_prop_recalc",
    propagation_stage: str = "post_review_authority_sync",
) -> None:
    if not property_id or not client_id:
        return
    try:
        await provisioning_service._update_property_compliance(property_id)
        corr = correlation_id or f"DOC_REVIEW:{doc_id}"
        await enqueue_compliance_recalc_with_fanout(
            transition_fanout,
            property_id=property_id,
            client_id=client_id,
            trigger_reason=reason,
            actor_type=ACTOR_ADMIN,
            actor_id=actor_id,
            correlation_id=corr,
            trigger_origin=trigger_origin,
            propagation_stage=propagation_stage,
            fanout_op="evidence_review_transition_fanout",
        )
    except Exception as ex:
        logger.debug("Property compliance recalc after review: %s", ex)

def _ensure_ai_tracking(ai: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(ai or {})
    extracted = out.get("extracted_fields") if isinstance(out.get("extracted_fields"), dict) else {}
    out["extracted_fields"] = dict(extracted)
    original = out.get("original_extracted_fields")
    if not isinstance(original, dict):
        out["original_extracted_fields"] = dict(extracted)
    out["field_reviews"] = out.get("field_reviews") if isinstance(out.get("field_reviews"), dict) else {}
    out["reviewer_overrides"] = out.get("reviewer_overrides") if isinstance(out.get("reviewer_overrides"), list) else []
    out["external_verification_records"] = out.get("external_verification_records") if isinstance(out.get("external_verification_records"), list) else []
    return out


@router.get("/{document_id}/review/verification-helpers")
async def get_external_verification_helpers(request: Request, document_id: str):
    _v2_guard()
    await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    requirement = None
    rid = doc.get("requirement_id")
    if rid:
        requirement = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})
    payload = build_verification_helpers(requirement, doc)
    return {"document_id": document_id, **payload}


@router.get("/{document_id}/review/ai-assistance")
async def get_ai_assistance(request: Request, document_id: str):
    _v2_guard()
    await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    ai = _ensure_ai_tracking(doc.get("ai_assistance") if isinstance(doc.get("ai_assistance"), dict) else {})
    return {
        "document_id": document_id,
        "ai_assistance": {
            "extracted_fields": ai.get("extracted_fields") or {},
            "original_extracted_fields": ai.get("original_extracted_fields") or {},
            "extraction_confidence": ai.get("extraction_confidence"),
            "extraction_source": ai.get("extraction_source"),
            "extraction_timestamp": ai.get("extraction_timestamp"),
            "ai_flags": ai.get("ai_flags") or [],
            "extraction_warnings": ai.get("extraction_warnings") or [],
            "anomaly_flags": ai.get("anomaly_flags") or [],
            "anomaly_risk_score": ai.get("anomaly_risk_score"),
            "reviewer_overrides": ai.get("reviewer_overrides") or [],
            "field_reviews": ai.get("field_reviews") or {},
            "external_verification_records": ai.get("external_verification_records") or [],
        },
    }


@router.post("/{document_id}/review/ai-extraction/apply")
async def apply_ai_extraction_override(request: Request, document_id: str, body: ApplyAIOverrideBody):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    corr = body.correlation_id or correlation_id_new()
    now_iso = datetime.now(timezone.utc).isoformat()
    reviewer = user.get("portal_user_id")
    accepted_fields = body.accepted_fields or {}
    rejected_fields = body.rejected_fields or []
    override_entry = {
        "applied_at": now_iso,
        "applied_by": reviewer,
        "notes": body.notes,
        "accepted_fields": accepted_fields,
        "rejected_fields": rejected_fields,
    }

    ai = _ensure_ai_tracking(doc.get("ai_assistance") if isinstance(doc.get("ai_assistance"), dict) else {})
    extracted_fields = ai.get("extracted_fields") if isinstance(ai.get("extracted_fields"), dict) else {}
    merged_fields = dict(extracted_fields)
    for key in rejected_fields:
        if key in merged_fields:
            merged_fields.pop(key, None)
    for key, value in accepted_fields.items():
        merged_fields[key] = value

    await db.documents.update_one(
        {"document_id": document_id},
        {
            "$set": {
                "ai_assistance.extracted_fields": merged_fields,
                "ai_assistance.original_extracted_fields": ai.get("original_extracted_fields") or {},
                "ai_assistance.last_override_at": now_iso,
                "ai_assistance.last_override_by": reviewer,
            },
            "$push": {"ai_assistance.reviewer_overrides": override_entry},
        },
    )
    await append_evidence_review_event(
        db,
        document_id=document_id,
        requirement_id=doc.get("requirement_id"),
        property_id=doc.get("property_id"),
        client_id=doc.get("client_id"),
        reviewer_id=reviewer,
        from_state=effective_evidence_review_state(doc),
        to_state=effective_evidence_review_state(doc),
        from_assurance_tier=effective_assurance_tier(doc),
        to_assurance_tier=effective_assurance_tier(doc),
        notes=body.notes,
        validation_snapshot={"override_entry": override_entry},
        decision_reason="AI_EXTRACTION_OVERRIDE_APPLIED",
        correlation_id=corr,
    )
    return {"message": "AI extraction overrides applied", "correlation_id": corr}


@router.post("/{document_id}/review/ai-extraction/field-action")
async def apply_ai_field_action(request: Request, document_id: str, body: AIFieldActionBody):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    corr = body.correlation_id or correlation_id_new()
    now_iso = datetime.now(timezone.utc).isoformat()
    reviewer = user.get("portal_user_id")
    action = str(body.action or "").strip().upper()
    field_name = str(body.field_name or "").strip()
    if action not in {"ACCEPT", "REJECT", "OVERRIDE"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error("INVALID_FIELD_REVIEW_ACTION", "Action must be ACCEPT, REJECT, or OVERRIDE."),
        )

    ai = _ensure_ai_tracking(doc.get("ai_assistance") if isinstance(doc.get("ai_assistance"), dict) else {})
    extracted_fields = ai.get("extracted_fields") if isinstance(ai.get("extracted_fields"), dict) else {}
    original_fields = ai.get("original_extracted_fields") if isinstance(ai.get("original_extracted_fields"), dict) else {}
    field_reviews = ai.get("field_reviews") if isinstance(ai.get("field_reviews"), dict) else {}
    current_value = extracted_fields.get(field_name)
    original_value = original_fields.get(field_name)

    field_action: Dict[str, Any] = {
        "field_name": field_name,
        "action": action,
        "at": now_iso,
        "by": reviewer,
        "notes": body.notes,
        "original_value": original_value,
        "previous_value": current_value,
    }
    if action == "OVERRIDE":
        reason = str(body.override_reason or "").strip()
        if not reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=structured_error(
                    "OVERRIDE_REASON_REQUIRED",
                    "override_reason is required when action=OVERRIDE.",
                ),
            )
        extracted_fields[field_name] = body.override_value
        field_action["override_value"] = body.override_value
        field_action["override_reason"] = reason
        field_reviews[field_name] = {
            "status": "OVERRIDDEN",
            "reviewed_at": now_iso,
            "reviewed_by": reviewer,
            "reason": reason,
            "value": body.override_value,
        }
    elif action == "REJECT":
        extracted_fields.pop(field_name, None)
        field_reviews[field_name] = {
            "status": "REJECTED",
            "reviewed_at": now_iso,
            "reviewed_by": reviewer,
            "reason": body.notes,
            "value": None,
        }
    else:
        # ACCEPT: keep current extracted value, mark explicit reviewer acceptance.
        field_reviews[field_name] = {
            "status": "ACCEPTED",
            "reviewed_at": now_iso,
            "reviewed_by": reviewer,
            "reason": body.notes,
            "value": current_value,
        }

    await db.documents.update_one(
        {"document_id": document_id},
        {
            "$set": {
                "ai_assistance.extracted_fields": extracted_fields,
                "ai_assistance.original_extracted_fields": original_fields,
                "ai_assistance.field_reviews": field_reviews,
                "ai_assistance.last_override_at": now_iso,
                "ai_assistance.last_override_by": reviewer,
            },
            "$push": {"ai_assistance.reviewer_overrides": field_action},
        },
    )

    await append_evidence_review_event(
        db,
        document_id=document_id,
        requirement_id=doc.get("requirement_id"),
        property_id=doc.get("property_id"),
        client_id=doc.get("client_id"),
        reviewer_id=reviewer,
        from_state=effective_evidence_review_state(doc),
        to_state=effective_evidence_review_state(doc),
        from_assurance_tier=effective_assurance_tier(doc),
        to_assurance_tier=effective_assurance_tier(doc),
        notes=body.notes,
        validation_snapshot={"field_action": field_action},
        decision_reason=f"AI_FIELD_{action}",
        correlation_id=corr,
    )
    return {"message": "Field review action applied", "correlation_id": corr, "field_action": field_action}


@router.post("/{document_id}/review/record-external-verification")
async def record_external_verification(request: Request, document_id: str, body: RecordExternalVerificationBody):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    corr = body.correlation_id or correlation_id_new()
    reviewer = user.get("portal_user_id")
    now_iso = datetime.now(timezone.utc).isoformat()
    verified_at = str(body.verified_at or now_iso)
    method = str(body.verification_method or "").strip().upper()
    reference = str(body.verification_reference or "").strip() or None
    notes = str(body.verification_notes or body.notes or "").strip() or None
    if not method:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=structured_error("VERIFICATION_METHOD_REQUIRED", "verification_method is required."),
        )
    if method not in ALLOWED_EXTERNAL_VERIFICATION_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=structured_error(
                "VERIFICATION_METHOD_UNSUPPORTED",
                "verification_method must be one of the allowed taxonomy values.",
                allowed_methods=sorted(ALLOWED_EXTERNAL_VERIFICATION_METHODS),
            ),
        )

    ai = _ensure_ai_tracking(doc.get("ai_assistance") if isinstance(doc.get("ai_assistance"), dict) else {})
    record = {
        "verification_method": method,
        "verification_reference": reference,
        "verification_notes": notes,
        "verified_at": verified_at,
        "recorded_at": now_iso,
        "recorded_by": reviewer,
    }
    await db.documents.update_one(
        {"document_id": document_id},
        {
            "$set": {
                "status": DocumentStatus.VERIFIED.value,
                "evidence_review_state": EvidenceReviewState.VERIFIED.value,
                "assurance_tier": AssuranceTier.EXTERNALLY_VERIFIED.value,
                "external_verification_method": method,
                "external_verification_reference": reference,
                "review_required": False,
                "review_notes_required": False,
                "review_decision_at": now_iso,
                "review_decision_by": reviewer,
                "updated_at": now_iso,
            },
            "$push": {"ai_assistance.external_verification_records": record},
        },
    )
    await append_evidence_review_event(
        db,
        document_id=document_id,
        requirement_id=doc.get("requirement_id"),
        property_id=doc.get("property_id"),
        client_id=doc.get("client_id"),
        reviewer_id=reviewer,
        from_state=effective_evidence_review_state(doc),
        to_state=EvidenceReviewState.VERIFIED.value,
        from_assurance_tier=effective_assurance_tier(doc),
        to_assurance_tier=AssuranceTier.EXTERNALLY_VERIFIED.value,
        notes=notes,
        validation_snapshot={"external_verification_record": record},
        decision_reason="EXTERNAL_VERIFICATION_RECORDED_PHASE3",
        correlation_id=corr,
    )
    return {"message": "External verification recorded", "correlation_id": corr, "verification": record}


@router.post("/{document_id}/review/start")
async def start_evidence_review(request: Request, document_id: str, body: ReviewNotesBody = Body(default_factory=ReviewNotesBody)):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    corr = body.correlation_id or correlation_id_new()
    now = datetime.now(timezone.utc).isoformat()
    await transition_review_fields(
        db,
        document_id=document_id,
        patch={
            "evidence_review_state": EvidenceReviewState.UNDER_REVIEW.value,
            "review_required": True,
            "updated_at": now,
        },
        reviewer_id=user.get("portal_user_id"),
        correlation_id=corr,
        prev_doc=doc,
        validation_snapshot=None,
        notes=body.notes,
        decision_reason="START_REVIEW",
    )
    if doc.get("requirement_id"):
        start_fanout: Dict[str, Any] = {}
        prev_rs = str(effective_evidence_review_state(doc) or "")
        await authority_sync_with_transition_observability(
            db,
            str(doc["requirement_id"]),
            property_id=str(doc.get("property_id") or "") or None,
            client_id=str(doc.get("client_id") or ""),
            correlation_base=str(corr),
            transition_origin="routes.evidence_review.start_evidence_review",
            transition_fanout=start_fanout,
        )
        merge_document_path_lineage_flags(start_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(
            start_fanout,
            review_id=str(corr),
            reviewer_retrigger_possible=True,
            review_chain_reentry_detected=(prev_rs == EvidenceReviewState.UNDER_REVIEW.value),
        )
    return {"message": "Review started", "correlation_id": corr}


@router.post("/{document_id}/review/request-information")
async def request_information(request: Request, document_id: str, body: RequestInfoBody):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    corr = body.correlation_id or correlation_id_new()
    now = datetime.now(timezone.utc).isoformat()
    await transition_review_fields(
        db,
        document_id=document_id,
        patch={
            "evidence_review_state": EvidenceReviewState.NEEDS_INFORMATION.value,
            "review_required": True,
            "review_notes_required": True,
            "status": DocumentStatus.UPLOADED.value,
            "updated_at": now,
        },
        reviewer_id=user.get("portal_user_id"),
        correlation_id=corr,
        prev_doc=doc,
        validation_snapshot=None,
        notes=body.notes,
        decision_reason="REQUEST_INFORMATION",
    )
    if doc.get("requirement_id"):
        prev_rs = str(effective_evidence_review_state(doc) or "")
        ri_fanout: Dict[str, Any] = {}
        await authority_sync_with_transition_observability(
            db,
            str(doc["requirement_id"]),
            property_id=str(doc.get("property_id") or "") or None,
            client_id=str(doc.get("client_id") or ""),
            correlation_base=str(corr),
            transition_origin="routes.evidence_review.request_information",
            transition_fanout=ri_fanout,
        )
        merge_document_path_lineage_flags(ri_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(
            ri_fanout,
            review_id=str(corr),
            review_chain_reentry_detected=(prev_rs == EvidenceReviewState.NEEDS_INFORMATION.value),
            reviewer_retrigger_possible=True,
        )
    return {"message": "Information requested", "correlation_id": corr}


@router.post("/{document_id}/review/accept-unverified")
async def accept_unverified(request: Request, document_id: str, body: AcceptUnverifiedBody = Body(default_factory=AcceptUnverifiedBody)):
    """Same server contract as POST /api/documents/verify (including evidence match override + V2 validation)."""
    _v2_guard()
    from routes.documents import VerifyDocumentBody, verify_document

    return await verify_document(
        request,
        document_id,
        VerifyDocumentBody(
            evidence_mismatch_override=body.evidence_mismatch_override,
            evidence_mismatch_override_reason=body.evidence_mismatch_override_reason,
            validation_override_reason=body.validation_override_reason,
        ),
    )


@router.post("/{document_id}/review/verify-external")
async def verify_external(request: Request, document_id: str, body: ExternalVerifyBody):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document_is_calendrically_expired(document):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error("EVIDENCE_EXPIRED", "Expired evidence cannot be externally verified."),
        )

    snapshot = await run_validation_for_document(db, document)
    vs = str(snapshot.get("validation_status") or "").upper()
    override = str(body.validation_override_reason or "").strip()
    if vs == "FAIL" and not override:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=structured_error(
                "EVIDENCE_VALIDATION_FAILED",
                "Provide validation_override_reason to override validation failures when recording external verification.",
                validation_result=snapshot,
            ),
        )

    promote = promotions_allowed_for_accept_unverified(
        validation_snapshot=snapshot,
        validation_override_reason=override,
    )

    corr = body.correlation_id or correlation_id_new()
    now_iso = datetime.now(timezone.utc).isoformat()
    report_id = str(uuid.uuid4())

    patch = {
        "status": DocumentStatus.VERIFIED.value,
        "evidence_review_state": EvidenceReviewState.VERIFIED.value,
        "assurance_tier": AssuranceTier.EXTERNALLY_VERIFIED.value,
        "external_verification_reference": body.external_verification_reference.strip(),
        "external_verification_method": body.external_verification_method.strip(),
        "review_required": False,
        "review_notes_required": False,
        "validation_report_id": report_id,
        "latest_validation_snapshot": snapshot,
        "updated_at": now_iso,
        "review_decision_at": now_iso,
        "review_decision_by": user.get("portal_user_id"),
    }

    decision_reason = "EXTERNAL_VERIFICATION_RECORDED"
    if vs == "FAIL" and override:
        decision_reason = "EXTERNAL_VERIFICATION_WITH_VALIDATION_OVERRIDE"

    await transition_review_fields(
        db,
        document_id=document_id,
        patch=patch,
        reviewer_id=user.get("portal_user_id"),
        correlation_id=corr,
        prev_doc=document,
        validation_snapshot=snapshot,
        notes=body.notes,
        decision_reason=decision_reason,
    )

    if document.get("requirement_id") and promote:
        await db.requirements.update_one(
            {"requirement_id": document["requirement_id"]},
            {
                "$set": {
                    "status": RequirementStatus.COMPLIANT.value,
                    "date_source": "VERIFIED_DOCUMENT",
                    "evidence_state": "VERIFIED",
                    "confidence_state": "VERIFIED",
                    "compliance_state": "VALID",
                }
            },
        )

    ve_fanout: Dict[str, Any] = {}
    if document.get("requirement_id"):
        await authority_sync_with_transition_observability(
            db,
            str(document["requirement_id"]),
            property_id=str(document.get("property_id") or "") or None,
            client_id=str(document.get("client_id") or ""),
            correlation_base=str(corr),
            transition_origin="routes.evidence_review.verify_external",
            transition_fanout=ve_fanout,
        )
        merge_document_path_lineage_flags(ve_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(
            ve_fanout,
            review_id=str(corr),
            admin_override_possible=bool(vs == "FAIL" and override),
            reviewer_retrigger_possible=True,
        )

    await _sync_prop_recalc(
        db,
        property_id=document.get("property_id"),
        client_id=document.get("client_id"),
        actor_id=user.get("portal_user_id"),
        doc_id=document_id,
        reason=TRIGGER_DOC_STATUS_CHANGED,
        transition_fanout=ve_fanout if ve_fanout.get("transition_id") else None,
        correlation_id=str(corr),
        trigger_origin="routes.evidence_review.verify_external",
        propagation_stage="post_verify_external",
    )

    return {"message": "External verification recorded", "validation": snapshot, "correlation_id": corr}


@router.post("/{document_id}/review/reject")
async def reject_evidence_review(request: Request, document_id: str, body: RejectBody):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    corr = body.correlation_id or correlation_id_new()
    now = datetime.now(timezone.utc).isoformat()
    await transition_review_fields(
        db,
        document_id=document_id,
        patch={
            "status": DocumentStatus.REJECTED.value,
            "evidence_review_state": EvidenceReviewState.REJECTED.value,
            "assurance_tier": AssuranceTier.REJECTED.value,
            "review_required": False,
            "updated_at": now,
        },
        reviewer_id=user.get("portal_user_id"),
        correlation_id=corr,
        prev_doc=doc,
        validation_snapshot=None,
        notes=body.notes,
        decision_reason="REJECT",
    )
    reject_fanout: Dict[str, Any] = {}
    if doc.get("requirement_id"):
        await authority_sync_with_transition_observability(
            db,
            str(doc["requirement_id"]),
            property_id=str(doc.get("property_id") or "") or None,
            client_id=str(doc.get("client_id") or ""),
            correlation_base=str(corr),
            transition_origin="routes.evidence_review.reject_evidence_review",
            transition_fanout=reject_fanout,
        )
        merge_document_path_lineage_flags(reject_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(reject_fanout, review_id=str(corr), review_reversal_possible=True)
    await _sync_prop_recalc(
        db,
        property_id=doc.get("property_id"),
        client_id=doc.get("client_id"),
        actor_id=user.get("portal_user_id"),
        doc_id=document_id,
        reason=TRIGGER_DOC_STATUS_CHANGED,
        transition_fanout=reject_fanout if reject_fanout.get("transition_id") else None,
        correlation_id=str(corr),
        trigger_origin="routes.evidence_review.reject_evidence_review",
        propagation_stage="post_review_reject",
    )
    return {"message": "Evidence rejected", "correlation_id": corr}


@router.post("/{document_id}/review/mark-expired")
async def mark_expired_review(request: Request, document_id: str, body: ReviewNotesBody = Body(default_factory=ReviewNotesBody)):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    corr = body.correlation_id or correlation_id_new()
    now = datetime.now(timezone.utc).isoformat()
    await transition_review_fields(
        db,
        document_id=document_id,
        patch={
            "status": DocumentStatus.EXPIRED.value,
            "evidence_review_state": EvidenceReviewState.EXPIRED.value,
            "assurance_tier": AssuranceTier.SYSTEM_EXPIRED.value,
            "review_required": False,
            "updated_at": now,
        },
        reviewer_id=user.get("portal_user_id"),
        correlation_id=corr,
        prev_doc=doc,
        validation_snapshot=None,
        notes=body.notes,
        decision_reason="MARK_EXPIRED",
    )
    exp_fanout: Dict[str, Any] = {}
    if doc.get("requirement_id"):
        await authority_sync_with_transition_observability(
            db,
            str(doc["requirement_id"]),
            property_id=str(doc.get("property_id") or "") or None,
            client_id=str(doc.get("client_id") or ""),
            correlation_base=str(corr),
            transition_origin="routes.evidence_review.mark_expired_review",
            transition_fanout=exp_fanout,
        )
        merge_document_path_lineage_flags(exp_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(exp_fanout, review_id=str(corr), review_reversal_possible=True)
    await _sync_prop_recalc(
        db,
        property_id=doc.get("property_id"),
        client_id=doc.get("client_id"),
        actor_id=user.get("portal_user_id"),
        doc_id=document_id,
        reason=TRIGGER_DOC_STATUS_CHANGED,
        transition_fanout=exp_fanout if exp_fanout.get("transition_id") else None,
        correlation_id=str(corr),
        trigger_origin="routes.evidence_review.mark_expired_review",
        propagation_stage="post_review_mark_expired",
    )
    return {"message": "Marked expired", "correlation_id": corr}


@router.post("/{document_id}/review/supersede")
async def supersede_evidence(request: Request, document_id: str, body: SupersedeBody = Body(default_factory=SupersedeBody)):
    _v2_guard()
    user = await admin_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    corr = body.correlation_id or correlation_id_new()
    now = datetime.now(timezone.utc).isoformat()
    meta_notes = body.notes or ""
    if body.superseded_by_document_id:
        meta_notes = (meta_notes + f" superseded_by={body.superseded_by_document_id}").strip()

    await transition_review_fields(
        db,
        document_id=document_id,
        patch={
            "status": DocumentStatus.EXPIRED.value,
            "evidence_review_state": EvidenceReviewState.SUPERSEDED.value,
            "assurance_tier": AssuranceTier.NONE.value,
            "review_required": False,
            "updated_at": now,
        },
        reviewer_id=user.get("portal_user_id"),
        correlation_id=corr,
        prev_doc=doc,
        validation_snapshot=None,
        notes=meta_notes or None,
        decision_reason="SUPERSEDED",
    )
    sup_fanout: Dict[str, Any] = {}
    if doc.get("requirement_id"):
        await authority_sync_with_transition_observability(
            db,
            str(doc["requirement_id"]),
            property_id=str(doc.get("property_id") or "") or None,
            client_id=str(doc.get("client_id") or ""),
            correlation_base=str(corr),
            transition_origin="routes.evidence_review.supersede_evidence",
            transition_fanout=sup_fanout,
        )
        merge_document_path_lineage_flags(sup_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(
            sup_fanout,
            review_id=str(corr),
            review_reversal_possible=True,
            reassignment_replay_possible=bool((body.superseded_by_document_id or "").strip()),
        )
    await _sync_prop_recalc(
        db,
        property_id=doc.get("property_id"),
        client_id=doc.get("client_id"),
        actor_id=user.get("portal_user_id"),
        doc_id=document_id,
        reason=TRIGGER_DOC_STATUS_CHANGED,
        transition_fanout=sup_fanout if sup_fanout.get("transition_id") else None,
        correlation_id=str(corr),
        trigger_origin="routes.evidence_review.supersede_evidence",
        propagation_stage="post_review_supersede",
    )
    return {"message": "Evidence superseded", "correlation_id": corr}
