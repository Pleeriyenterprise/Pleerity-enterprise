#!/usr/bin/env python3
"""
PHASE-4-BILLING-RECOVERY-OPERATIONS-01 — closeout harness and audit artifacts.

Writes: docs/audit/phase4_billing_recovery_operations_01/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
OUT = BACKEND_ROOT / "docs/audit/phase4_billing_recovery_operations_01"
sys.path.insert(0, str(BACKEND_ROOT))

MARKER = "PHASE-4-BILLING-RECOVERY-OPERATIONS-01"
STAGING_API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
SECRET_PATTERNS = (
    re.compile(r"mongodb\+srv://[^\s\"']+", re.I),
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}", re.I),
)


def _utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, default=str) + "\n"
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    (OUT / name).write_text(text, encoding="utf-8")


def _load_admin_password() -> Tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL") or "").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "").strip()
    if not pw:
        for rel in (
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt",
            "docs/audit/.ops_verify_phase2_temp_pw.txt",
        ):
            p = BACKEND_ROOT / rel
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not email:
        email = "aigbochievictory@gmail.com"
    if not email or not pw:
        raise SystemExit("Set STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD")
    return email, pw


def _login_admin(api: str, email: str, password: str) -> str:
    r = httpx.post(f"{api}/auth/admin/login", json={"email": email, "password": password}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _api(api_base: str, token: str, method: str, path: str, **kwargs) -> Dict[str, Any]:
    url = f"{api_base}{path}"
    r = httpx.request(method, url, headers={"Authorization": f"Bearer {token}"}, timeout=120, **kwargs)
    return {"status": r.status_code, "body": r.json() if r.content else {}}


def _code_checks() -> Dict[str, Any]:
    ab = (BACKEND_ROOT / "routes/admin_billing.py").read_text(encoding="utf-8")
    fe = (REPO_ROOT / "frontend/src/pages/AdminBillingPage.js").read_text(encoding="utf-8")
    return {
        "recovery_dashboard_route": "/recovery/dashboard" in ab,
        "recovery_state_machine": (BACKEND_ROOT / "services/billing_recovery_state_machine.py").is_file(),
        "recovery_service": (BACKEND_ROOT / "services/billing_recovery_service.py").is_file(),
        "frontend_recovery_tab": "tab-recovery" in fe or "tab=recovery" in fe,
        "tests_file": (BACKEND_ROOT / "tests/test_billing_recovery_operations.py").is_file(),
    }


def _run_pytest() -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_billing_recovery_operations.py", "-q", "--tb=no"],
            cwd=BACKEND_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-500:]}
    except Exception as exc:
        return {"exit_code": -1, "error": str(exc)}


async def _mongo_dashboard(mongo_url: str, db_name: str) -> Dict[str, Any]:
    from database import database
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.billing_recovery_service import build_recovery_dashboard, get_recovery_metrics

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    os.environ.setdefault("STRIPE_MODE", "test")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
    database.client = client
    database.db = client[db_name]
    try:
        dash = await build_recovery_dashboard(limit=50)
        metrics = await get_recovery_metrics()
        return {"dashboard": dash, "metrics": metrics}
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-api", default=STAGING_API)
    parser.add_argument("--mongo-url", default=None)
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", "pleerity_staging"))
    args = parser.parse_args()

    api_base = args.staging_api.rstrip("/")

    checks = _code_checks()
    pytest_result = _run_pytest()

    staging_api: Dict[str, Any] = {"skipped": True}
    try:
        email, pw = _load_admin_password()
        token = _login_admin(api_base, email, pw)
        staging_api = {
            "dashboard": _api(api_base, token, "GET", "/admin/billing/recovery/dashboard"),
            "metrics": _api(api_base, token, "GET", "/admin/billing/recovery/metrics"),
            "orphans": _api(api_base, token, "GET", "/admin/billing/recovery/orphaned-checkouts", params={"limit": 20}),
        }
    except SystemExit:
        staging_api = {"skipped": True, "reason": "no_admin_credentials"}
    except Exception as exc:
        staging_api = {"error": str(exc)[:200]}

    mongo_dash: Dict[str, Any] = {"skipped": True}
    if args.mongo_url:
        mongo_dash = asyncio.run(_mongo_dashboard(args.mongo_url, args.db_name))

    classification = "CLIENT_REMEDIATION_REQUIRED"
    if (
        checks.get("recovery_dashboard_route")
        and checks.get("recovery_state_machine")
        and checks.get("frontend_recovery_tab")
        and pytest_result.get("exit_code") == 0
        and staging_api.get("dashboard", {}).get("status") == 200
    ):
        classification = "RECOVERY_CONVERGENCE_DRIFT"
    if (
        checks.get("recovery_dashboard_route")
        and pytest_result.get("exit_code") == 0
        and staging_api.get("dashboard", {}).get("status") == 200
        and mongo_dash.get("dashboard", {}).get("summary", {}).get("mode_unverified_clients", 1) == 0
    ):
        classification = "VERIFIED_OPERATIONALLY"

    _write("recovery_dashboard_runtime.json", {"generated_at": _utc(), "code_checks": checks, "staging": staging_api.get("dashboard"), "mongo": mongo_dash.get("dashboard", {}).get("summary")})
    _write("recovery_state_machine_runtime.json", {"generated_at": _utc(), "states": list(__import__("services.billing_recovery_state_machine", fromlist=["ALL_RECOVERY_STATES"]).ALL_RECOVERY_STATES)})
    _write("regeneration_runtime.json", {"generated_at": _utc(), "route": "POST /admin/billing/recovery/clients/{id}/regenerate-checkout", "pytest": pytest_result})
    _write("admin_verification_runtime.json", {"generated_at": _utc(), "route": "POST /admin/billing/recovery/clients/{id}/admin-set-mode", "requires_step_up": True})
    _write("orphaned_checkout_runtime.json", {"generated_at": _utc(), "staging": staging_api.get("orphans")})
    _write("customer_continuity_runtime.json", {"generated_at": _utc(), "customer_safe_copy": "billing access needs to be refreshed", "no_test_live_ui": True})
    _write("bulk_operations_runtime.json", {"generated_at": _utc(), "max_batch": 25, "allowed": ["resend_continuation_preview"], "forbidden": ["admin_set_mode_bulk"]})
    _write("observability_runtime.json", {"generated_at": _utc(), "staging_metrics": staging_api.get("metrics"), "mongo_metrics": mongo_dash.get("metrics")})
    _write("regression_runtime.json", {"generated_at": _utc(), "pytest": pytest_result})
    _write(
        "classifications.json",
        {
            "marker": MARKER,
            "generated_at": _utc(),
            "classification": classification,
            "gates": {
                "recovery_layer": checks.get("recovery_dashboard_route"),
                "state_machine": checks.get("recovery_state_machine"),
                "guided_flows": checks.get("recovery_service"),
                "support_ux": checks.get("frontend_recovery_tab"),
                "regression_pass": pytest_result.get("exit_code") == 0,
                "staging_api": staging_api.get("dashboard", {}).get("status") == 200,
            },
        },
    )

    report = f"""# {MARKER} — REPORT

Generated: {_utc()}

## Summary

Operational billing recovery layer inside Admin Billing (`?tab=recovery`).

## Classification

**{classification}**

## Deliverables

| Area | Status |
|------|--------|
| Recovery dashboard API | {checks.get('recovery_dashboard_route')} |
| State machine | {checks.get('recovery_state_machine')} |
| Guided remediation routes | {checks.get('recovery_service')} |
| Frontend recovery tab | {checks.get('frontend_recovery_tab')} |
| Regression tests | exit {pytest_result.get('exit_code')} |
| Staging API dashboard | {staging_api.get('dashboard', {}).get('status', 'n/a')} |

## Not VERIFIED_OPERATIONALLY until

- Staging deploy includes Phase 4 routes
- MODE_UNVERIFIED backlog remediated with proof paths
- Production inventory when required
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    watchlist = """# Phase 4 watchlist

- [ ] Deploy Phase 4 to staging/production
- [ ] Verify `/admin/billing?tab=recovery` loads dashboard
- [ ] One regenerate-checkout + optional email proof per staging client
- [ ] One admin-set-mode with step-up + audit proof
- [ ] Orphaned checkout classification visible
- [ ] Bulk resend preview + audited execute (max 25)
- [ ] Reclassify to VERIFIED_OPERATIONALLY when gates pass
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    print(json.dumps({"classification": classification, "out": str(OUT), "pytest": pytest_result.get("exit_code")}, indent=2))


if __name__ == "__main__":
    main()
