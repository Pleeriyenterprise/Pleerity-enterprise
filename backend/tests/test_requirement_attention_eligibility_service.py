"""Tests for requirement attention eligibility (Today / CC convergence)."""
from __future__ import annotations

from datetime import datetime, timezone

from services.compliance_gap_engine import infer_compliance_gaps_for_requirement
from services.requirement_attention_eligibility_service import (
    SUPPRESSION_SATISFIED_VERIFIED,
    is_requirement_attention_eligible,
)
from services.requirement_truth import requirement_has_active_negative_actionability


def _verified_gas_row() -> dict:
    return {
        "requirement_id": "r-gas",
        "property_id": "p1",
        "client_id": "c1",
        "requirement_type": "gas_safety",
        "status": "PENDING",
        "truth_presentation_stage": "verified",
        "truth_presentation_label": "Verified",
        "semantic_state": "VERIFIED",
        "client_lifecycle_state": "VERIFIED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {
            "version": 1,
            "state": "VERIFIED_CURRENT",
            "effective_expiry_date": "2027-06-01T00:00:00+00:00",
        },
        "take_action": {"primary": {"label": "Upload valid gas safety certificate", "route": "/properties/p1"}},
    }


def test_verified_gas_suppressed_despite_legacy_pending_status():
    row = _verified_gas_row()
    eligible, reason, suppression = is_requirement_attention_eligible(row)
    assert eligible is False
    assert suppression == SUPPRESSION_SATISFIED_VERIFIED
    assert reason is None
    assert requirement_has_active_negative_actionability(row) is False


def test_legionella_declaration_recorded_suppressed():
    row = {
        "requirement_id": "r-leg",
        "requirement_type": "legionella",
        "status": "PENDING",
        "truth_presentation_stage": "declaration_recorded",
        "semantic_state": "DECLARATION_RECORDED",
        "governance_family": "SELF_CERTIFIED",
        "take_action": {"suppressed": True, "primary": None},
    }
    eligible, _, suppression = is_requirement_attention_eligible(row)
    assert eligible is False
    assert suppression is not None


def test_rejected_evidence_remains_attention_eligible():
    row = {
        "requirement_id": "r-rej",
        "requirement_type": "epc",
        "truth_presentation_stage": "action_required",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "REJECTED"},
        "take_action": {
            "primary": {"label": "Replace document", "route": "/documents?property_id=p1"},
        },
    }
    eligible, reason, _ = is_requirement_attention_eligible(row)
    assert eligible is True
    assert reason == "rejected"


def test_admin_review_suppressed_when_recorded_on_file():
    row = {
        "requirement_id": "r-smoke",
        "requirement_type": "smoke_heat_alarms",
        "status": "PENDING",
        "truth_presentation_stage": "recorded_on_file",
        "semantic_state": "EVIDENCE_ACCEPTED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "PENDING_ADMIN_REVIEW"},
    }
    eligible, reason, suppression = is_requirement_attention_eligible(row)
    assert eligible is False
    assert reason is None
    assert suppression is not None
    assert requirement_has_active_negative_actionability(row) is False


def test_expiring_verified_remains_attention_eligible():
    row = _verified_gas_row()
    row["evidence_authority"]["effective_expiry_date"] = "2026-06-15T00:00:00+00:00"
    row["take_action"] = {"primary": {"label": "Plan renewal", "route": "/properties/p1"}}
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    eligible, reason, _ = is_requirement_attention_eligible(row, now=now, expiring_window_days=60)
    assert eligible is True
    assert reason == "renewal_due"


def test_infer_gaps_empty_for_satisfied_verified():
    row = _verified_gas_row()
    gaps = infer_compliance_gaps_for_requirement(row, property_doc=None)
    assert gaps == []


def test_assessment_recorded_suppresses_stale_estimated_overdue():
    """Legionella-style: assessment on file + legacy OVERDUE from estimated renewal must not panic."""
    row = {
        "requirement_id": "r-leg-overdue",
        "requirement_type": "legionella",
        "requirement_code": "legionella",
        "status": "OVERDUE",
        "due_date": "2026-05-16T00:00:00+00:00",
        "truth_presentation_stage": "assessment_recorded",
        "truth_presentation_label": "Assessment recorded",
        "semantic_state": "DECLARATION_RECORDED",
        "governance_family": "PLATFORM_OVERSIGHT_OPTIONAL",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {
            "version": 1,
            "state": "MISSING",
            "primary_evidence_record_id": "cer-leg-1",
        },
        "primary_evidence_record_id": "cer-leg-1",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "take_action": {"suppressed": True, "primary": None},
    }
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    eligible, reason, suppression = is_requirement_attention_eligible(row, now=now)
    assert eligible is False
    assert reason is None
    assert suppression is not None


def test_escalation_review_preempts_stale_calendar_expired():
    row = {
        "requirement_id": "r-hmo-esc",
        "requirement_type": "hmo_licence",
        "status": "OVERDUE",
        "due_date": "2025-01-01T00:00:00+00:00",
        "truth_presentation_stage": "escalation_review",
        "truth_presentation_label": "Escalated for platform review",
        "review_owner": "platform_admin_escalation",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT"},
        "client_lifecycle_state": "PENDING_REVIEW",
    }
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    eligible, reason, _ = is_requirement_attention_eligible(row, now=now)
    assert eligible is True
    assert reason == "escalation_review"


def test_document_overdue_with_legacy_due_still_expired():
    row = {
        "requirement_id": "r-epc",
        "requirement_type": "epc",
        "status": "OVERDUE",
        "due_date": "2025-01-01T00:00:00+00:00",
        "governance_family": "PLATFORM_VERIFICATION",
        "document_upload_required": True,
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "MISSING"},
    }
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    eligible, reason, _ = is_requirement_attention_eligible(row, now=now)
    assert eligible is True
    assert reason == "expired"
