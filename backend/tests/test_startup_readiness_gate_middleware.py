"""Tests for startup readiness gate and Starlette BaseHTTPMiddleware no-response handling."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.responses import JSONResponse

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def _json_response_data(resp):
    raw = getattr(resp, "body", None)
    assert raw is not None, "expected concrete body on Response"
    return json.loads(raw.decode("utf-8"))


@pytest.mark.asyncio
async def test_readiness_gate_call_next_passes_through_normal_response():
    from server import _readiness_gate_call_next

    req = MagicMock()
    req.url.path = "/api/version"
    req.method = "GET"
    req.state = MagicMock()
    req.state.correlation_id = "cid-ok"

    async def call_next(_r):
        return JSONResponse({"ok": True})

    out = await _readiness_gate_call_next(req, call_next)
    assert out.status_code == 200
    data = _json_response_data(out)
    assert data == {"ok": True}


@pytest.mark.asyncio
async def test_readiness_gate_call_next_other_runtimeerror_reraises():
    from server import _readiness_gate_call_next

    req = MagicMock()
    req.state = MagicMock()

    async def call_next(_r):
        raise RuntimeError("unrelated failure")

    with pytest.raises(RuntimeError, match="unrelated failure"):
        await _readiness_gate_call_next(req, call_next)


@pytest.mark.asyncio
async def test_readiness_gate_call_next_no_response_client_disconnect_499():
    from server import _readiness_gate_call_next

    req = MagicMock()
    req.url.path = "/api/client/tasks"
    req.method = "GET"
    req.state = MagicMock()
    req.state.correlation_id = "cid-disc"
    req.is_disconnected = AsyncMock(return_value=True)

    async def call_next(_r):
        raise RuntimeError("No response returned.")

    out = await _readiness_gate_call_next(req, call_next)
    assert out.status_code == 499
    assert out.headers.get("x-correlation-id") == "cid-disc"


@pytest.mark.asyncio
async def test_readiness_gate_call_next_no_response_without_disconnect_500_with_correlation():
    from server import _readiness_gate_call_next

    req = MagicMock()
    req.url.path = "/api/client/tasks"
    req.method = "POST"
    req.state = MagicMock()
    req.state.correlation_id = "cid-500"
    req.is_disconnected = AsyncMock(return_value=False)

    async def call_next(_r):
        raise RuntimeError("No response returned.")

    out = await _readiness_gate_call_next(req, call_next)
    assert out.status_code == 500
    assert out.headers.get("x-correlation-id") == "cid-500"
    data = _json_response_data(out)
    assert data["detail"] == "Internal server error"
    assert data["correlation_id"] == "cid-500"


@pytest.mark.asyncio
async def test_readiness_gate_call_next_propagates_valueerror():
    from server import _readiness_gate_call_next

    req = MagicMock()
    req.state = MagicMock()

    async def call_next(_r):
        raise ValueError("endpoint bug")

    with pytest.raises(ValueError, match="endpoint bug"):
        await _readiness_gate_call_next(req, call_next)


def test_startup_readiness_gate_allows_traffic_when_ready_and_blocks_when_not(client):
    from server import app

    prev_db_ready = getattr(app.state, "db_ready", True)
    try:
        app.state.db_ready = True
        r = client.get("/api/version")
        assert r.status_code == 200
        assert "commit_sha" in r.json()

        app.state.db_ready = False
        blocked = client.get("/api/client/properties")
        assert blocked.status_code == 503
        assert blocked.json().get("detail")
        assert blocked.headers.get("retry-after") == "5"

        health = client.get("/api/health")
        assert health.status_code == 503
        assert health.json().get("status") == "starting"
    finally:
        app.state.db_ready = prev_db_ready


@pytest.mark.asyncio
async def test_readiness_gate_call_next_http_exception_not_swallowed():
    from fastapi import HTTPException
    from server import _readiness_gate_call_next

    req = MagicMock()
    req.state = MagicMock()

    async def call_next(_r):
        raise HTTPException(status_code=418, detail="teapot")

    with pytest.raises(HTTPException) as ei:
        await _readiness_gate_call_next(req, call_next)
    assert ei.value.status_code == 418


def test_import_server_app_smoke():
    from server import app as loaded

    assert loaded.title is not None
