import pytest

from services.cer_actionability_presentation import (
    apply_actionability_cta_override,
    build_reopen_context_for_requirement,
    build_reopen_prefill_from_record,
    component_guidance_lines,
    resolve_actionability_primary_cta_label,
    resolve_existing_submission_banner_copy,
)
from services.cer_governance_presentation import attach_cer_governance_presentation


def test_smoke_incomplete_cta_specific():
    row = {
        "requirement_type": "smoke_heat_alarms",
        "truth_presentation_stage": "operational_incomplete",
        "evidence_completeness": {
            "evaluated": True,
            "is_complete": False,
            "missing_components": [{"key": "co_alarm", "label": "Carbon monoxide alarm compliance"}],
            "summary_label": "Incomplete: CO alarm evidence missing",
        },
    }
    assert resolve_actionability_primary_cta_label(row) == "Complete CO alarm details"
    assert any("monoxide" in x.lower() or "co" in x.lower() for x in component_guidance_lines(row))


def test_legionella_followup_cta_and_banner():
    base = {
        "requirement_type": "legionella",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "state_reason": "external_assessment_remediation_or_followup_unresolved",
            "semantic_state": "ASSESSMENT_FOLLOWUP_REQUIRED",
            "primary_evidence_record_id": "cer_1",
        },
    }
    row = {**base, **attach_cer_governance_presentation(base)}
    assert row["truth_presentation_stage"] == "followup_required"
    assert resolve_actionability_primary_cta_label(row) == "Update Legionella assessment"
    banner = resolve_existing_submission_banner_copy(row)
    assert banner
    assert "awaiting review" not in banner.lower()
    assert "follow-up" in banner.lower() or "update" in banner.lower()


def test_fire_risk_incomplete_not_followup_label():
    base = {
        "requirement_type": "fire_risk_assessment",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {
            "state": "MISSING",
            "state_reason": "multi_evidence_components_incomplete",
        },
        "evidence_completeness": {"is_complete": False, "required_missing_count": 1},
    }
    row = {**base, **attach_cer_governance_presentation(base)}
    assert row["truth_presentation_stage"] == "operational_incomplete"
    assert row["truth_presentation_label"] == "Additional action still required"
    assert resolve_actionability_primary_cta_label(row) == "Add missing fire-risk actions"


def test_queue_backed_banner_allows_review_wording():
    base = {
        "requirement_type": "gas_safety",
        "workflow_class": "DOCUMENT_UPLOAD",
        "client_lifecycle_state": "PENDING_REVIEW",
        "evidence_authority": {"state": "PENDING_ADMIN_REVIEW", "primary_evidence_record_id": "doc_1"},
        "evidence_doc_id": "doc_1",
    }
    row = {**base, **attach_cer_governance_presentation(base)}
    banner = resolve_existing_submission_banner_copy(row)
    assert banner
    assert "platform verification" in banner.lower() or "awaiting review" in banner.lower()


def test_reopen_prefill_structured():
    rec = {
        "evidence_record_id": "cer_x",
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_payload": {
            "declaration_statement": "I confirm",
            "structured_fields": {
                "actions_required": {"answer": True, "notes": None},
                "assessment_date": {"answer": "2025-01-01"},
            },
        },
    }
    pre = build_reopen_prefill_from_record(rec)
    assert pre["evidence_mode"] == "STRUCTURED_DECLARATION"
    assert pre["structured_fields_prefill"]["actions_required"]["answer"] is True


def test_reopen_context_prior_submission_when_assessment_recorded():
    requirement = {
        "requirement_type": "legionella",
        "truth_presentation_stage": "assessment_recorded",
    }
    rec = {
        "evidence_record_id": "cer_leg",
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_payload": {
            "declaration_statement": "Legionella assessment on file",
            "structured_fields": {
                "assessment_date": {"answer": "2024-06-01"},
                "actions_required": {"answer": False},
            },
        },
    }
    ctx = build_reopen_context_for_requirement(requirement, evidence_record=rec)
    assert ctx is not None
    assert ctx["reopen_reason"] == "prior_submission_update"
    assert ctx["truth_presentation_stage"] == "assessment_recorded"
    assert ctx["structured_fields_prefill"]["assessment_date"]["answer"] == "2024-06-01"


def test_reopen_context_follow_up_when_operational_incomplete():
    requirement = {
        "requirement_type": "smoke_heat_alarms",
        "truth_presentation_stage": "operational_incomplete",
    }
    rec = {
        "evidence_record_id": "cer_smoke",
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_payload": {
            "declaration_statement": "Partial",
            "structured_fields": {"co_alarm": {"answer": False}},
        },
    }
    ctx = build_reopen_context_for_requirement(requirement, evidence_record=rec)
    assert ctx is not None
    assert ctx["reopen_reason"] == "follow_up_update"


def test_reopen_context_none_without_primary_record():
    assert build_reopen_context_for_requirement({"truth_presentation_stage": "assessment_recorded"}, evidence_record=None) is None


def test_fire_alarm_operational_incomplete_cta_specific():
    """Staging fire_alarm rows normalize to smoke_heat_alarms but take_action resolves before completeness."""
    row = {
        "requirement_type": "fire_alarm",
        "truth_presentation_stage": "operational_incomplete",
        "evidence_completeness": {
            "evaluated": True,
            "is_complete": False,
            "missing_components": [{"key": "smoke_alarm", "label": "Smoke alarm compliance"}],
            "summary_label": "Incomplete: smoke alarm evidence missing",
        },
    }
    assert resolve_actionability_primary_cta_label(row) == "Complete smoke alarm details"


def test_fire_alarm_cta_override_after_early_generic_take_action():
    row = {
        "requirement_type": "fire_alarm",
        "truth_presentation_stage": "operational_incomplete",
        "evidence_completeness": {
            "evaluated": True,
            "is_complete": False,
            "missing_components": [{"key": "smoke_alarm", "label": "Smoke alarm compliance"}],
            "summary_label": "Incomplete: smoke alarm evidence missing",
        },
        "take_action": {
            "primary": {
                "label": "Add compliance evidence",
                "kind": "guided_evidence_resolution",
                "handler": "guided_evidence",
            }
        },
    }
    assert apply_actionability_cta_override(row) is True
    assert row["take_action"]["primary"]["label"] == "Complete smoke alarm details"


def test_alarm_installation_cta_from_missing_label():
    row = {
        "requirement_type": "smoke_heat_alarms",
        "truth_presentation_stage": "operational_incomplete",
        "evidence_completeness": {
            "evaluated": True,
            "is_complete": False,
            "missing_components": [{"key": "smoke_alarm", "label": "Alarm installation count missing"}],
        },
    }
    assert resolve_actionability_primary_cta_label(row) == "Complete alarm installation details"


def test_gas_safety_cta_not_overridden_without_operational_specificity():
    row = {
        "requirement_type": "gas_safety",
        "truth_presentation_stage": "action_required",
        "take_action": {"primary": {"label": "Upload Gas Safety Certificate"}},
    }
    assert apply_actionability_cta_override(row) is False
    assert row["take_action"]["primary"]["label"] == "Upload Gas Safety Certificate"
