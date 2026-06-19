"""
Stage Y — Twin webhook ingestion connector tests.

No network calls in default unit tests.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from routes import discovery_twin_internal
from services.discovery.twin.twin_run_event_extractor import (
    extract_export_from_events,
    summarize_events_for_capture,
)
from services.discovery.twin.twin_webhook_verifier import (
    TwinWebhookVerificationError,
    verify_webhook_signature,
)


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


SAMPLE_WEBHOOK = {
    "event": "run.completed",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "data": {
        "run_id": "run_test_001",
        "agent_id": "agent_test_001",
        "status": "completed",
        "outcome": "success",
        "finished_at": "2026-06-19T12:00:00Z",
    },
}

SAMPLE_EVENTS = [
    {"index": 1, "event": {"started": {}}},
    {
        "index": 2,
        "event": {
            "output": {
                "export_id": "exp-1",
                "records": [
                    {
                        "twin_id": "twin-1",
                        "company_name": "Test Co",
                        "source_url": "https://example.com",
                        "confidence_score": 80,
                        "country": "GB",
                        "lawful_basis": "consent",
                    }
                ],
            }
        },
    },
]


@pytest.fixture
def twin_app():
    app = FastAPI()
    app.include_router(discovery_twin_internal.router)
    return app


def test_signature_verify_valid():
    secret = "whsec_test"
    body = b'{"event":"run.completed"}'
    verify_webhook_signature(
        signing_secret=secret,
        raw_body=body,
        signature_header=_sign(body, secret),
    )


def test_signature_verify_invalid():
    with pytest.raises(TwinWebhookVerificationError):
        verify_webhook_signature(
            signing_secret="whsec_test",
            raw_body=b"{}",
            signature_header="sha256=deadbeef",
        )


def test_summarize_events():
    summary = summarize_events_for_capture(SAMPLE_EVENTS)
    assert summary["event_count"] == 2
    assert "output" in summary["top_level_event_keys"] or any(
        "output" in str(s) for s in summary["summaries"]
    )


def test_extract_deferred_by_default(monkeypatch):
    monkeypatch.delenv("DISCOVERY_TWIN_EXPORT_EXTRACTION_ENABLED", raising=False)
    payload, diag = extract_export_from_events(
        SAMPLE_EVENTS,
        twin_run_id="run_test_001",
        twin_agent_id="agent_test_001",
    )
    assert payload is None
    assert diag["extraction_status"] == "deferred"
    assert diag["records_candidates"]


def test_extract_when_enabled(monkeypatch):
    monkeypatch.setenv("DISCOVERY_TWIN_EXPORT_EXTRACTION_ENABLED", "true")
    payload, diag = extract_export_from_events(
        SAMPLE_EVENTS,
        twin_run_id="run_test_001",
        twin_agent_id="agent_test_001",
    )
    assert payload is not None
    assert len(payload["records"]) == 1
    assert diag["extraction_status"] == "extracted"


@pytest.mark.asyncio
async def test_webhook_endpoint_disabled_returns_404(twin_app):
    with patch(
        "routes.discovery_twin_internal.TwinIngestionConnector.connector_enabled",
        return_value=False,
    ):
        transport = ASGITransport(app=twin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/internal/discovery/twin/webhooks", json=SAMPLE_WEBHOOK)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_capture_only_happy_path(twin_app, monkeypatch):
    secret = "whsec_stage_y"
    monkeypatch.setenv("TWIN_WEBHOOK_SIGNING_SECRET", secret)
    monkeypatch.setenv("TWIN_API_KEY", "tw_test_key")
    monkeypatch.setenv("TWIN_DISCOVERY_AGENT_ID", "agent_test_001")
    monkeypatch.setenv("DISCOVERY_TWIN_EVENT_CAPTURE_ONLY", "true")

    body = json.dumps(SAMPLE_WEBHOOK).encode()

    with patch(
        "routes.discovery_twin_internal.TwinIngestionConnector.connector_enabled",
        return_value=True,
    ), patch(
        "services.discovery.twin.twin_ingestion_connector.TwinIngestionConnector.connector_enabled",
        return_value=True,
    ), patch(
        "services.discovery.twin.twin_ingestion_connector.discovery_config.is_discovery_twin_event_capture_only",
        return_value=True,
    ), patch(
        "services.discovery.twin.twin_api_client.TwinApiClient.get_run",
        new_callable=AsyncMock,
        return_value={"run_id": "run_test_001", "status": "finished"},
    ), patch(
        "services.discovery.twin.twin_api_client.TwinApiClient.list_run_events",
        new_callable=AsyncMock,
        return_value=SAMPLE_EVENTS,
    ), patch(
        "services.discovery.twin.twin_webhook_receipt_service.TwinWebhookReceiptService.create_receipt",
        new_callable=AsyncMock,
        return_value={
            "receipt_id": "DTWR-TEST",
            "status": "received",
            "twin_agent_id": "agent_test_001",
            "twin_run_id": "run_test_001",
            "event": "run.completed",
        },
    ), patch(
        "services.discovery.twin.twin_webhook_receipt_service.TwinWebhookReceiptService.update_receipt",
        new_callable=AsyncMock,
        return_value={},
    ), patch(
        "services.discovery.twin.twin_event_capture_service.TwinEventCaptureService.capture_run_events",
        new_callable=AsyncMock,
        return_value={
            "capture_id": "DTCE-TEST",
            "event_count": 2,
        },
    ):
        transport = ASGITransport(app=twin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/internal/discovery/twin/webhooks",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Cobb-Signature": _sign(body, secret),
                    "X-Cobb-Event": "run.completed",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "captured"
    assert data["capture_id"] == "DTCE-TEST"
    assert data["capture_only"] is True


def test_connector_module_boundary_no_forbidden_imports():
    import ast
    import services.discovery.twin.twin_ingestion_connector as mod

    tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.split(".")[0])

    for forbidden in (
        "LeadService",
        "DiscoveryImportService",
        "DiscoveryApprovalQueueService",
        "leads",
    ):
        assert forbidden not in imported_names
