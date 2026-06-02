#!/usr/bin/env python3
"""
ADMIN-AUTH-RUNTIME-503-DIAGNOSTIC-01 positive auth verification.

Uses only STAGING_ADMIN_EMAIL / STAGING_ADMIN_PASSWORD from environment.
Never prints or persists credentials, tokens, or session secrets.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "audit" / "admin_auth_runtime_503_01"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")

_REDACT_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "token",
        "step_up_token",
        "password",
        "email",
        "authorization",
        "cookie",
        "session",
    }
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Dict[str, Any]) -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _require_creds() -> tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or "").strip()
    password = (os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
    if not email or not password:
        raise SystemExit(
            "STAGING_ADMIN_EMAIL and STAGING_ADMIN_PASSWORD must be set in the environment."
        )
    return email, password


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in _REDACT_KEYS:
                out[key] = "<redacted>"
            else:
                out[key] = _sanitize(item)
        return out
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _probe_login(email: str, password: str) -> tuple[Dict[str, Any], Optional[str]]:
    r = httpx.post(
        f"{API}/auth/admin/login",
        json={"email": email, "password": password},
        timeout=120,
    )
    raw = r.json() if r.content else {}
    issued = r.status_code == 200 and isinstance(raw, dict) and bool(raw.get("access_token"))
    token = str(raw.get("access_token")) if issued else None
    body = _sanitize(raw)
    return {
        "generated_at": _utc(),
        "endpoint": "/api/auth/admin/login",
        "status_code": r.status_code,
        "token_issued": issued,
        "readiness_block_observed": r.status_code == 503,
        "degraded_auth_path": False,
        "result": "pass" if issued else "fail",
        "detail": body.get("detail") if isinstance(body, dict) else None,
    }, token


def _probe_invalid_admin_login() -> Dict[str, Any]:
    r = httpx.post(
        f"{API}/auth/admin/login",
        json={"email": "invalid@example.com", "password": "wrongpass"},
        timeout=60,
    )
    body = _sanitize(r.json() if r.content else {})
    return {
        "status_code": r.status_code,
        "detail": body.get("detail") if isinstance(body, dict) else None,
        "result": "pass" if r.status_code in (401, 403) else "fail",
    }


def _probe_protected_route(token: str) -> Dict[str, Any]:
    r = httpx.get(
        f"{API}/admin/billing/recovery/dashboard",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    body = _sanitize(r.json() if r.content else {})
    authenticated = r.status_code not in (401, 403, 503)
    return {
        "generated_at": _utc(),
        "endpoint": "/api/admin/billing/recovery/dashboard",
        "status_code": r.status_code,
        "authenticated": authenticated,
        "readiness_block_observed": r.status_code == 503,
        "result": "pass" if authenticated else "fail",
        "has_dashboard_sections": bool(
            isinstance(body, dict) and isinstance(body.get("sections"), dict)
        ),
        "detail": body.get("detail") if isinstance(body, dict) else None,
    }


def _probe_invalid_bearer() -> Dict[str, Any]:
    r = httpx.get(
        f"{API}/admin/billing/recovery/dashboard",
        headers={"Authorization": "Bearer invalid"},
        timeout=60,
    )
    body = _sanitize(r.json() if r.content else {})
    return {
        "status_code": r.status_code,
        "detail": body.get("detail") if isinstance(body, dict) else None,
        "result": "pass" if r.status_code in (401, 403) else "fail",
    }


def _run_pytest_startup() -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/tests/test_startup_readiness_gate_middleware.py", "-q"],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {
        "exit_code": proc.returncode,
        "result": "pass" if proc.returncode == 0 else "fail",
        "stdout_tail": proc.stdout[-2000:],
    }


def _run_pytest_billing_recovery() -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/tests/test_billing_recovery_operations.py", "-q"],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {
        "exit_code": proc.returncode,
        "result": "pass" if proc.returncode == 0 else "fail",
        "stdout_tail": proc.stdout[-2000:],
    }


def _run_guided_closeout() -> Dict[str, Any]:
    env = {**os.environ, "STAGING_ADMIN_SECRETS_ONLY": "1"}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "phase4_billing_recovery_guided_flow_closeout_01.py")],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    return {
        "exit_code": proc.returncode,
        "result": "pass" if proc.returncode == 0 else "fail",
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def main() -> None:
    email, password = _require_creds()
    health = httpx.get(f"{API}/health", timeout=60)
    health_body = _sanitize(health.json() if health.content else {})

    login_art, token = _probe_login(email, password)
    login_art["health_status_code"] = health.status_code
    login_art["health_status"] = health_body.get("status") if isinstance(health_body, dict) else None
    _write("valid_admin_login_runtime.json", login_art)

    invalid_admin = _probe_invalid_admin_login()
    invalid_bearer = _probe_invalid_bearer()

    protected_art: Dict[str, Any]
    if token:
        protected_art = _probe_protected_route(token)
    else:
        protected_art = {
            "generated_at": _utc(),
            "endpoint": "/api/admin/billing/recovery/dashboard",
            "result": "skipped",
            "reason": "valid admin login did not issue token",
        }
    protected_art["invalid_admin_login_control"] = invalid_admin
    protected_art["invalid_bearer_control"] = invalid_bearer
    _write("protected_route_runtime.json", protected_art)

    startup_tests = _run_pytest_startup()
    billing_tests = _run_pytest_billing_recovery()
    _write(
        "regression_runtime.json",
        {
            "generated_at": _utc(),
            "startup_readiness_tests": startup_tests,
            "billing_recovery_tests": billing_tests,
        },
    )

    auth_verified = (
        login_art.get("result") == "pass"
        and login_art.get("token_issued") is True
        and protected_art.get("result") == "pass"
        and protected_art.get("authenticated") is True
        and invalid_admin.get("result") == "pass"
        and invalid_bearer.get("result") == "pass"
        and startup_tests.get("result") == "pass"
        and billing_tests.get("result") == "pass"
    )

    classification = "VERIFIED_OPERATIONALLY" if auth_verified else "PARTIAL"
    reason = (
        "Valid admin login and protected route authenticated; invalid controls reject safely; regression tests pass."
        if auth_verified
        else "Positive auth proof incomplete or regression/control checks failed."
    )
    _write(
        "classifications.json",
        {
            "classification": classification,
            "verified_operational": auth_verified,
            "reason": reason,
            "generated_at": _utc(),
        },
    )

    guided_result: Optional[Dict[str, Any]] = None
    if auth_verified:
        guided_result = _run_guided_closeout()
        _write("guided_flow_closeout_invoke.json", {"generated_at": _utc(), **guided_result})

    # stdout: no secrets
    print(
        json.dumps(
            {
                "auth_classification": classification,
                "login_status": login_art.get("status_code"),
                "protected_status": protected_art.get("status_code"),
                "guided_closeout_exit": (guided_result or {}).get("exit_code"),
            },
            indent=2,
        )
    )
    if not auth_verified:
        sys.exit(1)


if __name__ == "__main__":
    main()
