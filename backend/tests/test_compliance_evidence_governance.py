"""Compliance evidence records, registry policy, authority integration, and reporting helpers."""
from __future__ import annotations

import pytest

from services.compliance_evidence_record_service import (
    ALL_EVIDENCE_MODES,
    assign_confidence_for_new_record,
    checklist_schema_for_mode,
    create_compliance_evidence_record,
    effective_evidence_resolution,
    evidence_mode_allowed_for_requirement,
    non_document_record_satisfies_policy,
)
from services.compliance_registry_admin_service import validate_registry_draft
from services.compliance_status_authority import evidence_governance_summary_for_row, is_critical_safety_or_legal_obligation
from services.requirement_evidence_authority import preview_authority


def test_effective_evidence_resolution_defaults_document_only_for_unknown_type():
    req = {"requirement_type": "gas_safety", "registry_metadata": {}}
    pol = effective_evidence_resolution(req)
    assert pol["allowed_evidence_modes"] == ["DOCUMENT_UPLOAD"]


def test_effective_evidence_resolution_smoke_heat_defaults_multi_mode():
    req = {"requirement_type": "smoke_heat_alarms", "registry_metadata": {}}
    pol = effective_evidence_resolution(req)
    assert "STRUCTURED_DECLARATION" in pol["allowed_evidence_modes"]
    assert "DOCUMENT_UPLOAD" in pol["allowed_evidence_modes"]
    assert "allowed_upload_types" in pol


def test_evidence_mode_allowed_enforced():
    req_doc_only = {
        "requirement_type": "gas_safety",
        "registry_metadata": {"evidence_resolution": {"allowed_evidence_modes": ["DOCUMENT_UPLOAD"]}},
    }
    assert evidence_mode_allowed_for_requirement(req_doc_only, "DOCUMENT_UPLOAD") is True
    assert evidence_mode_allowed_for_requirement(req_doc_only, "STRUCTURED_DECLARATION") is False


def test_confidence_assignment_rules():
    assert (
        assign_confidence_for_new_record(
            evidence_mode="CONTRACTOR_CONFIRMATION",
            verification_status="VERIFIED",
            payload={},
        )
        == "HIGH"
    )
    assert (
        assign_confidence_for_new_record(
            evidence_mode="STRUCTURED_DECLARATION",
            verification_status="PENDING_REVIEW",
            payload={"declaration_statement": "x" * 25, "structured_fields": {"a": 1}},
        )
        == "MEDIUM"
    )
    low = assign_confidence_for_new_record(
        evidence_mode="STRUCTURED_DECLARATION",
        verification_status="PENDING_REVIEW",
        payload={"declaration_statement": "short", "structured_fields": {}},
    )
    assert low == "LOW"


def test_low_non_document_never_satisfies_critical_even_if_verified():
    req = {"requirement_type": "gas_safety", "registry_metadata": {}}
    assert is_critical_safety_or_legal_obligation(req) is True
    policy = {
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": True,
    }
    rec = {
        "evidence_mode": "STRUCTURED_DECLARATION",
        "verification_status": "VERIFIED",
        "evidence_confidence_level": "LOW",
    }
    assert non_document_record_satisfies_policy(
        record=rec, requirement=req, policy=policy, is_critical_obligation=True
    ) is False


def test_pending_declaration_satisfies_self_recorded_assurance():
    req = {"requirement_type": "right_to_rent", "registry_metadata": {}}
    policy = {
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    }
    rec = {
        "evidence_mode": "STRUCTURED_DECLARATION",
        "verification_status": "PENDING_REVIEW",
        "evidence_confidence_level": "MEDIUM",
    }
    assert non_document_record_satisfies_policy(
        record=rec, requirement=req, policy=policy, is_critical_obligation=False
    ) is True


def test_medium_non_document_satisfies_non_critical_without_registry_flag():
    req = {"requirement_type": "smoke_heat_alarms", "registry_metadata": {}}
    assert is_critical_safety_or_legal_obligation(req) is False
    policy = {
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
        "allow_medium_non_document_satisfaction": False,
        "allow_low_non_document_satisfaction": False,
    }
    rec = {
        "evidence_mode": "STRUCTURED_DECLARATION",
        "verification_status": "VERIFIED",
        "evidence_confidence_level": "MEDIUM",
    }
    assert non_document_record_satisfies_policy(
        record=rec, requirement=req, policy=policy, is_critical_obligation=False
    ) is True


def test_medium_non_document_blocked_for_critical_without_flag():
    req = {"requirement_type": "gas_safety", "registry_metadata": {}}
    policy = {
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
        "allow_medium_non_document_satisfaction": False,
        "allow_low_non_document_satisfaction": False,
    }
    rec = {
        "evidence_mode": "STRUCTURED_DECLARATION",
        "verification_status": "VERIFIED",
        "evidence_confidence_level": "MEDIUM",
    }
    assert non_document_record_satisfies_policy(
        record=rec, requirement=req, policy=policy, is_critical_obligation=True
    ) is False


def test_preview_authority_promotes_verified_non_document_when_no_document():
    req = {
        "requirement_id": "r1",
        "requirement_type": "smoke_heat_alarms",
        "property_id": "p1",
        "client_id": "c1",
        "applicability": "MANDATORY",
        "registry_metadata": {},
    }
    policy = effective_evidence_resolution(req)
    records = [
        {
            "evidence_record_id": "cer_x",
            "evidence_mode": "STRUCTURED_DECLARATION",
            "verification_status": "VERIFIED",
            "evidence_confidence_level": "HIGH",
            "archived": False,
            "included_in_active_compliance": True,
            "evidence_payload": {"declaration_statement": "We confirm alarms tested", "structured_fields": {"tested": True}},
        }
    ]
    out = preview_authority(req, [], property_doc={}, evidence_records=records, evidence_policy=policy)
    ea = out["evidence_authority"]
    assert ea["state"] == "VERIFIED_CURRENT"
    assert ea.get("primary_evidence_mode") == "STRUCTURED_DECLARATION"
    assert out["mirror"]["status"] == "COMPLIANT"


def test_evidence_governance_summary_projection():
    row = {
        "evidence_authority": {
            "state": "MISSING",
            "primary_evidence_mode": "CONTRACTOR_CONFIRMATION",
            "evidence_confidence_level": "MEDIUM",
            "non_document_verification_status": "PENDING_REVIEW",
        },
        "updated_at": "2026-01-01T00:00:00Z",
    }
    g = evidence_governance_summary_for_row(row)
    assert g["primary_evidence_mode"] == "CONTRACTOR_CONFIRMATION"
    assert g["unresolved_or_missing_evidence"] is True


def test_registry_draft_validates_evidence_resolution_modes():
    doc = {
        "canonical_code": "TEST",
        "scope_key": "DEFAULT",
        "identity": {"name": "Test", "category": "SAFETY"},
        "classification": {"requirement_type": "DOCUMENT"},
        "jurisdiction": {"display_jurisdictions": ["ENGLAND"]},
        "why_it_matters_short": "Because testing",
        "evidence_resolution": {"allowed_evidence_modes": ["NOT_A_REAL_MODE"], "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION"},
    }
    errs = validate_registry_draft(doc)
    assert any("evidence_resolution.allowed_evidence_modes" in e for e in errs)


@pytest.mark.asyncio
async def test_create_evidence_record_rejects_hidden_requirement():
    from unittest.mock import AsyncMock, MagicMock, patch

    req = {
        "requirement_id": "r1",
        "requirement_type": "gas_safety",
        "property_id": "p1",
        "client_id": "c1",
        "client_surface_visible": False,
    }
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value={})
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "client_id": "c1"})
    with patch(
        "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(ValueError, match="requirement_not_eligible"):
            await create_compliance_evidence_record(
                mock_db,
                requirement=req,
                evidence_mode="STRUCTURED_DECLARATION",
                created_by_user_id="u1",
                evidence_payload={"declaration_statement": "We declare x", "structured_fields": {"ok": True}},
            )


def test_all_evidence_modes_constant_contains_phase1():
    assert "INSPECTION_CHECKLIST" in ALL_EVIDENCE_MODES


def test_checklist_schema_fallback_for_mode():
    req = {"requirement_type": "smoke_heat_alarms", "registry_metadata": {}}
    schema = checklist_schema_for_mode(req, "INSPECTION_CHECKLIST")
    assert schema["fallback_used"] is True
    assert len(schema["items"]) >= 1


def test_create_evidence_record_rejects_future_contractor_completion_date():
    with pytest.raises(ValueError, match="date_cannot_be_in_future"):
        from services.compliance_evidence_record_service import _validate_payload_for_mode

        _validate_payload_for_mode(
            "CONTRACTOR_CONFIRMATION",
            {
                "contractor_name": "A",
                "completion_date": "2999-01-01",
                "work_summary": "Work summary with enough detail",
            },
        )


@pytest.mark.asyncio
async def test_upsert_document_upload_evidence_inserts_document_upload_row():
    from unittest.mock import AsyncMock, MagicMock

    from services.compliance_evidence_record_service import upsert_document_upload_evidence_for_linked_document

    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.compliance_evidence_records = coll
    mock_db.requirements = MagicMock()
    mock_db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": "r1", "client_id": "c1", "property_id": "p1"},
    )

    out = await upsert_document_upload_evidence_for_linked_document(
        mock_db,
        client_id="c1",
        property_id="p1",
        requirement_id="r1",
        document_id="d1",
        actor_user_id="u1",
        filename="cert.pdf",
    )
    assert out is not None
    assert out.get("evidence_mode") == "DOCUMENT_UPLOAD"
    assert "d1" in (out.get("linked_document_ids") or [])
    coll.insert_one.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_document_upload_evidence_idempotent_when_row_exists():
    from unittest.mock import AsyncMock, MagicMock

    from services.compliance_evidence_record_service import upsert_document_upload_evidence_for_linked_document

    existing = {"evidence_record_id": "cer_x", "evidence_mode": "DOCUMENT_UPLOAD", "linked_document_ids": ["d1"]}
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=existing)
    coll.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.compliance_evidence_records = coll
    mock_db.requirements = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=None)

    out = await upsert_document_upload_evidence_for_linked_document(
        mock_db,
        client_id="c1",
        property_id="p1",
        requirement_id="r1",
        document_id="d1",
        actor_user_id="u1",
    )
    assert out == existing
    coll.insert_one.assert_not_awaited()
