"""Tests for Zoho operational health, versioning, and platform observability hooks."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.integrations.zoho.config import integration_status_snapshot
from services.integrations.zoho.metrics.analytics_export import (
    build_analytics_export,
    resolve_daily_reporting_period,
)
from services.integrations.zoho.operational_health import (
    build_zoho_operational_health_summary,
    build_zoho_operational_snapshot,
)
from services.integrations.zoho.registry import ANALYTICS_EXPORT_METRICS
from services.integrations.zoho.version import (
    ZOHO_INTEGRATION_LAYER_VERSION,
    sync_run_versions,
)
from services.integrations.zoho.sync_store import zoho_sync_store


@pytest.fixture(autouse=True)
def zoho_flags_off(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "false")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_CRM_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_CAMPAIGNS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_SIGN_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_BOOKS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_WORKDRIVE_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "false")


def test_integration_layer_version_on_status_snapshot():
    snap = integration_status_snapshot()
    assert snap["integration_layer_version"] == ZOHO_INTEGRATION_LAYER_VERSION
    assert snap["mapping_version"] == "1.0.0"
    assert "adapters" in snap


def test_analytics_export_metrics_include_total_leads_and_payload_version():
    assert "total_leads_count" in ANALYTICS_EXPORT_METRICS
    assert "export_type" in ANALYTICS_EXPORT_METRICS
    assert "payload_version" in ANALYTICS_EXPORT_METRICS


def test_resolve_daily_reporting_period_is_last_completed_utc_day_and_stable():
    morning = datetime(2026, 7, 13, 9, 15, 30, tzinfo=timezone.utc)
    evening = datetime(2026, 7, 13, 22, 45, 0, tzinfo=timezone.utc)
    start_a, end_a = resolve_daily_reporting_period(morning)
    start_b, end_b = resolve_daily_reporting_period(evening)
    assert start_a == start_b == datetime(2026, 7, 12, 0, 0, 0, tzinfo=timezone.utc)
    assert end_a == end_b == datetime(2026, 7, 13, 0, 0, 0, tzinfo=timezone.utc)
    assert start_a.isoformat() == "2026-07-12T00:00:00+00:00"
    assert end_a.isoformat() == "2026-07-13T00:00:00+00:00"

    next_day = datetime(2026, 7, 14, 1, 0, 0, tzinfo=timezone.utc)
    start_c, end_c = resolve_daily_reporting_period(next_day)
    assert start_c == datetime(2026, 7, 13, 0, 0, 0, tzinfo=timezone.utc)
    assert end_c == datetime(2026, 7, 14, 0, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_build_analytics_export_includes_payload_version():
    mock_leads = AsyncMock()
    mock_leads.count_documents = AsyncMock(side_effect=[1, 0, 5])
    mock_billing = AsyncMock()
    mock_billing.count_documents = AsyncMock(return_value=0)
    agg_cursor = MagicMock()
    agg_cursor.to_list = AsyncMock(return_value=[])
    mock_billing.aggregate = MagicMock(return_value=agg_cursor)
    mock_tickets = AsyncMock()
    mock_tickets.count_documents = AsyncMock(return_value=0)

    mock_db = MagicMock()
    mock_db.leads = mock_leads
    mock_db.client_billing = mock_billing
    mock_db.support_tickets = mock_tickets

    period = (
        datetime(2026, 7, 12, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 13, 0, 0, 0, tzinfo=timezone.utc),
    )
    with (
        patch("services.integrations.zoho.metrics.analytics_export.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.metrics.analytics_export.resolve_daily_reporting_period",
            return_value=period,
        ),
    ):
        export = await build_analytics_export()
    assert export["payload_version"] == 1
    assert export["total_leads_count"] == 5
    assert export["export_type"] == "aggregated_daily"
    assert export["period_start"] == "2026-07-12T00:00:00+00:00"
    assert export["period_end"] == "2026-07-13T00:00:00+00:00"
    assert mock_leads.count_documents.await_args_list[0].args[0] == {
        "created_at": {
            "$gte": "2026-07-12T00:00:00+00:00",
            "$lt": "2026-07-13T00:00:00+00:00",
        }
    }
    assert mock_tickets.count_documents.await_args_list[1].args[0] == {
        "status": "closed",
        "updated_at": {
            "$gte": "2026-07-12T00:00:00+00:00",
            "$lt": "2026-07-13T00:00:00+00:00",
        }
    }


def test_sync_run_versions_block():
    versions = sync_run_versions("crm")
    assert versions["layer"] == ZOHO_INTEGRATION_LAYER_VERSION
    assert versions["adapter"] == "1.0.0"
    assert versions["mapping"] == "1.0.0"
    assert versions["payload"] == 1


@pytest.mark.asyncio
async def test_sync_store_create_run_includes_versions():
    from services.integrations.zoho.types import SyncDirection

    mock_collection = AsyncMock()
    mock_collection.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("services.integrations.zoho.sync_store.database.get_db", return_value=mock_db):
        sync_id = await zoho_sync_store.create_run(
            integration="analytics",
            operation="export_aggregates",
            direction=SyncDirection.OUTBOUND,
        )
        assert sync_id.startswith("ZSYNC-")
        doc = mock_collection.insert_one.call_args[0][0]
        assert doc["versions"]["layer"] == ZOHO_INTEGRATION_LAYER_VERSION
        assert doc["versions"]["adapter"] == "1.0.0"


@pytest.mark.asyncio
async def test_operational_snapshot_dormant_when_disabled():
    mock_runs = AsyncMock()
    mock_runs.find_one = AsyncMock(return_value=None)
    mock_runs.count_documents = AsyncMock(return_value=0)
    mock_queue = AsyncMock()
    mock_queue.count_documents = AsyncMock(return_value=0)
    mock_queue.find_one = AsyncMock(return_value=None)
    mock_dl = AsyncMock()
    mock_dl.count_documents = AsyncMock(return_value=0)
    mock_dl.find_one = AsyncMock(return_value=None)
    mock_oauth = AsyncMock()
    mock_oauth.find_one = AsyncMock(return_value=None)
    mock_audit = AsyncMock()
    mock_audit.find.return_value.limit = MagicMock(return_value=AsyncMock())
    mock_audit.find.return_value.limit.return_value.__aiter__ = lambda self: iter([])

    def _getitem(name):
        mapping = {
            "zoho_sync_runs": mock_runs,
            "zoho_sync_queue": mock_queue,
            "zoho_sync_dead_letter": mock_dl,
            "zoho_oauth_tokens": mock_oauth,
            "audit_logs": mock_audit,
        }
        return mapping.get(name, AsyncMock())

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=_getitem)

    with patch("services.integrations.zoho.operational_health.database.get_db", return_value=mock_db):
        snap = await build_zoho_operational_snapshot()
    assert snap["overall_status"] == "dormant"
    assert snap["zoho_integration_enabled"] is False
    summary = build_zoho_operational_health_summary(snap)
    assert summary["overall_status"] == "dormant"
    assert summary["health_posture"] == "INTEGRATED_WITH_PLATFORM_OBSERVABILITY"


@pytest.mark.asyncio
async def test_health_summary_includes_zoho_integration_health(monkeypatch):
    monkeypatch.setenv("PYTEST_RUNNING", "1")
    from routes.observability import HEALTH_SUMMARY_JOBS, build_health_summary_payload

    jobs_detail = {j: {"last_success": None, "last_completed": None} for j in HEALTH_SUMMARY_JOBS}

    with patch("routes.observability.database.get_db") as gdb, patch(
        "routes.observability._fetch_jobs_detail_for_health_summary", new_callable=AsyncMock
    ) as fj, patch(
        "services.incident_service.count_open_by_severity", new_callable=AsyncMock, return_value=0
    ), patch(
        "services.integrations.zoho.operational_health.build_zoho_operational_snapshot",
        new_callable=AsyncMock,
    ) as zsnap, patch(
        "services.compliance_recalc_operational_snapshot.build_recalc_queue_operational_snapshot",
        new_callable=AsyncMock,
        return_value={},
    ), patch(
        "services.compliance_recalc_operational_snapshot.build_recalc_queue_health_summary",
        return_value={},
    ):
        db = AsyncMock()
        db.scheduler_heartbeat.find_one = AsyncMock(return_value={"last_heartbeat_at": "2026-01-01T00:00:00+00:00"})
        db.job_runs.count_documents = AsyncMock(return_value=0)
        agg_cursor = MagicMock()
        agg_cursor.to_list = AsyncMock(return_value=[])
        db.job_runs.aggregate = MagicMock(return_value=agg_cursor)
        find_cursor = MagicMock()
        find_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
        find_cursor.sort.return_value.to_list = AsyncMock(return_value=[])
        db.job_runs.find = MagicMock(return_value=find_cursor)
        db.incidents.count_documents = AsyncMock(return_value=0)
        gdb.return_value = db
        fj.return_value = jobs_detail
        zsnap.return_value = {
            "overall_status": "dormant",
            "zoho_integration_enabled": False,
            "kill_switch_active": False,
            "queue": {"pending": 0, "processing": 0},
            "dead_letter": {"unresolved": 0},
            "oauth": {"configured": False, "token_valid": False},
            "webhooks_24h": {"accepted": 0, "rejected": 0},
            "circuit_breakers": {},
            "versions": {"integration_layer_version": ZOHO_INTEGRATION_LAYER_VERSION},
            "admin_path": "/api/admin/integrations/zoho/status",
        }
        payload = await build_health_summary_payload()
    assert "zoho_integration_health" in payload
    assert payload["integrations"]["zoho"]["overall_status"] == "dormant"
