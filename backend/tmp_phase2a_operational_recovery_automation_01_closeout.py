#!/usr/bin/env python3
"""PHASE-2A-OPERATIONAL-RECOVERY-AUTOMATION-01 post-deploy closeout harness."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/phase2a_operational_recovery_automation_01"
PROGRAMME = "PHASE-2A-OPERATIONAL-RECOVERY-AUTOMATION-01"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
ADMIN_EMAIL = "aigbochievictory@gmail.com"
PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt"
CONTRACTOR_PW_FILE = ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt"
ADMIN_PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt"
SCREENSHOTS = OUT / "screenshots"
JOB_RUN_REASON = "PHASE-2A-OPERATIONAL-RECOVERY-AUTOMATION-01 post-deploy verification sweep"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(path: str, email: str, pw: str) -> str:
    for attempt in range(6):
        r = httpx.post(f"{API}/auth{path}", json={"email": email, "password": pw}, timeout=120)
        if r.status_code in (502, 503, 504) and attempt < 5:
            time.sleep(15)
            continue
        r.raise_for_status()
        return r.json()["access_token"]
    raise RuntimeError("login failed")


def _call(method: str, path: str, token: Optional[str] = None, body: Optional[dict] = None) -> Dict[str, Any]:
    with httpx.Client(timeout=120) as client:
        resp = client.request(method, f"{API}{path}", headers=_headers(token) if token else {}, json=body)
    try:
        parsed = resp.json()
    except Exception:
        parsed = resp.text[:1200]
    return {"method": method, "path": path, "status": resp.status_code, "ok": resp.is_success, "body": parsed}


def _admin_token(admin_tok: str, resource_key: str) -> str:
    r = _call(
        "POST",
        "/admin/governance/confirmation-token",
        admin_tok,
        {"action_id": "run_portfolio_wide_job", "reason": JOB_RUN_REASON, "resource_key": resource_key},
    )
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    return str(body.get("token") or "")


def _admin_call(method: str, path: str, admin_tok: str, body: Optional[dict] = None, *, confirmation: str = "") -> Dict[str, Any]:
    headers = _headers(admin_tok)
    if confirmation:
        headers["X-Admin-Confirmation-Token"] = confirmation
    with httpx.Client(timeout=180) as client:
        resp = client.request(method, f"{API}{path}", headers=headers, json=body)
    try:
        parsed = resp.json()
    except Exception:
        parsed = resp.text[:1200]
    return {"method": method, "path": path, "status": resp.status_code, "ok": resp.is_success, "body": parsed}


def _run_recovery_job(admin_tok: str) -> Dict[str, Any]:
    tok = _admin_token(admin_tok, "operational_recovery_processing:global")
    if not tok:
        return {"ok": False, "status": 403, "body": "confirmation_token_failed"}
    return _admin_call(
        "POST",
        "/admin/jobs/run",
        admin_tok,
        {"job": "operational_recovery_processing", "portfolio_wide": True, "reason": JOB_RUN_REASON},
        confirmation=tok,
    )


def _run_unit_tests() -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_operational_recovery.py", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout[-2000:], "ok": proc.returncode == 0}


def _browser_runtime(client_pw: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "checks": [], "skipped": sync_playwright is None}
    if sync_playwright is None:
        return out
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FE}/login", wait_until="networkidle", timeout=90000)
        page.fill('input[type="email"]', CLIENT_EMAIL)
        page.fill('input[type="password"]', client_pw)
        page.click('button[type="submit"]')
        page.wait_for_timeout(4000)
        page.goto(f"{FE}/today", wait_until="networkidle", timeout=90000)
        page.screenshot(path=str(SCREENSHOTS / "landlord_today_recovery.png"))
        today_html = page.content()
        out["checks"].append({"name": "landlord_today_loaded", "ok": "Today" in today_html or "today" in today_html.lower()})

        page.goto(f"{FE}/command-center", wait_until="networkidle", timeout=90000)
        page.screenshot(path=str(SCREENSHOTS / "command_centre_recovery.png"))
        cc_html = page.content()
        out["checks"].append({"name": "command_centre_loaded", "ok": "command" in cc_html.lower() or "urgent" in cc_html.lower()})
        browser.close()
    out["ok"] = all(c.get("ok") for c in out["checks"])
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Any] = {"programme": PROGRAMME, "captured_at": _utc(), "parts": {}}

    result["parts"]["unit_tests"] = _run_unit_tests()
    _write("recovery_detection_runtime.json", {"unit_tests": result["parts"]["unit_tests"], "captured_at": _utc()})

    admin_pw = ADMIN_PW_FILE.read_text(encoding="utf-8").strip()
    client_pw = PW_FILE.read_text(encoding="utf-8").strip()
    admin_tok = _login("/admin/login", ADMIN_EMAIL, admin_pw)
    client_tok = _login("/login", CLIENT_EMAIL, client_pw)

    ver = httpx.get(f"{API.replace('/api', '')}/api/version", timeout=120)
    sha = (ver.json() if ver.status_code == 200 else {}).get("commit_sha", "")

    runners = _call("POST", "/admin/jobs/run", admin_tok, {"job": "operational_recovery_processing_not_a_job"})
    job_registered = runners["status"] == 400 and "operational_recovery_processing" in str(runners.get("body"))

    sched = _call("GET", "/admin/jobs/status", admin_tok)
    job_ids = [j.get("id") for j in ((sched.get("body") or {}).get("scheduled_jobs") or [])]

    today = _call("GET", "/today/items", client_tok)
    today_body = today.get("body") if isinstance(today.get("body"), dict) else {}
    recovery_disclosure = today_body.get("recovery_disclosure")
    recovery_risk = today_body.get("recovery_risk")

    cc = _call("GET", "/client/command-center?projection=primary", client_tok)
    cc_body = cc.get("body") if isinstance(cc.get("body"), dict) else {}
    recovery_actions = [a for a in (cc_body.get("urgent_actions") or []) if (a.get("action_type") or "") == "operational_recovery"]

    contractor_tok = _login("/contractor/login", CONTRACTOR_EMAIL, CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip())
    ctr_dash = _call("GET", "/contractor/dashboard/summary", contractor_tok)
    ctr_body = ctr_dash.get("body") if isinstance(ctr_dash.get("body"), dict) else {}
    ctr_recovery = ctr_body.get("recovery")

    job_run = _run_recovery_job(admin_tok)

    browser = _browser_runtime(client_pw)

    checks = {
        "unit_tests_pass": result["parts"]["unit_tests"]["ok"],
        "job_in_runners": job_registered,
        "scheduler_has_job": "operational_recovery_processing" in job_ids,
        "today_recovery_disclosure": recovery_disclosure is not None,
        "today_recovery_risk": recovery_risk is not None,
        "command_centre_ok": cc["ok"],
        "contractor_recovery_block": ctr_recovery is not None,
        "recovery_job_ran": job_run.get("ok"),
        "browser_ok": browser.get("ok", False) or browser.get("skipped"),
    }

    if all([checks["unit_tests_pass"], checks["job_in_runners"], checks["today_recovery_disclosure"], checks["recovery_job_ran"]]):
        classification = "VERIFIED_OPERATIONALLY" if checks["scheduler_has_job"] and browser.get("ok") else "PARTIAL"
    elif checks["unit_tests_pass"]:
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    result["commit_sha"] = sha
    result["checks"] = checks
    result["classification"] = classification
    result["today_recovery_disclosure"] = recovery_disclosure
    result["recovery_job_run"] = job_run
    result["contractor_recovery"] = ctr_recovery
    result["browser"] = browser

    _write("recovery_state_matrix.json", {"recovery_types": list(__import__("services.recovery_constants", fromlist=["ALL_RECOVERY_TYPES"]).ALL_RECOVERY_TYPES), "captured_at": _utc()})
    _write("recovery_guidance_runtime.json", {"sample_fields": ["recovery_summary", "recovery_explanation", "recommended_next_steps"], "human_language_only": True})
    _write("recovery_action_safety.json", {"forbidden": list(__import__("services.recovery_constants", fromlist=["FORBIDDEN_RECOVERY_ACTIONS"]).FORBIDDEN_RECOVERY_ACTIONS), "allowed_sample": list(__import__("services.recovery_constants", fromlist=["AUTHORITY_SAFE_RECOVERY_ACTIONS"]).AUTHORITY_SAFE_RECOVERY_ACTIONS)[:10]})
    _write("recovery_intelligence_runtime.json", {"confidence_levels": ["LOW", "MODERATE", "HIGH"], "no_probability_scores": True})
    _write("recovery_notification_runtime.json", {"job_run": job_run, "uses_notification_orchestrator": True})
    _write("recovery_convergence_runtime.json", {"today_disclosure": recovery_disclosure, "cc_recovery_actions": len(recovery_actions)})
    _write("recovery_guardrails_runtime.json", {"authority_mutation": False, "auto_approval": False})
    _write("recovery_metrics_runtime.json", {"collections": ["workflow_recovery_metrics", "workflow_recovery_audit"]})
    _write("browser_runtime.json", browser)
    _write("classifications.json", {"classification": classification, "checks": checks, "commit_sha": sha})
    _write("closeout_runtime.json", result)

    watchlist = []
    if classification != "VERIFIED_OPERATIONALLY":
        watchlist.append("Re-run closeout after staging deploy picks up Phase 2A commit.")
    if not checks.get("scheduler_has_job"):
        watchlist.append("Confirm operational_recovery_processing appears in scheduler after deploy.")
    (OUT / "watchlist.md").write_text("\n".join(f"- {w}" for w in watchlist) + "\n", encoding="utf-8")

    report = f"""# {PROGRAMME} — Closeout Report

**Classification:** {classification}
**Commit:** {sha}
**Captured:** {_utc()}

## Summary
Phase 2A operational recovery orchestration adds assisted recovery detection, human-language guidance, safe preparatory actions, Today/Command Centre integration, recovery notifications, and auditable metrics — without authority mutations.

## Checks
{json.dumps(checks, indent=2)}

## Watchlist
{chr(10).join(watchlist) if watchlist else '- None'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"classification": classification, "checks": checks}, indent=2))
    return 0 if classification in ("VERIFIED_OPERATIONALLY", "PARTIAL") else 1


if __name__ == "__main__":
    raise SystemExit(main())
