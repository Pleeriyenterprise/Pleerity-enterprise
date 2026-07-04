"""ILP-4 — read API and webhooks capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client_read_api as read_api_routes
from routes import webhooks_config as webhooks_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
CLIENT_ID = "c-ilp4-rw-1"


def _client(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _portal_user():
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-ilp4-rw-1",
        "role": "ROLE_CLIENT",
    }


def _contract(client=None, billing=None, **kwargs):
    return build_runtime_contract(
        client=client or _client(),
        billing=billing or _billing(),
        now=NOW,
        **kwargs,
    )


LIFECYCLE_PRESETS = {
    "ACTIVE": (_client(), _billing()),
    "TRIAL": (_client(), _billing(subscription_status="TRIALING")),
    "READ_ONLY": (
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
            read_only_retention=True,
        ),
    ),
    "CANCELLED_IMMEDIATE": (
        _client(),
        _billing(subscription_status="CANCELED", billing_lifecycle_state="cancelled"),
    ),
    "SUSPENDED": (
        _client(client_lifecycle_status="SUSPENDED"),
        _billing(),
    ),
}


def _mock_evaluate_contract(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


def _expected_allowed(contract, cap_id: str, action: str) -> bool:
    return CapabilityEnforcementService(db=None).evaluate_from_contract(
        contract, cap_id, action
    ).allowed


def _assert_capability_denied(res, cap_id: str):
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "capability_denied"
    assert detail["capability_id"] == cap_id


@pytest.fixture
def rw_user():
    return _portal_user()


@pytest.fixture
def override_guard(rw_user):
    async def _fake_guard(request: Request):
        return rw_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(read_api_routes, "client_route_guard", new=AsyncMock(return_value=rw_user)):
        with patch.object(webhooks_routes, "client_route_guard", new=AsyncMock(return_value=rw_user)):
            yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestReadApiWebhooksSourceGovernance:
    def test_read_api_routes_use_capability_enforcement(self):
        source = open(read_api_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "plan_registry" not in source
        assert "assert_client_capability" in source
        assert "CAP_INTEGRATION_READ_API" in source
        assert "CAP_EXPORT_API" in source

    def test_webhooks_config_routes_use_capability_enforcement(self):
        source = open(webhooks_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "plan_registry" not in source
        assert "assert_client_capability" in source
        assert "CAP_INTEGRATION_WEBHOOKS" in source


class TestReadApiWebhooksRuntimeMatrix:
    def test_integration_capabilities_in_contract(self):
        contract = _contract()
        for cap in (
            "CAP_INTEGRATION_WEBHOOKS",
            "CAP_INTEGRATION_READ_API",
            "CAP_EXPORT_API",
        ):
            assert cap in contract["capabilities"]

    def test_runtime_resolver_count_includes_integration_caps(self):
        from services.account_lifecycle_runtime_contract import _BASE_CAPABILITY_MATRIX

        assert len(_BASE_CAPABILITY_MATRIX) == 64


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestReadApiWebhooksLifecycle:
    def test_read_api_keys_list(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_INTEGRATION_READ_API"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.client_read_api.read_api.list_keys",
                        new=AsyncMock(return_value=[]),
                    )
                )
            res = client.get("/api/client/integrations/read-api-keys")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_webhooks_list(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_INTEGRATION_WEBHOOKS"
        allowed = _expected_allowed(contract, cap, "read")

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.webhooks.find = MagicMock(return_value=mock_cursor)
                stack.enter_context(
                    patch("routes.webhooks_config.database.get_db", return_value=mock_db)
                )
            res = client.get("/api/webhooks")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_webhooks_create_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_INTEGRATION_WEBHOOKS"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.webhooks.find_one = AsyncMock(return_value=None)
                mock_db.webhooks.insert_one = AsyncMock()
                stack.enter_context(
                    patch("routes.webhooks_config.database.get_db", return_value=mock_db)
                )
                stack.enter_context(
                    patch("routes.webhooks_config.create_audit_log", new=AsyncMock())
                )
            res = client.post(
                "/api/webhooks",
                json={
                    "name": "Hook",
                    "url": "https://example.com/hook",
                    "event_types": ["compliance.status_changed"],
                },
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)
