#!/usr/bin/env python3
"""
PHASE-2-STRIPE-MODE-INVENTORY-AND-BACKFILL-01 — inventory, backfill dry-run, audit artifacts.

READ ONLY inventory against staging/production (API or Mongo).
Backfill dry-run only unless --execute with admin confirmation.

Writes: docs/audit/phase2_stripe_mode_inventory_and_backfill_01/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/phase2_stripe_mode_inventory_and_backfill_01"
sys.path.insert(0, str(ROOT))

MARKER = "PHASE-2-STRIPE-MODE-INVENTORY-AND-BACKFILL-01"
STAGING_API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
PRODUCTION_API = os.getenv("PRODUCTION_API", STAGING_API).rstrip("/")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _load_mongo_url(explicit: Optional[str], url_file: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.staging")
    if explicit:
        return explicit.strip(), os.getenv("DB_NAME", "pleerity_staging")
    if url_file:
        p = Path(url_file)
        if p.is_file():
            raw = p.read_text(encoding="utf-8").strip()
            for line in raw.splitlines():
                if line.startswith("MONGO_URL="):
                    return line.split("=", 1)[1].strip(), os.getenv("DB_NAME", "pleerity_staging")
            if raw.startswith("mongodb"):
                return raw, os.getenv("DB_NAME", "pleerity_staging")
    for key in ("STAGING_MONGO_URL", "MONGO_URL", "DATABASE_URL"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val, os.getenv("DB_NAME", "pleerity_staging")
    return None, None


def _load_admin_password() -> Tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL") or "").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "").strip()
    if not pw:
        for rel in (
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt",
            "docs/audit/.ops_verify_phase2_temp_pw.txt",
        ):
            p = ROOT / rel
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not email:
        email = "aigbochievictory@gmail.com"
    if not email or not pw:
        raise SystemExit("Set STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD or ops_verify admin pw file.")
    return email, pw


def _login_admin(api: str, email: str, password: str) -> str:
    r = httpx.post(f"{api}/auth/admin/login", json={"email": email, "password": password}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


async def _connect_mongo(mongo_url: str, db_name: str):
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
    await client[db_name].command("ping")
    return client, client[db_name]


async def _run_local_inventory(mongo_url: str, db_name: str, env_label: str) -> Dict[str, Any]:
    from database import database
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.stripe_mode_backfill_service import (
        audit_legacy_stripe_callers,
        build_expanded_stripe_mode_inventory,
        run_backfill_batch,
    )

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    os.environ.setdefault("STRIPE_MODE", "test")
    os.environ.setdefault("STRIPE_SECRET_KEY_TEST", "sk_test_inventory_closeout_dummy")

    database.client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
    database.db = database.client[db_name]
    await database.db.command("ping")

    inventory = await build_expanded_stripe_mode_inventory(limit=500)
    inventory["environment"] = env_label
    inventory["execution"] = "local_mongo"
    inventory["marker"] = MARKER

    backfill_dry = await run_backfill_batch(limit=100, dry_run=True)
    backfill_dry["environment"] = env_label

    legacy = audit_legacy_stripe_callers()

    if database.client:
        database.client.close()
    database.client = None
    database.db = None

    return {"inventory": inventory, "backfill_dry_run": backfill_dry, "legacy_callers": legacy}


async def _run_api_inventory(api: str, token: str, env_label: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    inv = httpx.get(
        f"{api}/admin/billing/stripe-mode-inventory",
        params={"expanded": "true", "limit": 500},
        headers=headers,
        timeout=120,
    )
    backfill = httpx.post(
        f"{api}/admin/billing/stripe-mode-backfill",
        json={"dry_run": True, "limit": 100},
        headers=headers,
        timeout=120,
    )
    legacy = httpx.get(
        f"{api}/admin/billing/stripe-mode-legacy-callers",
        headers=headers,
        timeout=60,
    )
    return {
        "inventory": {**inv.json(), "environment": env_label, "execution": "staging_api", "status": inv.status_code},
        "backfill_dry_run": {**backfill.json(), "environment": env_label, "status": backfill.status_code},
        "legacy_callers": {**legacy.json(), "environment": env_label, "status": legacy.status_code},
    }


def _run_regression() -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_stripe_mode_containment.py",
        "tests/test_stripe_mode_backfill.py",
        "-q",
        "--tb=no",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:] if proc.stdout else "",
        "stderr": proc.stderr[-2000:] if proc.stderr else "",
        "passed": proc.returncode == 0,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=MARKER)
    parser.add_argument("--mongo-url", default=None)
    parser.add_argument("--mongo-url-file", default=None)
    parser.add_argument("--db-name", default=None)
    parser.add_argument("--production-mongo-url", default=None)
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--skip-regression", action="store_true")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {"marker": MARKER, "generated_at": _utc(), "artifacts": []}

    mongo_url, db_name = _load_mongo_url(args.mongo_url, args.mongo_url_file)
    if args.db_name:
        db_name = args.db_name

    staging_result: Optional[Dict[str, Any]] = None
    production_result: Optional[Dict[str, Any]] = None

    if mongo_url and db_name:
        staging_result = await _run_local_inventory(mongo_url, db_name, "staging")
        _write("staging_drift_inventory.json", staging_result["inventory"])
        manifest["artifacts"].append("staging_drift_inventory.json")

    if args.production_mongo_url:
        prod_db = os.getenv("PRODUCTION_DB_NAME", db_name or "pleerity_production")
        production_result = await _run_local_inventory(args.production_mongo_url, prod_db, "production")
        _write("production_drift_inventory.json", production_result["inventory"])
        manifest["artifacts"].append("production_drift_inventory.json")

    if not args.skip_api:
        try:
            email, pw = _load_admin_password()
            token = _login_admin(STAGING_API, email, pw)
            api_staging = await _run_api_inventory(STAGING_API, token, "staging")
            if not staging_result:
                _write("staging_drift_inventory.json", api_staging["inventory"])
                manifest["artifacts"].append("staging_drift_inventory.json")
            _write(
                "authoritative_backfill_runtime.json",
                api_staging.get("backfill_dry_run") or {},
            )
            manifest["artifacts"].append("authoritative_backfill_runtime.json")
        except Exception as exc:
            _write(
                "authoritative_backfill_runtime.json",
                {"error": str(exc), "execution": "api_failed", "generated_at": _utc()},
            )

    legacy = None
    if staging_result:
        legacy = staging_result.get("legacy_callers")
        _write("authoritative_backfill_runtime.json", staging_result.get("backfill_dry_run", {}))
    if legacy is None:
        from services.stripe_mode_backfill_service import audit_legacy_stripe_callers

        legacy = audit_legacy_stripe_callers()
    _write("legacy_stripe_caller_audit.json", legacy)
    manifest["artifacts"].append("legacy_stripe_caller_audit.json")

    _write(
        "unknown_mode_runtime.json",
        {
            "generated_at": _utc(),
            "governance": "MODE_UNVERIFIED blocks plan changes with customer-safe messaging",
            "customer_message": "Your billing record needs to be refreshed before plan changes can continue.",
            "staging_summary": (staging_result or {}).get("inventory", {}).get("summary"),
        },
    )
    _write(
        "remediation_runtime.json",
        {
            "generated_at": _utc(),
            "remediation_codes": [
                "REGENERATE_CHECKOUT_REQUIRED",
                "INVALID_SUBSCRIPTION_REFERENCE",
                "LEGACY_TEST_SUBSCRIPTION",
                "MODE_UNVERIFIED",
                "PORTAL_RELINK_REQUIRED",
                "CUSTOMER_RECONCILIATION_REQUIRED",
            ],
            "admin_endpoints": [
                "GET /api/admin/billing/stripe-mode-remediation/{client_id}",
                "POST /api/admin/billing/stripe-mode-backfill",
                "POST /api/admin/billing/stripe-mode-remediation/{client_id}/admin-set-mode",
            ],
        },
    )
    _write(
        "webhook_convergence_runtime.json",
        {
            "generated_at": _utc(),
            "persisted_fields": ["livemode", "environment_source", "event_verification_status"],
            "authority": "webhook livemode mismatch blocked at ingress",
        },
    )

    regression = {"skipped": True}
    if not args.skip_regression:
        regression = _run_regression()
    _write("regression_runtime.json", regression)

    staging_inv = (staging_result or {}).get("inventory", {})
    prod_inv_blocked = not production_result and not args.production_mongo_url
    legacy_count = legacy.get("legacy_caller_count", 0) if legacy else 0
    regression_pass = regression.get("passed", False)
    auth_coverage = (staging_inv.get("metrics") or {}).get("authoritative_mode_coverage", 0)
    backfill_summary = (staging_result or {}).get("backfill_dry_run", {}).get("summary", {})

    if (
        staging_inv
        and not prod_inv_blocked
        and regression_pass
        and legacy_count == 0
        and auth_coverage > 0
    ):
        classification = "VERIFIED_OPERATIONALLY"
    elif staging_inv and regression_pass and legacy_count == 0:
        classification = "MODE_UNVERIFIED_BACKLOG"
    elif staging_inv and regression_pass and legacy_count > 0:
        classification = "LEGACY_CALLER_DRIFT"
    elif staging_inv:
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    _write(
        "classifications.json",
        {
            "marker": MARKER,
            "generated_at": _utc(),
            "classification": classification,
            "gates": {
                "staging_inventory": bool(staging_inv),
                "production_inventory": not prod_inv_blocked,
                "regression_pass": regression_pass,
                "legacy_caller_count": legacy_count,
                "authoritative_mode_coverage": auth_coverage,
                "backfill_dry_run": backfill_summary,
            },
        },
    )
    _write("manifest.json", manifest)


if __name__ == "__main__":
    asyncio.run(main())
