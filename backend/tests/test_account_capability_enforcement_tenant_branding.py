"""ILP-4 — tenant and branding capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client as client_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)

CLIENT_ID = "c-ilp4-tb-1"


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
        "portal_user_id": "pu-ilp4-tb-1",
        "role": "ROLE_CLIENT_ADMIN",
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
    "ARCHIVED": (
        _client(is_deleted=True, client_lifecycle_status="ARCHIVED"),
        _billing(),
    ),
    "UNKNOWN": (
        _client(),
        _billing(subscription_status="WEIRD", billing_lifecycle_state="active"),
    ),
}


def _mock_evaluate_contract(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


def _svc():
    return CapabilityEnforcementService(db=None)


def _expected_allowed(contract, cap_id: str, action: str) -> bool:
    return _svc().evaluate_from_contract(contract, cap_id, action).allowed


def _assert_capability_denied(res, cap_id: str):
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "capability_denied"
    assert detail["capability_id"] == cap_id


@pytest.fixture
def tb_user():
    return _portal_user()


@pytest.fixture
def override_guard(tb_user):
    async def _fake_guard(request: Request):
        return tb_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=tb_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestTenantBrandingSourceGovernance:
    def test_tenant_and_branding_blocks_no_enforce_feature(self):
        source = open(client_routes.__file__, encoding="utf-8").read()
        tenant_start = source.index('@router.post("/tenants/invite")')
        branding_end = source.index("@router.get(\"/branding/preview\")") + len(
            '@router.get("/branding/preview")'
        )
        preview_end = source.index("branding_preview.pdf")
        block = source[tenant_start:preview_end]
        assert "enforce_feature" not in block
        assert 'client_require_capability("CAP_TENANT_MANAGE"' in block
        assert 'client_require_capability("CAP_TENANT_MESSAGES"' in block
        assert 'client_require_capability("CAP_BRANDING_VIEW"' in block
        assert 'client_require_capability("CAP_BRANDING_EDIT"' in block


class TestTenantBrandingRuntimeMatrix:
    def test_new_capabilities_in_contract(self):
        contract = _contract()
        for cap in (
            "CAP_TENANT_MANAGE",
            "CAP_TENANT_MESSAGES",
            "CAP_BRANDING_VIEW",
            "CAP_BRANDING_EDIT",
            "CAP_BRANDING_WHITE_LABEL",
        ):
            assert cap in contract["capabilities"]


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestTenantBrandingLifecycle:
    def test_tenant_list_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_TENANT_MANAGE"
        allowed = _expected_allowed(contract, cap, "read")

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.portal_users.find = MagicMock(return_value=mock_cursor)
                mock_db.tenant_assignments.find = MagicMock(return_value=mock_cursor)
                from database import database as db_singleton

                stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            res = client.get("/api/client/tenants")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_tenant_messages_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_TENANT_MESSAGES"
        allowed = _expected_allowed(contract, cap, "read")

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.tenant_messages.find = MagicMock(return_value=mock_cursor)
                from database import database as db_singleton

                stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            res = client.get("/api/client/tenant-messages")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_tenant_invite_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_TENANT_MANAGE"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            res = client.post(
                "/api/client/tenants/invite",
                json={"email": "t@example.com", "full_name": "Tenant"},
            )

        if allowed:
            assert res.status_code != 403 or res.json().get("detail", {}).get("capability_id") != cap
        else:
            _assert_capability_denied(res, cap)

    def test_branding_get_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_BRANDING_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        mock_db = MagicMock()
        mock_db.branding_settings.find_one = AsyncMock(return_value=None)
        mock_db.clients.find_one = AsyncMock(return_value={"company_name": "Co", "email": "a@b.c"})

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                from database import database as db_singleton

                stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
                stack.enter_context(
                    patch(
                        "services.branding_resolver_service.resolve_branding",
                        new=AsyncMock(
                            return_value=MagicMock(to_portal_dict=MagicMock(return_value={}))
                        ),
                    )
                )
            res = client.get("/api/client/branding")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_branding_update_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_BRANDING_EDIT"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.branding_settings.find_one = AsyncMock(return_value={})
                mock_db.branding_settings.update_one = AsyncMock()
                mock_db.clients.find_one = AsyncMock(return_value={"email": "a@b.c"})
                from database import database as db_singleton

                stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
                stack.enter_context(patch("utils.audit.create_audit_log", new=AsyncMock()))
                stack.enter_context(
                    patch(
                        "services.branding_resolver_service.resolve_branding",
                        new=AsyncMock(
                            return_value=MagicMock(to_portal_dict=MagicMock(return_value={}))
                        ),
                    )
                )
            res = client.put("/api/client/branding", json={"company_name": "Co"})

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)


class TestTenantBrandingPlanGating:
    def test_solo_plan_denies_tenant_manage(self, client, override_guard):
        contract = _contract(_client(billing_plan="PLAN_1_SOLO"), _billing())
        cap = "CAP_TENANT_MANAGE"
        assert not _expected_allowed(contract, cap, "read")

        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
        ):
            res = client.get("/api/client/tenants")
        _assert_capability_denied(res, cap)

    def test_solo_plan_branding_view_with_feature_disabled(self, client, override_guard):
        contract = _contract(_client(billing_plan="PLAN_1_SOLO"), _billing())
        assert _expected_allowed(contract, "CAP_BRANDING_VIEW", "read")
        assert not _expected_allowed(contract, "CAP_BRANDING_WHITE_LABEL", "read")

        mock_db = MagicMock()
        mock_db.branding_settings.find_one = AsyncMock(return_value=None)
        mock_db.clients.find_one = AsyncMock(return_value={"company_name": "Co", "email": "a@b.c"})

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            from database import database as db_singleton

            stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            stack.enter_context(
                patch(
                    "services.branding_resolver_service.resolve_branding",
                    new=AsyncMock(
                        return_value=MagicMock(to_portal_dict=MagicMock(return_value={}))
                    ),
                )
            )
            res = client.get("/api/client/branding")

        assert res.status_code == 200
        body = res.json()
        assert body["feature_enabled"] is False
        assert body.get("upgrade_required") is True
