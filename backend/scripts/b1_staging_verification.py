"""
B1 staging verification: governed triple materialise + replay + after artifacts.

Tenant-scoped only. No fleet rematerialise. No raw Mongo edits.

  python -m scripts.b1_staging_verification \\
    --client-id CID --property-id PID --out-dir docs/audit
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="B1 staging verification (tenant-scoped)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--before-slug-suffix", default="6fd5ac4c_d35a58ae")
    return p.parse_args()


def _row_state_sig(row: Dict[str, Any]) -> str:
    parts = [
        str(row.get("requirement_id") or ""),
        str(row.get("requirement_type") or ""),
        str(row.get("status") or ""),
        str(row.get("applicability") or ""),
        str(row.get("not_required_reason") or ""),
        str((row.get("registry_metadata") or {}).get("reconciled_obsolete")),
        str(row.get("requirement_generation_source") or ""),
        str(row.get("client_surface_visible")),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _aggregate_hash(sigs: List[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(sigs)).encode()).hexdigest()[:32]


def _explain_metrics(explain: Dict[str, Any]) -> Dict[str, Any]:
    rows = explain.get("rows") or []
    exclusion_reasons: Counter[str] = Counter()
    not_required_in_plan = 0
    included_types: List[str] = []
    for row in rows:
        if row.get("included"):
            included_types.append(str(row.get("requirement_type") or ""))
        else:
            exclusion_reasons[str(row.get("exclusion_reason") or "unknown")] += 1
            pers = row.get("persistence") or {}
            if str(row.get("exclusion_reason") or "") == "not_required_row":
                if pers.get("operator_curated_not_required") is False:
                    not_required_in_plan += 1
    return {
        "raw_count": int(explain.get("raw_count") or 0),
        "included_count": int(explain.get("included_count") or 0),
        "exclusion_reasons": dict(exclusion_reasons),
        "not_required_row_count": exclusion_reasons.get("not_required_row", 0),
        "included_types": sorted(t for t in included_types if t),
        "automated_not_required_excluded": not_required_in_plan,
    }


async def _client_api_visible_count(db, *, cid: str, pid: str) -> int:
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
    from services.compliance_registry_publish_service import fetch_active_published_registry_entries

    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    client_doc = await db.clients.find_one({"client_id": cid}, {"_id": 0}) or {}
    raw = await db.requirements.find({"client_id": cid, "property_id": pid}, {"_id": 0}).to_list(500)
    published = await fetch_active_published_registry_entries(db)
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=cid,
        requirements=raw,
        client_doc=client_doc,
        properties=[prop],
        published_registry_entries=published,
    )
    visible = [r for r in filtered if r.get("client_surface_visible", True)]
    return len(visible)


async def main() -> None:
    from database import database
    from services.compliance_registry_publish_service import fetch_active_published_registry_entries
    from services.compliance_requirement_registry import build_requirement_plan_for_property
    from services.requirement_client_runtime_surface import explain_runtime_requirement_rows_for_property
    from services.requirement_materialization_service import materialize_requirements_for_property

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    slug = args.before_slug_suffix
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()

    before_explain_path = out_dir / f"b1_explain_before_{slug}.json"
    before_baseline_path = out_dir / f"b1_replay_baseline_{slug}.json"
    if not before_explain_path.exists():
        raise SystemExit(f"Missing before explain: {before_explain_path}")

    before_explain_payload = json.loads(before_explain_path.read_text(encoding="utf-8"))
    before_explain = before_explain_payload.get("explain") or before_explain_payload
    before_metrics = _explain_metrics(before_explain)

    async def _audit_count() -> int:
        return await db.applicability_resolution_audit.count_documents(
            {"client_id": cid, "property_id": pid}
        )

    async def _queue_pending_count() -> int:
        return await db.compliance_recalc_queue.count_documents(
            {"client_id": cid, "property_id": pid, "status": "PENDING"}
        )

    async def _reconciled_row_snapshot() -> Optional[Dict[str, Any]]:
        row = await db.requirements.find_one(
            {
                "client_id": cid,
                "property_id": pid,
                "registry_metadata.reconciled_obsolete": True,
            },
            {"_id": 0, "requirement_id": 1, "requirement_type": 1, "updated_at": 1, "registry_metadata": 1},
        )
        if not row:
            return None
        meta = row.get("registry_metadata") or {}
        return {
            "requirement_id": row.get("requirement_id"),
            "requirement_type": row.get("requirement_type"),
            "updated_at": row.get("updated_at"),
            "reconciled_at": meta.get("reconciled_at"),
        }

    baseline_audit = await _audit_count()
    baseline_queue_pending = await _queue_pending_count()
    row_updated_at_before: Dict[str, Any] = {
        str(r.get("requirement_id") or ""): r.get("updated_at")
        for r in await db.requirements.find(
            {"client_id": cid, "property_id": pid},
            {"_id": 0, "requirement_id": 1, "updated_at": 1},
        ).to_list(500)
    }

    replay_runs: List[Dict[str, Any]] = []
    for i in range(1, 4):
        audit_before_run = await _audit_count()
        queue_before_run = await _queue_pending_count()
        reconciled_before = await _reconciled_row_snapshot()
        result = await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
        rows = await db.requirements.find({"client_id": cid, "property_id": pid}, {"_id": 0}).to_list(500)
        sigs = [_row_state_sig(r) for r in rows]
        row_updated_at_after = {
            str(r.get("requirement_id") or ""): r.get("updated_at")
            for r in rows
        }
        unchanged_updated_at = [
            rid
            for rid, ts in row_updated_at_before.items()
            if rid and row_updated_at_after.get(rid) == ts
        ]
        changed_updated_at = [
            rid
            for rid, ts in row_updated_at_before.items()
            if rid and row_updated_at_after.get(rid) != ts
        ]
        replay_runs.append(
            {
                "run": i,
                "materialize_result": result,
                "row_count": len(rows),
                "aggregate_state_hash": _aggregate_hash(sigs),
                "reopened_from_not_required": result.get("reopened_from_not_required"),
                "reconciled_obsolete": result.get("reconciled_obsolete"),
                "upsert_passes": result.get("upsert_passes"),
                "audit_count_before_run": audit_before_run,
                "audit_count_after_run": await _audit_count(),
                "audit_delta_run": await _audit_count() - audit_before_run,
                "queue_pending_before_run": queue_before_run,
                "queue_pending_after_run": await _queue_pending_count(),
                "queue_delta_run": await _queue_pending_count() - queue_before_run,
                "reconciled_row_before": reconciled_before,
                "reconciled_row_after": await _reconciled_row_snapshot(),
                "unchanged_updated_at_count": len(unchanged_updated_at),
                "changed_updated_at_count": len(changed_updated_at),
            }
        )
        row_updated_at_before = row_updated_at_after

    run2 = replay_runs[1]
    run3 = replay_runs[2]
    reconciled_run2 = (run2.get("materialize_result") or {}).get("reconciled_obsolete", run2.get("reconciled_obsolete"))
    reconciled_run3 = (run3.get("materialize_result") or {}).get("reconciled_obsolete", run3.get("reconciled_obsolete"))
    reconciled_row_stable = (
        run2.get("reconciled_row_after") == run3.get("reconciled_row_after")
        or (
            run2.get("reconciled_row_after")
            and run3.get("reconciled_row_after")
            and run2["reconciled_row_after"].get("updated_at") == run3["reconciled_row_after"].get("updated_at")
            and run2["reconciled_row_after"].get("reconciled_at") == run3["reconciled_row_after"].get("reconciled_at")
        )
    )
    replay_stable = (
        run2["aggregate_state_hash"] == run3["aggregate_state_hash"]
        and reconciled_run2 == 0
        and reconciled_run3 == 0
        and run3.get("reopened_from_not_required") == 0
        and run3.get("audit_delta_run") == 0
        and run3.get("queue_delta_run") == 0
        and reconciled_row_stable
    )

    explain_after = await explain_runtime_requirement_rows_for_property(db, client_id=cid, property_id=pid)
    after_metrics = _explain_metrics(explain_after)
    client_visible = await _client_api_visible_count(db, cid=cid, pid=pid)

    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    client_doc = await db.clients.find_one({"client_id": cid}, {"_id": 0}) or {}
    published = await fetch_active_published_registry_entries(db)
    plan = build_requirement_plan_for_property(prop, client_doc, published_registry_entries=published)
    planned_types = sorted({str(p.requirement_type or "").strip().lower() for p in plan if p.requirement_type})

    # A1 rerun
    from scripts.a1_obligation_tenant_classification import _run as a1_run

    a1_after = await a1_run(cid, pid)
    a1_path = out_dir / f"a1_tenant_classification_post_b1_{slug}.json"
    a1_path.write_text(json.dumps(a1_after, indent=2, default=str), encoding="utf-8")

    explain_after_path = out_dir / f"b1_explain_after_{slug}.json"
    explain_after_payload = {
        "captured_at_utc": run_at,
        "phase": "B1_after_staging_verification",
        "client_id": cid,
        "property_id": pid,
        "planned_types": planned_types,
        "planned_types_count": len(planned_types),
        "replay_runs": replay_runs,
        "replay_stable_run2_equals_run3": replay_stable,
        "explain": explain_after,
        "client_api_visible_count": client_visible,
    }
    explain_after_path.write_text(json.dumps(explain_after_payload, indent=2, default=str), encoding="utf-8")

    replay_after_path = out_dir / f"b1_replay_after_{slug}.json"
    replay_after_payload = {
        "captured_at_utc": run_at,
        "client_id": cid,
        "property_id": pid,
        "runs": replay_runs,
        "stable": replay_stable,
    }
    replay_after_path.write_text(json.dumps(replay_after_payload, indent=2, default=str), encoding="utf-8")

    core_types = ["eicr", "legionella", "epc", "hmo_license", "gas_safety"]
    included_set = set(after_metrics["included_types"])
    core_visible = {t: t in included_set for t in core_types if t in planned_types}

    dup_types = Counter(str(r.get("requirement_type") or "").lower() for r in await db.requirements.find(
        {"client_id": cid, "property_id": pid}, {"_id": 0, "requirement_type": 1}
    ).to_list(500))
    duplicate_row_types = [t for t, n in dup_types.items() if n > 1]

    checks = {
        "reconciled_obsolete_zero_run2": reconciled_run2 == 0,
        "reconciled_obsolete_zero_run3": reconciled_run3 == 0,
        "reconciled_row_updated_at_stable_run2_run3": reconciled_row_stable,
        "audit_delta_zero_run3": run3.get("audit_delta_run") == 0,
        "queue_delta_zero_run3": run3.get("queue_delta_run") == 0,
        "replay_run2_equals_run3": replay_stable,
        "included_count_increased": after_metrics["included_count"] > before_metrics["included_count"],
        "not_required_row_decreased": after_metrics["not_required_row_count"] < before_metrics["not_required_row_count"],
        "client_api_matches_explain_included": client_visible == after_metrics["included_count"],
        "no_duplicate_requirement_types": len(duplicate_row_types) == 0,
        "eicr_included_if_planned": (not ("eicr" in planned_types) or "eicr" in included_set),
        "core_obligations_visible": all(core_visible.values()) if core_visible else True,
    }
    passed = all(checks.values())

    diff_summary = {
        "before": before_metrics,
        "after": after_metrics,
        "delta": {
            "raw_count": after_metrics["raw_count"] - before_metrics["raw_count"],
            "included_count": after_metrics["included_count"] - before_metrics["included_count"],
            "not_required_row_count": after_metrics["not_required_row_count"] - before_metrics["not_required_row_count"],
        },
        "planned_types_unchanged": before_explain_payload.get("planned_types") == planned_types
        or before_explain_payload.get("planned_types_count") == len(planned_types),
        "core_visibility": core_visible,
        "a1_classification_after": a1_after.get("classification"),
        "a1_first_divergence_after": a1_after.get("first_divergence_point"),
    }

    report_path = out_dir / f"b1_verification_report_{slug}.json"
    report = {
        "captured_at_utc": run_at,
        "client_id": cid,
        "property_id": pid,
        "b1_pass": passed,
        "checks": checks,
        "diff_summary": diff_summary,
        "artifacts": {
            "explain_after": str(explain_after_path.relative_to(ROOT)),
            "replay_after": str(replay_after_path.relative_to(ROOT)),
            "a1_post_b1": str(a1_path.relative_to(ROOT)),
            "report": str(report_path.relative_to(ROOT)),
        },
        "b2_still_needed": after_metrics["not_required_row_count"] > 0
        or any(
            str(r.get("exclusion_reason") or "") not in ("not_required_row", "not_in_planner_membership")
            for r in (explain_after.get("rows") or [])
            if not r.get("included")
        ),
        "c1_blocked": not passed,
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
