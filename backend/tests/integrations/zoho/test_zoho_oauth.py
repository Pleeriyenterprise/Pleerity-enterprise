"""Regression tests for Zoho OAuth Option B architecture."""
from __future__ import annotations

import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.integrations.zoho.config import (
    integration_status_snapshot,
    zoho_credentials_configured,
    zoho_oauth_configured_for,
)
from services.integrations.zoho.credential_resolver import (
    RefreshTokenSource,
    reset_legacy_warning_cache_for_tests,
    resolve_oauth_credentials,
)
from services.integrations.zoho.oauth import zoho_oauth_manager
from services.integrations.zoho.oauth_credential_registry import (
    OAUTH_INTEGRATION_REGISTRY,
    registry_snapshot,
)
from services.integrations.zoho.operational_health import build_zoho_operational_snapshot


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
    reset_legacy_warning_cache_for_tests()


def test_registry_contains_all_oauth_integrations():
    assert set(OAUTH_INTEGRATION_REGISTRY.keys()) == {
        "analytics",
        "crm",
        "campaigns",
        "books",
        "workdrive",
    }
    snap = registry_snapshot()
    assert snap["crm"]["cache_identifier"] == "zoho_oauth_access_token_crm"
    assert snap["sign"]["requires_oauth"] is False


def test_credential_resolver_prefers_per_integration_token(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "legacy")
    monkeypatch.setenv("ZOHO_CRM_REFRESH_TOKEN", "crm-token")

    resolved = resolve_oauth_credentials("crm")
    assert resolved is not None
    assert resolved.refresh_token == "crm-token"
    assert resolved.refresh_token_source == RefreshTokenSource.PER_INTEGRATION
    assert resolved.cache_identifier == "zoho_oauth_access_token_crm"
    assert resolved.credentials_configured is True


def test_credential_resolver_legacy_fallback(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "legacy")

    resolved = resolve_oauth_credentials("crm")
    assert resolved is not None
    assert resolved.refresh_token == "legacy"
    assert resolved.refresh_token_source == RefreshTokenSource.LEGACY


def test_credential_resolver_no_credentials(monkeypatch):
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_CRM_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")

    resolved = resolve_oauth_credentials("crm")
    assert resolved is not None
    assert resolved.refresh_token_source == RefreshTokenSource.NONE
    assert resolved.credentials_configured is False


def test_legacy_warning_for_non_crm_integration(monkeypatch, caplog):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "legacy")

    with caplog.at_level(logging.WARNING):
        resolve_oauth_credentials("analytics")
        resolve_oauth_credentials("analytics")

    assert "deprecated legacy ZOHO_REFRESH_TOKEN" in caplog.text
    assert caplog.text.count("integration 'analytics'") == 1


def test_no_legacy_warning_for_crm_migration(monkeypatch, caplog):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "legacy")

    with caplog.at_level(logging.WARNING):
        resolve_oauth_credentials("crm")

    assert "deprecated legacy ZOHO_REFRESH_TOKEN" not in caplog.text


def test_zoho_oauth_configured_for_per_integration(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_ANALYTICS_REFRESH_TOKEN", "analytics-token")

    assert zoho_oauth_configured_for("analytics") is True
    assert zoho_oauth_configured_for("books") is False
    assert zoho_credentials_configured() is True


def test_integration_status_snapshot_oauth_by_integration(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_BOOKS_REFRESH_TOKEN", "books-token")

    snap = integration_status_snapshot()
    assert snap["shared_oauth_client_configured"] is True
    assert snap["oauth_by_integration"]["books"]["refresh_token_source"] == "per_integration"
    assert snap["oauth_by_integration"]["crm"]["refresh_token_source"] == "none"


@pytest.mark.asyncio
async def test_oauth_cache_isolation_per_integration(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_CRM_REFRESH_TOKEN", "crm-token")
    monkeypatch.setenv("ZOHO_ANALYTICS_REFRESH_TOKEN", "analytics-token")
    monkeypatch.setenv("ZOHO_ENVIRONMENT", "staging")

    stored: dict = {}

    async def _update_one(query, update, upsert=False):
        token_id = query["token_id"]
        stored[token_id] = {
            **query,
            **update.get("$set", {}),
        }
        return MagicMock(modified_count=1)

    async def _find_one(query, projection=None):
        return stored.get(query["token_id"])

    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(side_effect=_update_one)
    mock_collection.find_one = AsyncMock(side_effect=_find_one)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("services.integrations.zoho.oauth.database.get_db", return_value=mock_db), patch(
        "services.integrations.zoho.oauth.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "access-1", "expires_in": 3600}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        crm_token = await zoho_oauth_manager.get_access_token("crm")
        assert crm_token == "access-1"
        assert "zoho_oauth_access_token_crm" in stored

        mock_response.json.return_value = {"access_token": "access-2", "expires_in": 3600}
        analytics_token = await zoho_oauth_manager.get_access_token("analytics")
        assert analytics_token == "access-2"
        assert stored["zoho_oauth_access_token_crm"]["access_token"] == "access-1"
        assert stored["zoho_oauth_access_token_analytics"]["access_token"] == "access-2"


@pytest.mark.asyncio
async def test_operational_snapshot_per_integration_oauth(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_CRM_REFRESH_TOKEN", "crm-token")

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
    mock_oauth.find_one = AsyncMock(
        return_value={
            "expires_at": time.time() + 3600,
            "updated_at": "2026-07-10T00:00:00+00:00",
            "last_successful_refresh_at": "2026-07-10T00:00:00+00:00",
            "last_validation_at": "2026-07-10T00:00:00+00:00",
            "auth_failure_count": 0,
        }
    )
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

    crm_oauth = snap["oauth"]["by_integration"]["crm"]
    assert crm_oauth["credentials_configured"] is True
    assert crm_oauth["refresh_token_source"] == "per_integration"
    assert crm_oauth["expected_scope"].startswith("ZohoCRM")
    assert crm_oauth["oauth_status"] == "healthy"
    assert "credential_registry" in snap["oauth"]


@pytest.mark.asyncio
async def test_http_client_passes_integration_to_oauth_manager():
    from services.integrations.zoho.client import zoho_http_client

    with patch(
        "services.integrations.zoho.client.zoho_oauth_manager.get_access_token",
        new_callable=AsyncMock,
        return_value=None,
    ) as get_token:
        ok, _, err = await zoho_http_client.request("GET", "/crm/v6/Leads", integration="crm")
        get_token.assert_awaited_once_with("crm")
        assert ok is False
        assert err == "no_access_token"
