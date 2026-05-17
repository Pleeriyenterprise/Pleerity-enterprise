"""D1 §12 contract tests (mocked — no staging Mongo required)."""
from __future__ import annotations

from scripts.d1_snapshot import (
    analyze_run,
    bounded_growth_analysis,
    branch_cardinality,
    classify_branch_behaviours,
    compare_runs,
    detect_primary_rc,
    fanout_row_fingerprint,
    propagation_replay_lineage_fingerprint,
    replay_collapse_analysis,
    suppression_fingerprint,
)


def _fanout_with_rows(rows):
    return {"correlation_id": "REQUIREMENTS_SYNC:pid", "downstream_rows": rows}


def test_branch_cardinality_zero_unexpected_on_clean_fanout():
    fanout = _fanout_with_rows(
        [
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "propagation_stage": "test",
                "enqueue_attempted": True,
            },
            {
                "downstream_target": "risk_signal_regen_queue.enqueue_risk_signal_regen",
                "propagation_stage": "test:regen",
                "enqueue_attempted": True,
            },
        ]
    )
    card = branch_cardinality(fanout)
    assert card["unexpected_branch_count"] == 0


def test_behaviour_class_replay_collapsible_on_duplicate():
    fanout = _fanout_with_rows(
        [
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "duplicate_suppression_reason": "duplicate_pending",
                "enqueue_attempted": False,
            }
        ]
    )
    behaviours = classify_branch_behaviours(fanout, run_label="R2", is_replay=True)
    assert behaviours[0]["propagation_behaviour_class"] == "replay-collapsible"
    assert behaviours[0]["behaviour_match"] is True


def test_replay_collapse_deterministic_r2_r3():
    row = {
        "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
        "duplicate_suppression_reason": "duplicate_pending",
        "enqueue_attempted": False,
    }
    runs = [
        {"run": "R1", "transition_fanout": _fanout_with_rows([{**row, "enqueue_attempted": True}])},
        {"run": "R2", "transition_fanout": _fanout_with_rows([row])},
        {"run": "R3", "transition_fanout": _fanout_with_rows([row])},
    ]
    collapse = replay_collapse_analysis(runs)
    assert collapse["collapse_deterministic"] is True
    assert collapse["retained_lineage_visibility"] is True


def test_bounded_growth_stable_on_replay():
    row = {"downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc", "enqueue_attempted": False}
    runs = [
        {"run": "R1", "transition_fanout": _fanout_with_rows([row]), "branch_cardinality": {"actual_branch_count": 2}},
        {"run": "R2", "transition_fanout": _fanout_with_rows([row]), "branch_cardinality": {"actual_branch_count": 2}},
        {"run": "R3", "transition_fanout": _fanout_with_rows([row]), "branch_cardinality": {"actual_branch_count": 2}},
    ]
    growth = bounded_growth_analysis(runs)
    assert growth["branch_growth_delta"] == 0
    assert growth["bounded_growth_pass"] is True


def test_suppression_replay_equal():
    fp = suppression_fingerprint(_fanout_with_rows([{"duplicate_suppression_reason": "duplicate_pending"}]))
    runs = [
        {"run": "R1", "transition_fanout": _fanout_with_rows([]), "suppression_fingerprint": fp},
        {"run": "R2", "transition_fanout": _fanout_with_rows([]), "suppression_fingerprint": fp},
        {"run": "R3", "transition_fanout": _fanout_with_rows([]), "suppression_fingerprint": fp},
    ]
    out = compare_runs(runs)
    assert out["suppression_replay_equal"] is True


def test_fanout_row_fingerprint_stable():
    rows = [{"downstream_target": "a", "propagation_stage": "s", "enqueue_attempted": True}]
    assert fanout_row_fingerprint(rows) == fanout_row_fingerprint(rows)


def test_detect_primary_rc_cardinality_fail():
    rc = detect_primary_rc({"cardinality_pass": False, "bounded_growth_pass": True})
    assert rc == "D1-RC-11"


def test_propagation_replay_lineage_stable_r2_r3():
    row = {
        "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
        "duplicate_suppression_reason": "duplicate_pending",
        "enqueue_attempted": False,
        "propagation_stage": "d1_m1:recalc_enqueue",
    }
    regen = {
        "downstream_target": "risk_signal_regen_queue.enqueue_risk_signal_regen",
        "enqueue_attempted": True,
        "propagation_stage": "d1_m1:regen",
    }
    fanout = _fanout_with_rows([row, regen])
    r2 = analyze_run(fanout, run_label="R2", is_replay=True)
    r3 = analyze_run(fanout, run_label="R3", is_replay=True)
    r2["correlation_id"] = "REQUIREMENTS_SYNC:pid"
    r3["correlation_id"] = "REQUIREMENTS_SYNC:pid"
    r2["queue_status"] = "DONE"
    r3["queue_status"] = "DONE"
    fp2 = propagation_replay_lineage_fingerprint(r2)
    fp3 = propagation_replay_lineage_fingerprint(r3)
    assert fp2 == fp3
    assert fp2
