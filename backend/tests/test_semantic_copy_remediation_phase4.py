from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.live_semantic_copy_audit import (
    CLIENT_STATUS_CHIP,
    MISSING_REQUIRED_DISCLOSURE,
    PROHIBITED_WORDING_VIOLATION,
    REPORT_EXPORT,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    UNKNOWN_SEMANTIC_MAPPING,
)
from services.semantic_copy_remediation_planning import (
    APPROVED_SAFE_VOCABULARY_CATALOG,
    DISCLOSURE_PAIRING_CATALOG,
    DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION,
    P0_CRITICAL_TRUST_RISK,
    P1_HIGH_RISK_EXTERNAL_REPRESENTATION,
    P3_DISCLOSURE_GAP,
    P6_OBSERVE_ONLY,
    PROHIBITED_COMPACT_LABELS_GLOBAL,
    SAFE_FOR_COMPACT_REPRESENTATION,
    SIMPLIFICATION_SAFETY_CATALOG,
    build_semantic_copy_remediation_phase4_snapshot,
    build_semantic_copy_remediation_queue,
    write_semantic_copy_remediation_phase4_json,
)


def _synthetic_violations():
    return [
        {
            "violation_type": PROHIBITED_WORDING_VIOLATION,
            "severity": SEVERITY_CRITICAL,
            "consumer": CLIENT_STATUS_CHIP,
            "source_file": "x.js",
            "detected_wording": "Fully compliant",
            "associated_semantic_state": "DECLARATION_RECORDED",
            "governance_contract_reference": "DECLARATION_RECORDED:CLIENT_STATUS_CHIP",
        },
        {
            "violation_type": MISSING_REQUIRED_DISCLOSURE,
            "severity": SEVERITY_CRITICAL,
            "consumer": REPORT_EXPORT,
            "source_file": "y.js",
            "detected_wording": "Score summary",
            "associated_semantic_state": "PARTIALLY_COMPLETE",
            "governance_contract_reference": "PARTIALLY_COMPLETE:REPORT_EXPORT",
        },
        {
            "violation_type": UNKNOWN_SEMANTIC_MAPPING,
            "severity": SEVERITY_LOW,
            "consumer": "REQUIREMENT_LIST",
            "source_file": "z.js",
            "detected_wording": "General text",
            "associated_semantic_state": "UNKNOWN_MAPPED",
            "governance_contract_reference": "MISSING:REQUIREMENT_LIST",
        },
    ]


def test_remediation_queue_ordering_and_fingerprint():
    q = build_semantic_copy_remediation_queue(_synthetic_violations())
    payload = [
        (r["priority_tier"], r["consumer"], r["semantic_state"], r["recommended_remediation_class"], r["simplification_compression_class"])
        for r in q
    ]
    assert hashlib.sha256(json.dumps(payload).encode()).hexdigest() == (
        "75c8bb713009585578345f4ac2835fd70cd31118dfb5bc47d689d04a074e5b0a"
    )
    assert q[0]["priority_tier"] == P0_CRITICAL_TRUST_RISK
    assert any(r["priority_tier"] == P3_DISCLOSURE_GAP for r in q)
    assert any(r["priority_tier"] == P6_OBSERVE_ONLY for r in q)


def test_priority_p1_export_prohibited():
    viol = [
        {
            "violation_type": PROHIBITED_WORDING_VIOLATION,
            "severity": SEVERITY_HIGH,
            "consumer": REPORT_EXPORT,
            "source_file": "e.js",
            "detected_wording": "compliant",
            "associated_semantic_state": "VERIFIED_CURRENT",
            "governance_contract_reference": "",
        }
    ]
    q = build_semantic_copy_remediation_queue(viol)
    assert q[0]["priority_tier"] == P1_HIGH_RISK_EXTERNAL_REPRESENTATION


def test_disclosure_pairing_catalog_partially_complete():
    d = DISCLOSURE_PAIRING_CATALOG["PARTIALLY_COMPLETE"]
    assert "Additional evidence" in d["required_disclosure_pairing"][0]
    assert d["prohibited_disclosure_omission"]


def test_simplification_safety_chip():
    chip = SIMPLIFICATION_SAFETY_CATALOG[CLIENT_STATUS_CHIP]
    assert chip["maximum_safe_compression_level"] == DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION
    assert chip["verified_current_exception"] == SAFE_FOR_COMPACT_REPRESENTATION


def test_prohibited_compact_labels():
    assert "Compliant" in PROHIBITED_COMPACT_LABELS_GLOBAL
    assert "Verified" in APPROVED_SAFE_VOCABULARY_CATALOG["VERIFIED_CURRENT"]["approved_short_chip_labels"]


def test_phase4_snapshot_with_injected_violations():
    snap = build_semantic_copy_remediation_phase4_snapshot(violations_input=_synthetic_violations())
    assert snap["audit_only"] is True
    assert snap["runtime_behavior_changed"] is False
    assert snap["non_blocking"] is True
    assert snap["prioritized_remediation_queue_total"] == 3
    assert snap["phase3_violation_count"] == 3
    assert "approved_safe_vocabulary_catalog" in snap
    assert "disclosure_pairing_catalog" in snap
    assert snap["safest_approved_compact_labels"]


def test_write_phase4_json_tmp(tmp_path: Path):
    p = tmp_path / "p4.json"
    write_semantic_copy_remediation_phase4_json(
        target_path=p,
        repo_root=None,
        violations_input=_synthetic_violations(),
    )
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"prioritized_remediation_queue"' in text
