"""Admin API routes for pilot redemption recovery and eligibility overrides."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

import routes.admin_pilot_invites as invite_routes
import routes.admin_pilot_lifecycle as lifecycle_routes


@pytest.mark.asyncio
async def test_reset_incomplete_redemption_requires_reason():
    class FakeRequest:
        headers = {}

    body = invite_routes.PilotResetIncompleteRedemptionBody(reason="Support reset stale pending")
    with patch(
        "routes.admin_pilot_invites.require_recent_step_up",
        new_callable=AsyncMock,
    ):
        with patch(
            "services.pilot_invite_service.admin_reset_incomplete_redemption",
            new_callable=AsyncMock,
            return_value={"redemption": {"redemption_id": "r1", "status": "expired"}},
        ) as reset_mock:
            result = await invite_routes.reset_pilot_redemption_incomplete(
                FakeRequest(),
                "r1",
                body,
                user={"portal_user_id": "a1", "email": "admin@test.com"},
            )
    assert result["ok"] is True
    reset_mock.assert_awaited_once()
    assert reset_mock.await_args.kwargs["reason"] == "Support reset stale pending"


@pytest.mark.asyncio
async def test_allow_retry_reason_passed_through():
    class FakeRequest:
        headers = {}

    body = invite_routes.PilotAllowRedemptionRetryBody(reason="Customer payment failed twice")
    with patch("routes.admin_pilot_invites.require_recent_step_up", new_callable=AsyncMock):
        with patch(
            "services.pilot_invite_service.admin_allow_redemption_retry",
            new_callable=AsyncMock,
            return_value={"redemption": {"status": "revoked"}, "override": {"override_id": "ov1"}},
        ) as allow_mock:
            result = await invite_routes.allow_pilot_redemption_retry(
                FakeRequest(),
                "r1",
                body,
                user={"portal_user_id": "a1", "email": "admin@test.com"},
            )
    assert result["ok"] is True
    allow_mock.assert_awaited_once()
    assert allow_mock.await_args.kwargs["reason"] == "Customer payment failed twice"


@pytest.mark.asyncio
async def test_create_eligibility_override_requires_min_reason():
    with pytest.raises(Exception):
        invite_routes.PilotEligibilityOverrideBody(
            scope="email",
            scope_value="u@example.com",
            override_type="bypass_first_time",
            override_reason="ab",
        )


@pytest.mark.asyncio
async def test_create_account_eligibility_override_defaults_client_scope():
    class FakeRequest:
        headers = {}

    body = lifecycle_routes.PilotAccountEligibilityOverrideBody(
        override_type="bypass_first_time",
        override_reason="Existing landlord — approved exception",
        scope="client_id",
    )
    with patch("routes.admin_pilot_lifecycle.require_recent_step_up", new_callable=AsyncMock):
        with patch(
            "services.pilot_redemption_eligibility_service.create_eligibility_override",
            new_callable=AsyncMock,
            return_value={"override_id": "ov1", "override_type": "bypass_first_time"},
        ) as create_mock:
            with patch("services.pilot_invite_service.get_invite_code", new_callable=AsyncMock, return_value=None):
                result = await lifecycle_routes.create_account_eligibility_override(
                    FakeRequest(),
                    "client-abc",
                    body,
                    user={"portal_user_id": "a1", "email": "admin@test.com"},
                )
    assert result["ok"] is True
    create_mock.assert_awaited_once()
    assert create_mock.await_args.kwargs["scope_value"] == "client-abc"
    assert create_mock.await_args.kwargs["override_type"] == "bypass_first_time"


@pytest.mark.asyncio
async def test_revoke_eligibility_override_not_found():
    class FakeRequest:
        headers = {}

    with patch("routes.admin_pilot_invites.require_recent_step_up", new_callable=AsyncMock):
        with patch(
            "services.pilot_redemption_eligibility_service.revoke_eligibility_override",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(HTTPException) as exc:
                await invite_routes.revoke_pilot_eligibility_override(
                    FakeRequest(),
                    "missing-ov",
                    user={"portal_user_id": "a1", "email": "admin@test.com"},
                )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_overrides_for_client_includes_email_scope():
    from unittest.mock import MagicMock

    from services.pilot_redemption_eligibility_service import list_overrides_for_client

    class _Cursor:
        def __init__(self, rows):
            self._rows = rows

        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._rows):
                raise StopAsyncIteration
            self._i += 1
            return self._rows[self._i - 1]

    coll = MagicMock()
    coll.find = MagicMock(
        return_value=_Cursor([{"override_id": "ov1", "scope": "email", "scope_value": "u@example.com"}])
    )
    clients_coll = MagicMock()
    clients_coll.find_one = AsyncMock(
        return_value={"client_id": "c1", "email": "u@example.com", "contact_email": None}
    )

    def _getitem(key):
        if key == "pilot_redemption_eligibility_overrides":
            return coll
        if key == "clients":
            return clients_coll
        return MagicMock()

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=_getitem)
    with patch("services.pilot_redemption_eligibility_service.database.get_db", return_value=mock_db):
        rows = await list_overrides_for_client("c1")
    assert len(rows) == 1
    assert mock_db["clients"].find_one.awaited
    or_clause = coll.find.call_args[0][0]["$or"]
    assert any(c.get("scope") == "email" for c in or_clause)
