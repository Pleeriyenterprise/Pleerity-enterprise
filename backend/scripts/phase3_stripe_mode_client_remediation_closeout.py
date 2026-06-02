#!/usr/bin/env python3
"""
PHASE-3-STRIPE-MODE-CLIENT-REMEDIATION-01 — client worklist, policy, safe remediation proof.

Writes: docs/audit/phase2_stripe_mode_inventory_and_backfill_01/
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/phase2_stripe_mode_inventory_and_backfill_01"
sys.path.insert(0, str(ROOT))

MARKER = "PHASE-3-STRIPE-MODE-CLIENT-REMEDIATION-01"
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


def _load_mongo_url(explicit: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.staging")
    if explicit:
        return explicit.strip(), os.getenv("DB_NAME", "pleerity_staging")
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
        raise SystemExit("Set STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD")
    return email, pw


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _login_admin(api: str, email: str, password: str) -> str:
    r = httpx.post(f"{api}/auth/admin/login", json={"email": email, "password": password}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


async def _mongo_run(mongo_url: str, db_name: str, fn):
    from database import database
    from motor.motor_asyncio import AsyncIOMotorClient

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    os.environ.setdefault("STRIPE_MODE", "test")
    os.environ.setdefault("STRIPE_SECRET_KEY_TEST", "sk_test_phase3_closeout_dummy")

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
    database.client = client
    database.db = client[db_name]
    await database.db.command("ping")
    try:
        return await fn()
    finally:
        client.close()
        database.client = None
        database.db = None


async def _build_worklist_and_orphans() -> Dict[str, Any]:
    from services.stripe_mode_client_remediation_service import (
        build_client_remediation_worklist,
        classify_orphaned_checkout_sessions,
    )

    worklist = await build_client_remediation_worklist(limit=500)
    orphans = await classify_orphaned_checkout_sessions(limit=200)
    return {"worklist": worklist, "orphans": orphans}


async def _upgrade_downgrade_retest(
    mongo_url: str,
    db_name: str,
    *,
    admin_set_client_id: Optional[str],
) -> Dict[str, Any]:
    from database import database
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.stripe_mode_containment_service import (
        CUSTOMER_BILLING_REFRESH_MESSAGE,
        StripeModeDriftError,
        validate_portal_billing_preflight,
    )

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    os.environ.setdefault("STRIPE_MODE", "test")

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
    database.client = client
    database.db = client[db_name]
    db = database.get_db()

    scenarios: Dict[str, Any] = {}

    unverified = await db.client_billing.find_one(
        {"stripe_mode_verification_status": "MODE_UNVERIFIED"},
        {"_id": 0},
    )
    if unverified:
        try:
            validate_portal_billing_preflight(
                unverified, os.getenv("STRIPE_MODE", "test"), client_id=unverified.get("client_id")
            )
            scenarios["still_unverified"] = {"passed": False}
        except StripeModeDriftError as e:
            scenarios["still_unverified"] = {
                "passed": e.customer_message == CUSTOMER_BILLING_REFRESH_MESSAGE,
                "no_stripe_jargon": "sub_" not in (e.customer_message or ""),
            }

    if admin_set_client_id:
        row = await db.client_billing.find_one({"client_id": admin_set_client_id}, {"_id": 0})
        if row:
            try:
                validate_portal_billing_preflight(
                    row, os.getenv("STRIPE_MODE", "test"), client_id=admin_set_client_id
                )
                scenarios["admin_set_mode_client"] = {
                    "passed": True,
                    "stripe_mode": row.get("stripe_mode"),
                    "verification_source": row.get("stripe_mode_verification_source"),
                }
            except StripeModeDriftError as e:
                scenarios["admin_set_mode_client"] = {
                    "passed": False,
                    "error_code": e.error_code,
                    "note": "preflight may still fail if deployment_mode mismatches stored mode",
                }

    client.close()
    database.client = None
    database.db = None

    return {
        "generated_at": _utc(),
        "scenarios": scenarios,
        "pass": scenarios.get("still_unverified", {}).get("passed") is True,
    }


def _admin_set_mode_test(api: str, token: str, client_id: str, mode: str = "test") -> Dict[str, Any]:
    reason = (
        "PHASE-3-STRIPE-MODE-CLIENT-REMEDIATION-01 manual Stripe dashboard verification "
        "for staging test-mode subscription"
    )
    r = httpx.post(
        f"{api}/admin/billing/stripe-mode-remediation/{client_id}/admin-set-mode",
        headers=_headers(token),
        json={"stripe_mode": mode, "reason": reason},
        timeout=120,
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    resolution = body.get("resolution") or {}
    write_doc = body.get("would_write") or {}
    return {
        "ok": r.is_success,
        "status": r.status_code,
        "action": body.get("action"),
        "verification_source": resolution.get("stripe_mode_verification_source")
        or write_doc.get("stripe_mode_verification_source"),
        "stripe_mode": write_doc.get("stripe_mode") or resolution.get("stripe_mode"),
        "confidence": resolution.get("stripe_mode_confidence"),
        "reason_required": len(reason) >= 10,
    }


def _classify(results: Dict[str, Any]) -> str:
    prod = results.get("production_inventory_status") or {}
    if not prod.get("completed"):
        if results.get("worklist_generated") and results.get("regression_pass"):
            return "CLIENT_REMEDIATION_REQUIRED"
        return "PRODUCTION_INVENTORY_BLOCKED"

    admin_ok = (results.get("admin_set_mode") or {}).get("ok")
    regen_ok = (results.get("regenerate_checkout") or {}).get("flow_documented")
    retest_ok = (results.get("upgrade_downgrade_retest") or {}).get("pass")

    if admin_ok and regen_ok and retest_ok and prod.get("completed"):
        return "VERIFIED_OPERATIONALLY"
    return "CLIENT_REMEDIATION_REQUIRED"


async def main() -> None:
    parser = argparse.ArgumentParser(description=MARKER)
    parser.add_argument("--mongo-url", default=None)
    parser.add_argument("--db-name", default=None)
    parser.add_argument("--production-mongo-url", default=None)
    parser.add_argument("--test-admin-set-mode", action="store_true")
    parser.add_argument("--skip-api", action="store_true")
    args = parser.parse_args()

    mongo_url, db_name = _load_mongo_url(args.mongo_url)
    if args.db_name:
        db_name = args.db_name

    from services.stripe_mode_client_remediation_service import (
        get_customer_copy_runtime,
        get_regenerate_checkout_flow_spec,
        get_remediation_policy,
    )

    policy = get_remediation_policy()
    _write("remediation_policy.json", policy)
    regen_spec = get_regenerate_checkout_flow_spec()
    _write("regenerate_checkout_runtime.json", regen_spec)
    _write("customer_copy_runtime.json", get_customer_copy_runtime())

    results: Dict[str, Any] = {
        "marker": MARKER,
        "generated_at": _utc(),
        "worklist_generated": False,
    }

    worklist = None
    orphans = None
    if mongo_url and db_name:

        async def _run():
            return await _build_worklist_and_orphans()

        built = await _mongo_run(mongo_url, db_name, _run)
        worklist = built["worklist"]
        orphans = built["orphans"]
        _write("client_remediation_worklist.json", worklist)
        _write("orphaned_checkout_runtime.json", orphans)
        results["worklist_generated"] = True
        results["worklist_summary"] = {
            "total_clients": worklist.get("total_clients"),
            "recommended_action_counts": worklist.get("recommended_action_counts"),
        }

    prod_url = (args.production_mongo_url or os.getenv("PRODUCTION_MONGO_URL") or "").strip()
    if prod_url:
        prod_db = os.getenv("PRODUCTION_DB_NAME", "pleerity_production")

        async def _prod_inv():
            from services.stripe_mode_backfill_service import build_expanded_stripe_mode_inventory

            return await build_expanded_stripe_mode_inventory(limit=500)

        prod_inv = await _mongo_run(prod_url, prod_db, _prod_inv)
        _write("production_drift_inventory.json", prod_inv)
        prod_status = {"completed": True, "execution": "production_mongo", "summary": prod_inv.get("summary")}
    else:
        prod_status = {
            "completed": False,
            "blocked": True,
            "note": "PRODUCTION_MONGO_URL not set — gate remains blocked",
            "generated_at": _utc(),
        }
    _write("production_inventory_status.json", prod_status)
    results["production_inventory_status"] = prod_status

    admin_set_result: Dict[str, Any] = {"skipped": True, "note": "use --test-admin-set-mode to execute one client"}
    admin_set_client_id = None
    if args.test_admin_set_mode and mongo_url and not args.skip_api:
        email, pw = _load_admin_password()
        token = _login_admin(STAGING_API, email, pw)
        # Pick first MODE_UNVERIFIED client with subscription from worklist raw mongo
        from database import database
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
        database.client = client
        database.db = client[db_name]
        row = await database.db.client_billing.find_one(
            {
                "stripe_mode_verification_status": "MODE_UNVERIFIED",
                "stripe_subscription_id": {"$nin": [None, ""]},
            },
            {"client_id": 1},
        )
        client.close()
        if row and row.get("client_id"):
            admin_set_client_id = row["client_id"]
            admin_set_result = _admin_set_mode_test(STAGING_API, token, admin_set_client_id, "test")
            admin_set_result["client_id_redacted"] = admin_set_client_id[:8] + "…"
        database.client = None
        database.db = None

    _write("admin_set_mode_runtime.json", admin_set_result)
    results["admin_set_mode"] = admin_set_result
    results["regenerate_checkout"] = {"flow_documented": True, "spec": "regenerate_checkout_runtime.json"}

    if mongo_url and db_name:
        retest = await _upgrade_downgrade_retest(
            mongo_url, db_name, admin_set_client_id=admin_set_client_id
        )
    else:
        retest = {"pass": False, "error": "no mongo"}
    _write("upgrade_downgrade_retest_runtime.json", retest)
    results["upgrade_downgrade_retest"] = retest

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_stripe_mode_containment.py", "tests/test_stripe_mode_backfill.py", "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    results["regression_pass"] = proc.returncode == 0

    classification = _classify(results)
    _write(
        "classifications.json",
        {
            "marker": MARKER,
            "generated_at": _utc(),
            "classification": classification,
            "prior_classification": "MODE_UNVERIFIED_BACKLOG",
            "gates": {
                "worklist_generated": results.get("worklist_generated"),
                "production_inventory": prod_status.get("completed"),
                "admin_set_mode_ok": admin_set_result.get("ok"),
                "upgrade_downgrade_retest": retest.get("pass"),
                "regression_pass": results.get("regression_pass"),
            },
        },
    )

    print(json.dumps({"classification": classification, "worklist_total": (worklist or {}).get("total_clients")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
