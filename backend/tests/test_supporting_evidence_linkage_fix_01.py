"""SUPPORTING-DOCUMENT-LINKAGE-ESCALATION-FIX-01 regression tests."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import DocumentStatus, RequirementStatus
from services.cer_governance_presentation import attach_cer_governance_presentation, derive_truth_presentation, resolve_governance_meta
from services.client_requirement_lifecycle import derive_client_lifecycle_fields, PENDING_REVIEW, SATISFIED_UNVERIFIED
from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
    EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
)
from services.evidence_document_match_engine import MATCH_OUTCOME_NEEDS_ADMIN_REVIEW
from services.requirement_attention_eligibility_service import derive_attention_reason, is_requirement_attention_eligible
from services.requirement_evidence_authority import EA_MISMATCH_FLAGGED, EA_VERIFIED_CURRENT, preview_authority
from services.requirement_truth import enrich_requirement_dict
from services.supporting_evidence_linkage import (
    SUPPORTING_EVIDENCE_ATTACHMENT_SOURCE,
    document_excluded_from_admin_verification_pending,
    is_certificate_primary_requirement,
    should_skip_primary_document_pipeline_on_link,
    should_treat_linked_document_as_supporting_only,
)


def _req(**kwargs):
    base = {
        "requirement_id": "r1",
        "client_id": "c1",
        "property_id": "p1",
        "applicability": "REQUIRED",
        "status": "COMPLIANT",
    }
    base.update(kwargs)
    return base


def _doc(**kwargs):
    base = {
        "document_id": "d-support",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": DocumentStatus.UPLOADED.value,
        "source": SUPPORTING_EVIDENCE_ATTACHMENT_SOURCE,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "match_outcome": MATCH_OUTCOME_NEEDS_ADMIN_REVIEW,
        "requirement_evidence_mismatch": True,
    }
    base.update(kwargs)
    return base


def _legionella_structured_cer(**payload_overrides):
    payload = {
        "structured_fields": {
            "actions_required": {"answer": False},
            "assessment_completed": {"answer": True},
        }
    }
    payload.update(payload_overrides)
    return {
        "evidence_record_id": "cer-leg-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "evidence_confidence_level": "HIGH",
        "evidence_payload": payload,
    }


def test_certificate_primary_gas_is_not_supporting_only():
    req = _req(requirement_type="GAS_SAFETY_CERT", requirement_code="gas_safety_cert")
    assert is_certificate_primary_requirement(req) is True


def test_legionella_structured_satisfied_supporting_doc_does_not_mismatch_requirement():
    req = _req(requirement_type="legionella", requirement_code="legionella")
    structured = _legionella_structured_cer()
    supporting = _doc()
    out = preview_authority(req, [supporting], evidence_records=[structured])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["evidence_authority"]["state_reason"] == "verified_non_document_evidence"
    assert out["mirror"]["status"] == RequirementStatus.COMPLIANT.value
    assert out["evidence_authority"]["state"] != EA_MISMATCH_FLAGGED


def test_legionella_supporting_doc_does_not_trigger_escalation_presentation():
    req = _req(
        requirement_type="legionella",
        requirement_code="legionella",
        evidence_authority={
            "state": EA_VERIFIED_CURRENT,
            "state_reason": "verified_non_document_evidence",
            "primary_evidence_record_id": "cer-leg-1",
            "primary_evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        },
        client_lifecycle_state="SATISFIED_UNVERIFIED",
    )
    meta = resolve_governance_meta(req)
    truth = derive_truth_presentation(req, meta)
    assert truth.get("truth_presentation_stage") != "escalation_review"
    assert truth.get("truth_presentation_label") != "Escalated for platform review"


def test_legionella_linked_supporting_doc_lifecycle_not_pending_review():
    req = _req(
        requirement_type="legionella",
        requirement_code="legionella",
        status="COMPLIANT",
        evidence_authority={
            "state": EA_VERIFIED_CURRENT,
            "state_reason": "verified_non_document_evidence",
            "primary_evidence_record_id": "cer-leg-1",
            "primary_evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        },
    )
    supporting = _doc()
    out = derive_client_lifecycle_fields(req, linked_primary_document=supporting)
    assert out.get("client_lifecycle_state") != PENDING_REVIEW


def test_tenancy_declaration_supporting_link_stays_satisfied():
    req = _req(
        requirement_type="tenancy_agreement",
        requirement_code="tenancy_agreement",
        evidence_authority={
            "state": EA_VERIFIED_CURRENT,
            "state_reason": "verified_non_document_evidence",
            "primary_evidence_record_id": "cer-ta-1",
            "primary_evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        },
        semantic_state="DECLARATION_RECORDED",
    )
    out = derive_client_lifecycle_fields(req, linked_primary_document=_doc())
    assert out.get("client_lifecycle_state") in (None, SATISFIED_UNVERIFIED, "VERIFIED")


def test_smoke_multi_evidence_supporting_link_no_mismatch():
    req = _req(
        requirement_type="smoke_heat_alarms",
        requirement_code="smoke_heat_alarms",
        registry_metadata={"evidence_resolution": {"co_alarm_required": True}},
    )
    smoke_cer = {
        "evidence_record_id": "cer-smoke",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
        "evidence_confidence_level": "MEDIUM",
        "evidence_payload": {"component": "smoke_alarm", "notes": "tested"},
    }
    co_cer = {
        "evidence_record_id": "cer-co",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
        "evidence_confidence_level": "MEDIUM",
        "evidence_payload": {"component": "co_alarm", "notes": "tested"},
    }
    out = preview_authority(
        req,
        [_doc()],
        property_doc={"has_fuel_burning_appliance": True},
        evidence_records=[smoke_cer, co_cer],
    )
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["mirror"]["status"] == RequirementStatus.COMPLIANT.value


def test_gas_safety_certificate_primary_still_uses_document():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(requirement_type="GAS_SAFETY_CERT", requirement_code="gas_safety_cert")
    cert = _doc(
        source="portal",
        status=DocumentStatus.UPLOADED.value,
        match_outcome=None,
        requirement_evidence_mismatch=False,
        expiry_date=fut,
    )
    out = preview_authority(req, [cert], evidence_records=[])
    assert should_treat_linked_document_as_supporting_only(cert, req, []) is False
    assert out["evidence_authority"]["state"] != EA_VERIFIED_CURRENT or out["mirror"]["status"] == RequirementStatus.PENDING.value


@pytest.mark.asyncio
async def test_should_skip_primary_pipeline_on_supporting_attachment():
    db = MagicMock()
    doc = _doc()
    req = _req(requirement_type="legionella", requirement_code="legionella")
    assert await should_skip_primary_document_pipeline_on_link(
        db, doc=doc, requirement=req, client_id="c1"
    )


@pytest.mark.asyncio
async def test_should_not_skip_primary_pipeline_for_gas():
    db = MagicMock()
    doc = _doc(source="portal")
    req = _req(requirement_type="GAS_SAFETY_CERT", requirement_code="gas_safety_cert")
    assert not await should_skip_primary_document_pipeline_on_link(
        db, doc=doc, requirement=req, client_id="c1"
    )


@pytest.mark.asyncio
async def test_admin_verification_excludes_supporting_on_satisfied_structured():
    db = MagicMock()
    doc = _doc(requirement_id="r1", admin_verification_pending_suppressed=True)
    excluded = await document_excluded_from_admin_verification_pending(db, doc)
    assert excluded is True


@pytest.mark.asyncio
async def test_admin_verification_legacy_supporting_linked_to_satisfied_requirement():
    db = MagicMock()
    doc = _doc(requirement_id="r1")
    req = _req(
        requirement_type="legionella",
        requirement_code="legionella",
        evidence_authority={"state": EA_VERIFIED_CURRENT, "state_reason": "verified_non_document_evidence"},
    )
    db.requirements.find_one = AsyncMock(return_value=req)

    async def _load_records(db, rid, cid):
        return [_legionella_structured_cer()]

    with patch(
        "services.compliance_evidence_record_service.load_records_for_requirement_sync",
        side_effect=_load_records,
    ):
        excluded = await document_excluded_from_admin_verification_pending(db, doc)
    assert excluded is True


def test_attention_not_escalation_when_structured_satisfied():
    req = _req(
        requirement_type="legionella",
        requirement_code="legionella",
        truth_presentation_stage="assessment_recorded",
        evidence_authority={
            "state": EA_VERIFIED_CURRENT,
            "state_reason": "verified_non_document_evidence",
            "primary_evidence_record_id": "cer-leg-1",
        },
        client_lifecycle_state="SATISFIED_UNVERIFIED",
    )
    reason = derive_attention_reason(req)
    assert reason != "escalation_review"
    eligible, attention_reason, _ = is_requirement_attention_eligible(req)
    assert attention_reason != "escalation_review"


def test_enriched_legionella_with_supporting_doc_no_escalation_labels():
    req = _req(
        requirement_type="legionella",
        requirement_code="legionella",
        status="COMPLIANT",
    )
    structured = _legionella_structured_cer()
    preview = preview_authority(req, [_doc()], evidence_records=[structured])
    row = {**req, **preview["mirror"], "evidence_authority": preview["evidence_authority"]}
    enriched = enrich_requirement_dict(
        row,
        live_evidence_state=preview["mirror"]["evidence_state"],
        audience="client",
        compliance_evidence_records=[structured],
        linked_primary_document=_doc(),
    )
    assert enriched.get("truth_presentation_stage") != "escalation_review"
    assert "Escalated for platform review" not in str(enriched.get("truth_presentation_label") or "")
