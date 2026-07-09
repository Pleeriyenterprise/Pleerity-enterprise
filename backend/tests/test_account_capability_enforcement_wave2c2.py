"""ILP-4 Phase 2C-2 — dashboard, command centre, today, ledger capability enforcement."""
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

WAVE2C2_CLIENT_ID = "c-wave2c2-1"


def _client(**overrides):
    base = {
        "client_id": WAVE2C2_CLIENT_ID,
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": WAVE2C2_CLIENT_ID,
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _portal_user():
    return {
        "client_id": WAVE2C2_CLIENT_ID,
        "portal_user_id": "pu-wave2c2-1",
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
    "GRACE_PERIOD": (
        _client(),
        _billing(
            subscription_status="PAST_DUE",
            billing_lifecycle_state="grace_period",
            grace_period_ends_at=GRACE_END.isoformat(),
        ),
    ),
    "CANCELLATION_SCHEDULED": (
        _client(),
        _billing(
            subscription_status="ACTIVE",
            billing_lifecycle_state="cancel_at_period_end",
            cancel_at_period_end=True,
            current_period_end=PERIOD_END.isoformat(),
        ),
    ),
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
    "SUBSCRIPTION_EXPIRED": (
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
            canonical_entitlement_state="SUSPENDED",
        ),
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


def _is_capability_denied(res) -> bool:
    if res.status_code != 403:
        return False
    detail = res.json().get("detail")
    return isinstance(detail, dict) and detail.get("error") == "capability_denied"


def _assert_capability_denied(res, cap_id: str):
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "capability_denied"
    assert detail["capability_id"] == cap_id


@pytest.fixture
def wave2c2_user():
    return _portal_user()


@pytest.fixture
def override_guard(wave2c2_user):
    async def _fake_guard(request: Request):
        return wave2c2_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=wave2c2_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestWave2C2RuntimeMatrixExtensions:
    def test_ledger_capabilities_in_contract(self):
        contract = _contract()
        assert "CAP_LEDGER_VIEW" in contract["capabilities"]
        assert "CAP_LEDGER_EXPORT" in contract["capabilities"]


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestWave2C2ClientOpsLifecycle:
    def test_ledger_view_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_LEDGER_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.score_ledger_service.list_ledger",
                        new=AsyncMock(return_value={"items": [], "next_cursor": None}),
                    )
                )
            res = client.get("/api/client/ledger")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_ledger_export_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_LEDGER_EXPORT"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.score_ledger_service.list_ledger_export",
                        new=AsyncMock(return_value=[]),
                    )
                )
            res = client.get("/api/client/ledger/export.csv")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_dashboard_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_DASHBOARD_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        mock_db = MagicMock()
        mock_db.clients.find_one = AsyncMock(return_value={"client_id": WAVE2C2_CLIENT_ID})
        prop_cursor = MagicMock()
        prop_cursor.to_list = AsyncMock(return_value=[])
        mock_db.properties.find = MagicMock(return_value=prop_cursor)
        req_cursor = MagicMock()
        req_cursor.to_list = AsyncMock(return_value=[])
        mock_db.requirements.find = MagicMock(return_value=req_cursor)

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
                        "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
                        new=AsyncMock(side_effect=lambda _db, **kw: kw["requirements"]),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.requirement_truth.enrich_requirements_for_client",
                        new=AsyncMock(return_value=([], {})),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.onboarding_checklist_service.get_checklist_for_client",
                        new=AsyncMock(return_value={"items": []}),
                    )
                )
            res = client.get("/api/client/dashboard")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_command_center_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_CMD_CTR_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.ops_compliance_feature_flags.get_effective_flags",
                        new=AsyncMock(return_value={}),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.command_center_service.get_command_center_bundle",
                        new=AsyncMock(return_value={"urgent_actions": []}),
                    )
                )
            res = client.get("/api/client/command-center")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_today_tasks_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_TODAY_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.unified_tasks_service.get_unified_tasks_for_client",
                        new=AsyncMock(return_value={"tasks": {}, "summary": {}}),
                    )
                )
            res = client.get("/api/client/tasks")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_today_act_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_TODAY_ACT"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.client_task_state_service.apply_task_action",
                        new=AsyncMock(return_value={"ok": True}),
                    )
                )
            res = client.post(
                "/api/client/tasks/override",
                json={"task_id": "compliance:abc123", "action": "reviewed"},
            )

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)
