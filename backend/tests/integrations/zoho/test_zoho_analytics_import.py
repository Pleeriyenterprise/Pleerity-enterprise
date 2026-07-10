"""Tests for Zoho Analytics existing-table import targeting (API V2)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.integrations.zoho.adapters.analytics import (
    ANALYTICS_AGGREGATE_TABLE_NAME,
    ZohoAnalyticsAdapter,
    build_analytics_existing_table_import_path,
    build_analytics_import_config,
    build_analytics_import_data_string,
    resolve_analytics_import_target,
)
from services.integrations.zoho.types import SyncSkipReason, SyncStatus


@pytest.fixture(autouse=True)
def zoho_flags_off(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "false")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "false")


def test_existing_table_path_includes_restapi_and_view_id():
    path = build_analytics_existing_table_import_path("272205000000016002", "999000000000001")
    assert path == "/restapi/v2/workspaces/272205000000016002/views/999000000000001/data"
    assert "/analytics/v2/" not in path


def test_import_config_is_append_json():
    config = build_analytics_import_config()
    assert config == {
        "importType": "append",
        "fileType": "json",
        "autoIdentify": "true",
    }


def test_import_data_string_is_json_array():
    row = {"payload_version": 1, "export_type": "aggregated_daily"}
    raw = build_analytics_import_data_string(row)
    parsed = json.loads(raw)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["export_type"] == "aggregated_daily"


def test_resolve_target_requires_view_and_org(monkeypatch):
    monkeypatch.setenv("ZOHO_ANALYTICS_WORKSPACE_ID", "272205000000016002")
    monkeypatch.delenv("ZOHO_ANALYTICS_VIEW_ID", raising=False)
    monkeypatch.delenv("ZOHO_ANALYTICS_ORG_ID", raising=False)
    monkeypatch.delenv("ZOHO_ORG_ID", raising=False)
    url, org, missing = resolve_analytics_import_target()
    assert url is None
    assert "ZOHO_ANALYTICS_VIEW_ID" in missing
    assert "ZOHO_ANALYTICS_ORG_ID" in missing


def test_resolve_target_builds_eu_analytics_url(monkeypatch):
    monkeypatch.setenv("ZOHO_ANALYTICS_WORKSPACE_ID", "272205000000016002")
    monkeypatch.setenv("ZOHO_ANALYTICS_VIEW_ID", "111222333")
    monkeypatch.setenv("ZOHO_ANALYTICS_ORG_ID", "555666")
    monkeypatch.delenv("ZOHO_ANALYTICS_API_BASE", raising=False)
    url, org, missing = resolve_analytics_import_target()
    assert missing == []
    assert org == "555666"
    assert url == (
        "https://analyticsapi.zoho.eu/restapi/v2/workspaces/"
        "272205000000016002/views/111222333/data"
    )


@pytest.mark.asyncio
async def test_adapter_skips_when_view_id_missing(monkeypatch):
    monkeypatch.setenv("ZOHO_ANALYTICS_WORKSPACE_ID", "272205000000016002")
    monkeypatch.delenv("ZOHO_ANALYTICS_VIEW_ID", raising=False)
    monkeypatch.setenv("ZOHO_ANALYTICS_ORG_ID", "555")
    adapter = ZohoAnalyticsAdapter()
    result = await adapter.execute(
        "export_aggregates",
        {"sync_id": "ZSYNC-1", "export_data": {"payload_version": 1, "export_type": "aggregated_daily"}},
    )
    assert result.status == SyncStatus.SKIPPED
    assert result.skip_reason == SyncSkipReason.NO_CREDENTIALS
    assert "ZOHO_ANALYTICS_VIEW_ID" in (result.metadata or {}).get("missing_config", [])


@pytest.mark.asyncio
async def test_adapter_posts_existing_table_import(monkeypatch):
    monkeypatch.setenv("ZOHO_ANALYTICS_WORKSPACE_ID", "272205000000016002")
    monkeypatch.setenv("ZOHO_ANALYTICS_VIEW_ID", "111222333")
    monkeypatch.setenv("ZOHO_ANALYTICS_ORG_ID", "555666")
    export_row = {
        "payload_version": 1,
        "period_start": "2026-07-09T00:00:00+00:00",
        "period_end": "2026-07-10T00:00:00+00:00",
        "leads_created_count": 1,
        "leads_converted_count": 0,
        "total_leads_count": 1,
        "conversion_rate_pct": 0.0,
        "active_subscriptions_count": 0,
        "mrr_summary_gbp": 0.0,
        "support_tickets_open_count": 0,
        "support_tickets_closed_count": 0,
        "export_type": "aggregated_daily",
    }
    adapter = ZohoAnalyticsAdapter()
    with patch(
        "services.integrations.zoho.adapters.analytics.zoho_http_client.request",
        new_callable=AsyncMock,
        return_value=(True, {"status": "success"}, None),
    ) as req:
        result = await adapter.execute(
            "export_aggregates",
            {"sync_id": "ZSYNC-2", "export_data": export_row},
        )
    assert result.status == SyncStatus.SUCCESS
    assert result.message == "analytics_export_delivered"
    kwargs = req.await_args.kwargs
    assert req.await_args.args[0] == "POST"
    assert req.await_args.args[1] == (
        "/restapi/v2/workspaces/272205000000016002/views/111222333/data"
    )
    assert kwargs["api_base"] == "https://analyticsapi.zoho.eu"
    assert kwargs["headers"]["ZANALYTICS-ORGID"] == "555666"
    assert json.loads(kwargs["params"]["CONFIG"])["importType"] == "append"
    assert json.loads(kwargs["form_data"]["DATA"]) == [export_row]
    assert (result.metadata or {}).get("table_name") == ANALYTICS_AGGREGATE_TABLE_NAME
    assert (result.metadata or {}).get("import_type") == "append"
