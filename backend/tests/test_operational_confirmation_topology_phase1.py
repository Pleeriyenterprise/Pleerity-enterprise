from __future__ import annotations

from services.operational_confirmation_topology_audit import (
    CONSUMERS,
    CRITICAL_CONFIRMATION_RISK,
    DETERMINISTIC_CONFIRMATION,
    DOCUMENT_CONFIRMATION,
    INTENT_INITIATOR,
    LOW_CONFIRMATION_RISK,
    SEMANTIC_TRANSITIONS,
    UNKNOWN_CONFIRMATION_BOUNDARY,
    build_operational_confirmation_topology_matrix,
    build_operational_confirmation_topology_phase1_snapshot,
    write_operational_confirmation_topology_phase1_json,
)


def _cell(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"missing {transition}/{consumer}")


def test_confirmation_ownership_stability():
    m = build_operational_confirmation_topology_matrix()
    assert len(m) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    req = _cell(m, "MISSING", "REQUIREMENT_LIST")
    assert req["intent_owner"] == INTENT_INITIATOR
    assert req["confirmation_owner"] == DOCUMENT_CONFIRMATION
    for k in (
        "intent_owner",
        "dispatch_owner",
        "confirmation_owner",
        "closure_owner",
        "stale_state_detection_owner",
        "retry_owner",
        "fallback_confirmation_owner",
    ):
        assert k in req


def test_confirmation_quality_stability():
    m = build_operational_confirmation_topology_matrix()
    req = _cell(m, "VERIFIED_CURRENT", "REQUIREMENT_LIST")
    assert req["confirmation_quality"] == DETERMINISTIC_CONFIRMATION


def test_failure_mode_and_handoff_stability():
    m = build_operational_confirmation_topology_matrix()
    cache = _cell(m, "MISSING", "CACHE_INVALIDATION_REFRESH")
    assert UNKNOWN_CONFIRMATION_BOUNDARY in cache["confirmation_failure_modes"]
    assert cache["undefined_confirmation_boundary"] is True
    assert cache["confirmation_handoff_count"] >= 1


def test_confirmation_risk_stability():
    m = build_operational_confirmation_topology_matrix()
    req = _cell(m, "MISSING", "REQUIREMENT_LIST")
    assert req["confirmation_risk"] in (LOW_CONFIRMATION_RISK, "MODERATE_CONFIRMATION_RISK")


def test_phase1_artifact_shape_and_audit_only():
    snap = build_operational_confirmation_topology_phase1_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    for k in (
        "confirmation_topology_matrix",
        "confirmation_quality_summary",
        "confirmation_failure_summary",
        "confirmation_handoff_summary",
        "highest_risk_confirmation_paths",
        "safest_confirmation_paths",
        "stale_confirmation_findings",
        "semantic_transition_confirmation_ranking",
        "operational_reality_gap_summary",
        "remaining_state_model_limitation",
        "remaining_runtime_convergence_limitation",
    ):
        assert k in snap
    row = snap["confirmation_topology_matrix"][0]
    assert "operational_reality_gaps" in row
    assert "confirmation_handoff_chain" in row


def test_reality_gaps_shape():
    snap = build_operational_confirmation_topology_phase1_snapshot()
    g = snap["confirmation_topology_matrix"][0]["operational_reality_gaps"]
    for k in (
        "assumes_completion_without_explicit_confirmation",
        "infers_closure_from_read_projection",
        "lacks_confirmation_ownership",
        "lacks_stale_state_detection",
        "depends_on_periodic_sweep",
        "depends_on_user_revisit",
        "depends_on_human_reconciliation",
        "operational_closure_can_silently_fail",
    ):
        assert k in g


def test_ranking_includes_critical_worst_case():
    snap = build_operational_confirmation_topology_phase1_snapshot()
    worst = snap["semantic_transition_confirmation_ranking"]["most_dangerous_by_semantic_transition"]
    assert len(worst) >= 1
    assert worst[0]["worst_case_confirmation_risk"] == CRITICAL_CONFIRMATION_RISK


def test_write_confirmation_json(tmp_path):
    p = tmp_path / "conf.json"
    write_operational_confirmation_topology_phase1_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text
