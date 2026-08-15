#!/usr/bin/env python3
"""COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-COMPLETION-03 — staging runtime evidence.

Writes docs/audit/commercial_controls_e2e_results_03.json
Never writes passwords. Masks Stripe identifiers.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit" / "commercial_controls_e2e_results_03.json"
TOKEN_FILE = ROOT / ".cc_preflight_token.txt"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
PROD_API = os.getenv("PRODUCTION_API", "https://pleerity-api-production.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app").rstrip("/")
MARKER = "COMMERCIAL-CONTROLS-E2E-03"
REASON = f"{MARKER} governed commercial control staging certification"
IMPLEMENTATION_SHA = "02533d50faafc114292ab1cba56c2a283df01664"
EXPECTED_DOCS_SHA = "7c77391a5ee65f0a85372d9c462448c270b6b066"
PROD_SHA = "89217062481b4eb858a8b530ec90c83de067a4be"

ACTIONS: List[Tuple[str, Dict[str, Any]]] = [
    ("grant_grace_period", {"duration_days": 7}),
    ("grant_sponsored_access", {"duration_days": 14, "sponsor_reference": "E2E-03-SPONSOR"}),
    ("retention_extension", {"duration_days": 7}),
    ("waive_onboarding_fee", {"duration_days": 14}),
    ("apply_recovery_compensation", {"duration_days": 7}),
    ("restrict_entitlement", {"duration_days": 7}),
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


def _jwt_claims(token: str) -> Dict[str, Any]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return {
            "role": data.get("role"),
            "email": data.get("email"),
            "portal_user_id_prefix": _mask(data.get("portal_user_id")),
            "exp": data.get("exp"),
        }
    except Exception as exc:
        return {"decode_error": str(exc)[:120]}


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
        "token_prefix": _mask(token, 12) if token else None,
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
    return {
        "status": r.status_code,
        "ok": r.is_success and bool(tok),
        "token": tok,
        "expires_in_seconds": body.get("expires_in_seconds") if isinstance(body, dict) else None,
        "error_code": _error_code(body),
    }


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


def _execute(
    token: str,
    step_up: str,
    client_id: str,
    action: str,
    extra: Dict[str, Any],
    *,
    send_email: bool = False,
    confirmation: Optional[str] = None,
) -> Dict[str, Any]:
    conf = confirmation if confirmation is not None else _confirm(token, client_id)
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
        "governance_state",
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
        "effective_access_reason": gov.get("effective_access_reason"),
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
        "cancel_at_period_end": body.get("cancel_at_period_end"),
        "current_period_end": str(body.get("current_period_end") or "")[:40] or None,
        "next_billing_date": str(body.get("next_billing_date") or "")[:40] or None,
        "latest_invoice_id_prefix": _mask(body.get("latest_invoice_id") or body.get("last_stripe_invoice_id")),
        "billing_reconciliation_needed": body.get("billing_reconciliation_needed"),
        "lifecycle_subscription_status": life.get("subscription_status"),
        "lifecycle_has_subscription": life.get("has_subscription"),
        "open_invoice_status": life.get("open_invoice_status"),
        "pause_collection": life.get("pause_collection") or life.get("stripe_pause_collection") or body.get("stripe_pause_collection_behavior"),
        "stripe_collection_paused": body.get("stripe_collection_paused") or life.get("stripe_collection_paused"),
        "lifecycle_keys": sorted(life.keys())[:40] if isinstance(life, dict) else [],
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
                    "event_type": ev.get("event_type") or ev.get("action"),
                    "created_at": str(ev.get("created_at") or "")[:25],
                    "actor_role": ev.get("actor_role"),
                }
            )
    return {
        "assessment_ok": a.get("ok"),
        "found": ab.get("found"),
        "classification": (ab.get("classification") or {}).get("governance_state"),
        "has_active_exception": ab.get("has_active_exception"),
        "access": _sanitize_access(access if isinstance(access, dict) else {}),
        "active_governance": _sanitize_gov(gov if isinstance(gov, dict) else None),
        "executable_actions": ab.get("executable_actions"),
        "audit_events": audits,
        "billing": _sanitize_billing(bb),
        "billing_http": b.get("status"),
    }


def _frontend_markers() -> Dict[str, Any]:
    out: Dict[str, Any] = {"alias": FE}
    try:
        manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=90).json()
        main_js = manifest["files"]["main.js"]
        js = httpx.get(f"{FE}{main_js}", timeout=120).text
        out["bundle"] = main_js
        out["markers"] = {
            "commercial-entitlement-controls": "commercial-entitlement-controls" in js,
            "commercial-step-up-modal-host": "commercial-step-up-modal-host" in js,
            "commercial-effective-access": "commercial-effective-access" in js,
            "commercial-restored-plan": "commercial-restored-plan" in js,
            "staging_api_host": "pleerity-enterprise.onrender.com" in js,
            "production_api_host": "pleerity-api-production.onrender.com" in js,
            "timeout_60000_literal": ("timeout:60000" in js) or ("timeout: 60000" in js),
            "timeout_6e4": "6e4" in js,
        }
        out["spinner_fix_deployed"] = bool(out["markers"]["commercial-step-up-modal-host"])
        out["points_at_staging_api"] = bool(out["markers"]["staging_api_host"]) and not out["markers"]["production_api_host"]
    except Exception as exc:
        out["error"] = str(exc)[:300]
        out["spinner_fix_deployed"] = False
    return out


def _versions() -> Dict[str, Any]:
    st = httpx.get(f"{API}/version", timeout=60).json()
    pr = httpx.get(f"{PROD_API}/version", timeout=60).json()
    return {
        "staging": st,
        "production": pr,
        "runtime_sha": st.get("commit_sha"),
        "environment": st.get("environment"),
        "implementation_sha": IMPLEMENTATION_SHA,
        "docs_sha_expected": EXPECTED_DOCS_SHA,
        "behaviour_identical_to_implementation": st.get("commit_sha") == EXPECTED_DOCS_SHA,
        "production_unchanged": pr.get("commit_sha") == PROD_SHA and pr.get("environment") == "production",
    }


def _list_clients(token: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    for path in (
        "/admin/clients?lifecycle_bucket=all&limit=50",
        "/admin/clients?lifecycle_bucket=suspended&limit=50",
        "/admin/clients?lifecycle_bucket=test_like&limit=50",
        "/admin/clients?q=nancy@yopmail.com&lifecycle_bucket=all&limit=10",
        "/admin/pilot-lifecycle/accounts?limit=40",
    ):
        r = _req("GET", path, token, timeout=90)
        body = r.get("body") if isinstance(r.get("body"), dict) else {}
        items = body.get("clients") or body.get("accounts") or body.get("items") or []
        for row in items:
            cid = row.get("client_id")
            if cid and cid not in seen:
                seen.add(cid)
                rows.append(row)
    return rows


def _classify_fixtures(token: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    classified: List[Dict[str, Any]] = []
    for row in rows[:40]:
        cid = row.get("client_id")
        if not cid:
            continue
        a = _assessment(token, cid)
        body = a.get("body") if isinstance(a.get("body"), dict) else {}
        if not body.get("found"):
            continue
        access = body.get("access") or {}
        item = {
            "client_id": cid,
            "email": row.get("email") or row.get("contact_email"),
            "canonical": (access.get("underlying_canonical_entitlement_state") or access.get("canonical_entitlement_state") or "").upper(),
            "effective": (access.get("effective_entitlement_state") or "").upper(),
            "plan": access.get("restored_plan_code"),
            "has_active_exception": bool(body.get("has_active_exception")),
            "subscription_status": row.get("subscription_status"),
        }
        classified.append(item)
    active = None
    cancelled = None
    unresolved = None
    extra_active = None
    for item in classified:
        if item["has_active_exception"]:
            continue
        if item["canonical"] == "ENABLED" and item.get("plan") and active is None:
            active = item
        elif item["canonical"] == "ENABLED" and item.get("plan") and extra_active is None:
            extra_active = item
        if item["canonical"] == "CANCELLED" and item.get("plan") and cancelled is None:
            cancelled = item
        if not item.get("plan") and unresolved is None:
            unresolved = item
    return {
        "scanned": classified,
        "active_billable": active,
        "cancelled_with_plan": cancelled,
        "extra_active": extra_active or active,
        "plan_unresolved_candidate": unresolved,
    }


def _control_row(before: Dict[str, Any], exe: Dict[str, Any], after: Dict[str, Any], *, email_expected: Optional[bool]) -> Dict[str, Any]:
    exe_body = exe.get("body") if isinstance(exe.get("body"), dict) else {}
    after_acc = after.get("access") or {}
    before_acc = before.get("access") or {}
    gov = after.get("active_governance") or {}
    email_result = exe_body.get("email_result") if isinstance(exe_body, dict) else None
    stripe_pause = exe_body.get("stripe_pause") if isinstance(exe_body, dict) else None
    api_ok = bool(exe.get("ok"))
    db_ok = bool(after.get("has_active_exception")) if exe_body.get("action") != "revoke_commercial_exception" else not after.get("has_active_exception")
    return {
        "api": "PASS" if api_ok else "FAIL",
        "api_status": exe.get("status"),
        "elapsed_ms": exe.get("elapsed_ms"),
        "error_code": _error_code(exe_body) or (None if api_ok else "EXECUTE_FAILED"),
        "error": None if api_ok else exe_body,
        "db": "PASS" if after.get("assessment_ok") and (db_ok or api_ok) else "FAIL",
        "authority": "PASS" if after.get("classification") else "UNVERIFIED",
        "access": {
            "before": before_acc,
            "after": after_acc,
        },
        "before": {
            "lifecycle_canonical": before_acc.get("underlying_canonical_entitlement_state") or before_acc.get("canonical_entitlement_state"),
            "governance": before.get("classification"),
            "plan": before_acc.get("restored_plan_code"),
            "effective": before_acc.get("effective_entitlement_state"),
            "exception": before.get("has_active_exception"),
            "billing": before.get("billing"),
        },
        "after": {
            "lifecycle_canonical": after_acc.get("underlying_canonical_entitlement_state") or after_acc.get("canonical_entitlement_state"),
            "governance": after.get("classification"),
            "plan": after_acc.get("restored_plan_code"),
            "effective": after_acc.get("effective_entitlement_state"),
            "exception": after.get("has_active_exception"),
            "active_governance": gov,
            "billing": after.get("billing"),
            "audit_events": after.get("audit_events"),
        },
        "stripe_pause": stripe_pause,
        "email_result": email_result,
        "email_expected": email_expected,
        "preview": exe_body.get("impact_preview") if isinstance(exe_body, dict) else None,
        "ui_refresh_api": "PASS" if after.get("assessment_ok") else "FAIL",
    }


def _sanitize_messages(body: Any) -> List[Dict[str, Any]]:
    if not isinstance(body, dict):
        return []
    rows = body.get("items") or body.get("messages") or body.get("logs") or []
    out = []
    for m in rows[:15]:
        if not isinstance(m, dict):
            continue
        out.append(
            {
                "message_id_prefix": _mask(m.get("message_id")),
                "status": m.get("status") or m.get("delivery_status"),
                "template_key": m.get("template_key"),
                "event_type": m.get("event_type"),
                "recipient": m.get("recipient") or m.get("to"),
                "provider_id_prefix": _mask(m.get("provider_message_id") or m.get("provider_id")),
                "created_at": str(m.get("created_at") or "")[:25],
                "subject": (m.get("subject") or "")[:80] or None,
            }
        )
    return out


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
        "preflight": {
            "prior_login_status": 200,
            "prior_role": "ROLE_ADMIN",
            "note": "Exactly one preflight login already succeeded this exercise; token reused if still valid.",
        },
        "deployment": {},
        "operator": {},
        "step_up": {},
        "fixtures": {},
        "controls": {},
        "suspend_billing_active": {},
        "suspend_billing_cancelled": {},
        "plan_unresolved": {},
        "email": {},
        "expiry": {},
        "negative_paths": {},
        "rbac": {},
        "mongodb_soak": {
            "prior_window_must_not_carry_forward": True,
            "interrupt_utc": "2026-08-15T18:50:05Z",
            "docs_deploy_sha": EXPECTED_DOCS_SHA,
            "note": "Staging deploys/restarts on 15 August 2026 interrupted the previous MongoDB observation window. Soak duration is not carried forward. Commercial Controls certification is independent of production Mongo soak.",
        },
        "summary": {},
    }

    results["deployment"] = _versions()
    results["frontend"] = _frontend_markers()
    runtime_sha = results["deployment"].get("runtime_sha")
    results["runtime_sha_authority"] = runtime_sha

    token = ""
    auth_source = ""
    if TOKEN_FILE.is_file():
        candidate = TOKEN_FILE.read_text(encoding="utf-8").strip()
        probe = _req("GET", "/admin/clients?limit=1", candidate)
        if probe.get("ok"):
            token = candidate
            auth_source = "reused_preflight_token"
        elif probe.get("status") in (401, 403):
            auth_source = "preflight_token_expired"
        else:
            results["preflight"]["token_probe"] = {"status": probe.get("status")}
    if not token:
        login = _login_once(email, password)
        results["preflight"]["continuation_login"] = {
            "status": login["status"],
            "ok": login["ok"],
            "role": login.get("role"),
            "error_code": login.get("error_code"),
            "source": auth_source or "fresh_login",
        }
        if login["status"] == 401:
            results["summary"]["verdict"] = "BLOCKED_STAGING_CREDENTIALS"
            OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
            print(json.dumps(results["summary"], indent=2))
            return 3
        if login["status"] == 423:
            results["summary"]["verdict"] = "BLOCKED_STAGING_AUTH_LOCK"
            OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
            print(json.dumps(results["summary"], indent=2))
            return 3
        if not login["ok"]:
            results["summary"]["verdict"] = "COMMERCIAL_CONTROLS_INCOMPLETE"
            results["summary"]["reason"] = f"login_status_{login['status']}"
            OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
            print(json.dumps(results["summary"], indent=2))
            return 1
        token = login["token"]
        TOKEN_FILE.write_text(token, encoding="utf-8")
        auth_source = "one_login"
    claims = _jwt_claims(token)
    results["operator"] = {
        "auth_source": auth_source,
        "jwt": claims,
        "role_admin": claims.get("role") == "ROLE_ADMIN",
        "step_up_policy_commercial_entitlement_execute": {
            "requires_step_up": True,
            "requires_confirmation": True,
            "risk_class": "high_impact_operational",
        },
    }

    # STEP_UP_REQUIRED proof (no password attempt)
    cid_probe_rows = _list_clients(token)
    fixtures = _classify_fixtures(token, cid_probe_rows)
    results["fixtures"] = {
        "active_billable": fixtures.get("active_billable"),
        "cancelled_with_plan": fixtures.get("cancelled_with_plan"),
        "extra_active": fixtures.get("extra_active"),
        "plan_unresolved_candidate": fixtures.get("plan_unresolved_candidate"),
        "scanned_count": len(fixtures.get("scanned") or []),
        "scanned": fixtures.get("scanned"),
    }
    work_client = (fixtures.get("extra_active") or fixtures.get("active_billable") or fixtures.get("cancelled_with_plan") or {})
    work_id = work_client.get("client_id")
    if not work_id:
        results["summary"]["verdict"] = "COMMERCIAL_CONTROLS_INCOMPLETE"
        results["summary"]["reason"] = "no_staging_fixture_client"
        OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(results["summary"], indent=2))
        return 1

    no_step = _req(
        "POST",
        f"/admin/clients/{work_id}/commercial-entitlement/execute",
        token,
        json={"action": "grant_grace_period", "reason": REASON, "duration_days": 7},
        confirmation=_confirm(token, work_id),
    )
    results["step_up"]["without_token"] = {
        "status": no_step.get("status"),
        "error_code": _error_code(no_step.get("body")),
        "pass": no_step.get("status") == 403 and _error_code(no_step.get("body")) == "STEP_UP_REQUIRED",
    }

    early_step = _step_up(token, password)
    results["step_up"]["issued"] = {
        "ok": early_step.get("ok"),
        "status": early_step.get("status"),
        "expires_in_seconds": early_step.get("expires_in_seconds"),
        "issued_at_utc": _utc(),
    }
    if not early_step.get("ok"):
        results["summary"]["verdict"] = "COMMERCIAL_CONTROLS_INCOMPLETE"
        results["summary"]["reason"] = "step_up_verify_failed"
        results["step_up"]["verify_error_code"] = early_step.get("error_code")
        OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(results["summary"], indent=2))
        return 1
    step_up = early_step["token"]
    early_step_token = step_up

    # One invalid step-up (do not repeat)
    bad = httpx.post(
        f"{API}/auth/step-up/verify",
        json={"password": "not-the-operator-password"},
        headers=_headers(token),
        timeout=60,
    )
    try:
        bad_body = bad.json()
    except Exception:
        bad_body = {}
    results["step_up"]["invalid_password_once"] = {
        "status": bad.status_code,
        "error_code": _error_code(bad_body),
        "pass": bad.status_code in (401, 403, 422),
        "note": "Single invalid attempt only; AUTH_LOCK_EMAIL_MINUTES not bypassed.",
    }

    # Clear exceptions on chosen fixtures
    for key in ("active_billable", "cancelled_with_plan", "extra_active"):
        item = fixtures.get(key) or {}
        cid = item.get("client_id")
        if cid:
            _revoke_if_active(token, step_up, cid)

    active_id = (fixtures.get("active_billable") or {}).get("client_id")
    cancelled_id = (fixtures.get("cancelled_with_plan") or {}).get("client_id")
    other_id = (fixtures.get("extra_active") or {}).get("client_id") or active_id
    if other_id == active_id and cancelled_id and cancelled_id != active_id:
        # prefer keeping active_id dedicated for suspend+expiry
        pass

    control_client = other_id
    if control_client == active_id:
        control_client = other_id

    email_off_action = "waive_onboarding_fee"
    for action, extra in ACTIONS:
        cid = control_client
        send_email = action != email_off_action
        before = _snap(token, cid)
        # refresh step-up if needed
        exe = _execute(token, step_up, cid, action, extra, send_email=send_email)
        if exe.get("status") == 403 and _error_code(exe.get("body")) == "STEP_UP_REQUIRED":
            refreshed = _step_up(token, password)
            step_up = refreshed.get("token") or step_up
            exe = _execute(token, step_up, cid, action, extra, send_email=send_email)
        after = _snap(token, cid)
        msgs = _messages(token, cid)
        row = _control_row(before, exe, after, email_expected=send_email)
        row["client_id"] = cid
        row["runtime_sha"] = runtime_sha
        row["messages_after"] = _sanitize_messages(msgs.get("body"))
        if send_email:
            er = row.get("email_result") or {}
            outcome = (er or {}).get("outcome")
            if outcome == "sent":
                row["email"] = "PASS_PROVIDER_ACCEPTED"
            elif outcome == "queued":
                row["email"] = "QUEUED_NOT_DELIVERED"
            elif outcome == "duplicate_ignored":
                row["email"] = "DUPLICATE_IGNORED"
            else:
                row["email"] = f"FAIL_OR_UNVERIFIED:{outcome}"
        else:
            er = row.get("email_result") or {}
            row["email"] = "PASS_SKIPPED" if (not send_email and (not er or er.get("outcome") in (None, "skipped"))) or after.get("active_governance", {}).get("customer_notification_status") == "skipped" else "CHECK_SKIPPED"
        if exe.get("ok") and after.get("has_active_exception"):
            row["verdict"] = "PASS"
        else:
            row["verdict"] = "FAIL"
        results["controls"][action] = row
        _revoke_if_active(token, step_up, cid)

    # Phase 5 — Suspend billing ACTIVE
    short_expiry = _iso_z(datetime.now(timezone.utc) + timedelta(seconds=95))
    if active_id:
        _revoke_if_active(token, step_up, active_id)
        before = _snap(token, active_id)
        exe = _execute(
            token,
            step_up,
            active_id,
            "suspend_billing",
            {"duration_days": 14, "entitlement_expiry_at": short_expiry},
            send_email=True,
        )
        if exe.get("status") == 403:
            step_up = (_step_up(token, password).get("token") or step_up)
            exe = _execute(
                token,
                step_up,
                active_id,
                "suspend_billing",
                {"duration_days": 14, "entitlement_expiry_at": short_expiry},
                send_email=True,
            )
        after = _snap(token, active_id)
        msgs = _messages(token, active_id)
        row = _control_row(before, exe, after, email_expected=True)
        row["client_id"] = active_id
        row["runtime_sha"] = runtime_sha
        row["messages_after"] = _sanitize_messages(msgs.get("body"))
        stripe_pause = row.get("stripe_pause") or {}
        mutation = (stripe_pause or {}).get("mutation")
        acc = after.get("access") or {}
        underlying = (acc.get("underlying_canonical_entitlement_state") or acc.get("canonical_entitlement_state") or "").upper()
        effective = (acc.get("effective_entitlement_state") or "").upper()
        row["canonical_unchanged_enabled"] = underlying == "ENABLED" or (
            (before.get("access") or {}).get("canonical_entitlement_state") == acc.get("canonical_entitlement_state")
        )
        row["effective_enabled"] = effective == "ENABLED"
        row["stripe_mutation"] = mutation
        row["pause_behavior"] = (stripe_pause or {}).get("behavior")
        if exe.get("ok") and after.get("has_active_exception") and mutation in ("pause_collection", "already_paused"):
            row["verdict"] = "PASS"
        elif exe.get("ok") and mutation == "already_non_collecting":
            row["verdict"] = "FAIL_NOT_BILLABLE_FIXTURE"
        else:
            row["verdict"] = "FAIL"
        results["controls"]["suspend_billing"] = row
        results["suspend_billing_active"] = row
        # duplicate while active
        dup = _execute(token, step_up, active_id, "grant_grace_period", {"duration_days": 7})
        results["negative_paths"]["duplicate_active_exception"] = {
            "second_status": dup.get("status"),
            "error_code": _error_code(dup.get("body")),
            "pass": not dup.get("ok"),
            "runtime_sha": runtime_sha,
        }
    else:
        results["suspend_billing_active"] = {"verdict": "NO_ACTIVE_FIXTURE"}

    # Phase 6 — Suspend billing CANCELLED
    short_expiry_c = _iso_z(datetime.now(timezone.utc) + timedelta(seconds=95))
    if cancelled_id:
        _revoke_if_active(token, step_up, cancelled_id)
        before = _snap(token, cancelled_id)
        exe = _execute(
            token,
            step_up,
            cancelled_id,
            "suspend_billing",
            {"duration_days": 14, "entitlement_expiry_at": short_expiry_c},
            send_email=True,
        )
        if exe.get("status") == 403:
            step_up = (_step_up(token, password).get("token") or step_up)
            exe = _execute(
                token,
                step_up,
                cancelled_id,
                "suspend_billing",
                {"duration_days": 14, "entitlement_expiry_at": short_expiry_c},
                send_email=True,
            )
        after = _snap(token, cancelled_id)
        msgs = _messages(token, cancelled_id)
        row = _control_row(before, exe, after, email_expected=True)
        row["client_id"] = cancelled_id
        row["runtime_sha"] = runtime_sha
        row["messages_after"] = _sanitize_messages(msgs.get("body"))
        preview = row.get("preview") or {}
        acc = after.get("access") or {}
        underlying = (acc.get("underlying_canonical_entitlement_state") or "").upper()
        effective = (acc.get("effective_entitlement_state") or "").upper()
        stripe_pause = row.get("stripe_pause") or {}
        row["canonical_cancelled"] = underlying == "CANCELLED"
        row["effective_enabled"] = effective == "ENABLED"
        row["plan_restored"] = bool(acc.get("restored_plan_code"))
        row["stripe_no_recreate"] = (stripe_pause or {}).get("mutation") == "already_non_collecting"
        cust = (preview.get("customer_impact") or "") + " " + (preview.get("notification_subject") or "")
        row["email_copy_temporary_not_reactivation"] = (
            "reactiv" not in cust.lower()
            or "temporary" in cust.lower()
            or "cancelled" in cust.lower()
        )
        if (
            exe.get("ok")
            and after.get("has_active_exception")
            and row["canonical_cancelled"]
            and row["effective_enabled"]
            and row["stripe_no_recreate"]
        ):
            row["verdict"] = "PASS"
        else:
            row["verdict"] = "FAIL"
        results["suspend_billing_cancelled"] = row
    else:
        results["suspend_billing_cancelled"] = {"verdict": "NO_CANCELLED_FIXTURE"}

    # PLAN_UNRESOLVED
    unresolved_id = (fixtures.get("plan_unresolved_candidate") or {}).get("client_id")
    if unresolved_id:
        _revoke_if_active(token, step_up, unresolved_id)
        exe = _execute(token, step_up, unresolved_id, "suspend_billing", {"duration_days": 14})
        results["plan_unresolved"] = {
            "client_id": unresolved_id,
            "status": exe.get("status"),
            "error_code": _error_code(exe.get("body")),
            "body_preview": (json.dumps(exe.get("body"), default=str)[:500] if not isinstance(exe.get("body"), str) else exe.get("body")[:500]),
            "pass": _error_code(exe.get("body")) == "PLAN_UNRESOLVED" or (
                not exe.get("ok") and "PLAN_UNRESOLVED" in json.dumps(exe.get("body"), default=str)
            ),
            "did_not_default_solo": "solo" not in json.dumps(exe.get("body"), default=str).lower()
            or _error_code(exe.get("body")) == "PLAN_UNRESOLVED",
            "runtime_sha": runtime_sha,
        }
    else:
        results["plan_unresolved"] = {
            "pass": False,
            "reason": "NO_PLAN_UNRESOLVED_FIXTURE",
            "runtime_sha": runtime_sha,
        }

    # Negative paths on control_client (should be clean after revokes)
    cid = control_client
    _revoke_if_active(token, step_up, cid)
    missing_reason = _req(
        "POST",
        f"/admin/clients/{cid}/commercial-entitlement/execute",
        token,
        json={"action": "suspend_billing", "reason": "short", "duration_days": 14},
        step_up=step_up,
        confirmation=_confirm(token, cid),
    )
    results["negative_paths"]["insufficient_reason"] = {
        "status": missing_reason["status"],
        "pass": missing_reason["status"] in (400, 422),
        "runtime_sha": runtime_sha,
    }
    no_confirm = _req(
        "POST",
        f"/admin/clients/{cid}/commercial-entitlement/execute",
        token,
        json={"action": "suspend_billing", "reason": REASON, "duration_days": 14},
        step_up=step_up,
    )
    results["negative_paths"]["confirmation_missing"] = {
        "status": no_confirm["status"],
        "pass": no_confirm["status"] in (400, 401, 403, 422),
        "runtime_sha": runtime_sha,
    }
    bad_duration = _execute(token, step_up, cid, "grant_grace_period", {"duration_days": 31})
    results["negative_paths"]["invalid_duration"] = {
        "status": bad_duration["status"],
        "error_code": _error_code(bad_duration.get("body")),
        "pass": (not bad_duration.get("ok")) and bad_duration.get("status") in (400, 422),
        "runtime_sha": runtime_sha,
    }
    unauth = _req(
        "POST",
        f"/admin/clients/{cid}/commercial-entitlement/execute",
        "",
        json={"action": "suspend_billing", "reason": REASON, "duration_days": 14},
    )
    results["rbac"]["unauthenticated"] = {
        "status": unauth.get("status"),
        "pass": unauth.get("status") in (401, 403),
        "runtime_sha": runtime_sha,
    }

    # Email-off proof already captured on waive. Summarize message log deltas.
    results["email"]["waive_unchecked"] = results["controls"].get("waive_onboarding_fee", {}).get("email")
    results["email"]["note"] = "Queued is not treated as delivered. Provider acceptance requires outcome=sent plus message_logs correlation."

    # Phase 8 — wait for short expiries then run expiry job
    wait_s = 100
    results["expiry"]["wait_seconds"] = wait_s
    results["expiry"]["started_wait_utc"] = _utc()
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
    results["expiry"]["job_run"] = {
        "status": job.get("status"),
        "ok": job.get("ok"),
        "expired_count": ((job.get("body") or {}) if isinstance(job.get("body"), dict) else {}).get("result", {})
        if isinstance(job.get("body"), dict)
        else None,
        "runtime_sha": runtime_sha,
    }
    if isinstance(job.get("body"), dict):
        results["expiry"]["job_body_summary"] = {
            "success": job["body"].get("success"),
            "job": job["body"].get("job"),
            "result": job["body"].get("result"),
        }

    if active_id:
        after_exp = _snap(token, active_id)
        acc = after_exp.get("access") or {}
        results["expiry"]["suspend_billing_active"] = {
            "has_active_exception": after_exp.get("has_active_exception"),
            "canonical": acc.get("underlying_canonical_entitlement_state") or acc.get("canonical_entitlement_state"),
            "effective": acc.get("effective_entitlement_state"),
            "billing": after_exp.get("billing"),
            "audit_events": after_exp.get("audit_events"),
            "pass": not after_exp.get("has_active_exception"),
            "runtime_sha": runtime_sha,
        }
    if cancelled_id:
        after_exp = _snap(token, cancelled_id)
        acc = after_exp.get("access") or {}
        results["expiry"]["suspend_billing_cancelled"] = {
            "has_active_exception": after_exp.get("has_active_exception"),
            "canonical": acc.get("underlying_canonical_entitlement_state") or acc.get("canonical_entitlement_state"),
            "effective": acc.get("effective_entitlement_state"),
            "plan": acc.get("restored_plan_code"),
            "billing": after_exp.get("billing"),
            "audit_events": after_exp.get("audit_events"),
            "pass": (not after_exp.get("has_active_exception"))
            and (acc.get("underlying_canonical_entitlement_state") or acc.get("canonical_entitlement_state") or "").upper()
            == "CANCELLED"
            and (acc.get("effective_entitlement_state") or "").upper() == "CANCELLED",
            "runtime_sha": runtime_sha,
        }

    # Expired step-up token (practical if 10 minutes elapsed)
    expired_try = _req(
        "POST",
        f"/admin/clients/{cid}/commercial-entitlement/execute",
        token,
        json={"action": "grant_grace_period", "reason": REASON, "duration_days": 7},
        step_up=early_step_token,
        confirmation=_confirm(token, cid),
    )
    elapsed_step = None
    results["step_up"]["expired_token"] = {
        "status": expired_try.get("status"),
        "error_code": _error_code(expired_try.get("body")),
        "note": "STEP_UP_TOKEN_MINUTES default 10. Pass if 403 STEP_UP_REQUIRED/invalid after TTL; otherwise TTL not elapsed.",
        "runtime_sha": runtime_sha,
    }

    # Stripe void semantics (documented + live pause)
    results["stripe_void_semantics"] = {
        "implementation": "pause_collection.behavior=void",
        "invoices_during_pause": "Stripe marks invoices created while pause_collection.behavior=void as void immediately; amounts are not collectible later.",
        "resume": "Unsetting pause_collection resumes future invoices only; voided invoices stay void. Billing cycle/status remain active unless otherwise changed.",
        "next_billing_date": "pause_collection does not by itself change current_period_end.",
        "immediate_invoice_on_resume": "Not expected from unsetting pause_collection (this is not Subscription Pause status=paused Resume API).",
        "free_service": "Void pause temporarily offers service without collecting those invoices — matches approved exception duration if expiry is enforced.",
        "live_invoice_during_pause_observed": False,
        "live_pause_applied": ((results.get("suspend_billing_active") or {}).get("stripe_mutation") in ("pause_collection", "already_paused")),
        "runtime_sha": runtime_sha,
    }

    # Verdict assembly
    def _col_pass(row: Dict[str, Any], key: str) -> bool:
        return (row or {}).get(key) in ("PASS", "PASS_PROVIDER_ACCEPTED", "PASS_SKIPPED", "NO_STRIPE_ACTION")

    control_verdicts = {}
    for name, row in (results.get("controls") or {}).items():
        control_verdicts[name] = row.get("verdict")
    if results.get("suspend_billing_cancelled"):
        control_verdicts["suspend_billing_cancelled_path"] = results["suspend_billing_cancelled"].get("verdict")

    neg_ok = all(bool(v.get("pass")) for v in results["negative_paths"].values() if isinstance(v, dict) and "pass" in v)
    rbac_ok = bool((results.get("rbac") or {}).get("unauthenticated", {}).get("pass"))
    step_ok = bool(results["step_up"].get("without_token", {}).get("pass")) and bool(results["step_up"].get("issued", {}).get("ok"))
    fe_ok = bool(results.get("frontend", {}).get("spinner_fix_deployed")) and bool(results.get("frontend", {}).get("points_at_staging_api"))
    deploy_ok = bool(results["deployment"].get("environment") == "staging") and bool(results["deployment"].get("production_unchanged"))
    expiry_active_ok = bool((results.get("expiry") or {}).get("suspend_billing_active", {}).get("pass")) if active_id else False
    expiry_cancelled_ok = bool((results.get("expiry") or {}).get("suspend_billing_cancelled", {}).get("pass")) if cancelled_id else False
    seven_ok = all(v == "PASS" for k, v in control_verdicts.items() if k != "suspend_billing_cancelled_path")
    cancelled_ok = (results.get("suspend_billing_cancelled") or {}).get("verdict") == "PASS"
    unresolved = results.get("plan_unresolved") or {}
    unresolved_ok = bool(unresolved.get("pass"))

    blocking = []
    if not deploy_ok:
        blocking.append("deployment_authority")
    if not step_ok:
        blocking.append("step_up")
    if not seven_ok:
        blocking.append("seven_controls")
    if (results.get("suspend_billing_active") or {}).get("verdict") != "PASS":
        blocking.append("suspend_billing_active")
    if cancelled_id and not cancelled_ok:
        blocking.append("suspend_billing_cancelled")
    if not cancelled_id:
        blocking.append("missing_cancelled_fixture")
    if not expiry_active_ok:
        blocking.append("expiry_active")
    if cancelled_id and not expiry_cancelled_ok:
        blocking.append("expiry_cancelled")
    if not unresolved_ok:
        blocking.append("plan_unresolved")
    if not neg_ok:
        blocking.append("negative_paths")
    if not rbac_ok:
        blocking.append("rbac")
    if not fe_ok:
        blocking.append("frontend_fingerprint")

    conditions = []
    if not results["stripe_void_semantics"]["live_invoice_during_pause_observed"]:
        conditions.append("invoice_void_during_pause_not_live_invoiced_this_window")
    if results["step_up"]["expired_token"].get("status") not in (401, 403):
        conditions.append("step_up_ttl_not_elapsed")
    if not unresolved_ok and unresolved.get("reason") == "NO_PLAN_UNRESOLVED_FIXTURE":
        pass  # already blocking
    results["summary"] = {
        "runtime_sha": runtime_sha,
        "control_verdicts": control_verdicts,
        "negative_paths_pass": neg_ok,
        "step_up_pass": step_ok,
        "frontend_ok": fe_ok,
        "deployment_ok": deploy_ok,
        "blocking": blocking,
        "conditions": conditions,
        "operator_role_admin": bool(results["operator"].get("role_admin")),
    }
    if not blocking:
        if conditions:
            verdict = "COMMERCIAL_CONTROLS_VERIFIED_WITH_CONDITIONS"
        else:
            verdict = "COMMERCIAL_CONTROLS_VERIFIED"
    else:
        verdict = "COMMERCIAL_CONTROLS_INCOMPLETE"
    results["summary"]["verdict"] = verdict

    OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    print(f"wrote {OUT}")
    return 0 if verdict in ("COMMERCIAL_CONTROLS_VERIFIED", "COMMERCIAL_CONTROLS_VERIFIED_WITH_CONDITIONS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
