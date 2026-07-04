"""ILP-4 backend completion — remaining customer route capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client as client_routes
from routes import client_lifecycle_runtime as lifecycle_routes
from routes import knowledge_base as kb_routes
from routes import portal as portal_routes
from routes import support as support_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
CLIENT_ID = "c-ilp4-complete-1"


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
        "portal_user_id": "pu-ilp4-complete-1",
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
    "ARCHIVED": (
        _client(is_deleted=True, client_lifecycle_status="ARCHIVED"),
        _billing(),
    ),
    "SUSPENDED": (
        _client(client_lifecycle_status="SUSPENDED"),
        _billing(),
    ),
}


ROUTE_CASES = (
    ("GET", "/api/client/portal-context", "CAP_DASHBOARD_VIEW", "read"),
    ("GET", "/api/client/entitlements/context", "CAP_DASHBOARD_VIEW", "read"),
    ("GET", "/api/client/settings/jurisdiction", "CAP_PROFILE_JURISDICTION", "read"),
    ("GET", "/api/client/lifecycle-runtime", "CAP_PROFILE_VIEW", "read"),
    ("GET", "/api/client/help/categories", "CAP_KNOWLEDGE_CENTRE", "read"),
    ("GET", "/api/support/account-snapshot", "CAP_SUPPORT_ACCESS", "read"),
)


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
def portal_user():
    return _portal_user()


@pytest.fixture
def override_guard(portal_user):
    async def _fake_guard(request: Request):
        return portal_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=portal_user)):
        with patch.object(lifecycle_routes, "client_route_guard", new=AsyncMock(return_value=portal_user)):
            with patch.object(portal_routes, "client_route_guard", new=AsyncMock(return_value=portal_user)):
                with patch.object(kb_routes, "client_route_guard", new=AsyncMock(return_value=portal_user)):
                    with patch.object(support_routes, "client_route_guard", new=AsyncMock(return_value=portal_user)):
                        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestBackendCompletionSourceGovernance:
    def test_client_residual_handlers_use_capability_enforcement(self):
        source = open(client_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "require_feature" not in source
        assert "_require_capability_from_request" in source
        assert 'await _require_capability_from_request(request, "CAP_PROFILE_JURISDICTION"' in source
        assert 'await _require_capability_from_request(request, "CAP_PROFILE_VIEW", "read")' in source

    def test_no_guard_only_onboarding_entitlements_jurisdiction(self):
        source = open(client_routes.__file__, encoding="utf-8").read()
        for marker in (
            'get_onboarding_checklist',
            'get_client_entitlements(',
            'get_plan_features',
            'get_jurisdiction_settings',
        ):
            assert marker in source
        assert source.count("await client_route_guard(request)") == 1


class TestBackendCompletionRuntimeMatrix:
    def test_support_and_knowledge_caps_in_contract(self):
        contract = _contract()
        for cap in ("CAP_KNOWLEDGE_CENTRE", "CAP_SUPPORT_REQUEST"):
            assert cap in contract["capabilities"]

    def test_runtime_resolver_count_includes_support_caps(self):
        from services.account_lifecycle_runtime_contract import _BASE_CAPABILITY_MATRIX

        assert len(_BASE_CAPABILITY_MATRIX) == 69


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
@pytest.mark.parametrize("method,path,cap_id,action", ROUTE_CASES)
class TestBackendCompletionLifecycle:
    def test_route_capability_gate(
        self, client, override_guard, lifecycle, method, path, cap_id, action
    ):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        allowed = _expected_allowed(contract, cap_id, action)

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed and path == "/api/client/settings/jurisdiction":
                stack.enter_context(
                    patch(
                        "routes.client._resolved_jurisdiction_settings_for_client",
                        new=AsyncMock(
                            return_value={
                                "default_jurisdiction": "Scotland",
                                "enabled_jurisdictions": ["Scotland"],
                            }
                        ),
                    )
                )
            if allowed and path == "/api/client/portal-context":
                mock_db = MagicMock()
                mock_db.audit_logs.find_one = AsyncMock(return_value=None)
                stack.enter_context(
                    patch("routes.client.database.get_db", return_value=mock_db)
                )
            if allowed and path == "/api/client/entitlements/context":
                class _Props:
                    async def count_documents(self, q):
                        return 0

                mock_db = MagicMock()
                mock_db.properties = _Props()
                stack.enter_context(
                    patch("routes.client.database.get_db", return_value=mock_db)
                )
                stack.enter_context(
                    patch(
                        "services.plan_registry.plan_registry.get_client_entitlements",
                        new=AsyncMock(
                            return_value={
                                "plan": "PLAN_1_SOLO",
                                "plan_name": "Solo",
                                "is_active": True,
                                "max_properties": 2,
                            }
                        ),
                    )
                )
            if allowed and path == "/api/client/lifecycle-runtime":
                stack.enter_context(
                    patch(
                        "routes.client_lifecycle_runtime.resolve_runtime_contract_for_client",
                        new=AsyncMock(return_value=_contract(client_doc, billing)),
                    )
                )
            if allowed and path == "/api/client/help/categories":
                stack.enter_context(
                    patch(
                        "routes.knowledge_base.ensure_default_categories",
                        new=AsyncMock(),
                    )
                )
                mock_db = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.sort = MagicMock(return_value=mock_cursor)
                mock_cursor.to_list = AsyncMock(return_value=[])
                mock_db.__getitem__ = MagicMock(
                    side_effect=lambda name: MagicMock(
                        find=MagicMock(return_value=mock_cursor),
                        aggregate=MagicMock(return_value=AsyncMock()),
                    )
                )
                stack.enter_context(
                    patch("routes.knowledge_base.database.get_db", return_value=mock_db)
                )
            if allowed and path == "/api/support/account-snapshot":
                stack.enter_context(
                    patch(
                        "routes.support.get_client_snapshot",
                        new=AsyncMock(return_value={"client_id": CLIENT_ID}),
                    )
                )

            res = client.request(method, path)

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap_id)
