"""Snapshot / stability tests for live registry workflow drift audit (read-only)."""
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_drift_audit_runs_and_counts_match_snapshot():
    """Guardrail: methodology output shape + deduped severity totals (update when registry/governance intentionally changes)."""
    from scripts.registry_workflow_drift_audit import run_audit

    report = run_audit()
    assert report["scenarios_evaluated"] == 113
    assert report["findings_total"] == 4
    assert len(report["findings"]) == 4
    by_sev = report["findings_by_severity"]
    assert set(by_sev.keys()) <= {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert sum(by_sev.values()) == report["findings_total"]

    # Phase 3: client workflow_class MULTI_EVIDENCE alignment removes reference drift; aliases remain LOW.
    assert by_sev == {"LOW": 4}

    keys = []
    for f in report["findings"]:
        keys.append(
            (
                f.get("canonical_requirement_code"),
                f.get("jurisdiction"),
                f.get("drift_type"),
                f.get("finding_id"),
                str(f.get("detail", ""))[:120],
            )
        )
    assert len(keys) == len(set(keys)), "duplicate findings after dedupe"


def test_occupation_contract_non_wales_not_critical_policy_fallback():
    """Phase 1 alignment: non-Wales occupation_contract reference is GUIDANCE_ONLY — no CRITICAL guided-vs-legacy mismatch."""
    from scripts.registry_workflow_drift_audit import run_audit

    report = run_audit()
    crit = [
        f
        for f in report["findings"]
        if f.get("canonical_requirement_code") == "occupation_contract"
        and f.get("finding_id") == "POLICY_FALLBACK_VS_REFERENCE_GUIDED"
    ]
    assert len(crit) == 0


def test_lead_testing_engine_external_assessment_drift_flag_cleared():
    """Engine spec aligns with EXTERNAL_ASSESSMENT_EVIDENCE — audit heuristic no longer fires."""
    from scripts.registry_workflow_drift_audit import run_audit

    report = run_audit()
    hits = [
        f
        for f in report["findings"]
        if f.get("canonical_requirement_code") == "lead_testing"
        and f.get("finding_id") == "ENGINE_SPEC_VS_EXTERNAL_ASSESSMENT_REFERENCE"
    ]
    assert len(hits) == 0


def test_drift_audit_alias_low_findings_only():
    """Remaining synthetic drift is canonical identity (legacy storage slugs) at LOW."""
    from scripts.registry_workflow_drift_audit import run_audit

    report = run_audit()
    ids = {f.get("finding_id") for f in report["findings"]}
    assert ids == {"ALIAS_LEGACY_STORAGE_SLUG"}
    assert all(f.get("severity") == "LOW" for f in report["findings"])


def test_drift_audit_excludes_system_classification_codes_from_grid():
    from scripts.registry_workflow_drift_audit import _AUDIT_REQUIREMENT_CODES

    assert "hmo_classification" not in _AUDIT_REQUIREMENT_CODES
    assert "property_classification" not in _AUDIT_REQUIREMENT_CODES


def test_fire_risk_assessment_default_policy_is_multi_mode_guided():
    from services.compliance_evidence_record_service import (
        EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_INSPECTION_CHECKLIST,
        effective_evidence_resolution,
    )

    row = {
        "requirement_code": "fire_risk_assessment",
        "requirement_type": "fire_risk_assessment",
        "property_id": "p1",
        "registry_metadata": {},
    }
    policy = effective_evidence_resolution(row)
    modes = set(policy.get("allowed_evidence_modes") or [])
    assert modes == {
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
        EVIDENCE_MODE_INSPECTION_CHECKLIST,
    }
    assert str(policy.get("primary_resolution_workflow") or "").upper() == "GUIDED_EVIDENCE_RESOLUTION"
