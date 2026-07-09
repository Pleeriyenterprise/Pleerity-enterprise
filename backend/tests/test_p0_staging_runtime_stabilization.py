"""P0 staging runtime stabilization — guard and contract resolve behaviour."""
from __future__ import annotations

import inspect
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_runtime_contract_supports_emit_events_flag():
    from services.account_lifecycle_runtime_contract import resolve_runtime_contract_for_client

    sig = inspect.signature(resolve_runtime_contract_for_client)
    assert "emit_events" in sig.parameters


def test_client_guard_skips_event_emission():
    text = (BACKEND_ROOT / "middleware" / "__init__.py").read_text(encoding="utf-8")
    guard = text.split("_client_context_guard")[1].split("async def client_route_guard")[0]
    assert "emit_events=False" in guard


def test_http_exception_handler_includes_cors_headers():
    text = (BACKEND_ROOT / "server.py").read_text(encoding="utf-8")
    block = text.split("async def http_exception_handler")[1].split("@app.exception_handler(Exception)")[0]
    assert "_cors_headers_for_origin" in block


def test_validation_exception_handler_includes_cors_headers():
    text = (BACKEND_ROOT / "server.py").read_text(encoding="utf-8")
    block = text.split("async def validation_exception_handler")[1].split("@app.exception_handler(HTTPException)")[0]
    assert "_cors_headers_for_origin" in block


def test_client_context_guard_only_blocks_terminal_lifecycle():
    text = (BACKEND_ROOT / "middleware" / "__init__.py").read_text(encoding="utf-8")
    guard = text.split("_blocked_lifecycle = frozenset({")[1].split("})")[0]
    assert "ARCHIVED" in guard
    assert "ACCOUNT_DELETED" in guard
    assert "READ_ONLY" not in guard
    assert "CANCELLED_IMMEDIATE" not in guard
    assert "SUSPENDED" not in guard


def test_security_gate_skips_ip_block_for_options_preflight():
    text = (BACKEND_ROOT / "server.py").read_text(encoding="utf-8")
    gate = text.split("async def _security_monitoring_gate")[1].split("async def _readiness_gate_call_next")[0]
    assert 'method != "OPTIONS"' in gate
    assert "should_block_ip" in gate
