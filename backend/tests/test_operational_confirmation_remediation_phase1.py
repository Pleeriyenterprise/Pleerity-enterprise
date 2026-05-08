from __future__ import annotations

from services.operational_confirmation_topology_audit import (
    ACCEPTABLE_RISK,
    CACHE_INVALIDATION_REMEDIATION,
    COMPLIANCE_CONFIRMATION_CRITICAL,
    CONSUMERS,
    CRITICAL_IMMEDIATE,
    HARD_BLOCKER,
    MONITOR_ONLY,
    NON_BLOCKING,
    PLATFORM_INFRASTRUCTURE_OWNER,
    REPORTING_SEMANTIC_REMEDIATION,
    SEMANTIC_COLLAPSE_DEBT,
    SEMANTIC_CONFIRMATION_COLLAPSE_RISK,
    SEMANTIC_TRANSITIONS,
    UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT,
    build_operational_confirmation_remediation_matrix,
    build_operational_confirmation_remediation_phase1_snapshot,
    write_operational_confirmation_remediation_phase1_json,
)


def _cell(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"missing {transition}/{consumer}")


def test_remediation_classification_stability():
    m = build_operational_confirmation_remediation_matrix()
    assert len(m) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    req = _cell(m, "VERIFIED_CURRENT", "REQUIREMENT_LIST")
    assert req["primary_remediation_category"] == ACCEPTABLE_RISK
    assert req["secondary_remediation_categories"] == []


def test_ownership_classification_stability():
    m = build_operational_confirmation_remediation_matrix()
    cache = _cell(m, "MISSING", "CACHE_INVALIDATION_REFRESH")
    assert cache["primary_remediation_category"] == CACHE_INVALIDATION_REMEDIATION
    assert cache["remediation_owner"] == PLATFORM_INFRASTRUCTURE_OWNER


def test_urgency_and_blocker_severity():
    m = build_operational_confirmation_remediation_matrix()
    req_sat = _cell(m, "MISSING", "REQUIREMENT_LIST")
    assert req_sat["remediation_urgency"] == MONITOR_ONLY
    assert req_sat["enforcement_blocker_severity"] == NON_BLOCKING


def test_acceptable_risk_and_root_cause():
    m = build_operational_confirmation_remediation_matrix()
    row = next(
        r
        for r in m
        if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in (r.get("runtime_confirmation_blocker_reasons") or [])
    )
    assert row["primary_remediation_category"] == REPORTING_SEMANTIC_REMEDIATION
    assert row["root_cause_family"] == SEMANTIC_COLLAPSE_DEBT


def test_grouped_summary_stability():
    snap = build_operational_confirmation_remediation_phase1_snapshot()
    assert "must_block_runtime_enforcement" in snap
    assert "orchestration_debt_clusters" in snap
    assert "remediation_priority_ranking" in snap
    assert "fragmented_confirmation_summary" in snap
    assert snap["remediation_owner_summary"]


def test_phase_remediation_artifact_shape_and_audit_only():
    snap = build_operational_confirmation_remediation_phase1_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    row = snap["remediation_matrix"][0]
    for k in (
        "primary_remediation_category",
        "secondary_remediation_categories",
        "remediation_owner",
        "remediation_owner_confidence",
        "remediation_urgency",
        "enforcement_blocker_severity",
        "enforcement_blocker_reasoning",
        "acceptable_risk_classification",
        "root_cause_family",
    ):
        assert k in row


def test_must_block_contains_high_severity():
    snap = build_operational_confirmation_remediation_phase1_snapshot()
    assert len(snap["must_block_runtime_enforcement"]) >= 1
    assert any(
        x.get("acceptable_risk_classification") == UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT
        or x.get("enforcement_blocker_severity") == HARD_BLOCKER
        for x in snap["must_block_runtime_enforcement"]
    )


def test_priority_ranking_orders_critical_first():
    snap = build_operational_confirmation_remediation_phase1_snapshot()
    pr = snap["remediation_priority_ranking"]
    assert pr[0]["remediation_urgency"] == CRITICAL_IMMEDIATE


def test_write_remediation_json(tmp_path):
    p = tmp_path / "rem.json"
    write_operational_confirmation_remediation_phase1_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text


def test_compliance_row_remediation_urgency():
    m = build_operational_confirmation_remediation_matrix()
    rem = _cell(m, "EXPIRY_REVIEW_REQUIRED", "REMINDER_ENGINE")
    assert rem["confirmation_criticality"] == COMPLIANCE_CONFIRMATION_CRITICAL
    assert rem["remediation_urgency"] in (CRITICAL_IMMEDIATE, "HIGH_PRIORITY")
