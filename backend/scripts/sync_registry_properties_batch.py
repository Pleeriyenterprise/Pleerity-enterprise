"""
Batch sync properties after compliance registry publish/revert.

Usage (from backend/ with MONGO_URL + DB_NAME):
  python scripts/sync_registry_properties_batch.py --dry-run
  python scripts/sync_registry_properties_batch.py --apply

Optional filters:
  --client-id <client_id>       limit to one client
  --property-id <property_id>   limit to one property
  --max-properties 100          cap apply volume per run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient

from database import database
from services.compliance_registry_publish_service import fetch_active_published_registry_entries
from services.compliance_requirement_registry import build_requirement_plan_for_property
from services.compliance_requirement_registry import resolve_published_entry_for_requirement
from services.compliance_rules_registry import portfolio_jurisdiction_label
from services.requirement_materialization_service import materialize_requirements_for_property


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    s = str(value or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.min


async def _discover_candidates(
    db,
    *,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    entries = await fetch_active_published_registry_entries(db) or {}
    active = await db.compliance_requirement_registry_published.find_one(
        {"singleton_key": "active_registry"},
        {"_id": 0, "updated_at": 1},
    )
    snapshot_updated_at = _dt((active or {}).get("updated_at"))

    prop_q: Dict[str, Any] = {}
    if client_id:
        prop_q["client_id"] = client_id
    if property_id:
        prop_q["property_id"] = property_id

    props = await db.properties.find(
        prop_q,
        {"_id": 0, "property_id": 1, "client_id": 1, "jurisdiction": 1, "has_gas_supply": 1, "is_hmo": 1},
    ).to_list(50000)
    clients = await db.clients.find({}, {"_id": 0, "client_id": 1, "default_jurisdiction": 1}).to_list(50000)

    client_by_id = {str(c.get("client_id")): c for c in clients if c.get("client_id")}
    prop_by_id = {str(p.get("property_id")): p for p in props if p.get("property_id")}
    prop_ids = list(prop_by_id.keys())

    req_q: Dict[str, Any] = {"property_id": {"$in": prop_ids}} if prop_ids else {"property_id": {"$in": []}}
    if client_id:
        req_q["client_id"] = client_id
    reqs = await db.requirements.find(
        req_q,
        {
            "_id": 0,
            "requirement_id": 1,
            "property_id": 1,
            "client_id": 1,
            "requirement_type": 1,
            "requirement_code": 1,
            "applicability": 1,
            "not_required_reason": 1,
            "updated_at": 1,
            "registry_metadata": 1,
        },
    ).to_list(200000)

    by_property: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in reqs:
        pid = str(r.get("property_id") or "")
        if pid:
            by_property[pid].append(r)

    candidates: List[Dict[str, Any]] = []
    for pid, rows in by_property.items():
        prop = prop_by_id.get(pid)
        if not prop:
            continue
        cid = str(prop.get("client_id") or "")
        cdoc = client_by_id.get(cid, {})
        portfolio = portfolio_jurisdiction_label(prop, cdoc or {})
        plan_items = build_requirement_plan_for_property(
            prop,
            cdoc or {},
            published_registry_entries=entries,
        )
        planned_types = {str(x.requirement_type or "").strip().lower() for x in plan_items if x and x.requirement_type}

        stale_requirement_ids: List[str] = []
        for r in rows:
            rt = str(r.get("requirement_type") or r.get("requirement_code") or "")
            if not rt:
                continue
            # User-curated NOT_REQUIRED decisions are preserved by materialization and should
            # not be treated as stale publish metadata drift.
            if str(r.get("applicability") or "").strip().upper() == "NOT_REQUIRED" and r.get("not_required_reason"):
                continue
            # Only evaluate rows currently emitted by the planner for this property.
            # Legacy/obsolete rows are handled by materialize reconcile, not by stale-published detection.
            if rt.strip().lower() not in planned_types:
                continue
            pe = resolve_published_entry_for_requirement(
                published_registry_entries=entries,
                requirement_type=rt,
                portfolio_label=portfolio,
                property_doc=prop,
                # materialisation eligibility should remain strict here
                enforce_conditions=True,
            )
            if not pe:
                continue
            md = r.get("registry_metadata") if isinstance(r.get("registry_metadata"), dict) else {}
            has_published_marks = bool(md.get("action_links_published")) or bool(md.get("why_it_matters_short_published")) or bool(md.get("why_it_matters_long_published"))
            if _dt(r.get("updated_at")) < snapshot_updated_at and not has_published_marks:
                stale_requirement_ids.append(str(r.get("requirement_id") or ""))

        if stale_requirement_ids:
            candidates.append(
                {
                    "client_id": cid,
                    "property_id": pid,
                    "jurisdiction": prop.get("jurisdiction"),
                    "stale_count": len(stale_requirement_ids),
                    "stale_requirement_ids": stale_requirement_ids,
                }
            )

    candidates.sort(key=lambda x: (x["client_id"], x["property_id"]))
    return {
        "snapshot_updated_at": (active or {}).get("updated_at"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


async def _apply_candidates(candidates: List[Dict[str, Any]], *, max_properties: int) -> List[Dict[str, Any]]:
    applied: List[Dict[str, Any]] = []
    for idx, row in enumerate(candidates):
        if idx >= max_properties:
            break
        cid = str(row.get("client_id") or "")
        pid = str(row.get("property_id") or "")
        if not cid or not pid:
            continue
        try:
            result = await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
            applied.append(
                {
                    "client_id": cid,
                    "property_id": pid,
                    "stale_count_before": row.get("stale_count"),
                    "result": result,
                }
            )
        except Exception as exc:
            applied.append(
                {
                    "client_id": cid,
                    "property_id": pid,
                    "stale_count_before": row.get("stale_count"),
                    "error": str(exc),
                }
            )
    return applied


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--client-id", default="", help="Optional client_id filter")
    ap.add_argument("--property-id", default="", help="Optional property_id filter")
    ap.add_argument("--max-properties", type=int, default=500, help="Maximum properties to apply in one run")
    args = ap.parse_args()

    do_apply = bool(args.apply)
    if not args.dry_run and not do_apply:
        # Default to dry-run if neither switch provided.
        args.dry_run = True

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    await db.command("ping")
    # materialize_requirements_for_property uses database.get_db(); bind this process to the same handle.
    database.db = db

    discovered = await _discover_candidates(
        db,
        client_id=(args.client_id or "").strip() or None,
        property_id=(args.property_id or "").strip() or None,
    )

    out: Dict[str, Any] = {
        "mode": "apply" if do_apply else "dry_run",
        "db_name": db_name,
        "snapshot_updated_at": discovered.get("snapshot_updated_at"),
        "candidate_count": discovered.get("candidate_count"),
        "candidates": discovered.get("candidates"),
    }

    if do_apply:
        applied = await _apply_candidates(discovered.get("candidates") or [], max_properties=max(1, int(args.max_properties)))
        out["applied_count"] = len(applied)
        out["applied"] = applied

        # Post-apply verification.
        post = await _discover_candidates(
            db,
            client_id=(args.client_id or "").strip() or None,
            property_id=(args.property_id or "").strip() or None,
        )
        out["post_apply_candidate_count"] = post.get("candidate_count")
        out["post_apply_candidates"] = post.get("candidates")

    print(json.dumps(out, indent=2, default=str))
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
