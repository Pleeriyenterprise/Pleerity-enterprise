"""
Zoho integration tests — authority boundaries, flags, webhooks, sync layer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from routes.integrations.zoho import admin as zoho_admin
from routes.integrations.zoho import webhooks as zoho_webhooks
from services.integrations.zoho.adapters.books import ZohoBooksAdapter
from services.integrations.zoho.adapters.crm import ZohoCrmAdapter
from services.integrations.zoho.adapters.sign import ZohoSignAdapter
from services.integrations.zoho.adapters.workdrive import ZohoWorkdriveAdapter
from services.integrations.zoho.config import (
    integration_status_snapshot,
    zoho_analytics_sync_enabled,
    zoho_crm_sync_enabled,
    zoho_integration_enabled,
)
from services.integrations.zoho.pii import is_aggregate_export_safe, strip_pii_from_dict
from services.integrations.zoho.registry import validate_inbound_crm_fields
from services.integrations.zoho.service import ZohoIntegrationService
from services.integrations.zoho.types import SyncStatus
from services.integrations.zoho.webhooks.verifier import (
    ZohoWebhookVerificationError,
    verify_zoho_webhook_signature,
)


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


def test_feature_flags_default_disabled():
    assert zoho_integration_enabled() is False
    assert zoho_analytics_sync_enabled() is False
    assert zoho_crm_sync_enabled() is False
    snap = integration_status_snapshot()
    assert snap["zoho_integration_enabled"] is False
    assert snap["integration_layer_version"] == "1.0.0"
    assert all(v is False for v in snap["integrations"].values())


def test_kill_switch_disables_integrations(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "true")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "true")
    assert zoho_analytics_sync_enabled() is False


def test_pii_minimisation():
    data = {"email": "a@b.com", "leads_created_count": 5}
    stripped = strip_pii_from_dict(data)
    assert "email" not in stripped
    assert stripped["leads_created_count"] == 5
    assert is_aggregate_export_safe(stripped) is True
    assert is_aggregate_export_safe({"email": "x@y.com"}) is False


def test_crm_inbound_authority_blocked():
    blocked = validate_inbound_crm_fields({"Email": "x@y.com", "Lead_Status": "Qualified"})
    assert blocked


@pytest.mark.asyncio
async def test_sync_disabled_skips():
    svc = ZohoIntegrationService()
    result = await svc.run_sync("analytics", "export_aggregates", {})
    assert result.status == SyncStatus.SKIPPED


@pytest.mark.asyncio
async def test_books_cannot_touch_client_billing():
    adapter = ZohoBooksAdapter()
    err = adapter.authority_check_outbound({"collection": "client_billing"})
    assert err == "books_cannot_touch_client_billing"
    result = await adapter.execute("inbound_rejected", {"sync_id": "t1"})
    assert result.success is False
    assert "inbound" in result.message


@pytest.mark.asyncio
async def test_workdrive_rejects_compliance_evidence():
    adapter = ZohoWorkdriveAdapter()
    result = await adapter.execute(
        "archive_document",
        {"sync_id": "t1", "category": "compliance_evidence", "document_name": "cert.pdf"},
    )
    assert result.success is False
    assert "forbidden" in result.message


@pytest.mark.asyncio
async def test_sign_rejects_subscription_clickwrap():
    adapter = ZohoSignAdapter()
    result = await adapter.execute(
        "process_completion",
        {"sync_id": "t1", "category": "subscription_clickwrap"},
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_sign_allows_b2b():
    adapter = ZohoSignAdapter()
    result = await adapter.execute(
        "process_completion",
        {"sync_id": "t1", "category": "vendor", "request_id": "req-1"},
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_crm_one_way_inbound_rejected():
    adapter = ZohoCrmAdapter()
    result = await adapter.execute(
        "inbound_rejected",
        {"sync_id": "t1", "fields": {"email": "new@lead.com"}},
    )
    assert result.success is False
    assert "inbound_authority_denied" in result.message


def test_webhook_verification_rejects_invalid():
    body = b'{"event":"test"}'
    with pytest.raises(ZohoWebhookVerificationError):
        verify_zoho_webhook_signature(body, "bad", "secret")


def test_webhook_verification_accepts_valid():
    body = b'{"event":"test"}'
    secret = "testsecret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verify_zoho_webhook_signature(body, f"sha256={sig}", secret)


@pytest.mark.asyncio
async def test_admin_routes_404_when_disabled():
    app = FastAPI()
    app.include_router(zoho_admin.router)

    async def _mock_guard():
        return {"user_id": "admin1"}

    app.dependency_overrides[zoho_admin.admin_route_guard] = _mock_guard

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/admin/integrations/zoho/status")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_webhook_routes_404_when_disabled():
    app = FastAPI()
    app.include_router(zoho_webhooks.router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/internal/integrations/zoho/webhooks/crm", json={})
        assert res.status_code == 404
        res = await client.post("/api/internal/integrations/zoho/webhooks/books", json={})
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_books_webhook_requires_hmac_when_enabled(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    app = FastAPI()
    app.include_router(zoho_webhooks.router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/internal/integrations/zoho/webhooks/books",
            json={"event": "invoice.created"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_books_webhook_verifies_and_rejects_inbound(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_BOOKS_WEBHOOK_SECRET", "books-secret")
    body = b'{"event":"invoice.created"}'
    sig = hmac.new(b"books-secret", body, hashlib.sha256).hexdigest()

    app = FastAPI()
    app.include_router(zoho_webhooks.router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "services.integrations.zoho.webhooks.handlers.log_zoho_webhook_event",
            new_callable=AsyncMock,
        ):
            res = await client.post(
                "/api/internal/integrations/zoho/webhooks/books",
                content=body,
                headers={"X-Zoho-Signature": f"sha256={sig}", "Content-Type": "application/json"},
            )
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is False
    assert data["reason"] == "books_inbound_forbidden"
    assert "inbound" in data["message"]


@pytest.mark.asyncio
async def test_sync_creates_audit_and_dead_letter_on_failure(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_ANALYTICS_SYNC_ENABLED", "true")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ZOHO_ANALYTICS_REFRESH_TOKEN", "ref")

    svc = ZohoIntegrationService()

    with patch(
        "services.integrations.zoho.service.zoho_sync_store.create_run",
        new_callable=AsyncMock,
        return_value="ZSYNC-TEST",
    ), patch(
        "services.integrations.zoho.service.zoho_sync_store.mark_running",
        new_callable=AsyncMock,
    ), patch(
        "services.integrations.zoho.service.zoho_sync_store.add_dead_letter",
        new_callable=AsyncMock,
        return_value="ZDL-TEST",
    ), patch(
        "services.integrations.zoho.service.get_adapter"
    ) as ga, patch(
        "services.integrations.zoho.service.log_zoho_sync_event", new_callable=AsyncMock
    ) as audit:
        ga.return_value = MagicMock()
        ga.return_value.authority_check_outbound.return_value = None
        ga.return_value.execute = AsyncMock(side_effect=RuntimeError("api down"))

        result = await svc.run_sync("analytics", "export_aggregates", {})
        assert result.status == SyncStatus.DEAD_LETTER
        assert audit.called


@pytest.mark.asyncio
async def test_enqueue_crm_noop_when_disabled():
    from services.integrations.zoho.events import maybe_enqueue_crm_sync

    await maybe_enqueue_crm_sync("LEAD-1", "lead.created")


@pytest.mark.asyncio
async def test_campaigns_requires_kit_gap_flag(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_CAMPAIGNS_SYNC_ENABLED", "true")
    monkeypatch.setenv("ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED", "false")
    from services.integrations.zoho.config import zoho_campaigns_sync_enabled

    assert zoho_campaigns_sync_enabled() is False
