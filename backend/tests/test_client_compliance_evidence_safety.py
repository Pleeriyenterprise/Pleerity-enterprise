from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routes import client_compliance_evidence as route


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _limit):
        return list(self._rows)


def _req():
    return SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))


@pytest.mark.asyncio
async def test_supporting_attachment_cannot_satisfy_document_only_requirement():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "gas_safety",
            "registry_metadata": {"evidence_resolution": {"allowed_evidence_modes": ["DOCUMENT_UPLOAD"]}},
        }
    )
    db.documents.find = MagicMock(return_value=_Cursor([{"document_id": "doc_1", "content_type": "application/pdf"}]))
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Declaration text",
            structured_fields={"k": {"answer": True}},
        ),
        supporting_attachment_document_ids=["doc_1"],
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(
            route,
            "create_compliance_evidence_record",
            AsyncMock(side_effect=ValueError("evidence_mode_not_allowed_for_requirement")),
        ):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert "evidence_mode_not_allowed_for_requirement" in str(ei.value.detail)


@pytest.mark.asyncio
async def test_supporting_attachments_must_belong_to_same_client():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "smoke_heat_alarms",
            "registry_metadata": {"evidence_resolution": {"allowed_evidence_modes": ["STRUCTURED_DECLARATION"]}},
        }
    )
    db.documents.find = MagicMock(return_value=_Cursor([]))
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Declaration text",
            structured_fields={"k": {"answer": True}},
        ),
        supporting_attachment_document_ids=["doc_other_client"],
    )
    audit_mock = AsyncMock()
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_audit_log", audit_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "SUPPORTING_ATTACHMENT_INVALID"
    assert "invalid" in ei.value.detail["message"].lower()
    audit_mock.assert_awaited()
    md = audit_mock.await_args.kwargs["metadata"]
    assert md["reason_code"] == "supporting_attachment_not_found"
    assert md["attachment_id"] == "doc_other_client"


@pytest.mark.asyncio
async def test_unsupported_supporting_upload_type_is_rejected():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "smoke_heat_alarms",
            "registry_metadata": {
                "evidence_resolution": {
                    "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
                    "allowed_upload_types": ["application/pdf"],
                }
            },
        }
    )
    db.documents.find = MagicMock(
        return_value=_Cursor([{"document_id": "doc_1", "content_type": "image/png"}])
    )
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Declaration text",
            structured_fields={"k": {"answer": True}},
        ),
        supporting_attachment_document_ids=["doc_1"],
    )
    audit_mock = AsyncMock()
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_audit_log", audit_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "SUPPORTING_ATTACHMENT_INVALID"
    md = audit_mock.await_args.kwargs["metadata"]
    assert md["reason_code"] == "unsupported_supporting_upload_type"
    assert md["attachment_id"] == "doc_1"


@pytest.mark.asyncio
async def test_supporting_upload_required_enforced_server_side():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "smoke_heat_alarms",
            "registry_metadata": {
                "evidence_resolution": {
                    "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
                    "supporting_upload_required": True,
                }
            },
        }
    )
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Declaration text",
            structured_fields={"k": {"answer": True}},
        ),
    )
    audit_mock = AsyncMock()
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_audit_log", audit_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "SUPPORTING_ATTACHMENT_INVALID"
    md = audit_mock.await_args.kwargs["metadata"]
    assert md["reason_code"] == "supporting_upload_required"
    assert md["attachment_id"] is None


@pytest.mark.asyncio
async def test_fallback_checklist_schema_is_flagged():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "smoke_heat_alarms",
            "registry_metadata": {"evidence_resolution": {"allowed_evidence_modes": ["INSPECTION_CHECKLIST"]}},
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="r1",
            request=_req(),
            user={"client_id": "c1"},
        )
    rows = out.get("guided_methods") or []
    assert rows
    assert rows[0].get("checklist_schema_fallback_used") is True
    assert isinstance(rows[0].get("checklist_schema"), list)
    assert len(rows[0].get("checklist_schema")) >= 1


@pytest.mark.asyncio
async def test_how_to_rent_evidence_resolution_tenant_delivery_modal_and_schema():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "how_to_rent",
            "requirement_code": "how_to_rent",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="r1",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("modal_title") == "Record How to Rent delivery"
    assert out.get("primary_client_cta") == "Record How to Rent delivery"
    assert out.get("primary_resolution_workflow") == "TENANT_DELIVERY"
    assert out.get("client_evidence_disclosure")
    disc = str(out.get("client_evidence_disclosure") or "")
    assert "review" in disc.lower()
    assert "legal advice" in disc.lower()
    methods = {m.get("evidence_mode"): m for m in (out.get("guided_methods") or [])}
    sd = methods.get("STRUCTURED_DECLARATION")
    assert sd
    ids = [r.get("id") for r in (sd.get("checklist_schema") or [])]
    for key in (
        "tenancy_start_date",
        "guide_version_or_publication_date",
        "delivery_date",
        "delivery_method",
        "tenant_recipient",
        "proof_of_delivery",
        "declaration_confirmed",
    ):
        assert key in ids
    dm = next((r for r in (sd.get("checklist_schema") or []) if r.get("id") == "delivery_method"), None)
    assert dm and dm.get("answer_type") == "SELECT"
    assert isinstance(dm.get("choices"), list) and len(dm.get("choices")) >= 2


@pytest.mark.asyncio
async def test_right_to_rent_evidence_resolution_guided_declaration_schema():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW

    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "right_to_rent",
            "requirement_code": "right_to_rent",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="r1",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("modal_title") == "Record Right to Rent check"
    assert out.get("primary_client_cta") == "Record Right to Rent check"
    assert out.get("primary_resolution_workflow") == GUIDED_DECLARATION_WORKFLOW
    assert out.get("client_evidence_disclosure")
    assert "home office" in str(out.get("client_evidence_disclosure") or "").lower()
    methods = {m.get("evidence_mode"): m for m in (out.get("guided_methods") or [])}
    sd = methods.get("STRUCTURED_DECLARATION")
    assert sd
    assert sd.get("checklist_schema_fallback_used") is False
    ids = [r.get("id") for r in (sd.get("checklist_schema") or [])]
    for key in (
        "tenant_name",
        "check_date",
        "document_type",
        "document_reference",
        "right_to_rent_status",
        "follow_up_required",
        "follow_up_date",
        "declaration_confirmed",
    ):
        assert key in ids
    st = next((r for r in (sd.get("checklist_schema") or []) if r.get("id") == "right_to_rent_status"), None)
    assert st and st.get("answer_type") == "SELECT"
    assert isinstance(st.get("choices"), list) and len(st.get("choices")) == 3
    pol = out.get("policy") or {}
    assert isinstance(pol.get("structured_declaration_conditional_rules"), list)
    assert len(pol["structured_declaration_conditional_rules"]) >= 1


@pytest.mark.asyncio
async def test_deposit_pi_evidence_resolution_guided_declaration_schema():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW

    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "rdep",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "deposit_pi",
            "requirement_code": "deposit_pi",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="rdep",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("modal_title") == "Record deposit compliance"
    assert out.get("primary_client_cta") == "Record deposit compliance"
    assert out.get("primary_resolution_workflow") == GUIDED_DECLARATION_WORKFLOW
    disc = str(out.get("client_evidence_disclosure") or "")
    assert "prescribed information" in disc.lower()
    assert "legal verification" in disc.lower() or "not legal" in disc.lower()
    modes = [m.get("evidence_mode") for m in (out.get("guided_methods") or [])]
    assert modes[0] == "STRUCTURED_DECLARATION"
    assert "DOCUMENT_UPLOAD" in modes
    methods = {m.get("evidence_mode"): m for m in (out.get("guided_methods") or [])}
    sd = methods.get("STRUCTURED_DECLARATION")
    assert sd and sd.get("checklist_schema_fallback_used") is False
    ids = [r.get("id") for r in (sd.get("checklist_schema") or [])]
    for key in (
        "deposit_taken",
        "deposit_amount",
        "deposit_received_date",
        "scheme_name",
        "scheme_reference",
        "protection_date",
        "protection_confirmed",
        "prescribed_information_served",
        "prescribed_information_served_date",
        "served_to",
        "service_method",
        "proof_of_service",
        "declaration_confirmed",
    ):
        assert key in ids


@pytest.mark.asyncio
async def test_deposit_alias_evidence_resolution_matches_canonical():
    from services.compliance_evidence_record_service import effective_evidence_resolution

    canon = effective_evidence_resolution(
        {"requirement_type": "deposit_pi", "requirement_code": "deposit_pi", "registry_metadata": {}}
    )
    for slug in ("deposit_prescribed_info", "tenancy_deposit_protection"):
        alias_pol = effective_evidence_resolution(
            {"requirement_type": slug, "requirement_code": slug, "registry_metadata": {}}
        )
        assert alias_pol == canon

    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r2",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "deposit_prescribed_info",
            "requirement_code": "deposit_prescribed_info",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="r2",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("primary_client_cta") == canon.get("guided_primary_cta_label")
    sd = next(m for m in (out.get("guided_methods") or []) if m.get("evidence_mode") == "STRUCTURED_DECLARATION")
    sd_canon = canon.get("checklist_schema_by_mode", {}).get("STRUCTURED_DECLARATION") or []
    assert [r.get("id") for r in (sd.get("checklist_schema") or [])] == [r.get("id") for r in sd_canon]


@pytest.mark.asyncio
async def test_wales_occupation_contract_evidence_resolution_guided_declaration_schema():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW

    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "rwal",
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "Wales",
            "requirement_type": "wales_occupation_contract",
            "requirement_code": "wales_occupation_contract",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="rwal",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("modal_title") == "Record Wales occupation contract"
    assert out.get("primary_client_cta") == "Record Wales occupation contract"
    assert out.get("primary_resolution_workflow") == GUIDED_DECLARATION_WORKFLOW
    disc = str(out.get("client_evidence_disclosure") or "")
    assert "legal verification" in disc.lower()
    methods = {m.get("evidence_mode"): m for m in (out.get("guided_methods") or [])}
    sd = methods.get("STRUCTURED_DECLARATION")
    assert sd and sd.get("checklist_schema_fallback_used") is False
    ids = [r.get("id") for r in (sd.get("checklist_schema") or [])]
    for key in (
        "contract_type",
        "occupation_contract_issued",
        "issue_date",
        "contract_holder_name",
        "service_method",
        "proof_reference",
        "declaration_confirmed",
    ):
        assert key in ids


@pytest.mark.asyncio
async def test_occupation_contract_wales_context_uses_same_wales_schema():
    from services.compliance_evidence_record_service import effective_evidence_resolution

    canon = effective_evidence_resolution(
        {
            "requirement_type": "wales_occupation_contract",
            "requirement_code": "wales_occupation_contract",
            "jurisdiction": "Wales",
            "registry_metadata": {},
        }
    )
    alias_pol = effective_evidence_resolution(
        {
            "requirement_type": "occupation_contract",
            "requirement_code": "occupation_contract",
            "jurisdiction": "Wales",
            "registry_metadata": {},
        }
    )
    assert alias_pol == canon

    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "rwal2",
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "Wales",
            "requirement_type": "occupation_contract",
            "requirement_code": "occupation_contract",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="rwal2",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("primary_client_cta") == "Record Wales occupation contract"


@pytest.mark.asyncio
async def test_legionella_evidence_resolution_external_assessment_schema():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "rleg",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "legionella",
            "requirement_code": "legionella",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="rleg",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("modal_title") == "Record Legionella risk assessment"
    assert out.get("primary_client_cta") == "Record Legionella risk assessment"
    assert out.get("primary_resolution_workflow") == "EXTERNAL_ASSESSMENT_EVIDENCE"
    disc = str(out.get("client_evidence_disclosure") or "")
    assert "professional or legal verification" in disc.lower()
    modes = [m.get("evidence_mode") for m in (out.get("guided_methods") or [])]
    assert modes[0] == "STRUCTURED_DECLARATION"
    assert "DOCUMENT_UPLOAD" in modes
    methods = {m.get("evidence_mode"): m for m in (out.get("guided_methods") or [])}
    sd = methods.get("STRUCTURED_DECLARATION")
    assert sd and sd.get("checklist_schema_fallback_used") is False
    ids = [r.get("id") for r in (sd.get("checklist_schema") or [])]
    for key in (
        "assessment_completed",
        "assessment_date",
        "assessor_type",
        "assessor_name",
        "risk_level",
        "control_measures_in_place",
        "actions_required",
        "next_review_date",
        "declaration_confirmed",
    ):
        assert key in ids


@pytest.mark.asyncio
async def test_lead_testing_evidence_resolution_external_assessment_schema():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "rlead",
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "Scotland",
            "requirement_type": "lead_testing",
            "requirement_code": "lead_testing",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="rlead",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("modal_title") == "Record lead risk assessment"
    assert out.get("primary_client_cta") == "Record lead risk assessment"
    assert out.get("primary_resolution_workflow") == "EXTERNAL_ASSESSMENT_EVIDENCE"
    modes = [m.get("evidence_mode") for m in (out.get("guided_methods") or [])]
    assert modes[0] == "STRUCTURED_DECLARATION"
    assert "DOCUMENT_UPLOAD" in modes
    methods = {m.get("evidence_mode"): m for m in (out.get("guided_methods") or [])}
    sd = methods.get("STRUCTURED_DECLARATION")
    assert sd and sd.get("checklist_schema_fallback_used") is False
    ids = [r.get("id") for r in (sd.get("checklist_schema") or [])]
    for key in (
        "assessment_completed",
        "assessment_date",
        "assessment_type",
        "risk_level",
        "lead_present",
        "actions_required",
        "actions_taken",
        "next_review_date",
        "declaration_confirmed",
    ):
        assert key in ids


@pytest.mark.asyncio
async def test_right_to_rent_checks_alias_evidence_resolution_route_matches_canonical():
    from services.compliance_evidence_record_service import effective_evidence_resolution

    canon = effective_evidence_resolution(
        {"requirement_type": "right_to_rent", "requirement_code": "right_to_rent", "registry_metadata": {}}
    )
    alias_pol = effective_evidence_resolution(
        {"requirement_type": "right_to_rent_checks", "requirement_code": "right_to_rent_checks", "registry_metadata": {}}
    )
    assert canon == alias_pol

    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r2",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "right_to_rent_checks",
            "requirement_code": "right_to_rent_checks",
        }
    )
    with patch.object(route.database, "get_db", return_value=db):
        out = await route.get_evidence_resolution(
            property_id="p1",
            requirement_id="r2",
            request=_req(),
            user={"client_id": "c1"},
        )
    assert out.get("primary_client_cta") == canon.get("guided_primary_cta_label")
    sd = next(m for m in (out.get("guided_methods") or []) if m.get("evidence_mode") == "STRUCTURED_DECLARATION")
    sd_canon = canon.get("checklist_schema_by_mode", {}).get("STRUCTURED_DECLARATION") or []
    assert [r.get("id") for r in (sd.get("checklist_schema") or [])] == [r.get("id") for r in sd_canon]


def _right_to_rent_requirement_row():
    return {
        "requirement_id": "r1",
        "property_id": "p1",
        "client_id": "c1",
        "requirement_type": "right_to_rent",
        "requirement_code": "right_to_rent",
    }


@pytest.mark.asyncio
async def test_post_right_to_rent_rejects_time_limited_without_follow_up_date():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_right_to_rent_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Check recorded",
            structured_fields={
                "tenant_name": {"answer": "Tenant A"},
                "check_date": {"answer": "2026-01-01"},
                "document_type": {"answer": "passport"},
                "right_to_rent_status": {"answer": "time_limited"},
                "follow_up_required": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED"
    assert "follow-up" in str(ei.value.detail.get("message") or "").lower()
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_right_to_rent_rejects_follow_up_required_yes_without_follow_up_date():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_right_to_rent_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Check recorded",
            structured_fields={
                "tenant_name": {"answer": "Tenant A"},
                "check_date": {"answer": "2026-01-01"},
                "document_type": {"answer": "passport"},
                "right_to_rent_status": {"answer": "unlimited"},
                "follow_up_required": {"answer": "YES"},
                "follow_up_date": {"answer": ""},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_right_to_rent_accepts_unlimited_follow_up_no_without_follow_up_date():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_right_to_rent_requirement_row())
    create_mock = AsyncMock(return_value={"evidence_record_id": "cer_ok"})
    sync_mock = AsyncMock()
    enqueue_mock = AsyncMock(return_value=True)
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Check recorded",
            structured_fields={
                "tenant_name": {"answer": "Tenant A"},
                "check_date": {"answer": "2026-01-01"},
                "document_type": {"answer": "passport"},
                "right_to_rent_status": {"answer": "unlimited"},
                "follow_up_required": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    out = await route.post_compliance_evidence(
                        property_id="p1",
                        requirement_id="r1",
                        body=body,
                        request=_req(),
                        user={"client_id": "c1", "portal_user_id": "u1"},
                    )
    assert out["ok"] is True
    create_mock.assert_awaited()


@pytest.mark.asyncio
async def test_post_right_to_rent_checks_alias_same_follow_up_validation():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r2",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "right_to_rent_checks",
            "requirement_code": "right_to_rent_checks",
        }
    )
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Check recorded",
            structured_fields={
                "tenant_name": {"answer": "Tenant A"},
                "check_date": {"answer": "2026-01-01"},
                "document_type": {"answer": "passport"},
                "right_to_rent_status": {"answer": "time_limited"},
                "follow_up_required": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r2",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    create_mock.assert_not_called()


def _deposit_requirement_row(slug="deposit_pi"):
    return {
        "requirement_id": "r1",
        "property_id": "p1",
        "client_id": "c1",
        "requirement_type": slug,
        "requirement_code": slug,
    }


@pytest.mark.asyncio
async def test_post_deposit_rejects_deposit_taken_without_protection_fields():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_deposit_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Deposit record",
            structured_fields={
                "deposit_taken": {"answer": True},
                "deposit_amount": {"answer": ""},
                "deposit_received_date": {"answer": "2026-01-01"},
                "scheme_name": {"answer": "S"},
                "scheme_reference": {"answer": "R"},
                "protection_date": {"answer": "2026-01-02"},
                "protection_confirmed": {"answer": True},
                "prescribed_information_served": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "DEPOSIT_STRUCTURED_DECLARATION_INVALID"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_deposit_rejects_prescribed_served_without_pi_fields():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_deposit_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Deposit record",
            structured_fields={
                "deposit_taken": {"answer": False},
                "prescribed_information_served": {"answer": True},
                "prescribed_information_served_date": {"answer": ""},
                "served_to": {"answer": "T"},
                "service_method": {"answer": "email"},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "DEPOSIT_STRUCTURED_DECLARATION_INVALID"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_deposit_alias_validates_like_canonical():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_deposit_requirement_row("tenancy_deposit_protection"))
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Deposit record",
            structured_fields={
                "deposit_taken": {"answer": True},
                "deposit_amount": {"answer": "100"},
                "deposit_received_date": {"answer": "2026-01-01"},
                "scheme_name": {"answer": "S"},
                "scheme_reference": {"answer": "R"},
                "protection_date": {"answer": "2026-01-02"},
                "protection_confirmed": {"answer": False},
                "prescribed_information_served": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="r1",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "DEPOSIT_STRUCTURED_DECLARATION_INVALID"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_deposit_accepts_no_deposit_and_not_served():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_deposit_requirement_row())
    create_mock = AsyncMock(return_value={"evidence_record_id": "cer_d"})
    sync_mock = AsyncMock()
    enqueue_mock = AsyncMock(return_value=True)
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="No deposit / not served",
            structured_fields={
                "deposit_taken": {"answer": False},
                "prescribed_information_served": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    out = await route.post_compliance_evidence(
                        property_id="p1",
                        requirement_id="r1",
                        body=body,
                        request=_req(),
                        user={"client_id": "c1", "portal_user_id": "u1"},
                    )
    assert out["ok"] is True
    create_mock.assert_awaited()


def _wales_occupation_requirement_row(slug="wales_occupation_contract", jurisdiction="Wales"):
    return {
        "requirement_id": "rwoc",
        "property_id": "p1",
        "client_id": "c1",
        "jurisdiction": jurisdiction,
        "requirement_type": slug,
        "requirement_code": slug,
    }


@pytest.mark.asyncio
async def test_post_wales_occupation_contract_rejects_missing_declaration_confirmation():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_wales_occupation_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Wales contract record",
            structured_fields={
                "occupation_contract_issued": {"answer": False},
                "declaration_confirmed": {"answer": False},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="rwoc",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "WALES_OCCUPATION_CONTRACT_STRUCTURED_DECLARATION_INVALID"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_wales_occupation_contract_requires_fields_when_issued_yes():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_wales_occupation_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Wales contract record",
            structured_fields={
                "occupation_contract_issued": {"answer": True},
                "issue_date": {"answer": ""},
                "contract_holder_name": {"answer": "A"},
                "service_method": {"answer": "email"},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="rwoc",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "WALES_OCCUPATION_CONTRACT_STRUCTURED_DECLARATION_INVALID"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_occupation_contract_alias_validates_in_wales_context_only():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_wales_occupation_requirement_row("occupation_contract", "Wales"))
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Alias Wales contract record",
            structured_fields={
                "occupation_contract_issued": {"answer": True},
                "issue_date": {"answer": ""},
                "contract_holder_name": {"answer": "A"},
                "service_method": {"answer": "email"},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="rwoc",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "WALES_OCCUPATION_CONTRACT_STRUCTURED_DECLARATION_INVALID"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_occupation_contract_non_wales_context_unaffected():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_wales_occupation_requirement_row("occupation_contract", "England"))
    create_mock = AsyncMock(return_value={"evidence_record_id": "cer_occ"})
    sync_mock = AsyncMock()
    enqueue_mock = AsyncMock(return_value=True)
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Non-Wales legacy row",
            structured_fields={
                "occupation_contract_issued": {"answer": True},
                "issue_date": {"answer": ""},
                "contract_holder_name": {"answer": ""},
                "service_method": {"answer": ""},
                "declaration_confirmed": {"answer": False},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    out = await route.post_compliance_evidence(
                        property_id="p1",
                        requirement_id="rwoc",
                        body=body,
                        request=_req(),
                        user={"client_id": "c1", "portal_user_id": "u1"},
                    )
    assert out["ok"] is True
    create_mock.assert_awaited()


def _legionella_requirement_row():
    return {
        "requirement_id": "rleg",
        "property_id": "p1",
        "client_id": "c1",
        "requirement_type": "legionella",
        "requirement_code": "legionella",
    }


def _lead_testing_requirement_row():
    return {
        "requirement_id": "rlead",
        "property_id": "p1",
        "client_id": "c1",
        "jurisdiction": "Scotland",
        "requirement_type": "lead_testing",
        "requirement_code": "lead_testing",
    }


@pytest.mark.asyncio
async def test_post_legionella_rejects_missing_assessment_date_when_completed():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_legionella_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Legionella assessment record",
            structured_fields={
                "assessment_completed": {"answer": True},
                "assessment_date": {"answer": ""},
                "risk_level": {"answer": "medium"},
                "control_measures_in_place": {"answer": True},
                "actions_required": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="rleg",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "LEGIONELLA_ASSESSMENT_DATE_REQUIRED"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_legionella_rejects_next_review_when_actions_required():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_legionella_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Legionella assessment record",
            structured_fields={
                "assessment_completed": {"answer": True},
                "assessment_date": {"answer": "2026-04-01"},
                "risk_level": {"answer": "high"},
                "control_measures_in_place": {"answer": True},
                "actions_required": {"answer": True},
                "next_review_date": {"answer": ""},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="rleg",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "LEGIONELLA_NEXT_REVIEW_REQUIRED"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_legionella_valid_structured_submission_passes():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_legionella_requirement_row())
    create_mock = AsyncMock(return_value={"evidence_record_id": "cer_leg"})
    sync_mock = AsyncMock()
    enqueue_mock = AsyncMock(return_value=True)
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Legionella assessment record",
            structured_fields={
                "assessment_completed": {"answer": True},
                "assessment_date": {"answer": "2026-04-01"},
                "assessor_type": {"answer": "external"},
                "risk_level": {"answer": "medium"},
                "control_measures_in_place": {"answer": True},
                "actions_required": {"answer": True},
                "next_review_date": {"answer": "2026-10-01"},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    out = await route.post_compliance_evidence(
                        property_id="p1",
                        requirement_id="rleg",
                        body=body,
                        request=_req(),
                        user={"client_id": "c1", "portal_user_id": "u1"},
                    )
    assert out["ok"] is True
    create_mock.assert_awaited()


@pytest.mark.asyncio
async def test_post_lead_testing_rejects_missing_assessment_date_when_completed():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_lead_testing_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Lead assessment record",
            structured_fields={
                "assessment_completed": {"answer": True},
                "assessment_date": {"answer": ""},
                "assessment_type": {"answer": "water_test"},
                "risk_level": {"answer": "medium"},
                "lead_present": {"answer": True},
                "actions_required": {"answer": False},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="rlead",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "LEAD_TESTING_ASSESSMENT_DATE_REQUIRED"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_lead_testing_rejects_next_review_when_actions_required():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=_lead_testing_requirement_row())
    create_mock = AsyncMock()
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Lead assessment record",
            structured_fields={
                "assessment_completed": {"answer": True},
                "assessment_date": {"answer": "2026-04-01"},
                "assessment_type": {"answer": "full_assessment"},
                "risk_level": {"answer": "high"},
                "lead_present": {"answer": True},
                "actions_required": {"answer": True},
                "next_review_date": {"answer": ""},
                "declaration_confirmed": {"answer": True},
            },
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with pytest.raises(HTTPException) as ei:
                await route.post_compliance_evidence(
                    property_id="p1",
                    requirement_id="rlead",
                    body=body,
                    request=_req(),
                    user={"client_id": "c1", "portal_user_id": "u1"},
                )
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "LEAD_TESTING_NEXT_REVIEW_REQUIRED"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_post_smoke_heat_structured_declaration_unaffected_by_r2r_follow_up_rule():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "rsm",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "smoke_heat_alarms",
            "registry_metadata": {"evidence_resolution": {"allowed_evidence_modes": ["STRUCTURED_DECLARATION"]}},
        }
    )
    create_mock = AsyncMock(return_value={"evidence_record_id": "cer_s"})
    sync_mock = AsyncMock()
    enqueue_mock = AsyncMock(return_value=True)
    body = route.CreateEvidenceRequest(
        evidence_mode="STRUCTURED_DECLARATION",
        structured_declaration=route.StructuredDeclarationBody(
            declaration_statement="Alarms ok",
            structured_fields={"declaration_confirmed": {"answer": True}},
        ),
    )
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    out = await route.post_compliance_evidence(
                        property_id="p1",
                        requirement_id="rsm",
                        body=body,
                        request=_req(),
                        user={"client_id": "c1", "portal_user_id": "u1"},
                    )
    assert out["ok"] is True
    create_mock.assert_awaited()


@pytest.mark.asyncio
async def test_authority_sync_runs_after_evidence_creation_and_legacy_payload_works():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "smoke_heat_alarms",
            "registry_metadata": {"evidence_resolution": {"allowed_evidence_modes": ["CONTRACTOR_CONFIRMATION"]}},
        }
    )
    body = route.CreateEvidenceRequest.model_validate(
        {
            "evidence_mode": "CONTRACTOR_CONFIRMATION",
            "contractor_confirmation": {
                "contractor_name": "Trade Person",
                "contractor_company": "Legacy Company Ltd",
                "completion_date": "2026-04-01",
                "work_summary": "Installed and tested alarms in all required rooms.",
            },
        }
    )
    create_mock = AsyncMock(return_value={"evidence_record_id": "cer_1"})
    sync_mock = AsyncMock()
    enqueue_mock = AsyncMock(return_value=True)
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    out = await route.post_compliance_evidence(
                        property_id="p1",
                        requirement_id="r1",
                        body=body,
                        request=_req(),
                        user={"client_id": "c1", "portal_user_id": "u1"},
                    )
    assert out["ok"] is True
    create_mock.assert_awaited()
    sync_mock.assert_awaited_once()
    enqueue_mock.assert_awaited_once()
    ek = enqueue_mock.await_args.kwargs
    assert ek["property_id"] == "p1"
    assert ek["client_id"] == "c1"
    assert ek["correlation_id"] == "GUIDED_EVIDENCE_AUTHORITY:p1:r1:cer_1"


@pytest.mark.asyncio
async def test_evidence_verification_enqueues_recalc_after_authority_sync():
    db = MagicMock()
    db.compliance_evidence_records.find_one = AsyncMock(
        return_value={
            "evidence_record_id": "cer_v1",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
        }
    )
    apply_mock = AsyncMock(return_value={"evidence_record_id": "cer_v1", "status": "VERIFIED"})
    sync_mock = AsyncMock()
    enqueue_mock = AsyncMock(return_value=True)
    body = route.VerifyEvidenceRequest(decision="VERIFY")
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "apply_verification_decision", apply_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    out = await route.post_evidence_verification(
                        property_id="p1",
                        requirement_id="r1",
                        evidence_record_id="cer_v1",
                        body=body,
                        request=_req(),
                        user={
                            "client_id": "c1",
                            "portal_user_id": "u1",
                            "role": "ROLE_CLIENT_ADMIN",
                        },
                    )
    assert out["ok"] is True
    sync_mock.assert_awaited_once()
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.kwargs["correlation_id"] == "GUIDED_EVIDENCE_VERIFY:p1:r1:cer_v1"


@pytest.mark.asyncio
async def test_post_compliance_evidence_propagates_sync_failure_no_enqueue_no_ok():
    """If sync_requirement_evidence_authority raises after create, request fails and recalc is not enqueued."""
    db = MagicMock()
    db.requirements.find_one = AsyncMock(
        return_value={
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "smoke_heat_alarms",
            "registry_metadata": {"evidence_resolution": {"allowed_evidence_modes": ["CONTRACTOR_CONFIRMATION"]}},
        }
    )
    body = route.CreateEvidenceRequest.model_validate(
        {
            "evidence_mode": "CONTRACTOR_CONFIRMATION",
            "contractor_confirmation": {
                "contractor_name": "Trade Person",
                "contractor_company": "Legacy Company Ltd",
                "completion_date": "2026-04-01",
                "work_summary": "Installed and tested alarms in all required rooms.",
            },
        }
    )
    create_mock = AsyncMock(return_value={"evidence_record_id": "cer_sync_fail"})
    sync_mock = AsyncMock(side_effect=RuntimeError("authority_sync_failed"))
    enqueue_mock = AsyncMock(return_value=True)
    audit_mock = AsyncMock()
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "create_compliance_evidence_record", create_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    with patch.object(route, "create_audit_log", audit_mock):
                        with pytest.raises(RuntimeError, match="authority_sync_failed"):
                            await route.post_compliance_evidence(
                                property_id="p1",
                                requirement_id="r1",
                                body=body,
                                request=_req(),
                                user={"client_id": "c1", "portal_user_id": "u1"},
                            )
    create_mock.assert_awaited_once()
    sync_mock.assert_awaited_once()
    enqueue_mock.assert_not_awaited()
    audit_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_evidence_verification_propagates_sync_failure_no_enqueue_no_ok():
    """If sync_requirement_evidence_authority raises after verify, request fails and recalc is not enqueued."""
    db = MagicMock()
    db.compliance_evidence_records.find_one = AsyncMock(
        return_value={
            "evidence_record_id": "cer_v1",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
        }
    )
    apply_mock = AsyncMock(return_value={"evidence_record_id": "cer_v1", "status": "VERIFIED"})
    sync_mock = AsyncMock(side_effect=RuntimeError("authority_sync_failed"))
    enqueue_mock = AsyncMock(return_value=True)
    audit_mock = AsyncMock()
    body = route.VerifyEvidenceRequest(decision="VERIFY")
    with patch.object(route.database, "get_db", return_value=db):
        with patch.object(route, "apply_verification_decision", apply_mock):
            with patch.object(route, "sync_requirement_evidence_authority", sync_mock):
                with patch.object(route, "enqueue_compliance_recalc", enqueue_mock):
                    with patch.object(route, "create_audit_log", audit_mock):
                        with pytest.raises(RuntimeError, match="authority_sync_failed"):
                            await route.post_evidence_verification(
                                property_id="p1",
                                requirement_id="r1",
                                evidence_record_id="cer_v1",
                                body=body,
                                request=_req(),
                                user={
                                    "client_id": "c1",
                                    "portal_user_id": "u1",
                                    "role": "ROLE_CLIENT_ADMIN",
                                },
                            )
    apply_mock.assert_awaited_once()
    sync_mock.assert_awaited_once()
    enqueue_mock.assert_not_awaited()
    audit_mock.assert_not_awaited()
