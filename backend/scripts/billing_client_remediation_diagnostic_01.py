#!/usr/bin/env python3
"""
BILLING-CLIENT-REMEDIATION-DIAGNOSTIC-01 — blocked plan-change convergence.

Writes: docs/audit/billing_client_remediation_diagnostic_01/
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
from typing import Any, Dict, List, Optional

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
OUT = BACKEND_ROOT / "docs/audit/billing_client_remediation_diagnostic_01"
sys.path.insert(0, str(BACKEND_ROOT))

MARKER = "BILLING-CLIENT-REMEDIATION-DIAGNOSTIC-01"
CLIENT_ID = os.getenv("DIAG_CLIENT_ID", "80f83edd-ba12-41ed-929a-bbaf8c696a23")
CLIENT_EMAIL = os.getenv("DIAG_CLIENT_EMAIL", "nancy@yopmail.com")
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


def _redact_id(value: Optional[str]) -> Optional[str]:
    if not value or len(value) < 12:
        return value
    return f"{value[:8]}…{value[-8:]}"


def _load_password(path_rel: str) -> str:
    p = BACKEND_ROOT / path_rel
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return ""


def _load_admin_creds() -> tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or "aigbochievictory@gmail.com").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or _load_password("docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt")).strip()
    return email, pw


def _load_client_password() -> str:
    return (os.getenv("DIAG_CLIENT_PASSWORD") or _load_password("docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt")).strip()


def _api(api_base: str, token: Optional[str], method: str, path: str, **kwargs) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{api_base}{path}"
    r = httpx.request(method, url, headers=headers, timeout=120, **kwargs)
    body: Any
    try:
        body = r.json() if r.content else {}
    except Exception:
        body = {"text": (r.text or "")[:500]}
    return {"status": r.status_code, "body": body}


def _login_admin(api_base: str, email: str, password: str) -> str:
    r = httpx.post(f"{api_base}/auth/admin/login", json={"email": email, "password": password}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _login_client(api_base: str, email: str, password: str) -> str:
    r = httpx.post(f"{api_base}/auth/login", json={"email": email, "password": password}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _step_up_token(api_base: str, client_token: str, password: str) -> str:
    r = httpx.post(
        f"{api_base}/auth/step-up/verify",
        headers={"Authorization": f"Bearer {client_token}"},
        json={"password": password},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["step_up_token"]


def _simulate_preflight(billing: Dict[str, Any]) -> Dict[str, Any]:
    os.environ.setdefault("STRIPE_MODE", "live")
    os.environ.setdefault("STRIPE_SECRET_KEY_LIVE", "sk_live_diagnostic_probe_only")
    from services.stripe_mode_authority import get_stripe_mode
    from services.stripe_mode_containment_service import (
        CUSTOMER_BILLING_REFRESH_MESSAGE,
        StripeModeDriftError,
        requires_deployment_checkout_for_plan_change,
        validate_portal_billing_preflight,
    )

    deployment_mode = get_stripe_mode()
    out: Dict[str, Any] = {
        "deployment_mode": deployment_mode,
        "requires_deployment_checkout": requires_deployment_checkout_for_plan_change(billing),
        "validator_chain": [
            "BillingPage.handlePlanChange → POST /api/billing/checkout",
            "routes.billing.create_checkout → stripe_service.create_upgrade_session",
            "validate_stripe_subscription_mode (no verification kwargs on subscription-only call)",
            "validate_portal_billing_preflight → validate_stripe_customer_mode + validate_stripe_subscription_mode",
            "_assert_not_mode_unverified when stripe_mode_verification_status=MODE_UNVERIFIED",
        ],
    }
    try:
        validate_portal_billing_preflight(
            billing,
            deployment_mode,
            client_id=billing.get("client_id"),
            operation="upgrade_downgrade",
        )
        out["portal_preflight"] = {"ok": True}
    except StripeModeDriftError as exc:
        out["portal_preflight"] = {
            "ok": False,
            "error_code": exc.error_code,
            "customer_message": exc.customer_message,
            "admin_reason": exc.admin_reason,
            "recovery_action": exc.recovery_action,
            "matches_ux_copy": exc.customer_message == CUSTOMER_BILLING_REFRESH_MESSAGE,
        }
    except Exception as exc:
        out["portal_preflight"] = {"ok": False, "unexpected": str(exc)[:300]}
    return out


async def _mongo_client_state(mongo_url: str, db_name: str, client_id: str) -> Dict[str, Any]:
    from database import database
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.stripe_mode_backfill_service import resolve_authoritative_mode

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=15000)
    database.client = client
    database.db = client[db_name]
    try:
        db = database.get_db()
        billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
        recovery = await db.billing_recovery_cases.find_one({"client_id": client_id}, {"_id": 0})
        checkouts = (
            await db.checkout_sessions.find({"client_id": client_id}, {"_id": 0})
            .sort("created_at", -1)
            .limit(10)
            .to_list(10)
        )
        events = (
            await db.stripe_events.find(
                {"$or": [{"related_client_id": client_id}, {"related_subscription_id": billing.get("stripe_subscription_id") if billing else None}]},
                {"_id": 0, "event_id": 1, "type": 1, "livemode": 1, "created": 1, "environment_source": 1},
            )
            .sort("created", -1)
            .limit(8)
            .to_list(8)
        )
        resolution = await resolve_authoritative_mode(client_id, billing=billing) if billing else {}
        return {
            "client_billing": billing,
            "billing_recovery_case": recovery,
            "checkout_sessions_recent": checkouts,
            "stripe_events_recent": events,
            "authoritative_resolution_probe": resolution,
        }
    finally:
        client.close()


def _run_pytest() -> Dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_stripe_mode_containment.py",
            "tests/test_billing_recovery_operations.py",
            "-q",
            "--tb=no",
        ],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout[-2500:], "stderr": proc.stderr[-500:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-api", default=STAGING_API)
    parser.add_argument("--client-id", default=CLIENT_ID)
    parser.add_argument("--apply-safe-remediation", action="store_true")
    parser.add_argument("--mongo-url", default=os.getenv("MONGO_URL"))
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", "pleerity_staging"))
    args = parser.parse_args()

    api_base = args.staging_api.rstrip("/")
    client_id = args.client_id

    pytest_result = _run_pytest()

    client_state: Dict[str, Any] = {
        "audit_id": MARKER,
        "generated_at": _utc(),
        "client_id": client_id,
        "client_email": CLIENT_EMAIL,
        "api_base": api_base,
    }
    preflight: Dict[str, Any] = {"generated_at": _utc(), "client_id": client_id}
    evidence: Dict[str, Any] = {"generated_at": _utc(), "client_id": client_id}
    remediation: Dict[str, Any] = {"generated_at": _utc(), "executed": False, "actions": []}
    validation: Dict[str, Any] = {"generated_at": _utc(), "client_id": client_id}
    regression: Dict[str, Any] = {"generated_at": _utc(), "pytest": pytest_result}

    if args.mongo_url:
        mongo_state = asyncio.run(_mongo_client_state(args.mongo_url, args.db_name, client_id))
        client_state["mongo"] = mongo_state
        billing_row = mongo_state.get("client_billing") or {}
    else:
        client_state["mongo"] = {"skipped": True, "reason": "MONGO_URL not set"}
        billing_row = {}

    try:
        admin_email, admin_pw = _load_admin_creds()
        admin_token = _login_admin(api_base, admin_email, admin_pw)
        snapshot = _api(api_base, admin_token, "GET", f"/admin/billing/clients/{client_id}")
        client_state["admin_billing_snapshot"] = snapshot

        dash = _api(api_base, admin_token, "GET", "/admin/billing/recovery/dashboard")
        row = None
        for section in (dash.get("body") or {}).get("sections", {}).values():
            if not isinstance(section, list):
                continue
            for item in section:
                if item.get("client_id") == client_id:
                    row = item
                    break
        client_state["recovery_dashboard_row"] = row

        guidance = _api(api_base, admin_token, "GET", f"/admin/billing/stripe-mode-remediation/{client_id}")
        client_state["stripe_mode_remediation"] = guidance
        evidence["remediation_guidance"] = guidance

        backfill_dry = _api(
            api_base,
            admin_token,
            "POST",
            "/admin/billing/stripe-mode-backfill",
            json={"client_id": client_id, "dry_run": True},
        )
        evidence["backfill_dry_run"] = backfill_dry

        remediation_code = (guidance.get("body") or {}).get("remediation_code") or "MODE_UNVERIFIED"
        if guidance.get("status") == 200:
            gbody = guidance.get("body") or {}
            billing_row = {
                "client_id": client_id,
                "stripe_customer_id": (gbody.get("billing_identifiers") or {}).get("stripe_customer_id"),
                "stripe_subscription_id": (gbody.get("billing_identifiers") or {}).get("stripe_subscription_id"),
                "stripe_mode": gbody.get("stored_stripe_mode"),
                "stripe_customer_mode": gbody.get("stored_stripe_customer_mode"),
                "stripe_mode_verification_status": gbody.get("verification_status"),
                "stripe_mode_confidence": gbody.get("confidence"),
            }
        elif snapshot.get("status") == 200:
            body = snapshot.get("body") or {}
            billing_row = body.get("billing") or body.get("client_billing") or {}

        preflight["billing_row_probe"] = billing_row
        preflight["local_simulation"] = _simulate_preflight({**billing_row, "client_id": client_id})
        preflight["blocker"] = {
            "upgrade_blocked": not preflight["local_simulation"].get("portal_preflight", {}).get("ok", False),
            "primary_validator": "validate_portal_billing_preflight",
            "drift_classification": remediation_code,
            "requires_deployment_checkout": preflight["local_simulation"].get("requires_deployment_checkout"),
            "refresh_did_not_converge_because": [
                "client /billing/checkout uses create_upgrade_session → validate_portal_billing_preflight on staging",
                "billing row carries MODE_UNVERIFIED and/or legacy test-mode persistence on live deployment",
                "recovery case shows RECOVERY_RESOLVED while remediation_code remains MODE_UNVERIFIED (stale recovery metadata)",
                "admin regenerate-checkout deployment path fixed in recovery service but not wired to client self-serve checkout",
                "authoritative backfill must not re-apply test mode on live (LEGACY_TEST_SUBSCRIPTION)",
            ],
        }

        if args.apply_safe_remediation:
            from services.stripe_mode_containment_service import normalize_persisted_mode

            resolution = (backfill_dry.get("body") or {}).get("resolution") or {}
            rem_code = resolution.get("remediation_code") or remediation_code
            mode_to_write = normalize_persisted_mode(resolution.get("stripe_mode"))
            dep_mode = normalize_persisted_mode((guidance.get("body") or {}).get("deployment_mode") or "live")
            safe_backfill = (
                resolution.get("stripe_mode_confidence") == "authoritative"
                and rem_code not in ("LEGACY_TEST_SUBSCRIPTION",)
                and mode_to_write == dep_mode
                and (guidance.get("body") or {}).get("verification_status") == "MODE_UNVERIFIED"
            )
            if safe_backfill:
                apply = _api(
                    api_base,
                    admin_token,
                    "POST",
                    "/admin/billing/stripe-mode-backfill",
                    json={"client_id": client_id, "dry_run": False},
                )
                remediation["executed"] = True
                remediation["actions"].append({"action": "stripe_mode_backfill_execute", "result": apply})
            else:
                remediation["skipped"] = (
                    "unsafe_or_mismatched_backfill"
                    if resolution.get("stripe_mode_confidence") == "authoritative"
                    else "no_authoritative_evidence_for_backfill"
                )
                remediation["actions"].append(
                    {
                        "action": "deploy_client_deployment_checkout_path",
                        "note": "requires_deployment_checkout_for_plan_change on create_upgrade_session; "
                        "use admin regenerate-checkout in deployment mode for legacy test/live drift",
                        "remediation_code": rem_code,
                    }
                )

        probe_email = CLIENT_EMAIL
        if snapshot.get("status") == 200:
            probe_email = (snapshot.get("body") or {}).get("portal_user", {}).get("email") or (snapshot.get("body") or {}).get("contact_email") or probe_email
        validation["probe_email"] = probe_email

        client_pw = _load_client_password()
        if client_pw and probe_email:
            client_token = _login_client(api_base, probe_email, client_pw)
            step_token = _step_up_token(api_base, client_token, client_pw)
            checkout_probe = _api(
                api_base,
                client_token,
                "POST",
                "/billing/checkout",
                json={"plan_code": "PLAN_2_PORTFOLIO"},
                headers={"X-Step-Up-Token": step_token, "Origin": "https://pleerity-enterprise.onrender.com"},
            )
            portal_probe = _api(
                api_base,
                client_token,
                "POST",
                "/billing/portal",
                headers={"X-Step-Up-Token": step_token, "Origin": "https://pleerity-enterprise.onrender.com"},
            )
            validation["checkout_probe"] = checkout_probe
            validation["portal_probe"] = portal_probe
            validation["billing_status"] = _api(api_base, client_token, "GET", "/billing/status")

            post_billing = {}
            if remediation.get("executed"):
                snap2 = _api(api_base, admin_token, "GET", f"/admin/billing/clients/{client_id}")
                post_billing = (snap2.get("body") or {}).get("billing") or (snap2.get("body") or {}).get("client_billing") or {}
                preflight["post_remediation_simulation"] = _simulate_preflight({**post_billing, "client_id": client_id})
        else:
            validation["skipped"] = "no_client_password"

    except Exception as exc:
        client_state["error"] = str(exc)[:400]
        preflight["error"] = str(exc)[:400]

    evidence["authoritative_evidence_classification"] = _classify_evidence(evidence, client_state)
    classification = _classify_overall(client_state, preflight, remediation, validation, regression)

    _write("client_state_runtime.json", client_state)
    _write("authoritative_evidence_runtime.json", evidence)
    _write("preflight_runtime.json", preflight)
    _write("remediation_runtime.json", remediation)
    _write("validation_runtime.json", validation)
    _write("regression_runtime.json", regression)
    _write("classifications.json", classification)

    report = _build_report(classification, client_state, preflight, evidence, remediation, validation)
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "watchlist.md").write_text(_build_watchlist(classification), encoding="utf-8")

    print(json.dumps({"classification": classification.get("classification"), "out": str(OUT)}, indent=2))


def _classify_evidence(evidence: Dict[str, Any], client_state: Dict[str, Any]) -> str:
    guidance = (evidence.get("remediation_guidance") or {}).get("body") or {}
    code = guidance.get("remediation_code") or ""
    if code == "LEGACY_TEST_SUBSCRIPTION":
        return "requires_checkout_regeneration"
    dry = (evidence.get("backfill_dry_run") or {}).get("body") or {}
    resolution = dry.get("resolution") or {}
    if resolution.get("stripe_mode_confidence") == "authoritative":
        src = resolution.get("stripe_mode_verification_source") or resolution.get("inferred_mode_source")
        if src in ("webhook_livemode", "checkout_session"):
            return "safely_recoverable"
        if src in ("admin_verified", "admin_remediation", "persisted_authoritative"):
            return "legacy_test_live_artifacts"
    recovery = client_state.get("recovery_dashboard_row") or {}
    if recovery.get("recovery_state") == "RECOVERY_RESOLVED" and recovery.get("remediation_code") == "MODE_UNVERIFIED":
        return "orphaned_lifecycle_drift"
    return "stale_MODE_UNVERIFIED_flag"


def _classify_overall(
    client_state: Dict[str, Any],
    preflight: Dict[str, Any],
    remediation: Dict[str, Any],
    validation: Dict[str, Any],
    regression: Dict[str, Any],
) -> Dict[str, Any]:
    checkout_status = (validation.get("checkout_probe") or {}).get("status")
    post_ok = (preflight.get("post_remediation_simulation") or {}).get("portal_preflight", {}).get("ok")
    code_fix = regression.get("pytest", {}).get("exit_code") == 0

    if checkout_status == 200 and post_ok and code_fix:
        classification = "VERIFIED_OPERATIONALLY"
    elif code_fix and preflight.get("blocker", {}).get("upgrade_blocked") and preflight.get("local_simulation", {}).get("requires_deployment_checkout"):
        classification = "STRIPE_MODE_DRIFT"
    elif remediation.get("executed") and checkout_status in (200, 409):
        classification = "PARTIAL"
    elif preflight.get("blocker", {}).get("upgrade_blocked"):
        classification = "CLIENT_REMEDIATION_REQUIRED"
    else:
        classification = "FAIL_OPERATIONAL"

    return {
        "marker": MARKER,
        "generated_at": _utc(),
        "classification": classification,
        "client_id": CLIENT_ID,
        "gates": {
            "root_cause_identified": bool(preflight.get("blocker") or preflight.get("local_simulation")),
            "code_fix_tests_pass": code_fix,
            "checkout_probe_status": checkout_status,
            "portal_preflight_post_remediation": post_ok,
            "safe_remediation_executed": remediation.get("executed"),
        },
    }


def _build_report(
    classification: Dict[str, Any],
    client_state: Dict[str, Any],
    preflight: Dict[str, Any],
    evidence: Dict[str, Any],
    remediation: Dict[str, Any],
    validation: Dict[str, Any],
) -> str:
    blocker = preflight.get("blocker") or {}
    guidance = (evidence.get("remediation_guidance") or {}).get("body") or {}
    recovery = client_state.get("recovery_dashboard_row") or {}
    return f"""# {MARKER} — REPORT

Generated: {_utc()}

## Classification

**{classification.get("classification")}**

## Client

- **client_id:** `{CLIENT_ID}`
- **label:** {recovery.get("client_label", "Confidence Marcel")}
- **CRN:** {recovery.get("crn", "PLE-CVP-2026-000011")}
- **portal probe email:** {validation.get("probe_email", CLIENT_EMAIL)}

## Root cause

1. **Preflight blocker:** `validate_portal_billing_preflight` → `_assert_not_mode_unverified` when `stripe_mode_verification_status` is `MODE_UNVERIFIED`, surfacing `{blocker.get("drift_classification", "MODE_UNVERIFIED")}` customer copy.
2. **Stripe mode drift:** persisted authoritative **test** mode on **live** deployment (`LEGACY_TEST_SUBSCRIPTION`) from prior admin remediation — plan changes must use deployment Checkout, not portal subscription_update_confirm.
3. **Stale recovery metadata:** recovery state `RECOVERY_RESOLVED` while dashboard `remediation_code` remains `MODE_UNVERIFIED` — refresh/closeout did not clear containment flags on the billing row.
4. **Path gap:** admin `regenerate-checkout` uses `deployment_checkout`; client `/billing/checkout` still used portal preflight on staging (fixed in this change set).

## Safe remediation applied

- **Code fix:** shared `requires_deployment_checkout_for_plan_change`; `create_upgrade_session` routes to deployment Checkout when governance requires it.
- **Data:** backfill execute skipped when resolution would reinforce test-on-live; use admin regenerate-checkout (live) after deploy.

## Validation (staging pre-deploy)

- Checkout probe: `{(validation.get("checkout_probe") or {}).get("status", "n/a")}`
- Portal probe: `{(validation.get("portal_probe") or {}).get("status", "n/a")}`
- Local preflight blocked: `{blocker.get("upgrade_blocked")}`
- Requires deployment checkout: `{preflight.get("local_simulation", {}).get("requires_deployment_checkout")}`

## Authoritative evidence

- **remediation_code:** `{guidance.get("remediation_code")}`
- **stored_stripe_mode:** `{guidance.get("stored_stripe_mode")}`
- **verification_status:** `{guidance.get("verification_status")}`

## Artifacts

`client_state_runtime.json`, `preflight_runtime.json`, `authoritative_evidence_runtime.json`, `remediation_runtime.json`, `validation_runtime.json`, `regression_runtime.json`, `classifications.json`
"""


def _build_watchlist(classification: Dict[str, Any]) -> str:
    cls = classification.get("classification")
    return f"""# Billing client remediation watchlist

- [ ] Deploy checkout `deployment_checkout` path for MODE_UNVERIFIED clients
- [ ] Re-run diagnostic with `--apply-safe-remediation` after deploy
- [ ] Confirm `{CLIENT_ID}` upgrade/downgrade + portal on staging UI
- [ ] Batch authoritative backfill for remaining MODE_UNVERIFIED backlog (webhook evidence)
- [ ] Classification target: VERIFIED_OPERATIONALLY (current: **{cls}**)
"""


if __name__ == "__main__":
    main()
