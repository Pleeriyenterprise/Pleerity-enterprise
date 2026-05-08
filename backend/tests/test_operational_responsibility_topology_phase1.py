from __future__ import annotations

from services.operational_responsibility_topology_audit import (
    CLEAR_SINGLE_OWNER,
    CONSUMERS,
    CRITICAL_TOPOLOGY_RISK,
    FRAGMENTED,
    LOW_TOPOLOGY_RISK,
    SEMANTIC_TRANSITIONS,
    build_operational_responsibility_topology_matrix,
    build_operational_responsibility_topology_phase1_snapshot,
    write_operational_responsibility_topology_phase1_json,
)


def _cell(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"missing {transition}/{consumer}")


def test_ownership_classification_stability():
    m = build_operational_responsibility_topology_matrix()
    assert len(m) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    req = _cell(m, "MISSING", "REQUIREMENT_LIST")
    assert req["detection_owner"] == "SEMANTIC_AUTHORITY"
    assert req["propagation_owner"] == "READ_PROJECTION"
    assert req["visibility_owner"] == "USER_VISIBILITY"
    assert req["ownership_quality"] == CLEAR_SINGLE_OWNER


def test_ownership_quality_stability():
    m = build_operational_responsibility_topology_matrix()
    rem = _cell(m, "EXPIRY_REVIEW_REQUIRED", "REMINDER_ENGINE")
    assert rem["ownership_quality"] in (FRAGMENTED, "AMBIGUOUS", "SHARED_BUT_DEFINED")


def test_failure_mode_and_handoff_stability():
    m = build_operational_responsibility_topology_matrix()
    cache = _cell(m, "MISSING", "CACHE_INVALIDATION_REFRESH")
    assert "UNKNOWN_REFRESH_BOUNDARY" in cache["topology_failure_modes"]
    assert cache["undefined_handoff_boundary"] is True
    assert cache["handoff_count"] >= 1


def test_topology_risk_stability():
    m = build_operational_responsibility_topology_matrix()
    low = _cell(m, "MISSING", "REQUIREMENT_LIST")
    assert low["topology_risk"] in (LOW_TOPOLOGY_RISK, "MODERATE_TOPOLOGY_RISK")


def test_phase1_artifact_shape_and_audit_only():
    snap = build_operational_responsibility_topology_phase1_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    for k in (
        "ownership_topology_matrix",
        "ownership_quality_summary",
        "topology_failure_summary",
        "handoff_chain_summary",
        "highest_risk_topology_paths",
        "safest_topology_paths",
        "semantic_transition_risk_ranking",
        "remaining_state_model_limitation",
        "remaining_runtime_convergence_limitation",
    ):
        assert k in snap
    row = snap["ownership_topology_matrix"][0]
    for k in (
        "detection_owner",
        "propagation_owner",
        "refresh_owner",
        "operational_followthrough_owner",
        "visibility_owner",
        "escalation_owner",
        "fallback_owner",
        "ownership_quality",
        "topology_failure_modes",
        "handoff_chain",
        "handoff_count",
        "topology_risk",
        "operational_followthrough_analysis",
    ):
        assert k in row


def test_semantic_transition_ranking_includes_extremes():
    snap = build_operational_responsibility_topology_phase1_snapshot()
    worst = snap["semantic_transition_risk_ranking"]["most_dangerous_semantic_transitions"]
    best = snap["semantic_transition_risk_ranking"]["safest_semantic_transitions"]
    assert len(worst) >= 1
    assert len(best) >= 1
    assert worst[0]["worst_case_risk"] == CRITICAL_TOPOLOGY_RISK


def test_write_phase1_json(tmp_path):
    p = tmp_path / "topo.json"
    write_operational_responsibility_topology_phase1_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text
