"""Unit tests for requirement evidence authority projection and scope rules."""
from datetime import datetime, timezone, timedelta

import pytest

from models import DocumentStatus, RequirementStatus
from services.requirement_evidence_authority import (
    EA_EXTRACTION_PENDING_CONFIRMATION,
    EA_MISMATCH_FLAGGED,
    EA_MISSING,
    EA_REJECTED,
    EA_UPLOADED_UNCONFIRMED,
    EA_VERIFIED_CURRENT,
    EA_VERIFIED_EXPIRED,
    SCOPE_INTAKE_STAGING,
    SCOPE_PORTFOLIO,
    SCOPE_PROPERTY,
    document_evidence_compatible_with_requirement,
    normalize_document_evidence_scope,
    preview_authority,
)
from services.semantic_state_model import (
    ASSESSMENT_FOLLOWUP_REQUIRED,
    DECLARATION_RECORDED,
    EXPIRY_REVIEW_REQUIRED,
    OPERATIONALLY_OPEN,
    PARTIALLY_COMPLETE,
    REGISTRATION_RECORDED,
    TENANT_DELIVERY_RECORDED,
    VERIFIED_CURRENT,
)


def _req(**kwargs):
    base = {
        "requirement_id": "r1",
        "client_id": "c1",
        "property_id": "p1",
        "applicability": "REQUIRED",
        "requirement_type": "GAS_SAFETY_CERT",
    }
    base.update(kwargs)
    return base


def _doc(**kwargs):
    base = {
        "document_id": "d1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": DocumentStatus.UPLOADED.value,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_scope_type": SCOPE_PROPERTY,
        "evidence_scope_id": "p1",
        "authoritative_property_id": "p1",
    }
    base.update(kwargs)
    return base


def test_normalize_property_scope():
    out = normalize_document_evidence_scope(property_id="p1", client_id="c1", evidence_scope_type="PROPERTY")
    assert out["evidence_scope_type"] == SCOPE_PROPERTY
    assert out["authoritative_property_id"] == "p1"
    assert out["property_id"] == "p1"


def test_normalize_portfolio_scope():
    out = normalize_document_evidence_scope(property_id=None, client_id="c1", evidence_scope_type="PORTFOLIO")
    assert out["evidence_scope_type"] == SCOPE_PORTFOLIO
    assert out["property_id"] is None


def test_normalize_intake_staging_requires_session():
    with pytest.raises(ValueError):
        normalize_document_evidence_scope(property_id=None, client_id="", evidence_scope_type="INTAKE_STAGING")
    out = normalize_document_evidence_scope(
        property_id=None,
        client_id="",
        evidence_scope_type="INTAKE_STAGING",
        intake_session_id="sess-1",
    )
    assert out["evidence_scope_type"] == SCOPE_INTAKE_STAGING
    assert out["evidence_scope_id"] == "sess-1"


def test_property_mismatch_not_compatible_with_requirement():
    doc = _doc(property_id="p2", authoritative_property_id="p2", evidence_scope_id="p2")
    assert document_evidence_compatible_with_requirement(doc, _req()) is False


def test_portfolio_doc_not_compatible_with_property_requirement():
    doc = _doc(
        property_id=None,
        authoritative_property_id=None,
        evidence_scope_type=SCOPE_PORTFOLIO,
        evidence_scope_id="c1",
    )
    assert document_evidence_compatible_with_requirement(doc, _req()) is False


def test_preview_missing_no_docs():
    out = preview_authority(_req(), [])
    assert out["evidence_authority"]["state"] == EA_MISSING


def test_preview_rejected_only():
    out = preview_authority(_req(), [_doc(status=DocumentStatus.REJECTED.value)])
    assert out["evidence_authority"]["state"] == EA_REJECTED


def test_preview_verified_expired():
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    out = preview_authority(
        _req(),
        [
            _doc(
                status=DocumentStatus.VERIFIED.value,
                expiry_date=past,
            )
        ],
    )
    assert out["evidence_authority"]["state"] == EA_VERIFIED_EXPIRED


def test_preview_verified_current():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    out = preview_authority(_req(), [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["evidence_authority"]["semantic_state"] == VERIFIED_CURRENT


def test_document_upload_verified_without_expiry_blocks_compliant_projection():
    req = _req(requirement_type="gas_safety", requirement_code="gas_safety")
    out = preview_authority(req, [_doc(status=DocumentStatus.VERIFIED.value)])
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
    assert out["evidence_authority"]["state"] == EA_UPLOADED_UNCONFIRMED
    assert out["evidence_authority"]["state_reason"] == "document_upload_missing_required_expiry_semantics"
    assert out["evidence_authority"]["semantic_state"] == EXPIRY_REVIEW_REQUIRED


def test_document_upload_verified_without_doc_expiry_uses_requirement_confirmed_expiry():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="gas_safety",
        requirement_code="gas_safety",
        confirmed_expiry_date=fut,
    )
    out = preview_authority(req, [_doc(status=DocumentStatus.VERIFIED.value)])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["mirror"]["status"] in (
        RequirementStatus.COMPLIANT.value,
        RequirementStatus.EXPIRING_SOON.value,
    )


def test_preview_verified_current_naive_iso_string_expiry_mirror_days_no_typeerror():
    """Naive ISO strings (no offset) must normalize to UTC before (eff_expiry - now).days."""
    fut = datetime.now(timezone.utc) + timedelta(days=200)
    naive_str = fut.strftime("%Y-%m-%dT%H:%M:%S")
    out = preview_authority(_req(), [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=naive_str)])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["mirror"]["status"] in (
        RequirementStatus.COMPLIANT.value,
        RequirementStatus.EXPIRING_SOON.value,
    )


def test_preview_verified_current_timezone_aware_datetime_expiry():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).replace(microsecond=0)
    aware = fut.astimezone(timezone.utc)
    out = preview_authority(_req(), [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=aware)])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["mirror"]["status"] in (
        RequirementStatus.COMPLIANT.value,
        RequirementStatus.EXPIRING_SOON.value,
    )


def test_preview_pending_with_extraction():
    out = preview_authority(
        _req(),
        [_doc(status=DocumentStatus.PENDING.value, extraction_status="extracted")],
    )
    assert out["evidence_authority"]["state"] == EA_EXTRACTION_PENDING_CONFIRMATION


def test_preview_scope_mismatch_flags():
    bad = _doc(
        document_id="d2",
        property_id=None,
        authoritative_property_id=None,
        evidence_scope_type=SCOPE_PORTFOLIO,
        evidence_scope_id="c1",
    )
    out = preview_authority(_req(), [bad])
    assert out["evidence_authority"]["state"] == EA_MISMATCH_FLAGGED


def test_condition_standard_verified_document_stays_pending_when_operational_followup_open():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="fitness_for_human_habitation",
        requirement_code="fitness_for_human_habitation",
        active_standard_status_summary={
            "state": "active_issues_present",
            "signal_counts": {
                "open_issues": 1,
                "open_work_orders": 1,
                "open_risk_signals": 0,
                "open_compliance_gaps": 1,
            },
            "read_only": True,
        },
    )
    out = preview_authority(
        req,
        [
            _doc(
                status=DocumentStatus.VERIFIED.value,
                expiry_date=fut,
            )
        ],
        evidence_records=[],
    )
    assert out["evidence_authority"]["effective_verified_document_id"] == "d1"
    assert out["evidence_authority"]["state"] == "UPLOADED_UNCONFIRMED"
    assert out["evidence_authority"]["state_reason"] == "operational_followup_required_condition_standard"
    assert out["evidence_authority"]["semantic_state"] == OPERATIONALLY_OPEN
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value


def test_external_assessment_verified_document_stays_pending_without_structured_assessment_record():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="legionella",
        requirement_code="legionella",
    )
    out = preview_authority(
        req,
        [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)],
        evidence_records=[],
    )
    assert out["evidence_authority"]["effective_verified_document_id"] == "d1"
    assert out["evidence_authority"]["state"] == "UPLOADED_UNCONFIRMED"
    assert out["evidence_authority"]["state_reason"] == "external_assessment_remediation_or_followup_unresolved"
    assert out["evidence_authority"]["semantic_state"] == ASSESSMENT_FOLLOWUP_REQUIRED
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value


def test_guided_declaration_structured_row_blocks_certificate_style_authority():
    req = _req(
        requirement_type="tenancy_agreement",
        requirement_code="tenancy_agreement",
        compliance_requirement_class="OBLIGATION",
        engine_informational=True,
    )
    structured = {
        "evidence_record_id": "cer-ta-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_confidence_level": "MEDIUM",
        "evidence_payload": {
            "structured_fields": {
                "agreement_exists": {"answer": True},
                "signed_by_parties": {"answer": True},
            },
        },
        "linked_document_ids": [],
    }
    out = preview_authority(req, [], evidence_records=[structured])
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
    assert out["evidence_authority"]["state"] == "UPLOADED_UNCONFIRMED"
    assert out["evidence_authority"]["state_reason"] == "guided_declaration_not_independently_verified"
    assert out["evidence_authority"]["semantic_state"] == DECLARATION_RECORDED


def test_registration_tracking_structured_row_blocks_authority_style_projection():
    req = _req(
        requirement_type="landlord_registration",
        requirement_code="landlord_registration",
    )
    structured = {
        "evidence_record_id": "cer-lr-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_confidence_level": "MEDIUM",
        "evidence_payload": {
            "structured_fields": {
                "registration_number": {"answer": "LRN-UNIT-1"},
                "issuing_authority": {"answer": "Test authority"},
                "registration_status": {"answer": "active"},
                "declaration_confirmed": {"answer": True},
            },
        },
        "linked_document_ids": [],
    }
    out = preview_authority(req, [], evidence_records=[structured])
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
    assert out["evidence_authority"]["state"] == "UPLOADED_UNCONFIRMED"
    assert out["evidence_authority"]["state_reason"] == "registration_tracking_regulator_confirmation_not_verified"
    assert out["evidence_authority"]["semantic_state"] == REGISTRATION_RECORDED


def test_tenant_delivery_structured_row_blocks_confirmation_style_authority():
    req = _req(
        requirement_type="how_to_rent",
        requirement_code="how_to_rent",
        compliance_requirement_class="OBLIGATION",
        engine_informational=True,
    )
    structured = {
        "evidence_record_id": "cer-h2r-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_confidence_level": "MEDIUM",
        "evidence_payload": {
            "structured_fields": {
                "tenancy_start_date": {"answer": "2026-01-01"},
                "guide_version_or_publication_date": {"answer": "2025 edition"},
                "delivery_date": {"answer": "2026-01-02"},
                "delivery_method": {"answer": "email"},
                "tenant_recipient": {"answer": "Unit tenant"},
                "declaration_confirmed": {"answer": True},
            },
        },
        "linked_document_ids": [],
    }
    out = preview_authority(req, [], evidence_records=[structured])
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
    assert out["evidence_authority"]["state"] == "UPLOADED_UNCONFIRMED"
    assert out["evidence_authority"]["state_reason"] == "tenant_delivery_tenant_confirmation_not_verified"
    assert out["evidence_authority"]["semantic_state"] == TENANT_DELIVERY_RECORDED


def test_tenant_delivery_verified_supporting_document_stays_pending():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="how_to_rent",
        requirement_code="how_to_rent",
        compliance_requirement_class="OBLIGATION",
        engine_informational=True,
    )
    out = preview_authority(
        req,
        [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)],
        evidence_records=[],
    )
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
    assert out["evidence_authority"]["state_reason"] == "tenant_delivery_tenant_confirmation_not_verified"


def test_registration_tracking_verified_supporting_document_stays_pending():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="landlord_registration",
        requirement_code="landlord_registration",
    )
    out = preview_authority(
        req,
        [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)],
        evidence_records=[],
    )
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
    assert out["evidence_authority"]["state_reason"] == "registration_tracking_regulator_confirmation_not_verified"


def test_guided_declaration_verified_supporting_document_stays_pending():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="tenancy_agreement",
        requirement_code="tenancy_agreement",
        compliance_requirement_class="OBLIGATION",
        engine_informational=True,
    )
    out = preview_authority(
        req,
        [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)],
        evidence_records=[],
    )
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
    assert out["evidence_authority"]["state_reason"] == "guided_declaration_not_independently_verified"


def test_external_assessment_allows_compliant_mirror_when_structured_record_declares_no_actions():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="legionella",
        requirement_code="legionella",
    )
    structured = {
        "evidence_record_id": "cer-leg-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_confidence_level": "HIGH",
        "evidence_payload": {
            "structured_fields": {
                "actions_required": {"answer": False},
                "assessment_completed": {"answer": True},
            }
        },
    }
    out = preview_authority(
        req,
        [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)],
        evidence_records=[structured],
    )
    assert out["mirror"]["status"] == RequirementStatus.COMPLIANT.value
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT


def test_multi_evidence_partial_components_stay_pending_when_co_component_missing():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="smoke_heat_alarms",
        requirement_code="smoke_heat_alarms",
        registry_metadata={"evidence_resolution": {"co_alarm_required": True}},
    )
    partial_smoke_only = {
        "evidence_record_id": "cer-smoke-only",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": "CONTRACTOR_CONFIRMATION",
        "evidence_confidence_level": "MEDIUM",
        "evidence_payload": {"component": "smoke_alarm", "notes": "smoke alarm tested and recorded"},
    }
    out = preview_authority(
        req,
        [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)],
        property_doc={"has_fuel_burning_appliance": True},
        evidence_records=[partial_smoke_only],
    )
    assert out["evidence_authority"]["effective_verified_document_id"] == "d1"
    assert out["evidence_authority"]["state"] == "UPLOADED_UNCONFIRMED"
    assert out["evidence_authority"]["state_reason"] == "multi_evidence_components_incomplete"
    assert out["evidence_authority"]["semantic_state"] == PARTIALLY_COMPLETE
    comp = out["evidence_authority"].get("evidence_completeness") or {}
    assert comp.get("evaluated") is True
    assert comp.get("is_complete") is False
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
