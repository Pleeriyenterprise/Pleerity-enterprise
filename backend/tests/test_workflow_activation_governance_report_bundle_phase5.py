"""Phase 5: governance bundle persistence, hash, diff (mocked reports, temp files)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from services.workflow_activation_governance_report import build_workflow_activation_governance_report
from services.workflow_activation_governance_report_bundle import (
    CRITICAL_GOVERNANCE_DRIFT,
    NO_SIGNIFICANT_DRIFT,
    build_frozen_governance_bundle,
    compute_diagnostic_bundle_hash,
    diff_frozen_governance_bundles,
    diff_workflow_activation_governance_reports,
    format_governance_diff_operator_summary,
    format_governance_report_operator_summary,
    governance_report_hash_payload,
    load_workflow_activation_governance_report,
    normalize_governance_report_for_diff,
    verify_bundle_integrity,
    write_workflow_activation_governance_report,
)


def _strong_kw():
    return dict(
        generated_at_iso="2026-05-08T15:00:00Z",
        convergence_snapshot={
            "convergence_evidence_matrix": {
                "matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}],
            },
            "joined_rows": [],
        },
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"skipped_unbounded_scan": False, "returned_count": 2}},
        observability_summary={
            "reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}
        },
    )


def test_normalize_strips_generated_at_and_stable_hash():
    r1 = build_workflow_activation_governance_report(**_strong_kw())
    r2 = dict(r1)
    r2["generated_at"] = "2099-01-01T00:00:00Z"
    n1 = normalize_governance_report_for_diff(r1)
    n2 = normalize_governance_report_for_diff(r2)
    assert "generated_at" not in n1 and "generated_at" not in n2
    assert compute_diagnostic_bundle_hash(n1) == compute_diagnostic_bundle_hash(n2)


def test_bundle_hash_matches_recomputed():
    r = build_workflow_activation_governance_report(**_strong_kw())
    b = build_frozen_governance_bundle(r, environment_label="test", generated_at_iso="2026-05-08T15:00:00Z")
    ok, msg = verify_bundle_integrity(b)
    assert ok and msg == "ok"


def test_write_load_roundtrip_and_integrity():
    r = build_workflow_activation_governance_report(**_strong_kw())
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bundle.json"
        write_workflow_activation_governance_report(p, r, environment_label="ci", generated_at_iso="2026-05-08T15:00:00Z")
        loaded = load_workflow_activation_governance_report(p)
        assert loaded.get("governance_bundle_id")
        assert verify_bundle_integrity(loaded)[0] is True


def test_diff_no_significant_drift_identical():
    r = build_workflow_activation_governance_report(**_strong_kw())
    d = diff_workflow_activation_governance_reports(r, r)
    assert d["diff_severity"] == NO_SIGNIFICANT_DRIFT


def test_diff_determinism():
    a = build_workflow_activation_governance_report(**_strong_kw())
    b = build_workflow_activation_governance_report(**_strong_kw())
    d1 = diff_workflow_activation_governance_reports(a, b)
    d2 = diff_workflow_activation_governance_reports(a, b)
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)


def test_diff_severity_on_critical_priority():
    from services.workflow_activation_readiness import FAMILY_COMPLIANCE_SCORE_RECALC

    kw = _strong_kw()
    rep_a = build_workflow_activation_governance_report(**kw)
    rep_b = build_workflow_activation_governance_report(**kw)
    fams_b = []
    for row in rep_a["family_activation_reports"]:
        row = dict(row)
        if row.get("workflow_family") == FAMILY_COMPLIANCE_SCORE_RECALC:
            row["operational_priority_band"] = "PRIORITY_P0_CRITICAL"
        fams_b.append(row)
    rep_b = dict(rep_b)
    rep_b["family_activation_reports"] = sorted(fams_b, key=lambda x: str(x.get("workflow_family")))
    d = diff_workflow_activation_governance_reports(rep_a, rep_b)
    assert d["diff_severity"] == CRITICAL_GOVERNANCE_DRIFT
    assert any(x.get("to") == "PRIORITY_P0_CRITICAL" for x in d["governance_priority_changes"])


def test_summary_output_deterministic():
    r = build_workflow_activation_governance_report(**_strong_kw())
    b = build_frozen_governance_bundle(r, environment_label="ci", generated_at_iso="2026-05-08T15:00:00Z")
    s1 = format_governance_report_operator_summary(b)
    s2 = format_governance_report_operator_summary(b)
    assert s1 == s2


def test_diff_summary_deterministic():
    a = build_workflow_activation_governance_report(**_strong_kw())
    b = dict(a)
    b["generated_at"] = "2099-01-01T00:00:00Z"
    d = diff_workflow_activation_governance_reports(a, b)
    assert format_governance_diff_operator_summary(d) == format_governance_diff_operator_summary(d)


def test_diff_frozen_bundles():
    r = build_workflow_activation_governance_report(**_strong_kw())
    ba = build_frozen_governance_bundle(r, environment_label="a", generated_at_iso="2026-05-08T15:00:00Z")
    bb = build_frozen_governance_bundle(r, environment_label="b", generated_at_iso="2026-05-08T16:00:00Z")
    d = diff_frozen_governance_bundles(ba, bb)
    assert d["diff_severity"] == NO_SIGNIFICANT_DRIFT


def test_governance_report_hash_payload_sorted_keys():
    r = build_workflow_activation_governance_report(**_strong_kw())
    n = normalize_governance_report_for_diff(r)
    p1 = governance_report_hash_payload(n)
    p2 = governance_report_hash_payload(normalize_governance_report_for_diff(r))
    assert p1 == p2
