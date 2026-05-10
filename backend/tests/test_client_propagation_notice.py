"""L-009 client-safe propagation_notice from transition fanout."""

from __future__ import annotations

from services.client_propagation_notice import (
    NOTICE_AUTHORITY_SYNC_DEFERRED,
    NOTICE_RECALC_ENQUEUE_DEFERRED,
    build_propagation_notice_from_transition_fanout,
    merge_propagation_notice_from_ordered_transition_fanouts,
)


def test_no_notice_when_empty_fanout():
    assert build_propagation_notice_from_transition_fanout(None) is None
    assert build_propagation_notice_from_transition_fanout({}) is None


def test_notice_when_rst_backbone_blocks_authority_sync():
    fanout = {
        "rst_core_backbone_activation": {
            "permitted": False,
            "activation_reason": "rst_core_backbone_registry_ceiling_disabled",
        }
    }
    n = build_propagation_notice_from_transition_fanout(fanout)
    assert n is not None
    assert n["code"] == NOTICE_AUTHORITY_SYNC_DEFERRED
    assert "not fully synchronised" in n["message"].lower() or "synchronised" in n["message"].lower()


def test_notice_when_recalc_enqueue_skipped_due_to_backbone():
    fanout = {
        "rst_core_backbone_activation": {"permitted": True},
        "downstream_trigger_targets": [
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "propagation_stage": "post_verify:rst_core_backbone_blocked_skip_enqueue",
            }
        ],
    }
    n = build_propagation_notice_from_transition_fanout(fanout)
    assert n is not None
    assert n["code"] == NOTICE_RECALC_ENQUEUE_DEFERRED
    assert "background" in n["message"].lower()


def test_authority_blocked_takes_precedence_over_recalc_row():
    fanout = {
        "rst_core_backbone_activation": {"permitted": False},
        "downstream_trigger_targets": [
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "propagation_stage": "x:rst_core_backbone_blocked_skip_enqueue",
            }
        ],
    }
    n = build_propagation_notice_from_transition_fanout(fanout)
    assert n["code"] == NOTICE_AUTHORITY_SYNC_DEFERRED


def test_merge_ordered_prefers_authority_on_later_fanout():
    prior = {
        "rst_core_backbone_activation": {"permitted": True},
        "downstream_trigger_targets": [
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "propagation_stage": "post:rst_core_backbone_blocked_skip_enqueue",
            }
        ],
    }
    new = {"rst_core_backbone_activation": {"permitted": False}}
    n = merge_propagation_notice_from_ordered_transition_fanouts([prior, new])
    assert n is not None
    assert n["code"] == NOTICE_AUTHORITY_SYNC_DEFERRED


def test_merge_ordered_first_recalc_when_no_authority():
    prior = {"rst_core_backbone_activation": {"permitted": True}}
    new = {
        "rst_core_backbone_activation": {"permitted": True},
        "downstream_trigger_targets": [
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "propagation_stage": "post:rst_core_backbone_blocked_skip_enqueue",
            }
        ],
    }
    n = merge_propagation_notice_from_ordered_transition_fanouts([prior, new])
    assert n is not None
    assert n["code"] == NOTICE_RECALC_ENQUEUE_DEFERRED


def test_merge_empty_sequence_returns_none():
    assert merge_propagation_notice_from_ordered_transition_fanouts(()) is None
    assert merge_propagation_notice_from_ordered_transition_fanouts([{}, {}]) is None
