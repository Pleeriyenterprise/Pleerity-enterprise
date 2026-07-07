"""Security IP block behaviour — portal retry storms must not lock out signed-in users."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
STAGING_PREVIEW_ORIGIN = "https://pleerity-enterprise-9jjg.vercel.app"


def test_security_gate_skips_ip_block_for_valid_bearer():
    text = (BACKEND_ROOT / "server.py").read_text(encoding="utf-8")
    assert "def _request_has_valid_bearer(request: Request)" in text
    block = text.split("async def _security_monitoring_gate")[1].split("async def _readiness_gate_call_next")[0]
    assert "not _request_has_valid_bearer(request)" in block


def test_endpoint_probing_counts_only_http_404():
    text = (BACKEND_ROOT / "services" / "security_monitoring_service.py").read_text(encoding="utf-8")
    section = text.split("# Endpoint probing")[1].split("# Admin route request spike")[0]
    assert 'event_type == "http.404"' in section
    assert '"http.403"' not in section
    assert '"http.401"' not in section


def test_staging_startup_clears_active_ip_blocks():
    text = (BACKEND_ROOT / "server.py").read_text(encoding="utf-8")
    startup = text.split("async def _heavy_startup")[1].split("if True:")[0]
    assert "resolve_deployment_tier" in startup
    assert "clear_all_ip_blocks" in startup


def test_options_preflight_not_blocked_when_ip_is_blocked():
    from server import app

    with patch(
        "services.security_monitoring_service.should_block_ip",
        new=AsyncMock(return_value=True),
    ), patch(
        "services.security_monitoring_service.record_security_event",
        new=AsyncMock(return_value=None),
    ):
        client = TestClient(app)
        resp = client.options(
            "/api/auth/login",
            headers={
                "Origin": STAGING_PREVIEW_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("access-control-allow-origin") == STAGING_PREVIEW_ORIGIN

        post = client.post(
            "/api/auth/login",
            headers={"Origin": STAGING_PREVIEW_ORIGIN},
            json={"email": "probe@example.com", "password": "wrong"},
        )
        assert post.status_code == 429
