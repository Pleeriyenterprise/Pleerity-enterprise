from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.live_semantic_copy_audit import (
    PROHIBITED_WORDING_VIOLATION,
    SEMANTIC_COLLAPSE_RISK,
    audit_reporting_export_readiness,
    audit_reporting_wording_contract_compare,
    build_live_semantic_copy_audit_phase3_snapshot,
    build_semantic_copy_inventory,
    evaluate_inventory_violations,
    extract_live_semantic_strings,
    map_audit_consumer_to_contract_consumer,
    write_live_semantic_copy_audit_phase3_json,
)


def _make_fixture_repo(base: Path) -> None:
    (base / "frontend/src/pages").mkdir(parents=True)
    (base / "frontend/src/utils").mkdir(parents=True)
    (base / "frontend/src/pages/ComplianceScorePage.js").write_text(
        'const a = "Fully compliant requirement status";\n'
        'const b = "verified current certificate";\n'
        'const c = "follow-up outstanding remediation";\n',
        encoding="utf-8",
    )
    (base / "frontend/src/utils/evidenceStatus.js").write_text(
        'const chip = "Compliant and verified today";\n',
        encoding="utf-8",
    )


def test_inventory_and_violation_determinism(tmp_path):
    _make_fixture_repo(tmp_path)
    ext = extract_live_semantic_strings(tmp_path)
    inv = build_semantic_copy_inventory(ext, tmp_path)
    viol = []
    for r in inv:
        viol.extend(evaluate_inventory_violations(r))
    viol.sort(key=lambda x: (x["violation_type"], x["source_file"], x["detected_wording"]))
    assert hashlib.sha256(json.dumps(viol).encode()).hexdigest() == (
        "dfe47c69ed5af06167e8007f26cfc9f4072fbdf7131cdd52eca6f7e6cea27ccd"
    )


def test_prohibited_and_collapse_detection(tmp_path):
    _make_fixture_repo(tmp_path)
    inv = build_semantic_copy_inventory(extract_live_semantic_strings(tmp_path), tmp_path)
    texts = {r["detected_wording"]: r for r in inv}
    row = texts["Fully compliant requirement status"]
    vs = evaluate_inventory_violations(row)
    types = {v["violation_type"] for v in vs}
    assert SEMANTIC_COLLAPSE_RISK in types or PROHIBITED_WORDING_VIOLATION in types


def test_map_audit_consumer():
    assert map_audit_consumer_to_contract_consumer("COMMAND_CENTER") == "CLIENT_STATUS_CHIP"
    assert map_audit_consumer_to_contract_consumer("PORTFOLIO_SCORE") == "PORTFOLIO_SCORE"


def test_audit_helpers(tmp_path):
    _make_fixture_repo(tmp_path)
    inv = build_semantic_copy_inventory(extract_live_semantic_strings(tmp_path), tmp_path)
    row = inv[0]
    w = audit_reporting_wording_contract_compare(row)
    assert "contract_prohibited" in w
    e = audit_reporting_export_readiness(row)
    assert "export_readiness" in e and "trust_risk" in e


def test_phase3_snapshot_shape(tmp_path):
    _make_fixture_repo(tmp_path)
    snap = build_live_semantic_copy_audit_phase3_snapshot(tmp_path)
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    for k in (
        "inventory_total_rows",
        "violations_total",
        "violations_by_severity",
        "violations_by_consumer",
        "prohibited_wording_matrix",
        "missing_disclosure_matrix",
        "highest_risk_wording_surfaces",
        "safest_wording_surfaces",
        "semantic_collapse_hotspots",
        "unsafe_wording_exposure_summary",
        "trust_risk_rankings",
        "consumer_audit_views",
        "remaining_state_model_limitation",
        "remaining_runtime_convergence_limitation",
    ):
        assert k in snap
    assert snap["consumer_audit_views"]["PORTFOLIO_SCORE"]["violation_count"] >= 1


def test_write_phase3_json(tmp_path):
    _make_fixture_repo(tmp_path)
    p = tmp_path / "out.json"
    write_live_semantic_copy_audit_phase3_json(target_path=p, repo_root=tmp_path)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"trust_risk_rankings"' in text
