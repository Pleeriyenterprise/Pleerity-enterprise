"""
Admin Discovery review workflow routes — Stage O.

Review queue, detail, audit history, and reviewer actions only.
No DiscoveryImportService, LeadService, CRM writes, or import routes.
"""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from middleware import admin_route_guard
from services.discovery import discovery_config
from services.discovery.discovery_approval_queue_service import (
    DiscoveryApprovalQueueError,
    DiscoveryApprovalQueueService,
    ReviewQueueFilters,
    ReviewerAttribution,
)
from services.discovery.discovery_audit_service import DiscoveryAuditService
from services.discovery.discovery_duplicate_service import DiscoveryDuplicateService
from services.discovery.discovery_models import DiscoveryErasureStatus
from services.discovery.discovery_quality_service import DiscoveryQualityService

FORBIDDEN_RESPONSE_KEYS = frozenset(
    {
        "raw_payload",
        "raw_row",
        "csv_row",
        "html_payload",
        "provider_raw_response",
        "raw_payload_reference",
    }
)

ERASED_PII_FIELDS = frozenset(
    {
        "email",
        "phone",
        "contact_name",
        "company_name",
        "website",
        "source_url",
    }
)


class ApproveBody(BaseModel):
    override_reason: Optional[str] = None
    notes: Optional[str] = None
    reason_code: Optional[str] = None


class RejectBody(BaseModel):
    reason_code: str = Field(..., min_length=1)
    notes: str = Field(..., min_length=1)


class RequestChangesBody(BaseModel):
    change_request_notes: str = Field(..., min_length=1)


class ClearDuplicateBody(BaseModel):
    reason_code: Optional[str] = None
    notes: Optional[str] = None


def _discovery_module_guard() -> None:
    if not discovery_config.is_discovery_module_enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "DISCOVERY_MODULE_DISABLED",
                "message": "Discovery module is not enabled",
            },
        )


async def _require_discovery_admin(request: Request) -> dict:
    _discovery_module_guard()
    return await admin_route_guard(request)


router = APIRouter(
    prefix="/api/admin/discovery/review",
    tags=["admin-discovery-review"],
    dependencies=[Depends(_require_discovery_admin)],
)


def _attribution_from_user(user: Mapping[str, Any]) -> ReviewerAttribution:
    actor_id = str(user.get("portal_user_id") or user.get("user_id") or "").strip()
    actor_email = str(user.get("email") or "").strip()
    return ReviewerAttribution(actor_id=actor_id, actor_email=actor_email)


def _strip_forbidden_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _strip_forbidden_keys(v)
            for k, v in value.items()
            if k not in FORBIDDEN_RESPONSE_KEYS
        }
    if isinstance(value, list):
        return [_strip_forbidden_keys(item) for item in value]
    return value


def _sanitize_prospect(prospect: Mapping[str, Any]) -> Dict[str, Any]:
    data = _strip_forbidden_keys(copy.deepcopy(dict(prospect)))
    if data.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
        for field in ERASED_PII_FIELDS:
            if field in data and data[field] not in (None, "", "[ERASED]"):
                data[field] = "[ERASED]"
        data["email"] = None
        data["phone"] = None
    return data


def _presence_flags(prospect: Mapping[str, Any]) -> Dict[str, bool]:
    erased = prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value
    if erased:
        return {"has_email": False, "has_phone": False}
    email = prospect.get("email")
    phone = prospect.get("phone")
    return {
        "has_email": bool(email and str(email).strip() and email != "[ERASED]"),
        "has_phone": bool(phone and str(phone).strip() and phone != "[ERASED]"),
    }


def _queue_item(prospect: Mapping[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_prospect(prospect)
    presence = _presence_flags(prospect)
    return {
        "prospect_id": sanitized.get("prospect_id"),
        "company_name": sanitized.get("company_name"),
        "contact_name": sanitized.get("contact_name"),
        **presence,
        "provider": sanitized.get("provider"),
        "campaign_id": sanitized.get("campaign_id"),
        "review_status": sanitized.get("review_status"),
        "duplicate_status": sanitized.get("duplicate_status"),
        "platform_quality_score": sanitized.get("platform_quality_score"),
        "review_priority": sanitized.get("review_priority"),
        "created_at": sanitized.get("created_at"),
        "erasure_status": sanitized.get("erasure_status"),
    }


async def _duplicate_evidence_for_prospect(
    prospect: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    audit_result = await DiscoveryAuditService.list_prospect_audit_events(
        str(prospect.get("prospect_id") or ""),
        skip=0,
        limit=200,
    )
    for event in reversed(audit_result.items):
        details = event.get("details") or {}
        snapshot = details.get("duplicate_evidence_snapshot")
        if snapshot:
            return _strip_forbidden_keys(snapshot)

    if prospect.get("duplicate_status") in ("possible", "confirmed"):
        enriched = DiscoveryDuplicateService.enrich_prospect_hashes(prospect)
        candidates = await DiscoveryDuplicateService.find_duplicate_candidates(
            enriched,
            exclude_prospect_id=str(prospect.get("prospect_id") or ""),
        )
        classification = DiscoveryDuplicateService.classify_duplicate(
            enriched, candidates
        )
        if classification.classification.value != "none":
            return _strip_forbidden_keys(classification.to_dict())
    return None


def _quality_detail(prospect: Mapping[str, Any]) -> Dict[str, Any]:
    inputs = DiscoveryQualityService.quality_inputs_from_mapping(prospect)
    explanation = DiscoveryQualityService.explain_quality_score(inputs)
    return _strip_forbidden_keys(explanation)


def _audit_event_for_api(event: Mapping[str, Any]) -> Dict[str, Any]:
    return _strip_forbidden_keys(copy.deepcopy(dict(event)))


def _queue_error(exc: DiscoveryApprovalQueueError) -> HTTPException:
    status = 404 if exc.code == "PROSPECT_NOT_FOUND" else 400
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": exc.message},
    )


@router.get("/queue")
async def get_review_queue(
    review_status: Optional[str] = None,
    duplicate_status: Optional[str] = None,
    provider: Optional[str] = None,
    campaign_id: Optional[str] = None,
    quality_score_min: Optional[int] = Query(None, ge=0, le=100),
    quality_score_max: Optional[int] = Query(None, ge=0, le=100),
    review_priority_min: Optional[int] = Query(None, ge=0, le=100),
    review_priority_max: Optional[int] = Query(None, ge=0, le=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Return paginated discovery review queue."""
    filters = ReviewQueueFilters(
        review_status=review_status,
        duplicate_status=duplicate_status,
        provider=provider,
        campaign_id=campaign_id,
        quality_score_min=quality_score_min,
        quality_score_max=quality_score_max,
        review_priority_min=review_priority_min,
        review_priority_max=review_priority_max,
        skip=skip,
        limit=limit,
    )
    result = await DiscoveryApprovalQueueService.list_review_queue(filters)
    return {
        "items": [_queue_item(item) for item in result.items],
        "total": result.total,
        "skip": result.skip,
        "limit": result.limit,
    }


@router.get("/summary")
async def get_review_summary(
):
    """Return queue summary counts."""
    return await DiscoveryApprovalQueueService.get_review_summary()


@router.get("/{prospect_id}")
async def get_review_detail(
    prospect_id: str,
):
    """Return review detail for a single prospect."""
    item = await DiscoveryApprovalQueueService.get_review_item(prospect_id)
    if not item:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROSPECT_NOT_FOUND", "message": "Prospect not found"},
        )

    prospect = item["prospect"]
    sanitized = _sanitize_prospect(prospect)
    audit_result = await DiscoveryAuditService.list_prospect_audit_events(
        prospect_id, skip=0, limit=200
    )
    audit_summary = DiscoveryAuditService.build_audit_summary(audit_result.items)
    duplicate_evidence = await _duplicate_evidence_for_prospect(prospect)
    quality = _quality_detail(prospect)

    return {
        "prospect": sanitized,
        "review_status": sanitized.get("review_status"),
        "duplicate_status": sanitized.get("duplicate_status"),
        "duplicate_evidence": duplicate_evidence,
        "platform_quality_score": sanitized.get("platform_quality_score"),
        "quality_breakdown": quality.get("breakdown"),
        "quality_explanation": {
            "strengths": quality.get("strengths"),
            "weaknesses": quality.get("weaknesses"),
            "recommended_improvements": quality.get("recommended_improvements"),
            "breakdown_lines": quality.get("breakdown_lines"),
        },
        "origin_lineage": sanitized.get("origin_lineage") or [],
        "lawful_basis": sanitized.get("lawful_basis"),
        "marketing_consent": sanitized.get("marketing_consent"),
        "import_readiness": item.get("import_readiness"),
        "import_readiness_notice": (
            "Import readiness only. Import is not enabled in this stage."
        ),
        "audit_summary": audit_summary,
        "audit_history_path": f"/api/admin/discovery/review/{prospect_id}/audit",
    }


@router.get("/{prospect_id}/audit")
async def get_prospect_audit_history(
    prospect_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Return audit history for a prospect."""
    prospect = await DiscoveryApprovalQueueService.get_review_item(prospect_id)
    if not prospect:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROSPECT_NOT_FOUND", "message": "Prospect not found"},
        )
    result = await DiscoveryAuditService.list_prospect_audit_events(
        prospect_id, skip=skip, limit=limit
    )
    return {
        "items": [_audit_event_for_api(e) for e in result.items],
        "total": result.total,
        "skip": result.skip,
        "limit": result.limit,
        "summary": DiscoveryAuditService.build_audit_summary(result.items),
    }


@router.post("/{prospect_id}/approve")
async def approve_prospect(
    prospect_id: str,
    body: ApproveBody,
    current_user: dict = Depends(_require_discovery_admin),
):
    """Approve prospect — no CRM import."""
    attribution = _attribution_from_user(current_user)
    try:
        result = await DiscoveryApprovalQueueService.approve_prospect(
            prospect_id,
            attribution,
            override_reason=body.override_reason,
            override_notes=body.notes,
            reason_code=body.reason_code,
        )
    except DiscoveryApprovalQueueError as exc:
        raise _queue_error(exc) from exc
    return {
        "prospect": _sanitize_prospect(result["prospect"]),
        "warnings": result.get("warnings") or [],
        "import_eligible": result.get("import_eligible"),
        "import_blocking_reasons": result.get("import_blocking_reasons") or [],
        "import_readiness_notice": (
            "Import readiness only. Import is not enabled in this stage."
        ),
    }


@router.post("/{prospect_id}/reject")
async def reject_prospect(
    prospect_id: str,
    body: RejectBody,
    current_user: dict = Depends(_require_discovery_admin),
):
    """Reject prospect."""
    attribution = _attribution_from_user(current_user)
    try:
        result = await DiscoveryApprovalQueueService.reject_prospect(
            prospect_id,
            attribution,
            reason_code=body.reason_code.strip(),
            notes=body.notes.strip(),
        )
    except DiscoveryApprovalQueueError as exc:
        raise _queue_error(exc) from exc
    return {"prospect": _sanitize_prospect(result["prospect"])}


@router.post(
    "/{prospect_id}/request-changes",
)
async def request_changes(
    prospect_id: str,
    body: RequestChangesBody,
    current_user: dict = Depends(_require_discovery_admin),
):
    """Request changes on a prospect."""
    attribution = _attribution_from_user(current_user)
    try:
        result = await DiscoveryApprovalQueueService.request_changes(
            prospect_id,
            attribution,
            change_request_notes=body.change_request_notes.strip(),
        )
    except DiscoveryApprovalQueueError as exc:
        raise _queue_error(exc) from exc
    return {
        "prospect": _sanitize_prospect(result["prospect"]),
        "import_eligible": result.get("import_eligible"),
        "import_readiness_notice": (
            "Import readiness only. Import is not enabled in this stage."
        ),
    }


@router.post(
    "/{prospect_id}/mark-duplicate",
)
async def mark_duplicate(
    prospect_id: str,
    current_user: dict = Depends(_require_discovery_admin),
):
    """Mark prospect as duplicate."""
    attribution = _attribution_from_user(current_user)
    try:
        result = await DiscoveryApprovalQueueService.mark_duplicate(
            prospect_id, attribution
        )
    except DiscoveryApprovalQueueError as exc:
        raise _queue_error(exc) from exc
    return {
        "prospect": _sanitize_prospect(result["prospect"]),
        "classification": _strip_forbidden_keys(result.get("classification") or {}),
    }


@router.post(
    "/{prospect_id}/clear-duplicate",
)
async def clear_duplicate(
    prospect_id: str,
    body: ClearDuplicateBody,
    current_user: dict = Depends(_require_discovery_admin),
):
    """Clear duplicate status."""
    attribution = _attribution_from_user(current_user)
    try:
        result = await DiscoveryApprovalQueueService.clear_duplicate(
            prospect_id,
            attribution,
            reason_code=body.reason_code,
            notes=body.notes,
        )
    except DiscoveryApprovalQueueError as exc:
        raise _queue_error(exc) from exc
    return {"prospect": _sanitize_prospect(result["prospect"])}


@router.post("/{prospect_id}/archive")
async def archive_prospect(
    prospect_id: str,
    current_user: dict = Depends(_require_discovery_admin),
):
    """Archive prospect."""
    attribution = _attribution_from_user(current_user)
    try:
        result = await DiscoveryApprovalQueueService.archive_prospect(
            prospect_id, attribution
        )
    except DiscoveryApprovalQueueError as exc:
        raise _queue_error(exc) from exc
    return {"prospect": _sanitize_prospect(result["prospect"])}
