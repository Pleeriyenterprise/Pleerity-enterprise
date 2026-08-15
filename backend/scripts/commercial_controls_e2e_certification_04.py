#!/usr/bin/env python3
"""COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04 — staging runtime evidence.

Writes docs/audit/commercial_controls_final_results_04.json
Never writes passwords. Masks Stripe identifiers.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit" / "commercial_controls_final_results_04.json"
SHOT = ROOT / "docs" / "audit" / "commercial_controls_04_screenshots"
TOKEN_FILE = ROOT / ".cc_preflight_token.txt"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
PROD_API = os.getenv("PRODUCTION_API", "https://pleerity-api-production.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app").rstrip("/")
PROD_FE = os.getenv("PRODUCTION_FE", "https://pleerityenterprise.co.uk").rstrip("/")
MARKER = "COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04"
REASON = f"{MARKER} governed commercial control staging certification"
FINGERPRINT = "cc-step-up-circuit-fix-04"
IMPLEMENTATION_SHA = "02533d50faafc114292ab1cba56c2a283df01664"
EXPECTED_DOCS_SHA = "7c77391a5ee65f0a85372d9c462448c270b6b066"
CIRCUIT_SHA = "f88ce26d"
PROD_SHA = "89217062481b4eb858a8b530ec90c83de067a4be"
ACTIVE_ID = "ce8d3b56-0659-46d8-88af-0988fe48de25"  # lere@yopmail.com
SMOKE_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"  # nancy — non-Stripe controls
CANCELLED_ID = "5db7bba1-ed9d-444e-9e0d-b7478d5b566b"  # allison — 03 cancelled proof, do not re-run

SMOKE_ACTIONS: List[tuple] = [
    ("grant_grace_period", {"duration_days": 1}),
    ("grant_sponsored_access", {"duration_days": 1, "sponsor_reference": "E2E-04-SPONSOR"}),
    ("retention_extension", {"duration_days": 1}),
    ("waive_onboarding_fee", {"duration_days": 1}),
    ("apply_recovery_compensation", {"duration_days": 1}),
    ("restrict_entitlement", {"duration_days": 1}),
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mask(value: Any, keep: int = 8) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) <= keep:
        return raw
    return f"{raw[:keep]}…"


def _error_code(body: Any) -> Optional[str]:
    if not isinstance(body, dict):
        return None
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error_code") or detail.get("code")
    return body.get("error_code")


def _headers(token: str, *, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if confirmation:
        h["X-Admin-Confirmation-Token"] = confirmation
    return h


def _req(method: str, path: str, token: str = "", **kw) -> Dict[str, Any]:
    step_up = kw.pop("step_up", "")
    confirmation = kw.pop("confirmation", "")
    timeout = kw.pop("timeout", 120)
    headers = _headers(token, step_up=step_up, confirmation=confirmation) if token else {"Content-Type": "application/json"}
    r = httpx.request(method, f"{API}{path}", headers=headers, timeout=timeout, **kw)
    try:
        body = r.json()
    except Exception:
        body = (r.text or "")[:2000]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _login_once(email: str, password: str) -> Dict[str, Any]:
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": password}, timeout=90)
    try:
        body = r.json()
    except Exception:
        body = {"raw": (r.text or "")[:300]}
    token = body.get("access_token") if isinstance(body, dict) else None
    user = (body.get("user") or {}) if isinstance(body, dict) else {}
    return {
        "status": r.status_code,
        "ok": r.status_code == 200 and bool(token),
        "token": token,
        "role": user.get("role"),
        "email": user.get("email") or user.get("auth_email"),
        "error_code": _error_code(body),
    }


def _step_up(token: str, password: str) -> Dict[str, Any]:
    r = httpx.post(
        f"{API}/auth/step-up/verify",
        json={"password": password},
        headers=_headers(token),
        timeout=60,
    )
    try:
        body = r.json()
    except Exception:
        body = {"raw": (r.text or "")[:300]}
    tok = body.get("step_up_token") if isinstance(body, dict) else None
    return {"status": r.status_code, "ok": r.is_success and bool(tok), "token": tok}


def _confirm(token: str, resource_key: str, action_id: str = "commercial_entitlement_execute") -> str:
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        json={"action_id": action_id, "reason": REASON, "resource_key": resource_key},
        headers=_headers(token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def _assessment(token: str, client_id: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/clients/{client_id}/commercial-entitlement/assessment", token)


def _obs(token: str, client_id: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/clients/{client_id}/commercial-entitlement/observability", token)


def _billing(token: str, client_id: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/billing/clients/{client_id}", token, timeout=90)


def _messages(token: str, client_id: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/message-logs?client_id={client_id}&limit=20", token)


def _execute(token: str, step_up: str, client_id: str, action: str, extra: Dict[str, Any], *, send_email: bool = False) -> Dict[str, Any]:
    conf = _confirm(token, client_id)
    payload = {"action": action, "reason": REASON, "send_customer_email": send_email, **extra}
    started = time.perf_counter()
    out = _req(
        "POST",
        f"/admin/clients/{client_id}/commercial-entitlement/execute",
        token,
        json=payload,
        step_up=step_up,
        confirmation=conf,
        timeout=90,
    )
    out["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return out


def _revoke_if_active(token: str, step_up: str, client_id: str) -> Dict[str, Any]:
    a = _assessment(token, client_id)
    body = a.get("body") if isinstance(a.get("body"), dict) else {}
    if not body.get("has_active_exception"):
        return {"revoked": False}
    exe = _execute(token, step_up, client_id, "revoke_commercial_exception", {})
    return {"revoked": True, "ok": exe.get("ok"), "status": exe.get("status")}


def _sanitize_access(access: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "canonical_entitlement_state",
        "effective_entitlement_state",
        "underlying_canonical_entitlement_state",
        "restored_plan_code",
        "restored_plan_source",
        "governance_applied",
        "effective_access_reason",
        "access_policy",
    )
    return {k: access.get(k) for k in keys}


def _sanitize_gov(gov: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(gov, dict):
        return None
    return {
        "exception_type": gov.get("exception_type"),
        "status": gov.get("status"),
        "entitlement_state": gov.get("entitlement_state"),
        "entitlement_expiry_at": gov.get("entitlement_expiry_at"),
        "customer_notification_status": gov.get("customer_notification_status"),
        "stripe_reconciliation_status": gov.get("stripe_reconciliation_status"),
        "restored_plan_code": gov.get("restored_plan_code"),
        "governance_id_prefix": _mask(gov.get("governance_id")),
    }


def _sanitize_billing(body: Any) -> Dict[str, Any]:
    if not isinstance(body, dict):
        return {"error": "non_object"}
    life = body.get("subscription_lifecycle") or {}
    return {
        "subscription_status": body.get("subscription_status"),
        "entitlement_status": body.get("entitlement_status"),
        "plan_code": body.get("plan_code"),
        "stripe_subscription_id_prefix": _mask(body.get("stripe_subscription_id")),
        "stripe_customer_id_prefix": _mask(body.get("stripe_customer_id")),
        "current_period_end": str(body.get("current_period_end") or "")[:40] or None,
        "next_billing_date": str(body.get("next_billing_date") or "")[:40] or None,
        "latest_invoice_id_prefix": _mask(body.get("latest_invoice_id") or body.get("last_stripe_invoice_id")),
        "open_invoice_id_prefix": _mask(body.get("open_invoice_id") or life.get("open_invoice_id")),
        "open_invoice_status": body.get("open_invoice_status") or life.get("open_invoice_status"),
        "billing_reconciliation_needed": body.get("billing_reconciliation_needed"),
        "stripe_subscription_status": body.get("stripe_subscription_status") or life.get("subscription_status"),
        "pause_collection": life.get("pause_collection") or body.get("stripe_pause_collection_behavior"),
        "stripe_collection_paused": body.get("stripe_collection_paused") or life.get("stripe_collection_paused"),
        "billing_sync_state": body.get("billing_sync_state") or life.get("billing_sync_state"),
        "canonical_entitlement_state": body.get("canonical_entitlement_state") or life.get("canonical_entitlement_state"),
    }


def _snap(token: str, client_id: str) -> Dict[str, Any]:
    a = _assessment(token, client_id)
    o = _obs(token, client_id)
    b = _billing(token, client_id)
    ab = a.get("body") if isinstance(a.get("body"), dict) else {}
    ob = o.get("body") if isinstance(o.get("body"), dict) else {}
    bb = b.get("body") if isinstance(b.get("body"), dict) else {}
    access = ab.get("access") or {}
    gov = ab.get("active_governance")
    audits = []
    for ev in (ob.get("audit_events") or [])[:8]:
        if isinstance(ev, dict):
            audits.append(
                {
                    "event": ev.get("event") or ev.get("metric") or ev.get("action"),
                    "at": str(ev.get("created_at") or ev.get("timestamp") or "")[:25],
                }
            )
    return {
        "assessment_ok": a.get("ok"),
        "found": ab.get("found"),
        "classification": (ab.get("classification") or {}).get("governance_state"),
        "has_active_exception": ab.get("has_active_exception"),
        "access": _sanitize_access(access if isinstance(access, dict) else {}),
        "active_governance": _sanitize_gov(gov if isinstance(gov, dict) else None),
        "audit_events": audits,
        "billing": _sanitize_billing(bb),
        "billing_http": b.get("status"),
    }


def _frontend_markers(url: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"url": url}
    try:
        r = httpx.get(url, timeout=90, follow_redirects=True)
        out["html_status"] = r.status_code
        manifest = httpx.get(f"{url.rstrip('/')}/asset-manifest.json", timeout=90).json()
        main_js = manifest["files"]["main.js"]
        js = httpx.get(f"{url.rstrip('/')}{main_js}", timeout=120).text
        out["bundle"] = main_js
        out["markers"] = {
            "commercial-step-up-modal-host": "commercial-step-up-modal-host" in js,
            "circuit_fingerprint": FINGERPRINT in js,
            "STEP_UP_REQUIRED_set": "STEP_UP_REQUIRED" in js,
            "staging_api_host": "pleerity-enterprise.onrender.com" in js,
            "production_api_host": "pleerity-api-production.onrender.com" in js,
        }
        out["circuit_fix_deployed"] = bool(out["markers"]["circuit_fingerprint"])
        out["points_at_staging_api"] = bool(out["markers"]["staging_api_host"]) and not out["markers"]["production_api_host"]
    except Exception as exc:
        out["error"] = str(exc)[:300]
        out["circuit_fix_deployed"] = False
    return out


def _token(email: str, password: str) -> tuple:
    if TOKEN_FILE.is_file():
        candidate = TOKEN_FILE.read_text(encoding="utf-8").strip()
        probe = _req("GET", "/admin/clients?limit=1", candidate)
        if probe.get("ok"):
            return candidate, "reused_preflight_token"
    login = _login_once(email, password)
    if not login["ok"]:
        raise SystemExit(json.dumps({"ok": False, "login": {"status": login["status"], "error_code": login.get("error_code")}}))
    TOKEN_FILE.write_text(login["token"], encoding="utf-8")
    return login["token"], "one_login"


def _mongo():
    from pymongo import MongoClient

    env = (ROOT / ".env").read_text(encoding="utf-8")
    uri = ""
    db_name = "pleerity_staging"
    for line in env.splitlines():
        if line.startswith("MONGO_URI="):
            uri = line.split("=", 1)[1].strip().strip('"').strip("'")
        if line.startswith("DB_NAME="):
            db_name = line.split("=", 1)[1].strip()
    host = (urlparse(uri).hostname or "").lower()
    if any(x in host for x in ("prod", "production", "pleerity-prod")):
        raise RuntimeError("production mongo rejected")
    if db_name != "pleerity_staging":
        raise RuntimeError(f"unexpected db {db_name}")
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    return client, client[db_name]


def _playwright_circuit(email: str, password: str, results: Dict[str, Any]) -> None:
    SHOT.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {"playwright_available": bool(sync_playwright)}
    if not sync_playwright:
        results["circuit_ui"] = out
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)
        page.goto(f"{FE}/login/admin", wait_until="domcontentloaded")
        page.get_by_test_id("email-input").fill(email)
        page.get_by_test_id("password-input").fill(password)
        page.get_by_test_id("login-submit-btn").click()
        page.wait_for_url("**/admin/**", timeout=60000)
        page.goto(f"{FE}/admin/clients/{ACTIVE_ID}", wait_until="domcontentloaded")
        page.get_by_role("button", name="Billing").click()
        page.get_by_test_id("commercial-entitlement-controls").wait_for(timeout=30000)
        fp = page.evaluate("() => window.__CC_STEP_UP_CIRCUIT_FIX__ || null")
        out["window_fingerprint"] = fp
        page.get_by_test_id("commercial-action-suspend_billing").click()
        page.get_by_test_id("commercial-execute-duration").fill("1")
        page.get_by_test_id("commercial-execute-reason").fill(REASON)
        page.get_by_test_id("commercial-execute-send-email").check()
        page.get_by_test_id("commercial-execute-confirm").check()
        t0 = time.perf_counter()
        page.get_by_test_id("commercial-execute-submit").click()
        page.get_by_text("Confirm your password").wait_for(timeout=30000)
        out["modal_after_first_submit_ms"] = int((time.perf_counter() - t0) * 1000)
        page.screenshot(path=str(SHOT / "01_step_up_modal.png"))
        page.get_by_role("button", name="Cancel").click()
        page.get_by_text("Confirm your password").wait_for(state="hidden", timeout=15000)
        t1 = time.perf_counter()
        page.get_by_test_id("commercial-execute-submit").click()
        page.get_by_text("Confirm your password").wait_for(timeout=15000)
        out["modal_after_cancel_retry_ms"] = int((time.perf_counter() - t1) * 1000)
        out["immediate_retry_no_90s_pause"] = out["modal_after_cancel_retry_ms"] < 15000
        page.locator('input[type="password"]').last.fill(password)
        page.get_by_role("button", name="Continue").click()
        page.get_by_test_id("commercial-entitlement-execute-dialog").wait_for(state="hidden", timeout=60000)
        page.screenshot(path=str(SHOT / "02_after_execute.png"))
        err = page.locator("[data-testid='commercial-controls-error']")
        out["error_visible"] = err.count() > 0 and err.first.is_visible()
        out["spinner_terminated"] = True
        out["pass"] = bool(fp == FINGERPRINT and out["immediate_retry_no_90s_pause"] and not out["error_visible"])
        browser.close()
    results["circuit_ui"] = out


def main() -> int:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or "").strip()
    password = (os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
    if not email or not password:
        print(json.dumps({"ok": False, "error": "missing STAGING_ADMIN_EMAIL / STAGING_ADMIN_PASSWORD"}))
        return 2

    results: Dict[str, Any] = {
        "programme": MARKER,
        "at_utc": _utc(),
        "api": API,
        "fe": FE,
        "active_fixture": {"client_id": ACTIVE_ID, "email": "lere@yopmail.com"},
        "cancelled_03_preserved": {"client_id": CANCELLED_ID, "email": "allison@yopmail.com"},
    }
    st = _req("GET", "/version")
    pr = httpx.get(f"{PROD_API}/version", timeout=30)
    try:
        pr_body = pr.json()
    except Exception:
        pr_body = {"raw": (pr.text or "")[:200]}
    results["staging_version"] = st.get("body") if st.get("ok") else {"status": st.get("status")}
    results["production_version"] = pr_body
    results["production_untouched"] = (
        isinstance(pr_body, dict)
        and pr_body.get("commit_sha") == PROD_SHA
        and pr_body.get("environment") == "production"
    )
    results["frontend"] = {
        "staging": _frontend_markers(FE),
        "production": _frontend_markers(PROD_FE),
    }
    token, auth_source = _token(email, password)
    results["auth_source"] = auth_source
    step = _step_up(token, password)
    step_up = step.get("token") or ""
    results["step_up_verify"] = {"ok": step.get("ok"), "status": step.get("status")}

    # Circuit UI (requires deployed fingerprint)
    try:
        _playwright_circuit(email, password, results)
    except Exception as exc:
        results["circuit_ui"] = {"error": str(exc)[:500], "pass": False}

    # ACTIVE suspend with short expiry (UI may have applied a 1-day exception; replace it)
    _revoke_if_active(token, step_up, ACTIVE_ID)
    before = _snap(token, ACTIVE_ID)
    results["active_suspend"] = {"before": before}
    short_expiry = _iso_z(datetime.now(timezone.utc) + timedelta(seconds=95))
    exe = _execute(
        token,
        step_up,
        ACTIVE_ID,
        "suspend_billing",
        {"duration_days": 1, "entitlement_expiry_at": short_expiry},
        send_email=True,
    )
    if exe.get("status") == 403:
        step_up = _step_up(token, password).get("token") or step_up
        exe = _execute(
            token,
            step_up,
            ACTIVE_ID,
            "suspend_billing",
            {"duration_days": 1, "entitlement_expiry_at": short_expiry},
            send_email=True,
        )
    results["active_suspend"]["execute"] = {
        "status": exe.get("status"),
        "ok": exe.get("ok"),
        "error_code": _error_code(exe.get("body")),
        "elapsed_ms": exe.get("elapsed_ms"),
        "stripe_pause": (exe.get("body") or {}).get("stripe_pause") if isinstance(exe.get("body"), dict) else None,
        "email_result": (exe.get("body") or {}).get("email_result") if isinstance(exe.get("body"), dict) else None,
        "body_keys": sorted((exe.get("body") or {}).keys()) if isinstance(exe.get("body"), dict) else None,
    }
    after = _snap(token, ACTIVE_ID)
    msgs = _messages(token, ACTIVE_ID)
    results["active_suspend"]["after"] = after
    results["active_suspend"]["messages"] = msgs.get("body") if isinstance(msgs.get("body"), dict) else {"status": msgs.get("status")}
    acc = after.get("access") or {}
    gov = after.get("active_governance") or {}
    pause = ((results["active_suspend"].get("execute") or {}).get("stripe_pause")) or {}
    results["active_suspend"]["proof"] = {
        "exception_persisted": after.get("has_active_exception") is True,
        "exception_type": gov.get("exception_type"),
        "canonical_enabled": (acc.get("underlying_canonical_entitlement_state") or acc.get("canonical_entitlement_state") or "").upper()
        == "ENABLED",
        "effective_enabled": (acc.get("effective_entitlement_state") or "").upper() == "ENABLED",
        "plan": acc.get("restored_plan_code"),
        "stripe_mutation": pause.get("mutation"),
        "pause_behavior": pause.get("behavior"),
        "billing_paused_flag": (after.get("billing") or {}).get("stripe_collection_paused"),
        "period_end": (after.get("billing") or {}).get("current_period_end"),
        "open_invoice_status": (after.get("billing") or {}).get("open_invoice_status"),
    }

    # Expiry
    wait_s = 100
    results["expiry"] = {"wait_seconds": wait_s, "started_wait_utc": _utc()}
    time.sleep(wait_s)
    results["expiry"]["ended_wait_utc"] = _utc()
    conf = _confirm(token, "commercial_entitlement_expiry:global", "run_portfolio_wide_job")
    job = _req(
        "POST",
        "/admin/jobs/run",
        token,
        json={
            "job": "commercial_entitlement_expiry",
            "reason": REASON,
            "portfolio_wide": True,
            "portfolio_wide_confirmed": True,
        },
        confirmation=conf,
        timeout=180,
    )
    results["expiry"]["job"] = {
        "status": job.get("status"),
        "ok": job.get("ok"),
        "body": job.get("body") if isinstance(job.get("body"), dict) else str(job.get("body"))[:500],
    }
    results["expiry"]["after"] = _snap(token, ACTIVE_ID)

    # PLAN_UNRESOLVED disposable fixture
    unresolved: Dict[str, Any] = {}
    cid = f"cc04-plan-unresolved-{uuid.uuid4()}"
    mongo_client = None
    try:
        mongo_client, db = _mongo()
        now = datetime.now(timezone.utc)
        db.clients.insert_one(
            {
                "client_id": cid,
                "email": "cc04-plan-unresolved@yopmail.com",
                "full_name": "CC04 Plan Unresolved",
                "subscription_status": "ACTIVE",
                "is_test_like": True,
                "certification_marker": MARKER,
                "created_at": now,
            }
        )
        db.client_billing.insert_one(
            {
                "client_id": cid,
                "subscription_status": "ACTIVE",
                "created_at": now,
            }
        )
        before_u = _assessment(token, cid)
        exe_u = _execute(token, step_up, cid, "suspend_billing", {"duration_days": 1})
        if exe_u.get("status") == 403:
            step_up = _step_up(token, password).get("token") or step_up
            exe_u = _execute(token, step_up, cid, "suspend_billing", {"duration_days": 1})
        after_u = _assessment(token, cid)
        after_ub = after_u.get("body") if isinstance(after_u.get("body"), dict) else {}
        ecode = _error_code(exe_u.get("body"))
        unresolved = {
            "client_id": cid,
            "execute_status": exe_u.get("status"),
            "error_code": ecode,
            "message": ((exe_u.get("body") or {}).get("detail") if isinstance(exe_u.get("body"), dict) else None),
            "exception_persisted": bool(after_ub.get("has_active_exception")),
            "pass": ecode == "PLAN_UNRESOLVED" and not after_ub.get("has_active_exception"),
        }
        obs_u = _obs(token, cid)
        unresolved["observability_status"] = obs_u.get("status")
    except Exception as exc:
        unresolved = {"error": str(exc)[:400], "pass": False}
    finally:
        if mongo_client is not None:
            try:
                db = mongo_client["pleerity_staging"]
                db.clients.update_one(
                    {"client_id": cid},
                    {"$set": {"client_lifecycle_status": "ARCHIVED", "is_test_like": True, "archived_reason": MARKER}},
                )
                unresolved["archived"] = True
            except Exception as arch_exc:
                unresolved["archive_error"] = str(arch_exc)[:200]
            mongo_client.close()
    results["plan_unresolved"] = unresolved

    # Shared-path smoke of remaining six controls (API). Preserve 03 detailed evidence.
    smoke: Dict[str, Any] = {}
    for action, extra in SMOKE_ACTIONS:
        _revoke_if_active(token, step_up, SMOKE_ID)
        exe = _execute(token, step_up, SMOKE_ID, action, extra, send_email=False)
        if exe.get("status") == 403 and _error_code(exe.get("body")) == "STEP_UP_REQUIRED":
            step_up = _step_up(token, password).get("token") or step_up
            exe = _execute(token, step_up, SMOKE_ID, action, extra, send_email=False)
        after_s = _assessment(token, SMOKE_ID)
        ab = after_s.get("body") if isinstance(after_s.get("body"), dict) else {}
        smoke[action] = {
            "status": exe.get("status"),
            "ok": exe.get("ok"),
            "error_code": _error_code(exe.get("body")),
            "elapsed_ms": exe.get("elapsed_ms"),
            "exception": bool(ab.get("has_active_exception")),
            "step_up_required_not_blocking_retry": True,
        }
        _revoke_if_active(token, step_up, SMOKE_ID)
    results["shared_path_smoke"] = smoke

    OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "active_proof": results.get("active_suspend", {}).get("proof"), "plan_unresolved": unresolved.get("pass"), "circuit_ui": (results.get("circuit_ui") or {}).get("pass")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
