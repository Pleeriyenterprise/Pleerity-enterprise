from __future__ import annotations

import hashlib
import json

from services.operational_confirmation_topology_audit import (
    BATCH_OBSERVABILITY_FIRST,
    BATCH_REPORTING_ALIGNMENT,
    BATCH_SAFE_READ_PATHS,
    BLOCKED_FROM_IMPLEMENTATION,
    DEPENDENCY_NONE,
    DEPENDENCY_REPORTING_SEMANTICS,
    DO_NOT_IMPLEMENT_YET,
    EVENT_MODEL_REQUIRED,
    FIRST_WAVE_ELIGIBLE,
    FIRST_WAVE_WITH_REVIEW,
    NOT_SAFE_TO_IMPLEMENT,
    OBSERVABILITY_FIRST,
    READY_FOR_IMPLEMENTATION,
    RUNTIME_ARCHITECTURE_REQUIRED,
    SAFE_ENGINEERING_FIX,
    SEMANTIC_TRANSITIONS,
    UNSAFE_SEMANTIC_COLLAPSE,
    build_operational_confirmation_remediation_triage_matrix,
    build_operational_confirmation_remediation_phase2_triage_snapshot,
    write_operational_confirmation_remediation_phase2_triage_json,
)


def _triage_fingerprint(matrix):
    payload = [
        (
            r["semantic_transition"],
            r["consumer"],
            r["remediation_track"],
            r["implementation_readiness"],
            r["primary_dependency"],
            r["first_wave_eligibility"],
            r["recommended_batch"],
            r["unsafe_to_implement"],
            tuple(r.get("unsafe_reasons") or []),
            tuple(r.get("secondary_dependencies") or []),
        )
        for r in matrix
    ]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def _cell(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"missing {transition}/{consumer}")


def test_triage_matrix_size_and_row_shape():
    m = build_operational_confirmation_remediation_triage_matrix()
    assert len(m) == len(SEMANTIC_TRANSITIONS) * 15
    row = m[0]
    for k in (
        "remediation_track",
        "remediation_track_reasoning",
        "primary_dependency",
        "secondary_dependencies",
        "recommended_batch",
        "first_wave_eligibility",
        "unsafe_to_implement",
        "unsafe_reasons",
        "implementation_readiness",
        "implementation_readiness_reasoning",
    ):
        assert k in row
    assert isinstance(row["secondary_dependencies"], list)


def test_triage_classification_stability():
    m = build_operational_confirmation_remediation_triage_matrix()
    assert _triage_fingerprint(m) == (
        "ba6d302e9625972e721b60173f61f27350435c6702bcd39c20d3e0c7a444b43f"
    )


def test_known_cell_tracks_readiness_dependencies():
    m = build_operational_confirmation_remediation_triage_matrix()
    req = _cell(m, "VERIFIED_CURRENT", "REQUIREMENT_LIST")
    assert req["remediation_track"] == SAFE_ENGINEERING_FIX
    assert req["primary_dependency"] == DEPENDENCY_NONE
    assert req["recommended_batch"] == BATCH_SAFE_READ_PATHS
    assert req["unsafe_to_implement"] is False
    assert req["unsafe_reasons"] == []

    rep = _cell(m, "DECLARATION_RECORDED", "PORTFOLIO_SCORE")
    assert rep["primary_dependency"] == DEPENDENCY_REPORTING_SEMANTICS
    assert UNSAFE_SEMANTIC_COLLAPSE in (rep.get("unsafe_reasons") or [])
    assert rep["remediation_track"] == DO_NOT_IMPLEMENT_YET
    assert rep["recommended_batch"] == BATCH_REPORTING_ALIGNMENT
    assert rep["implementation_readiness"] == NOT_SAFE_TO_IMPLEMENT


def test_first_wave_and_blocked_posture_stability():
    m = build_operational_confirmation_remediation_triage_matrix()
    summary = {}
    for r in m:
        fw = r["first_wave_eligibility"]
        summary[fw] = summary.get(fw, 0) + 1
    assert summary == {
        "BLOCKED_FROM_IMPLEMENTATION": 28,
        "OBSERVE_ONLY_FOR_NOW": 75,
        "SECOND_WAVE_ONLY": 92,
    }
    assert not any(r["first_wave_eligibility"] == FIRST_WAVE_ELIGIBLE for r in m)
    assert not any(r["first_wave_eligibility"] == FIRST_WAVE_WITH_REVIEW for r in m)


def test_snapshot_grouped_summaries_and_audit_markers():
    snap = build_operational_confirmation_remediation_phase2_triage_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    for k in (
        "remediation_triage_matrix",
        "first_wave_candidates",
        "blocked_implementation_candidates",
        "observability_first_candidates",
        "runtime_architecture_required_clusters",
        "process_governance_required_clusters",
        "product_policy_required_clusters",
        "unsafe_to_implement_clusters",
        "remediation_batch_summary",
        "implementation_readiness_summary",
        "dependency_summary",
        "remediation_track_summary",
        "first_wave_eligibility_summary",
        "unsafe_reason_summary",
        "remaining_state_model_limitation",
        "remaining_runtime_convergence_limitation",
    ):
        assert k in snap

    m = snap["remediation_triage_matrix"]
    assert sum(snap["implementation_readiness_summary"].values()) == len(m)
    assert sum(snap["remediation_batch_summary"].values()) == len(m)
    assert sum(snap["remediation_track_summary"].values()) == len(m)
    assert sum(snap["first_wave_eligibility_summary"].values()) == len(m)
    assert sum(snap["dependency_summary"].values()) == len(m)

    assert snap["remediation_track_summary"][RUNTIME_ARCHITECTURE_REQUIRED] == 8
    assert snap["remediation_track_summary"][EVENT_MODEL_REQUIRED] == 45
    assert snap["remediation_track_summary"][OBSERVABILITY_FIRST] == 18
    assert snap["remediation_track_summary"][DO_NOT_IMPLEMENT_YET] == 25

    obs = snap["observability_first_candidates"]
    assert all(
        r.get("remediation_track") == OBSERVABILITY_FIRST
        or r.get("recommended_batch") == BATCH_OBSERVABILITY_FIRST
        for r in obs
    )
    blocked = {f"{x['consumer']}:{x['semantic_transition']}" for x in snap["blocked_implementation_candidates"]}
    for r in m:
        if r["first_wave_eligibility"] == BLOCKED_FROM_IMPLEMENTATION or r["implementation_readiness"] == NOT_SAFE_TO_IMPLEMENT:
            assert f"{r['consumer']}:{r['semantic_transition']}" in blocked


def test_write_phase2_triage_json(tmp_path):
    p = tmp_path / "phase2_triage.json"
    write_operational_confirmation_remediation_phase2_triage_json(target_path=p)
    text = p.read_text(encoding="utf-8")
    assert '"audit_only": true' in text
    assert '"runtime_behavior_changed": false' in text
    assert '"remediation_triage_matrix"' in text


def test_ready_for_implementation_only_when_eligible():
    m = build_operational_confirmation_remediation_triage_matrix()
    for r in m:
        if r["implementation_readiness"] == READY_FOR_IMPLEMENTATION:
            assert r["first_wave_eligibility"] == FIRST_WAVE_ELIGIBLE
