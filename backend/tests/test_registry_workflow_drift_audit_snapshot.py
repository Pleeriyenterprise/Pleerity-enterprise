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
    assert report["scenarios_evaluated"] == 128
    assert report["findings_total"] == 127
    assert len(report["findings"]) == 127
    by_sev = report["findings_by_severity"]
    assert set(by_sev.keys()) <= {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert sum(by_sev.values()) == report["findings_total"]

    # Snapshot — bump when canonical requirement list or drift rules change deliberately.
    assert by_sev == {"CRITICAL": 3, "HIGH": 73, "MEDIUM": 43, "LOW": 8}

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


def test_occupation_contract_non_wales_critical_fallback():
    from scripts.registry_workflow_drift_audit import run_audit

    report = run_audit()
    crit = [
        f
        for f in report["findings"]
        if f.get("canonical_requirement_code") == "occupation_contract"
        and f.get("finding_id") == "POLICY_FALLBACK_VS_REFERENCE_GUIDED"
    ]
    assert len(crit) == 3
    assert {f.get("jurisdiction") for f in crit} == {"england", "scotland", "northern_ireland"}


def test_lead_testing_engine_external_assessment_flag_present():
    from scripts.registry_workflow_drift_audit import run_audit

    report = run_audit()
    hits = [
        f
        for f in report["findings"]
        if f.get("canonical_requirement_code") == "lead_testing"
        and f.get("finding_id") == "ENGINE_SPEC_VS_EXTERNAL_ASSESSMENT_REFERENCE"
    ]
    assert len(hits) == 4


def test_governance_metadata_consumed_in_audit_flags():
    """At least one finding originates from governance_augment (semantic collapse umbrella)."""
    from scripts.registry_workflow_drift_audit import run_audit

    report = run_audit()
    assert any(f.get("finding_id") == "WORKFLOW_SEMANTIC_COLLAPSE_RISK" for f in report["findings"])
