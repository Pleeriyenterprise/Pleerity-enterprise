"""
Idempotent production baseline seed for system-owned content only.

Touches: legal pages, KB categories/articles, compliance registry drafts (+ initial
published snapshot when empty). Does not touch customer/operational collections.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from bson import ObjectId

from routes.knowledge_base import DEFAULT_CATEGORIES
from scripts.seed_kb_articles import (
    ARTICLES_COLLECTION,
    CATEGORIES_COLLECTION,
    EXAMPLE_ARTICLES,
    SCORING_COPY_REFRESH_SLUGS,
)
from services.compliance_registry_admin_service import (
    COLLECTION as REGISTRY_DRAFTS_COLLECTION,
    bundle_entries_to_drafts,
    load_baseline_bundle_from_disk,
    validate_registry_draft,
)
from services.compliance_registry_publish_service import (
    COLLECTION_PUBLISHED,
    COLLECTION_PUBLISHED_HISTORY,
    SINGLETON_KEY,
    _normalise_active_snapshot_entry,
    _snapshot_entries_from_drafts,
    append_published_history_record,
)
from services.legal_content_defaults import LEGAL_SLUGS, PROVENANCE, get_canonical
from services.legal_content_service import seed_canonical_content

BASELINE_KB_PROVENANCE = "production_baseline_v1"
BASELINE_REGISTRY_ACTIVATION_KIND = "baseline_seed_v1"
SYSTEM_ACTOR_EMAIL = "system@production-baseline-seed"
SYSTEM_ACTOR_USER_ID = "production_baseline_seed"

# Collections this module may write (for safety tests and audits).
ALLOWED_WRITE_COLLECTIONS: frozenset[str] = frozenset(
    {
        "legal_content",
        "legal_content_versions",
        "kb_articles",
        "kb_categories",
        "compliance_requirement_registry_drafts",
        "compliance_requirement_registry_published",
        "compliance_requirement_registry_published_history",
    }
)

# Representative operational collections — must never be written by this seed.
FORBIDDEN_TOUCH_COLLECTIONS: frozenset[str] = frozenset(
    {
        "clients",
        "portal_users",
        "documents",
        "message_logs",
        "subscriptions",
        "stripe_events",
        "leads",
        "audit_logs",
        "properties",
        "requirements",
        "payments",
        "intake_submissions",
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _actor() -> Dict[str, str]:
    return {"portal_user_id": SYSTEM_ACTOR_USER_ID, "email": SYSTEM_ACTOR_EMAIL}


def _is_system_managed_kb(doc: Optional[Dict[str, Any]]) -> bool:
    if not doc:
        return True
    provenance = str(doc.get("provenance") or "").strip()
    created_by = str(doc.get("created_by") or "").strip()
    return provenance == BASELINE_KB_PROVENANCE or created_by in (
        "seed_kb_articles",
        SYSTEM_ACTOR_USER_ID,
    )


async def _plan_kb_categories(db) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for cat in DEFAULT_CATEGORIES:
        cid = cat["id"]
        existing = await db[CATEGORIES_COLLECTION].find_one({"category_id": cid})
        if existing:
            actions.append({"collection": CATEGORIES_COLLECTION, "key": cid, "action": "skip", "reason": "exists"})
        else:
            actions.append({"collection": CATEGORIES_COLLECTION, "key": cid, "action": "create"})
    return actions


async def _plan_kb_articles(db) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for item in EXAMPLE_ARTICLES:
        slug = item["slug"]
        existing = await db[ARTICLES_COLLECTION].find_one({"slug": slug})
        if existing and slug in SCORING_COPY_REFRESH_SLUGS and _is_system_managed_kb(existing):
            actions.append(
                {
                    "collection": ARTICLES_COLLECTION,
                    "key": slug,
                    "action": "update",
                    "reason": "scoring_copy_refresh_system_managed",
                }
            )
        elif existing:
            actions.append(
                {
                    "collection": ARTICLES_COLLECTION,
                    "key": slug,
                    "action": "skip",
                    "reason": "custom_or_existing",
                }
            )
        else:
            actions.append({"collection": ARTICLES_COLLECTION, "key": slug, "action": "create"})
    return actions


async def _plan_legal(db, *, force: bool) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for slug in LEGAL_SLUGS:
        canonical = get_canonical(slug)
        if not canonical:
            actions.append({"collection": "legal_content", "key": slug, "action": "skip", "reason": "no_canonical"})
            continue
        existing = await db.legal_content.find_one({"slug": slug})
        if existing and not force:
            if existing.get("provenance") == PROVENANCE:
                actions.append(
                    {
                        "collection": "legal_content",
                        "key": slug,
                        "action": "skip",
                        "reason": "already_seeded",
                        "version": existing.get("version"),
                    }
                )
                continue
            if (existing.get("version") or 0) > 0 and (existing.get("content") or "").strip():
                actions.append(
                    {
                        "collection": "legal_content",
                        "key": slug,
                        "action": "skip",
                        "reason": "custom_content_present",
                        "version": existing.get("version"),
                    }
                )
                continue
        actions.append({"collection": "legal_content", "key": slug, "action": "seed"})
    return actions


async def _plan_registry(db, *, force: bool) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    bundle = load_baseline_bundle_from_disk()
    drafts, summary = bundle_entries_to_drafts(bundle, actor=_actor())
    actions: List[Dict[str, Any]] = []
    for doc in drafts:
        code = doc.get("canonical_code")
        sk = doc.get("scope_key")
        filt = {"canonical_code": code, "scope_key": sk}
        prior = await db[REGISTRY_DRAFTS_COLLECTION].find_one(filt, {"_id": 0, "entry_id": 1})
        if prior and not force:
            actions.append(
                {
                    "collection": REGISTRY_DRAFTS_COLLECTION,
                    "key": f"{code}|{sk}",
                    "action": "skip",
                    "reason": "exists",
                }
            )
            continue
        errs = validate_registry_draft(doc)
        if errs:
            actions.append(
                {
                    "collection": REGISTRY_DRAFTS_COLLECTION,
                    "key": f"{code}|{sk}",
                    "action": "skip",
                    "reason": "validation_failed",
                    "errors": errs[:3],
                }
            )
            continue
        action = "update" if prior and force else ("create" if not prior else "skip")
        if action == "skip":
            actions.append(
                {
                    "collection": REGISTRY_DRAFTS_COLLECTION,
                    "key": f"{code}|{sk}",
                    "action": "skip",
                    "reason": "exists",
                }
            )
        else:
            actions.append({"collection": REGISTRY_DRAFTS_COLLECTION, "key": f"{code}|{sk}", "action": action})

    prev = await db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0, "version": 1})
    prev_version = int((prev or {}).get("version") or 0)
    publish_action = "skip"
    publish_reason = "published_snapshot_exists"
    if prev_version == 0 and not (prev or {}).get("entries"):
        valid_drafts = []
        for doc in drafts:
            errs = validate_registry_draft(copy.deepcopy(doc))
            if not errs:
                valid_drafts.append(doc)
        if valid_drafts:
            publish_action = "create_initial_published"
            publish_reason = "empty_published_snapshot"
    actions.append(
        {
            "collection": COLLECTION_PUBLISHED,
            "key": SINGLETON_KEY,
            "action": publish_action,
            "reason": publish_reason,
            "draft_count": summary.get("drafts_built"),
        }
    )
    return actions, {"bundle_summary": summary, "import_bundle_version": bundle.get("import_bundle_version")}


async def plan_production_baseline_seed(
    db,
    *,
    force_legal: bool = False,
    force_registry: bool = False,
) -> Dict[str, Any]:
    """Read-only plan of seed operations."""
    kb_categories = await _plan_kb_categories(db)
    kb_articles = await _plan_kb_articles(db)
    legal = await _plan_legal(db, force=force_legal)
    registry_actions, registry_meta = await _plan_registry(db, force=force_registry)
    actions = kb_categories + kb_articles + legal + registry_actions
    counts = {"create": 0, "update": 0, "seed": 0, "skip": 0}
    for row in actions:
        act = row.get("action")
        if act in counts:
            counts[act] += 1
        elif act == "create_initial_published":
            counts["create"] += 1
    return {
        "dry_run": True,
        "actions": actions,
        "counts": counts,
        "allowed_write_collections": sorted(ALLOWED_WRITE_COLLECTIONS),
        "forbidden_touch_collections": sorted(FORBIDDEN_TOUCH_COLLECTIONS),
        "registry_meta": registry_meta,
        "legal_slugs": list(LEGAL_SLUGS),
        "kb_article_slugs": [a["slug"] for a in EXAMPLE_ARTICLES],
    }


async def _apply_kb_categories(db, now_iso: str) -> Dict[str, int]:
    created = 0
    skipped = 0
    for cat in DEFAULT_CATEGORIES:
        cid = cat["id"]
        existing = await db[CATEGORIES_COLLECTION].find_one({"category_id": cid})
        if existing:
            skipped += 1
            continue
        await db[CATEGORIES_COLLECTION].insert_one(
            {
                "category_id": cid,
                "name": cat["name"],
                "icon": cat["icon"],
                "order": cat["order"],
                "audience": cat.get("audience", "USER"),
                "description": None,
                "is_active": True,
                "article_count": 0,
                "created_at": now_iso,
            }
        )
        created += 1
    return {"created": created, "skipped": skipped}


async def _apply_kb_articles(db, now_iso: str) -> Dict[str, int]:
    created = 0
    skipped = 0
    updated = 0
    for item in EXAMPLE_ARTICLES:
        slug = item["slug"]
        existing = await db[ARTICLES_COLLECTION].find_one({"slug": slug})
        if existing and slug in SCORING_COPY_REFRESH_SLUGS and _is_system_managed_kb(existing):
            await db[ARTICLES_COLLECTION].update_one(
                {"slug": slug},
                {
                    "$set": {
                        "title": item["title"],
                        "excerpt": item["excerpt"],
                        "content": item["content"],
                        "tags": item.get("tags", []),
                        "summary": item["excerpt"][:500],
                        "meta_title": item["title"],
                        "meta_description": item["excerpt"],
                        "updated_at": now_iso,
                        "updated_by": SYSTEM_ACTOR_USER_ID,
                        "provenance": BASELINE_KB_PROVENANCE,
                    }
                },
            )
            updated += 1
            continue
        if existing:
            skipped += 1
            continue
        article_id = f"kb-{uuid.uuid4().hex[:12]}"
        doc = {
            "article_id": article_id,
            "title": item["title"],
            "slug": slug,
            "category_id": item["category_id"],
            "excerpt": item["excerpt"],
            "content": item["content"],
            "tags": item.get("tags", []),
            "status": "published",
            "audience": "USER",
            "version": "1.0",
            "summary": item["excerpt"][:500],
            "meta_title": item["title"],
            "meta_description": item["excerpt"],
            "view_count": 0,
            "is_active": True,
            "product_module": None,
            "related_feature_flags": [],
            "article_type": None,
            "release_version": None,
            "release_date": None,
            "changes": [],
            "affected_modules": [],
            "provenance": BASELINE_KB_PROVENANCE,
            "created_at": now_iso,
            "created_by": SYSTEM_ACTOR_USER_ID,
            "updated_at": now_iso,
            "updated_by": SYSTEM_ACTOR_USER_ID,
            "published_at": now_iso,
        }
        await db[ARTICLES_COLLECTION].insert_one(doc)
        created += 1
    return {"created": created, "updated": updated, "skipped": skipped}


async def _apply_registry_drafts(db, *, force: bool) -> Dict[str, Any]:
    bundle = load_baseline_bundle_from_disk()
    drafts, summary = bundle_entries_to_drafts(bundle, actor=_actor())
    inserted = 0
    updated = 0
    skipped = 0
    for doc in drafts:
        code = doc.get("canonical_code")
        sk = doc.get("scope_key")
        filt = {"canonical_code": code, "scope_key": sk}
        prior = await db[REGISTRY_DRAFTS_COLLECTION].find_one(filt, {"_id": 0, "entry_id": 1})
        if prior and not force:
            skipped += 1
            continue
        if prior and force:
            doc["entry_id"] = prior.get("entry_id") or doc.get("entry_id")
        errs = validate_registry_draft(doc)
        if errs:
            summary.setdefault("validation_failures", []).append(
                {"canonical_code": code, "scope_key": sk, "errors": errs}
            )
            continue
        if prior:
            await db[REGISTRY_DRAFTS_COLLECTION].update_one(
                filt, {"$set": {k: v for k, v in doc.items() if k != "_id"}}
            )
            updated += 1
        else:
            await db[REGISTRY_DRAFTS_COLLECTION].insert_one({**doc, "_id": ObjectId()})
            inserted += 1
    summary["inserted"] = inserted
    summary["updated"] = updated
    summary["skipped_existing"] = skipped
    return summary


async def _apply_initial_published_if_empty(db) -> Dict[str, Any]:
    prev = await db[COLLECTION_PUBLISHED].find_one(
        {"singleton_key": SINGLETON_KEY},
        {"_id": 0, "version": 1, "entries": 1},
    )
    prev_version = int((prev or {}).get("version") or 0)
    prev_entries = (prev or {}).get("entries") if isinstance((prev or {}).get("entries"), dict) else {}
    if prev_version > 0 or prev_entries:
        return {"action": "skip", "reason": "published_snapshot_exists", "version": prev_version}

    draft_docs = await db[REGISTRY_DRAFTS_COLLECTION].find({}, {"_id": 0}).to_list(5000)
    valid: List[Dict[str, Any]] = []
    for d in draft_docs:
        doc = copy.deepcopy(d)
        errs = validate_registry_draft(doc)
        if not errs:
            valid.append(doc)
    if not valid:
        return {"action": "skip", "reason": "no_valid_drafts"}

    entries_raw = _snapshot_entries_from_drafts(valid)
    entries = {k: _normalise_active_snapshot_entry(v) for k, v in entries_raw.items()}
    now = _iso(_now())
    actor = _actor()
    next_v = 1
    await db[COLLECTION_PUBLISHED].update_one(
        {"singleton_key": SINGLETON_KEY},
        {
            "$set": {
                "singleton_key": SINGLETON_KEY,
                "version": next_v,
                "entries": copy.deepcopy(entries),
                "updated_at": now,
                "last_queue_id": None,
                "last_published_by": actor,
                "last_activation_kind": BASELINE_REGISTRY_ACTIVATION_KIND,
                "reverted_from_published_line_version": None,
            }
        },
        upsert=True,
    )
    await append_published_history_record(
        db,
        published_line_version=next_v,
        entries=entries,
        recorded_at=now,
        last_queue_id=None,
        activated_by=actor,
        activation_kind=BASELINE_REGISTRY_ACTIVATION_KIND,
        reverted_from_published_line_version=None,
    )
    return {"action": "created_initial_published", "version": next_v, "entry_count": len(entries)}


async def run_production_baseline_seed(
    db,
    *,
    dry_run: bool = True,
    force_legal: bool = False,
    force_registry: bool = False,
) -> Dict[str, Any]:
    """Plan or apply baseline content seed."""
    plan = await plan_production_baseline_seed(db, force_legal=force_legal, force_registry=force_registry)
    if dry_run:
        plan["dry_run"] = True
        return plan

    now_iso = _iso(_now())
    kb_cat = await _apply_kb_categories(db, now_iso)
    kb_art = await _apply_kb_articles(db, now_iso)
    legal = await seed_canonical_content(
        db,
        actor_email=SYSTEM_ACTOR_EMAIL,
        actor_user_id=SYSTEM_ACTOR_USER_ID,
        force=force_legal,
    )
    registry = await _apply_registry_drafts(db, force=force_registry)
    published = await _apply_initial_published_if_empty(db)
    return {
        "dry_run": False,
        "kb_categories": kb_cat,
        "kb_articles": kb_art,
        "legal": legal,
        "registry_drafts": registry,
        "registry_published": published,
        "allowed_write_collections": sorted(ALLOWED_WRITE_COLLECTIONS),
    }
