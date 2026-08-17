"""Tests for Zoho Analytics schedule lock, job runner skips, and registration gate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.integrations.zoho.types import SyncSkipReason, SyncStatus


@pytest.fixture(autouse=True)
def zoho_flags_off(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "false")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "false")


@pytest.mark.asyncio
async def test_run_zoho_analytics_export_skips_kill_switch(monkeypatch):
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "true")
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "true")
    from job_runner import run_zoho_analytics_export

    result = await run_zoho_analytics_export()
    assert result["status"] == SyncStatus.SKIPPED.value
    assert result["skip_reason"] == SyncSkipReason.KILL_SWITCH.value
    assert result["outcome_status"] == "success"
    assert result["outcome_metrics"]["skipped"] == 1


@pytest.mark.asyncio
async def test_run_zoho_analytics_export_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "false")
    from job_runner import run_zoho_analytics_export

    result = await run_zoho_analytics_export()
    assert result["status"] == SyncStatus.SKIPPED.value
    assert result["skip_reason"] == SyncSkipReason.DISABLED.value
    assert result["outcome_status"] == "success"


@pytest.mark.asyncio
async def test_run_zoho_analytics_export_skips_when_lock_held(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "true")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "false")
    from job_runner import run_zoho_analytics_export

    with patch(
        "services.integrations.zoho.analytics_schedule.acquire_analytics_export_lock",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await run_zoho_analytics_export()
    assert result["skip_reason"] == SyncSkipReason.RUN_LOCK_HELD.value
    assert result["outcome_status"] == "success"


@pytest.mark.asyncio
async def test_run_zoho_analytics_export_no_force_reexport_and_releases_lock(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "true")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "false")
    from job_runner import run_zoho_analytics_export
    from services.integrations.zoho.types import SyncResult

    sync = AsyncMock(
        return_value=SyncResult(
            success=True,
            sync_id="ZSYNC-TEST",
            integration="analytics",
            operation="export_aggregates",
            status=SyncStatus.SKIPPED,
            skip_reason=SyncSkipReason.DUPLICATE_PERIOD,
            message="period_already_exported:prior",
        )
    )
    release = AsyncMock()
    with (
        patch(
            "services.integrations.zoho.analytics_schedule.acquire_analytics_export_lock",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "services.integrations.zoho.analytics_schedule.release_analytics_export_lock",
            release,
        ),
        patch(
            "services.integrations.zoho.service.zoho_integration_service.run_sync",
            sync,
        ),
    ):
        result = await run_zoho_analytics_export()
    assert result["outcome_status"] == "success"
    assert result["outcome_metrics"]["duplicate_skip"] == 1
    assert sync.await_args.args[2] == {"force_reexport": False}
    release.assert_awaited()


@pytest.mark.asyncio
async def test_acquire_lock_insert_and_reject_second(monkeypatch):
    from services.integrations.zoho.analytics_schedule import (
        acquire_analytics_export_lock,
        release_analytics_export_lock,
    )
    from services.integrations.zoho.types import ANALYTICS_EXPORT_LOCK_ID
    from pymongo.errors import DuplicateKeyError

    coll = AsyncMock()
    coll.insert_one = AsyncMock(side_effect=[None, DuplicateKeyError("dup")])
    coll.find_one = AsyncMock(
        return_value={
            "_id": ANALYTICS_EXPORT_LOCK_ID,
            "owner": "first",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
    )
    coll.delete_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=coll)

    with patch(
        "services.integrations.zoho.analytics_schedule.database.get_db",
        return_value=mock_db,
    ):
        assert await acquire_analytics_export_lock("owner-a") is True
        assert await acquire_analytics_export_lock("owner-b") is False
        await release_analytics_export_lock("owner-a")
    coll.delete_one.assert_awaited()


def test_next_daily_run_utc():
    from services.integrations.zoho.analytics_schedule import next_daily_run_utc

    before = datetime(2026, 7, 14, 2, 0, 0, tzinfo=timezone.utc)
    after = datetime(2026, 7, 14, 2, 16, 0, tzinfo=timezone.utc)
    assert next_daily_run_utc(now=before) == datetime(2026, 7, 14, 2, 15, 0, tzinfo=timezone.utc)
    assert next_daily_run_utc(now=after) == datetime(2026, 7, 15, 2, 15, 0, tzinfo=timezone.utc)
