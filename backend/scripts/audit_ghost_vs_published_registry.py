"""
Read-only: classify ghost-visible requirement rows vs active published registry.

Expects ``audit_ghost_visible.json`` from ``run_published_registry_audit_once.py``.
Does not apply migrations.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import database  # noqa: E402
from services.compliance_registry_publish_service import fetch_active_published_registry_entries  # noqa: E402
from services.compliance_requirement_registry import (  # noqa: E402
    published_registry_entry_eligible_for_runtime,
    resolve_published_entry_for_requirement,
)
from services.compliance_registry_admin_service import draft_applies_to_portfolio_label, plan_types_for_draft_canonical  # noqa: E402
from services.compliance_rules_registry import portfolio_jurisdiction_label  # noqa: E402
from services.requirement_code_registry import normalize_requirement_code  # noqa: E402
from services.requirement_client_runtime_surface import (  # noqa: E402
    filter_requirement_rows_for_client_runtime_surfaces,
    project_requirement_row_client_runtime,
    client_portal_surface_visible_row,
)

# Catalog-only / operational extras that are not part of the published client obligation model.
LEGACY_CATALOG_ONLY_TYPES: Set[str] = frozenset(
    {
        "emergency_lighting",
        "fire_extinguisher",
        "communal_cleaning",
        "communal_fire_doors",
    }
)

BUCKET_CORRECTLY_DEPRECATED = "1_correctly_deprecated_legacy_not_client_facing"
BUCKET_MISSING_PUBLISH_ABSENT = "2a_missing_no_published_row_for_type"
BUCKET_MISSING_PUBLISH_BLOCKED = "2b_published_row_exists_but_not_activatable_for_property"
BUCKET_MAP_CANONICAL = "3_should_map_to_existing_published_canonical"
BUCKET_READONLY_EVIDENCE = "4_should_remain_readonly_legacy_evidence"
BUCKET_SAFE_HIDE = "5_safe_to_hide"


def _norm_type(row: Dict[str, Any]) -> str:
    return str(row.get("requirement_type") or row.get("requirement_code") or "").strip().lower()


def _entry_canonical_upper(entry: Dict[str, Any]) -> str:
    return str(entry.get("canonical_code") or "").strip().upper()


def _snapshot_types_for_entry(entry: Dict[str, Any]) -> Set[str]:
    cc = _entry_canonical_upper(entry)
    if not cc:
        return set()
    return {str(x).strip().lower() for x in plan_types_for_draft_canonical(cc)}


def _type_appears_in_any_entry(entries: Dict[str, Any], rt_lower: str) -> bool:
    for ent in entries.values():
        if not isinstance(ent, dict):
            continue
        if rt_lower in _snapshot_types_for_entry(ent):
            return True
    return False


def _type_matches_eligible_entry_for_portfolio(
    entries: Dict[str, Any],
    rt_lower: str,
    portfolio_label: str,
) -> bool:
    for ent in entries.values():
        if not isinstance(ent, dict):
            continue
        if not published_registry_entry_eligible_for_runtime(ent):
            continue
        if rt_lower not in _snapshot_types_for_entry(ent):
            continue
        if not draft_applies_to_portfolio_label(ent, portfolio_label):
            continue
        return True
    return False


def _classify_ghost_row(
    *,
    row: Dict[str, Any],
    property_doc: Dict[str, Any],
    client_doc: Dict[str, Any],
    published: Optional[Dict[str, Any]],
    doc_count: int,
) -> Tuple[str, str]:
    """
    Returns (bucket, detail_reason).
    """
    rt = _norm_type(row)
    canon = normalize_requirement_code(rt) or None
    plabel = portfolio_jurisdiction_label(property_doc, client_doc or {})

    if doc_count > 0 or bool(row.get("evidence_doc_id")) or bool(str(row.get("document_id") or "").strip()):
        return BUCKET_READONLY_EVIDENCE, "linked_or_inline_evidence"

    if rt in LEGACY_CATALOG_ONLY_TYPES:
        return BUCKET_CORRECTLY_DEPRECATED, "catalog_operational_extra_not_published_model"

    if not isinstance(published, dict) or not published:
        return BUCKET_MISSING_PUBLISH_ABSENT, "no_active_published_snapshot"

    pub_raw = resolve_published_entry_for_requirement(
        published_registry_entries=published,
        requirement_type=rt,
        portfolio_label=str(plabel or ""),
        property_doc=property_doc,
        enforce_conditions=True,
    )
    pub_canon = None
    if canon:
        pub_canon = resolve_published_entry_for_requirement(
            published_registry_entries=published,
            requirement_type=canon,
            portfolio_label=str(plabel or ""),
            property_doc=property_doc,
            enforce_conditions=True,
        )
    if pub_raw:
        return BUCKET_SAFE_HIDE, "unexpected_ghost_resolves_published_strict_recheck_data"

    if canon and pub_canon:
        return BUCKET_MAP_CANONICAL, "published_resolves_on_canonical_not_raw_slug"

    pub_raw_relaxed = resolve_published_entry_for_requirement(
        published_registry_entries=published,
        requirement_type=rt,
        portfolio_label=str(plabel or ""),
        property_doc=property_doc,
        enforce_conditions=False,
    )
    pub_canon_relaxed = None
    if canon:
        pub_canon_relaxed = resolve_published_entry_for_requirement(
            published_registry_entries=published,
            requirement_type=canon,
            portfolio_label=str(plabel or ""),
            property_doc=property_doc,
            enforce_conditions=False,
        )
    if pub_raw_relaxed or pub_canon_relaxed:
        return BUCKET_MISSING_PUBLISH_BLOCKED, "published_row_exists_but_conditions_or_overlay_block"

    if not _type_appears_in_any_entry(published, rt):
        return BUCKET_MISSING_PUBLISH_ABSENT, "type_absent_from_active_published_snapshot_keys"

    if not _type_matches_eligible_entry_for_portfolio(published, rt, str(plabel or "")):
        return BUCKET_MISSING_PUBLISH_ABSENT, "type_in_snapshot_but_no_eligible_row_for_portfolio_label"

    return BUCKET_CORRECTLY_DEPRECATED, "published_registry_has_type_but_unresolvable_for_property"


async def _doc_count_for_requirement(db, client_id: str, requirement_id: str) -> int:
    return int(
        await db.documents.count_documents(
            {"client_id": client_id, "$or": [{"requirement_id": requirement_id}, {"requirement_ids": requirement_id}]}
        )
    )


async def _portfolio_type_visibility_after(db) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    """
    Union of types visible before vs after runtime filter, across all requirements.

    Returns (before_canon_keys, after_canon_keys, before_raw_types, after_raw_types).
    """
    raw_reqs = await db.requirements.find({}, {"_id": 0}).to_list(100_000)
    if not raw_reqs:
        return set(), set(), set(), set()
    clients = await db.clients.find({}, {"_id": 0}).to_list(50_000)
    client_by_id = {c["client_id"]: c for c in clients if c.get("client_id")}
    props = await db.properties.find({}, {"_id": 0}).to_list(100_000)
    props_by_client: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in props:
        cid = str(p.get("client_id") or "")
        if cid:
            props_by_client[cid].append(p)

    def _code_key(r: Dict[str, Any]) -> str:
        c = normalize_requirement_code(str(r.get("requirement_type") or r.get("requirement_code") or ""))
        return c or _norm_type(r) or "unknown"

    before_codes: Set[str] = set()
    after_codes: Set[str] = set()
    before_raw: Set[str] = set()
    after_raw: Set[str] = set()
    by_client: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in raw_reqs:
        cid = str(r.get("client_id") or "")
        if cid:
            by_client[cid].append(r)

    for cid, reqs in by_client.items():
        client_doc = client_by_id.get(cid) or {}
        plist = props_by_client.get(cid, [])
        before_visible = [r for r in reqs if r.get("client_surface_visible") is not False]
        for r in before_visible:
            pr = project_requirement_row_client_runtime(r)
            if client_portal_surface_visible_row(pr):
                before_codes.add(_code_key(r))
                before_raw.add(_norm_type(r))
        filtered = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=cid,
            requirements=reqs,
            client_doc=client_doc,
            properties=plist,
        )
        for r in filtered:
            pr = project_requirement_row_client_runtime(r)
            if client_portal_surface_visible_row(pr):
                after_codes.add(_code_key(r))
                after_raw.add(_norm_type(r))
    return before_codes, after_codes, before_raw, after_raw


async def _main() -> int:
    await database.connect()
    try:
        db = database.get_db()
        script_dir = Path(__file__).resolve().parent
        ghost_path = script_dir / "audit_ghost_visible.json"
        if not ghost_path.is_file():
            print(json.dumps({"error": f"missing {ghost_path.name}; run run_published_registry_audit_once.py first"}))
            return 2
        ghosts: List[Dict[str, Any]] = json.loads(ghost_path.read_text(encoding="utf-8"))
        published = await fetch_active_published_registry_entries(db)
        entry_count = len(published) if isinstance(published, dict) else 0

        rid_keys = {(g["client_id"], g["requirement_id"]) for g in ghosts if g.get("client_id") and g.get("requirement_id")}
        req_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        client_ids: List[str] = []
        if rid_keys:
            client_ids = sorted({k[0] for k in rid_keys})
            cursor = db.requirements.find({"client_id": {"$in": client_ids}}, {"_id": 0})
            async for doc in cursor:
                k = (str(doc.get("client_id") or ""), str(doc.get("requirement_id") or ""))
                if k in rid_keys:
                    req_map[k] = doc

        prop_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        if client_ids:
            async for p in db.properties.find({"client_id": {"$in": client_ids}}, {"_id": 0}):
                prop_map[(str(p.get("client_id") or ""), str(p.get("property_id") or ""))] = p

        client_docs: Dict[str, Dict[str, Any]] = {}
        if client_ids:
            async for c in db.clients.find({"client_id": {"$in": client_ids}}, {"_id": 0}):
                if c.get("client_id"):
                    client_docs[str(c["client_id"])] = c

        rows_out: List[Dict[str, Any]] = []
        bucket_counts = Counter()
        by_type_canon: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
        by_jurisdiction = Counter()
        by_client = Counter()
        by_property = Counter()

        for g in ghosts:
            cid = str(g.get("client_id") or "")
            rid = str(g.get("requirement_id") or "")
            pid = str(g.get("property_id") or "")
            row = req_map.get((cid, rid), {})
            prop = prop_map.get((cid, pid), {})
            cdoc = client_docs.get(cid, {})
            rt = str(g.get("requirement_type") or _norm_type(row) or "").strip().lower()
            canon = g.get("canonical_code")
            if canon is None and row:
                canon = normalize_requirement_code(rt)
            doc_count = await _doc_count_for_requirement(db, cid, rid) if cid and rid else 0
            plabel = portfolio_jurisdiction_label(prop, cdoc) if prop else str((cdoc or {}).get("default_jurisdiction") or "unknown")
            bucket, reason = _classify_ghost_row(row=row or g, property_doc=prop, client_doc=cdoc, published=published or {}, doc_count=doc_count)
            bucket_counts[bucket] += 1
            by_jurisdiction[str(plabel or "unknown")] += 1
            by_client[cid] += 1
            by_property[f"{cid}|{pid}"] += 1
            key = (rt, str(canon) if canon else None)
            agg = by_type_canon.setdefault(
                key,
                {"requirement_type": rt, "canonical_code": canon, "count": 0, "buckets": Counter()},
            )
            agg["count"] += 1
            agg["buckets"][bucket] += 1
            rows_out.append(
                {
                    "requirement_id": rid,
                    "client_id": cid,
                    "property_id": pid,
                    "portfolio_jurisdiction": str(plabel or ""),
                    "requirement_type": rt,
                    "canonical_code": canon,
                    "bucket": bucket,
                    "detail": reason,
                    "document_link_count": doc_count,
                }
            )

        before_codes, after_codes, before_raw, after_raw = await _portfolio_type_visibility_after(db)
        disappear_entirely_canon = sorted(before_codes - after_codes)
        disappear_entirely_raw = sorted(before_raw - after_raw)

        publish_first = (
            bucket_counts.get(BUCKET_MISSING_PUBLISH_ABSENT, 0)
            + bucket_counts.get(BUCKET_MISSING_PUBLISH_BLOCKED, 0)
            + bucket_counts.get(BUCKET_MAP_CANONICAL, 0)
        )
        safeish = bucket_counts.get(BUCKET_SAFE_HIDE, 0) + bucket_counts.get(BUCKET_CORRECTLY_DEPRECATED, 0)
        recommendation = (
            "publish_missing_or_fix_registry_overlays_first"
            if publish_first > safeish
            else "likely_safe_to_apply_after_review_readonly_evidence_rows"
        )

        report = {
            "published_registry_entry_count": entry_count,
            "ghost_row_count": len(ghosts),
            "bucket_counts": dict(bucket_counts),
            "by_jurisdiction": dict(by_jurisdiction),
            "by_client_id": dict(by_client),
            "by_client_property_key": dict(by_property),
            "grouped_by_requirement_type_and_canonical": sorted(
                [
                    {
                        "requirement_type": v["requirement_type"],
                        "canonical_code": v["canonical_code"],
                        "count": v["count"],
                        "buckets": dict(v["buckets"]),
                    }
                    for v in by_type_canon.values()
                ],
                key=lambda x: -x["count"],
            ),
            "canonical_keys_visible_before_not_after_anywhere": disappear_entirely_canon,
            "requirement_types_visible_before_not_after_anywhere": disappear_entirely_raw,
            "recommendation": recommendation,
            "recommendation_notes": {
                "publish_or_map_first_rows": int(publish_first),
                "deprecated_or_safe_hide_rows": int(safeish),
                "readonly_evidence_rows": int(bucket_counts.get(BUCKET_READONLY_EVIDENCE, 0)),
                "missing_publish_absent_2a": int(bucket_counts.get(BUCKET_MISSING_PUBLISH_ABSENT, 0)),
                "missing_publish_blocked_2b": int(bucket_counts.get(BUCKET_MISSING_PUBLISH_BLOCKED, 0)),
                "map_canonical_3": int(bucket_counts.get(BUCKET_MAP_CANONICAL, 0)),
            },
            "rollup_user_categories": {
                "1_correctly_deprecated_legacy": int(bucket_counts.get(BUCKET_CORRECTLY_DEPRECATED, 0)),
                "2_missing_or_unactivatable_published": int(
                    bucket_counts.get(BUCKET_MISSING_PUBLISH_ABSENT, 0) + bucket_counts.get(BUCKET_MISSING_PUBLISH_BLOCKED, 0)
                ),
                "3_should_map_to_existing_published_canonical": int(bucket_counts.get(BUCKET_MAP_CANONICAL, 0)),
                "4_readonly_legacy_evidence": int(bucket_counts.get(BUCKET_READONLY_EVIDENCE, 0)),
                "5_safe_to_hide": int(bucket_counts.get(BUCKET_SAFE_HIDE, 0)),
            },
            "rows": rows_out,
        }
        out_path = script_dir / "ghost_vs_published_report.json"
        out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"written": str(out_path), "ghost_row_count": len(ghosts)}, indent=2))
        return 0
    finally:
        await database.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
