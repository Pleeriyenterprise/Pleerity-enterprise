"""
Governed compliance rule versions: draft → submit → approve → publish (Owner/Admin for approve/publish).

Engine/scoring code is unchanged; published payloads sync into ``requirement_rules`` (governed=true).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from middleware import admin_route_guard, require_owner_or_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/compliance/governed-rules", tags=["Admin - Governed compliance rules"])


class CreateDraftBody(BaseModel):
    rule_type: str
    clone_from_version_id: Optional[str] = None
    initial_payload: Optional[Dict[str, Any]] = None


class PatchDraftBody(BaseModel):
    payload: Optional[Dict[str, Any]] = None
    change_reason: Optional[str] = None
    effective_from: Optional[str] = None


class PublishOptionsBody(BaseModel):
    enqueue_property_recalc: bool = True
    recalc_max_properties: int = Field(2000, ge=1, le=10000)


@router.get("/versions")
async def list_governed_versions(
    request: Request,
    rule_type: Optional[str] = None,
    limit: int = 50,
):
    await admin_route_guard(request)
    from services.compliance_governed_rules_service import list_versions

    try:
        return {"versions": await list_versions(rule_type, limit=limit)}
    except Exception as e:
        logger.exception("list_governed_versions: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list versions")


@router.get("/versions/{version_id}")
async def get_governed_version(request: Request, version_id: str):
    await admin_route_guard(request)
    from services.compliance_governed_rules_service import get_version

    v = await get_version(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@router.get("/versions/{version_id}/preview-impact")
async def preview_impact(request: Request, version_id: str):
    await admin_route_guard(request)
    from services.compliance_governed_rules_service import preview_publish_impact

    try:
        return await preview_publish_impact(version_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("preview_impact: %s", e)
        raise HTTPException(status_code=500, detail="Preview failed")


@router.get("/versions/{version_id}/runtime-diff")
async def runtime_diff(request: Request, version_id: str):
    await admin_route_guard(request)
    from services.compliance_governed_rules_service import runtime_row_diff

    try:
        return await runtime_row_diff(version_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post("/drafts")
async def create_draft(request: Request, body: CreateDraftBody):
    user = await admin_route_guard(request)
    from services.compliance_governed_rules_service import create_draft

    try:
        doc = await create_draft(
            body.rule_type,
            user,
            clone_from_version_id=body.clone_from_version_id,
            initial_payload=body.initial_payload,
        )
        return doc
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.patch("/versions/{version_id}")
async def patch_draft(request: Request, version_id: str, body: PatchDraftBody):
    user = await admin_route_guard(request)
    from services.compliance_governed_rules_service import update_draft

    try:
        patch = body.model_dump(exclude_none=True)
        return await update_draft(version_id, user, patch)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/versions/{version_id}/submit")
async def submit_version(request: Request, version_id: str):
    user = await admin_route_guard(request)
    from services.compliance_governed_rules_service import submit_for_approval

    try:
        return await submit_for_approval(version_id, user)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/versions/{version_id}/approve")
async def approve(request: Request, version_id: str):
    user = await require_owner_or_admin(request)
    from services.compliance_governed_rules_service import approve_version

    try:
        return await approve_version(version_id, user)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/versions/{version_id}/publish")
async def publish(request: Request, version_id: str, body: PublishOptionsBody = PublishOptionsBody()):
    user = await require_owner_or_admin(request)
    from services.compliance_governed_rules_service import publish_version

    opts = body
    try:
        return await publish_version(
            version_id,
            user,
            enqueue_property_recalc=opts.enqueue_property_recalc,
            recalc_max_properties=opts.recalc_max_properties,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/rollback/{rule_type}")
async def rollback(request: Request, rule_type: str):
    user = await require_owner_or_admin(request)
    from services.compliance_governed_rules_service import rollback_published

    try:
        return await rollback_published(rule_type, user)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
