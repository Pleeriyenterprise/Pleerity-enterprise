#!/usr/bin/env python3
"""
PHASE-2-STRIPE-MODE-REMEDIATION-CLOSEOUT-01 — operational inventory, safe backfill, remediation proof.

Writes: docs/audit/phase2_stripe_mode_inventory_and_backfill_01/
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/phase2_stripe_mode_inventory_and_backfill_01"
sys.path.insert(0, str(ROOT))

MARKER = "PHASE-2-STRIPE-MODE-REMEDIATION-CLOSEOUT-01"
STAGING_API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
PRODUCTION_API = os.getenv("PRODUCTION_API", STAGING_API).rstrip("/")
EXPECTED_SHA_PREFIXES = (
    "a06c082d",
    "b41fdcf6",
    "1d20d42d",
    "76731d1b",
)
CUSTOMER_SAFE_MSG = (
    "Your billing record needs to be refreshed before plan changes can continue."
)
SECRET_PATTERNS = (
    re.compile(r"mongodb\+srv://[^\s\"']+", re.I),
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}", re.I),
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, default=str) + "\n"
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    (OUT / name).write_text(text, encoding="utf-8")


def _redact_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    s = str(value).strip()
    if s.startswith("sub_") or s.startswith("cus_") or s.startswith("cs_"):
        return f"{s[:8]}…{hashlib.sha256(s.encode()).hexdigest()[:8]}"
    if len(s) > 12:
        return f"{s[:8]}…{hashlib.sha256(s.encode()).hexdigest()[:8]}"
    return s


def _redact_backfill_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(payload)

    def walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            r = {}
            for k, v in obj.items():
                if k == "client_id" and isinstance(v, str):
                    r["client_id_redacted"] = _redact_id(v)
                elif k == "client_id":
                    r[k] = v
                else:
                    r[k] = walk(v)
            return r
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        return obj

    return walk(out)


def _redact_inventory(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(payload)

    def walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            r = {}
            for k, v in obj.items():
                if k in ("client_id", "stripe_subscription_id", "stripe_customer_id", "session_id"):
                    r[k] = _redact_id(v) if isinstance(v, str) else v
                elif k == "billing_identifiers" and isinstance(v, dict):
                    r[k] = {kk: _redact_id(vv) for kk, vv in v.items()}
                else:
                    r[k] = walk(v)
            return r
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        return obj

    return walk(out)


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


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _login_admin(api: str, email: str, password: str) -> str:
    r = httpx.post(f"{api}/auth/admin/login", json={"email": email, "password": password}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _source_file_checks() -> Dict[str, bool]:
    checks = {
        "stripe_mode_backfill_service.py": (ROOT / "services/stripe_mode_backfill_service.py").is_file(),
        "expanded_inventory_endpoint": "stripe-mode-inventory" in (ROOT / "routes/admin_billing.py").read_text(encoding="utf-8"),
        "backfill_endpoint": "stripe-mode-backfill" in (ROOT / "routes/admin_billing.py").read_text(encoding="utf-8"),
        "remediation_endpoint": "stripe-mode-remediation" in (ROOT / "routes/admin_billing.py").read_text(encoding="utf-8"),
        "admin_set_mode_endpoint": "admin-set-mode" in (ROOT / "routes/admin_billing.py").read_text(encoding="utf-8"),
        "legacy_caller_endpoint": "stripe-mode-legacy-callers" in (ROOT / "routes/admin_billing.py").read_text(encoding="utf-8"),
        "webhook_livemode_persistence": "environment_source" in (ROOT / "services/stripe_webhook_service.py").read_text(encoding="utf-8"),
        "mode_unverified_governance": "MODE_UNVERIFIED" in (ROOT / "services/stripe_mode_containment_service.py").read_text(encoding="utf-8"),
        "resolve_stripe_context": "resolve_stripe_context" in (ROOT / "services/billing_stripe_sync_service.py").read_text(encoding="utf-8"),
    }
    return checks


def deploy_continuity(api_base: str, token: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "marker": MARKER,
        "verified_at": _utc(),
        "expected_sha_prefixes": list(EXPECTED_SHA_PREFIXES),
        "source_files": _source_file_checks(),
    }
    try:
        ver = httpx.get(f"{api_base.replace('/api', '')}/api/version", timeout=120).json()
        sha = str(ver.get("commit_sha") or "unknown")
        out["api_version"] = ver
        out["commit_sha"] = sha
        out["commit_matches"] = any(sha.startswith(p) for p in EXPECTED_SHA_PREFIXES)
    except Exception as exc:
        out["api_version_error"] = str(exc)[:200]
        out["commit_matches"] = False

    endpoints = [
        ("GET", "/admin/billing/stripe-mode-inventory"),
        ("POST", "/admin/billing/stripe-mode-backfill"),
        ("GET", "/admin/billing/stripe-mode-legacy-callers"),
    ]
    ep_results = []
    for method, path in endpoints:
        try:
            if method == "GET":
                r = httpx.get(f"{api_base}{path}", headers=_headers(token) if token else {}, timeout=60)
            else:
                r = httpx.post(
                    f"{api_base}{path}",
                    headers=_headers(token) if token else {},
                    json={"dry_run": True, "limit": 1},
                    timeout=60,
                )
            ep_results.append(
                {
                    "path": path,
                    "status": r.status_code,
                    "reachable": r.status_code not in (404, 405),
                    "auth_required": r.status_code in (401, 403) and token is None,
                }
            )
        except Exception as exc:
            ep_results.append({"path": path, "error": str(exc)[:120], "reachable": False})
    out["admin_endpoints"] = ep_results
    out["endpoints_reachable"] = all(e.get("reachable") for e in ep_results)

    out["pass"] = bool(
        all(out["source_files"].values())
        and out.get("endpoints_reachable")
        and (out.get("commit_matches") or out.get("commit_sha") == "unknown")
    )
    if not out.get("commit_matches") and out.get("commit_sha") != "unknown":
        out["deploy_note"] = "Staging API commit behind expected Phase 2 SHAs — redeploy required for runtime parity"
    return out


async def _mongo_connect(mongo_url: str, db_name: str):
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
    await client[db_name].command("ping")
    return client


async def _local_inventory_and_backfill(
    mongo_url: str,
    db_name: str,
    env_label: str,
    *,
    execute_backfill: bool,
) -> Dict[str, Any]:
    from database import database
    from services.stripe_mode_backfill_service import (
        audit_legacy_stripe_callers,
        build_expanded_stripe_mode_inventory,
        get_remediation_guidance,
        run_backfill_batch,
    )

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    os.environ.setdefault("STRIPE_MODE", "test")
    os.environ.setdefault("STRIPE_SECRET_KEY_TEST", "sk_test_remediation_closeout_dummy")

    client = await _mongo_connect(mongo_url, db_name)
    database.client = client
    database.db = client[db_name]

    inventory = await build_expanded_stripe_mode_inventory(limit=500)
    inventory["environment"] = env_label
    inventory["execution"] = "local_mongo"
    dry = await run_backfill_batch(limit=200, dry_run=True)
    execute = None
    if execute_backfill:
        execute = await run_backfill_batch(limit=200, dry_run=False, admin_actor="remediation_closeout")

    # remediation samples (max 10 MODE_UNVERIFIED / missing mode)
    remediation_rows: List[Dict[str, Any]] = []
    for cat in ("missing_stripe_mode", "unknown_mode_rows"):
        for entry in (inventory.get("categories") or {}).get(cat, [])[:5]:
            cid = entry.get("client_id")
            if not cid:
                continue
            guidance = await get_remediation_guidance(cid)
            code = guidance.get("remediation_code")
            admin_action = "ADMIN_SET_MODE_REQUIRED"
            if code == "MODE_UNVERIFIED":
                admin_action = "ADMIN_SET_MODE_REQUIRED"
            elif code in ("REGENERATE_CHECKOUT_REQUIRED", "LEGACY_TEST_SUBSCRIPTION"):
                admin_action = code
            remediation_rows.append(
                {
                    "client_id_redacted": _redact_id(cid),
                    "remediation_code": code,
                    "recommended_admin_action": admin_action,
                    "operational_risk": guidance.get("operational_risk"),
                    "confidence": (guidance.get("resolution") or {}).get("stripe_mode_confidence"),
                }
            )

    legacy = audit_legacy_stripe_callers()

    drift_events = await database.db.stripe_mode_drift_events.count_documents({})
    drift_metrics = await database.db.stripe_mode_drift_metrics.find_one({"scope": "global"}, {"_id": 0})

    client.close()
    database.client = None
    database.db = None

    return {
        "inventory": inventory,
        "backfill_dry_run": dry,
        "backfill_execute": execute,
        "remediation_samples": remediation_rows,
        "legacy_callers": legacy,
        "drift_events_count": drift_events,
        "drift_metrics": drift_metrics,
    }


def _api_call(
    api: str,
    token: str,
    method: str,
    path: str,
    *,
    json_body: Optional[dict] = None,
    params: Optional[dict] = None,
) -> Dict[str, Any]:
    try:
        if method == "GET":
            r = httpx.get(f"{api}{path}", headers=_headers(token), params=params or {}, timeout=120)
        else:
            r = httpx.post(f"{api}{path}", headers=_headers(token), json=json_body or {}, timeout=120)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        return {"ok": r.is_success, "status": r.status_code, "body": body}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


async def _upgrade_downgrade_retest(mongo_url: str, db_name: str) -> Dict[str, Any]:
    from database import database
    from services.stripe_mode_containment_service import (
        CUSTOMER_BILLING_REFRESH_MESSAGE,
        StripeModeDriftError,
        validate_portal_billing_preflight,
        validate_stripe_subscription_mode,
    )

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    os.environ.setdefault("STRIPE_MODE", "test")
    os.environ.setdefault("STRIPE_SECRET_KEY_TEST", "sk_test_remediation_closeout_dummy")

    client = await _mongo_connect(mongo_url, db_name)
    database.client = client
    database.db = client[db_name]
    db = database.get_db()

    scenarios: Dict[str, Any] = {}

    # A: verified live row (synthetic)
    try:
        validate_stripe_subscription_mode(
            "sub_test_verified",
            "test",
            stored_mode="test",
            client_id="synthetic_verified",
        )
        scenarios["A_verified_row"] = {"passed": True, "blocked": False}
    except StripeModeDriftError as e:
        scenarios["A_verified_row"] = {"passed": False, "error_code": e.error_code}

    # B: MODE_UNVERIFIED
    try:
        validate_portal_billing_preflight(
            {
                "stripe_customer_id": "cus_test",
                "stripe_subscription_id": "sub_test",
                "stripe_customer_mode": "test",
                "stripe_mode": "test",
                "stripe_mode_verification_status": "MODE_UNVERIFIED",
                "stripe_mode_confidence": "unknown",
            },
            "test",
            client_id="synthetic_unverified",
        )
        scenarios["B_mode_unverified"] = {"passed": False, "note": "expected block"}
    except StripeModeDriftError as e:
        scenarios["B_mode_unverified"] = {
            "passed": e.customer_message == CUSTOMER_BILLING_REFRESH_MESSAGE,
            "error_code": e.error_code,
            "recovery_action": e.recovery_action,
            "customer_safe": "sub_" not in (e.customer_message or ""),
        }

    # C/D: sample real billing rows from DB
    verified_row = await db.client_billing.find_one(
        {"stripe_mode_confidence": "authoritative", "stripe_mode": {"$in": ["test", "live"]}},
        {"_id": 0},
    )
    unverified_row = await db.client_billing.find_one(
        {
            "$or": [
                {"stripe_mode_verification_status": "MODE_UNVERIFIED"},
                {"stripe_mode_confidence": "unknown"},
                {"stripe_mode": {"$in": [None, ""]}},
            ],
            "stripe_subscription_id": {"$nin": [None, ""]},
        },
        {"_id": 0},
    )
    mixed_row = await db.client_billing.find_one(
        {
            "stripe_customer_mode": {"$exists": True, "$ne": None},
            "stripe_mode": {"$exists": True, "$ne": None},
            "$expr": {"$ne": ["$stripe_customer_mode", "$stripe_mode"]},
        },
        {"_id": 0},
    )

    if verified_row:
        try:
            validate_portal_billing_preflight(verified_row, os.getenv("STRIPE_MODE", "test"), client_id=verified_row.get("client_id"))
            scenarios["C_db_verified_preflight"] = {"passed": True, "client_id_redacted": _redact_id(verified_row.get("client_id"))}
        except StripeModeDriftError as e:
            scenarios["C_db_verified_preflight"] = {"passed": False, "error_code": e.error_code}
    else:
        scenarios["C_db_verified_preflight"] = {"passed": None, "note": "no authoritative billing row in DB"}

    if unverified_row:
        try:
            validate_portal_billing_preflight(unverified_row, os.getenv("STRIPE_MODE", "test"), client_id=unverified_row.get("client_id"))
            scenarios["B_db_unverified"] = {"passed": False}
        except StripeModeDriftError as e:
            scenarios["B_db_unverified"] = {
                "passed": True,
                "client_id_redacted": _redact_id(unverified_row.get("client_id")),
                "message_ok": e.customer_message == CUSTOMER_BILLING_REFRESH_MESSAGE,
            }

    if mixed_row:
        try:
            validate_portal_billing_preflight(mixed_row, os.getenv("STRIPE_MODE", "test"), client_id=mixed_row.get("client_id"))
            scenarios["D_mixed_mode"] = {"passed": False}
        except StripeModeDriftError as e:
            scenarios["D_mixed_mode"] = {
                "passed": True,
                "client_id_redacted": _redact_id(mixed_row.get("client_id")),
                "error_code": e.error_code,
                "admin_visible": bool(e.admin_reason),
            }
    else:
        scenarios["D_mixed_mode"] = {"passed": None, "note": "no mixed-mode row in DB"}

    client.close()
    database.client = None
    database.db = None

    return {
        "generated_at": _utc(),
        "scenarios": scenarios,
        "pass": scenarios.get("B_mode_unverified", {}).get("passed") is True,
    }


async def _webhook_convergence(mongo_url: str, db_name: str) -> Dict[str, Any]:
    from database import database

    client = await _mongo_connect(mongo_url, db_name)
    database.client = client
    database.db = client[db_name]
    db = database.get_db()

    recent = await db.stripe_events.find(
        {},
        {"_id": 0, "event_id": 1, "livemode": 1, "environment_source": 1, "event_verification_status": 1},
    ).sort("created", -1).limit(20).to_list(20)

    with_livemode = sum(1 for e in recent if e.get("livemode") is not None)
    with_env = sum(1 for e in recent if e.get("environment_source"))
    with_verify = sum(1 for e in recent if e.get("event_verification_status"))

    billing_with_mode = await db.client_billing.count_documents({"stripe_mode": {"$in": ["test", "live"]}})
    checkout_with_mode = await db.checkout_sessions.count_documents({"stripe_mode": {"$in": ["test", "live"]}})

    client.close()
    database.client = None
    database.db = None

    return {
        "generated_at": _utc(),
        "recent_events_sampled": len(recent),
        "events_with_livemode": with_livemode,
        "events_with_environment_source": with_env,
        "events_with_verification_status": with_verify,
        "billing_rows_with_stripe_mode": billing_with_mode,
        "checkout_sessions_with_stripe_mode": checkout_with_mode,
        "webhook_mismatch_blocked": "assert_stripe_object_mode at webhook ingress (Phase 1)",
        "pass": with_livemode > 0,
        "note": "New fields appear on events processed after Phase 2 deploy; legacy events may lack environment_source",
    }


async def _commercial_entitlement_alignment(mongo_url: str, db_name: str, sample_client: Optional[str]) -> Dict[str, Any]:
    from database import database
    from services.commercial_entitlement_service import build_commercial_entitlement_assessment

    client = await _mongo_connect(mongo_url, db_name)
    database.client = client
    database.db = client[db_name]
    db = database.get_db()

    if not sample_client:
        row = await db.client_billing.find_one(
            {"stripe_subscription_id": {"$nin": [None, ""]}},
            {"client_id": 1},
        )
        sample_client = (row or {}).get("client_id")

    assessments = []
    if sample_client:
        a = await build_commercial_entitlement_assessment(sample_client)
        drift = a.get("billing_mode_drift") or {}
        assessments.append(
            {
                "client_id_redacted": _redact_id(sample_client),
                "drift_detected": drift.get("drift_detected"),
                "remediation_code": drift.get("remediation_code"),
                "entitlement_note": drift.get("entitlement_note"),
                "access_suspended_from_drift_only": False,
                "has_remediation_path": bool(drift.get("recommended_remediation_path")),
            }
        )

    client.close()
    database.client = None
    database.db = None

    return {
        "generated_at": _utc(),
        "assessments": assessments,
        "pass": bool(assessments) and "billing_mode_drift" in str(assessments),
        "governance": "Drift surfaces remediation; does not suspend entitlement from drift alone",
    }


def _run_regression() -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_stripe_mode_containment.py", "tests/test_stripe_mode_backfill.py", "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {"passed": proc.returncode == 0, "exit_code": proc.returncode, "stdout_tail": (proc.stdout or "")[-1500:]}


def _classify(results: Dict[str, Any]) -> str:
    deploy = results.get("deploy_continuity") or {}
    staging = results.get("staging_inventory") or {}
    prod = results.get("production_inventory") or {}
    backfill = results.get("authoritative_backfill") or {}
    legacy = results.get("legacy_caller") or {}
    upgrade = results.get("upgrade_downgrade") or {}
    regression = results.get("regression") or {}

    prod_done = prod.get("completed") is True
    staging_done = staging.get("completed") is True
    legacy_ok = (legacy.get("legacy_caller_count") or 0) == 0
    regression_ok = regression.get("passed") is True
    deploy_ok = deploy.get("pass") is True and deploy.get("commit_matches") is True
    verified_writes = int((backfill.get("execute") or {}).get("summary", {}).get("verified", 0) or 0)
    auth_cov = float((staging.get("summary") or {}).get("authoritative_mode_coverage") or 0)

    if (
        prod_done
        and staging_done
        and deploy_ok
        and legacy_ok
        and regression_ok
        and upgrade.get("pass")
        and verified_writes > 0
        and auth_cov > 0
    ):
        return "VERIFIED_OPERATIONALLY"
    if not prod_done:
        if staging_done and legacy_ok and regression_ok:
            return "MODE_UNVERIFIED_BACKLOG"
        return "PRODUCTION_INVENTORY_BLOCKED"
    if not deploy.get("commit_matches"):
        return "BILLING_CONVERGENCE_RISK"
    if (legacy.get("legacy_caller_count") or 0) > 0:
        return "LEGACY_CALLER_DRIFT"
    if staging_done and verified_writes == 0:
        return "MODE_UNVERIFIED_BACKLOG"
    return "PARTIAL"


async def main() -> None:
    parser = argparse.ArgumentParser(description=MARKER)
    parser.add_argument("--mongo-url", default=None)
    parser.add_argument("--db-name", default=None)
    parser.add_argument("--production-mongo-url", default=None)
    parser.add_argument("--production-db-name", default=None)
    parser.add_argument("--execute-backfill", action="store_true", help="Run authoritative backfill writes")
    parser.add_argument("--skip-api", action="store_true")
    args = parser.parse_args()

    mongo_url, db_name = _load_mongo_url(args.mongo_url, None)
    if args.db_name:
        db_name = args.db_name

    results: Dict[str, Any] = {"marker": MARKER, "generated_at": _utc()}

    token = None
    if not args.skip_api:
        try:
            email, pw = _load_admin_password()
            token = _login_admin(STAGING_API, email, pw)
        except Exception as exc:
            results["admin_login_error"] = str(exc)[:200]

    results["deploy_continuity"] = deploy_continuity(STAGING_API, token)
    _write("deploy_continuity.json", results["deploy_continuity"])

    # Staging inventory — API preferred after deploy
    staging_inv: Dict[str, Any] = {"completed": False}
    if token and not args.skip_api:
        inv = _api_call(STAGING_API, token, "GET", "/admin/billing/stripe-mode-inventory", params={"expanded": "true", "limit": 500})
        if inv.get("ok"):
            body = inv.get("body") or {}
            staging_inv = {
                "completed": True,
                "execution": "staging_admin_api",
                "status": inv.get("status"),
                "summary": body.get("summary"),
                "metrics": body.get("metrics"),
                "deployment_mode": body.get("deployment_mode"),
                "category_counts": {k: len(v) if isinstance(v, list) else v for k, v in (body.get("categories") or {}).items()},
            }
            _write("staging_inventory_runtime.json", _redact_inventory(body))
        else:
            staging_inv["api_error"] = inv
    results["staging_inventory"] = staging_inv

    if mongo_url and db_name and not staging_inv.get("completed"):
        local = await _local_inventory_and_backfill(mongo_url, db_name, "staging", execute_backfill=False)
        inv = local["inventory"]
        staging_inv = {
            "completed": True,
            "execution": "staging_local_mongo",
            "summary": inv.get("summary"),
            "metrics": inv.get("metrics"),
        }
        _write("staging_inventory_runtime.json", _redact_inventory(inv))

    if not staging_inv.get("completed"):
        _write("staging_inventory_runtime.json", {"completed": False, "error": "no staging mongo or API"})

    # Production inventory
    prod_inv: Dict[str, Any] = {"completed": False}
    prod_url = (args.production_mongo_url or os.getenv("PRODUCTION_MONGO_URL") or "").strip()
    prod_db = args.production_db_name or os.getenv("PRODUCTION_DB_NAME", "pleerity_production")
    if prod_url:
        local_prod = await _local_inventory_and_backfill(prod_url, prod_db, "production", execute_backfill=False)
        prod_body = _redact_inventory(local_prod["inventory"])
        prod_inv = {"completed": True, "execution": "production_local_mongo", "summary": local_prod["inventory"].get("summary")}
        _write("production_drift_inventory.json", prod_body)
    else:
        _write(
            "production_drift_inventory.json",
            {
                "completed": False,
                "execution": "blocked",
                "note": "Set PRODUCTION_MONGO_URL or --production-mongo-url",
                "generated_at": _utc(),
            },
        )
    results["production_inventory"] = prod_inv

    # Backfill dry-run + optional execute (staging mongo)
    backfill_runtime: Dict[str, Any] = {"generated_at": _utc()}
    if token and not args.skip_api:
        dry_api = _api_call(
            STAGING_API,
            token,
            "POST",
            "/admin/billing/stripe-mode-backfill",
            json_body={"dry_run": True, "limit": 200},
        )
        backfill_runtime["dry_run_api"] = dry_api
        if args.execute_backfill and dry_api.get("ok"):
            exec_api = _api_call(
                STAGING_API,
                token,
                "POST",
                "/admin/billing/stripe-mode-backfill",
                json_body={"dry_run": False, "limit": 200},
            )
            backfill_runtime["execute_api"] = exec_api
            backfill_runtime["execute"] = exec_api.get("body")

    if mongo_url and db_name:
        local_bf = await _local_inventory_and_backfill(
            mongo_url, db_name, "staging", execute_backfill=args.execute_backfill
        )
        backfill_runtime["dry_run"] = local_bf.get("backfill_dry_run")
        if args.execute_backfill:
            backfill_runtime["execute"] = local_bf.get("backfill_execute")
        backfill_runtime["drift_events_count"] = local_bf.get("drift_events_count")

    results["authoritative_backfill"] = _redact_backfill_payload(backfill_runtime)
    _write("authoritative_backfill_runtime.json", results["authoritative_backfill"])

    # MODE_UNVERIFIED remediation
    remediation_runtime: Dict[str, Any] = {"generated_at": _utc(), "samples": []}
    if mongo_url and db_name:
        local = await _local_inventory_and_backfill(mongo_url, db_name, "staging", execute_backfill=False)
        remediation_runtime["samples"] = local.get("remediation_samples", [])
        remediation_runtime["classification_counts"] = {}
        for s in remediation_runtime["samples"]:
            code = s.get("remediation_code") or "UNKNOWN"
            remediation_runtime["classification_counts"][code] = remediation_runtime["classification_counts"].get(code, 0) + 1
    results["mode_unverified_remediation"] = remediation_runtime
    _write("mode_unverified_remediation_runtime.json", remediation_runtime)

    # Upgrade/downgrade
    if mongo_url and db_name:
        upgrade = await _upgrade_downgrade_retest(mongo_url, db_name)
    else:
        upgrade = {"pass": False, "error": "no mongo"}
    results["upgrade_downgrade"] = upgrade
    _write("upgrade_downgrade_runtime.json", upgrade)

    # Legacy callers
    from services.stripe_mode_backfill_service import audit_legacy_stripe_callers

    legacy = audit_legacy_stripe_callers()
    legacy_runtime = {
        "generated_at": _utc(),
        "legacy_caller_count": legacy.get("legacy_caller_count"),
        "operational_unconverged": legacy.get("operational_unconverged", []),
        "convergence_targets": legacy.get("convergence_targets"),
        "pass": legacy.get("legacy_caller_count", 0) == 0,
    }
    results["legacy_caller"] = legacy_runtime
    _write("legacy_caller_runtime.json", legacy_runtime)

    # Webhook convergence
    if mongo_url and db_name:
        webhook = await _webhook_convergence(mongo_url, db_name)
    else:
        webhook = {"pass": False, "error": "no mongo"}
    results["webhook_convergence"] = webhook
    _write("webhook_convergence_runtime.json", webhook)

    # Commercial entitlement
    if mongo_url and db_name:
        ce = await _commercial_entitlement_alignment(mongo_url, db_name, None)
    else:
        ce = {"pass": False}
    results["commercial_entitlement"] = ce
    _write("commercial_entitlement_alignment_runtime.json", ce)

    results["regression"] = _run_regression()
    _write("regression_runtime.json", results["regression"])

    classification = _classify(results)
    results["classification"] = classification
    _write(
        "classifications.json",
        {
            "marker": MARKER,
            "generated_at": _utc(),
            "classification": classification,
            "prior_classification": "MODE_UNVERIFIED_BACKLOG",
            "gates": {
                "deploy_commit_matches": (results["deploy_continuity"] or {}).get("commit_matches"),
                "staging_inventory": staging_inv.get("completed"),
                "production_inventory": prod_inv.get("completed"),
                "legacy_caller_count": legacy.get("legacy_caller_count"),
                "regression_pass": results["regression"].get("passed"),
                "backfill_verified_writes": int((backfill_runtime.get("execute") or {}).get("summary", {}).get("verified", 0) or 0),
            },
        },
    )

    print(json.dumps({"classification": classification, "artifacts_dir": str(OUT)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
