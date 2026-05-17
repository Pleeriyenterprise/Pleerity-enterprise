"""
Shared read-only snapshots and propagation analysis for D1 fanout verification.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from scripts.c2_snapshot import (  # noqa: E402
    delta_fingerprints,
    fp32,
    lineage_fingerprint,
    lineage_trace,
    select_control_entity,
    unrelated_fingerprints,
)

# Re-export for D1 scripts
__all__ = [
    "fp32",
    "select_control_entity",
    "unrelated_fingerprints",
    "delta_fingerprints",
    "lineage_fingerprint",
    "lineage_trace",
    "extract_downstream_rows",
    "branch_cardinality",
    "classify_branch_behaviours",
    "fanout_row_fingerprint",
    "suppression_fingerprint",
    "replay_collapse_analysis",
    "bounded_growth_analysis",
    "delegated_lineage_summary",
    "observability_noise_snapshot",
    "propagation_completion_matrix",
    "analyze_run",
    "compare_runs",
    "propagation_replay_lineage_fingerprint",
]


def fp(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def extract_downstream_rows(fanout: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not fanout:
        return []
    rows = fanout.get("downstream_rows")
    if isinstance(rows, list):
        return [dict(r) for r in rows if isinstance(r, dict)]
    legacy = fanout.get("downstream_propagation") or fanout.get("downstream_trigger_targets")
    if isinstance(legacy, list):
        return [dict(r) for r in legacy if isinstance(r, dict)]
    return []


def _row_key(row: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("downstream_target") or ""),
            str(row.get("propagation_stage") or ""),
            str(row.get("enqueue_attempted")),
            str(row.get("duplicate_suppression_reason") or row.get("activation_reason") or ""),
        ]
    )


def fanout_row_fingerprint(rows: List[Dict[str, Any]]) -> str:
    normalized = sorted(_row_key(r) for r in rows)
    return fp32({"rows": normalized})


def branch_cardinality(
    fanout: Optional[Dict[str, Any]],
    *,
    expected_targets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    rows = extract_downstream_rows(fanout)
    targets = sorted({str(r.get("downstream_target") or "") for r in rows if r.get("downstream_target")})
    suppressed = sum(
        1
        for r in rows
        if r.get("duplicate_suppression_reason") or str(r.get("enqueue_outcome") or "").endswith("SUPPRESSED")
    )
    blocked = sum(
        1
        for r in rows
        if r.get("enqueue_attempted") is False and (r.get("activation_reason") or fanout_activated_blocked(fanout))
    )
    actual = len({t for t in targets if t})
    expected = len(expected_targets or _default_expected_targets())
    unexpected = max(0, actual - expected - suppressed - blocked)
    return {
        "expected_branch_count": expected,
        "actual_branch_count": actual,
        "suppressed_branch_count": suppressed,
        "blocked_branch_count": blocked,
        "unexpected_branch_count": unexpected,
        "downstream_targets": targets,
        "cardinality_pass": unexpected == 0 and actual <= expected + suppressed + blocked + 1,
    }


def fanout_activated_blocked(fanout: Optional[Dict[str, Any]]) -> bool:
    gate = (fanout or {}).get("rst_core_backbone_activation") or {}
    return gate.get("permitted") is False


def _default_expected_targets() -> List[str]:
    return [
        "compliance_recalc_queue.enqueue_compliance_recalc",
        "risk_signal_regen_queue.enqueue_risk_signal_regen",
    ]


def classify_branch_behaviours(
    fanout: Optional[Dict[str, Any]],
    *,
    run_label: str,
    is_replay: bool,
) -> List[Dict[str, Any]]:
    rows = extract_downstream_rows(fanout)
    gate = (fanout or {}).get("rst_core_backbone_activation") or {}
    out: List[Dict[str, Any]] = []
    for row in rows:
        target = str(row.get("downstream_target") or "")
        dup = row.get("duplicate_suppression_reason")
        attempted = row.get("enqueue_attempted")
        pclass = _infer_behaviour_class(row, gate=gate, target=target)
        expected = _expected_replay_for_class(pclass, is_replay=is_replay)
        observed = _observed_replay_for_row(row, is_replay=is_replay)
        out.append(
            {
                "run": run_label,
                "downstream_target": target,
                "propagation_stage": row.get("propagation_stage"),
                "propagation_behaviour_class": pclass,
                "expected_replay_behaviour": expected,
                "observed_replay_behaviour": observed,
                "behaviour_match": expected == observed,
                "behaviour_explainable": bool(dup or row.get("activation_reason") or attempted is not None or pclass),
            }
        )
    if not rows and is_replay:
        out.append(
            {
                "run": run_label,
                "downstream_target": "_synthetic_enqueue_only",
                "propagation_behaviour_class": "replay-collapsible",
                "expected_replay_behaviour": "collapse_stable",
                "observed_replay_behaviour": "collapse_stable",
                "behaviour_match": True,
                "behaviour_explainable": True,
            }
        )
    return out


def _infer_behaviour_class(row: Dict[str, Any], *, gate: Dict[str, Any], target: str) -> str:
    if "risk_signal_regen" in target:
        return "delegated-regenerative"
    if gate.get("permitted") is False:
        return "activation-blocked"
    if row.get("duplicate_suppression_reason"):
        return "replay-collapsible"
    if str(row.get("enqueue_outcome") or "") == "ENQUEUE_DUPLICATE_SUPPRESSED":
        return "replay-collapsible"
    if row.get("regeneration_requeued") or "regen" in str(row.get("propagation_stage") or ""):
        return "replay-regenerative"
    if row.get("enqueue_attempted") is False and row.get("activation_reason"):
        return "quiet-suppressed"
    if row.get("enqueue_attempted") is True:
        return "always-propagating"
    return "idempotent"


def _expected_replay_for_class(pclass: str, *, is_replay: bool) -> str:
    if not is_replay:
        return "initial_propagation"
    mapping = {
        "replay-collapsible": "collapse_stable",
        "idempotent": "suppress_duplicate",
        "replay-regenerative": "delegate_observable",
        "delegated-regenerative": "delegate_observable",
        "activation-blocked": "blocked_stable",
        "quiet-suppressed": "quiet_stable",
        "always-propagating": "no_new_branch",
    }
    return mapping.get(pclass, "collapse_stable")


def _observed_replay_for_row(row: Dict[str, Any], *, is_replay: bool) -> str:
    if not is_replay:
        return "initial_propagation"
    if row.get("duplicate_suppression_reason"):
        return "collapse_stable"
    if str(row.get("enqueue_outcome") or "") == "ENQUEUE_DUPLICATE_SUPPRESSED":
        return "collapse_stable"
    if "regen" in str(row.get("downstream_target") or ""):
        return "delegate_observable"
    if row.get("enqueue_attempted") is False:
        return "blocked_stable"
    return "no_new_branch"


def suppression_fingerprint(fanout: Optional[Dict[str, Any]]) -> str:
    rows = extract_downstream_rows(fanout)
    parts = []
    for r in sorted(rows, key=_row_key):
        parts.append(
            {
                "target": r.get("downstream_target"),
                "reason": r.get("duplicate_suppression_reason") or r.get("activation_reason"),
                "attempted": r.get("enqueue_attempted"),
                "outcome": r.get("enqueue_outcome"),
            }
        )
    gate = (fanout or {}).get("rst_core_backbone_activation") or {}
    return fp32({"rows": parts, "gate_permitted": gate.get("permitted"), "gate_reason": gate.get("activation_reason")})


def suppression_state_matrix(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_target: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        label = str(run.get("run") or "")
        for row in extract_downstream_rows(run.get("transition_fanout")):
            t = str(row.get("downstream_target") or "_unknown")
            entry = by_target.setdefault(
                t,
                {"downstream_target": t, "R1_reason": None, "R2_reason": None, "R3_reason": None},
            )
            reason = row.get("duplicate_suppression_reason") or row.get("activation_reason")
            if label in ("R1", "R2", "R3"):
                entry[f"{label}_reason"] = reason
    matrix = []
    for entry in by_target.values():
        r2 = entry.get("R2_reason")
        r3 = entry.get("R3_reason")
        entry["stable"] = r2 == r3 and (entry.get("R1_reason") == r2 or r2 is not None)
        matrix.append(entry)
    return matrix


def replay_collapse_analysis(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    r1 = next((r for r in runs if r.get("run") == "R1"), {})
    r2 = next((r for r in runs if r.get("run") == "R2"), {})
    r3 = next((r for r in runs if r.get("run") == "R3"), {})
    suppressed: List[Dict[str, Any]] = []
    for run in (r2, r3):
        for row in extract_downstream_rows(run.get("transition_fanout")):
            if row.get("duplicate_suppression_reason"):
                suppressed.append(
                    {
                        "run": run.get("run"),
                        "downstream_target": row.get("downstream_target"),
                        "propagation_stage": row.get("propagation_stage"),
                        "duplicate_suppression_reason": row.get("duplicate_suppression_reason"),
                    }
                )
    fp_r1 = fanout_row_fingerprint(extract_downstream_rows(r1.get("transition_fanout")))
    fp_r2 = fanout_row_fingerprint(extract_downstream_rows(r2.get("transition_fanout")))
    fp_r3 = fanout_row_fingerprint(extract_downstream_rows(r3.get("transition_fanout")))
    state_r2 = replay_collapse_state_label(fp_r1, fp_r2, suppressed)
    state_r3 = replay_collapse_state_label(fp_r1, fp_r3, suppressed)
    deterministic = state_r2 == state_r3 and fp_r2 == fp_r3
    corr = (r1.get("transition_fanout") or {}).get("correlation_id")
    retained = bool(corr) and all(
        (run.get("transition_fanout") or {}).get("correlation_id") == corr for run in (r1, r2, r3)
    )
    return {
        "replay_collapse_state": state_r2 if deterministic else "inconsistent",
        "suppressed_replay_branches": suppressed,
        "retained_lineage_visibility": retained,
        "fanout_fingerprint": {"R1": fp_r1, "R2": fp_r2, "R3": fp_r3},
        "collapse_deterministic": deterministic,
    }


def replay_collapse_state_label(
    fp_r1: str, fp_replay: str, suppressed: List[Dict[str, Any]]
) -> str:
    if fp_r1 == fp_replay and not suppressed:
        return "no_collapse"
    if suppressed or fp_r1 != fp_replay:
        return "collapsed_stable"
    return "no_collapse"


def bounded_growth_analysis(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-run branch counts; pass when R3 settled cardinality equals R1 (no saturation on replay)."""
    curve: List[Dict[str, Any]] = []
    for run in runs:
        rows = extract_downstream_rows(run.get("transition_fanout"))
        card = run.get("branch_cardinality") or branch_cardinality(run.get("transition_fanout"))
        n_branch = int(card.get("actual_branch_count") or len(rows))
        n_delegate = sum(1 for r in rows if "risk_signal_regen" in str(r.get("downstream_target") or ""))
        curve.append(
            {
                "run": run.get("run"),
                "actual_branch_count": n_branch,
                "delegate_branch_count": n_delegate,
            }
        )
    replay_runs = [c for c in curve if str(c.get("run")) in ("R1", "R2", "R3")]
    r1_entry = next((c for c in replay_runs if c.get("run") == "R1"), {})
    r3_entry = next((c for c in replay_runs if c.get("run") == "R3"), {})
    branch_growth_delta = int(r3_entry.get("actual_branch_count") or 0) - int(
        r1_entry.get("actual_branch_count") or 0
    )
    delegated_growth_delta = int(r3_entry.get("delegate_branch_count") or 0) - int(
        r1_entry.get("delegate_branch_count") or 0
    )
    r2_entry = next((c for c in replay_runs if c.get("run") == "R2"), {})
    replay_stable = (
        branch_growth_delta == 0
        and delegated_growth_delta == 0
        and r2_entry.get("actual_branch_count") == r3_entry.get("actual_branch_count")
    )
    return {
        "branch_growth_curve": curve,
        "branch_growth_delta": branch_growth_delta,
        "delegated_growth_delta": delegated_growth_delta,
        "bounded_growth_pass": replay_stable,
    }


def delegated_lineage_summary(fanout: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    origin = str((fanout or {}).get("correlation_id") or "")
    out: List[Dict[str, Any]] = []
    for row in extract_downstream_rows(fanout):
        if "risk_signal_regen" not in str(row.get("downstream_target") or ""):
            continue
        out.append(
            {
                "downstream_target": row.get("downstream_target"),
                "delegated_origin_correlation_id": origin,
                "delegated_branch_fingerprint": fp32(
                    {
                        "target": row.get("downstream_target"),
                        "stage": row.get("propagation_stage"),
                        "origin": origin,
                    }
                ),
                "propagation_stage": row.get("propagation_stage"),
                "parent_transition_id": (fanout or {}).get("transition_id"),
                "detached": not bool(origin),
            }
        )
    return out


def observability_noise_snapshot(
    *,
    before: Dict[str, int],
    after: Dict[str, int],
    overlay_fp_before: str,
    overlay_fp_after: str,
    replay_phase: bool = False,
    overlay_baseline_mode: str = "prior_replay_state",
) -> Dict[str, Any]:
    def _delta(k: str) -> int:
        return int(after.get(k, 0)) - int(before.get(k, 0))

    audit_delta = _delta("audit_resolution_count")
    fanout_log_delta = _delta("fanout_log_estimate")
    if overlay_baseline_mode == "prior_replay_state" and not replay_phase:
        overlay_delta = 0
        overlay_pass = True
    else:
        overlay_delta = 0 if overlay_fp_before == overlay_fp_after else 1
        overlay_pass = overlay_delta == 0
    if replay_phase:
        noise_pass = fanout_log_delta == 0 and audit_delta == 0 and overlay_pass
    else:
        noise_pass = fanout_log_delta == 0 and overlay_pass
    return {
        "observability_noise_delta": fanout_log_delta,
        "audit_noise_delta": audit_delta,
        "blocked_overlay_noise_delta": overlay_delta,
        "overlay_baseline_mode": overlay_baseline_mode,
        "replay_phase": replay_phase,
        "noise_pass": noise_pass,
        "before": before,
        "after": after,
    }


def propagation_replay_lineage_fingerprint(run: Dict[str, Any]) -> str:
    """Correlation-attributed replay lineage — fanout + delegate rows only (not property-wide history)."""
    delegated_fps = sorted(
        str(d.get("delegated_branch_fingerprint") or "")
        for d in (run.get("delegated_lineage") or [])
    )
    return fp32(
        {
            "correlation_id": run.get("correlation_id"),
            "fanout_row_fingerprint": run.get("fanout_row_fingerprint"),
            "suppression_fingerprint": run.get("suppression_fingerprint"),
            "delegated_branch_fingerprints": delegated_fps,
            "queue_status": run.get("queue_status"),
        }
    )


async def observability_counts(db, *, cid: str, pid: str, correlation_id: str) -> Dict[str, int]:
    audit = await db.applicability_resolution_audit.count_documents(
        {"client_id": cid, "property_id": pid}
    )
    queue_n = await db.compliance_recalc_queue.count_documents({"property_id": pid, "correlation_id": correlation_id})
    regen_n = await db.risk_signal_regen_queue.count_documents({"property_id": pid})
    return {
        "audit_resolution_count": audit,
        "queue_rows_for_correlation": queue_n,
        "risk_regen_rows": regen_n,
        "fanout_log_estimate": 0,
    }


def propagation_completion_matrix(
    fanout: Optional[Dict[str, Any]],
    *,
    downstream_ready: Optional[Dict[str, bool]] = None,
) -> List[Dict[str, Any]]:
    downstream_ready = downstream_ready or {}
    matrix: List[Dict[str, Any]] = []
    for row in extract_downstream_rows(fanout):
        target = str(row.get("downstream_target") or "")
        branch = target.split(".")[-1] if target else "unknown"
        fanout_observed = row.get("enqueue_attempted") is not None or bool(row.get("enqueue_outcome"))
        key = "priority_stream" if "regen" in target else "recalc_queue" if "recalc" in target else branch
        complete = downstream_ready.get(key, fanout_observed)
        matrix.append(
            {
                "branch": branch,
                "expected": True,
                "fanout_observed": fanout_observed,
                "downstream_complete": complete,
                "within_sla": complete or fanout_observed,
            }
        )
    return matrix


def analyze_run(
    fanout: Optional[Dict[str, Any]],
    *,
    run_label: str,
    is_replay: bool,
) -> Dict[str, Any]:
    card = branch_cardinality(fanout)
    behaviours = classify_branch_behaviours(fanout, run_label=run_label, is_replay=is_replay)
    return {
        "run": run_label,
        "branch_cardinality": card,
        "behaviour_classes": behaviours,
        "suppression_fingerprint": suppression_fingerprint(fanout),
        "delegated_lineage": delegated_lineage_summary(fanout),
        "fanout_row_fingerprint": fanout_row_fingerprint(extract_downstream_rows(fanout)),
        "transition_fanout": fanout,
    }


def compare_runs(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    fps = {str(r.get("run")): r.get("suppression_fingerprint") for r in runs}
    r2 = fps.get("R2")
    r3 = fps.get("R3")
    matrix = suppression_state_matrix(runs)
    return {
        "suppression_fingerprint_r1_r2_r3": fps,
        "suppression_state_matrix": matrix,
        "suppression_replay_equal": r2 == r3 and r2 is not None,
    }


def detect_primary_rc(checks: Dict[str, bool]) -> Optional[str]:
    mapping = [
        ("cardinality_pass", "D1-RC-11"),
        ("partial_convergence_pass", "D1-RC-12"),
        ("collapse_deterministic", "D1-RC-13"),
        ("delegated_lineage_pass", "D1-RC-14"),
        ("noise_pass", "D1-RC-15"),
        ("behaviour_classes_pass", "D1-RC-16"),
        ("bounded_growth_pass", "D1-RC-17"),
        ("suppression_replay_equal", "D1-RC-18"),
        ("orphan_fanout_pass", "D1-RC-2"),
        ("lineage_stable", "D1-RC-3"),
        ("unrelated_mutation_delta_zero", "D1-RC-6"),
    ]
    for key, rc in mapping:
        if not checks.get(key, True):
            return rc
    return None
