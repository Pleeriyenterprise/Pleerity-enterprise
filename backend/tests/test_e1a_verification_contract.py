"""E1a harness contract tests (mocked)."""
from __future__ import annotations

from scripts.e1a_snapshot import (
    FIXTURE_AUTHORITY_CAPABLE,
    FIXTURE_INCAPABLE,
    FIXTURE_PARTIALLY_CAPABLE,
    authority_cardinality_snapshot_e1a,
    authority_explainability_snapshot_e1a,
    classify_e1_fixture,
    normalize_evidence_authority_semantic,
    replay_authority_comparison,
    reconciliation_suppression_fingerprint_semantic,
    semantic_authority_fingerprint,
    supersession_replay_equal,
)


def test_semantic_fingerprint_ignores_evidence_last_updated_at():
    req_a = {
        "evidence_authority": {
            "state": "NOT_REQUIRED",
            "evidence_last_updated_at": "2026-05-17T15:16:17Z",
        }
    }
    req_b = {
        "evidence_authority": {
            "state": "NOT_REQUIRED",
            "evidence_last_updated_at": "2026-05-17T15:16:21Z",
        }
    }
    assert semantic_authority_fingerprint(doc=None, requirement=req_a) == semantic_authority_fingerprint(
        doc=None, requirement=req_b
    )


def test_normalize_evidence_authority_semantic_strips_timestamps():
    raw = {"state": "EA_PRESENT", "evidence_last_updated_at": "x", "evidence_last_verified_at": "y"}
    out = normalize_evidence_authority_semantic(raw)
    assert "evidence_last_updated_at" not in out
    assert "evidence_last_verified_at" not in out
    assert out["state"] == "EA_PRESENT"


def test_supersession_replay_equal_empty_strings():
    assert supersession_replay_equal({"R2": "", "R3": ""}) is True


def test_replay_comparison_timestamp_only_drift():
    runs = [
        {
            "run": "R2",
            "authority_fingerprint_after": "raw-a",
            "semantic_authority_fingerprint_after": "sem-stable",
        },
        {
            "run": "R3",
            "authority_fingerprint_after": "raw-b",
            "semantic_authority_fingerprint_after": "sem-stable",
        },
    ]
    comp = replay_authority_comparison(runs)
    assert comp["lineage_replay_stable_semantic"] is True
    assert comp["lineage_replay_stable_raw"] is False
    assert comp["timestamp_only_drift"] is True


def test_fixture_incapable_classification():
    out = classify_e1_fixture(
        requirement={"requirement_id": "r1", "evidence_authority": {"state": "NOT_REQUIRED"}},
        document=None,
        document_count=0,
        requirements_with_evidence_doc=0,
        client_id="c",
        property_id="p",
        requirement_id="r1",
        document_id="",
    )
    assert out["fixture_classification"] == FIXTURE_INCAPABLE
    assert out["vacuous_proof_prevented"] is True


def test_fixture_authority_capable_with_review_lineage():
    doc = {
        "document_id": "d1",
        "evidence_review_state": "VERIFIED",
        "status": "VERIFIED",
    }
    out = classify_e1_fixture(
        requirement={
            "requirement_id": "r1",
            "evidence_doc_id": "d1",
            "evidence_authority": {"state": "EA_PRESENT"},
        },
        document=doc,
        document_count=1,
        requirements_with_evidence_doc=1,
        client_id="c",
        property_id="p",
        requirement_id="r1",
        document_id="d1",
    )
    assert out["fixture_classification"] == FIXTURE_AUTHORITY_CAPABLE


def test_cardinality_not_vacuous_pass_when_incapable():
    card = authority_cardinality_snapshot_e1a(None, fixture_classification=FIXTURE_INCAPABLE)
    assert card["authority_cardinality_pass"] is None
    assert card["vacuous"] is True


def test_reconciliation_suppression_semantic_ignores_run_label():
    outcomes = [
        {"run": "R2", "dry_run": True, "status": "skipped", "reason": "already_aligned"},
        {"run": "R3", "dry_run": True, "status": "skipped", "reason": "already_aligned"},
    ]
    assert reconciliation_suppression_fingerprint_semantic([outcomes[0]]) == reconciliation_suppression_fingerprint_semantic(
        [outcomes[1]]
    )


def test_explainability_insufficient_governed_fixture():
    row = authority_explainability_snapshot_e1a(
        requirement_id="r1",
        document_id=None,
        doc=None,
        requirement={"evidence_authority": {"state": "NOT_REQUIRED"}},
        lineage=None,
        fixture_classification=FIXTURE_INCAPABLE,
    )
    assert row["explainability_classification"] == "insufficient_governed_fixture"
    assert row["reconstructable"] is None
    assert "insufficient_governed_fixture" in row["gaps"]
