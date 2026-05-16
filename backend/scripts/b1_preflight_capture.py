"""
B1 preflight: before explain snapshot, replay baseline, root-cause confirmation.

Read-only. Run from backend/ with MONGO_URL + DB_NAME.

  python -m scripts.b1_preflight_capture \\
    --client-id CID --property-id PID \\
    --out-dir docs/audit
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
    p = argparse.ArgumentParser(description="B1 preflight capture (read-only)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
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
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


async def main() -> None:
    from database import database
    from services.compliance_registry_publish_service import fetch_active_published_registry_entries
    from services.compliance_requirement_registry import build_requirement_plan_for_property
    from services.requirement_client_runtime_surface import explain_runtime_requirement_rows_for_property
    from services.requirement_materialization_service import REQUIREMENT_GENERATION_SOURCE_REGISTRY

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = f"{cid[:8]}_{pid[:8]}"
    db = database.get_db()

    explain = await explain_runtime_requirement_rows_for_property(db, client_id=cid, property_id=pid)
    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    client_doc = await db.clients.find_one({"client_id": cid}, {"_id": 0}) or {}
    published = await fetch_active_published_registry_entries(db)
    plan = build_requirement_plan_for_property(prop, client_doc, published_registry_entries=published)
    planned_types: Set[str] = {str(p.requirement_type or "").strip().lower() for p in plan if p.requirement_type}

    rows = await db.requirements.find(
        {"client_id": cid, "property_id": pid},
        {"_id": 0},
    ).to_list(500)

    baseline_rows: List[Dict[str, Any]] = []
    rc_analysis: List[Dict[str, Any]] = []
    counters: Counter[str] = Counter()

    for row in rows:
        rid = str(row.get("requirement_id") or "")
        rtype = str(row.get("requirement_type") or "").strip().lower()
        status = (row.get("status") or "").upper()
        app = (row.get("applicability") or "").upper()
        nrr = row.get("not_required_reason")
        meta = row.get("registry_metadata") if isinstance(row.get("registry_metadata"), dict) else {}
        reconciled = meta.get("reconciled_obsolete") is True
        gen_src = str(row.get("requirement_generation_source") or "")
        in_plan = rtype in planned_types
        wrongly_nr = (
            (status == "NOT_REQUIRED" or app == "NOT_REQUIRED")
            and not nrr
            and in_plan
            and gen_src == REQUIREMENT_GENERATION_SOURCE_REGISTRY
        )

        baseline_rows.append(
            {
                "requirement_id": rid,
                "requirement_type": rtype,
                "state_sig": _row_state_sig(row),
                "status": status,
                "applicability": app,
                "not_required_reason": nrr,
                "reconciled_obsolete": reconciled,
                "in_planned_types": in_plan,
                "requirement_generation_source": gen_src,
            }
        )

        mechanism = "ok"
        if wrongly_nr:
            if reconciled:
                mechanism = "B1-RC-1_reconcile_obsolete"
                counters["B1-RC-1_reconcile_obsolete"] += 1
            elif gen_src == REQUIREMENT_GENERATION_SOURCE_REGISTRY:
                mechanism = "B1-RC-3_reopen_not_applied"
                counters["B1-RC-3_reopen_not_applied"] += 1
            else:
                mechanism = "B1-RC-other_NOT_REQUIRED_in_plan"
                counters["B1-RC-other"] += 1
            rc_analysis.append(
                {
                    "requirement_id": rid,
                    "requirement_type": rtype,
                    "mechanism": mechanism,
                    "reconciled_obsolete": reconciled,
                    "reconciled_at": meta.get("reconciled_at"),
                    "in_planned_types": in_plan,
                    "legacy_requirement_state": row.get("legacy_requirement_state"),
                }
            )

    # applicability_resolution_audit sample
    audit_samples = await db.applicability_resolution_audit.find(
        {"client_id": cid, "property_id": pid},
        {"_id": 0},
    ).sort("created_at", -1).limit(30).to_list(30)

    audit_event_types = Counter(str(a.get("event_type") or "") for a in audit_samples)

    run_at = datetime.now(timezone.utc).isoformat()
    before_explain_path = out_dir / f"b1_explain_before_{slug}.json"
    baseline_path = out_dir / f"b1_replay_baseline_{slug}.json"
    rc_path = out_dir / f"b1_root_cause_confirmation_{slug}.json"

    before_payload = {
        "captured_at_utc": run_at,
        "phase": "B1_before_IN_PROGRESS",
        "client_id": cid,
        "property_id": pid,
        "planned_types": sorted(planned_types),
        "planned_types_count": len(planned_types),
        "explain": explain,
    }
    before_explain_path.write_text(json.dumps(before_payload, indent=2, default=str), encoding="utf-8")

    baseline_payload = {
        "captured_at_utc": run_at,
        "client_id": cid,
        "property_id": pid,
        "rows": baseline_rows,
        "aggregate_state_hash": hashlib.sha256(
            json.dumps(sorted([r["state_sig"] for r in baseline_rows])).encode()
        ).hexdigest()[:32],
    }
    baseline_path.write_text(json.dumps(baseline_payload, indent=2, default=str), encoding="utf-8")

    primary_rc = counters.most_common(1)[0][0] if counters else "none"
    rc_payload = {
        "captured_at_utc": run_at,
        "client_id": cid,
        "property_id": pid,
        "primary_mechanism": primary_rc,
        "mechanism_counts": dict(counters),
        "wrongly_not_required_in_plan_count": len(rc_analysis),
        "wrongly_not_required_rows": rc_analysis,
        "audit_event_type_counts": dict(audit_event_types),
        "audit_samples_recent": audit_samples[:10],
        "conclusion": (
            "Implement B1-RC-1 + B1-RC-3: reconcile_obsolete left in-plan rows NOT_REQUIRED; "
            "reopen path (no not_required_reason) must run on materialise when type re-enters plan."
            if counters else "No wrongly NOT_REQUIRED in-plan rows found — re-evaluate."
        ),
    }
    rc_path.write_text(json.dumps(rc_payload, indent=2, default=str), encoding="utf-8")

    print(json.dumps(
        {
            "before_explain": str(before_explain_path.relative_to(ROOT)),
            "replay_baseline": str(baseline_path.relative_to(ROOT)),
            "root_cause": str(rc_path.relative_to(ROOT)),
            "primary_mechanism": primary_rc,
            "mechanism_counts": dict(counters),
            "planned_types_count": len(planned_types),
            "explain_included": explain.get("included_count"),
            "explain_raw": explain.get("raw_count"),
        },
        indent=2,
    ))


if __name__ == "__main__":
    asyncio.run(main())
