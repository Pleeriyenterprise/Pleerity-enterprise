"""Unit tests for operational cognition envelope v1 (read-only, deterministic)."""
from __future__ import annotations

import pytest

from services.operational_cognition_service import (
    COGNITION_VERSION,
    FORBIDDEN_MUTATIONS,
    GUIDANCE_VERSION,
    TRUTH_DISTINCTIONS,
    assert_cognition_read_only,
    build_envelope_for_issue,
    build_envelope_for_job,
    build_envelope_for_requirement,
    build_envelope_for_rent_ledger,
    build_envelope_for_risk_signal,
    build_envelope_for_unresolved_evidence,
    build_list_guidance,
    build_requirement_guidance_v1,
)


def _assert_envelope_safety(envelope: dict) -> None:
    assert envelope["read_only"] is True
    assert envelope["cognition_version"] == COGNITION_VERSION
    assert set(envelope["forbidden_mutations"]) == set(FORBIDDEN_MUTATIONS)
    assert_cognition_read_only(envelope)


def test_job_envelope_primary_from_next_actions():
    payload = {
        "job_status": "OPEN",
        "status": "OPEN",
        "next_actions": [{"id": "assign", "label": "Assign contractor", "hint": "Pick a contractor", "section": "assignment"}],
    }
    env = build_envelope_for_job(payload)
    _assert_envelope_safety(env)
    assert env["primary_action"]["label"] == "Assign contractor"
    assert env["primary_action"]["source"] == "compliance_workflow_service.next_job_actions"


def test_job_envelope_assigned_not_fixed_truth():
    payload = {
        "job_status": "ASSIGNED",
        "status": "ASSIGNED",
        "contractor_id": "c-1",
        "next_actions": [],
    }
    env = build_envelope_for_job(payload)
    assert env["operational_truth_flags"]["assigned_not_fixed"] is True
    assert any(w["code"] == "ASSIGNED_NOT_FIXED" for w in env["warnings"])


def test_issue_envelope_continuation_primary():
    issue = {
        "status": "open",
        "operational_continuation": {
            "has_active_lineage": True,
            "continuation_cta": {"key": "view_workflow", "label": "View active job", "url": "/operations/jobs/wo-1"},
            "user_safe_reason": "Job already exists",
            "continuation_state": "ACTIVE",
        },
    }
    env = build_envelope_for_issue(issue)
    _assert_envelope_safety(env)
    assert env["primary_action"]["label"] == "View active job"
    assert env["list_guidance"]["recommended_action_label"] == "View active job"


def test_requirement_envelope_false_progression():
    req = {
        "client_lifecycle_state": "PENDING_REVIEW",
        "lifecycle_tier": "overdue",
        "evidence_completeness": {"required_missing_count": 2},
        "take_action": {
            "primary": {"intent": "upload", "label": "Upload evidence", "route": "/documents?x=1"},
        },
    }
    env = build_envelope_for_requirement(req)
    _assert_envelope_safety(env)
    assert env["operational_truth_flags"]["submitted_not_compliant"] is True
    assert any(b["code"] == "DECLARATION_INCOMPLETE" for b in env["blockers"])
    assert env["escalation_state"]["active"] is True
    guidance = env.get("requirement_guidance_v1") or {}
    assert guidance.get("guidance_version") == GUIDANCE_VERSION
    assert guidance.get("submitted_not_verified") is True
    assert isinstance(guidance.get("progression_steps"), list)


def test_requirement_guidance_rejected_requires_resubmit():
    req = {
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {"state": "REJECTED"},
        "registry_metadata": {
            "evidence_resolution": {
                "allowed_evidence_modes": ["STRUCTURED_DECLARATION", "CONTRACTOR_CONFIRMATION"],
                "primary_resolution_workflow": "GUIDED_DECLARATION",
            }
        },
    }
    guidance = build_requirement_guidance_v1(req)
    assert guidance["rejected_requires_action"] is True
    assert guidance["strongest_evidence_method"] == "STRUCTURED_DECLARATION"
    assert "CONTRACTOR_CONFIRMATION" in guidance["weaker_alternative_methods"]
    assert "resubmit" in guidance["recommended_next_step"].lower()


def test_requirement_guidance_uploaded_not_submitted():
    req = {
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {"state": "UPLOADED_UNCONFIRMED"},
        "registry_metadata": {
            "evidence_resolution": {
                "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
                "primary_resolution_workflow": "GUIDED_DECLARATION",
            }
        },
    }
    guidance = build_requirement_guidance_v1(req)
    assert guidance["uploaded_not_submitted"] is True
    assert guidance["current_progress_state"] == "supporting_uploaded"
    assert "vault" in guidance["recommended_next_step_reason"].lower() or "structured" in guidance["recommended_next_step"].lower()


def test_requirement_guidance_read_only():
    req = {"client_lifecycle_state": "ACTION_REQUIRED", "evidence_authority": {"state": "MISSING"}}
    guidance = build_requirement_guidance_v1(req)
    assert guidance["read_only"] is True
    assert guidance["guidance_version"] == GUIDANCE_VERSION


def test_rent_ledger_overdue_primary():
    ledger = {
        "ledger_id": "l-1",
        "property_id": "p-1",
        "tenant_name": "Tenant A",
        "period_key": "2026-05",
        "status": "OVERDUE",
        "is_overdue": True,
        "outstanding_balance_minor": 50000,
    }
    env = build_envelope_for_rent_ledger(ledger)
    _assert_envelope_safety(env)
    assert env["primary_action"]["key"] == "record_payment"
    assert env["escalation_state"]["active"] is True


def test_unresolved_evidence_never_implies_verified():
    doc = {"document_id": "d-1", "file_name": "scan.pdf", "evidence_review_state": "UNRESOLVED"}
    env = build_envelope_for_unresolved_evidence(doc)
    _assert_envelope_safety(env)
    assert env["operational_truth_flags"]["uploaded_not_verified"] is True
    assert TRUTH_DISTINCTIONS["uploaded_not_verified"] in env["blockers"][0]["truth_note"]


def test_risk_signal_list_guidance_parity():
    signal = {
        "risk_type": "Boiler risk",
        "status": "active",
        "operational_continuation": {"has_active_lineage": True, "continuation_cta": {"label": "View job"}},
    }
    env = build_envelope_for_risk_signal(signal)
    guidance = build_list_guidance(env)
    assert guidance["recommended_action_label"] == env["primary_action"]["label"]
