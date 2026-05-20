"""Promo recovery context — any account with redemption history, not pilot-lifecycle gated."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.pilot_promo_recovery_service import (
    build_recovery_indicators,
    get_account_promo_recovery_context,
    list_redemptions_for_account,
    should_show_recovery_panel,
)


@pytest.mark.asyncio
async def test_list_redemptions_for_account_matches_email():
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

    redemption = {
        "redemption_id": "r1",
        "client_id": None,
        "redemption_email": "stranded@example.com",
        "status": "payment_failed",
        "created_at": "2026-05-01T12:00:00Z",
    }
    coll = MagicMock()
    coll.find = MagicMock(return_value=_Cursor([redemption]))
    clients_coll = MagicMock()
    clients_coll.find_one = AsyncMock(
        return_value={"client_id": "c-intake", "email": "stranded@example.com", "contact_email": None}
    )

    def _getitem(key):
        if key == "pilot_invite_redemptions":
            return coll
        if key == "clients":
            return clients_coll
        return MagicMock()

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=_getitem)
    mock_db.clients = clients_coll
    with patch("services.pilot_promo_recovery_service.database.get_db", return_value=mock_db):
        rows = await list_redemptions_for_account("c-intake")
    assert len(rows) == 1
    assert rows[0]["status"] == "payment_failed"
    filt = coll.find.call_args[0][0]
    assert "$or" in filt


def test_should_show_recovery_panel_intake_pending_with_redemption():
    client = {"client_id": "c1", "onboarding_status": "INTAKE_PENDING", "pilot_invite_code": "FOUNDING2026"}
    redemptions = [{"status": "payment_failed", "retry_eligible": False, "consumes_eligibility": False}]
    indicators = build_recovery_indicators(redemptions=redemptions, overrides=[], client=client)
    assert should_show_recovery_panel(redemptions=redemptions, overrides=[], client=client, indicators=indicators)
    assert indicators["stranded_onboarding"] is True
    assert indicators["payment_failed"] is True


def test_should_show_recovery_panel_override_only():
    overrides = [{"override_id": "ov1", "override_type": "bypass_first_time", "revoked_at": None}]
    indicators = build_recovery_indicators(redemptions=[], overrides=overrides, client=None)
    assert should_show_recovery_panel(redemptions=[], overrides=overrides, client=None, indicators=indicators)


def test_should_show_recovery_panel_intake_with_invite_only():
    client = {"client_id": "c1", "onboarding_status": "INTAKE_PENDING", "pilot_invite_code": "FOUNDING"}
    indicators = build_recovery_indicators(redemptions=[], overrides=[], client=client)
    assert should_show_recovery_panel(redemptions=[], overrides=[], client=client, indicators=indicators)


def test_should_hide_recovery_panel_no_promo_history():
    assert (
        should_show_recovery_panel(
            redemptions=[],
            overrides=[],
            client={"client_id": "c1", "onboarding_status": "ACTIVE"},
            indicators=build_recovery_indicators(redemptions=[], overrides=[], client={"client_id": "c1"}),
        )
        is False
    )


@pytest.mark.asyncio
async def test_get_account_promo_recovery_context_active_pilot():
    with patch(
        "services.pilot_promo_recovery_service.list_redemptions_for_account",
        new_callable=AsyncMock,
        return_value=[{"status": "redeemed", "consumes_eligibility": True, "retry_eligible": False}],
    ):
        with patch(
            "services.pilot_promo_recovery_service.list_overrides_for_client",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch(
                "services.pilot_promo_recovery_service.database.get_db",
            ) as mock_db:
                mock_db.return_value.clients.find_one = AsyncMock(
                    return_value={"client_id": "c1", "pilot_invite_code": "PILOT", "email": "a@x.com"}
                )
                with patch(
                    "services.pilot_promo_recovery_service.find_active_overrides",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    ctx = await get_account_promo_recovery_context("c1")
    assert ctx["show_recovery_panel"] is True
    assert len(ctx["redemptions"]) == 1
    assert "override_history" in ctx
    assert "waiver_history" in ctx
