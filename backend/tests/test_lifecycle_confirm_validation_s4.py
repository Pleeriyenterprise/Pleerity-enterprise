"""Phase 2 S4 — shadow-only lifecycle confirm validation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from database import database as db_singleton
from routes import properties as properties_routes
from server import app
from services.evidence_document_taxonomy import MATCH_OUTCOME_MATCH_CONFIRMED
from services.lifecycle_confirm_validation import (
    observe_lifecycle_confirm_shadow_for_requirement,
    validate_confirm_payload_against_contract,
)
from services.lifecycle_confirm_contract import build_contract_for_requirement


@pytest.fixture
def client_http():
    with TestClient(app) as c:
        yield c


def _req(requirement_code: str) -> dict:
    return {"requirement_id": "req-s4", "requirement_code": requirement_code}


class TestValidateConfirmPayload:
    @pytest.mark.parametrize(
        "code,payload,expect_accept",
        [
            ("gas_safety", {"expiry_date": "2027-03-15"}, True),
            ("hmo_license", {"expiry_date": "2027-03-15"}, True),
            ("tenancy_agreement", {"expiry_date": "2027-03-15"}, False),
            ("deposit_pi", {"expiry_date": "2027-03-15"}, False),
            ("right_to_rent", {"expiry_date": "2027-03-15"}, False),
            ("legionella", {"expiry_date": "2027-03-15"}, False),
        ],
    )
    def test_expiry_acceptance_by_lifecycle(self, code, payload, expect_accept):
        contract = build_contract_for_requirement(_req(code))
        would_accept, violations = validate_confirm_payload_against_contract(payload, contract)
        assert would_accept is expect_accept
        if not expect_accept:
            assert any(
                v["code"] in ("LIFECYCLE_FIELD_FORBIDDEN", "LIFECYCLE_CONFIRMED_EXPIRY_FORBIDDEN")
                for v in violations
            )

    def test_tenancy_requires_start_not_expiry(self):
        contract = build_contract_for_requirement(_req("tenancy_agreement"))
        would_accept, violations = validate_confirm_payload_against_contract(
            {"tenancy_start_date": "2026-01-01"}, contract
        )
        assert would_accept is True
        would_accept2, violations2 = validate_confirm_payload_against_contract(
            {
                "expiry_date": "2027-01-01",
                "fixed_term_end_date": "2027-01-01",
            },
            contract,
        )
        assert would_accept2 is False
        assert any(v["code"] == "LIFECYCLE_SEMANTIC_EXPIRY_MAP" for v in violations2)

    def test_invalid_date_format(self):
        contract = build_contract_for_requirement(_req("gas_safety"))
        would_accept, violations = validate_confirm_payload_against_contract(
            {"expiry_date": "not-a-date"}, contract
        )
        assert would_accept is False
        assert any(v["code"] == "LIFECYCLE_INVALID_DATE" for v in violations)

    def test_expiry_alias_confirmed_expiry_date(self):
        contract = build_contract_for_requirement(_req("gas_safety"))
        would_accept, _ = validate_confirm_payload_against_contract(
            {"confirmed_expiry_date": "2027-03-15"}, contract
        )
        assert would_accept is True

    def test_review_date_mapped_as_expiry(self):
        contract = build_contract_for_requirement(_req("legionella"))
        would_accept, violations = validate_confirm_payload_against_contract(
            {"expiry_date": "2026-06-01", "assessment_date": "2026-06-01"}, contract
        )
        assert would_accept is False
        assert any(v["code"] == "LIFECYCLE_SEMANTIC_EXPIRY_MAP" for v in violations)


class TestShadowObserveGating:
    def test_off_mode_no_observation(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
        out = observe_lifecycle_confirm_shadow_for_requirement(
            _req("gas_safety"),
            {"expiry_date": "2027-01-01"},
            surface="test",
        )
        assert out is None

    def test_active_mode_no_observation(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
        out = observe_lifecycle_confirm_shadow_for_requirement(
            _req("gas_safety"),
            {"expiry_date": "2027-01-01"},
            surface="test",
        )
        assert out is None

    def test_shadow_returns_observation(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        out = observe_lifecycle_confirm_shadow_for_requirement(
            _req("tenancy_agreement"),
            {"expiry_date": "2027-01-01"},
            surface="test",
        )
        assert out is not None
        assert out["would_accept"] is False
        assert out["violations"]


@pytest.mark.asyncio
async def test_apply_extraction_succeeds_when_shadow_would_reject_tenancy_expiry(monkeypatch):
    monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
    from routes import documents as dr
    from routes.documents import apply_ai_extraction

    doc_id = "doc-s4-tenancy"
    document = {
        "document_id": doc_id,
        "client_id": "cli-s4",
        "property_id": "prop-s4",
        "requirement_id": "req-tenancy",
        "file_name": "tenancy.pdf",
        "document_type": "tenancy_agreement",
        "ai_extraction": {
            "status": "completed",
            "data": {"document_type": "tenancy_agreement", "expiry_date": "2030-01-15"},
        },
    }
    requirement = {
        "requirement_id": "req-tenancy",
        "client_id": "cli-s4",
        "property_id": "prop-s4",
        "status": "PENDING",
        "due_date": None,
        "requirement_type": "tenancy_agreement",
    }
    apply_ok = {
        "evidence_satisfies_requirement": True,
        "match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
        "requirement_evidence_mismatch": False,
        "match_confidence": 0.9,
        "predicted_document_type": "tenancy_agreement",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=document)
    mock_db.requirements.find_one = AsyncMock(return_value=requirement)
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "prop-s4", "client_id": "cli-s4"})
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.notification_preferences.find_one = AsyncMock(return_value={"document_updates": False})

    user = {"client_id": "cli-s4", "portal_user_id": "pu-cli", "role": "ROLE_CLIENT_ADMIN"}
    request = MagicMock(spec=Request)

    with (
        patch.object(dr, "client_route_guard", AsyncMock(return_value=user)),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(dr, "evaluate_document_requirement_match", return_value=apply_ok),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(dr, "_document_path_sync_requirement_authority", new_callable=AsyncMock),
        patch.object(dr, "_document_path_enqueue_recalc", new_callable=AsyncMock),
        patch.object(dr, "create_audit_log", new_callable=AsyncMock),
        patch.object(dr, "_append_document_evidence_to_work_order", new_callable=AsyncMock),
        patch.object(dr, "_set_compliance_work_order_proof_verified", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
        patch(
            "services.property_assets_service.update_asset_last_service_from_requirement",
            new_callable=AsyncMock,
        ),
        patch(
            "services.lifecycle_confirm_validation.observe_lifecycle_confirm_shadow_for_requirement",
            return_value={"would_accept": False, "violations": [{"code": "LIFECYCLE_FIELD_FORBIDDEN"}]},
        ) as observe_mock,
    ):
        out = await apply_ai_extraction(request, doc_id, None)

    assert out.get("document_id") == doc_id
    observe_mock.assert_called_once()
    mock_db.requirements.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_apply_extraction_off_mode_still_calls_observer_without_effect(monkeypatch):
    monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
    from routes import documents as dr
    from routes.documents import apply_ai_extraction

    document = {
        "document_id": "doc-off",
        "client_id": "cli-s4",
        "property_id": "prop-s4",
        "requirement_id": "req-gas",
        "file_name": "gas.pdf",
        "ai_extraction": {
            "status": "completed",
            "data": {"expiry_date": "2030-01-15"},
        },
    }
    requirement = {
        "requirement_id": "req-gas",
        "client_id": "cli-s4",
        "property_id": "prop-s4",
        "requirement_type": "gas_safety",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=document)
    mock_db.requirements.find_one = AsyncMock(return_value=requirement)
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "prop-s4"})
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.notification_preferences.find_one = AsyncMock(return_value=None)

    with (
        patch.object(dr, "client_route_guard", AsyncMock(return_value={"client_id": "cli-s4", "portal_user_id": "pu", "role": "ROLE_CLIENT_ADMIN"})),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(dr, "evaluate_document_requirement_match", return_value={"evidence_satisfies_requirement": True, "match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED}),
        patch("services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces", new_callable=AsyncMock, return_value=True),
        patch.object(dr, "_document_path_sync_requirement_authority", new_callable=AsyncMock),
        patch.object(dr, "_document_path_enqueue_recalc", new_callable=AsyncMock),
        patch.object(dr, "create_audit_log", new_callable=AsyncMock),
        patch.object(dr, "_append_document_evidence_to_work_order", new_callable=AsyncMock),
        patch.object(dr, "_set_compliance_work_order_proof_verified", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
        patch("services.property_assets_service.update_asset_last_service_from_requirement", new_callable=AsyncMock),
        patch("services.lifecycle_confirm_validation.enforce_lifecycle_confirm_or_raise", side_effect=lambda _req, payload, **_kw: payload) as enforce_mock,
    ):
        out = await apply_ai_extraction(MagicMock(spec=Request), "doc-off", None)

    assert out.get("document_id") == "doc-off"
    enforce_mock.assert_called_once()


def test_patch_requirement_shadow_would_reject_but_succeeds(client_http, monkeypatch):
    monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")

    user = {"client_id": "c-s4", "portal_user_id": "pu-1", "role": "ROLE_CLIENT_ADMIN"}
    req_row = {
        "requirement_id": "r-tenancy",
        "property_id": "p-s4",
        "client_id": "c-s4",
        "status": "PENDING",
        "requirement_type": "tenancy_agreement",
    }
    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=req_row)
    mock_db.requirements.update_one = AsyncMock()
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p-s4", "jurisdiction": "England"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c-s4"})

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(properties_routes, "client_route_guard", AsyncMock(return_value=user)),
        patch("services.requirement_evidence_authority.sync_requirement_evidence_authority", AsyncMock()),
        patch("routes.properties.create_audit_log", AsyncMock()),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", AsyncMock()),
        patch("services.score_events_service.write_score_event", AsyncMock()),
    ):
        res = client_http.patch(
            "/api/properties/p-s4/requirements/r-tenancy",
            json={"confirmed_expiry_date": "2027-06-15"},
        )

    assert res.status_code == 200, res.text
    mock_db.requirements.update_one.assert_awaited()
    obs = observe_lifecycle_confirm_shadow_for_requirement(
        req_row,
        {"confirmed_expiry_date": "2027-06-15"},
        surface="patch_requirement",
    )
    assert obs is not None
    assert obs["would_accept"] is False
