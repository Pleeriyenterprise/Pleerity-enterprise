"""E1 §14 contract tests (mocked — no staging Mongo required)."""
from __future__ import annotations

from scripts.e1_snapshot import (
    authority_cardinality_snapshot,
    authority_collapse_snapshot,
    collapse_boundedness_snapshot,
    detect_primary_rc,
    human_review_preservation_snapshot,
    lineage_boundedness_snapshot,
    reconciliation_suppression_fingerprint,
    resolve_authority_precedence,
    supersession_state_fingerprint,
)


def test_precedence_human_review_wins_over_extraction():
    doc = {
        "evidence_review_state": "REJECTED",
        "extraction_status": "NEEDS_REVIEW",
        "ai_extraction": {"status": "completed", "review_status": "PENDING", "data": {"x": 1}},
    }
    row = resolve_authority_precedence(doc, entity_key="doc1")
    assert row["winning_authority_source"] == "human_review"
    assert row["precedence_pass"] is True


def test_authority_cardinality_single_winner():
    doc = {
        "evidence_review_state": "VERIFIED",
        "status": "VERIFIED",
    }
    card = authority_cardinality_snapshot(doc)
    assert card["authority_cardinality_pass"] is True
    assert card["unexpected_parallel_authority_count"] == 0


def test_supersession_fingerprint_stable_on_replay():
    doc = {
        "extraction_confirmation_superseded": True,
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "extraction_status": "CONFIRMED",
    }
    assert supersession_state_fingerprint(doc) == supersession_state_fingerprint(doc)


def test_reconciliation_suppression_replay_equal():
    outcomes = [{"run": "R2", "status": "skipped", "reason": "already_aligned"}]
    fp2 = reconciliation_suppression_fingerprint(outcomes)
    fp3 = reconciliation_suppression_fingerprint(outcomes)
    assert fp2 == fp3


def test_authority_collapse_deterministic_r2_r3():
    runs = [
        {"run": "R2", "authority_collapse_state": "collapsed_stable", "authority_write_suppressed": True},
        {"run": "R3", "authority_collapse_state": "collapsed_stable", "authority_write_suppressed": True},
    ]
    collapse = authority_collapse_snapshot(runs)
    assert collapse["collapse_deterministic"] is True
    assert collapse["retained_authority_visibility"] is True


def test_collapse_boundedness_zero_growth():
    runs = [
        {"run": "R2", "collapsed_authority_mutations": [], "collapsed_lineage_depth": 1},
        {"run": "R3", "collapsed_authority_mutations": [], "collapsed_lineage_depth": 1},
    ]
    bounded = collapse_boundedness_snapshot(runs)
    assert bounded["collapse_growth_pass"] is True


def test_human_review_preservation_pass():
    before = {
        "document": {"evidence_review_state": "REJECTED", "status": "REJECTED"},
    }
    after = {
        "document": {"evidence_review_state": "REJECTED", "status": "REJECTED"},
    }
    out = human_review_preservation_snapshot(before, after)
    assert out["human_review_preservation_pass"] is True


def test_lineage_boundedness_stable():
    runs = [
        {"run": "R2", "lineage_depth": 1, "supersession_chain_depth": 1, "override_chain_depth": 1},
        {"run": "R3", "lineage_depth": 1, "supersession_chain_depth": 1, "override_chain_depth": 1},
    ]
    out = lineage_boundedness_snapshot(runs)
    assert out["lineage_growth_pass"] is True


def test_detect_primary_rc_cardinality():
    rc = detect_primary_rc({"authority_cardinality_pass": False, "precedence_pass": True})
    assert rc == "E1-RC-21"


def test_detect_primary_rc_precedence():
    rc = detect_primary_rc({"precedence_pass": False, "authority_cardinality_pass": True})
    assert rc == "E1-RC-16"


def test_authority_fingerprint_stable_dict():
    from scripts.e1_snapshot import authority_fingerprint

    doc = {"evidence_review_state": "VERIFIED", "status": "VERIFIED"}
    req = {"evidence_authority": {"version": 1, "state": "EA_PRESENT"}}
    assert authority_fingerprint(doc=doc, requirement=req) == authority_fingerprint(
        doc=doc, requirement=req
    )


def test_audit_noise_pass_when_unchanged():
    from scripts.e1_snapshot import audit_authority_noise_snapshot

    snap = audit_authority_noise_snapshot({"audit_authority_events": 5}, {"audit_authority_events": 5})
    assert snap["noise_pass"] is True
