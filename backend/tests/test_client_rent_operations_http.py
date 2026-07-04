"""HTTP-level isolation tests for Rent Operations client API."""
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client_rent_operations
from server import app
from services.account_capability_enforcement import CapabilityDecision, GRANT_ALLOW

CLIENT_A = "cli-rent-a"
LEDGER_B = "rlp_foreign"
EXPENSE_B = "pe_foreign"
PROP_B = "prop-rent-b"


async def _allow_capability_evaluate(client_id, capability_id, action, *, contract=None):
    return CapabilityDecision(
        capability_id=capability_id,
        action=action,
        grant=GRANT_ALLOW,
        effective_semantic=GRANT_ALLOW,
        allowed=True,
        source="test",
        reason_code="allowed",
        reason="test allow",
    )


async def _guard_client_a(request: Request):
    return {
        "client_id": CLIENT_A,
        "portal_user_id": "pu-rent-a",
        "role": "ROLE_CLIENT",
    }


@pytest.fixture
def rent_http_guard():
    app.dependency_overrides[middleware_client_route_guard] = _guard_client_a
    yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


@pytest.fixture
def rent_flags_on():
    with patch(
        "routes.client_rent_operations.CapabilityEnforcementService.evaluate",
        new_callable=AsyncMock,
        side_effect=_allow_capability_evaluate,
    ), patch.object(
        client_rent_operations,
        "client_route_guard",
        new=_guard_client_a,
    ):
        yield


def test_http_foreign_ledger_returns_404(client, rent_http_guard, rent_flags_on):
    with patch.object(
        client_rent_operations.rent_ledger_service,
        "get_ledger",
        new_callable=AsyncMock,
        return_value=None,
    ):
        r = client.get(f"/api/client/operations/rent/ledgers/{LEDGER_B}")
    assert r.status_code == 404


def test_http_foreign_expense_returns_404(client, rent_http_guard, rent_flags_on):
    with patch.object(
        client_rent_operations.property_expense_service,
        "update_expense",
        new_callable=AsyncMock,
        return_value=None,
    ):
        r = client.patch(
            f"/api/client/operations/expenses/{EXPENSE_B}",
            json={"description": "x"},
        )
    assert r.status_code == 404


def test_http_foreign_property_summary_404(client, rent_http_guard, rent_flags_on):
    with patch.object(
        client_rent_operations.property_expense_service,
        "get_property_financial_snapshot",
        new_callable=AsyncMock,
        side_effect=ValueError("PROPERTY_NOT_FOUND"),
    ):
        r = client.get(f"/api/client/properties/{PROP_B}/financial-snapshot")
    assert r.status_code == 404


def test_http_payment_foreign_ledger_404(client, rent_http_guard, rent_flags_on):
    with patch.object(
        client_rent_operations.rent_payment_service,
        "record_payment",
        new_callable=AsyncMock,
        side_effect=ValueError("LEDGER_NOT_FOUND"),
    ):
        r = client.post(
            "/api/client/operations/rent/payments",
            json={
                "amount_minor": 10000,
                "payment_date": "2026-05-15",
                "ledger_id": LEDGER_B,
            },
        )
    assert r.status_code == 404
