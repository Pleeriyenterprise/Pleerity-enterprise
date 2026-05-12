"""Catalog mark-not-applicable: client route wires sync + audit + async enqueue (governance alignment)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from database import database as db_singleton
from middleware import client_route_guard as middleware_client_route_guard
from routes import client as client_routes
from server import app


@pytest.fixture
def client_http():
    with TestClient(app) as c:
        yield c


def test_client_catalog_mark_not_applicable_orders_sync_audit_enqueue(client_http):
    user = {"client_id": "c-na", "portal_user_id": "pu-1", "role": "ROLE_CLIENT_ADMIN"}
    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={"property_id": "p-na", "jurisdiction": "England", "client_id": "c-na"},
    )
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c-na", "default_jurisdiction": None})
    mock_db.requirements_catalog.find_one = AsyncMock(
        return_value={"code": "gas_safety", "title": "Gas Safety"},
    )
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_db.requirements.find = MagicMock(return_value=mock_cursor)
    mock_db.requirements.insert_one = AsyncMock()
    mock_db.requirements.update_one = AsyncMock()

    call_order: list[str] = []

    async def track_sync(*_a, **_k):
        call_order.append("sync")

    async def track_audit(*_a, **_k):
        call_order.append("audit")

    async def track_enqueue(*_a, **_k):
        call_order.append("enqueue")

    async def _fake_guard(request: Request):
        return user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    try:
        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=user)),
            patch(
                "services.requirement_evidence_authority.sync_requirement_evidence_authority",
                AsyncMock(side_effect=track_sync),
            ),
            patch(
                "services.requirement_mark_not_applicable_catalog.create_audit_log",
                AsyncMock(side_effect=track_audit),
            ),
            patch(
                "services.compliance_recalc_queue.enqueue_compliance_recalc",
                AsyncMock(side_effect=track_enqueue),
            ),
        ):
            res = client_http.post(
                "/api/client/properties/p-na/requirements/mark-not-applicable",
                json={
                    "requirement_code": "gas_safety",
                    "not_required_reason": "not_applicable",
                    "reason": "This property has no gas supply at all for operational audit.",
                },
            )
    finally:
        app.dependency_overrides.pop(middleware_client_route_guard, None)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("requirement_id")
    assert body.get("created") is True
    assert call_order == ["sync", "audit", "enqueue"]
