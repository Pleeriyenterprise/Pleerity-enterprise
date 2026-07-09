"""ILP-4 — profile, assistant, and calendar capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import assistant as assistant_routes
from routes import calendar as calendar_routes
from routes import profile as profile_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

CLIENT_ID = "c-ilp4-pac-1"


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
        "portal_user_id": "pu-ilp4-pac-1",
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
    "CANCELLATION_SCHEDULED": (
        _client(),
        _billing(
            subscription_status="ACTIVE",
            billing_lifecycle_state="cancel_at_period_end",
            cancel_at_period_end=True,
            current_period_end=PERIOD_END.isoformat(),
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
def pac_user():
    return _portal_user()


@pytest.fixture
def override_guard(pac_user):
    async def _fake_guard(request: Request):
        return pac_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(profile_routes, "client_route_guard", new=AsyncMock(return_value=pac_user)):
        with patch.object(assistant_routes, "client_route_guard", new=AsyncMock(return_value=pac_user)):
            with patch.object(calendar_routes, "client_route_guard", new=AsyncMock(return_value=pac_user)):
                with patch.object(profile_routes, "require_auth", new=AsyncMock(return_value=pac_user)):
                    yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestProfileAssistantCalendarSourceGovernance:
    def test_profile_routes_use_capability_enforcement(self):
        source = open(profile_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "require_feature" not in source
        assert "_enforce_capability" in source
        assert "CAP_PROFILE_VIEW" in source
        assert "CAP_PROFILE_EDIT" in source

    def test_assistant_routes_use_capability_enforcement(self):
        source = open(assistant_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "require_feature" not in source
        assert "_enforce_capability" in source
        assert "CAP_AI_ASSISTANT" in source

    def test_calendar_routes_use_capability_enforcement(self):
        source = open(calendar_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "plan_registry" not in source
        assert "require_feature" not in source
        assert "_require_calendar_view" in source
        assert "CAP_CALENDAR_VIEW" in source


class TestProfileAssistantCalendarRuntimeMatrix:
    def test_new_capabilities_in_contract(self):
        contract = _contract()
        for cap in ("CAP_PROFILE_JURISDICTION", "CAP_CALENDAR_VIEW"):
            assert cap in contract["capabilities"]

    def test_existing_capabilities_in_contract(self):
        contract = _contract()
        for cap in ("CAP_PROFILE_VIEW", "CAP_PROFILE_EDIT", "CAP_AI_ASSISTANT"):
            assert cap in contract["capabilities"]


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestProfileLifecycle:
    def test_profile_view_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_PROFILE_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.portal_users.find_one = AsyncMock(
                    return_value={"portal_user_id": "pu-ilp4-pac-1", "auth_email": "a@example.com"}
                )
                mock_db.clients.find_one = AsyncMock(
                    return_value={"full_name": "Test", "client_type": "INDIVIDUAL"}
                )
                mock_db.notification_preferences.find_one = AsyncMock(return_value=None)
                stack.enter_context(
                    patch("routes.profile.database.get_db", return_value=mock_db)
                )
            res = client.get("/api/profile/me")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_profile_edit_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_PROFILE_EDIT"
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
                mock_db.clients.find_one = AsyncMock(
                    return_value={"full_name": "Old Name", "phone": ""}
                )
                mock_db.clients.update_one = AsyncMock()
                stack.enter_context(
                    patch("routes.profile.database.get_db", return_value=mock_db)
                )
                stack.enter_context(
                    patch("routes.profile.create_audit_log", new=AsyncMock())
                )
            res = client.patch("/api/profile/me", json={"full_name": "Updated Name"})

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestAssistantLifecycle:
    def test_assistant_snapshot_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_AI_ASSISTANT"
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
                        "routes.assistant.assistant_service.get_client_snapshot",
                        new=AsyncMock(return_value={"client_id": CLIENT_ID}),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.assistant.rate_limiter.check_rate_limit",
                        new=AsyncMock(return_value=(True, None)),
                    )
                )
            res = client.get("/api/assistant/snapshot")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_assistant_chat_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_AI_ASSISTANT"
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
                        "routes.assistant.assistant_chat_turn",
                        new=AsyncMock(
                            return_value={
                                "conversation_id": "conv-1",
                                "answer": "ok",
                                "citations": [],
                                "safety_flags": {},
                            }
                        ),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.assistant.rate_limiter.check_rate_limit",
                        new=AsyncMock(return_value=(True, None)),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.assistant.rate_limiter.check_rate_limit_daily",
                        new=AsyncMock(return_value=(True, None)),
                    )
                )
                stack.enter_context(
                    patch("routes.assistant.ai_config.AI_ENABLED", False)
                )
            res = client.post("/api/assistant/chat", json={"message": "Hello"})

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestCalendarLifecycle:
    def test_calendar_events_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_CALENDAR_VIEW"
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
                        "routes.calendar.get_timeline_events_for_range",
                        new=AsyncMock(return_value=[]),
                    )
                )
            res = client.get("/api/calendar/events")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_calendar_export_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_CALENDAR_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.clients.find_one = AsyncMock(return_value={"full_name": "Test"})
                stack.enter_context(
                    patch("routes.calendar.database.get_db", return_value=mock_db)
                )
                stack.enter_context(
                    patch(
                        "routes.calendar.get_timeline_events_for_range",
                        new=AsyncMock(return_value=[]),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.calendar.build_ical_from_timeline_events",
                        return_value="BEGIN:VCALENDAR\nEND:VCALENDAR",
                    )
                )
            res = client.get("/api/calendar/export.ics")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)
