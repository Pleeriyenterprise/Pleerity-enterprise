"""ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01 — extension tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.admin_customer_operations_centre_service import (
    build_customer_health_summary,
    build_health_indicators,
    build_support_bundle_payload,
    support_bundle_zip_bytes,
)


def test_health_summary_critical_when_webhooks_failed():
    indicators = build_health_indicators(
        contract={"lifecycle_state": "ACTIVE", "portal_mode": "FULL_ACCESS", "capabilities": {"CAP_X": "ALLOW"}},
        billing={"stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"},
        client={},
        failed_webhook_count=2,
        background_summary={"paused_count": 0, "terminated_count": 0},
        communications_summary={"suppressed_channels": [], "last_sent_at": None},
        drift_flags=[],
        now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    summary = build_customer_health_summary(indicators)
    assert summary["overall"] == "Critical"
    assert indicators["webhook_processing"]["status"] == "critical"


def test_health_summary_healthy_active():
    indicators = build_health_indicators(
        contract={"lifecycle_state": "ACTIVE", "portal_mode": "FULL_ACCESS", "runtime_version": 42, "capabilities": {"CAP_X": "ALLOW"}},
        billing={
            "stripe_subscription_id": "sub_1",
            "stripe_customer_id": "cus_1",
            "stripe_mode": "test",
            "stripe_webhook_last_received_at": "2026-07-09T10:00:00+00:00",
        },
        client={},
        failed_webhook_count=0,
        background_summary={"paused_count": 0, "terminated_count": 0},
        communications_summary={"suppressed_channels": [], "last_sent_at": "2026-07-09T09:00:00+00:00"},
        drift_flags=[],
        now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    summary = build_customer_health_summary(indicators)
    assert summary["overall"] == "Healthy"


def test_support_bundle_zip_no_secrets():
    snapshot = {
        "client_id": "c1",
        "generated_at": "2026-07-09T10:00:00Z",
        "customer_health": {"overall": "Healthy"},
        "lifecycle": {"lifecycle_state": "ACTIVE"},
        "billing": {"stripe_customer_id": "cus_x"},
        "actions": {},
    }
    client = {"email": "test@example.com", "password": "secret-should-redact"}
    files = build_support_bundle_payload(snapshot, client)
    assert "README.txt" in files
    assert "secret-should-redact" not in files["customer_summary.json"]
    blob = support_bundle_zip_bytes(snapshot, client)
    assert len(blob) > 100


@pytest.mark.asyncio
async def test_export_support_bundle_route_audited():
    from routes import admin_lifecycle_operations as routes

    user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}
    req = MagicMock()
    req.headers = {}
    with patch.object(routes, "admin_route_guard", new=AsyncMock(return_value=user)):
        with patch.object(routes, "enforce_governed_admin_action", new=AsyncMock()):
            with patch.object(
                routes,
                "build_support_bundle_for_client",
                new=AsyncMock(return_value=({"customer_health": {"overall": "Healthy"}}, b"PK\x03\x04")),
            ):
                with patch.object(routes, "create_audit_log", new=AsyncMock()) as audit:
                    body = routes.LifecycleOpsReasonBody(reason="Export for billing escalation review")
                    resp = await routes.post_export_support_bundle(req, "client-1", body)
    assert resp.media_type == "application/zip"
    audit.assert_awaited_once()
