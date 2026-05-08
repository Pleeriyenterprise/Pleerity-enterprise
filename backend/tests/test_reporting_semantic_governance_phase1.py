from __future__ import annotations

import hashlib
import json

from services.reporting_semantic_governance_audit import (
    CLIENT_STATUS_CHIP,
    EXPORT_BLOCKED_PENDING_GOVERNANCE,
    EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT,
    NO_DISCLAIMER_REQUIRED,
    PROPERTY_SUMMARY,
    REPORT_EXPORT,
    SAFE_FOR_DIRECT_REPRESENTATION,
    SEMANTIC_TRANSITIONS,
    UNSAFE_FOR_SIMPLIFIED_REPORTING,
    build_reporting_semantic_governance_matrix,
    build_reporting_semantic_governance_phase1_snapshot,
    write_reporting_semantic_governance_phase1_json,
)


def _matrix_fingerprint(matrix):
    payload = [
        (
            r["semantic_transition"],
            r["consumer"],
            r["representation_safety"],
            r["semantic_collapse_risk"],
            r["compliant_language_allowed"],
            r["current_language_allowed"],
            tuple(r["required_contexts"]),
            tuple(r["prohibited_wording"]),
            r["disclaimer_requirement"],
            r["report_trust_risk"],
            r["export_readiness"],
            r["reporting_governance_blocked"],
            tuple(r["reporting_governance_blockers"]),
            r["compliant_language_governance"],
            r["current_language_governance"],
        )
        for r in matrix
    ]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def _cell(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"missing {transition}/{consumer}")


def test_governance_matrix_shape_and_size():
    m = build_reporting_semantic_governance_matrix()
    assert len(m) == len(SEMANTIC_TRANSITIONS) * 6
    row = m[0]
    for k in (
        "representation_safety",
        "semantic_collapse_risk",
        "compliant_language_allowed",
        "current_language_allowed",
        "required_contexts",
        "prohibited_wording",
        "disclaimer_requirement",
        "report_trust_risk",
        "export_readiness",
        "reporting_governance_blocked",
        "reporting_governance_blockers",
        "governance_triage_source_consumer",
        "compliant_language_governance",
        "current_language_governance",
    ):
        assert k in row


def test_classification_stability():
    m = build_reporting_semantic_governance_matrix()
    assert _matrix_fingerprint(m) == (
        "33a5d2dd337c06a057dc8263fa17f77a5ec54f5a66c360ad3712b92e2eb37ae0"
    )


def test_client_status_chip_uses_property_summary_triage_proxy():
    m = build_reporting_semantic_governance_matrix()
    chip = _cell(m, "VERIFIED_CURRENT", CLIENT_STATUS_CHIP)
    prop = _cell(m, "VERIFIED_CURRENT", PROPERTY_SUMMARY)
    assert chip["governance_triage_source_consumer"] == PROPERTY_SUMMARY
    assert chip["triage_confirmation_gap_classification"] == prop["triage_confirmation_gap_classification"]
    assert chip["triage_unsafe_to_implement"] == prop["triage_unsafe_to_implement"]


def test_verified_current_requirement_list_safe_direct():
    m = build_reporting_semantic_governance_matrix()
    row = _cell(m, "VERIFIED_CURRENT", "REQUIREMENT_LIST")
    assert row["representation_safety"] == SAFE_FOR_DIRECT_REPRESENTATION
    assert row["disclaimer_requirement"] == NO_DISCLAIMER_REQUIRED
    assert row["semantic_collapse_risk"] == "NO_COLLAPSE_RISK"


def test_report_export_multi_state_unsafe():
    m = build_reporting_semantic_governance_matrix()
    row = next(
        r
        for r in m
        if r["consumer"] == REPORT_EXPORT
        and r["representation_safety"] == UNSAFE_FOR_SIMPLIFIED_REPORTING
    )
    assert row["export_readiness"] in (
        EXPORT_BLOCKED_PENDING_GOVERNANCE,
        EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT,
    )
    assert row["reporting_governance_blocked"] is True
    assert "SEMANTIC_REPRESENTATION_BLOCKER" in row["reporting_governance_blockers"]


def test_snapshot_summaries_and_audit_flags():
    snap = build_reporting_semantic_governance_phase1_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    assert snap["representation_safety_summary"] == {
        "SAFE_FOR_DIRECT_REPRESENTATION": 3,
        "SAFE_WITH_CONTEXT": 26,
        "SAFE_WITH_DISCLAIMER": 12,
        "UNKNOWN_REPRESENTATION_SAFETY": 3,
        "UNSAFE_FOR_COMPLIANT_LANGUAGE": 6,
        "UNSAFE_FOR_CURRENT_LANGUAGE": 12,
        "UNSAFE_FOR_SIMPLIFIED_REPORTING": 16,
    }
    assert snap["collapse_risk_summary"] == {
        "DECLARATION_VERIFICATION_COLLAPSE": 18,
        "EXPIRY_CURRENTNESS_COLLAPSE": 12,
        "FOLLOWUP_RESOLUTION_COLLAPSE": 12,
        "MULTI_STATE_COLLAPSE": 7,
        "NO_COLLAPSE_RISK": 6,
        "OPERATIONAL_OPEN_COLLAPSE": 6,
        "PARTIAL_COMPLETENESS_COLLAPSE": 11,
        "REPORTING_SIMPLIFICATION_COLLAPSE": 6,
    }
    assert snap["trust_risk_summary"] == {
        "CRITICAL_TRUST_RISK": 10,
        "HIGH_TRUST_RISK": 27,
        "LOW_TRUST_RISK": 5,
        "MODERATE_TRUST_RISK": 36,
    }
    assert snap["export_readiness_summary"] == {
        "EXPORT_BLOCKED_PENDING_GOVERNANCE": 7,
        "EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT": 30,
        "EXPORT_READY": 3,
        "EXPORT_READY_WITH_CONTEXT": 26,
        "EXPORT_READY_WITH_DISCLAIMER": 12,
    }
    for k in (
        "reporting_governance_matrix",
        "safest_reporting_states",
        "highest_reporting_risk_states",
        "compliant_language_blocked_states",
        "current_language_blocked_states",
        "disclaimer_required_states",
        "export_blocked_states",
        "trust_risk_summary",
        "collapse_risk_summary",
        "disclaimer_requirement_summary",
        "governance_blocker_summary",
        "reporting_readiness_summary",
        "remaining_state_model_limitation",
        "remaining_runtime_convergence_limitation",
    ):
        assert k in snap
    assert len(snap["safest_reporting_states"]) == 3
    assert len(snap["highest_reporting_risk_states"]) == 16
    assert len(snap["compliant_language_blocked_states"]) == 75
    assert len(snap["export_blocked_states"]) == 37


def test_write_phase1_json(tmp_path):
    p = tmp_path / "gov.json"
    write_reporting_semantic_governance_phase1_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text
    assert '"reporting_governance_matrix"' in text
