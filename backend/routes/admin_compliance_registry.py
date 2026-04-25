"""
Admin Compliance Requirement Registry — Mongo-backed draft governance and **publish queue**.

Drafts and bundle imports are preparation data until a queue item is **published**; each activation
**merges** this queue’s draft snapshots into the active published snapshot map (other keys already live
stay unless superseded by a later publish). That map is read by ``build_requirement_plan_for_property``
and related paths. Unpublished drafts still do not affect client generation.

Compare endpoints project the in-code engine baseline for drift review only.

``GET /preview-simulation`` runs the same planner + serializer as production (including active
published merge when configured), then merges Mongo drafts in memory for read-only comparison.
"""
from __future__ import annotations

import copy
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
    build_registry_publish_impact,
    bundle_entries_to_drafts,
    default_draft_shell,
    diff_draft_vs_baseline,
    load_baseline_bundle_from_disk,
    merge_partial_draft,
    validate_registry_draft,
)
from services.compliance_registry_conditions import condition_builder_options_payload, human_summary_registry_conditions
from services.compliance_registry_controlled_vocab import (
    REGISTRY_UK_DISPLAY_REGION_SET,
    controlled_field_options_payload,
    normalise_registry_draft_for_storage,
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
    record_publish_queue_review_ack,
    reject_publish_queue_item,
    revert_active_published_to_line_version,
    submit_publish_queue_item,
)
from services.requirement_client_runtime_surface import explain_runtime_requirement_rows_for_property
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


class PublishApproveBody(BaseModel):
    review_ack_token: str = Field(default="", max_length=128)


@router.get("/controlled-field-options")
async def registry_controlled_field_options(user: dict = Depends(require_admin)):
    """Canonical enum option sets for the registry editor (aligned with draft validation)."""
    _ = user
    return {**controlled_field_options_payload(), **condition_builder_options_payload()}


def _draft_match_clauses_for_published_keys(pub: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(pub, dict) or not pub:
        return []
    out: List[Dict[str, Any]] = []
    for k in pub.keys():
        ks = str(k).strip()
        if "|" not in ks:
            continue
        cc, sk = ks.split("|", 1)
        out.append({"canonical_code": cc, "scope_key": sk})
    return out


@router.get("/drafts")
async def list_registry_drafts(
    user: dict = Depends(require_admin),
    q: Optional[str] = Query(None, description="Filter by canonical_code or name substring"),
    needs_review: bool = Query(
        False,
        description="When true, only drafts with non-empty governance.needs_review_fields",
    ),
    ready_to_publish: bool = Query(
        False,
        description="When true, only drafts with empty/absent governance.needs_review_fields (editorial queue clear)",
    ),
    jurisdiction: Optional[str] = Query(
        None,
        description="Filter: draft lists this UK region in jurisdiction.display_jurisdictions (ENGLAND, …)",
    ),
    category: Optional[str] = Query(None, description="Exact identity.category (controlled enum, case-insensitive)"),
    requirement_type: Optional[str] = Query(
        None,
        description="Exact classification.requirement_type (DOCUMENT, JOB, …)",
    ),
    live_snapshot: Optional[str] = Query(
        None,
        description="yes = row key in active published snapshot; no = not in snapshot (ignored if unset)",
    ),
    sort: str = Query(
        "code_asc",
        description="code_asc | code_desc | name_asc | name_desc | updated_desc",
    ),
    include_registry_validation: bool = Query(
        False,
        description="When true, attach validate_registry_draft per row (use limit <= 50 for performance).",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    _ = user
    if include_registry_validation and int(limit) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="include_registry_validation requires limit <= 50",
        )
    if needs_review and ready_to_publish:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose either needs_review or ready_to_publish, not both",
        )
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
    if ready_to_publish:
        parts.append(
            {
                "$or": [
                    {"governance.needs_review_fields": {"$exists": False}},
                    {"governance.needs_review_fields": []},
                ]
            }
        )
    if category and str(category).strip():
        parts.append({"identity.category": str(category).strip().upper()})
    if requirement_type and str(requirement_type).strip():
        parts.append({"classification.requirement_type": str(requirement_type).strip().upper()})
    if jurisdiction and str(jurisdiction).strip():
        jur_tok = str(jurisdiction).strip().upper()
        if jur_tok not in REGISTRY_UK_DISPLAY_REGION_SET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"jurisdiction must be one of: {', '.join(sorted(REGISTRY_UK_DISPLAY_REGION_SET))}",
            )
        parts.append({"jurisdiction.display_jurisdictions": jur_tok})
    ls = (live_snapshot or "").strip().lower()
    if ls in ("yes", "y", "true", "1"):
        pub = await fetch_active_published_registry_entries(db)
        clauses = _draft_match_clauses_for_published_keys(pub)
        if not clauses:
            parts.append({"canonical_code": {"$in": []}})
        else:
            parts.append({"$or": clauses})
    elif ls in ("no", "n", "false", "0"):
        pub = await fetch_active_published_registry_entries(db)
        clauses = _draft_match_clauses_for_published_keys(pub)
        if clauses:
            parts.append({"$nor": clauses})
    elif live_snapshot not in (None, ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="live_snapshot must be yes or no")

    if not parts:
        filt: Dict[str, Any] = {}
    elif len(parts) == 1:
        filt = parts[0]
    else:
        filt = {"$and": parts}

    sort_key = (sort or "code_asc").strip().lower()
    sort_list: List[tuple]
    if sort_key == "code_desc":
        sort_list = [("canonical_code", -1), ("scope_key", -1)]
    elif sort_key == "name_asc":
        sort_list = [("identity.name", 1), ("canonical_code", 1)]
    elif sort_key == "name_desc":
        sort_list = [("identity.name", -1), ("canonical_code", 1)]
    elif sort_key == "updated_desc":
        sort_list = [("updated_at", -1), ("canonical_code", 1)]
    else:
        sort_list = [("canonical_code", 1), ("scope_key", 1)]

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
                "classification.requirement_type": 1,
                "jurisdiction": 1,
                "updated_at": 1,
                "governance.needs_review_fields": 1,
                "governance.import_row_ref": 1,
                "governance.import_source": 1,
            },
        )
        .sort(sort_list)
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)
    total = await col.count_documents(filt)
    review_queue_total = await col.count_documents({"governance.needs_review_fields.0": {"$exists": True}})

    if include_registry_validation:
        for item in items:
            eid = (item or {}).get("entry_id")
            if not eid:
                item["registry_validation"] = {"valid": False, "errors": ["missing entry_id"]}
                continue
            full = await col.find_one({"entry_id": eid}, {"_id": 0})
            if not full:
                item["registry_validation"] = {"valid": False, "errors": ["draft not found"]}
                continue
            d2 = copy.deepcopy(full)
            v_errs = validate_registry_draft(d2)
            item["registry_validation"] = {
                "valid": len(v_errs) == 0,
                "errors": v_errs,
            }

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "review_queue_total": review_queue_total,
    }


@router.get("/publish-impact")
async def registry_publish_impact(
    user: dict = Depends(require_admin),
    entry_ids: str = Query(
        ...,
        min_length=1,
        description="Comma-separated list of draft entry_id values to assess",
    ),
):
    """
    Pre-publish / operator impact: validation per draft, keys vs active published, region union.
    Read-only; does not mutate. Use before submit/approve to catch unsafe jurisdiction or copy gaps.
    """
    _ = user
    db = database.get_db()
    ids = [s.strip() for s in (entry_ids or "").split(",") if s.strip()]
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entry_ids required")
    draft_docs: List[Dict[str, Any]] = []
    for eid in ids:
        d = await db[COLLECTION].find_one({"entry_id": eid}, {"_id": 0})
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"draft_not_found:{eid}")
        draft_docs.append(d)
    published = await fetch_active_published_registry_entries(db)
    impact = build_registry_publish_impact(draft_docs, published_entries=published)
    return {
        "entry_ids": ids,
        "impact": impact,
        "rematerialisation": REMATERIALISATION_INFO,
    }


@router.get("/published/entry-keys")
async def registry_published_entry_keys_index(user: dict = Depends(require_admin)):
    """Lightweight index of keys in the active published snapshot (canonical_code|scope_key)."""
    _ = user
    db = database.get_db()
    ent = await fetch_active_published_registry_entries(db)
    if not isinstance(ent, dict) or not ent:
        return {"active": bool(ent), "keys": []}
    return {"active": True, "keys": sorted(ent.keys())}


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
    norm_warnings = normalise_registry_draft_for_storage(merged)
    merged["updated_by"] = _actor(user)
    errs = validate_registry_draft(merged)
    if errs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": errs})
    await col.update_one({"entry_id": entry_id}, {"$set": {k: v for k, v in merged.items() if k != "_id"}})
    out = _strip_id(await col.find_one({"entry_id": entry_id}, {"_id": 0}))
    if isinstance(out, dict) and norm_warnings:
        out = {**out, "normalisation_warnings": norm_warnings}
    return out


@router.delete("/drafts/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registry_draft(
    request: Request,
    entry_id: str,
    user: dict = Depends(require_owner_or_admin),
):
    """
    Permanently remove a draft registry row (e.g. data entry error). Does not alter the active
    published snapshot; republish if a published key must be retired (use lifecycle/archival flags).
    """
    db = database.get_db()
    res = await db[COLLECTION].delete_one({"entry_id": entry_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_DRAFT_DELETED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        resource_type="compliance_requirement_registry_draft",
        resource_id=entry_id,
        metadata={"entry_id": entry_id},
        ip_address=request.client.host if request.client else None,
    )


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


def _registry_entry_key(draft_doc: Dict[str, Any]) -> str:
    cc = str(draft_doc.get("canonical_code") or "").strip().upper()
    sk = str(draft_doc.get("scope_key") or "DEFAULT").strip() or "DEFAULT"
    return f"{cc}|{sk}"


def _field_diff_rows(current: Dict[str, Any], proposed: Dict[str, Any], *, prefix: str = "") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    keys = sorted(set((current or {}).keys()) | set((proposed or {}).keys()))
    for k in keys:
        path = f"{prefix}.{k}" if prefix else str(k)
        lv = (current or {}).get(k)
        rv = (proposed or {}).get(k)
        if isinstance(lv, dict) and isinstance(rv, dict):
            rows.extend(_field_diff_rows(lv, rv, prefix=path))
            continue
        if lv != rv:
            rows.append({"path": path, "current": lv, "proposed": rv})
    return rows


def _extract_review_warnings(draft_docs: List[Dict[str, Any]], impact: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if bool(impact.get("broad_uk_operator_warning")):
        out.append({"code": "broad_uk_scope", "severity": "warning", "message": "At least one draft covers all four UK regions."})
    if bool(impact.get("has_blocking_validation_errors")):
        out.append({"code": "validation_blockers", "severity": "error", "message": "One or more drafts contain blocking validation errors."})
    overlap: Dict[str, List[str]] = {}
    for d in draft_docs:
        cc = str(d.get("canonical_code") or "").strip().upper()
        if not cc:
            continue
        overlap.setdefault(cc, []).append(_registry_entry_key(d))
        jur = (d.get("jurisdiction") or {}).get("display_jurisdictions")
        if not isinstance(jur, list) or not [x for x in jur if str(x or "").strip()]:
            out.append(
                {
                    "code": "missing_jurisdiction",
                    "severity": "warning",
                    "entry_key": _registry_entry_key(d),
                    "message": "Client-visible draft has no explicit display_jurisdictions list.",
                }
            )
        short = str(d.get("why_it_matters_short") or "").strip()
        if not short:
            out.append(
                {
                    "code": "missing_why_it_matters_short",
                    "severity": "warning",
                    "entry_key": _registry_entry_key(d),
                    "message": "why_it_matters_short is empty.",
                }
            )
    for cc, keys in overlap.items():
        if len(keys) > 1:
            out.append(
                {
                    "code": "duplicate_or_overlap_risk",
                    "severity": "warning",
                    "canonical_code": cc,
                    "keys": sorted(keys),
                    "message": "Multiple scope entries for same canonical_code in this queue; verify scope intent.",
                }
            )
    return out


def _client_preview_payload_for_jurisdiction(draft_doc: Dict[str, Any], jurisdiction: str) -> Dict[str, Any]:
    jur = str(jurisdiction or "").strip().upper()
    by_j = draft_doc.get("why_it_matters_by_jurisdiction") if isinstance(draft_doc.get("why_it_matters_by_jurisdiction"), dict) else {}
    j_block = by_j.get(jur) if isinstance(by_j.get(jur), dict) else {}
    why_short = str(j_block.get("short") or draft_doc.get("why_it_matters_short") or "").strip() or None
    why_long = str(j_block.get("long") or draft_doc.get("why_it_matters_long") or "").strip() or None
    links = [x for x in (draft_doc.get("action_links") or []) if isinstance(x, dict)]
    filtered = []
    for link in links:
        js = link.get("jurisdictions")
        if isinstance(js, list) and js:
            tok = [str(x).strip().upper() for x in js if str(x).strip()]
            if jur not in tok:
                continue
        if link.get("is_active") is False:
            continue
        filtered.append(link)
    filtered.sort(key=lambda x: int(x.get("priority") or 9999))
    ab = draft_doc.get("action_behaviour") if isinstance(draft_doc.get("action_behaviour"), dict) else {}
    return {
        "jurisdiction": jur,
        "requirement_card": {
            "name": ((draft_doc.get("identity") or {}).get("name") or draft_doc.get("canonical_code")),
            "code": draft_doc.get("canonical_code"),
            "category": ((draft_doc.get("identity") or {}).get("category")),
            "criticality": ((draft_doc.get("classification") or {}).get("criticality")),
            "client_visible": ((draft_doc.get("classification") or {}).get("client_surface_visible")),
        },
        "why_it_matters_short": why_short,
        "why_it_matters_long": why_long,
        "action_links": filtered,
        "cta": {
            "primary_action_mode": ab.get("primary_action_mode"),
            "cta_label_override": ab.get("cta_label_override"),
        },
    }


@router.get("/publish-queue/{queue_id}/review")
async def registry_publish_queue_review(queue_id: str, user: dict = Depends(require_admin)):
    """
    Admin-only review payload reusing existing compare/impact logic + queue drafts.
    Also records a review acknowledgement token required by approve.
    """
    db = database.get_db()
    queue = await get_publish_queue_item(db, queue_id)
    if not queue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    ids = [str(x).strip() for x in (queue.get("draft_entry_ids") or []) if str(x).strip()]
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="queue_has_no_drafts")

    draft_docs: List[Dict[str, Any]] = []
    for eid in ids:
        d = await db[COLLECTION].find_one({"entry_id": eid}, {"_id": 0})
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"draft_not_found:{eid}")
        draft_docs.append(d)

    published_meta = await fetch_published_metadata(db) or {}
    published_entries = await fetch_active_published_registry_entries(db) or {}
    impact = build_registry_publish_impact(draft_docs, published_entries=published_entries)

    current_entries = dict(published_entries or {})
    proposed_entries = dict(current_entries)
    touched_rows: List[Dict[str, Any]] = []
    affected_jurisdictions: set[str] = set()
    for d in draft_docs:
        key = _registry_entry_key(d)
        proposed_entries[key] = d
        for tok in (((d.get("jurisdiction") or {}).get("display_jurisdictions")) or []):
            if str(tok).strip():
                affected_jurisdictions.add(str(tok).strip().upper())
        touched_rows.append(
            {
                "entry_id": d.get("entry_id"),
                "entry_key": key,
                "canonical_code": d.get("canonical_code"),
                "scope_key": d.get("scope_key"),
                "conditions_summary": human_summary_registry_conditions(d.get("conditions") if isinstance(d.get("conditions"), dict) else {}),
                "why_it_matters_short": d.get("why_it_matters_short"),
                "why_it_matters_long": d.get("why_it_matters_long"),
                "action_behaviour": d.get("action_behaviour"),
                "action_links": d.get("action_links") or [],
                "baseline_diff": diff_draft_vs_baseline(d, build_published_baseline_snapshot(str(d.get("canonical_code") or "").strip().upper())),
                "field_diff_vs_current_live": _field_diff_rows(current_entries.get(key) if isinstance(current_entries.get(key), dict) else {}, d),
                "current_live_entry": current_entries.get(key),
                "proposed_entry": d,
                "client_preview_by_jurisdiction": {
                    region: _client_preview_payload_for_jurisdiction(d, region)
                    for region in ("ENGLAND", "SCOTLAND", "WALES", "NORTHERN_IRELAND")
                },
            }
        )

    queue_with_ack = await record_publish_queue_review_ack(db, queue_id, _actor(user), scope="full_review")
    review_ack = (((queue_with_ack or {}).get("review_gate") or {}).get("review_ack") or {})
    warnings = _extract_review_warnings(draft_docs, impact)

    return {
        "queue": _strip_id(queue_with_ack),
        "review_ack_token": review_ack.get("token"),
        "current_live_published": {
            "active": bool(published_meta),
            "version": published_meta.get("version"),
            "updated_at": published_meta.get("updated_at"),
            "entry_count": len(current_entries),
            "entries": current_entries,
        },
        "proposed_published_after_approval": {
            "entry_count": len(proposed_entries),
            "entries": proposed_entries,
        },
        "touched_entries": touched_rows,
        "affected_jurisdictions": sorted(affected_jurisdictions),
        "publish_impact": impact,
        "warnings": warnings,
        "rematerialisation": REMATERIALISATION_INFO,
    }


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
    body: PublishApproveBody = PublishApproveBody(),
    user: dict = Depends(require_owner),
):
    """Owner-only (temporary product gate); Admin may still submit/reject earlier states."""
    db = database.get_db()
    q = await get_publish_queue_item(db, queue_id)
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="queue_not_found")
    gate = q.get("review_gate") if isinstance(q.get("review_gate"), dict) else {}
    review_ack = gate.get("review_ack") if isinstance(gate.get("review_ack"), dict) else {}
    expected_tok = str(review_ack.get("token") or "").strip()
    got_tok = str(body.review_ack_token or "").strip()
    if bool(gate.get("require_preview_before_approve", True)) and (not expected_tok or expected_tok != got_tok):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="preview_required_before_approve")
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
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reject_reason_required")
    db = database.get_db()
    try:
        doc = await reject_publish_queue_item(db, queue_id, _actor(user), reason=reason)
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
        metadata={"reason": reason},
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


@router.get("/runtime-requirements/explain")
async def registry_runtime_requirements_explain(
    user: dict = Depends(require_admin),
    client_id: str = Query(..., min_length=1),
    property_id: str = Query(..., min_length=1),
):
    """
    Admin/dev explain mode for runtime requirement inclusion + dedupe decisions.
    Never exposed on client routes.
    """
    _ = user
    db = database.get_db()
    out = await explain_runtime_requirement_rows_for_property(
        db,
        client_id=client_id,
        property_id=property_id,
    )
    return out
