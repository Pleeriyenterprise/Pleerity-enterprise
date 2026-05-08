from __future__ import annotations

from services.operational_confirmation_topology_audit import (
    BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT,
    COMPLIANCE_CONFIRMATION_CRITICAL,
    CONSUMERS,
    DETERMINISTIC_ACKNOWLEDGEMENT,
    DETERMINISTIC_CONFIRMATION,
    INFERRED_ACKNOWLEDGEMENT,
    NEAR_REAL_TIME_CONFIRMATION,
    UX_CONFIRMATION_ONLY,
    SEMANTIC_TRANSITIONS,
    UNKNOWN_CONFIRMATION_BOUNDARY,
    build_operational_confirmation_expected_vs_current_matrix,
    build_operational_confirmation_topology_phase2_snapshot,
    write_operational_confirmation_topology_phase2_json,
)


def _cell(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"missing {transition}/{consumer}")


def test_expected_contract_stability():
    m = build_operational_confirmation_expected_vs_current_matrix()
    assert len(m) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    req = _cell(m, "VERIFIED_CURRENT", "REQUIREMENT_LIST")
    assert req["expected_confirmation_quality"] == DETERMINISTIC_CONFIRMATION
    assert req["expected_confirmation_freshness"] == NEAR_REAL_TIME_CONFIRMATION
    assert req["confirmation_criticality"] == UX_CONFIRMATION_ONLY
    for k in (
        "expected_operational_confirmation_required",
        "expected_acknowledgement_required",
        "expected_stale_detection_required",
        "expected_retry_owner_required",
        "expected_confirmation_confidence",
    ):
        assert k in req


def test_criticality_classification():
    m = build_operational_confirmation_expected_vs_current_matrix()
    rem = _cell(m, "EXPIRY_REVIEW_REQUIRED", "REMINDER_ENGINE")
    assert rem["confirmation_criticality"] == COMPLIANCE_CONFIRMATION_CRITICAL


def test_freshness_and_ack_guarantee_classification():
    m = build_operational_confirmation_expected_vs_current_matrix()
    req = _cell(m, "MISSING", "REQUIREMENT_LIST")
    assert req["current_acknowledgement_guarantee"] == DETERMINISTIC_ACKNOWLEDGEMENT
    assert req["expected_acknowledgement_guarantee"] in (
        DETERMINISTIC_ACKNOWLEDGEMENT,
        "LIKELY_ACKNOWLEDGEMENT",
        INFERRED_ACKNOWLEDGEMENT,
    )
    assert "current_confirmation_freshness_effective" in req


def test_gap_and_blocker_classification():
    m = build_operational_confirmation_expected_vs_current_matrix()
    cache = _cell(m, "MISSING", "CACHE_INVALIDATION_REFRESH")
    assert UNKNOWN_CONFIRMATION_BOUNDARY in cache["runtime_confirmation_blocker_reasons"]
    assert cache["runtime_confirmation_enforcement_blocked"] is True


def test_grouped_summary_stability():
    snap = build_operational_confirmation_topology_phase2_snapshot()
    assert "safest_confirmation_rollout_candidates" in snap
    assert "highest_risk_confirmation_paths" in snap
    assert "blocked_confirmation_consumers" in snap
    assert snap["confirmation_gap_summary"]
    assert snap["promotion_blocker_summary"]


def test_phase2_artifact_shape_and_audit_only():
    snap = build_operational_confirmation_topology_phase2_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    row = snap["confirmation_expected_vs_current_matrix"][0]
    for k in (
        "confirmation_gap_classification",
        "confirmation_freshness_mismatch",
        "confirmation_acknowledgement_mismatch",
        "stale_detection_mismatch",
        "retry_owner_mismatch",
        "runtime_confirmation_enforcement_blocked",
        "runtime_confirmation_blocker_reasons",
        "expected_confirmation_quality",
        "expected_confirmation_freshness",
    ):
        assert k in row


def test_write_phase2_json(tmp_path):
    p = tmp_path / "p2.json"
    write_operational_confirmation_topology_phase2_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text


def test_blocked_enforcement_gap_present():
    m = build_operational_confirmation_expected_vs_current_matrix()
    blocked = [r for r in m if r["confirmation_gap_classification"] == BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT]
    assert len(blocked) >= 1
