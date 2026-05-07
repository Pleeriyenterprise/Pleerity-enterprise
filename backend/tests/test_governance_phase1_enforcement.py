"""Phase 1 governance: CI bundle, snapshots, and additive forbidden-representation flags (read-only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

_SNAP = backend_root / "tests" / "snapshots"


def _load_json(name: str) -> object:
    return json.loads((_SNAP / name).read_text(encoding="utf-8"))


def test_phase1_ci_bundle_ok():
    from services.governance_validation_engine import run_phase1_ci_bundle

    bundle = run_phase1_ci_bundle()
    assert bundle["overall"] == "OK"
    assert all(p.get("summary") == "OK" for p in bundle["parts"])


def test_governance_surface_registry_snapshot():
    from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY
    from services.governance_validation_engine import snapshot_governance_surface_registry

    expected = _load_json("governance_phase1_surface_registry.json")
    live = json.loads(snapshot_governance_surface_registry())
    assert live == expected
    assert set(live) == set(GOVERNANCE_SURFACE_REGISTRY)


def test_workflow_capability_keys_snapshot():
    from services.governance_validation_engine import snapshot_workflow_capability_keys
    from services.workflow_behaviour_governance import EXECUTION_SEMANTICS_METADATA, list_governance_workflow_keys

    expected = _load_json("governance_phase1_workflow_keys.json")
    live = json.loads(snapshot_workflow_capability_keys())
    assert live == expected
    assert set(live) == set(list_governance_workflow_keys())
    assert set(live) == set(EXECUTION_SEMANTICS_METADATA.keys())


def test_governance_validation_bundle_snapshot():
    from services.governance_validation_engine import run_phase1_ci_bundle

    expected = _load_json("governance_phase1_ci_bundle.json")
    assert run_phase1_ci_bundle() == expected


def test_strict_surfaces_require_workflow_and_display_contracts():
    from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY

    for sid, row in GOVERNANCE_SURFACE_REGISTRY.items():
        if row.get("enforcement_level") != "STRICT":
            continue
        assert row.get("consumes_workflow_contract") is True, sid
        assert row.get("consumes_requirement_display_contract") is True, sid
        assert row.get("uses_local_fallback_logic") is False, sid


def test_governance_augment_forbidden_declaration_audit_ready():
    from services.workflow_behaviour_governance import WC_GUIDED_DECLARATION, governance_augment_mismatch_flags
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD, EVIDENCE_MODE_STRUCTURED_DECLARATION

    enriched = {
        "workflow_class": WC_GUIDED_DECLARATION,
        "requirement_code": "smoke_alarm",
        "status": "PENDING",
        "allowed_evidence_modes": [EVIDENCE_MODE_STRUCTURED_DECLARATION, EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"label": "Submit audit-ready declaration", "intent": "guided_evidence_resolution"}},
    }
    flags = governance_augment_mismatch_flags(
        enriched,
        reference_class=WC_GUIDED_DECLARATION,
        existing_flag_ids=frozenset(),
    )
    ids = {f["id"] for f in flags}
    assert "DECLARATION_PRESENTED_AS_AUDIT_READY" in ids
    assert "FORBIDDEN_COMPLIANCE_REPRESENTATION" in ids


def test_governance_augment_forbidden_assessment_operationally_safe():
    from services.workflow_behaviour_governance import WC_EXTERNAL_ASSESSMENT_EVIDENCE, governance_augment_mismatch_flags

    enriched = {
        "workflow_class": WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        "requirement_code": "legionella_risk_assessment",
        "status": "PENDING",
        "take_action": {"primary": {"label": "Mark operationally safe", "intent": "upload_evidence"}},
    }
    flags = governance_augment_mismatch_flags(
        enriched,
        reference_class=WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        existing_flag_ids=frozenset(),
    )
    ids = {f["id"] for f in flags}
    assert "ASSESSMENT_PRESENTED_AS_OPERATIONALLY_SAFE" in ids
    assert "FORBIDDEN_COMPLIANCE_REPRESENTATION" in ids


def test_validate_noncanonical_requirement_ids_fails_on_synthetic():
    from services.governance_validation_engine import validate_noncanonical_requirement_ids

    out = validate_noncanonical_requirement_ids({"requirement_code": "not_a_real_requirement_code_xyz123"})
    assert out["summary"] == "FAIL"


def test_validate_workflow_contract_coverage_structure():
    from services.governance_validation_engine import validate_workflow_contract_coverage

    out = validate_workflow_contract_coverage()
    assert out["summary"] == "OK"
    assert len(out["results"]) == 1
    r0 = out["results"][0]
    assert set(r0) == {"surface", "severity", "violations", "warnings"}
    assert r0["surface"] == "workflow_contract_coverage"


def test_reminder_generation_registry_upgraded_to_partial():
    from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY

    row = GOVERNANCE_SURFACE_REGISTRY["reminder_generation"]
    assert row["enforcement_level"] == "PARTIAL"
    assert row["consumes_workflow_contract"] is True
    assert row["consumes_requirement_display_contract"] is True


def test_command_centre_registry_upgraded_to_partial():
    from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY

    row = GOVERNANCE_SURFACE_REGISTRY["command_centre"]
    assert row["enforcement_level"] == "PARTIAL"
    assert row["consumes_workflow_contract"] is True
    assert row["consumes_requirement_display_contract"] is True


def test_validate_command_centre_requirement_backed_rows_flags_missing_contracts():
    from services.governance_validation_engine import validate_command_centre_requirement_backed_rows

    out = validate_command_centre_requirement_backed_rows(
        [
            {
                "source_type": "requirement",
                "title": "Missing document - blocking compliance",
                "primary_action_label": "Start compliance action",
                "metadata": {},
            }
        ]
    )
    assert out["summary"] == "FAIL"
    ids = set(out["results"][0]["violations"])
    assert any("missing_canonical_requirement_id" in x for x in ids)
    assert any("missing_requirement_display" in x for x in ids)
    assert any("missing_take_action" in x for x in ids)
    assert any("forbidden_generic_wording" in x for x in ids)


def test_validate_command_centre_requirement_backed_rows_flags_local_cta_fallback():
    from services.governance_validation_engine import validate_command_centre_requirement_backed_rows

    out = validate_command_centre_requirement_backed_rows(
        [
            {
                "source_type": "requirement",
                "requirement_id": "r-1",
                "primary_action_label": "Start compliance action",
                "metadata": {
                    "requirement_display": {"short_name": "Gas safety", "canonical_name": "Gas safety certificate"},
                    "take_action": {"primary": {"label": "Upload compliance evidence"}},
                },
            }
        ]
    )
    assert out["summary"] == "WARN"
    warns = set(out["results"][0]["warnings"])
    assert any("local_cta_fallback_with_resolver_take_action" in x for x in warns)
