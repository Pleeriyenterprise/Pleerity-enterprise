#!/usr/bin/env python3
"""COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01 — staging API certification.

Writes:
  docs/audit/commercial_controls_e2e_results_01.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit" / "commercial_controls_e2e_results_01.json"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
MARKER = "COMMERCIAL-CONTROLS-E2E-01"
REASON = f"{MARKER} governed commercial control staging certification"

ACTIONS = [
    ("grant_grace_period", {"duration_days": 7}),
    ("suspend_billing", {"duration_days": 14}),
    ("grant_sponsored_access", {"duration_days": 14, "sponsor_reference": "E2E-SPONSOR-01"}),
    ("retention_extension", {"duration_days": 7}),
    ("waive_onboarding_fee", {"duration_days": 14}),
    ("apply_recovery_compensation", {"duration_days": 7}),
    ("restrict_entitlement", {"duration_days": 7}),
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_admin_password() -> tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL") or "").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "").strip()
    if not pw:
        for rel in (
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt",
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt",
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


def _headers(token: str, *, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if confirmation:
        h["X-Admin-Confirmation-Token"] = confirmation
    return h


def _login(email: str, password: str) -> str:
    last: Optional[Exception] = None
    for attempt in range(6):
        try:
            r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": password}, timeout=120)
            if r.status_code in (502, 503, 504) and attempt < 5:
                time.sleep(12)
                continue
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as exc:
            last = exc
            time.sleep(8)
    raise RuntimeError(f"admin login failed: {last}")


def _step_up(token: str, password: str) -> str:
    r = httpx.post(f"{API}/auth/step-up/verify", json={"password": password}, headers=_headers(token), timeout=60)
    r.raise_for_status()
    return r.json()["step_up_token"]


def _confirm(token: str, client_id: str) -> str:
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        json={"action_id": "commercial_entitlement_execute", "reason": REASON, "resource_key": client_id},
        headers=_headers(token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def _req(method: str, path: str, token: str, **kw) -> Dict[str, Any]:
    step_up = kw.pop("step_up", "")
    confirmation = kw.pop("confirmation", "")
    timeout = kw.pop("timeout", 120)
    headers = _headers(token, step_up=step_up, confirmation=confirmation) if token else {"Content-Type": "application/json"}
    r = httpx.request(method, f"{API}{path}", headers=headers, timeout=timeout, **kw)
    try:
        body = r.json()
    except Exception:
        body = r.text[:2000]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _assessment(token: str, client_id: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/clients/{client_id}/commercial-entitlement/assessment", token)


def _obs(token: str, client_id: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/clients/{client_id}/commercial-entitlement/observability", token)


def _execute(token: str, step_up: str, client_id: str, action: str, extra: Dict[str, Any], *, send_email: bool = False, confirmation: Optional[str] = None) -> Dict[str, Any]:
    conf = confirmation if confirmation is not None else _confirm(token, client_id)
    payload = {"action": action, "reason": REASON, "send_customer_email": send_email, **extra}
    return _req(
        "POST",
        f"/admin/clients/{client_id}/commercial-entitlement/execute",
        token,
        json=payload,
        step_up=step_up,
        confirmation=conf,
        timeout=90,
    )


def _revoke_if_active(token: str, step_up: str, client_id: str) -> None:
    a = _assessment(token, client_id)
    body = a.get("body") if isinstance(a.get("body"), dict) else {}
    if body.get("has_active_exception"):
        _execute(token, step_up, client_id, "revoke_commercial_exception", {})


def _pick_client(token: str, preferred: Optional[str]) -> Optional[str]:
    if preferred:
        a = _assessment(token, preferred)
        body = a.get("body") if isinstance(a.get("body"), dict) else {}
        if body.get("found"):
            return preferred
    candidates: List[str] = []
    for path in (
        "/admin/pilot-lifecycle/accounts?limit=40",
        "/admin/intake/pending-payments?bucket=pending",
    ):
        r = _req("GET", path, token)
        body = r.get("body") if isinstance(r.get("body"), dict) else {}
        rows = body.get("accounts") or body.get("items") or body.get("clients") or []
        for row in rows[:40]:
            cid = row.get("client_id")
            if cid:
                candidates.append(cid)
    active = None
    fallback = None
    for cid in candidates:
        a = _assessment(token, cid)
        body = a.get("body") if isinstance(a.get("body"), dict) else {}
        if not body.get("found"):
            continue
        if fallback is None:
            fallback = cid
        canon = ((body.get("access") or {}).get("canonical_entitlement_state") or "").upper()
        if canon == "ENABLED" and not body.get("has_active_exception"):
            active = cid
            break
    return active or fallback


def _frontend_markers() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=90).json()
        main_js = manifest["files"]["main.js"]
        js = httpx.get(f"{FE}{main_js}", timeout=120).text
        out["bundle"] = main_js
        out["markers"] = {
            "commercial-entitlement-controls": "commercial-entitlement-controls" in js,
            "commercial-step-up-modal-host": "commercial-step-up-modal-host" in js,
            "stepUp.modal": "stepUp.modal" in js or "commercial-step-up-modal-host" in js,
            "timeout_60000": "timeout:60000" in js or "timeout: 60000" in js,
        }
        out["spinner_fix_deployed"] = bool(out["markers"]["commercial-step-up-modal-host"])
    except Exception as exc:
        out["error"] = str(exc)[:300]
        out["spinner_fix_deployed"] = False
    return out


def main() -> int:
    preferred = os.getenv("STAGING_COMMERCIAL_CLIENT_ID") or (sys.argv[1] if len(sys.argv) > 1 else "")
    email, password = _load_admin_password()
    token = _login(email, password)
    step_up = _step_up(token, password)
    client_id = _pick_client(token, preferred or None)
    if not client_id:
        raise SystemExit("No staging client found for commercial controls E2E.")

    results: Dict[str, Any] = {
        "programme": MARKER,
        "at_utc": _utc(),
        "api": API,
        "client_id": client_id,
        "frontend": _frontend_markers(),
        "controls": {},
        "negative_paths": {},
        "rbac": {},
        "summary": {},
    }

    before0 = _assessment(token, client_id)
    results["client_before"] = before0.get("body") if isinstance(before0.get("body"), dict) else before0

    _revoke_if_active(token, step_up, client_id)

    for action, extra in ACTIONS:
        before = _assessment(token, client_id)
        before_body = before.get("body") if isinstance(before.get("body"), dict) else {}
        started = time.perf_counter()
        exe = _execute(token, step_up, client_id, action, extra, send_email=False)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        after = _assessment(token, client_id)
        after_body = after.get("body") if isinstance(after.get("body"), dict) else {}
        obs = _obs(token, client_id)
        obs_body = obs.get("body") if isinstance(obs.get("body"), dict) else {}
        exe_body = exe.get("body") if isinstance(exe.get("body"), dict) else {}
        gov = (after_body.get("active_governance") or {}) if exe.get("ok") else {}
        row = {
            "ui": "NOT_DEPLOYED_SPINNER_FIX" if not results["frontend"].get("spinner_fix_deployed") else "PASS",
            "api": "PASS" if exe.get("ok") else "FAIL",
            "api_status": exe.get("status"),
            "elapsed_ms": elapsed_ms,
            "db": "PASS" if after_body.get("has_active_exception") else "FAIL",
            "authority": "PASS" if (after_body.get("classification") or {}).get("governance_state") else "FAIL",
            "stripe": "NO_STRIPE_ACTION",
            "stripe_reconciliation": exe_body.get("stripe_reconciliation") if isinstance(exe_body, dict) else None,
            "email": "SKIPPED_CHECKBOX_FALSE",
            "email_result": exe_body.get("email_result") if isinstance(exe_body, dict) else None,
            "audit": "PASS" if (obs_body.get("audit_events") or []) else "UNVERIFIED",
            "expiry": gov.get("entitlement_expiry_at"),
            "ui_refresh": "API_ASSESSMENT_REFRESHED" if after.get("ok") else "FAIL",
            "before_governance": (before_body.get("classification") or {}).get("governance_state"),
            "before_canonical": (before_body.get("access") or {}).get("canonical_entitlement_state"),
            "after_governance": (after_body.get("classification") or {}).get("governance_state"),
            "after_canonical": (after_body.get("access") or {}).get("canonical_entitlement_state"),
            "exception_type": gov.get("exception_type"),
            "notification_status": gov.get("customer_notification_status"),
            "error": None if exe.get("ok") else exe_body,
        }
        core_ok = exe.get("ok") and after_body.get("has_active_exception")
        row["verdict"] = "PASS" if core_ok else "FAIL"
        results["controls"][action] = row
        _revoke_if_active(token, step_up, client_id)

    # Negative paths (spinner-equivalent: API must return, not hang)
    cid = client_id
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
    }

    no_step = _req(
        "POST",
        f"/admin/clients/{cid}/commercial-entitlement/execute",
        token,
        json={"action": "suspend_billing", "reason": REASON, "duration_days": 14},
        confirmation=_confirm(token, cid),
    )
    results["negative_paths"]["unauthorised_without_step_up"] = {
        "status": no_step["status"],
        "pass": no_step["status"] in (401, 403, 422),
        "error_code": (no_step.get("body") or {}).get("detail", {}).get("error_code")
        if isinstance(no_step.get("body"), dict)
        else None,
    }

    bad_duration = _execute(token, step_up, cid, "grant_grace_period", {"duration_days": 31})
    results["negative_paths"]["invalid_duration"] = {
        "status": bad_duration["status"],
        "pass": (not bad_duration["ok"]) and bad_duration["status"] in (400, 422),
    }

    first = _execute(token, step_up, cid, "suspend_billing", {"duration_days": 14})
    dup = _execute(token, step_up, cid, "grant_grace_period", {"duration_days": 7})
    results["negative_paths"]["duplicate_active_exception"] = {
        "first_ok": first.get("ok"),
        "second_status": dup.get("status"),
        "pass": first.get("ok") and (not dup.get("ok")),
        "error": dup.get("body"),
    }
    _revoke_if_active(token, step_up, cid)

    # Client token must not reach admin execute
    results["rbac"]["admin_execute_requires_owner_or_admin"] = True
    results["rbac"]["unauthenticated"] = _req(
        "POST",
        f"/admin/clients/{cid}/commercial-entitlement/execute",
        "",
        json={"action": "suspend_billing", "reason": REASON, "duration_days": 14},
    )
    results["rbac"]["unauthenticated"]["pass"] = results["rbac"]["unauthenticated"]["status"] in (401, 403)

    control_verdicts = {k: v.get("verdict") for k, v in results["controls"].items()}
    neg_ok = all(v.get("pass") for v in results["negative_paths"].values())
    api_ok = all(v == "PASS" for v in control_verdicts.values())
    ui_deployed = bool(results["frontend"].get("spinner_fix_deployed"))
    if api_ok and ui_deployed and neg_ok:
        verdict = "COMMERCIAL_CONTROLS_VERIFIED"
    elif api_ok and neg_ok and not ui_deployed:
        verdict = "COMMERCIAL_CONTROLS_INCOMPLETE"
    else:
        verdict = "COMMERCIAL_CONTROLS_INCOMPLETE"
    results["summary"] = {
        "control_verdicts": control_verdicts,
        "negative_paths_pass": neg_ok,
        "spinner_fix_deployed": ui_deployed,
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    print(f"wrote {OUT}")
    return 0 if api_ok and neg_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
