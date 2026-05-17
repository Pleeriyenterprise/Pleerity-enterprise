"""
D1 staging verification: propagation fanout integrity (R1–R3 + optional M2).

  python -m scripts.d1_staging_verification \\
    --client-id CID --property-id PID --out-dir docs/audit

D1b rerun (preserve original d1_* artifacts):

  python -m scripts.d1_staging_verification \\
    --artifact-prefix d1b --verification-run d1b_harness_rerun
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.c1_staging_verification import _wait_queue_terminal  # noqa: E402
from scripts.c2_snapshot import delta_fingerprints, unrelated_fingerprints  # noqa: E402
from scripts.d1_snapshot import (  # noqa: E402
    analyze_run,
    bounded_growth_analysis,
    compare_runs,
    detect_primary_rc,
    lineage_fingerprint,
    propagation_replay_lineage_fingerprint,
    lineage_trace,
    observability_counts,
    observability_noise_snapshot,
    propagation_completion_matrix,
    replay_collapse_analysis,
    suppression_fingerprint,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D1 staging verification")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--poll-seconds", type=int, default=120)
    p.add_argument("--skip-m2", action="store_true")
    p.add_argument(
        "--artifact-prefix",
        default="d1",
        help="Artifact filename prefix (use d1b for D1b rerun without overwriting d1_*)",
    )
    p.add_argument(
        "--verification-run",
        default="d1_staging_rev3",
        help="Report verification_run label",
    )
    return p.parse_args()


def _artifact_name(prefix: str, stem: str, slug: str) -> str:
    return f"{prefix}_{stem}_{slug}.json"


async def _build_fanout_stub(db, *, cid: str, pid: str, correlation_id: str, origin: str) -> Dict[str, Any]:
    from services.requirement_transition_observability import build_transition_fanout_trace

    req = await db.requirements.find_one(
        {"client_id": cid, "property_id": pid},
        {"_id": 0, "requirement_id": 1},
    )
    rid = str((req or {}).get("requirement_id") or f"property:{pid}")
    stub = {
        "status": "PENDING",
        "due_date": None,
        "evidence_state": "X",
        "evidence_authority": {"version": 1, "state": "EA_MISSING"},
    }
    return build_transition_fanout_trace(
        transition_id=f"d1-{origin}-{pid}-{uuid.uuid4().hex[:8]}",
        correlation_id=correlation_id,
        transition_origin=origin,
        requirement_id=rid,
        property_id=pid,
        client_id=cid,
        before_requirement=stub,
        after_requirement=dict(stub),
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )


async def _d1_m1(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.authority_mutation_fanout import enqueue_compliance_recalc_with_fanout
    from services.compliance_recalc_queue import ACTOR_CLIENT, TRIGGER_PROPERTY_UPDATED
    from services.provisioning import provisioning_service
    from services.requirement_materialization_service import materialize_requirements_for_property

    correlation_id = f"REQUIREMENTS_SYNC:{pid}"
    origin = "D1_VERIFICATION:REQUIREMENTS_SYNC"
    fanout = await _build_fanout_stub(db, cid=cid, pid=pid, correlation_id=correlation_id, origin=origin)
    mat = await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
    await provisioning_service._update_property_compliance(pid)
    await enqueue_compliance_recalc_with_fanout(
        fanout,
        property_id=pid,
        client_id=cid,
        trigger_reason=TRIGGER_PROPERTY_UPDATED,
        actor_type=ACTOR_CLIENT,
        actor_id=None,
        correlation_id=correlation_id,
        trigger_origin=origin,
        propagation_stage="d1_m1:recalc_enqueue",
    )
    return {
        "mutation": "D1-M1",
        "correlation_id": correlation_id,
        "materialize": mat,
        "transition_fanout": fanout,
    }


async def _d1_m2(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.authority_mutation_fanout import enqueue_compliance_recalc_with_fanout
    from services.compliance_recalc_queue import ACTOR_ADMIN, TRIGGER_ADMIN_MANUAL_JOB
    from services.provisioning import provisioning_service
    from services.requirement_materialization_service import materialize_requirements_for_property

    correlation_id = f"{TRIGGER_ADMIN_MANUAL_JOB}:REGISTRY_SYNC:{pid}:{uuid.uuid4().hex[:12]}"
    origin = "D1_VERIFICATION:ADMIN_REGISTRY_SYNC"
    fanout = await _build_fanout_stub(db, cid=cid, pid=pid, correlation_id=correlation_id, origin=origin)
    mat = await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
    await provisioning_service._update_property_compliance(pid)
    await enqueue_compliance_recalc_with_fanout(
        fanout,
        property_id=pid,
        client_id=cid,
        trigger_reason=TRIGGER_ADMIN_MANUAL_JOB,
        actor_type=ACTOR_ADMIN,
        actor_id=None,
        correlation_id=correlation_id,
        trigger_origin=origin,
        propagation_stage="d1_m2:recalc_enqueue",
    )
    return {
        "mutation": "D1-M2",
        "correlation_id": correlation_id,
        "materialize": mat,
        "transition_fanout": fanout,
    }


def _orphan_check(fanout: Optional[Dict[str, Any]], queue_row: Optional[Dict[str, Any]]) -> bool:
    from scripts.d1_snapshot import extract_downstream_rows

    for row in extract_downstream_rows(fanout):
        if row.get("enqueue_attempted") is True and not row.get("duplicate_suppression_reason"):
            if queue_row and str(queue_row.get("status") or "").upper() in ("DONE", "PENDING", "RUNNING"):
                return True
            return False
    return True


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


async def main() -> None:
    from database import database

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    slug = args.slug_suffix
    prefix = args.artifact_prefix.strip().rstrip("_")
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()
    stable_corr = f"REQUIREMENTS_SYNC:{pid}"

    control_path = out_dir / _artifact_name("d1", "control_selection", slug)
    ctrl_cid, ctrl_pid = cid, pid
    if control_path.exists():
        meta = json.loads(control_path.read_text(encoding="utf-8"))
        ctrl_cid = meta.get("control_client_id") or cid
        ctrl_pid = meta.get("control_property_id") or pid

    ctrl_fp_before = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    prior_overlay_fp: Optional[str] = None

    runs: List[Dict[str, Any]] = []
    cardinality_summary: List[Dict[str, Any]] = []
    all_behaviours: List[Dict[str, Any]] = []
    all_delegated: List[Dict[str, Any]] = []

    for label in ("R1", "R2", "R3"):
        noise_run_before = await observability_counts(db, cid=cid, pid=pid, correlation_id=stable_corr)
        outcome = await _d1_m1(db, cid=cid, pid=pid)
        queue_row = await _wait_queue_terminal(
            db, pid=pid, correlation_id=stable_corr, timeout_s=args.poll_seconds
        )
        fanout = outcome.get("transition_fanout")
        analyzed = analyze_run(fanout, run_label=label, is_replay=label != "R1")
        analyzed["mutation"] = outcome.get("mutation")
        analyzed["correlation_id"] = outcome.get("correlation_id")
        analyzed["enqueue_materialize"] = outcome.get("materialize")
        analyzed["queue_status"] = (queue_row or {}).get("status")
        analyzed["global_lineage_fingerprint"] = await lineage_fingerprint(
            db, pid=pid, correlation_id=stable_corr
        )
        analyzed["lineage_fingerprint"] = propagation_replay_lineage_fingerprint(analyzed)
        analyzed["orphan_fanout_pass"] = _orphan_check(fanout, queue_row)

        overlay_after = suppression_fingerprint(fanout)
        overlay_before = prior_overlay_fp if prior_overlay_fp is not None else overlay_after
        noise_run_after = await observability_counts(db, cid=cid, pid=pid, correlation_id=stable_corr)
        analyzed["observability_noise"] = observability_noise_snapshot(
            before=noise_run_before,
            after=noise_run_after,
            overlay_fp_before=overlay_before,
            overlay_fp_after=overlay_after,
            replay_phase=(label != "R1"),
            overlay_baseline_mode="prior_replay_state",
        )
        prior_overlay_fp = overlay_after

        analyzed["propagation_completion_matrix"] = propagation_completion_matrix(
            fanout,
            downstream_ready={"recalc_queue": bool(queue_row)},
        )
        cardinality_summary.append({**analyzed["branch_cardinality"], "run": label, "mutation": "D1-M1"})
        all_behaviours.extend(analyzed.get("behaviour_classes") or [])
        all_delegated.extend(analyzed.get("delegated_lineage") or [])
        runs.append(analyzed)
        if label == "R1":
            await asyncio.sleep(2)

    lineage_r2 = runs[1].get("lineage_fingerprint") if len(runs) > 1 else ""
    lineage_r3 = runs[2].get("lineage_fingerprint") if len(runs) > 2 else ""
    lineage_replay_stable = lineage_r2 == lineage_r3 and bool(lineage_r2)
    lineage_replay_trace = await lineage_trace(db, cid=cid, pid=pid, correlation_id=stable_corr)

    m2_run: Optional[Dict[str, Any]] = None
    m2_lineage_trace: Optional[Dict[str, Any]] = None
    if not args.skip_m2:
        m2_out = await _d1_m2(db, cid=cid, pid=pid)
        m2_corr = str(m2_out.get("correlation_id"))
        m2_queue = await _wait_queue_terminal(db, pid=pid, correlation_id=m2_corr, timeout_s=args.poll_seconds)
        m2_run = analyze_run(m2_out.get("transition_fanout"), run_label="M2", is_replay=False)
        m2_run["mutation"] = "D1-M2"
        m2_run["correlation_id"] = m2_corr
        m2_run["queue_status"] = (m2_queue or {}).get("status")
        m2_run["lineage_fingerprint"] = await lineage_fingerprint(db, pid=pid, correlation_id=m2_corr)
        m2_lineage_trace = await lineage_trace(db, cid=cid, pid=pid, correlation_id=m2_corr)
        m2_lineage_trace["phase"] = "m2_legitimate_new_correlation"
        cardinality_summary.append({**m2_run["branch_cardinality"], "run": "M2", "mutation": "D1-M2"})
        all_behaviours.extend(m2_run.get("behaviour_classes") or [])
        all_delegated.extend(m2_run.get("delegated_lineage") or [])

    collapse = replay_collapse_analysis(runs)
    growth = bounded_growth_analysis(runs)
    suppression = compare_runs(runs)
    partial_rows: List[Dict[str, Any]] = []
    partial_reason: Optional[str] = None
    for r in runs:
        matrix = r.get("propagation_completion_matrix") or []
        partial_rows.extend(matrix)
        for row in matrix:
            if row.get("expected") and row.get("fanout_observed") and not row.get("downstream_complete"):
                partial_reason = partial_reason or f"incomplete:{row.get('branch')}"

    behaviour_pass = all(b.get("behaviour_match", True) for b in all_behaviours)
    delegated_pass = all(not d.get("detached") for d in all_delegated)
    cardinality_pass = all(
        c.get("cardinality_pass", False) for c in cardinality_summary if c.get("run") in ("R1", "R2", "R3")
    )
    replay_noise = [r for r in runs if r.get("run") in ("R2", "R3")]
    noise_pass = all((r.get("observability_noise") or {}).get("noise_pass", True) for r in replay_noise)

    ctrl_fp_after = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    unrelated_delta = delta_fingerprints(ctrl_fp_before, ctrl_fp_after)
    unrelated_count = sum(1 for v in unrelated_delta.values() if isinstance(v, dict) and v.get("changed"))

    checks = {
        "cardinality_pass": cardinality_pass,
        "partial_convergence_pass": partial_reason is None,
        "collapse_deterministic": collapse.get("collapse_deterministic", False),
        "delegated_lineage_pass": delegated_pass,
        "noise_pass": noise_pass,
        "behaviour_classes_pass": behaviour_pass,
        "bounded_growth_pass": growth.get("bounded_growth_pass", False),
        "suppression_replay_equal": suppression.get("suppression_replay_equal", False),
        "orphan_fanout_pass": all(r.get("orphan_fanout_pass", True) for r in runs),
        "lineage_replay_stable": lineage_replay_stable,
        "lineage_m2_observed": m2_run is not None,
        "unrelated_mutation_delta_zero": unrelated_count == 0,
        "r2_r3_fanout_fingerprint_equal": (
            runs[1].get("fanout_row_fingerprint") == runs[2].get("fanout_row_fingerprint")
            if len(runs) > 2
            else False
        ),
    }
    d1_pass = all(checks.values())
    primary_rc = detect_primary_rc(
        {
            **checks,
            "lineage_stable": checks["lineage_replay_stable"],
        }
    ) if not d1_pass else None

    report = {
        "captured_at_utc": run_at,
        "verification_run": args.verification_run,
        "parent_unit": "D1",
        "micro_unit": "D1b" if prefix == "d1b" else None,
        "harness_refinements": [
            "observability_noise_prior_replay_overlay_baseline",
            "lineage_replay_window_pre_m2",
            "propagation_replay_lineage_correlation_attributed",
        ],
        "client_id": cid,
        "property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "d1_pass": d1_pass,
        "primary_rc_branch": primary_rc,
        "checks": checks,
        "lineage_replay": {
            "scope": "correlation_attributed_propagation_replay",
            "R2_fingerprint": lineage_r2,
            "R3_fingerprint": lineage_r3,
            "replay_stable": lineage_replay_stable,
            "R2_global_lineage_fingerprint": runs[1].get("global_lineage_fingerprint") if len(runs) > 1 else None,
            "R3_global_lineage_fingerprint": runs[2].get("global_lineage_fingerprint") if len(runs) > 2 else None,
        },
        "lineage_m2_correlation": (m2_run or {}).get("correlation_id"),
        "propagation_cardinality_summary": cardinality_summary,
        "propagation_completion_matrix": partial_rows,
        "partial_convergence_reason": partial_reason,
        "replay_collapse_state": collapse.get("replay_collapse_state"),
        "suppressed_replay_branches": collapse.get("suppressed_replay_branches"),
        "retained_lineage_visibility": collapse.get("retained_lineage_visibility"),
        "branch_growth_curve": growth.get("branch_growth_curve"),
        "bounded_growth_pass": growth.get("bounded_growth_pass"),
        "suppression_replay_equal": suppression.get("suppression_replay_equal"),
        "governed_mutations": ["D1-M1", "D1-M2"] if m2_run else ["D1-M1"],
        "production_path_observation": {
            "route": "POST /api/properties/{property_id}/requirements/sync",
            "production_enqueue": "enqueue_compliance_recalc (direct)",
            "verification_driver_enqueue": "enqueue_compliance_recalc_with_fanout",
            "classification": "expected_c1_only_queue_behaviour_on_production_http",
            "governance": "open_context_only_not_remediated_in_d1b",
        },
        "prior_d1_artifacts_preserved": f"docs/audit/d1_verification_report_{slug}.json",
    }

    def ap(stem: str) -> str:
        return f"docs/audit/{_artifact_name(prefix, stem, slug)}"

    report["artifacts"] = {
        "fanout_after": ap("fanout_after"),
        "propagation_replay": ap("propagation_replay"),
        "propagation_topology": ap("propagation_topology"),
        "branch_cardinality": ap("branch_cardinality"),
        "branch_behaviour_classes": ap("branch_behaviour_classes"),
        "partial_convergence": ap("partial_convergence"),
        "delegated_lineage": ap("delegated_lineage"),
        "suppression_determinism": ap("suppression_determinism"),
        "observability_noise": ap("observability_noise"),
        "bounded_growth": ap("bounded_growth"),
        "lineage_trace_replay": ap("lineage_trace_replay"),
        "lineage_trace_m2": ap("lineage_trace_m2"),
        "unrelated_surface_integrity": ap("unrelated_surface_integrity"),
        "verification_report": ap("verification_report"),
    }

    replay_payload = {"runs": runs, "replay_collapse": collapse, "m2": m2_run}
    topology = {
        "runs": [
            {
                "run": r.get("run"),
                "mutation": r.get("mutation"),
                "downstream_targets": (r.get("branch_cardinality") or {}).get("downstream_targets"),
            }
            for r in runs
        ]
    }

    _write_json(out_dir / _artifact_name(prefix, "fanout_after", slug), runs[-1].get("transition_fanout"))
    _write_json(out_dir / _artifact_name(prefix, "propagation_replay", slug), replay_payload)
    _write_json(out_dir / _artifact_name(prefix, "propagation_topology", slug), topology)
    _write_json(out_dir / _artifact_name(prefix, "branch_cardinality", slug), cardinality_summary)
    _write_json(out_dir / _artifact_name(prefix, "branch_behaviour_classes", slug), all_behaviours)
    _write_json(
        out_dir / _artifact_name(prefix, "partial_convergence", slug),
        {
            "propagation_completion_matrix": partial_rows,
            "partial_convergence_reason": partial_reason,
        },
    )
    _write_json(out_dir / _artifact_name(prefix, "delegated_lineage", slug), all_delegated)
    _write_json(
        out_dir / _artifact_name(prefix, "suppression_determinism", slug),
        {**suppression, "suppression_fingerprint_r1_r2_r3": suppression.get("suppression_fingerprint_r1_r2_r3")},
    )
    _write_json(
        out_dir / _artifact_name(prefix, "observability_noise", slug),
        [r.get("observability_noise") for r in runs],
    )
    _write_json(out_dir / _artifact_name(prefix, "bounded_growth", slug), growth)
    _write_json(out_dir / _artifact_name(prefix, "lineage_trace_replay", slug), lineage_replay_trace)
    if m2_lineage_trace:
        _write_json(out_dir / _artifact_name(prefix, "lineage_trace_m2", slug), m2_lineage_trace)
    _write_json(
        out_dir / _artifact_name(prefix, "unrelated_surface_integrity", slug),
        {
            "phase": "verification_window",
            "captured_at_utc": run_at,
            "control_fingerprints_before": ctrl_fp_before,
            "control_fingerprints_after": ctrl_fp_after,
            "unrelated_mutation_delta": unrelated_delta,
            "unrelated_mutation_count": unrelated_count,
        },
    )
    _write_json(out_dir / _artifact_name(prefix, "verification_report", slug), report)

    print(json.dumps({"d1_pass": d1_pass, "primary_rc_branch": primary_rc, "checks": checks}, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
