"""
Admin Compliance Requirement Registry — Mongo-backed draft governance and **publish queue**.

Drafts and bundle imports are preparation data until a queue item is **published**; the active
published snapshot is then merged into ``build_requirement_plan_for_property`` (same path as
materialisation and admin plan-preview). Unpublished drafts still do not affect client generation.

Compare endpoints project the in-code engine baseline for drift review only.

``GET /preview-simulation`` runs the same planner + serializer as production (including active
published merge when configured), then merges Mongo drafts in memory for read-only comparison.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard, require_admin, require_owner, require_owner_or_admin
from models import AuditAction, UserRole
from services.compliance_registry_admin_service import (
    COLLECTION,
    build_published_baseline_snapshot,
    build_registry_preview_simulation,
    bundle_entries_to_drafts,
    default_draft_shell,
    diff_draft_vs_baseline,
    load_baseline_bundle_from_disk,
    merge_partial_draft,
    validate_registry_draft,
)
from services.compliance_registry_publish_service import (
    REMATERIALISATION_INFO,
    approve_publish_queue_item,
    create_publish_queue_item,
    fetch_active_published_registry_entries,
    fetch_published_metadata,
    get_publish_queue_item,
    get_published_history_record,
    list_publish_queue_items,
    list_published_history,
    publish_publish_queue_item,
    reject_publish_queue_item,
    revert_active_published_to_line_version,
    submit_publish_queue_item,
)
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/compliance/registry",
    tags=["admin-compliance-registry"],
    dependencies=[Depends(admin_route_guard)],
)


def _actor(user: dict) -> Dict[str, str]:
    return {
        "portal_user_id": str(user.get("portal_user_id") or user.get("user_id") or ""),
        "email": str(user.get("email") or ""),
    }


def _portal_user_role_for_audit(user: dict) -> Optional[UserRole]:
    try:
        return UserRole(str(user.get("role") or ""))
    except ValueError:
        return None


def _strip_id(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


class RegistryDraftCreateBody(BaseModel):
    canonical_code: str = Field(..., min_length=1, max_length=64)
    scope_key: str = Field(default="DEFAULT", max_length=64)


class RegistryDraftPatchBody(BaseModel):
    patch: Dict[str, Any] = Field(default_factory=dict)


class ImportBaselineBody(BaseModel):
    """When force is true, existing drafts with the same (canonical_code, scope_key) are replaced."""

    force: bool = False


class PublishQueueCreateBody(BaseModel):
    title: str = Field(default="", max_length=256)
    draft_entry_ids: List[str] = Field(..., min_length=1)


class PublishRejectBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


@router.get("/drafts")
async def list_registry_drafts(
    user: dict = Depends(require_admin),
    q: Optional[str] = Query(None, description="Filter by canonical_code or name substring"),
    needs_review: bool = Query(
        False,
        description="When true, only drafts with non-empty governance.needs_review_fields",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    _ = user
    db = database.get_db()
    col = db[COLLECTION]
    parts: List[Dict[str, Any]] = []
    if q and str(q).strip():
        qq = str(q).strip()
        parts.append(
            {
                "$or": [
                    {"canonical_code": {"$regex": qq, "$options": "i"}},
                    {"identity.name": {"$regex": qq, "$options": "i"}},
                ]
            }
        )
    if needs_review:
        parts.append({"governance.needs_review_fields.0": {"$exists": True}})
    if not parts:
        filt: Dict[str, Any] = {}
    elif len(parts) == 1:
        filt = parts[0]
    else:
        filt = {"$and": parts}
    cursor = (
        col.find(
            filt,
            {
                "_id": 0,
                "entry_id": 1,
                "canonical_code": 1,
                "scope_key": 1,
                "status": 1,
                "identity": 1,
                "jurisdiction": 1,
                "updated_at": 1,
                "governance.needs_review_fields": 1,
                "governance.import_row_ref": 1,
                "governance.import_source": 1,
            },
        )
        .sort([("canonical_code", 1), ("scope_key", 1)])
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)
    total = await col.count_documents(filt)
    review_queue_total = await col.count_documents({"governance.needs_review_fields.0": {"$exists": True}})
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "review_queue_total": review_queue_total,
    }


@router.get("/drafts/{entry_id}")
async def get_registry_draft(entry_id: str, user: dict = Depends(require_admin)):
    _ = user
    db = database.get_db()
    doc = await db[COLLECTION].find_one({"entry_id": entry_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return doc


@router.get("/drafts/{entry_id}/compare")
async def compare_registry_draft(entry_id: str, user: dict = Depends(require_admin)):
    _ = user
    db = database.get_db()
    doc = await db[COLLECTION].find_one({"entry_id": entry_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    code = str(doc.get("canonical_code") or "").strip().upper()
    baseline = build_published_baseline_snapshot(code)
    rows = diff_draft_vs_baseline(doc, baseline)
    return {"entry_id": entry_id, "canonical_code": code, "baseline": baseline, "diff": rows}


@router.post("/drafts", status_code=status.HTTP_201_CREATED)
async def create_registry_draft(body: RegistryDraftCreateBody, user: dict = Depends(require_owner_or_admin)):
    db = database.get_db()
    code = str(body.canonical_code or "").strip().upper()
    sk = str(body.scope_key or "DEFAULT").strip() or "DEFAULT"
    existing = await db[COLLECTION].find_one({"canonical_code": code, "scope_key": sk}, {"_id": 0, "entry_id": 1})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Draft already exists for this code and scope_key", "entry_id": existing.get("entry_id")},
        )
    shell = default_draft_shell(canonical_code=code, scope_key=sk)
    shell["updated_by"] = _actor(user)
    errs = validate_registry_draft(shell)
    if errs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": errs})
    await db[COLLECTION].insert_one({**shell, "_id": ObjectId()})
    return _strip_id(await db[COLLECTION].find_one({"entry_id": shell["entry_id"]}, {"_id": 0}))


@router.patch("/drafts/{entry_id}")
async def patch_registry_draft(
    entry_id: str,
    body: RegistryDraftPatchBody,
    user: dict = Depends(require_owner_or_admin),
):
    db = database.get_db()
    col = db[COLLECTION]
    existing = await col.find_one({"entry_id": entry_id})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    base = {k: v for k, v in existing.items() if k != "_id"}
    if not isinstance(base, dict):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid stored document")
    merged = merge_partial_draft(base, body.patch if isinstance(body.patch, dict) else {})
    merged["updated_by"] = _actor(user)
    errs = validate_registry_draft(merged)
    if errs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": errs})
    await col.update_one({"entry_id": entry_id}, {"$set": {k: v for k, v in merged.items() if k != "_id"}})
    return _strip_id(await col.find_one({"entry_id": entry_id}, {"_id": 0}))


@router.post("/import-baseline-bundle")
async def import_baseline_bundle(body: ImportBaselineBody, user: dict = Depends(require_owner_or_admin)):
    """
    Load structured baseline JSON from disk (workbook-aligned import). Upserts by (canonical_code, scope_key).
    """
    db = database.get_db()
    col = db[COLLECTION]
    try:
        bundle = load_baseline_bundle_from_disk()
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Baseline bundle file missing")
    except Exception as e:
        logger.exception("Failed to read baseline bundle: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to read baseline bundle")

    drafts, summary = bundle_entries_to_drafts(bundle, actor=_actor(user))
    inserted = 0
    updated = 0
    skipped = 0

    for doc in drafts:
        code = doc.get("canonical_code")
        sk = doc.get("scope_key")
        filt = {"canonical_code": code, "scope_key": sk}
        prior = await col.find_one(filt, {"_id": 0, "entry_id": 1})
        if prior and not body.force:
            skipped += 1
            continue
        if prior and body.force:
            doc["entry_id"] = prior.get("entry_id") or doc.get("entry_id")
        errs = validate_registry_draft(doc)
        if errs:
            summary.setdefault("validation_failures", []).append({"canonical_code": code, "scope_key": sk, "errors": errs})
            continue
        if prior:
            await col.update_one(filt, {"$set": {k: v for k, v in doc.items() if k != "_id"}})
            updated += 1
        else:
            await col.insert_one({**doc, "_id": ObjectId()})
            inserted += 1

    summary["inserted"] = inserted
    summary["updated"] = updated
    summary["skipped_existing"] = skipped
    summary["force"] = body.force
    baseline_manual_review = {
        "unmapped_workbook_rows": bundle.get("unmapped_workbook_rows"),
        "detected_conflicts": bundle.get("detected_conflicts"),
        "suspected_cross_jurisdiction_mixing": bundle.get("suspected_cross_jurisdiction_mixing"),
        "mapping_summary": bundle.get("mapping_summary"),
    }
    return {"ok": True, "summary": summary, "baseline_manual_review": baseline_manual_review}


@router.get("/preview-simulation")
async def registry_preview_simulation(
    user: dict = Depends(require_admin),
    property_id: str = Query(..., min_length=1, description="Property to simulate against"),
    include_explanations: bool = Query(
        False,
        description="Include per-row catalog explanations (same as plan-preview).",
    ),
):
    """
    Read-only: run the **same** planner + serializer as production, then apply Mongo draft
    overlays in-memory for comparison. No writes; does not affect client generation.

    Response includes ``preview_coverage``: this pass **decorates** rows the production planner
    already emits; it does **not** model would-publish expansion (net-new plan members). Treat
    results as useful for cadence/metadata/visibility overrides on existing rows, not as a full
    expansion simulator for net-new plan members.
    """
    _ = user
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id}, {"_id": 0})
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    client_id = prop.get("client_id")
    client_doc = (
        await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) if client_id else None
    ) or {}

    published = await fetch_active_published_registry_entries(db)
    drafts = await db[COLLECTION].find({}, {"_id": 0}).sort([("canonical_code", 1), ("scope_key", 1)]).to_list(2000)
    sim = build_registry_preview_simulation(
        prop,
        client_doc,
        drafts,
        include_explanations=include_explanations,
        published_registry_entries=published,
    )
    return {
        "property_id": property_id,
        "client_id": client_id,
        **sim,
    }


@router.get("/baseline-bundle-meta")
async def baseline_bundle_meta(user: dict = Depends(require_admin)):
    """Read-only: bundle version, disclaimer, and manual triage fields from disk (no DB writes)."""
    _ = user
    try:
        bundle = load_baseline_bundle_from_disk()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    entries = bundle.get("entries")
    return {
        "registry_layer": "draft_governance",
        "registry_layer_detail": (
            "Admin UI manages Mongo drafts and the publish queue. Imports populate drafts; "
            "publishing activates a snapshot merged into requirement generation alongside the in-code registry."
        ),
        "import_bundle_version": bundle.get("import_bundle_version"),
        "source": bundle.get("source"),
        "disclaimer": bundle.get("disclaimer"),
        "mapping_summary": bundle.get("mapping_summary"),
        "unmapped_workbook_rows": bundle.get("unmapped_workbook_rows"),
        "detected_conflicts": bundle.get("detected_conflicts"),
        "suspected_cross_jurisdiction_mixing": bundle.get("suspected_cross_jurisdiction_mixing"),
        "entry_count": len(entries) if isinstance(entries, list) else 0,
    }


@router.get("/publish-queue")
async def registry_publish_queue_list(user: dict = Depends(require_admin)):
    _ = user
    db = database.get_db()
    items = await list_publish_queue_items(db, limit=200)
    return {"items": items}


@router.post("/publish-queue")
async def registry_publish_queue_create(
    request: Request,
    body: PublishQueueCreateBody,
    user: dict = Depends(require_owner_or_admin),
):
    db = database.get_db()
    actor = _actor(user)
    try:
        doc = await create_publish_queue_item(
            db,
            title=body.title,
            draft_entry_ids=body.draft_entry_ids,
            actor=actor,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    qid = str(doc.get("queue_id") or "")
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_PUBLISH_QUEUE_CREATED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        resource_type="compliance_registry_publish_queue",
        resource_id=qid,
        metadata={"draft_entry_ids": body.draft_entry_ids, "title": doc.get("title")},
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True, "queue": doc}


@router.get("/publish-queue/{queue_id}")
async def registry_publish_queue_get(queue_id: str, user: dict = Depends(require_admin)):
    _ = user
    db = database.get_db()
    doc = await get_publish_queue_item(db, queue_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    return {"queue": _strip_id(doc)}


@router.post("/publish-queue/{queue_id}/submit")
async def registry_publish_queue_submit(
    request: Request,
    queue_id: str,
    user: dict = Depends(require_owner_or_admin),
):
    db = database.get_db()
    try:
        doc = await submit_publish_queue_item(db, queue_id, _actor(user))
    except ValueError as e:
        msg = str(e)
        if msg == "queue_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_PUBLISH_QUEUE_SUBMITTED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        resource_type="compliance_registry_publish_queue",
        resource_id=queue_id,
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True, "queue": doc}


@router.post("/publish-queue/{queue_id}/approve")
async def registry_publish_queue_approve(
    request: Request,
    queue_id: str,
    user: dict = Depends(require_owner),
):
    """Owner-only (temporary product gate); Admin may still submit/reject earlier states."""
    db = database.get_db()
    try:
        doc = await approve_publish_queue_item(db, queue_id, _actor(user))
    except ValueError as e:
        msg = str(e)
        if msg == "queue_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_PUBLISH_QUEUE_APPROVED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        resource_type="compliance_registry_publish_queue",
        resource_id=queue_id,
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True, "queue": doc}


@router.post("/publish-queue/{queue_id}/reject")
async def registry_publish_queue_reject(
    request: Request,
    queue_id: str,
    body: PublishRejectBody,
    user: dict = Depends(require_owner_or_admin),
):
    db = database.get_db()
    try:
        doc = await reject_publish_queue_item(db, queue_id, _actor(user), reason=body.reason)
    except ValueError as e:
        msg = str(e)
        if msg == "queue_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_PUBLISH_QUEUE_REJECTED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        resource_type="compliance_registry_publish_queue",
        resource_id=queue_id,
        metadata={"reason": (body.reason or "").strip()},
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True, "queue": doc}


@router.post("/publish-queue/{queue_id}/publish")
async def registry_publish_queue_publish(
    request: Request,
    queue_id: str,
    user: dict = Depends(require_owner),
):
    """Owner-only: activates the published snapshot consumed by the planner/materialiser."""
    db = database.get_db()
    try:
        result = await publish_publish_queue_item(db, queue_id, _actor(user))
    except ValueError as e:
        msg = str(e)
        if msg == "queue_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e
        if msg.startswith("missing_draft:") or msg.startswith("duplicate_publish_key:"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_PUBLISH_ACTIVATED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        resource_type="compliance_registry_publish_queue",
        resource_id=queue_id,
        metadata=result,
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True, **result, "rematerialisation": REMATERIALISATION_INFO}


@router.get("/published/active")
async def registry_published_active(user: dict = Depends(require_admin)):
    """Read-only: active published snapshot metadata (not the full entries payload)."""
    _ = user
    db = database.get_db()
    meta = await fetch_published_metadata(db)
    if not meta:
        return {
            "active": False,
            "singleton_key": "active_registry",
            "version": None,
            "updated_at": None,
            "entry_count": 0,
            "rematerialisation": REMATERIALISATION_INFO,
        }
    ent = await fetch_active_published_registry_entries(db)
    n = len(ent) if isinstance(ent, dict) else 0
    return {
        "active": True,
        "singleton_key": meta.get("singleton_key"),
        "version": meta.get("version"),
        "updated_at": meta.get("updated_at"),
        "last_queue_id": meta.get("last_queue_id"),
        "last_published_by": meta.get("last_published_by"),
        "last_activation_kind": meta.get("last_activation_kind"),
        "reverted_from_published_line_version": meta.get("reverted_from_published_line_version"),
        "entry_count": n,
        "rematerialisation": REMATERIALISATION_INFO,
    }


@router.get("/published/history")
async def registry_published_history_list(
    user: dict = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Append-only published snapshot activations (no ``entries`` body — use detail GET)."""
    _ = user
    db = database.get_db()
    items = await list_published_history(db, skip=skip, limit=limit)
    return {"items": items, "skip": skip, "limit": limit, "rematerialisation": REMATERIALISATION_INFO}


@router.get("/published/history/{published_line_version}")
async def registry_published_history_get(
    published_line_version: Annotated[int, Path(ge=1)],
    user: dict = Depends(require_admin),
    include_entries: bool = Query(
        False,
        description="When true, includes full entries payload (can be large).",
    ),
):
    """Inspect one historical activation by monotonic ``published_line_version``."""
    _ = user
    db = database.get_db()
    row = await get_published_history_record(db, published_line_version, include_entries=include_entries)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="history_not_found")
    return {"record": row, "rematerialisation": REMATERIALISATION_INFO}


@router.post("/published/revert-to/{published_line_version}")
async def registry_published_revert_to_version(
    request: Request,
    published_line_version: Annotated[int, Path(ge=1)],
    user: dict = Depends(require_owner),
):
    """
    Owner-only: copy ``entries`` from the append-only history row into the active singleton.

    ``published_line_version`` is the historical line to restore (not the current singleton version).
    """
    db = database.get_db()
    actor = _actor(user)
    try:
        result = await revert_active_published_to_line_version(db, published_line_version, actor)
    except ValueError as e:
        msg = str(e)
        if msg == "history_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e
        if msg in ("already_active_line_version", "invalid_version"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_PUBLISH_REVERTED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        resource_type="compliance_requirement_registry_published",
        resource_id=str(published_line_version),
        metadata=result,
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True, **result, "rematerialisation": REMATERIALISATION_INFO}
