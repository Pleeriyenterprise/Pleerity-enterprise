"""PATCH /api/properties/{property_id}/requirements/{requirement_id} — audit + ordering (Stream E row 10)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from database import database as db_singleton
from models import AuditAction
from routes import properties as properties_routes
from server import app


@pytest.fixture
def client_http():
    with TestClient(app) as c:
        yield c


def test_patch_requirement_audit_metadata_and_order(client_http):
    user = {
        "client_id": "c-audit",
        "portal_user_id": "pu-1",
        "role": "ROLE_CLIENT_ADMIN",
    }
    req_row = {
        "requirement_id": "r-audit",
        "property_id": "p-audit",
        "client_id": "c-audit",
        "status": "OVERDUE",
        "applicability": "REQUIRED",
    }
    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=req_row)
    mock_db.requirements.update_one = AsyncMock()
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p-audit", "jurisdiction": "England"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c-audit", "default_jurisdiction": None})

    call_order: list[str] = []

    async def track_sync(*args, **kwargs):
        call_order.append("sync")

    async def track_audit(*args, **kwargs):
        call_order.append("audit")

    async def track_enqueue(*args, **kwargs):
        call_order.append("enqueue")

    audit_mock = AsyncMock(side_effect=track_audit)
    enqueue_mock = AsyncMock(side_effect=track_enqueue)

    async def guard(_request):
        return user

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(properties_routes, "client_route_guard", guard),
        patch(
            "services.requirement_evidence_authority.sync_requirement_evidence_authority",
            AsyncMock(side_effect=track_sync),
        ),
        patch("routes.properties.create_audit_log", audit_mock),
        patch(
            "services.compliance_recalc_queue.enqueue_compliance_recalc",
            enqueue_mock,
        ),
        patch("services.score_events_service.write_score_event", AsyncMock()),
    ):
        res = client_http.patch(
            "/api/properties/p-audit/requirements/r-audit",
            json={"confirmed_expiry_date": "2027-06-15"},
        )

    assert res.status_code == 200, res.text
    assert call_order == ["sync", "audit", "enqueue"]
    audit_mock.assert_awaited_once()
    kw = audit_mock.await_args.kwargs
    assert kw["action"] == AuditAction.REQUIREMENT_ACTION_TRIGGERED
    assert kw["client_id"] == "c-audit"
    assert kw["resource_type"] == "requirement"
    assert kw["resource_id"] == "r-audit"
    meta = kw["metadata"]
    assert meta["property_id"] == "p-audit"
    assert meta["requirement_id"] == "r-audit"
    assert meta["mutation_source"] == "routes.properties.patch_requirement"
    assert meta["event"] == "client_patch_requirement"
    assert meta["fields_changed"] == ["confirmed_expiry_date"]
    assert meta["status_before"] == "OVERDUE"
    assert meta["correlation_id"] == "REQUIREMENT_UPDATED:r-audit"
    assert "status_after" in meta
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.kwargs["correlation_id"] == "REQUIREMENT_UPDATED:r-audit"


def test_patch_requirement_clears_na_metadata_when_applicability_required(client_http):
    user = {
        "client_id": "c-audit",
        "portal_user_id": "pu-1",
        "role": "ROLE_CLIENT_ADMIN",
    }
    req_row = {
        "requirement_id": "r-na",
        "property_id": "p-audit",
        "client_id": "c-audit",
        "status": "NOT_REQUIRED",
        "applicability": "NOT_REQUIRED",
        "not_required_reason": "other",
        "not_applicable_audit_reason": "previous audit reason long enough",
    }
    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=req_row)
    mock_db.requirements.update_one = AsyncMock()
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p-audit", "jurisdiction": "England"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c-audit", "default_jurisdiction": None})

    async def guard(_request):
        return user

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(properties_routes, "client_route_guard", guard),
        patch(
            "services.requirement_evidence_authority.sync_requirement_evidence_authority",
            AsyncMock(),
        ),
        patch("routes.properties.create_audit_log", AsyncMock()),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", AsyncMock()),
        patch("services.score_events_service.write_score_event", AsyncMock()),
    ):
        res = client_http.patch(
            "/api/properties/p-audit/requirements/r-na",
            json={"applicability": "REQUIRED"},
        )

    assert res.status_code == 200, res.text
    mock_db.requirements.update_one.assert_awaited_once()
    upd = mock_db.requirements.update_one.await_args[0][1]
    assert "$unset" in upd
    assert "not_required_reason" in upd["$unset"]
    assert "not_applicable_audit_reason" in upd["$unset"]


def test_patch_requirement_not_required_requires_audit_reason(client_http):
    user = {
        "client_id": "c-audit",
        "portal_user_id": "pu-1",
        "role": "ROLE_CLIENT_ADMIN",
    }
    req_row = {
        "requirement_id": "r-na",
        "property_id": "p-audit",
        "client_id": "c-audit",
        "status": "OVERDUE",
        "applicability": "REQUIRED",
    }
    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=req_row)
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p-audit", "jurisdiction": "England"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c-audit", "default_jurisdiction": None})

    async def guard(_request):
        return user

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(properties_routes, "client_route_guard", guard),
    ):
        res = client_http.patch(
            "/api/properties/p-audit/requirements/r-na",
            json={"applicability": "NOT_REQUIRED", "not_required_reason": "other"},
        )

    assert res.status_code == 400
    assert "not_applicable_audit_reason" in res.text.lower()


def test_patch_requirement_no_audit_when_no_updates(client_http):
    user = {
        "client_id": "c-audit",
        "portal_user_id": "pu-1",
        "role": "ROLE_CLIENT_ADMIN",
    }
    req_row = {
        "requirement_id": "r-audit",
        "property_id": "p-audit",
        "client_id": "c-audit",
        "status": "COMPLIANT",
    }
    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=req_row)
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p-audit"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c-audit"})

    async def guard(_request):
        return user

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(properties_routes, "client_route_guard", guard),
        patch("routes.properties.create_audit_log", AsyncMock()) as audit_mock,
        patch(
            "services.requirement_evidence_authority.sync_requirement_evidence_authority",
            AsyncMock(),
        ),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", AsyncMock()),
    ):
        res = client_http.patch("/api/properties/p-audit/requirements/r-audit", json={})

    assert res.status_code == 200
    audit_mock.assert_not_called()
