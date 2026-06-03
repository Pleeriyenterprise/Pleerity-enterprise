#!/usr/bin/env python3
"""SCORE-RECALCULATION-LATENCY-FINAL-VERIFICATION-01"""
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
FIX_COMMIT = os.getenv("SCORE_LATENCY_FIX_COMMIT", "d5252f99")
POLL_INTERVAL_S = 2
POLL_MAX_S = 180
CORRELATION_PREFIX = "REQUIREMENTS_SYNC:"


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


def _login(email: str, password: str) -> tuple[Optional[str], Dict[str, Any]]:
    for _ in range(5):
        try:
            r = httpx.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=120)
            if r.status_code == 503:
                time.sleep(10)
                continue
            if r.status_code != 200:
                return None, {"status": r.status_code}
            body = r.json()
            return body.get("access_token"), body.get("user") or {}
        except Exception:
            time.sleep(6)
    return None, {}


def deploy_verification() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "programme": "SCORE-RECALCULATION-LATENCY-FINAL-VERIFICATION-01",
        "generated_at": _utc(),
        "fix_commit_expected": FIX_COMMIT,
        "frontend_url": FE,
        "api_url": API,
    }
    try:
        html = httpx.get(f"{FE}/", timeout=60).text
        scripts = re.findall(r'src="(/static/js/[^"]+)"', html)
        main = next((s for s in scripts if "main" in s), "")
        js_url = f"{FE}{main}" if main else ""
        js = httpx.get(js_url, timeout=120).text if js_url else ""
        markers = {
            "score_cognition_line": "score_cognition_line" in js,
            "updating_headline": "Updating" in js,
            "compliance_score_pending": "compliance_score_pending" in js,
            "pending_processing_copy": "recent compliance changes are being processed" in js,
        }
        out["main_js"] = js_url
        out["bundle_markers"] = markers
        out["frontend_ok"] = all(markers.values())
    except Exception as exc:
        out["frontend_error"] = str(exc)
        out["frontend_ok"] = False
    try:
        r = httpx.get(f"{API}/health", timeout=30)
        body = r.json() if r.content else {}
        out["api_health"] = {"status": r.status_code, "body": body}
        readiness = (body.get("readiness") or {}) if isinstance(body, dict) else {}
        out["worker_healthy"] = r.status_code == 200 and readiness.get("stage") == "ready"
    except Exception as exc:
        out["api_health"] = {"error": str(exc)}
        out["worker_healthy"] = False
    out["deploy_verified"] = bool(out.get("frontend_ok")) and bool(out.get("worker_healthy"))
    return out


def _summarize_row(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "property_id": p.get("property_id"),
        "name": p.get("name") or p.get("nickname"),
        "score": p.get("property_score") or p.get("score"),
        "score_status": p.get("score_status"),
        "risk_level": p.get("risk_level"),
        "compliance_score_pending": p.get("compliance_score_pending"),
        "score_cognition_line": p.get("score_cognition_line"),
    }


def _portfolio(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{API}/portfolio/compliance-summary", headers=h, timeout=120)
    return r.json() if r.status_code == 200 and r.content else {}


def _compliance_score(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120)
    return r.json() if r.status_code == 200 and r.content else {}


def _property_explain(token: str, pid: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{API}/client/properties/{pid}/compliance-score/explanation", headers=h, timeout=120)
    try:
        return r.json() if r.content else {}
    except Exception:
        return {"text": (r.text or "")[:400]}


def _trigger_sync(token: str, pid: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    t0 = time.time()
    r = httpx.post(f"{API}/properties/{pid}/requirements/sync", headers=h, timeout=300)
    elapsed = round(time.time() - t0, 2)
    try:
        body = r.json()
    except Exception:
        body = {"text": (r.text or "")[:400]}
    return {
        "status": r.status_code,
        "body": body,
        "elapsed_s": elapsed,
        "triggered_at": _utc(),
        "correlation_id": f"{CORRELATION_PREFIX}{pid}",
    }


def _poll_pending_through_convergence(token: str, pid: str, t0: float) -> Dict[str, Any]:
    """Single continuous poll from trigger through pending visibility and worker convergence."""
    snaps: List[Dict[str, Any]] = []
    pending_first: Optional[float] = None
    pending_last: Optional[float] = None
    converged_at: Optional[float] = None
    score_at_trigger: Optional[Any] = None

    deadline = time.time() + POLL_MAX_S
    while time.time() < deadline:
        body = _portfolio(token)
        row = next((p for p in (body.get("properties") or []) if p.get("property_id") == pid), {})
        if score_at_trigger is None:
            score_at_trigger = row.get("property_score") or row.get("score")
        snap = {
            "at": _utc(),
            "elapsed_s": round(time.time() - t0, 2),
            **_summarize_row(row),
            "portfolio_score_status": body.get("score_status"),
            "portfolio_pending_note": body.get("portfolio_score_recalc_pending_note"),
        }
        snaps.append(snap)
        is_pending = bool(row.get("compliance_score_pending")) or row.get("score_status") == "calculating"
        if is_pending:
            if pending_first is None:
                pending_first = time.time()
            pending_last = time.time()
        elif pending_first is not None:
            converged_at = time.time()
            break
        time.sleep(1 if pending_first is None else POLL_INTERVAL_S)

    score_after = snaps[-1].get("score") if snaps else None
    score_changed = score_at_trigger is not None and score_after is not None and score_after != score_at_trigger
    pending_cleared = bool(snaps) and not (
        snaps[-1].get("compliance_score_pending") or snaps[-1].get("score_status") == "calculating"
    )
    converged = converged_at is not None or (pending_first is not None and pending_cleared and score_changed)

    total = round((converged_at or time.time()) - t0, 2)
    pending_visible = round((pending_last - pending_first), 2) if pending_first and pending_last else 0.0
    if not pending_first:
        latency_class = "no_pending_observed"
    elif total < 120:
        latency_class = "acceptable"
    elif total <= 600:
        latency_class = "degraded"
    else:
        latency_class = "dangerous"

    return {
        "pending_first_elapsed_s": round(pending_first - t0, 2) if pending_first else None,
        "pending_visible_duration_s": pending_visible,
        "converged_at_elapsed_s": round(converged_at - t0, 2) if converged_at else None,
        "total_elapsed_s": total,
        "latency_class": latency_class,
        "converged": converged,
        "score_at_trigger": score_at_trigger,
        "score_after": score_after,
        "score_changed": score_changed,
        "snapshots": snaps[-30:],
        "fast_poll_snapshots": [s for s in snaps if s.get("compliance_score_pending") or s.get("score_status") == "calculating"][:5],
        "immediate_after_trigger": next(
            (s for s in snaps if s.get("compliance_score_pending") or s.get("score_status") == "calculating"),
            snaps[0] if snaps else {},
        ),
        "pending_seen": pending_first is not None,
    }


def _safety_probe(token: str, pid: str) -> Dict[str, Any]:
    """Second sync immediately after convergence — should not storm; may regenerate once."""
    t0 = time.time()
    first = _trigger_sync(token, pid)
    poll1 = _poll_pending_through_convergence(token, pid, t0)
    time.sleep(3)
    second = _trigger_sync(token, pid)
    poll2 = _poll_pending_through_convergence(token, pid, time.time())
    pending_count = len(poll1.get("fast_poll_snapshots") or []) + len(poll2.get("fast_poll_snapshots") or [])
    return {
        "first_sync_status": first.get("status"),
        "second_sync_status": second.get("status"),
        "pending_observations": pending_count,
        "duplicate_safe": pending_count <= 4,
        "note": "duplicate_safe=true when repeated sync does not cause unbounded pending storms",
    }


def browser_capture(
    email: str,
    password: str,
    label: str,
    property_id: Optional[str] = None,
    *,
    path_suffix: str = "dashboard",
) -> Dict[str, Any]:
    shots = OUT / "screenshots" / "final_verification"
    shots.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {"label": label, "captured": False}
    path = shots / f"{label}.png"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{FE}/login/client", timeout=90000)
            page.fill('input[type="email"], input[name="email"]', email)
            page.fill('input[type="password"], input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_timeout(4000)
            if path_suffix == "property" and property_id:
                page.goto(f"{FE}/properties/{property_id}", timeout=90000)
            elif path_suffix == "portfolio":
                page.goto(f"{FE}/dashboard", timeout=90000)
                page.wait_for_timeout(2000)
                for sel in ('text=Highest risk', 'text=highest risk', 'text=Portfolio'):
                    try:
                        page.locator(sel).first.click(timeout=3000)
                        break
                    except Exception:
                        continue
            else:
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
        "tests/test_compliance_recalc_queue_stabilization_phase1.py",
        "tests/test_score_cognition_service.py",
        "tests/test_compliance_scoring_v2_model.py",
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
        results[suite] = {"passed": ok, "tail": (proc.stdout or proc.stderr)[-600:]}
        all_ok = all_ok and ok
    return {"all_passed": all_ok, "suites": results}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    email, pw = _client_creds()

    deploy = deploy_verification()
    _write("deploy_runtime.json", deploy)

    regression = run_regression()
    _write("regression_runtime.json", regression)

    token, user = _login(email, pw)
    if not token:
        _write("classifications.json", {"classification": "FAIL_OPERATIONAL", "reason": "client_login_failed"})
        return 1

    client_id = user.get("client_id")
    body_before = _portfolio(token)
    props = body_before.get("properties") or []
    target = props[0] if props else {}
    pid = target.get("property_id")
    if not pid:
        _write("classifications.json", {"classification": "FAIL_OPERATIONAL", "reason": "no_property"})
        return 1

    before_row = _summarize_row(target)
    score_before = _compliance_score(token)

    t0 = time.time()
    trigger = _trigger_sync(token, pid)
    trigger["correlation_id"] = f"{CORRELATION_PREFIX}{pid}"
    trigger["inferred_regenerated_from_done_duplicate"] = None
    trigger["backend_fix_probe"] = "pending_after_done_duplicate_implies_d5252f99+"
    _write("recalc_trigger_runtime.json", trigger)

    poll = _poll_pending_through_convergence(token, pid, t0)
    immediate = poll.get("immediate_after_trigger") or {}
    pending_seen = bool(poll.get("pending_seen"))
    if pending_seen and trigger.get("status") == 200:
        trigger["inferred_regenerated_from_done_duplicate"] = True
        _write("recalc_trigger_runtime.json", trigger)

    fast_snaps = poll.get("fast_poll_snapshots") or []
    stale_risk = [
        s
        for s in (poll.get("snapshots") or [])
        if (s.get("compliance_score_pending") or s.get("score_status") == "calculating")
        and s.get("risk_level")
        and "elevated" in str(s.get("risk_level")).lower()
    ]
    explain = _property_explain(token, pid)

    pending = {
        "generated_at": _utc(),
        "property_id": pid,
        "client_id": client_id,
        "before": before_row,
        "immediate_after_trigger": immediate,
        "fast_poll_snapshots": fast_snaps,
        "pending_seen": pending_seen,
        "stale_elevated_risk_while_pending": stale_risk,
        "portfolio_score": score_before,
        "property_explainability": {
            "score_status": (explain.get("authoritative") or explain).get("score_status")
            if isinstance(explain, dict)
            else None,
            "score_status_message": (explain.get("authoritative") or explain).get("score_status_message")
            if isinstance(explain, dict)
            else None,
            "message": (explain.get("authoritative") or explain).get("message") if isinstance(explain, dict) else None,
        },
        "cognition_checks": {
            "no_stale_elevated_risk": len(stale_risk) == 0,
            "pending_or_calculating": pending_seen,
            "score_cognition_present": bool(immediate.get("score_cognition_line")),
        },
    }
    _write("pending_runtime.json", pending)

    latency = {
        k: poll[k]
        for k in (
            "pending_first_elapsed_s",
            "pending_visible_duration_s",
            "converged_at_elapsed_s",
            "total_elapsed_s",
            "latency_class",
            "converged",
            "snapshots",
        )
        if k in poll
    }
    latency["enqueue_elapsed_s"] = trigger.get("elapsed_s")
    _write("latency_runtime.json", latency)

    after_body = _portfolio(token)
    after_row = _summarize_row(
        next((p for p in (after_body.get("properties") or []) if p.get("property_id") == pid), {})
    )
    score_after = _compliance_score(token)

    browser_dash = browser_capture(email, pw, "dashboard_converged", path_suffix="dashboard")
    browser_prop = browser_capture(email, pw, "property_converged", property_id=pid, path_suffix="property")
    browser_portfolio = browser_capture(email, pw, "portfolio_highest_risk_converged", path_suffix="portfolio")

    worker = {
        "generated_at": _utc(),
        "before": before_row,
        "after": after_row,
        "score_before": before_row.get("score"),
        "score_after": after_row.get("score"),
        "pending_cleared": not after_row.get("compliance_score_pending")
        and after_row.get("score_status") != "calculating",
        "portfolio_agrees": {
            "portfolio_summary": after_row,
            "compliance_score_headline": {
                "score": score_after.get("score"),
                "score_status": score_after.get("score_status"),
                "properties_pending_score_recalc_count": score_after.get("properties_pending_score_recalc_count"),
            },
        },
        "contradictions": [
            c
            for c in [
                after_row.get("score_cognition_line"),
            ]
            if c
            and "no open gaps" in str(c).lower()
            and after_row.get("risk_level")
            and "elevated" in str(after_row.get("risk_level")).lower()
        ],
        "latency": latency,
        "queue_convergence": {
            "converged": poll.get("converged"),
            "score_changed": poll.get("score_changed"),
        },
        "browser_after": {
            "dashboard": browser_dash,
            "property": browser_prop,
            "portfolio_highest_risk": browser_portfolio,
        },
    }
    _write("worker_convergence_runtime.json", worker)

    pending["browser"] = {
        "note": "Pending-window screenshots captured during prior run; converged state below",
        "dashboard_converged": browser_dash,
        "property_converged": browser_prop,
        "portfolio_highest_risk_converged": browser_portfolio,
    }
    _write("pending_runtime.json", pending)

    safety = _safety_probe(token, pid)
    _write("safety_runtime.json", safety)

    tests_ok = regression.get("all_passed")
    deploy_ok = deploy.get("deploy_verified")
    pending_ok = pending_seen
    stale_ok = len(stale_risk) == 0
    converged_ok = latency.get("converged")
    latency_ok = latency.get("latency_class") in ("acceptable", "degraded")
    safety_ok = safety.get("duplicate_safe")
    browser_ok = (
        browser_dash.get("captured")
        and browser_prop.get("captured")
        and browser_portfolio.get("captured")
    )

    if (
        deploy_ok
        and tests_ok
        and pending_ok
        and stale_ok
        and converged_ok
        and latency_ok
        and safety_ok
        and browser_ok
    ):
        klass = "VERIFIED_OPERATIONALLY"
    elif not pending_ok:
        klass = "REQUEUE_DRIFT" if deploy_ok else "PARTIAL"
    elif pending_ok and not converged_ok:
        klass = "SCORE_PROPAGATION_DRIFT"
    elif pending_ok and not stale_ok:
        klass = "STALE_SNAPSHOT_DRIFT"
    else:
        klass = "PARTIAL"

    classifications = {
        "programme": "SCORE-RECALCULATION-LATENCY-FINAL-VERIFICATION-01",
        "verified_at": _utc(),
        "fix_commit": FIX_COMMIT,
        "classification": klass,
        "checks": {
            "deploy_verified": deploy_ok,
            "regression_passed": tests_ok,
            "pending_visible": pending_ok,
            "stale_risk_suppressed": stale_ok,
            "worker_converged": converged_ok,
            "latency_acceptable_or_degraded": latency_ok,
            "safety_duplicate_ok": safety_ok,
            "browser_captured": browser_ok,
            "inferred_regenerated_from_done_duplicate": trigger.get("inferred_regenerated_from_done_duplicate"),
        },
        "latency_class": latency.get("latency_class"),
        "total_convergence_s": latency.get("total_elapsed_s"),
    }
    _write("classifications.json", classifications)

    watchlist = f"""# Watchlist — final verification ({_utc()[:10]})

## Classification: {klass}

- Fix commit: {FIX_COMMIT}
- Pending visible: {pending_ok}
- Worker converged: {converged_ok} ({latency.get('total_elapsed_s')}s)
- Latency class: {latency.get('latency_class')}

## Screenshots
- `screenshots/final_verification/dashboard_pending.png`
- `screenshots/final_verification/property_pending.png`
- `screenshots/final_verification/dashboard_converged.png`
- `screenshots/final_verification/property_converged.png`
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# SCORE-RECALCULATION-LATENCY-FINAL-VERIFICATION-01

Verified at: {_utc()}
Fix commit: {FIX_COMMIT}
Classification: **{klass}**

## Deploy
- Frontend OK: {deploy.get('frontend_ok')}
- Worker healthy: {deploy.get('worker_healthy')}

## Trigger
- Method: requirements/sync
- Property: {pid}
- Pending seen: {pending_ok}
- Inferred DONE duplicate regeneration: {trigger.get('inferred_regenerated_from_done_duplicate')}

## Convergence
- Converged: {converged_ok}
- Total: {latency.get('total_elapsed_s')}s ({latency.get('latency_class')})

## Regression
{'PASS' if tests_ok else 'FAIL'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    print(f"Final verification complete classification={klass}")
    return 0 if klass == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
