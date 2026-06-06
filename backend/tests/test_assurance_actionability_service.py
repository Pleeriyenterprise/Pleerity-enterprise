"""Assurance vs operational actionability convergence."""

from datetime import datetime, timezone

from services.assurance_actionability_service import (
    ASSURANCE_CONFIDENCE_OPPORTUNITY,
    OPERATIONAL_ACTION,
    STALE_INVALID,
    classify_score_action,
    partition_score_recommendations,
    requirement_has_assurance_confidence_gap,
    task_is_assurance_only_inbox_item,
)
from services.today_projection_service import today_task_is_actionable


def _satisfied_self_recorded():
    return {
        "requirement_id": "r1",
        "property_id": "p1",
        "truth_presentation_stage": "recorded_on_file",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "assurance_tier": "SELF_RECORDED",
        "requirement_satisfied": True,
        "status": "PENDING",
    }


def test_requirement_has_assurance_confidence_gap_when_satisfied_self_recorded():
    assert requirement_has_assurance_confidence_gap(_satisfied_self_recorded()) is True


def test_classify_score_action_stale_when_satisfied_no_gap():
    row = {
        "requirement_id": "r1",
        "property_id": "p1",
        "truth_presentation_stage": "verified",
        "client_lifecycle_state": "VERIFIED",
        "assurance_tier": "VERIFIED",
        "requirement_satisfied": True,
        "status": "COMPLIANT",
        "evidence_authority_synced_at": "2026-01-01T00:00:00Z",
        "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT", "effective_expiry_date": "2027-01-01"},
    }
    action = {"action": "Some evidence is self-recorded", "requirement_code": "GAS_SAFETY"}
    assert classify_score_action(action, row) == STALE_INVALID


def test_classify_score_action_assurance_for_satisfied_self_recorded():
    action = {"action": "Some evidence is self-recorded or awaiting verification", "requirement_code": "FIRE_DETECTION"}
    assert classify_score_action(action, _satisfied_self_recorded()) == ASSURANCE_CONFIDENCE_OPPORTUNITY


def test_classify_score_action_operational_for_overdue():
    row = {
        "requirement_id": "r2",
        "property_id": "p1",
        "status": "OVERDUE",
        "truth_presentation_stage": "action_required",
        "client_lifecycle_state": "ACTION_REQUIRED",
    }
    action = {"action": "Upload gas safety certificate", "requirement_code": "GAS_SAFETY"}
    assert classify_score_action(action, row) == OPERATIONAL_ACTION


def test_partition_score_recommendations_splits_assurance():
    req = _satisfied_self_recorded()
    actions = [
        {
            "requirement_code": "FIRE_DETECTION",
            "property_id": "p1",
            "action": "Some evidence for Smoke is self-recorded or awaiting verification",
            "impact_points": 2,
            "priority": "high",
        }
    ]
    req_by_id = {("p1", "r1"): req}
    req_by_code = {("p1", "fire_detection"): req}
    operational, assurance = partition_score_recommendations(actions, req_by_id, req_by_code)
    assert len(operational) == 0
    assert len(assurance) == 1
    assert assurance[0]["priority"] == "info"
    assert assurance[0]["action_kind"] == ASSURANCE_CONFIDENCE_OPPORTUNITY


def test_issue_task_assurance_only_suppressed_from_today_actionable():
    task = {
        "id": "issue:r1",
        "source_type": "issue",
        "source_entity_id": "r1",
        "property_id": "p1",
        "title": "Please review the uploaded file",
        "metadata": {
            "requirement_id": "r1",
            "issue_triggering_rule": "MISMATCHED_EVIDENCE",
            "truth_presentation_stage": "recorded_on_file",
            "client_lifecycle_state": "SATISFIED_UNVERIFIED",
            "assurance_tier": "SELF_RECORDED",
            "requirement_satisfied": True,
        },
        "business_actions": [{"id": "view", "label": "Review"}],
        "primary_action_url": "/requirements",
    }
    assert task_is_assurance_only_inbox_item(task) is True
    assert today_task_is_actionable(task) is False


def test_scenario_missing_evidence_remains_operational():
    row = {
        "requirement_id": "r3",
        "property_id": "p1",
        "status": "MISSING",
        "truth_presentation_stage": "collect_evidence",
        "client_lifecycle_state": "ACTION_REQUIRED",
    }
    task = {
        "id": "requirement:r3",
        "source_type": "requirement",
        "source_entity_id": "r3",
        "property_id": "p1",
        "metadata": {
            "requirement_id": "r3",
            "truth_presentation_stage": "collect_evidence",
            "status": "MISSING",
        },
        "business_actions": [{"id": "upload", "label": "Upload"}],
    }
    assert classify_score_action({"action": "Upload evidence", "requirement_code": "EICR"}, row) == OPERATIONAL_ACTION
    assert today_task_is_actionable(task) is True
