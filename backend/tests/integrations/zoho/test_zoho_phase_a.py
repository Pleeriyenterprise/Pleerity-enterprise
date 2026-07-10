"""Phase A sandbox pilot — runtime and operational validation tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from routes.integrations.zoho import admin as zoho_admin
from routes.integrations.zoho import webhooks as zoho_webhooks
from services.integrations.zoho.config import integration_status_snapshot, zoho_integration_enabled
from services.integrations.zoho.credential_resolver import resolve_oauth_credentials
from services.integrations.zoho.events import maybe_enqueue_crm_sync
from services.integrations.zoho.operational_health import (
    build_zoho_operational_health_summary,
    build_zoho_operational_snapshot,
)
from services.integrations.zoho.service import ZohoIntegrationService
from services.integrations.zoho.types import SyncSkipReason, SyncStatus


@pytest.fixture
def phase_a_env(monkeypatch):
    """Phase A: master enabled, all integration flags disabled."""
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "false")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_CRM_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_CAMPAIGNS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED", "false")
    monkeypatch.setenv("ZOHO_SIGN_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_BOOKS_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_WORKDRIVE_SYNC_ENABLED", "false")
    monkeypatch.setenv("ZOHO_ENVIRONMENT", "staging")


def _mock_db():
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
        return {
            "zoho_sync_runs": mock_runs,
            "zoho_sync_queue": mock_queue,
            "zoho_sync_dead_letter": mock_dl,
            "zoho_oauth_tokens": mock_oauth,
            "audit_logs": mock_audit,
        }.get(name, AsyncMock())

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=_getitem)
    return mock_db


def test_phase_a_master_enabled_integration_flags_off(phase_a_env):
    assert zoho_integration_enabled() is True
    snap = integration_status_snapshot()
    assert snap["zoho_integration_enabled"] is True
    assert snap["kill_switch_active"] is False
    assert all(v is False for v in snap["integrations"].values())
    assert snap["integration_layer_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_phase_a_operational_snapshot_healthy_with_no_credentials(phase_a_env, monkeypatch):
    mock_db = _mock_db()
    with patch("services.integrations.zoho.operational_health.database.get_db", return_value=mock_db):
        snap = await build_zoho_operational_snapshot()
    assert snap["overall_status"] == "healthy"
    assert snap["zoho_integration_enabled"] is True
    for name, row in snap["integrations"].items():
        assert row["enabled"] is False
    summary = build_zoho_operational_health_summary(snap)
    assert summary["overall_status"] == "healthy"
    assert summary["oauth_integrations_configured"] == []


@pytest.mark.asyncio
async def test_phase_a_no_sync_when_integration_disabled(phase_a_env):
    svc = ZohoIntegrationService()
    result = await svc.run_sync("analytics", "export_aggregates", {})
    assert result.status == SyncStatus.SKIPPED
    assert result.skip_reason == SyncSkipReason.DISABLED


@pytest.mark.asyncio
async def test_phase_a_enqueue_crm_noop(phase_a_env):
    await maybe_enqueue_crm_sync("LEAD-1", "lead.created")


@pytest.mark.asyncio
async def test_phase_a_manual_sync_skipped_not_outbound(phase_a_env):
    svc = ZohoIntegrationService()
    with patch("services.integrations.zoho.client.zoho_http_client.request", new_callable=AsyncMock) as req:
        result = await svc.run_sync("crm", "upsert_lead", {"lead_id": "L1"})
        req.assert_not_called()
    assert result.skip_reason == SyncSkipReason.DISABLED


@pytest.mark.asyncio
async def test_phase_a_oauth_exposes_per_integration_status(phase_a_env, monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    snap = integration_status_snapshot()
    assert snap["shared_oauth_client_configured"] is True
    assert "oauth_by_integration" in snap
    assert snap["oauth_by_integration"]["crm"]["refresh_token_source"] == "none"


def test_phase_a_partial_credentials_client_only(phase_a_env, monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
    resolved = resolve_oauth_credentials("crm")
    assert resolved is not None
    assert resolved.shared_client_configured is False
    assert resolved.credentials_configured is False


def test_phase_a_complete_credentials_without_refresh(phase_a_env, monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    resolved = resolve_oauth_credentials("analytics")
    assert resolved is not None
    assert resolved.shared_client_configured is True
    assert resolved.refresh_token_configured is False
    assert resolved.credentials_configured is False


@pytest.mark.asyncio
async def test_phase_a_webhook_route_available_master_on_integration_off(phase_a_env):
    app = FastAPI()
    app.include_router(zoho_webhooks.router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/internal/integrations/zoho/webhooks/sign", json={})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_phase_a_admin_status_requires_master_flag(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "false")
    app = FastAPI()
    app.include_router(zoho_admin.router)

    async def _admin(_user=None):
        return {"user_id": "admin-1"}

    app.dependency_overrides[zoho_admin.admin_route_guard] = _admin
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/admin/integrations/zoho/status")
    assert res.status_code == 404
