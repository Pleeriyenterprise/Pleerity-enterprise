"""
A1 — Tenant-level obligation classification (read-only).

Launch authority: LAUNCH_AUTHORITY_TRACKER.md § A1; RUNBOOK §12.7.

Usage (from backend/, with MONGO_URL + DB_NAME set):

  python -m scripts.a1_obligation_tenant_classification --discover-affected --limit 5
  python -m scripts.a1_obligation_tenant_classification --client-id CID --property-id PID
  python -m scripts.a1_obligation_tenant_classification --client-id CID --property-id PID --json

No writes, no provisioning, no sync.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _iso(val: Any) -> Optional[str]:
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A1 obligation tenant classification (read-only).")
    p.add_argument("--client-id", default=None, help="Client ID (CID)")
    p.add_argument("--property-id", default=None, help="Property ID (PID)")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    p.add_argument(
        "--discover-affected",
        action="store_true",
        help="Find staging candidates (missing reqs, stuck onboarding, visibility mismatch)",
    )
    p.add_argument("--limit", type=int, default=5, help="Max candidates for --discover-affected")
    return p.parse_args(argv)


def _failure_characterization(
    *,
    classification: str,
    onboarding_status: Optional[str],
    provisioning_failed: bool,
    raw_count: int,
    included_count: int,
    top_exclusions: List[Tuple[str, int]],
    published_entry_count: Optional[int],
    queue_pending: int,
    req_ts_spread_seconds: Optional[float],
) -> Dict[str, Any]:
    tags: List[str] = []
    primary = "unknown"

    onb = (onboarding_status or "").upper()
    if onb in ("INTAKE_PENDING", "PROVISIONING") or provisioning_failed:
        tags.append("timing_order_dependent")
        primary = "timing_order_dependent"
    if classification == "A-only" and onb == "PROVISIONED" and raw_count == 0:
        tags.append("deterministic")
        primary = "deterministic"
    if classification == "B-only":
        tags.append("registry_publish_related")
        if any(r[0] in ("not_in_planner_membership", "draft_or_unpublished_materialization") for r in top_exclusions):
            tags.append("migration_related")
        primary = "registry_publish_related"
    if classification == "A+B":
        tags.append("deterministic")
        tags.append("registry_publish_related")
        primary = "registry_publish_related"
    if published_entry_count == 0:
        tags.append("registry_publish_related")
    if queue_pending > 0 and classification == "Neither":
        tags.append("scheduler_dependent")
        if primary == "unknown":
            primary = "scheduler_dependent"
    if req_ts_spread_seconds is not None and req_ts_spread_seconds > 86400:
        tags.append("timing_order_dependent")

    tags = list(dict.fromkeys(tags))
    return {
        "primary_hypothesis": primary,
        "tags": tags,
        "notes": (
            "Heuristic from single-point read; re-run after provision/sync to detect intermittent/self-healing."
        ),
    }


def _next_units(classification: str, *, raw_count: int, included_count: int) -> List[str]:
    if classification == "A-only":
        return ["A2"]
    if classification == "B-only":
        units = ["B1"]
        if raw_count > 0 and included_count == 0:
            units.append("B2")
        return units
    if classification == "A+B":
        return ["A2", "B1", "B2"]
    if classification == "Neither":
        return ["C1"]
    return []


async def _published_registry_meta(db) -> Dict[str, Any]:
    active = await db.compliance_requirement_registry_published.find_one({}, {"_id": 0}) or {}
    hist = (
        await db.compliance_requirement_registry_published_history.find({}, {"_id": 0})
        .sort("published_line_version", -1)
        .limit(1)
        .to_list(1)
    )
    from services.compliance_registry_publish_service import fetch_active_published_registry_entries

    entries = await fetch_active_published_registry_entries(db)
    entry_count = len(entries) if isinstance(entries, dict) else 0
    return {
        "active_published_updated_at": _iso(active.get("updated_at")),
        "active_published_line_version": active.get("published_line_version"),
        "last_history_published_at": _iso(hist[0].get("published_at")) if hist else None,
        "last_history_published_line_version": hist[0].get("published_line_version") if hist else None,
        "active_published_entry_count": entry_count,
    }


async def _run(client_id: str, property_id: str) -> Dict[str, Any]:
    from database import database
    from services.requirement_client_runtime_surface import explain_runtime_requirement_rows_for_property

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    if not client:
        raise SystemExit(f"Client not found: {client_id}")

    prop = await db.properties.find_one(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    )
    if not prop:
        raise SystemExit(f"Property not found: {property_id} for client {client_id}")

    properties_count = await db.properties.count_documents({"client_id": client_id})
    raw_count = await db.requirements.count_documents(
        {"client_id": client_id, "property_id": property_id}
    )

    job = await db.provisioning_jobs.find_one(
        {"client_id": client_id},
        sort=[("updated_at", -1)],
    )
    job_status = None
    job_doc: Dict[str, Any] = {}
    if job:
        job_doc = dict(job)
        job_status = job.get("status") or job.get("state")

    explain = await explain_runtime_requirement_rows_for_property(
        db, client_id=client_id, property_id=property_id
    )
    included_count = int(explain.get("included_count") or 0)
    explain_raw = int(explain.get("raw_count") or 0)

    exclusion_reasons: Counter[str] = Counter()
    excluded_rows: List[Dict[str, Any]] = []
    included_rows: List[Dict[str, Any]] = []
    for row in explain.get("rows") or []:
        if row.get("included"):
            included_rows.append(row)
        else:
            reason = str(row.get("exclusion_reason") or "unknown").strip()
            exclusion_reasons[reason] += 1
            excluded_rows.append(row)

    requirements = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {
            "_id": 0,
            "requirement_id": 1,
            "requirement_type": 1,
            "requirement_code": 1,
            "status": 1,
            "applicability": 1,
            "requirement_generation_source": 1,
            "client_surface_visible": 1,
            "legacy_requirement_state": 1,
            "legacy_readonly_visible": 1,
            "created_at": 1,
            "updated_at": 1,
        },
    ).to_list(500)

    generation_sources: Counter[str] = Counter()
    created_times: List[datetime] = []
    for s in requirements:
        gs = str(s.get("requirement_generation_source") or "missing").strip()
        generation_sources[gs] += 1
        for k in ("created_at", "updated_at"):
            v = s.get(k)
            if isinstance(v, datetime):
                created_times.append(v)
            elif v:
                try:
                    created_times.append(datetime.fromisoformat(str(v).replace("Z", "+00:00")))
                except Exception:
                    pass

    req_ts_spread: Optional[float] = None
    if len(created_times) >= 2:
        req_ts_spread = (max(created_times) - min(created_times)).total_seconds()

    onboarding_status = client.get("onboarding_status")
    provisioning_failed = (
        str(onboarding_status or "").upper() == "FAILED"
        or str(job_status or "").upper() == "FAILED"
    )

    classification = _classify(
        raw_count=raw_count,
        included_count=included_count,
        onboarding_status=onboarding_status,
        provisioning_status=client.get("provisioning_status"),
        provisioning_failed=provisioning_failed,
    )

    pub_meta = await _published_registry_meta(db)

    queue_rows = await db.compliance_recalc_queue.find(
        {"property_id": property_id},
        {"_id": 0},
    ).sort("updated_at", -1).limit(5).to_list(5)

    queue_pending = sum(1 for q in queue_rows if str(q.get("status") or "").upper() == "PENDING")

    job_runs = await db.job_runs.find(
        {"job_name": "compliance_recalc_worker"},
        {"_id": 0, "job_name": 1, "status": 1, "started_at": 1, "finished_at": 1},
    ).sort("started_at", -1).limit(3).to_list(3)

    characterization = _failure_characterization(
        classification=classification,
        onboarding_status=onboarding_status,
        provisioning_failed=provisioning_failed,
        raw_count=raw_count,
        included_count=included_count,
        top_exclusions=exclusion_reasons.most_common(10),
        published_entry_count=pub_meta.get("active_published_entry_count"),
        queue_pending=queue_pending,
        req_ts_spread_seconds=req_ts_spread,
    )

    first_divergence = _first_divergence_point(
        classification=classification,
        onboarding_status=onboarding_status,
        raw_count=raw_count,
        included_count=included_count,
        top_exclusions=exclusion_reasons.most_common(3),
    )

    return {
        "a1_unit": "A1",
        "run_at_utc": run_at,
        "environment": {
            "ENVIRONMENT": os.getenv("ENVIRONMENT"),
            "DB_NAME": os.getenv("DB_NAME"),
            "has_mongo_url": bool(os.getenv("MONGO_URL")),
        },
        "classification": classification,
        "first_divergence_point": first_divergence,
        "failure_characterization": characterization,
        "client_id": client_id,
        "property_id": property_id,
        "client": {
            "onboarding_status": onboarding_status,
            "provisioning_status": client.get("provisioning_status"),
            "subscription_status": client.get("subscription_status"),
            "provisioning_started_at": _iso(client.get("provisioning_started_at")),
            "provisioning_completed_at": _iso(client.get("provisioning_completed_at")),
            "portal_user_created_at": _iso(client.get("portal_user_created_at")),
            "created_at": _iso(client.get("created_at")),
            "updated_at": _iso(client.get("updated_at")),
            "last_provisioning_error": client.get("last_provisioning_error"),
        },
        "property": {
            "property_id": property_id,
            "jurisdiction": prop.get("jurisdiction"),
            "property_type": prop.get("property_type"),
            "is_hmo": prop.get("is_hmo"),
            "created_at": _iso(prop.get("created_at")),
            "updated_at": _iso(prop.get("updated_at")),
        },
        "provisioning_job_latest": {
            k: _iso(v) if "at" in k or k.endswith("_at") else v
            for k, v in job_doc.items()
            if k in (
                "status",
                "state",
                "created_at",
                "updated_at",
                "started_at",
                "completed_at",
                "error",
                "last_error",
            )
        }
        if job_doc
        else None,
        "properties_count": properties_count,
        "counts": {
            "raw_count_mongo": raw_count,
            "raw_count_explain": explain_raw,
            "included_count": included_count,
            "excluded_count": max(0, explain_raw - included_count),
        },
        "top_exclusion_reasons": exclusion_reasons.most_common(20),
        "requirement_generation_source_counts": dict(generation_sources),
        "requirements_sample": requirements[:25],
        "requirements_timestamp_spread_seconds": req_ts_spread,
        "explain_summary": {
            "property_jurisdiction": explain.get("property_jurisdiction"),
            "jurisdiction_source": explain.get("jurisdiction_source"),
        },
        "explain_excluded_rows": excluded_rows,
        "explain_included_rows": included_rows,
        "published_registry": pub_meta,
        "compliance_recalc_queue_latest": [
            {k: _iso(v) if "at" in k else v for k, v in q.items()}
            for q in queue_rows
        ],
        "job_runs_compliance_recalc_worker_latest": [
            {k: _iso(v) if "at" in k else v for k, v in r.items()}
            for r in job_runs
        ],
        "next_units_unlocked": _next_units(
            classification,
            raw_count=raw_count,
            included_count=included_count,
        ),
    }


def _first_divergence_point(
    *,
    classification: str,
    onboarding_status: Optional[str],
    raw_count: int,
    included_count: int,
    top_exclusions: List[Tuple[str, int]],
) -> str:
    onb = (onboarding_status or "").upper()
    if raw_count == 0 and onb != "PROVISIONED":
        return "A: provisioning/onboarding incomplete before requirement materialisation"
    if raw_count == 0 and onb == "PROVISIONED":
        return "A: PROVISIONED but zero requirement rows (materialisation did not persist or wrong property)"
    if raw_count > 0 and included_count == 0:
        top = top_exclusions[0][0] if top_exclusions else "published_overlay_or_runtime_gate"
        return f"B: {raw_count} Mongo rows but 0 client-runtime rows (primary exclusion: {top})"
    if raw_count > 0 and included_count < raw_count:
        return f"B: partial visibility suppression ({included_count}/{raw_count} included)"
    if raw_count > 0 and included_count == raw_count:
        return "Neither at obligation layer: materialisation + client filter pass; investigate queue/fanout (C1+)"
    return "Unknown — re-run explain"


def _classify(
    *,
    raw_count: int,
    included_count: int,
    onboarding_status: Optional[str],
    provisioning_failed: bool,
    provisioning_status: Optional[str] = None,
) -> str:
    _ = provisioning_status
    onb = (onboarding_status or "").strip().upper()
    provisioned = onb == "PROVISIONED"
    has_raw = raw_count > 0
    has_included = included_count > 0

    if not has_raw and (not provisioned or provisioning_failed):
        return "A-only"
    if has_raw and included_count == 0:
        return "B-only"
    if not has_raw and provisioned:
        return "A-only"
    if has_raw and has_included and included_count < raw_count:
        return "A+B"
    if has_raw and has_included and included_count == raw_count:
        return "Neither"
    if not has_raw:
        return "A-only"
    return "A+B"


async def _discover_affected(limit: int) -> Dict[str, Any]:
    from database import database
    from services.requirement_client_runtime_surface import explain_runtime_requirement_rows_for_property

    db = database.get_db()
    candidates: List[Dict[str, Any]] = []

    # Stuck onboarding with properties (symptom: paid but no obligations path)
    stuck = await db.clients.find(
        {
            "onboarding_status": {"$in": ["INTAKE_PENDING", "PROVISIONING", "FAILED"]},
            "subscription_status": {"$in": ["ACTIVE", "TRIALING", "active", "trialing"]},
        },
        {"_id": 0, "client_id": 1, "onboarding_status": 1, "email": 1},
    ).limit(20).to_list(20)

    for c in stuck:
        cid = c["client_id"]
        prop = await db.properties.find_one({"client_id": cid}, {"_id": 0, "property_id": 1})
        if not prop:
            continue
        pid = prop["property_id"]
        rc = await db.requirements.count_documents({"client_id": cid, "property_id": pid})
        candidates.append(
            {
                "client_id": cid,
                "property_id": pid,
                "score": 100,
                "reason": f"stuck_onboarding_{c.get('onboarding_status')}_req_count_{rc}",
                "onboarding_status": c.get("onboarding_status"),
                "raw_count": rc,
            }
        )

    # PROVISIONED but zero requirements on first property
    prov_zero = await db.clients.find(
        {"onboarding_status": "PROVISIONED"},
        {"_id": 0, "client_id": 1, "onboarding_status": 1},
    ).limit(40).to_list(40)

    for c in prov_zero:
        cid = c["client_id"]
        props = await db.properties.find({"client_id": cid}, {"_id": 0, "property_id": 1}).limit(3).to_list(3)
        for p in props:
            pid = p["property_id"]
            rc = await db.requirements.count_documents({"client_id": cid, "property_id": pid})
            if rc == 0:
                candidates.append(
                    {
                        "client_id": cid,
                        "property_id": pid,
                        "score": 90,
                        "reason": "provisioned_zero_requirements",
                        "onboarding_status": "PROVISIONED",
                        "raw_count": 0,
                    }
                )

    # Visibility mismatch: raw > 0, run explain (cap expensive scans)
    seen = {(x["client_id"], x["property_id"]) for x in candidates}
    rich_props = await db.requirements.aggregate(
        [
            {"$group": {"_id": {"c": "$client_id", "p": "$property_id"}, "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": 3}}},
            {"$sort": {"n": -1}},
            {"$limit": 25},
        ]
    ).to_list(25)

    for row in rich_props:
        cid = row["_id"]["c"]
        pid = row["_id"]["p"]
        if (cid, pid) in seen:
            continue
        explain = await explain_runtime_requirement_rows_for_property(db, client_id=cid, property_id=pid)
        raw = int(explain.get("raw_count") or 0)
        inc = int(explain.get("included_count") or 0)
        if raw > 0 and inc < raw:
            candidates.append(
                {
                    "client_id": cid,
                    "property_id": pid,
                    "score": 80 + (raw - inc),
                    "reason": f"visibility_gap_raw_{raw}_included_{inc}",
                    "onboarding_status": None,
                    "raw_count": raw,
                    "included_count": inc,
                }
            )
            seen.add((cid, pid))

    candidates.sort(key=lambda x: -int(x.get("score") or 0))
    return {
        "discovered_at_utc": datetime.now(timezone.utc).isoformat(),
        "DB_NAME": os.getenv("DB_NAME"),
        "candidate_count": len(candidates),
        "candidates": candidates[:limit],
    }


async def main(argv: Optional[List[str]] = None) -> None:
    from database import database

    await database.connect()
    args = _parse_args(argv)
    if args.discover_affected:
        out = await _discover_affected(args.limit)
        print(json.dumps(out, indent=2, default=str))
        return
    if not args.client_id or not args.property_id:
        raise SystemExit("Provide --client-id and --property-id, or use --discover-affected")

    out = await _run(args.client_id.strip(), args.property_id.strip())
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
