"""
C1 staging verification: governed mutations, replay, recalc stability, reclaim observability.

Uses the same service calls as HTTP sync routes (not raw Mongo queue inserts).

  python -m scripts.c1_staging_verification \\
    --client-id CID --property-id PID --out-dir docs/audit
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="C1 staging verification")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--poll-seconds", type=int, default=120)
    return p.parse_args()


def _fp(obj: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


async def _property_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    return {
        "compliance_score": prop.get("compliance_score"),
        "compliance_score_pending": prop.get("compliance_score_pending"),
        "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
        "fingerprint": _fp(
            {
                "compliance_score": prop.get("compliance_score"),
                "compliance_score_pending": prop.get("compliance_score_pending"),
                "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
            }
        ),
    }


async def _queue_counts(db, *, pid: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    pipeline = [
        {"$match": {"property_id": pid}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]
    async for row in db.compliance_recalc_queue.aggregate(pipeline):
        counts[str(row.get("_id") or "unknown").upper()] = int(row.get("n") or 0)
    counts["TOTAL"] = sum(counts.values())
    return counts


async def _boundary_counts(db, *, cid: str, pid: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    try:
        out["risk_signal_regen_pending"] = await db.risk_signal_regen_queue.count_documents(
            {"property_id": pid, "status": "PENDING"}
        )
    except Exception:
        out["risk_signal_regen_pending"] = -1
    try:
        out["notification_retry_pending"] = await db.notification_retry_queue.count_documents(
            {"client_id": cid, "status": "PENDING"}
        )
    except Exception:
        out["notification_retry_pending"] = -1
    return out


async def _audit_count(db, *, cid: str, pid: str) -> int:
    return await db.applicability_resolution_audit.count_documents(
        {"client_id": cid, "property_id": pid}
    )


async def _score_events_count(db, *, cid: str, pid: str) -> int:
    return await db.score_events.count_documents({"client_id": cid, "property_id": pid})


async def _job_runs_recent(db) -> List[Dict[str, Any]]:
    return await db.job_runs.find(
        {"job_name": "compliance_recalc_worker"},
        {"_id": 0, "job_name": 1, "status": 1, "started_at": 1, "finished_at": 1, "error": 1},
    ).sort("started_at", -1).limit(8).to_list(8)


async def _queue_for_correlation(db, *, pid: str, correlation_id: str) -> Optional[Dict[str, Any]]:
    return await db.compliance_recalc_queue.find_one(
        {"property_id": pid, "correlation_id": correlation_id},
        {"_id": 0},
    )


async def _wait_queue_terminal(
    db, *, pid: str, correlation_id: str, timeout_s: int
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        row = await _queue_for_correlation(db, pid=pid, correlation_id=correlation_id)
        if row:
            last = dict(row)
            st = str(row.get("status") or "").upper()
            if st in ("DONE", "DEAD", "FAILED"):
                return last
        await asyncio.sleep(2)
    return last


async def _c1_m1_sync(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.compliance_recalc_queue import (
        ACTOR_CLIENT,
        TRIGGER_PROPERTY_UPDATED,
        enqueue_compliance_recalc,
    )
    from services.provisioning import provisioning_service
    from services.requirement_materialization_service import materialize_requirements_for_property

    correlation_id = f"REQUIREMENTS_SYNC:{pid}"
    mat = await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
    await provisioning_service._update_property_compliance(pid)
    enq = await enqueue_compliance_recalc(
        property_id=pid,
        client_id=cid,
        trigger_reason=TRIGGER_PROPERTY_UPDATED,
        actor_type=ACTOR_CLIENT,
        correlation_id=correlation_id,
    )
    return {
        "mutation": "C1-M1",
        "correlation_id": correlation_id,
        "materialize": mat,
        "enqueue": {
            "enqueued": enq.enqueued,
            "duplicate_suppression_reason": enq.duplicate_suppression_reason,
            "regeneration_requeued": enq.regeneration_requeued,
        },
    }


async def _c1_m2_sync(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.compliance_recalc_queue import (
        ACTOR_ADMIN,
        TRIGGER_ADMIN_MANUAL_JOB,
        enqueue_compliance_recalc,
    )
    from services.provisioning import provisioning_service
    from services.requirement_materialization_service import materialize_requirements_for_property

    correlation_id = f"{TRIGGER_ADMIN_MANUAL_JOB}:REGISTRY_SYNC:{pid}:{uuid.uuid4().hex[:12]}"
    mat = await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
    await provisioning_service._update_property_compliance(pid)
    enq = await enqueue_compliance_recalc(
        property_id=pid,
        client_id=cid,
        trigger_reason=TRIGGER_ADMIN_MANUAL_JOB,
        actor_type=ACTOR_ADMIN,
        correlation_id=correlation_id,
    )
    return {
        "mutation": "C1-M2",
        "correlation_id": correlation_id,
        "materialize": mat,
        "enqueue": {
            "enqueued": enq.enqueued,
            "duplicate_suppression_reason": enq.duplicate_suppression_reason,
            "regeneration_requeued": enq.regeneration_requeued,
        },
    }


async def _stuck_running(db, *, pid: str) -> List[Dict[str, Any]]:
    from datetime import timedelta

    from services.compliance_recalc_operational_snapshot import _parse_iso

    stale_s = int(os.getenv("COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "1800"))
    cut = datetime.now(timezone.utc) - timedelta(seconds=stale_s)
    out: List[Dict[str, Any]] = []
    async for row in db.compliance_recalc_queue.find({"property_id": pid, "status": "RUNNING"}, {"_id": 0}):
        hb = _parse_iso(row.get("heartbeat_at")) or _parse_iso(row.get("updated_at"))
        if hb and hb < cut:
            out.append(
                {
                    "correlation_id": row.get("correlation_id"),
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
    slug = args.slug_suffix
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()
    stable_corr = f"REQUIREMENTS_SYNC:{pid}"

    before_path = out_dir / f"c1_queue_before_{slug}.json"
    before_loaded: Dict[str, Any] = {}
    if before_path.exists():
        before_loaded = json.loads(before_path.read_text(encoding="utf-8"))

    baseline = {
        "queue_counts": await _queue_counts(db, pid=pid),
        "property": await _property_snapshot(db, cid=cid, pid=pid),
        "audit_count": await _audit_count(db, cid=cid, pid=pid),
        "score_events_count": await _score_events_count(db, cid=cid, pid=pid),
        "score_history_count": await db.property_compliance_score_history.count_documents(
            {"property_id": pid}
        ),
        "boundary_counts": await _boundary_counts(db, cid=cid, pid=pid),
        "job_runs_count": await db.job_runs.count_documents({"job_name": "compliance_recalc_worker"}),
    }

    runs: List[Dict[str, Any]] = []
    for label in ("R1", "R2", "R3"):
        snap_before = {
            "property": await _property_snapshot(db, cid=cid, pid=pid),
            "queue_counts": await _queue_counts(db, pid=pid),
            "audit_count": await _audit_count(db, cid=cid, pid=pid),
            "score_events_count": await _score_events_count(db, cid=cid, pid=pid),
            "score_history_count": await db.property_compliance_score_history.count_documents(
                {"property_id": pid}
            ),
            "boundary_counts": await _boundary_counts(db, cid=cid, pid=pid),
        }
        outcome = await _c1_m1_sync(db, cid=cid, pid=pid)
        queue_row = await _wait_queue_terminal(
            db, pid=pid, correlation_id=stable_corr, timeout_s=args.poll_seconds
        )
        snap_after = {
            "property": await _property_snapshot(db, cid=cid, pid=pid),
            "queue_counts": await _queue_counts(db, pid=pid),
            "audit_count": await _audit_count(db, cid=cid, pid=pid),
            "score_events_count": await _score_events_count(db, cid=cid, pid=pid),
            "score_history_count": await db.property_compliance_score_history.count_documents(
                {"property_id": pid}
            ),
            "boundary_counts": await _boundary_counts(db, cid=cid, pid=pid),
            "job_runs_recent": await _job_runs_recent(db),
        }
        runs.append(
            {
                "run": label,
                "mutation": "C1-M1",
                "outcome": outcome,
                "queue_row": queue_row,
                "before": snap_before,
                "after": snap_after,
                "deltas": {
                    "audit": snap_after["audit_count"] - snap_before["audit_count"],
                    "score_events": snap_after["score_events_count"] - snap_before["score_events_count"],
                    "score_history": snap_after["score_history_count"] - snap_before["score_history_count"],
                    "queue_total": snap_after["queue_counts"].get("TOTAL", 0)
                    - snap_before["queue_counts"].get("TOTAL", 0),
                },
            }
        )

    m2_before = await _boundary_counts(db, cid=cid, pid=pid)
    m2_outcome = await _c1_m2_sync(db, cid=cid, pid=pid)
    m2_corr = m2_outcome["correlation_id"]
    m2_queue = await _wait_queue_terminal(db, pid=pid, correlation_id=m2_corr, timeout_s=args.poll_seconds)
    m2_after = await _boundary_counts(db, cid=cid, pid=pid)

    ops = await build_recalc_queue_operational_snapshot(max_sample=15)
    queue_after = {
        "captured_at_utc": run_at,
        "phase": "C1_after_verification",
        "client_id": cid,
        "property_id": pid,
        "queue_counts": await _queue_counts(db, pid=pid),
        "property": await _property_snapshot(db, cid=cid, pid=pid),
        "stable_correlation_row": await _queue_for_correlation(db, pid=pid, correlation_id=stable_corr),
        "job_runs_recent": await _job_runs_recent(db),
    }

    recalc_stability = {
        "captured_at_utc": run_at,
        "baseline_before_file": str(before_path.relative_to(ROOT)) if before_path.exists() else None,
        "verification_baseline": baseline,
        "runs": [
            {
                "run": r["run"],
                "property_before": r["before"]["property"],
                "property_after": r["after"]["property"],
                "score_history_delta": r["deltas"]["score_history"],
                "score_events_delta": r["deltas"]["score_events"],
                "compliance_last_calculated_at_after": r["after"]["property"].get(
                    "compliance_last_calculated_at"
                ),
            }
            for r in runs
        ],
    }

    reclaim_after = {
        "captured_at_utc": run_at,
        "phase": "C1_after_verification",
        "reclaim_config": {
            "COMPLIANCE_RECALC_RUNNING_STALE_SECONDS": os.getenv(
                "COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "1800"
            ),
            "COMPLIANCE_RECALC_HEARTBEAT_SECONDS": os.getenv("COMPLIANCE_RECALC_HEARTBEAT_SECONDS", "45"),
        },
        "operational_snapshot_excerpt": {
            k: ops.get(k)
            for k in (
                "running_job_count",
                "pending_job_count",
                "dead_job_count",
                "duplicate_suppression_enqueue_total",
                "reconciliation_observability",
            )
            if isinstance(ops, dict)
        },
        "stuck_running_on_pilot": await _stuck_running(db, pid=pid),
        "operator_detection_paths": [
            "GET /health-summary → recalc_queue_health",
            "build_recalc_queue_operational_snapshot",
        ],
    }

    replay_path = out_dir / f"c1_replay_{slug}.json"
    replay_payload = {
        "captured_at_utc": run_at,
        "stable_correlation": stable_corr,
        "runs": runs,
        "legitimate_mutation": {
            "outcome": m2_outcome,
            "queue_row": m2_queue,
            "boundary_before": m2_before,
            "boundary_after": m2_after,
        },
    }
    replay_path.write_text(json.dumps(replay_payload, indent=2, default=str), encoding="utf-8")
    (out_dir / f"c1_queue_after_{slug}.json").write_text(
        json.dumps(queue_after, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c1_recalc_stability_{slug}.json").write_text(
        json.dumps(recalc_stability, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c1_reclaim_observability_{slug}.json").write_text(
        json.dumps(reclaim_after, indent=2, default=str), encoding="utf-8"
    )

    r1, r2, r3 = runs[0], runs[1], runs[2]
    stable_replay = (
        r2["outcome"]["enqueue"]["enqueued"] is False
        and r3["outcome"]["enqueue"]["enqueued"] is False
        and r2["after"]["property"]["fingerprint"] == r3["after"]["property"]["fingerprint"]
        and r3["deltas"]["score_history"] == 0
        and r3["deltas"]["score_events"] == 0
    )
    r1_pending_cleared = (
        r1["queue_row"].get("status") == "DONE"
        and r1["after"]["property"].get("compliance_score_pending") is False
    )
    legitimate = m2_outcome["enqueue"]["enqueued"] is True and str(m2_queue.get("status") or "").upper() in (
        "DONE",
        "PENDING",
        "RUNNING",
    )
    no_fanout_storm = (
        r2["deltas"].get("queue_total", 99) <= 0
        and r3["deltas"].get("queue_total", 99) <= 0
        and r2["after"]["boundary_counts"].get("notification_retry_pending", 0)
        == r3["after"]["boundary_counts"].get("notification_retry_pending", 0)
    )

    report = {
        "captured_at_utc": run_at,
        "client_id": cid,
        "property_id": pid,
        "queue_before_total": before_loaded.get("queue_total_for_property")
        or baseline["queue_counts"].get("TOTAL"),
        "queue_after_total": queue_after["queue_counts"].get("TOTAL"),
        "c1_pass": stable_replay and legitimate and r1_pending_cleared and len(reclaim_after["stuck_running_on_pilot"]) == 0,
        "checks": {
            "r1_enqueue_and_complete": r1_pending_cleared,
            "stable_replay_suppressed_r2_r3": r2["outcome"]["enqueue"]["enqueued"] is False
            and r3["outcome"]["enqueue"]["enqueued"] is False,
            "duplicate_reason_r2": r2["outcome"]["enqueue"].get("duplicate_suppression_reason"),
            "duplicate_reason_r3": r3["outcome"]["enqueue"].get("duplicate_suppression_reason"),
            "recalc_fingerprint_stable_r2_r3": r2["after"]["property"]["fingerprint"]
            == r3["after"]["property"]["fingerprint"],
            "recalc_last_calculated_stable_r2_r3": r2["after"]["property"].get("compliance_last_calculated_at")
            == r3["after"]["property"].get("compliance_last_calculated_at"),
            "score_history_delta_r3": r3["deltas"]["score_history"],
            "legitimate_m2_enqueued": legitimate,
            "stuck_running_zero": len(reclaim_after["stuck_running_on_pilot"]) == 0,
            "no_unexpected_fanout_boundary": no_fanout_storm,
        },
        "artifacts": {
            "replay": str(replay_path.relative_to(ROOT)),
            "queue_after": f"docs/audit/c1_queue_after_{slug}.json",
            "recalc_stability": f"docs/audit/c1_recalc_stability_{slug}.json",
            "reclaim_observability": f"docs/audit/c1_reclaim_observability_{slug}.json",
        },
    }
    report_path = out_dir / f"c1_verification_report_{slug}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
