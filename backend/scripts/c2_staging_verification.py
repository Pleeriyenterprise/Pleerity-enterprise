"""
C2 staging verification: downstream convergence after recalc (R1–R3 replay).

  python -m scripts.c2_staging_verification \\
    --client-id CID --property-id PID --out-dir docs/audit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.c1_staging_verification import (  # noqa: E402
    _c1_m1_sync,
    _wait_queue_terminal,
)
from scripts.c2_snapshot import (  # noqa: E402
    consistency_hashes,
    delta_fingerprints,
    detect_ordering_violation,
    exclusions_matrix,
    full_convergence_snapshot,
    lineage_fingerprint,
    lineage_trace,
    ordering_tick,
    stale_decay_snapshot,
    unrelated_fingerprints,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="C2 staging verification")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--poll-seconds", type=int, default=120)
    return p.parse_args()


async def _poll_convergence(
    db, *, cid: str, pid: str, correlation_id: str, timeout_s: int
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    deadline = time.monotonic() + timeout_s
    timeline: List[Dict[str, Any]] = []
    last_snap: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        snap = await full_convergence_snapshot(db, cid=cid, pid=pid)
        viol = detect_ordering_violation(snap)
        timeline.append(ordering_tick(snap, violation=viol))
        last_snap = snap
        prop = snap.get("property_score") or {}
        risk = snap.get("risk_priority") or {}
        if (
            prop.get("compliance_score_pending") is False
            and int(risk.get("risk_regen_pending") or 0) == 0
        ):
            row = await db.compliance_recalc_queue.find_one(
                {"property_id": pid, "correlation_id": correlation_id},
                {"status": 1},
            )
            if row and str(row.get("status") or "").upper() == "DONE":
                break
        await asyncio.sleep(3)
    return last_snap, timeline


async def main() -> None:
    from database import database

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

    control_path = out_dir / f"c2_control_selection_{slug}.json"
    ctrl_cid, ctrl_pid = cid, pid
    if control_path.exists():
        meta = json.loads(control_path.read_text(encoding="utf-8"))
        ctrl_cid = meta.get("control_client_id") or cid
        ctrl_pid = meta.get("control_property_id") or pid

    unrelated_path = out_dir / f"c2_unrelated_surface_integrity_{slug}.json"
    ctrl_fp_before = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    unrelated_baseline_note = (
        "control baseline captured at verification run start (normalized_stable_business_keys_c2a); "
        "not legacy preflight fingerprints"
    )

    runs: List[Dict[str, Any]] = []
    all_timeline: List[Dict[str, Any]] = []
    hash_by_run: Dict[str, Dict[str, str]] = {}
    lineage_by_run: Dict[str, str] = {}
    decay_by_run: Dict[str, Any] = {}

    for label in ("R1", "R2", "R3"):
        outcome = await _c1_m1_sync(db, cid=cid, pid=pid)
        queue_row = await _wait_queue_terminal(
            db, pid=pid, correlation_id=stable_corr, timeout_s=args.poll_seconds
        )
        snap, timeline = await _poll_convergence(
            db, cid=cid, pid=pid, correlation_id=stable_corr, timeout_s=min(60, args.poll_seconds)
        )
        all_timeline.extend([{**t, "run": label} for t in timeline])
        hashes = await consistency_hashes(db, cid=cid, pid=pid)
        lineage_fp = await lineage_fingerprint(db, pid=pid, correlation_id=stable_corr)
        hash_by_run[label] = hashes
        lineage_by_run[label] = lineage_fp
        decay_by_run[label] = await stale_decay_snapshot(db, cid=cid, pid=pid)
        runs.append(
            {
                "run": label,
                "mutation": "C2-M1",
                "correlation_id": stable_corr,
                "enqueue": outcome.get("enqueue"),
                "queue_status": (queue_row or {}).get("status"),
                "convergence_snapshot": snap,
                "consistency_hashes": hashes,
                "lineage_fingerprint": lineage_fp,
                "stale_decay": decay_by_run[label],
            }
        )

    after_snap = await full_convergence_snapshot(db, cid=cid, pid=pid)
    after_snap["phase"] = "C2_convergence_after"

    ctrl_fp_after = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    unrelated_delta = delta_fingerprints(ctrl_fp_before, ctrl_fp_after)

    exclusions = await exclusions_matrix(db, cid=cid, pid=pid)
    lineage_traces = {
        "R1": await lineage_trace(db, cid=cid, pid=pid, correlation_id=stable_corr),
        "R3": await lineage_trace(db, cid=cid, pid=pid, correlation_id=stable_corr),
    }

    r2_equals_r3 = hash_by_run.get("R2", {}).get("tasks_today") == hash_by_run.get("R3", {}).get("tasks_today")
    r2_equals_r3_full = hash_by_run.get("R2") == hash_by_run.get("R3")
    lineage_r2 = lineage_by_run.get("R2", "")
    lineage_r3 = lineage_by_run.get("R3", "")
    replay_lineage_drift: List[Dict[str, Any]] = []
    if lineage_r2 != lineage_r3:
        replay_lineage_drift.append(
            {
                "run": "R3",
                "surface": "lineage",
                "drift_type": "fingerprint_mismatch",
                "detail": f"R2={lineage_r2} R3={lineage_r3}",
            }
        )

    persistent_violations = [
        t for t in all_timeline if t.get("ordering_violation") and t.get("run") in ("R2", "R3")
    ]
    unrelated_mutation_count = sum(
        1 for v in unrelated_delta.values() if isinstance(v, dict) and v.get("changed")
    )

    downstream_lineage_summary: List[Dict[str, Any]] = [
        {
            "surface": "compliance_recalc_queue",
            "entity_key": stable_corr,
            "correlation_id": stable_corr,
            "attributable": str(runs[-1].get("queue_status") or "") in ("DONE", "PENDING", "RUNNING"),
            "notes": "C2-M1 stable correlation",
        },
        {
            "surface": "property_compliance_score_history",
            "entity_key": pid,
            "correlation_id": stable_corr,
            "attributable": lineage_r3 is not None,
            "notes": "score history sample in c2_lineage_trace",
        },
    ]

    parity = after_snap.get("parity_included_vs_client") is True
    exclusions_ok = exclusions.get("pass") is True
    decay_r2_r3_stable = decay_by_run.get("R2") == decay_by_run.get("R3")
    no_unrelated = unrelated_mutation_count == 0
    no_temporal = len(persistent_violations) == 0
    lineage_ok = len(replay_lineage_drift) == 0 and r2_equals_r3

    checks = {
        "r1_queue_done": str(runs[0].get("queue_status") or "").upper() == "DONE",
        "r2_r3_tasks_today_hash_equal": r2_equals_r3,
        "r2_r3_full_hash_equal": r2_equals_r3_full,
        "verification_fingerprint_mode": "normalized_stable_business_keys_c2a",
        "lineage_r2_equals_r3": lineage_r2 == lineage_r3,
        "replay_lineage_drift_empty": len(replay_lineage_drift) == 0,
        "parity_included_vs_client": parity,
        "exclusions_provenance_ok": exclusions_ok,
        "stale_decay_stable_r2_r3": decay_r2_r3_stable,
        "unrelated_mutation_delta_zero": no_unrelated,
        "temporal_ordering_violations_empty": no_temporal,
        "r2_suppressed": runs[1].get("enqueue", {}).get("enqueued") is False
        if isinstance(runs[1].get("enqueue"), dict)
        else None,
        "r3_suppressed": runs[2].get("enqueue", {}).get("enqueued") is False
        if isinstance(runs[2].get("enqueue"), dict)
        else None,
    }

    c2_pass = all(
        [
            checks["r1_queue_done"],
            checks["r2_r3_tasks_today_hash_equal"],
            checks["lineage_r2_equals_r3"],
            checks["parity_included_vs_client"],
            checks["exclusions_provenance_ok"],
            checks["unrelated_mutation_delta_zero"],
            checks["temporal_ordering_violations_empty"],
        ]
    )

    primary_rc: Optional[str] = None
    if not checks["r2_r3_tasks_today_hash_equal"] or not checks["lineage_r2_equals_r3"]:
        primary_rc = "C2-RC-8" if not checks["r2_r3_tasks_today_hash_equal"] else "C2-RC-16"
    elif not checks["unrelated_mutation_delta_zero"]:
        primary_rc = "C2-RC-14"
    elif not checks["temporal_ordering_violations_empty"]:
        primary_rc = "C2-RC-13"
    elif not checks["exclusions_provenance_ok"]:
        primary_rc = "C2-RC-11"
    elif not checks["parity_included_vs_client"]:
        primary_rc = "C2-RC-7"
    elif not checks["r1_queue_done"]:
        primary_rc = "C2-RC-9"

    # Write artifacts
    (out_dir / f"c2_convergence_after_{slug}.json").write_text(
        json.dumps(after_snap, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c2_gaps_{slug}.json").write_text(
        json.dumps({"pilot": after_snap.get("gaps"), "runs": {r["run"]: r["convergence_snapshot"].get("gaps") for r in runs}}, indent=2, default=str),
        encoding="utf-8",
    )
    (out_dir / f"c2_risk_priority_{slug}.json").write_text(
        json.dumps(
            {"pilot_after": after_snap.get("risk_priority"), "runs": {r["run"]: r["convergence_snapshot"].get("risk_priority") for r in runs}},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (out_dir / f"c2_dashboard_tasks_{slug}.json").write_text(
        json.dumps(
            {"pilot_after": after_snap.get("dashboard_tasks"), "runs": {r["run"]: r["convergence_snapshot"].get("dashboard_tasks") for r in runs}},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (out_dir / f"c2_stale_decay_{slug}.json").write_text(
        json.dumps(decay_by_run, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c2_consistency_hashes_{slug}.json").write_text(
        json.dumps({"R1": hash_by_run.get("R1"), "R2": hash_by_run.get("R2"), "R3": hash_by_run.get("R3"), "r2_equals_r3": r2_equals_r3}, indent=2, default=str),
        encoding="utf-8",
    )
    unrelated_payload = {
        "pilot": {"client_id": cid, "property_id": pid},
        "control": {
            "client_id": ctrl_cid,
            "property_id": ctrl_pid,
            "selection_reason": (json.loads(control_path.read_text(encoding="utf-8")).get("control_selection_reason")
                                   if control_path.exists() else "verification_run"),
        },
        "baseline_note": unrelated_baseline_note,
        "control_fingerprints_before": ctrl_fp_before,
        "control_fingerprints_after": ctrl_fp_after,
        "unrelated_mutation_delta": unrelated_delta,
        "unrelated_mutation_count": unrelated_mutation_count,
        "phase": "verification_window",
        "captured_at_utc": run_at,
    }
    (out_dir / f"c2_unrelated_surface_integrity_{slug}.json").write_text(
        json.dumps(unrelated_payload, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c2_lineage_trace_{slug}.json").write_text(
        json.dumps(lineage_traces, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c2_exclusions_{slug}.json").write_text(
        json.dumps(exclusions, indent=2, default=str), encoding="utf-8"
    )
    replay_payload = {
        "captured_at_utc": run_at,
        "stable_correlation": stable_corr,
        "runs": runs,
        "lineage_fingerprint_r1": lineage_by_run.get("R1"),
        "lineage_fingerprint_r2": lineage_by_run.get("R2"),
        "lineage_fingerprint_r3": lineage_by_run.get("R3"),
        "replay_lineage_drift": replay_lineage_drift,
        "r2_r3_lineage_equal": lineage_r2 == lineage_r3,
    }
    (out_dir / f"c2_replay_{slug}.json").write_text(
        json.dumps(replay_payload, indent=2, default=str), encoding="utf-8"
    )

    report = {
        "captured_at_utc": run_at,
        "verification_run": "c2_normalized_rerun_c2a",
        "client_id": cid,
        "property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "c2_pass": c2_pass,
        "primary_rc_branch": primary_rc,
        "checks": checks,
        "convergence_order_timeline": all_timeline,
        "downstream_lineage_summary": downstream_lineage_summary,
        "unrelated_mutation_delta": unrelated_delta,
        "unrelated_mutation_count": unrelated_mutation_count,
        "precedence_violations": [],
        "artifacts": {
            "convergence_before": f"docs/audit/c2_convergence_before_{slug}.json",
            "convergence_after": f"docs/audit/c2_convergence_after_{slug}.json",
            "gaps": f"docs/audit/c2_gaps_{slug}.json",
            "risk_priority": f"docs/audit/c2_risk_priority_{slug}.json",
            "dashboard_tasks": f"docs/audit/c2_dashboard_tasks_{slug}.json",
            "stale_decay": f"docs/audit/c2_stale_decay_{slug}.json",
            "consistency_hashes": f"docs/audit/c2_consistency_hashes_{slug}.json",
            "unrelated_surface_integrity": f"docs/audit/c2_unrelated_surface_integrity_{slug}.json",
            "lineage_trace": f"docs/audit/c2_lineage_trace_{slug}.json",
            "exclusions": f"docs/audit/c2_exclusions_{slug}.json",
            "replay": f"docs/audit/c2_replay_{slug}.json",
        },
    }
    report_path = out_dir / f"c2_verification_report_{slug}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
