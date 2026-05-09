from __future__ import annotations

from services.governance_ux_trust_architecture import (
    BADGE_PLUS_SUBLINE,
    CLIENT_STATUS_CHIP,
    DISCLOSURE_REQUIRED_SIMPLIFICATION,
    EXPORT_PLUS_DISCLOSURE_BLOCK,
    FOUNDATIONAL_TRUST_FIX,
    HIGH_RISK_PUBLIC_SURFACE,
    LAYER_COMPACT_SIGNAL,
    LAYER_DISCLOSURE_SUPPORT,
    LOW_COGNITIVE_LOAD,
    PORTFOLIO_SCORE,
    REPORT_EXPORT,
    SAFE_TRUTHFUL_SIMPLIFICATION,
    SCORE_PLUS_CONTEXT_PANEL,
    build_cognitive_load_matrix,
    build_consumer_disclosure_layering_catalog,
    build_governance_ux_trust_architecture_phase5_snapshot,
    build_remediation_sequencing_plan,
    build_truthful_simplification_matrix,
    build_ux_trust_layer_matrix,
    phase5_snapshot_fingerprint,
    write_governance_ux_trust_architecture_phase5_json,
)


def test_snapshot_fingerprint_stability():
    assert phase5_snapshot_fingerprint() == (
        "94e30e7dfcec628b3de828751a32768b5ec11876fa83c6479f996702e7a1a58c"
    )


def test_trust_layer_matrix_determinism():
    m = build_ux_trust_layer_matrix()
    assert len(m) == 13 * 3
    row = next(r for r in m if r["semantic_state"] == "VERIFIED_CURRENT" and r["consumer"] == CLIENT_STATUS_CHIP)
    assert row["minimum_required_layer"] == LAYER_COMPACT_SIGNAL
    exp = next(r for r in m if r["semantic_state"] == "DECLARATION_RECORDED" and r["consumer"] == REPORT_EXPORT)
    assert exp["minimum_required_layer"] == LAYER_DISCLOSURE_SUPPORT


def test_truthful_simplification_governance():
    t = build_truthful_simplification_matrix()
    assert t["VERIFIED_CURRENT"]["simplification_class"] == SAFE_TRUTHFUL_SIMPLIFICATION
    assert t["PARTIALLY_COMPLETE"]["simplification_class"] == DISCLOSURE_REQUIRED_SIMPLIFICATION


def test_disclosure_layering_catalog():
    c = build_consumer_disclosure_layering_catalog()
    assert BADGE_PLUS_SUBLINE in c[CLIENT_STATUS_CHIP]["preferred_patterns"]
    assert EXPORT_PLUS_DISCLOSURE_BLOCK in c[REPORT_EXPORT]["preferred_patterns"]
    assert SCORE_PLUS_CONTEXT_PANEL in c[PORTFOLIO_SCORE]["preferred_patterns"]


def test_cognitive_load_matrix():
    cm = build_cognitive_load_matrix()
    vc = next(
        r for r in cm if r["semantic_state"] == "VERIFIED_CURRENT" and r["consumer"] == CLIENT_STATUS_CHIP
    )
    assert vc["cognitive_load_class"] == LOW_COGNITIVE_LOAD


def test_remediation_sequencing_order():
    plan = build_remediation_sequencing_plan()
    assert plan[0]["sequencing_category"] == FOUNDATIONAL_TRUST_FIX
    assert plan[1]["sequencing_category"] == HIGH_RISK_PUBLIC_SURFACE
    assert all("sequence_rank" in x for x in plan)


def test_anti_patterns_determinism():
    snap = build_governance_ux_trust_architecture_phase5_snapshot()
    assert len(snap["highest_risk_ux_anti_patterns"]) == 6
    assert "Green Compliant chip" in snap["highest_risk_ux_anti_patterns"][0]


def test_phase5_snapshot_shape_and_flags():
    snap = build_governance_ux_trust_architecture_phase5_snapshot()
    assert snap["audit_only"] is True
    assert snap["runtime_behavior_changed"] is False
    assert snap["non_blocking"] is True
    for k in (
        "ux_trust_layer_matrix",
        "truthful_simplification_governance_matrix",
        "disclosure_layering_catalog",
        "cognitive_load_matrix",
        "remediation_sequencing_plan",
        "consumer_specific_trust_guidance",
        "prohibited_compression_patterns",
    ):
        assert k in snap


def test_write_phase5_json(tmp_path):
    p = tmp_path / "ux5.json"
    write_governance_ux_trust_architecture_phase5_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"ux_trust_layer_matrix"' in text
