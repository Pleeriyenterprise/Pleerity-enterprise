"""S2 — customer_status_projector_v2 unit and integration tests."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from services import customer_status_vocabulary as vocab
from services.cer_governance_presentation import GF_PLATFORM_VER, GF_SELF
from services.customer_status_projector_config import get_customer_status_projector_mode
from services.customer_status_projector_shadow import compare_legacy_vs_projector
from services.customer_status_projector_v2 import (
    apply_customer_status_projection,
    project_customer_status,
    resolve_obligation_class,
)
from services.requirement_truth import enrich_requirement_dict


def _base_row(**overrides):
    row = {
        "requirement_id": "req-test-1",
        "client_id": "client-test-1",
        "property_id": "prop-test-1",
        "requirement_code": "tenancy_agreement",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "evidence_authority": {"state": "EA_MISSING"},
        "governance_family": GF_SELF,
    }
    row.update(overrides)
    return row


@pytest.fixture(autouse=True)
def _default_projector_disabled(monkeypatch):
    monkeypatch.delenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", raising=False)


def test_config_defaults_disabled():
    assert get_customer_status_projector_mode() == "disabled"


def test_config_shadow_mode(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "shadow")
    assert get_customer_status_projector_mode() == "shadow"


def test_class_a_no_evidence():
    row = _base_row()
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.ACTION_REQUIRED
    assert out["customer_status_class"] == "A"


def test_class_a_recorded():
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
        client_lifecycle_state="SATISFIED_UNVERIFIED",
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.RECORDED
    assert out["customer_status_label"] == "Recorded on file"
    assert "Review pending" not in out["customer_status_label"]


def test_class_a_phantom_pending_review_not_under_review():
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
        client_lifecycle_state="PENDING_REVIEW",
        queue_backed_review=False,
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.RECORDED
    assert out["customer_status_key"] != vocab.UNDER_REVIEW


def test_class_a_satisfied():
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
        satisfaction_state="SATISFIED",
        client_lifecycle_state="SATISFIED",
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.SATISFIED


def test_d1_satisfied_no_review_subline():
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
        satisfaction_state="SATISFIED",
        client_lifecycle_state="SATISFIED",
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    sub = out["customer_status_subline"].lower()
    assert "review pending" not in sub
    assert "awaiting review" not in sub


def test_class_b_uploaded_pre_queue():
    row = _base_row(
        requirement_code="gas_safety",
        governance_family=GF_PLATFORM_VER,
        evidence_authority={"state": "EA_UPLOADED_UNCONFIRMED"},
        queue_backed_review=False,
    )
    assert resolve_obligation_class(row) == "B"
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.UPLOADED
    assert out["customer_status_class"] == "B"


def test_class_b_under_review_queue_proven():
    row = _base_row(
        requirement_code="gas_safety",
        governance_family=GF_PLATFORM_VER,
        evidence_authority={"state": "EA_PENDING_ADMIN_REVIEW"},
        queue_backed_review=True,
        review_owner="platform_admin",
    )
    out = project_customer_status(
        row,
        linked_primary_document={"status": "UPLOADED"},
    )
    assert out["customer_status_key"] == vocab.UNDER_REVIEW
    assert out["customer_status_label"] == "Under review"


def test_class_b_phantom_pending_not_under_review():
    row = _base_row(
        requirement_code="gas_safety",
        governance_family=GF_PLATFORM_VER,
        evidence_authority={"state": "EA_PENDING_ADMIN_REVIEW"},
        queue_backed_review=False,
    )
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.UPLOADED


def test_escalation_supersedes_review():
    row = _base_row(
        requirement_code="gas_safety",
        governance_family=GF_PLATFORM_VER,
        evidence_authority={"state": "EA_MISMATCH_FLAGGED", "manual_review_flag": True},
        queue_backed_review=True,
        review_owner="platform_admin_escalation",
    )
    out = project_customer_status(
        row,
        linked_primary_document={"status": "UPLOADED"},
    )
    assert out["customer_status_key"] == vocab.ESCALATION_REQUIRED


def test_d4_escalation_not_review_phrase():
    row = _base_row(
        evidence_authority={"state": "EA_MISMATCH_FLAGGED"},
        manual_review_flag=True,
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.ESCALATION_REQUIRED
    assert "review" not in out["customer_status_label"].lower() or out["customer_status_label"] == "Escalation required"


def test_supporting_upload_only_action_required():
    row = _base_row(
        evidence_authority={"state": "EA_UPLOADED_UNCONFIRMED"},
        truth_presentation_stage="supporting_upload_only",
    )
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.ACTION_REQUIRED
    assert "Supporting files alone" in out["customer_status_subline"]


def test_followup_supersedes_satisfied_display():
    row = _base_row(
        requirement_code="legionella",
        governance_family="PLATFORM_OVERSIGHT_OPTIONAL",
        evidence_authority={
            "state": "EA_RECORDED_CURRENT",
            "semantic_state": "EXTERNAL_ASSESSMENT_FOLLOWUP_REQUIRED",
        },
        satisfaction_state="SATISFIED",
        client_lifecycle_state="SATISFIED",
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.FOLLOWUP_REQUIRED


def test_no_retired_phrases_in_active_output():
    fixtures = [
        _base_row(evidence_authority={"state": "EA_RECORDED_CURRENT"}, evidence_record_id="x"),
        _base_row(
            requirement_code="gas_safety",
            governance_family=GF_PLATFORM_VER,
            evidence_authority={"state": "EA_PENDING_ADMIN_REVIEW"},
            queue_backed_review=True,
            review_owner="platform_admin",
        ),
    ]
    for row in fixtures:
        if row.get("requirement_code") == "gas_safety":
            out = project_customer_status(row, linked_primary_document={"status": "UPLOADED"})
        else:
            row["evidence_record_id"] = "cer-1"
            out = project_customer_status(row)
        text = f"{out['customer_status_label']} {out['customer_status_subline']}".lower()
        for phrase in vocab.RETIRED_REVIEW_PHRASES:
            assert phrase.lower() not in text, f"retired phrase {phrase!r} in {out}"


def test_shadow_mode_adds_fields_preserves_legacy(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "shadow")
    row = _base_row(
        truth_presentation_label="Platform verification pending",
        truth_presentation_stage="platform_verification_pending",
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
    )
    row["evidence_record_id"] = "cer-1"
    apply_customer_status_projection(row)
    assert row["customer_status_key"] == vocab.RECORDED
    assert row["truth_presentation_label"] == "Platform verification pending"


def test_active_mode_mirrors_legacy_from_projector(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "active")
    row = _base_row(
        truth_presentation_label="Platform verification pending",
        truth_presentation_stage="platform_verification_pending",
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
    )
    row["evidence_record_id"] = "cer-1"
    apply_customer_status_projection(row)
    assert row["customer_status_label"] == "Recorded on file"
    assert row["truth_presentation_label"] == "Recorded on file"
    assert row["client_lifecycle_label"] == "Recorded on file"


def test_disabled_mode_no_customer_status_fields(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "disabled")
    row = _base_row()
    apply_customer_status_projection(row)
    assert "customer_status_key" not in row


def test_shadow_divergence_expected_normalization():
    legacy = {
        "truth_presentation_label": "Platform verification pending",
        "truth_presentation_subline": "",
        "truth_presentation_stage": "platform_verification_pending",
    }
    projection = {
        "customer_status_label": "Recorded on file",
        "customer_status_subline": "Self-recorded",
        "customer_status_key": vocab.RECORDED,
        "customer_status_class": "A",
    }
    cmp = compare_legacy_vs_projector({}, legacy, projection)
    assert cmp is not None
    assert cmp["divergence_type"] in ("expected_normalization", "label_mismatch", "retired_phrase_legacy")


def test_smoke_heat_additional_action():
    row = _base_row(
        requirement_code="smoke_heat_alarms",
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
        evidence_completeness={"is_complete": False, "required_missing_count": 1},
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    assert out["customer_status_key"] == vocab.ADDITIONAL_ACTION_REQUIRED


def test_legionella_family_recorded():
    row = _base_row(
        requirement_code="legionella",
        governance_family="PLATFORM_OVERSIGHT_OPTIONAL",
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
    )
    row["evidence_record_id"] = "cer-1"
    out = project_customer_status(row)
    assert out["customer_status_class"] == "A"
    assert out["customer_status_key"] in (vocab.RECORDED, vocab.SATISFIED, vocab.FOLLOWUP_REQUIRED)


def test_enrich_disabled_no_customer_status(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "disabled")
    row = _base_row()
    enriched = enrich_requirement_dict(row, "MISSING", audience="client")
    assert "customer_status_key" not in enriched


def test_enrich_shadow_adds_customer_status(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "shadow")
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
    )
    row["evidence_record_id"] = "cer-1"
    enriched = enrich_requirement_dict(row, "UPLOADED_UNVERIFIED", audience="client")
    assert enriched.get("customer_status_key") == vocab.RECORDED
    assert enriched.get("truth_presentation_label")


def test_enrich_active_authoritative(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "active")
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
    )
    row["evidence_record_id"] = "cer-1"
    enriched = enrich_requirement_dict(row, "UPLOADED_UNVERIFIED", audience="client")
    assert enriched.get("customer_status_label") == "Recorded on file"
    assert enriched.get("truth_presentation_label") == "Recorded on file"
    assert enriched.get("client_lifecycle_label") == "Recorded on file"
    ta = enriched.get("take_action") or {}
    pri = ta.get("primary") or {}
    assert pri.get("label") == "View submission"


def test_take_action_resolved_after_projector_active(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "active")
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
    )
    row["evidence_record_id"] = "cer-1"
    enriched = enrich_requirement_dict(row, "UPLOADED_UNVERIFIED", audience="client")
    assert enriched.get("customer_status_key")
    assert enriched.get("take_action")


def test_cognition_uses_customer_status_active(monkeypatch):
    monkeypatch.setenv("CUSTOMER_STATUS_PROJECTOR_V2_MODE", "active")
    row = _base_row(
        evidence_authority={"state": "EA_RECORDED_CURRENT"},
    )
    row["evidence_record_id"] = "cer-1"
    enriched = enrich_requirement_dict(row, "UPLOADED_UNVERIFIED", audience="client")
    guidance = (enriched.get("operational_cognition") or {}).get("requirement_guidance_v1") or {}
    step = guidance.get("recommended_next_step") or (enriched.get("operational_cognition") or {}).get(
        "user_safe_summary"
    )
    assert step
    assert "Awaiting review — submission not yet verified" not in step
