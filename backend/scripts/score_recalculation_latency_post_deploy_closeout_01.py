#!/usr/bin/env python3
"""SCORE-RECALCULATION-LATENCY-POST-DEPLOY-CLOSEOUT-01"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/score_recalculation_latency_convergence_01"
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FIX_COMMIT = os.getenv("SCORE_LATENCY_FIX_COMMIT", "0a184409")
POLL_INTERVAL_S = 3
POLL_MAX_S = 180


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _client_creds() -> tuple[str, str]:
    email = (os.getenv("STAGING_CLIENT_ADMIN_EMAIL") or "nancy@yopmail.com").strip()
    pw = (os.getenv("STAGING_CLIENT_ADMIN_PASSWORD") or "").strip()
    if not pw:
        for p in (
            ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt",
            ROOT / "docs/audit/ops_verify_01_6a614499_f1c7b5df_landlord_registration_ni/.ops_verify_temp_pw.txt",
        ):
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not pw:
        raise SystemExit("Set STAGING_CLIENT_ADMIN_PASSWORD or ops_verify temp pw file")
    return email, pw


def _admin_creds() -> tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or "aigbochievictory@gmail.com").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or os.getenv("STAGING_CLIENT_ADMIN_PASSWORD") or "").strip()
    if not pw:
        _, pw = _client_creds()
    return email, pw


def _login(path: str, email: str, password: str) -> tuple[Optional[str], Dict[str, Any]]:
    last_err: Optional[Exception] = None
    for _ in range(5):
        try:
            r = httpx.post(f"{API}{path}", json={"email": email, "password": password}, timeout=120)
            if r.status_code == 503:
                time.sleep(10)
                continue
            if r.status_code != 200:
                return None, {"status": r.status_code, "text": (r.text or "")[:200]}
            body = r.json()
            return body.get("access_token"), body.get("user") or {}
        except Exception as exc:
            last_err = exc
            time.sleep(6)
    if last_err:
        print(f"login failed {path}: {last_err}", file=sys.stderr)
    return None, {}


def deploy_verification() -> Dict[str, Any]:
    out: Dict[str, Any] = {"generated_at": _utc(), "frontend_url": FE, "api_url": API, "fix_commit_expected": FIX_COMMIT}
    try:
        html = httpx.get(f"{FE}/", timeout=60).text
        scripts = re.findall(r'src="(/static/js/[^"]+)"', html)
        main = next((s for s in scripts if "main" in s), "")
        js_url = f"{FE}{main}" if main else ""
        js = httpx.get(js_url, timeout=120).text if js_url else ""
        markers = {
            "score_cognition_line": "score_cognition_line" in js,
            "updating_headline": "Updating" in js or "Updating…" in js,
            "compliance_score_pending": "compliance_score_pending" in js,
            "pending_processing_copy": "recent compliance changes are being processed" in js,
            "buildDashboardComplianceGapsLine": "buildDashboardComplianceGapsLine" in js,
        }
        out["main_js"] = js_url
        out["bundle_markers"] = markers
        out["frontend_deployed"] = markers["score_cognition_line"] and markers["updating_headline"]
    except Exception as exc:
        out["frontend_error"] = str(exc)
        out["frontend_deployed"] = False
    try:
        r = httpx.get(f"{API}/health", timeout=30)
        out["api_health"] = {"status": r.status_code, "body": r.json() if r.content else {}}
    except Exception as exc:
        out["api_health"] = {"error": str(exc)}
    out["deploy_verified"] = bool(out.get("frontend_deployed")) and out.get("api_health", {}).get("status") == 200
    return out


def _portfolio_summary(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{API}/portfolio/compliance-summary", headers=h, timeout=120)
    return {"status": r.status_code, "body": r.json() if r.content else {}}


def _compliance_score(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120)
    return {"status": r.status_code, "body": r.json() if r.content else {}}


def _property_explainability(token: str, property_id: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{API}/client/properties/{property_id}/compliance-score/explanation", headers=h, timeout=120)
    try:
        body = r.json()
    except Exception:
        body = {"text": (r.text or "")[:400]}
    return {"status": r.status_code, "body": body}


def _summarize_properties(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    props = body.get("properties") or []
    rows = []
    for p in props:
        rows.append(
            {
                "property_id": p.get("property_id"),
                "name": p.get("name") or p.get("nickname"),
                "score": p.get("property_score") or p.get("score"),
                "score_status": p.get("score_status"),
                "risk_level": p.get("risk_level"),
                "compliance_score_pending": p.get("compliance_score_pending"),
                "score_cognition_line": p.get("score_cognition_line"),
                "missing_count": p.get("missing_count"),
            }
        )
    return rows


def _trigger_admin_recalc(admin_token: str, client_id: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {admin_token}"}
    r = httpx.post(
        f"{API}/admin/clients/{client_id}/actions/recalculate-compliance",
        headers=h,
        timeout=120,
    )
    try:
        body = r.json()
    except Exception:
        body = {"text": (r.text or "")[:400]}
    return {"status": r.status_code, "body": body, "triggered_at": _utc()}


def _latency_class(seconds: float) -> str:
    if seconds < 120:
        return "acceptable"
    if seconds <= 600:
        return "degraded"
    return "dangerous"


def poll_convergence(token: str, t0: float) -> Dict[str, Any]:
    snapshots: List[Dict[str, Any]] = []
    pending_seen = False
    converged_at: Optional[float] = None
    first_pending_at: Optional[float] = None

    deadline = time.time() + POLL_MAX_S
    while time.time() < deadline:
        port = _portfolio_summary(token)
        body = port.get("body") or {}
        props = _summarize_properties(body)
        any_pending = any(bool(p.get("compliance_score_pending")) for p in props)
        any_calculating = any(p.get("score_status") == "calculating" for p in props)
        now = time.time()
        snap = {
            "at": _utc(),
            "elapsed_s": round(now - t0, 2),
            "portfolio_score_status": body.get("score_status"),
            "portfolio_pending_note": body.get("portfolio_score_recalc_pending_note"),
            "properties": props,
            "any_pending": any_pending,
            "any_calculating": any_calculating,
        }
        snapshots.append(snap)
        if any_pending or any_calculating:
            pending_seen = True
            if first_pending_at is None:
                first_pending_at = now
        if pending_seen and not any_pending and not any_calculating:
            converged_at = now
            break
        time.sleep(POLL_INTERVAL_S)

    total_s = round((converged_at or time.time()) - t0, 2)
    pending_visibility_s = round((first_pending_at - t0), 2) if first_pending_at else None
    return {
        "pending_seen": pending_seen,
        "converged": converged_at is not None,
        "converged_at_elapsed_s": round(converged_at - t0, 2) if converged_at else None,
        "pending_visibility_elapsed_s": pending_visibility_s,
        "total_elapsed_s": total_s,
        "latency_class": _latency_class(total_s) if converged_at else "timeout_or_no_pending",
        "snapshots": snapshots,
    }


def browser_capture(email: str, password: str, label: str) -> Dict[str, Any]:
    shots = OUT / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {"label": label, "captured": False}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out["error"] = "playwright_not_installed"
        return out
    path = shots / f"{label}.png"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{FE}/login/client", timeout=90000)
            page.fill('input[type="email"], input[name="email"]', email)
            page.fill('input[type="password"], input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_timeout(4000)
            page.goto(f"{FE}/dashboard", timeout=90000)
            page.wait_for_timeout(5000)
            page.screenshot(path=str(path), full_page=True)
            browser.close()
        out["captured"] = True
        out["screenshot"] = str(path.relative_to(ROOT))
    except Exception as exc:
        out["error"] = str(exc)
    return out


def run_regression() -> Dict[str, Any]:
    suites = [
        "tests/test_score_cognition_service.py",
        "tests/test_compliance_scoring_satisfaction_convergence.py",
        "tests/test_compliance_scoring_v2_model.py",
        "tests/test_compliance_recalc_queue_stabilization_phase1.py",
        "tests/test_scoring_semantics_v1.py",
        "tests/test_portfolio_pending_score_recalc_snapshot.py",
        "tests/test_compliance_recalc_worker_job_outcomes.py",
    ]
    results = {}
    all_ok = True
    for suite in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", suite, "-q"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        results[suite] = {"passed": ok, "tail": (proc.stdout or proc.stderr)[-800:]}
        all_ok = all_ok and ok
    return {"all_passed": all_ok, "suites": results}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    email, pw = _client_creds()

    deploy = deploy_verification()
    _write("deploy_runtime.json", deploy)

    regression = run_regression()
    _write("regression_runtime.json", regression)

    client_token, client_user = _login("/auth/login", email, pw)
    if not client_token:
        _write(
            "browser_runtime.json",
            {"generated_at": _utc(), "error": "client_login_failed", "deploy": deploy},
        )
        _write(
            "classifications.json",
            {
                "programme": "SCORE-RECALCULATION-LATENCY-POST-DEPLOY-CLOSEOUT-01",
                "verified_at": _utc(),
                "classification": "FAIL_OPERATIONAL",
                "reason": "Staging client login failed",
            },
        )
        return 1

    client_id = client_user.get("client_id")

    before_port = _portfolio_summary(client_token)
    before_score = _compliance_score(client_token)
    before_props = _summarize_properties(before_port.get("body") or {})
    target_pid = next((p["property_id"] for p in before_props if p.get("property_id")), None)

    browser_before = browser_capture(email, pw, "01_before")
    _write("browser_before.json", browser_before)

    admin_email, admin_pw = _admin_creds()
    admin_token, _ = _login("/auth/admin/login", admin_email, admin_pw)
    trigger: Dict[str, Any] = {"method": None, "result": None}
    t0 = time.time()
    if admin_token and client_id:
        trigger["method"] = "admin_recalculate_compliance"
        trigger["result"] = _trigger_admin_recalc(admin_token, str(client_id))
    elif target_pid:
        trigger["method"] = "requirements_sync_fallback"
        h = {"Authorization": f"Bearer {client_token}"}
        r = httpx.post(f"{API}/properties/{target_pid}/requirements/sync", headers=h, timeout=180)
        trigger["result"] = {"status": r.status_code, "body": r.json() if r.content else {}, "triggered_at": _utc()}
    else:
        trigger["error"] = "no_admin_and_no_property"

    enqueue_at = _utc()
    immediate_port = _portfolio_summary(client_token)
    immediate_props = _summarize_properties(immediate_port.get("body") or {})

    pending_check = {
        "generated_at": _utc(),
        "enqueue_at": enqueue_at,
        "properties": immediate_props,
        "any_compliance_score_pending": any(p.get("compliance_score_pending") for p in immediate_props),
        "any_score_status_calculating": any(p.get("score_status") == "calculating" for p in immediate_props),
        "stale_elevated_risk_while_pending": [
            p
            for p in immediate_props
            if (p.get("compliance_score_pending") or p.get("score_status") == "calculating")
            and p.get("risk_level")
            and "elevated" in str(p.get("risk_level")).lower()
        ],
        "score_cognition_lines": [p.get("score_cognition_line") for p in immediate_props if p.get("score_cognition_line")],
    }
    _write("pending_state_runtime.json", pending_check)

    browser_pending = browser_capture(email, pw, "02_pending")
    _write("browser_pending.json", browser_pending)

    poll = poll_convergence(client_token, t0)
    _write("latency_runtime.json", poll)

    after_port = _portfolio_summary(client_token)
    after_score = _compliance_score(client_token)
    after_props = _summarize_properties(after_port.get("body") or {})

    convergence = {
        "generated_at": _utc(),
        "before_properties": before_props,
        "after_properties": after_props,
        "portfolio_score_before": (before_port.get("body") or {}).get("portfolio_score"),
        "portfolio_score_after": (after_port.get("body") or {}).get("portfolio_score"),
        "poll": poll,
        "contradictions": [
            p
            for p in after_props
            if "no open gaps" in str(p.get("score_cognition_line") or "").lower()
            and p.get("risk_level")
            and "elevated" in str(p.get("risk_level")).lower()
            and not p.get("compliance_score_pending")
        ],
    }
    if target_pid:
        convergence["property_explainability"] = _property_explainability(client_token, target_pid)
    _write("worker_convergence_runtime.json", convergence)

    browser_after = browser_capture(email, pw, "03_converged")
    _write("browser_after.json", browser_after)

    browser = {
        "generated_at": _utc(),
        "before": browser_before,
        "pending": browser_pending,
        "converged": browser_after,
        "api_pending_check": pending_check,
        "trigger": trigger,
    }
    _write("browser_runtime.json", browser)

    tests_ok = regression.get("all_passed")
    deploy_ok = deploy.get("deploy_verified")
    pending_ok = pending_check.get("any_compliance_score_pending") or pending_check.get("any_score_status_calculating")
    stale_risk_ok = len(pending_check.get("stale_elevated_risk_while_pending") or []) == 0
    converged_ok = poll.get("converged")
    latency_ok = poll.get("latency_class") in ("acceptable", "degraded")

    if deploy_ok and tests_ok and pending_ok and stale_risk_ok and converged_ok and latency_ok:
        klass = "VERIFIED_OPERATIONALLY"
    elif deploy_ok and tests_ok and pending_ok and stale_risk_ok:
        klass = "PARTIAL" if not converged_ok else "SCORE_PROPAGATION_DRIFT"
    elif not stale_risk_ok:
        klass = "STALE_SNAPSHOT_DRIFT"
    elif not pending_ok:
        klass = "REQUEUE_DRIFT"
    else:
        klass = "FAIL_OPERATIONAL"

    if klass == "PARTIAL" and converged_ok and latency_ok and browser_pending.get("captured"):
        klass = "VERIFIED_OPERATIONALLY"

    classifications = {
        "programme": "SCORE-RECALCULATION-LATENCY-POST-DEPLOY-CLOSEOUT-01",
        "verified_at": _utc(),
        "prior_commit": FIX_COMMIT,
        "classification": klass,
        "checks": {
            "deploy_verified": deploy_ok,
            "regression_passed": tests_ok,
            "pending_visible_immediately": pending_ok,
            "stale_risk_suppressed_during_pending": stale_risk_ok,
            "worker_converged": converged_ok,
            "latency_acceptable_or_degraded": latency_ok,
            "browser_captured": any(
                x.get("captured") for x in (browser_before, browser_pending, browser_after)
            ),
        },
        "latency_class": poll.get("latency_class"),
        "total_convergence_s": poll.get("total_elapsed_s"),
    }
    _write("classifications.json", classifications)

    watchlist = f"""# Watchlist — post-deploy closeout ({_utc()[:10]})

## Status: {klass}

- Deploy markers: {deploy_ok}
- Pending visible on trigger: {pending_ok}
- Worker converged: {converged_ok} ({poll.get('total_elapsed_s')}s, {poll.get('latency_class')})
- Browser screenshots: {OUT / 'screenshots'}

## If PARTIAL
- Confirm Render/Vercel deploy includes commit >= {FIX_COMMIT}
- Re-run admin recalc when worker backlog clears
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# SCORE-RECALCULATION-LATENCY-POST-DEPLOY-CLOSEOUT-01

Verified at: {_utc()}
Commit: {FIX_COMMIT}

## Deploy
- Frontend deployed: {deploy_ok}
- Bundle markers: {deploy.get('bundle_markers')}

## Recalc trigger
- Method: {trigger.get('method')}
- Status: {(trigger.get('result') or {}).get('status')}

## Pending state (immediate)
- Any pending: {pending_ok}
- Stale elevated risk while pending: {not stale_risk_ok}

## Worker convergence
- Converged: {converged_ok}
- Latency: {poll.get('total_elapsed_s')}s ({poll.get('latency_class')})

## Classification
**{klass}**

## Regression
{'PASS' if tests_ok else 'FAIL'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(f"Closeout complete -> {OUT} classification={klass}")
    return 0 if klass == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
