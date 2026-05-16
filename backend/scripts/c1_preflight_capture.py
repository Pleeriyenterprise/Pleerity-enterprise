"""
C1 preflight: before queue/recalc snapshots (read-only).

Run from backend/ with MONGO_URL + DB_NAME:

  python -m scripts.c1_preflight_capture \\
    --client-id CID --property-id PID --out-dir docs/audit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="C1 preflight capture (read-only)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    return p.parse_args()


def _score_fingerprint(prop: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "compliance_score",
        "compliance_score_pending",
        "compliance_last_calculated_at",
        "compliance_score_version",
    )
    return {k: prop.get(k) for k in keys if k in prop}


async def _stuck_running_rows(db, *, pid: str, stale_seconds: int) -> List[Dict[str, Any]]:
    from datetime import timedelta

    from services.compliance_recalc_operational_snapshot import _parse_iso

    now = datetime.now(timezone.utc)
    cut = now - timedelta(seconds=stale_seconds)
    out: List[Dict[str, Any]] = []
    cursor = db.compliance_recalc_queue.find(
        {"property_id": pid, "status": "RUNNING"},
        {"_id": 0},
    )
    async for row in cursor:
        hb = _parse_iso(row.get("heartbeat_at")) or _parse_iso(row.get("updated_at"))
        if hb and hb < cut:
            out.append(
                {
                    "correlation_id": row.get("correlation_id"),
                    "status": row.get("status"),
                    "heartbeat_at": row.get("heartbeat_at"),
                    "updated_at": row.get("updated_at"),
                }
            )
    return out


async def main() -> None:
    from database import database
    from services.compliance_recalc_operational_snapshot import build_recalc_queue_operational_snapshot

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    slug = f"{cid[:8]}_{pid[:8]}"
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()
    stale_running_seconds = int(os.getenv("COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "1800"))

    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    queue_rows = await db.compliance_recalc_queue.find(
        {"property_id": pid},
        {"_id": 0},
    ).sort("updated_at", -1).limit(20).to_list(20)
    queue_by_status: Dict[str, int] = {}
    for row in queue_rows:
        st = str(row.get("status") or "unknown").upper()
        queue_by_status[st] = queue_by_status.get(st, 0) + 1

    job_runs = await db.job_runs.find(
        {"job_name": "compliance_recalc_worker"},
        {"_id": 0},
    ).sort("started_at", -1).limit(5).to_list(5)

    heartbeat = await db.scheduler_heartbeat.find_one({}, {"_id": 0}) or {}

    try:
        ops_snapshot = await build_recalc_queue_operational_snapshot(max_sample=15)
    except Exception as exc:
        ops_snapshot = {"error": str(exc)}

    gap_count = await db.compliance_gaps.count_documents({"client_id": cid, "property_id": pid})
    score_history_count = await db.property_compliance_score_history.count_documents(
        {"property_id": pid}
    )

    reclaim_config = {
        "COMPLIANCE_RECALC_RUNNING_STALE_SECONDS": os.getenv(
            "COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "1800"
        ),
        "COMPLIANCE_RECALC_HEARTBEAT_SECONDS": os.getenv("COMPLIANCE_RECALC_HEARTBEAT_SECONDS", "45"),
        "DB_NAME": os.getenv("DB_NAME"),
    }

    queue_before = {
        "captured_at_utc": run_at,
        "phase": "C1_before_IN_PROGRESS",
        "client_id": cid,
        "property_id": pid,
        "property_score_fingerprint": _score_fingerprint(prop),
        "queue_rows_recent": queue_rows,
        "queue_status_counts_sample": queue_by_status,
        "queue_total_for_property": await db.compliance_recalc_queue.count_documents({"property_id": pid}),
        "job_runs_recent": job_runs,
        "scheduler_heartbeat": heartbeat,
        "operational_snapshot": ops_snapshot,
        "reclaim_config": reclaim_config,
        "stuck_running_on_pilot": await _stuck_running_rows(db, pid=pid, stale_seconds=stale_running_seconds),
        "gap_count": gap_count,
        "score_history_count": score_history_count,
    }

    queue_path = out_dir / f"c1_queue_before_{slug}.json"
    reclaim_path = out_dir / f"c1_reclaim_observability_before_{slug}.json"
    recalc_path = out_dir / f"c1_recalc_stability_before_{slug}.json"

    queue_path.write_text(json.dumps(queue_before, indent=2, default=str), encoding="utf-8")
    reclaim_path.write_text(
        json.dumps(
            {
                "captured_at_utc": run_at,
                "phase": "C1_before_IN_PROGRESS",
                "reclaim_config": reclaim_config,
                "operational_snapshot_excerpt": {
                    k: ops_snapshot.get(k)
                    for k in (
                        "running_job_count",
                        "pending_job_count",
                        "dead_job_count",
                        "duplicate_suppression_enqueue_total",
                        "reconciliation_observability",
                    )
                    if isinstance(ops_snapshot, dict)
                },
                "stuck_running_on_pilot": queue_before["stuck_running_on_pilot"],
                "operator_detection_paths": [
                    "GET /health-summary → recalc_queue_health",
                    "build_recalc_queue_operational_snapshot",
                    "RUNBOOK §12.7 C1 + SCHEDULER_AND_COMPLIANCE_JOBS.md",
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    recalc_path.write_text(
        json.dumps(
            {
                "captured_at_utc": run_at,
                "phase": "C1_before_IN_PROGRESS",
                "baseline_run": "pre-R1",
                "property_score_fingerprint": _score_fingerprint(prop),
                "score_history_count": score_history_count,
                "gap_count": gap_count,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "queue_before": str(queue_path.relative_to(ROOT)),
                "reclaim_observability_before": str(reclaim_path.relative_to(ROOT)),
                "recalc_stability_before": str(recalc_path.relative_to(ROOT)),
                "queue_total_for_property": queue_before["queue_total_for_property"],
                "stuck_running_count": len(queue_before["stuck_running_on_pilot"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
