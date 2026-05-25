"""HTTP registration tests for tenancy-authority rent routes."""
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client_rent_operations
from server import app

CLIENT_ID = "cli-rent-tenancy-routes"


async def _guard(request: Request):
    return {"client_id": CLIENT_ID, "portal_user_id": "pu-1", "role": "ROLE_CLIENT"}


@pytest.fixture
def rent_http():
    app.dependency_overrides[middleware_client_route_guard] = _guard
    with patch.object(
        client_rent_operations,
        "get_effective_flags",
        new_callable=AsyncMock,
        return_value={"RENT_OPERATIONS": True},
    ), patch.object(client_rent_operations, "client_route_guard", new=_guard):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


def test_capabilities_endpoint(client, rent_http):
    r = client.get("/api/client/operations/rent/capabilities")
    assert r.status_code == 200
    assert r.json().get("tenancy_authority") is True


def test_tenancies_list_route_registered(client, rent_http):
    with patch.object(
        client_rent_operations.tenancy_authority,
        "list_property_tenancies",
        new_callable=AsyncMock,
        return_value=[{"tenancy_id": "pty_1"}],
    ):
        r = client.get("/api/client/operations/rent/tenancies", params={"property_id": "p1"})
    assert r.status_code == 200
    assert r.json()["tenancies"][0]["tenancy_id"] == "pty_1"


def test_schedule_preview_route_registered(client, rent_http):
    with patch.object(
        client_rent_operations.rent_ledger_service,
        "ensure_property_scope",
        new_callable=AsyncMock,
    ), patch.object(
        client_rent_operations.rent_ledger_service,
        "preview_schedule_periods",
        return_value={"period_count": 3, "disclosure": "3 monthly periods"},
    ):
        r = client.post(
            "/api/client/operations/rent/schedules/preview",
            json={
                "property_id": "p1",
                "expected_amount_minor": 120000,
                "start_date": "2026-06-01",
                "due_day": 1,
            },
        )
    assert r.status_code == 200
    assert r.json()["period_count"] == 3


def test_create_schedule_external_payer_passes_body(client, rent_http):
    with patch.object(
        client_rent_operations.rent_ledger_service,
        "create_rent_schedule",
        new_callable=AsyncMock,
        return_value={"schedule_id": "rs_ext", "is_external_payer": True},
    ) as create_mock:
        r = client.post(
            "/api/client/operations/rent/schedules",
            json={
                "property_id": "p1",
                "expected_amount_minor": 100000,
                "start_date": "2026-06-01",
                "due_day": 1,
                "is_external_payer": True,
                "external_payer_name": "Council",
            },
        )
    assert r.status_code == 200
    body = create_mock.call_args[0][1]
    assert body.get("is_external_payer") is True
    assert body.get("external_payer_name") == "Council"
