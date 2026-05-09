"""Phase 2: read-only recalc join + convergence correlation (synthetic data only)."""

from __future__ import annotations

from services.workflow_runtime_convergence_observability import (
    JOIN_AMBIGUOUS,
    JOIN_CONFIRMED,
    JOIN_NOT_VISIBLE,
    JOIN_PROBABLE,
    JOIN_WEAK,
    RECONCILIATION_CHAIN_VISIBLE,
    classify_reconciliation_chain,
    SETTLEMENT_CONFIRMED,
    SETTLEMENT_DEGRADED,
    SETTLEMENT_PENDING,
    build_convergence_join_operational_summary,
    build_queue_settlement_visibility_summary,
    build_recalc_joined_convergence_snapshot,
    join_transition_traces_with_recalc_jobs,
)
from services.requirement_transition_observability import (
    ENQUEUE_ACCEPTED,
    transition_origin_outcome_engine,
)


def _trace(
    *,
    cid: str,
    pid: str,
    cl: str,
    rid: str = "r1",
    downstream: list | None = None,
):
    return {
        "transition_id": "tid",
        "correlation_id": cid,
        "property_id": pid,
        "client_id": cl,
        "requirement_id": rid,
        "transition_origin": transition_origin_outcome_engine("test"),
        "transition_outcome": "TRANSITION_APPLIED",
        "downstream_trigger_targets": downstream or [],
        "downstream_propagation": [
            {
                "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                "propagation_degraded_possible": False,
            }
        ],
        "partial_downstream_failure": False,
    }


def test_join_confirmed_exact_correlation():
    tr = _trace(cid="ROOT:1", pid="p1", cl="c1")
    jobs = [
        {"_id": "j1", "property_id": "p1", "client_id": "c1", "correlation_id": "ROOT:1", "status": "DONE"},
    ]
    rows = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=jobs)
    assert rows[0]["join_classification"] == JOIN_CONFIRMED
    assert rows[0]["settlement_linkage"] == SETTLEMENT_CONFIRMED


def test_join_probable_trace_extends_job_correlation():
    tr = _trace(cid="ROOT:1:authority:r1", pid="p1", cl="c1")
    jobs = [
        {"_id": "j1", "property_id": "p1", "client_id": "c1", "correlation_id": "ROOT:1", "status": "PENDING"},
    ]
    rows = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=jobs)
    assert rows[0]["join_classification"] == JOIN_PROBABLE
    assert rows[0]["settlement_linkage"] == SETTLEMENT_PENDING
    assert rows[0]["stale_read_risk_visible"] is True


def test_join_weak_substring_correlation():
    tr = _trace(cid="ZZROOT99", pid="p1", cl="c1")
    jobs = [
        {"_id": "j1", "property_id": "p1", "client_id": "c1", "correlation_id": "ROOT", "status": "DONE"},
    ]
    rows = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=jobs)
    assert rows[0]["join_classification"] == JOIN_WEAK


def test_join_not_visible_enqueue_pending_unknown_settlement():
    tr = _trace(
        cid="orphan",
        pid="p1",
        cl="c1",
        downstream=[
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "enqueue_outcome": ENQUEUE_ACCEPTED,
                "enqueue_attempted": True,
            }
        ],
    )
    rows = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=[])
    assert rows[0]["join_classification"] == JOIN_NOT_VISIBLE
    assert rows[0]["settlement_linkage"] == SETTLEMENT_PENDING


def test_join_ambiguous_two_jobs_same_correlation():
    tr = _trace(cid="DUP", pid="p1", cl="c1")
    jobs = [
        {"_id": "a", "property_id": "p1", "client_id": "c1", "correlation_id": "DUP", "status": "DONE"},
        {"_id": "b", "property_id": "p1", "client_id": "c1", "correlation_id": "DUP", "status": "PENDING"},
    ]
    rows = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=jobs)
    assert rows[0]["join_classification"] == JOIN_AMBIGUOUS


def test_dead_job_settlement_degraded():
    tr = _trace(cid="X", pid="p1", cl="c1")
    jobs = [{"_id": "j1", "property_id": "p1", "client_id": "c1", "correlation_id": "X", "status": "DEAD"}]
    rows = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=jobs)
    assert rows[0]["settlement_linkage"] == SETTLEMENT_DEGRADED
    assert rows[0]["dead_job_present"] is True


def test_reconciliation_chain_visible_duplicate_and_dead():
    tr = _trace(cid="Y", pid="p1", cl="c1")
    tr["downstream_trigger_targets"] = [
        {"enqueue_outcome": "ENQUEUE_DUPLICATE_SUPPRESSED", "downstream_target": "q"},
        {"enqueue_outcome": "ENQUEUE_ACCEPTED", "downstream_target": "risk_signal_regen_queue.enqueue_risk_signal_regen"},
    ]
    jobs = [
        {
            "_id": "j1",
            "property_id": "p1",
            "client_id": "c1",
            "correlation_id": "Y",
            "status": "DEAD",
            "recalc_execution_signals": {"reconciliation_recommended": True},
        }
    ]
    assert classify_reconciliation_chain(tr, jobs) == RECONCILIATION_CHAIN_VISIBLE


def test_bounded_max_jobs_scanned_truncates():
    tr = _trace(cid="MATCHME", pid="p1", cl="c1")
    jobs = [
        {"_id": "only", "property_id": "p1", "client_id": "c1", "correlation_id": "AAA", "status": "DONE"},
        {"_id": "extra", "property_id": "p1", "client_id": "c1", "correlation_id": "MATCHME", "status": "DONE"},
    ]
    rows = join_transition_traces_with_recalc_jobs(
        transition_traces=[tr],
        recalc_queue_jobs=jobs,
        max_jobs_scanned=1,
    )
    assert rows[0]["join_classification"] == JOIN_NOT_VISIBLE


def test_joined_snapshot_determinism():
    tr1 = _trace(cid="A", pid="p1", cl="c1", rid="r1")
    tr2 = _trace(cid="B", pid="p1", cl="c1", rid="r2")
    jobs = [
        {"_id": "1", "property_id": "p1", "client_id": "c1", "correlation_id": "A", "status": "DONE"},
        {"_id": "2", "property_id": "p1", "client_id": "c1", "correlation_id": "B", "status": "DONE"},
    ]
    s1 = build_recalc_joined_convergence_snapshot(
        transition_traces=[tr1, tr2],
        recalc_queue_jobs=jobs,
        generated_at_iso="2026-05-08T00:00:00Z",
    )
    s2 = build_recalc_joined_convergence_snapshot(
        transition_traces=[tr1, tr2],
        recalc_queue_jobs=list(reversed(jobs)),
        generated_at_iso="2026-05-08T00:00:00Z",
    )
    assert s1["joined_rows"] == s2["joined_rows"]


def test_queue_visibility_enqueue_without_join_count():
    tr = _trace(cid="only-trace", pid="p1", cl="c1", downstream=[{"enqueue_outcome": ENQUEUE_ACCEPTED, "enqueue_attempted": True}])
    joined = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=[])
    qv = build_queue_settlement_visibility_summary(
        recalc_queue_jobs=[{"_id": "x", "property_id": "p9", "client_id": "c9", "correlation_id": "orphan-queue", "status": "PENDING"}],
        joined_rows=joined,
        transition_traces=[tr],
    )
    assert qv["trace_enqueue_accepted_without_queue_join_count"] == 1


def test_operational_summary_strongest():
    tr = _trace(cid="S", pid="p1", cl="c1")
    jobs = [{"_id": "j", "property_id": "p1", "client_id": "c1", "correlation_id": "S", "status": "DONE"}]
    joined = join_transition_traces_with_recalc_jobs(transition_traces=[tr], recalc_queue_jobs=jobs)
    op = build_convergence_join_operational_summary(
        joined_rows=joined,
        transition_traces=[tr],
        recalc_queue_jobs=jobs,
    )
    assert "automated_outcome_authority" in op["strongest_joined_workflows"]
