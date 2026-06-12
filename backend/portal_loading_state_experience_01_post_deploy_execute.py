#!/usr/bin/env python3
"""
PORTAL-LOADING-STATE-EXPERIENCE-01 — post-deploy staging browser verification.
"""
from __future__ import annotations

import importlib.util
import json
import re
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
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/portal_loading_state_experience_01"
SHOT = OUT / "screenshots"
PROGRAMME = "PORTAL-LOADING-STATE-EXPERIENCE-01-POST-DEPLOY"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MIN_COMMIT = "3e974609"
NANCY_EMAIL = "nancy@yopmail.com"
PW_PATH = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"

_fc_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_fc", _fc_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)
API = _fc.API
FRONTEND = _fc.FRONTEND.rstrip("/")

BUNDLE_MARKERS = ["portal_loading_started", "today-page-loading", "command-center-primary-loading"]
REQUIRED_FRONTEND_MARKERS = ["portal_loading_started", "today-page-loading"]


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def deploy_proof() -> Dict[str, Any]:
    proof: Dict[str, Any] = {"run_tag": RUN_TAG, "min_commit": MIN_COMMIT}
    try:
        ver = httpx.get(f"{API}/version", timeout=60).json()
        sha = str(ver.get("commit_sha") or "")
        proof["api_version"] = {"commit_sha": sha, "environment": ver.get("environment")}
        proof["api_deploy_match"] = sha.startswith(MIN_COMMIT) or MIN_COMMIT in sha
    except Exception as exc:
        proof["api_version"] = {"error": str(exc)[:200]}
        proof["api_deploy_match"] = False

    marker_hits: Dict[str, List[str]] = {}
    chunks: List[str] = []
    try:
        html = httpx.get(FRONTEND, timeout=60, follow_redirects=True).text
        scripts = re.findall(r'src="(/static/js/[^"]+\.js)"', html)
        for rel in scripts[:14]:
            try:
                js = httpx.get(f"{FRONTEND}{rel}", timeout=90).text
                chunks.append(rel)
                for m in BUNDLE_MARKERS:
                    if m in js:
                        marker_hits.setdefault(m, []).append(rel)
            except Exception:
                continue
        proof["frontend_chunks_checked"] = chunks
        proof["frontend_marker_hits"] = marker_hits
        proof["frontend_deploy_match"] = all(marker_hits.get(m) for m in REQUIRED_FRONTEND_MARKERS)
    except Exception as exc:
        proof["frontend_error"] = str(exc)[:200]
        proof["frontend_deploy_match"] = False

    proof["deploy_ready"] = proof.get("api_deploy_match") and proof.get("frontend_deploy_match")
    return proof


def login_session() -> tuple[str, Dict[str, Any]]:
    pw = PW_PATH.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": NANCY_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body["token"]
    user = body.get("user") or {"email": NANCY_EMAIL, "role": "ROLE_CLIENT", "client_id": body.get("client_id")}
    return token, user


def run_regression() -> Dict[str, Any]:
    cmd = (
        'npx react-scripts test --watchAll=false '
        '"--testPathPattern=PortalLoadingState|PortalCardLoading|ClientCommandCenterPage|ClientDashboard.score"'
    )
    fe = subprocess.run(
        cmd,
        cwd=str(ROOT.parent / "frontend"),
        capture_output=True,
        text=True,
        shell=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = fe.stdout or ""
    stderr = fe.stderr or ""
    return {
        "exit_code": fe.returncode,
        "pass": fe.returncode == 0,
        "stdout_tail": stdout[-3000:],
        "stderr_tail": stderr[-1500:],
    }


def browser_verify(token: str, user: Dict[str, Any]) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"skipped": True, "reason": "playwright not installed"}

    SHOT.mkdir(parents=True, exist_ok=True)
    analytics_events: List[Dict[str, Any]] = []
    results: Dict[str, Any] = {"pages": {}, "analytics": [], "accessibility": {}}

    def on_analytics(request):
        if "/client/analytics/events" in request.url and request.method == "POST":
            try:
                body = request.post_data_json or {}
                analytics_events.append(body)
            except Exception:
                pass

    delay_s = 12

    def install_delay_route(page, pattern: str) -> None:
        def handler(route):
            time.sleep(delay_s)
            route.continue_()

        page.route(pattern, handler)

    def auth_page(context, viewport: Dict[str, int]):
        page = context.new_page()
        page.set_viewport_size(viewport)
        page.on("request", on_analytics)
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
        return page

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for viewport_name, viewport in [("desktop", {"width": 1280, "height": 800}), ("mobile_390", {"width": 390, "height": 844})]:
            def verify_page(
                page_key: str,
                path: str,
                delay_glob: str,
                loading_testid: str,
                ready_testid: str,
                text_needle: str,
                extra_loading: Optional[Any] = None,
            ) -> None:
                row: Dict[str, Any] = {"pass": False}
                try:
                    ctx = browser.new_context(viewport=viewport)
                    page = auth_page(ctx, viewport)
                    install_delay_route(page, delay_glob)
                    page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120000)
                    page.wait_for_selector(f'[data-testid="{loading_testid}"]', timeout=60000)
                    loading = page.locator(f'[data-testid="{loading_testid}"]')
                    row["role_status"] = loading.get_attribute("role") == "status"
                    row["aria_live"] = loading.get_attribute("aria-live") == "polite"
                    row["loading_copy"] = loading.inner_text(timeout=5000)[:500]
                    row["staged_copy_ok"] = text_needle in row["loading_copy"]
                    if extra_loading:
                        row.update(extra_loading(page))
                    page.screenshot(path=str(SHOT / f"{viewport_name}_{page_key}_loading.png"), full_page=True)
                    page.unroute(delay_glob)
                    page.wait_for_selector(f'[data-testid="{ready_testid}"]', timeout=180000)
                    row["ready_after_load"] = page.locator(f'[data-testid="{ready_testid}"]').count() > 0
                    row["pass"] = row["staged_copy_ok"] and row["ready_after_load"]
                    if extra_loading and page_key == "dashboard":
                        row["pass"] = row["pass"] and row.get("kpi_preview_cards", False)
                    ctx.close()
                except Exception as exc:
                    row["error"] = str(exc)[:400]
                results["pages"].setdefault(page_key, {})[viewport_name] = row

            verify_page(
                "today",
                "/today",
                "**/api/today/items**",
                "today-page-loading",
                "client-tasks-page",
                "Loading your operational inbox",
            )
            verify_page(
                "command_center",
                "/command-center",
                "**/api/client/command-center**",
                "command-center-primary-loading",
                "command-center-primary-ready",
                "Analysing portfolio health",
            )

            def dash_loading_extra(page):
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                )
                kpi_cards = page.locator('[data-testid="dashboard-kpi-loading-preview"]')
                card_loaders = page.locator(
                    '[data-testid="dashboard-kpi-today-loading"],'
                    '[data-testid="dashboard-kpi-compliance-loading"],'
                    '[data-testid="dashboard-kpi-risk-loading"]'
                )
                loader_count = card_loaders.count()
                return {
                    "kpi_preview_cards": kpi_cards.count() > 0,
                    "kpi_card_loaders": loader_count,
                    "kpi_loading_copy_ok": "Preparing operational summary" in kpi_cards.inner_text(timeout=3000),
                    "horizontal_overflow": overflow,
                    "card_loading_status": loader_count >= 3,
                }

            verify_page(
                "dashboard",
                "/dashboard",
                "**/api/client/dashboard**",
                "dashboard-page-loading",
                "client-dashboard",
                "Loading your dashboard",
                extra_loading=dash_loading_extra,
            )

        browser.close()

    started = [e for e in analytics_events if e.get("event") == "portal_loading_started"]
    completed = [e for e in analytics_events if e.get("event") == "portal_loading_completed"]
    durations = [
        e.get("properties", {}).get("portal_loading_duration_ms")
        for e in completed
        if isinstance(e.get("properties", {}).get("portal_loading_duration_ms"), (int, float))
    ]
    results["analytics"] = {
        "events_captured": len(analytics_events),
        "portal_loading_started": len(started),
        "portal_loading_completed": len(completed),
        "duration_ms_recorded": len(durations) > 0,
        "sample_events": analytics_events[:12],
    }
    return results


def classify(deploy: Dict[str, Any], browser: Dict[str, Any], regression: Dict[str, Any]) -> str:
    if not deploy.get("deploy_ready"):
        return "PARTIAL"
    if browser.get("skipped"):
        return "PARTIAL"
    if not regression.get("pass"):
        return "PARTIAL"

    pages = browser.get("pages", {})
    today = pages.get("today", {}).get("desktop", {})
    cc = pages.get("command_center", {}).get("desktop", {})
    dash = pages.get("dashboard", {}).get("desktop", {})
    mobile_dash = pages.get("dashboard", {}).get("mobile_390", {})
    analytics = browser.get("analytics", {})

    checks = [
        today.get("pass"),
        today.get("role_status"),
        today.get("aria_live"),
        cc.get("pass"),
        cc.get("role_status"),
        cc.get("aria_live"),
        dash.get("pass"),
        dash.get("kpi_preview_cards"),
        dash.get("kpi_loading_copy_ok"),
        dash.get("card_loading_status"),
        not mobile_dash.get("horizontal_overflow", True),
        analytics.get("portal_loading_started", 0) > 0,
        analytics.get("portal_loading_completed", 0) > 0,
        analytics.get("duration_ms_recorded"),
    ]
    if all(checks):
        return "VERIFIED_OPERATIONALLY"
    return "PARTIAL"


def main() -> int:
    deploy = deploy_proof()

    browser: Dict[str, Any] = {"skipped": True}
    if PW_PATH.exists() and sync_playwright is not None:
        try:
            token, user = login_session()
            browser = browser_verify(token, user)
        except Exception as exc:
            browser = {"error": str(exc)[:500]}

    regression = run_regression()
    classification = classify(deploy, browser, regression)
    if classification == "VERIFIED_OPERATIONALLY":
        code_class = "PORTAL_LOADING_STATE_EXPERIENCE_CONVERGED"
    else:
        code_class = "PARTIAL"

    verify = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "commit": MIN_COMMIT,
        "deploy_proof": deploy,
        "browser_verification": browser,
        "regression": regression,
        "classification": classification,
        "code_classification": code_class,
    }
    write("post_deploy_verify.json", verify)
    write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "pre_deploy": "PARTIAL",
            "post_deploy_classification": classification,
            "code_classification": code_class,
            "deploy_ready": deploy.get("deploy_ready"),
        },
    )
    write("regression_runtime.json", {"programme": PROGRAMME, "run_tag": RUN_TAG, **regression})

    watchlist = [
        "- [x] Commit 3e974609 pushed",
        f"- [{'x' if deploy.get('deploy_ready') else ' '}] Staging deploy proof",
        f"- [{'x' if classification == 'VERIFIED_OPERATIONALLY' else ' '}] Browser verification",
    ]
    (OUT / "watchlist.md").write_text(
        f"# {PROGRAMME}\n\n" + "\n".join(watchlist) + "\n",
        encoding="utf-8",
    )

    post_section = f"""## Post-deploy verification

**Run:** `{RUN_TAG}`  
**Classification:** `{classification}` / `{code_class}`

- API deploy match: **{deploy.get('api_deploy_match')}**
- Frontend bundle markers: **{deploy.get('frontend_deploy_match')}**
- Deploy ready: **{deploy.get('deploy_ready')}**
- Regression pass: **{regression.get('pass')}**

See `post_deploy_verify.json` and `screenshots/`.
"""
    report_path = OUT / "REPORT.md"
    if report_path.exists():
        body = report_path.read_text(encoding="utf-8")
        if "## Post-deploy verification" in body:
            body = body.split("## Post-deploy verification")[0].rstrip()
        report_path.write_text(body + "\n\n" + post_section, encoding="utf-8")

    print(f"Classification: {classification}")
    print(f"Deploy ready: {deploy.get('deploy_ready')}")
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
