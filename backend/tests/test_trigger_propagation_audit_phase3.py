from __future__ import annotations

from services.trigger_propagation_audit import (
    BLOCKED,
    CACHE_INVALIDATION_UNKNOWN,
    COMPLIANCE_CRITICAL,
    CONDITIONAL,
    CONSUMERS,
    INSUFFICIENT_EVIDENCE,
    NO_OPERATIONAL_FOLLOWTHROUGH,
    READY,
    WAIVER_ALLOWED_FOR_ANALYTICS_ONLY,
    WAIVER_NOT_ALLOWED,
    build_consumer_rollout_gate_profiles,
    build_expected_vs_current_matrix,
    build_trigger_propagation_audit_phase3_snapshot,
    write_trigger_propagation_audit_phase3_json,
    _minimum_evidence_met_for_consumer,
    _waiver_policy_for_blocker,
)


def test_rollout_state_classification_deterministic():
    profiles = build_consumer_rollout_gate_profiles()
    assert len(profiles) == len(CONSUMERS)
    by_name = {p["consumer"]: p["rollout_state"] for p in profiles}
    assert by_name["REMINDER_ENGINE"] == BLOCKED
    assert by_name["SLA_ESCALATION_PATHS"] == BLOCKED
    assert by_name["PRIORITY_ACTIONS"] == BLOCKED
    assert by_name["COMMAND_CENTER"] == READY
    assert by_name["REQUIREMENT_LIST"] == READY
    assert by_name["CACHE_INVALIDATION_REFRESH"] == INSUFFICIENT_EVIDENCE
    assert by_name["PROPERTY_SUMMARY"] == READY
    assert by_name["TODAY_VIEW"] == CONDITIONAL


def test_minimum_evidence_thresholds():
    matrix = build_expected_vs_current_matrix()
    cache_rows = [r for r in matrix if r["consumer"] == "CACHE_INVALIDATION_REFRESH"]
    ok, detail = _minimum_evidence_met_for_consumer(cache_rows, "CACHE_INVALIDATION_REFRESH")
    assert ok is False
    assert detail["row_count"] == len(cache_rows)
    assert detail["non_unknown_confidence_rows"] < 8


def test_waiver_policy_classification():
    assert (
        _waiver_policy_for_blocker(CACHE_INVALIDATION_UNKNOWN, COMPLIANCE_CRITICAL, "REMINDER_ENGINE")
        == WAIVER_NOT_ALLOWED
    )
    assert (
        _waiver_policy_for_blocker(NO_OPERATIONAL_FOLLOWTHROUGH, COMPLIANCE_CRITICAL, "REMINDER_ENGINE")
        == WAIVER_NOT_ALLOWED
    )
    assert (
        _waiver_policy_for_blocker(NO_OPERATIONAL_FOLLOWTHROUGH, COMPLIANCE_CRITICAL, "REQUIREMENT_LIST")
        != WAIVER_NOT_ALLOWED
    )


def test_grouped_summary_stability():
    snap = build_trigger_propagation_audit_phase3_snapshot()
    g = snap["grouped_summaries"]
    keys = (
        "consumers_by_rollout_state",
        "consumers_by_highest_criticality",
        "blockers_by_consumer",
        "waiver_eligibility_by_consumer",
        "safest_rollout_candidates",
        "consumers_blocked_from_semantic_aware_rollout",
    )
    for k in keys:
        assert k in g
    states = g["consumers_by_rollout_state"]
    assert list(states.keys()) == sorted(states.keys())
    assert set(states.get(BLOCKED, [])) == {"PRIORITY_ACTIONS", "REMINDER_ENGINE", "SLA_ESCALATION_PATHS"}
    safest = g["safest_rollout_candidates"]
    assert safest[0]["consumer"] == safest[0]["consumer"]
    assert all("score" in x for x in safest)


def test_phase3_artifact_shape_and_non_behavioral_contract():
    snap = build_trigger_propagation_audit_phase3_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    assert snap["remaining_state_model_limitation"]
    assert snap["remaining_runtime_convergence_limitation"]
    assert snap["minimum_evidence_thresholds"]["min_rows_per_consumer"] == 13
    for p in snap["consumer_rollout_profiles"]:
        for k in (
            "consumer",
            "rollout_state",
            "criticality_mix",
            "blocked_transition_count",
            "high_risk_gap_count",
            "unknown_refresh_count",
            "semantic_collapse_risk_count",
            "minimum_evidence_met",
            "waiver_eligible",
            "blocker_reasons",
            "recommended_next_action",
        ):
            assert k in p
        assert isinstance(p["blocker_reasons"], list)


def test_write_phase3_json_roundtrip(tmp_path):
    path = tmp_path / "phase3.json"
    written = write_trigger_propagation_audit_phase3_json(target_path=path)
    assert written == path
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text


def test_waiver_summary_uses_deterministic_policies():
    snap = build_trigger_propagation_audit_phase3_snapshot()
    ws = snap["waiver_policy_summary"]
    assert WAIVER_NOT_ALLOWED in ws or WAIVER_ALLOWED_FOR_ANALYTICS_ONLY in ws
