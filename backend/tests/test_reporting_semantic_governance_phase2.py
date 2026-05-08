from __future__ import annotations

import hashlib
import json

from services.reporting_semantic_copy_contract import (
    CLIENT_STATUS_CHIP,
    EXPORT_BLOCKED_PENDING_GOVERNANCE,
    EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT,
    EXPORT_READY_WITH_DISCLOSURE,
    OPERATIONALLY_OPEN_DISCLOSURE,
    PORTFOLIO_SCORE,
    REPORT_EXPORT,
    SAFE_FOR_DIRECT_REPRESENTATION,
    SAFE_WITH_DISCLAIMER,
    SEMANTIC_TRANSITIONS,
    UNSAFE_FOR_COMPLIANT_LANGUAGE,
    UNSAFE_FOR_SIMPLIFIED_REPORTING,
    audit_reporting_disclosure_contract,
    audit_reporting_export_readiness,
    audit_reporting_representation_risk,
    audit_reporting_wording_contract,
    build_reporting_semantic_copy_contract_matrix,
    build_reporting_semantic_governance_phase2_snapshot,
    semantic_wording_contract_base,
    write_reporting_semantic_governance_phase2_json,
)


def _matrix_fingerprint(matrix):
    payload = [
        (
            r["semantic_state"],
            r["consumer"],
            r["representation_safety"],
            r["trust_risk"],
            r["export_readiness"],
            r["copy_governance_primary"],
            tuple(r["allowed_wording"]),
            tuple(r["prohibited_wording"]),
            tuple(r["required_contexts"]),
            tuple(r["required_disclosures"]),
            tuple(r["unsafe_simplifications"]),
            tuple(r["unsafe_wording_exposures"]),
        )
        for r in matrix
    ]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def _cell(matrix, state: str, consumer: str):
    for r in matrix:
        if r["semantic_state"] == state and r["consumer"] == consumer:
            return r
    raise AssertionError(f"missing {state}/{consumer}")


def test_copy_contract_matrix_size():
    m = build_reporting_semantic_copy_contract_matrix()
    assert len(m) == len(SEMANTIC_TRANSITIONS) * 3
    row = m[0]
    for k in (
        "allowed_wording",
        "prohibited_wording",
        "required_contexts",
        "required_disclosures",
        "unsafe_simplifications",
        "representation_safety",
        "trust_risk",
        "export_readiness",
        "copy_governance_primary",
        "consumer_simplification_policy",
        "unsafe_wording_exposures",
    ):
        assert k in row


def test_snapshot_fingerprint_and_summaries():
    m = build_reporting_semantic_copy_contract_matrix()
    assert _matrix_fingerprint(m) == (
        "4f7caee32799689249676dff05b92b7ef5167d84610398bedecdb3fcfe6bc74d"
    )
    snap = build_reporting_semantic_governance_phase2_snapshot(m)
    assert snap["representation_safety_summary"] == {
        "SAFE_FOR_DIRECT_REPRESENTATION": 2,
        "SAFE_WITH_CONTEXT": 6,
        "SAFE_WITH_DISCLAIMER": 6,
        "UNKNOWN_REPRESENTATION_SAFETY": 2,
        "UNSAFE_FOR_COMPLIANT_LANGUAGE": 3,
        "UNSAFE_FOR_CURRENT_LANGUAGE": 6,
        "UNSAFE_FOR_SIMPLIFIED_REPORTING": 14,
    }
    assert snap["copy_governance_summary"] == {
        "CONTEXT_REQUIRED": 3,
        "DISCLAIMER_REQUIRED": 22,
        "PROHIBITED_WORDING": 14,
    }
    assert snap["export_readiness_summary"] == {
        "EXPORT_BLOCKED_PENDING_GOVERNANCE": 7,
        "EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT": 21,
        "EXPORT_READY": 1,
        "EXPORT_READY_WITH_CONTEXT": 6,
        "EXPORT_READY_WITH_DISCLOSURE": 4,
    }
    assert snap["trust_risk_summary"] == {
        "CRITICAL_TRUST_RISK": 9,
        "HIGH_TRUST_RISK": 24,
        "LOW_TRUST_RISK": 2,
        "MODERATE_TRUST_RISK": 4,
    }
    assert snap["unsafe_wording_exposure_summary"] == {
        "COMPLIANT_LANGUAGE_EXPOSURE": 30,
        "CURRENT_LANGUAGE_EXPOSURE": 9,
        "EXPIRY_VALIDITY_EXPOSURE": 6,
        "FOLLOWUP_SUPPRESSION_EXPOSURE": 6,
        "OPERATIONAL_CLOSURE_EXPOSURE": 3,
        "SEMANTIC_COLLAPSE_EXPOSURE": 16,
    }
    assert snap["safest_reporting_states"] == ["VERIFIED_CURRENT"]
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True


def test_semantic_state_contract_examples():
    decl = semantic_wording_contract_base("DECLARATION_RECORDED")
    assert decl["representation_safety"] == SAFE_WITH_DISCLAIMER
    assert "compliant" in decl["prohibited_wording"]
    assert "verified" in decl["prohibited_wording"]
    assert "self-declared" in decl["allowed_wording"]

    partial = semantic_wording_contract_base("PARTIALLY_COMPLETE")
    assert "complete" in partial["prohibited_wording"]
    assert any("partially complete" in x for x in partial["allowed_wording"])

    expiry = semantic_wording_contract_base("EXPIRY_REVIEW_REQUIRED")
    assert "current" in expiry["prohibited_wording"]
    assert any("expiry review required" in x for x in expiry["allowed_wording"])

    follow = semantic_wording_contract_base("ASSESSMENT_FOLLOWUP_REQUIRED")
    assert "passed" in follow["prohibited_wording"]
    assert OPERATIONALLY_OPEN_DISCLOSURE not in follow["required_disclosures"]


def test_client_status_chip_simplification_policy_and_declaration_row():
    m = build_reporting_semantic_copy_contract_matrix()
    chip_decl = _cell(m, "DECLARATION_RECORDED", CLIENT_STATUS_CHIP)
    assert chip_decl["consumer_simplification_policy"]["maximum_simplification_allowed"] == "NONE"
    assert chip_decl["export_readiness"] == EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT
    assert chip_decl["representation_safety"] == UNSAFE_FOR_SIMPLIFIED_REPORTING
    score_decl = _cell(m, "DECLARATION_RECORDED", PORTFOLIO_SCORE)
    assert chip_decl["trust_risk"] == "HIGH_TRUST_RISK"
    assert score_decl["trust_risk"] == "CRITICAL_TRUST_RISK"


def test_report_export_strong_disclosure_bias():
    m = build_reporting_semantic_copy_contract_matrix()
    row = _cell(m, "DECLARATION_RECORDED", REPORT_EXPORT)
    assert row["copy_governance_primary"] in ("DISCLAIMER_REQUIRED", "PROHIBITED_WORDING", "CONTEXT_REQUIRED")


def test_audit_helpers():
    w = audit_reporting_wording_contract("VERIFIED_CURRENT", PORTFOLIO_SCORE)
    assert w["prohibited_wording_enforced"] is True
    d = audit_reporting_disclosure_contract("VERIFIED_CURRENT", PORTFOLIO_SCORE)
    assert d["disclosure_required"] is False
    d2 = audit_reporting_disclosure_contract("DECLARATION_RECORDED", REPORT_EXPORT)
    assert d2["disclosure_required"] is True
    r = audit_reporting_representation_risk("OPERATIONALLY_OPEN", REPORT_EXPORT)
    assert r["representation_safety"] == UNSAFE_FOR_COMPLIANT_LANGUAGE
    assert r["unsafe_wording_exposures"]
    e = audit_reporting_export_readiness("MISSING", CLIENT_STATUS_CHIP)
    assert e["export_readiness"] in (EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT, EXPORT_BLOCKED_PENDING_GOVERNANCE)


def test_unsafe_exposure_on_simplified_reporting():
    m = build_reporting_semantic_copy_contract_matrix()
    row = next(r for r in m if r["representation_safety"] == UNSAFE_FOR_SIMPLIFIED_REPORTING)
    assert "SEMANTIC_COLLAPSE_EXPOSURE" in row["unsafe_wording_exposures"]


def test_phase2_json_write(tmp_path):
    p = tmp_path / "phase2.json"
    write_reporting_semantic_governance_phase2_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text
    assert '"reporting_semantic_copy_contract_matrix"' in text


def test_highest_risk_states_include_operational_open():
    snap = build_reporting_semantic_governance_phase2_snapshot()
    assert "OPERATIONALLY_OPEN" in snap["highest_risk_semantic_states"]
