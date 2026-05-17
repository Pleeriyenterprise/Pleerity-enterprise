"""G1 harness contract tests — Tranche T1 subset only (no semantic/governance simulation)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.g1_snapshot import (
    CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY,
    CONSTITUTIONAL_MASS_ACCOUNTING_MODE,
    CONSTITUTIONAL_MASS_ELEMENT_BUDGET,
    IMPLEMENTATION_SCOPE,
    MANIFEST_TIER_CLASSIFICATION,
    REFUSED_CAPABILITY_INVENTORY,
    SURVEILLANCE_DEGRADED,
    SURVEILLANCE_FULL,
    T1_APPROVED_PRIMARY_RCS,
    T2_T3_BLOCKED_RCS,
    apply_scaffold_legitimacy_prohibition,
    assemble_t1_readiness,
    attempt_scope_escalation,
    bind_tracker_claims,
    build_anti_seepage_envelope,
    build_launch_baseline_manifest,
    compare_scope_registry,
    count_constitutional_mass,
    detect_primary_rc_t1,
    detect_retired_artifact_usage,
    evaluate_live_staging_gate,
    evaluate_pass_prohibition,
    inventory_critical_authoritative,
    is_prohibited_write_target,
    is_retired_artifact_filename,
    refuse_capability_activation,
    refuse_t2_t3_predicate,
    scan_manifest_normative_assertions,
    t1_tracker_claims,
    validate_manifest_t1,
    verify_readonly_preservation,
    write_json_readonly_emit,
)

AUDIT_DIR = Path(__file__).resolve().parent.parent / "docs" / "audit"
PILOT_SLUG = "6fd5ac4c_d35a58ae"


def test_implementation_scope_is_t1_only():
    assert IMPLEMENTATION_SCOPE == "T1_ONLY"


def test_t2_t3_predicates_refused_observably():
    refusal = refuse_t2_t3_predicate("G1-P3")
    assert refusal["refused"] is True
    assert refusal["observable_refusal"] is True
    assert refusal["silent_noop"] is False
    assert refusal["implementation_scope"] == "T1_ONLY"
    assert refusal["predicate"] == "G1-P3"
    assert "G1-P3" in T2_T3_BLOCKED_RCS


def test_refused_capability_inventory_complete():
    envelope = build_anti_seepage_envelope()
    assert envelope["refused_capability_inventory"] == list(REFUSED_CAPABILITY_INVENTORY)
    assert len(envelope["capability_refusal_reason"]) == len(REFUSED_CAPABILITY_INVENTORY)


def test_attempt_scope_escalation_is_observable_not_silent():
    envelope = build_anti_seepage_envelope()
    refusal = attempt_scope_escalation(
        envelope,
        capability_id="SEMANTIC_REINTERPRETATION",
        detail="unit_test_probe",
    )
    assert refusal["refused"] is True
    assert envelope["attempted_scope_escalations"]
    assert envelope["attempted_scope_escalations"][0]["refused"] is True


def test_refuse_capability_activation_not_silent_noop():
    refusal = refuse_capability_activation(
        capability_id="CONTRADICTION_ARCHAEOLOGY",
        detail="probe",
    )
    assert refusal["silent_noop"] is False
    assert refusal["observable_refusal"] is True


def test_degraded_mode_prohibits_pass_and_eligibility():
    out = evaluate_pass_prohibition(surveillance_mode=SURVEILLANCE_DEGRADED, degraded_mode=True)
    assert out["g1_pass"] is False
    assert out["verified_eligible"] is False
    assert out["done_eligible"] is False
    assert out["degraded_mode"] is True


def test_non_full_surveillance_prohibits_pass_even_if_not_degraded_flag():
    out = evaluate_pass_prohibition(surveillance_mode=SURVEILLANCE_DEGRADED, degraded_mode=False)
    assert out["g1_pass"] is False
    assert out["verified_eligible"] is False


def test_full_surveillance_without_degraded_allows_pass_predicate():
    out = evaluate_pass_prohibition(surveillance_mode=SURVEILLANCE_FULL, degraded_mode=False)
    assert out["g1_pass"] is True
    assert out["verified_eligible"] is True
    assert out["degraded_mode"] is False


def test_scaffold_legitimacy_prohibition_even_when_checks_would_pass():
    would_pass = evaluate_pass_prohibition(surveillance_mode=SURVEILLANCE_FULL, degraded_mode=False)
    assert would_pass["g1_pass"] is True
    prohibited = apply_scaffold_legitimacy_prohibition(would_pass, scaffold_only=True)
    assert prohibited["g1_pass"] is False
    assert prohibited["verified_eligible"] is False
    assert prohibited["done_eligible"] is False
    assert prohibited["constitutional_authority_level"] == CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY
    assert prohibited["scaffold_legitimacy_prohibition_pass"] is True
    assert prohibited["scaffold_authority_boundary"]


def test_assemble_readiness_scaffold_never_inflates_legitimacy():
    posture = {
        "surveillance_mode": SURVEILLANCE_FULL,
        "pass_fields": evaluate_pass_prohibition(
            surveillance_mode=SURVEILLANCE_FULL,
            degraded_mode=False,
        ),
        "primary_rc": None,
        "tracker_binding": {
            "tier0_link_resolution": [{"claim_id": "X"}],
            "unresolved_tracker_claims": [],
            "tracker_truth_binding_pass": True,
        },
        "current_entries": [{"path": "docs/audit/d1b_verification_report_x.json", "sha256": "abc"}],
        "manifest": build_launch_baseline_manifest(audit_dir=AUDIT_DIR, slug=PILOT_SLUG),
    }
    readiness = assemble_t1_readiness(
        slug=PILOT_SLUG,
        posture=posture,
        artifacts=[{"tier0_entries": []}, {"watchlist_inventory": []}],
        scaffold_only=True,
    )
    assert readiness["t1_harness_scaffold_only"] is True
    assert readiness["g1_pass"] is False
    assert readiness["verified_eligible"] is False
    assert readiness["constitutional_authority_level"] == CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY


def test_critical_authoritative_inventory_present_for_pilot():
    inv = inventory_critical_authoritative(AUDIT_DIR, PILOT_SLUG)
    assert inv["critical_complete"] is True
    assert inv["missing_critical_authoritative_artifacts"] == []
    families = {row["family"] for row in inv["critical_authoritative_artifact_inventory"]}
    assert families == {"d1b", "e1b", "f1a"}


def test_critical_omission_triggers_rc27_precedence():
    rc = detect_primary_rc_t1({"critical_omission_masking": True, "manifest_rc21": True})
    assert rc == "G1-RC-27"


def test_manifest_t1_classification_valid_for_baseline_build():
    manifest = build_launch_baseline_manifest(audit_dir=AUDIT_DIR, slug=PILOT_SLUG)
    assert manifest["manifest_tier_classification"] == MANIFEST_TIER_CLASSIFICATION
    validation = validate_manifest_t1(manifest)
    assert validation["manifest_t1_valid"] is True
    assert validation["manifest_assertion_scan_pass"] is True
    assert validation["violations"] == []


def test_manifest_forbidden_keys_fail_rc21():
    manifest = build_launch_baseline_manifest(audit_dir=AUDIT_DIR, slug=PILOT_SLUG)
    manifest["governance_assertion"] = "must not be here"
    validation = validate_manifest_t1(manifest)
    assert validation["manifest_t1_valid"] is False
    assert validation["manifest_assertion_scan_pass"] is False
    assert validation["metadata_authority_escalation"] is True
    assert any("prohibited_field" in v or "forbidden_manifest_key" in v for v in validation["violations"])


def test_manifest_normative_value_marker_detected():
    manifest = build_launch_baseline_manifest(audit_dir=AUDIT_DIR, slug=PILOT_SLUG)
    manifest["notes"] = "system is constitutionally_adequate for launch"
    scan = scan_manifest_normative_assertions(manifest)
    assert scan["manifest_assertion_scan_pass"] is False
    assert scan["forbidden_manifest_assertions"]


def test_tracker_binding_resolves_authoritative_tier0_paths():
    manifest = build_launch_baseline_manifest(audit_dir=AUDIT_DIR, slug=PILOT_SLUG)
    binding = bind_tracker_claims(
        claims=[c for c in t1_tracker_claims(slug=PILOT_SLUG) if not c.get("explicit_unresolved")],
        tier0_entries=manifest["tier0_entries"],
        audit_dir=AUDIT_DIR,
        slug=PILOT_SLUG,
    )
    assert binding["tracker_truth_binding_pass"] is True
    assert binding["unresolved_tracker_claims"] == []
    for row in binding["tier0_link_resolution"]:
        assert row["tier0_artifact_path"]
        assert row["tier0_artifact_sha256"]


def test_unresolved_tracker_claim_explicit_state():
    binding = bind_tracker_claims(
        claims=t1_tracker_claims(slug=PILOT_SLUG),
        tier0_entries=[],
        audit_dir=AUDIT_DIR,
        slug=PILOT_SLUG,
    )
    assert binding["tracker_truth_binding_pass"] is False
    assert any(c["claim_id"] == "F1_DONE_SCOPE" for c in binding["unresolved_tracker_claims"])


def test_scope_erasure_detects_silently_removed():
    baseline = {
        "deferred_risk_inventory": [{"id": "F1-M2-M7"}],
        "watchlist_inventory": [{"id": "watch-a"}],
        "accepted_scope_limitations": [],
    }
    current = {
        "deferred_risk_inventory": [],
        "watchlist_inventory": [{"id": "watch-a"}],
        "accepted_scope_limitations": [],
    }
    diff = compare_scope_registry(baseline=baseline, current=current)
    assert "deferred_risk_inventory:F1-M2-M7" in diff["silently_removed"]
    assert detect_primary_rc_t1({"scope_erasure": True}) == "G1-P5"


def test_constitutional_mass_field_plus_element_accounting():
    payloads = [{"tier0_entries": [{"a": 1}, {"b": 2}], "tags": ["x"]}]
    mass = count_constitutional_mass(payloads)
    assert mass["constitutional_mass_accounting_mode"] == CONSTITUTIONAL_MASS_ACCOUNTING_MODE
    assert mass["mass_total"] == mass["field_count"] + mass["element_count"]
    assert mass["constitutional_mass_element_budget"] == CONSTITUTIONAL_MASS_ELEMENT_BUDGET


def test_constitutional_mass_budget_exceeded():
    huge = {"rows": list(range(CONSTITUTIONAL_MASS_ELEMENT_BUDGET + 5))}
    mass = count_constitutional_mass([huge])
    assert mass["budget_exceeded"] is True


def test_retired_artifact_prohibited_for_pass_fail_inputs():
    assert is_retired_artifact_filename("g1_governance_legitimacy_pilot.json")
    violations = detect_retired_artifact_usage(
        ["docs/audit/g1_bounded_reinterpretation_x.json", "docs/audit/g1_upstream_integrity_x.json"]
    )
    assert "g1_bounded_reinterpretation_x.json" in violations
    assert "g1_upstream_integrity_x.json" not in violations


def test_advisory_tag_posture_no_primary_rc_from_tags():
    assert "G1-RC-25" in T2_T3_BLOCKED_RCS
    assert "G1-P3" not in T1_APPROVED_PRIMARY_RCS


def test_prohibited_write_target_upstream_tier0():
    assert is_prohibited_write_target("d1b_verification_report_x.json") is True
    assert is_prohibited_write_target("g1_launch_readiness_x.json") is False
    assert is_prohibited_write_target("launch_baseline_manifest_x_v1.json") is False


def test_readonly_preservation_blocks_upstream_write_path():
    preservation = verify_readonly_preservation(path=AUDIT_DIR / "d1b_verification_report_x.json")
    assert preservation["readonly_preservation_pass"] is False
    assert preservation["attempted_upstream_mutations"]


def test_write_json_refuses_upstream_target(tmp_path: Path):
    target = tmp_path / "b1_verification_report_test.json"
    with pytest.raises(RuntimeError, match="G1_READONLY_PRESERVATION_VIOLATION"):
        write_json_readonly_emit(target, {"probe": True})


def test_write_json_allows_g1_emit(tmp_path: Path):
    target = tmp_path / "g1_launch_readiness_test.json"
    preservation = write_json_readonly_emit(target, {"g1_pass": False, "read_only": True})
    assert preservation["readonly_preservation_pass"] is True
    assert target.is_file()


def test_live_staging_refused_without_approval():
    gate = evaluate_live_staging_gate(
        explicit_execution_approval=False,
        implementation_scope=IMPLEMENTATION_SCOPE,
        live_staging_requested=True,
    )
    assert gate["authorised"] is False
    assert gate["reason"] == "MISSING_EXPLICIT_EXECUTION_APPROVAL"
    assert gate["attempted_scope_escalations"]


def test_live_staging_refused_with_approval_under_t1_scope():
    gate = evaluate_live_staging_gate(
        explicit_execution_approval=True,
        implementation_scope=IMPLEMENTATION_SCOPE,
        live_staging_requested=True,
    )
    assert gate["authorised"] is False
    assert gate["reason"] == "SCOPE_AUTHORITY_INSUFFICIENT_T1_ONLY"
    assert gate["approval_flag_alone_insufficient"] is True


@pytest.mark.parametrize(
    "rc",
    ["G1-P1", "G1-P2", "G1-P5", "G1-RC-21", "G1-RC-27"],
)
def test_t1_approved_rc_membership(rc: str):
    assert rc in T1_APPROVED_PRIMARY_RCS


def test_pilot_manifest_on_disk_if_preflight_run():
    path = AUDIT_DIR / f"launch_baseline_manifest_{PILOT_SLUG}_v1.json"
    if not path.is_file():
        pytest.skip("preflight manifest not captured yet")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["manifest_tier_classification"] == MANIFEST_TIER_CLASSIFICATION
    scan = scan_manifest_normative_assertions(manifest)
    assert scan["manifest_assertion_scan_pass"] is True
