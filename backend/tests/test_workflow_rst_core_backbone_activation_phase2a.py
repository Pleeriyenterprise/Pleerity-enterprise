"""Phase 2A: RST core backbone activation (registry + guards + fanout hooks; mocked paths)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import services.authority_mutation_fanout as amf
import services.workflow_runtime_activation_registry as reg
from services.workflow_activation_readiness import (
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
)
from services.workflow_runtime_activation_registry import (
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
    GUARD_RESULT_BLOCKED_CORE_BACKBONE_COMPOSITE_CHILD,
    GUARD_RESULT_PERMITTED,
    build_rst_core_backbone_activation_operational_visibility,
    build_runtime_activation_snapshot,
    list_registry_family_keys,
    resolve_requirement_state_transition_core_backbone_gate,
)
from services.workflow_runtime_activation_validation import (
    VALIDATION_CONFIRMED,
    build_runtime_activation_validation_snapshot,
    validate_live_rst_core_backbone_gate,
    validate_rst_core_backbone_convergence_continuity,
)
from services.workflow_activation_governance_report import build_workflow_activation_governance_report
from services.requirement_transition_observability import merge_rst_core_backbone_activation_into_fanout


def test_registry_v3_and_backbone_family_key():
    assert ACTIVATION_GOVERNANCE_VERSION == "workflow_runtime_activation_registry_v3"
    assert FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE in list_registry_family_keys()


def test_rst_core_backbone_gate_permitted_under_default_ceiling():
    g = resolve_requirement_state_transition_core_backbone_gate()
    assert g["permitted"] is True
    assert g["activation_guard_result"] == GUARD_RESULT_PERMITTED
    assert g["activation_scope"] == "requirement_state_transition_core_backbone_only"
    assert g["activation_governance_version"] == ACTIVATION_GOVERNANCE_VERSION
    v = validate_live_rst_core_backbone_gate()
    assert v["activation_validation"] == VALIDATION_CONFIRMED


def test_rst_core_backbone_blocked_when_registry_observe_only():
    with patch.dict(reg._REGISTRY_CEILING, {FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE: ACTIVATION_OBSERVE_ONLY}, clear=False):
        g = resolve_requirement_state_transition_core_backbone_gate()
        assert g["permitted"] is False


def test_rst_core_backbone_blocked_when_child_compliance_observe_only():
    with patch.dict(reg._REGISTRY_CEILING, {reg.FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_OBSERVE_ONLY}, clear=False):
        g = resolve_requirement_state_transition_core_backbone_gate()
        assert g["permitted"] is False
        assert g["activation_guard_result"] == GUARD_RESULT_BLOCKED_CORE_BACKBONE_COMPOSITE_CHILD


def test_snapshot_ordering_includes_backbone_row():
    snap = build_runtime_activation_snapshot(generated_at_iso="2026-05-12T12:00:00Z")
    fams = [str(r.get("activation_family")) for r in snap.get("families") or []]
    assert fams == sorted(fams)
    assert FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE in fams


def test_operational_visibility_schema():
    vis = build_rst_core_backbone_activation_operational_visibility(generated_at_iso="2026-05-12T12:00:00Z")
    assert vis["rst_core_backbone_permitted"] is True
    assert vis["schema_version"] == "rst_core_backbone_activation_operational_visibility_v1"


def test_governance_report_embeds_rst_core_backbone_visibility():
    rep = build_workflow_activation_governance_report(generated_at_iso="2026-05-12T12:00:00Z")
    assert "requirement_transition_core_backbone_activation_operational_visibility" in rep
    assert rep["requirement_transition_core_backbone_activation_operational_visibility"]["schema_version"].endswith("_v1")


def test_validation_snapshot_has_rst_core_backbone_blocks():
    snap = build_runtime_activation_validation_snapshot(generated_at_iso="2026-05-12T12:00:00Z")
    assert "rst_core_backbone_gate_validation" in snap
    assert "rst_core_backbone_convergence_continuity" in snap


def test_convergence_continuity_on_mock_trace():
    gate = resolve_requirement_state_transition_core_backbone_gate()
    tr = {
        "correlation_id": "x",
        "transition_id": "t1",
        "downstream_trigger_targets": [
            {"downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc", "enqueue_outcome": "ENQUEUE_ACCEPTED"}
        ],
    }
    merge_rst_core_backbone_activation_into_fanout(tr, gate, propagation_continuity="PROPAGATION_CONTINUITY_ACTIVE")
    v = validate_rst_core_backbone_convergence_continuity(transition_traces=[tr])
    assert v["activation_validation"] == VALIDATION_CONFIRMED


async def _authority_sync_blocked_skips_downstream():
    mock_db = MagicMock()
    fanout: dict = {"transition_id": "tid", "correlation_id": "cid"}
    with patch.dict(reg._REGISTRY_CEILING, {FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE: ACTIVATION_OBSERVE_ONLY}, clear=False):
        await amf.authority_sync_with_transition_observability(
            mock_db,
            "req1",
            property_id="p1",
            client_id="c1",
            correlation_base="cid",
            transition_origin="test",
            transition_fanout=fanout,
        )
    assert "rst_core_backbone_activation" in fanout
    rows = fanout.get("downstream_trigger_targets") or []
    assert rows and "requirement_state_transition.core_backbone.authority_sync" in str(rows[0].get("downstream_target"))


def test_authority_sync_skips_when_backbone_blocked():
    asyncio.run(_authority_sync_blocked_skips_downstream())


async def _enqueue_skipped_when_backbone_blocked():
    with patch.dict(reg._REGISTRY_CEILING, {FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE: ACTIVATION_OBSERVE_ONLY}, clear=False):
        tf = {"transition_id": "tid", "correlation_id": "cid"}
        await amf.enqueue_compliance_recalc_with_fanout(
            tf,
            property_id="p",
            client_id="c",
            trigger_reason="DOC_UPLOADED",
            actor_type="ADMIN",
            actor_id=None,
            correlation_id="corr",
            trigger_origin="test",
            propagation_stage="stage",
        )
        rows = tf.get("downstream_trigger_targets") or []
        assert any("compliance_recalc_queue.enqueue_compliance_recalc" in str(r.get("downstream_target")) for r in rows)


def test_enqueue_fanout_skips_under_backbone_observe_only():
    asyncio.run(_enqueue_skipped_when_backbone_blocked())
