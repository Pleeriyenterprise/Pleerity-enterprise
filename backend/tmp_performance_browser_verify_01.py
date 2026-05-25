#!/usr/bin/env python3
"""Post-deploy browser verification for PRELAUNCH-PERFORMANCE-RUNTIME-VERIFY-01."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs" / "audit" / "performance_runtime_verify_01"
FRONTEND = "https://pleerityenterprise.co.uk"
API = "https://pleerity-enterprise.onrender.com/api"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
EXPECTED_COMMIT = "cb14b437"
DEPLOY_MARKERS = [
    "portal-stale-refresh-banner",
    "Showing last loaded data while refreshing",
    "PortalPageShell",
    "portal-section-skeleton",
    "clientOperationalFetch",
    "OPERATIONAL_CACHE_KEYS",
]

# Must match frontend/src/utils/clientOperationalFetch.js DEFAULT_STALE_MS
OPERATIONAL_CACHE_STALE_MS = 45_000

SURFACES = [
    ("P1_Today", "/today", "client-tasks-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P2_CommandCentre", "/command-center", "command-center-root", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P3_Dashboard", "/dashboard", "client-dashboard", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P4_Properties", "/properties", "properties-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P5_Requirements", "/requirements", "requirements-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P6_Documents", "/documents", "documents-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P7_RentOperations", "/operations/rent?tab=attention", "rent-operations-page", [], "portal-stale-refresh-banner"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_deploy() -> dict[str, Any]:
    out: dict[str, Any] = {
        "verified_at_utc": utc_now(),
        "expected_commit": EXPECTED_COMMIT,
        "frontend_url": FRONTEND,
    }
    try:
        r = httpx.get(FRONTEND, timeout=30, follow_redirects=True)
        out["frontend_status"] = r.status_code
        html = r.text
    except Exception as exc:
        out["frontend_status"] = "error"
        out["error"] = str(exc)[:300]
        out["deploy_ready"] = False
        return out

    scripts = re.findall(r'src="(/static/js/[^"]+\.js)"', html)
    out["script_chunks_found"] = len(scripts)
    marker_hits: dict[str, list[str]] = {m: [] for m in DEPLOY_MARKERS}
    chunks_checked: list[str] = []
    for rel in scripts[:8]:
        url = f"{FRONTEND}{rel}"
        try:
            js = httpx.get(url, timeout=60).text
            chunks_checked.append(rel)
            for m in DEPLOY_MARKERS:
                if m in js:
                    marker_hits[m].append(rel)
        except Exception:
            continue

    out["chunks_checked"] = chunks_checked
    out["marker_hits"] = {k: v for k, v in marker_hits.items() if v}
    out["markers_found_count"] = sum(1 for v in marker_hits.values() if v)
    out["deploy_ready"] = out["markers_found_count"] >= 3 and bool(
        marker_hits.get("portal-stale-refresh-banner")
    )

    ver = httpx.get(f"{API.replace('/api', '')}/api/version", timeout=30)
    out["api_version"] = ver.json() if ver.status_code == 200 else {"status": ver.status_code}
    try:
        import subprocess

        origin = subprocess.check_output(
            ["git", "rev-parse", "--short", "origin/main"],
            cwd=str(ROOT.parent),
            text=True,
        ).strip()
        out["origin_main_short"] = origin
        out["origin_matches_expected"] = origin.startswith(EXPECTED_COMMIT[:7]) or origin == EXPECTED_COMMIT
    except Exception as exc:
        out["origin_main_short"] = None
        out["origin_git_error"] = str(exc)[:200]

    return out


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _visible(page, selector: str, timeout_ms: int = 500) -> bool:
    try:
        loc = page.locator(f'[data-testid="{selector}"]')
        if loc.count() == 0:
            return False
        loc.first.wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False


def _full_page_loading_only(page) -> bool:
    """True when route shows only legacy full-page loading panel (no page root)."""
    loading_ids = [
        "command-center-loading",
        "documents-loading",
        "properties-loading",
        "requirements-loading",
        "client-dashboard-loading",
    ]
    for lid in loading_ids:
        loc = page.locator(f'[data-testid="{lid}"]')
        if loc.count() and loc.first.is_visible():
            h1 = page.locator("h1")
            if h1.count() == 0 or not h1.first.is_visible():
                return True
    # Centered spinner without shell title
    if page.locator('[data-testid="portal-section-skeleton"]').count() == 0:
        spin = page.locator("text=Loading dashboard").or_(page.locator("text=Loading command center"))
        if spin.count() and spin.first.is_visible():
            return True
    return False


def measure_surface(page, name: str, path: str, root_testid: str, skeleton_ids: list[str], stale_banner: str, *, warm: bool) -> dict[str, Any]:
    t0 = time.perf_counter()
    page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=180_000)
    t_dom = _ms(t0)

    t_shell = None
    t_primary = None
    t_stale = None
    deadline = time.perf_counter() + 120
    full_page_blocking_ms = None

    while time.perf_counter() < deadline:
        elapsed = _ms(t0)
        if t_shell is None:
            if _visible(page, root_testid, 300) or page.locator("h1").count() > 0:
                t_shell = elapsed
            elif any(_visible(page, s, 200) for s in skeleton_ids):
                t_shell = elapsed
            elif page.locator("h1").count() and page.locator("h1").first.is_visible():
                t_shell = elapsed

        if t_primary is None and _visible(page, root_testid, 300):
            # Heuristic: root visible and not only skeleton
            if page.locator('[data-testid="portal-section-skeleton"]').count() == 0 or elapsed > 3000:
                t_primary = elapsed

        if t_stale is None and _visible(page, stale_banner, 200):
            t_stale = elapsed

        if _full_page_loading_only(page):
            if full_page_blocking_ms is None:
                full_page_blocking_ms = elapsed
        else:
            if t_primary is not None:
                break

        if t_primary and elapsed > t_primary + 2000:
            break
        page.wait_for_timeout(250)

    spinner_end = _ms(t0)
    rent_loading = page.locator('[data-testid="rent-loading"]')
    rent_tab_spinner_only = name.startswith("P7") and rent_loading.count() and rent_loading.first.is_visible()

    return {
        "surface": name,
        "path": path,
        "warm": warm,
        "dom_content_loaded_ms": t_dom,
        "shell_visible_ms": t_shell,
        "primary_content_ms": t_primary,
        "stale_refresh_banner_ms": t_stale,
        "observation_window_ms": spinner_end,
        "full_page_spinner_only_detected": full_page_blocking_ms is not None and t_shell is None,
        "full_page_blocking_ms": full_page_blocking_ms,
        "tab_body_spinner_only": rent_tab_spinner_only,
        "stale_banner_seen": t_stale is not None,
        "progressive_shell": t_shell is not None and (t_shell < (t_primary or 999999)),
    }


def probe_stale_refresh_disclosure(page) -> dict[str, Any]:
    """Force expired in-session cache + slow refresh so stale-while-refresh banner must show."""
    banner_testid = "portal-stale-refresh-banner"
    refresh_delay_ms = 3000
    expiry_wait_ms = OPERATIONAL_CACHE_STALE_MS + 1000

    page.goto(f"{FRONTEND}/properties", wait_until="domcontentloaded", timeout=180_000)
    page.wait_for_selector('[data-testid="properties-page"]', timeout=180_000)

    page.goto(f"{FRONTEND}/dashboard", wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(expiry_wait_ms)

    def delayed_properties(route):
        time.sleep(refresh_delay_ms / 1000)
        route.continue_()

    page.route("**/client/properties**", delayed_properties)
    t0 = time.perf_counter()
    page.goto(f"{FRONTEND}/properties", wait_until="domcontentloaded", timeout=180_000)

    seen_at = None
    text = None
    for _ in range(100):
        loc = page.locator(f'[data-testid="{banner_testid}"]')
        if loc.count() and loc.first.is_visible():
            seen_at = int((time.perf_counter() - t0) * 1000)
            text = (loc.first.inner_text() or "").strip()
            break
        page.wait_for_timeout(50)

    try:
        page.unroute("**/client/properties**", delayed_properties)
    except Exception:
        pass

    return {
        "stale_banner_seen": seen_at is not None,
        "stale_banner_ms": seen_at,
        "stale_banner_text": text,
        "cache_expiry_wait_ms": expiry_wait_ms,
        "refresh_delay_ms": refresh_delay_ms,
        "charter_gate": "stale_refresh_disclosed_in_browser",
    }


def run_browser() -> dict[str, Any]:
    out: dict[str, Any] = {"attempted": False}
    if sync_playwright is None:
        out["error"] = "playwright not installed"
        return out

    pw = PW_FILE.read_text(encoding="utf-8").strip()
    login = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
    if login.status_code != 200:
        out["login_status"] = login.status_code
        return out

    body = login.json()
    token, user = body["access_token"], body["user"]
    out["attempted"] = True
    out["login_status"] = 200

    cold: list[dict] = []
    warm: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        page.goto(f"{FRONTEND}/login/client", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )

        for name, path, root, skel, banner in SURFACES:
            cold.append(measure_surface(page, name, path, root, skel, banner, warm=False))

        # Warm revisit: requirements -> documents -> requirements (cache)
        warm.append(measure_surface(page, "P5_Requirements_revisit", "/requirements", "requirements-page", ["portal-section-skeleton"], banner, warm=True))
        warm.append(measure_surface(page, "P6_Documents_revisit", "/documents", "documents-page", ["portal-section-skeleton"], banner, warm=True))
        warm.append(measure_surface(page, "P4_Properties_revisit", "/properties", "properties-page", ["portal-section-skeleton"], banner, warm=True))

        out["stale_refresh_disclosure_probe"] = probe_stale_refresh_disclosure(page)

        # Truth: error visibility probe — force bad token should not show fake calm on dashboard
        page.evaluate("() => localStorage.removeItem('auth_token')")
        err_t0 = time.perf_counter()
        page.goto(f"{FRONTEND}/dashboard", wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3000)
        out["auth_error_surface"] = {
            "login_redirect_or_error_ms": _ms(err_t0),
            "url": page.url,
            "shows_login": "/login" in page.url,
        }

        browser.close()

    out["cold_navigation"] = cold
    out["warm_navigation"] = warm
    return out


def classify(deploy: dict, browser: dict) -> dict[str, Any]:
    deploy_ok = deploy.get("deploy_ready") is True
    cold = browser.get("cold_navigation") or []
    if not cold:
        return {"classification": "BLOCKED", "verified_operationally": False, "reason": "no_browser_timings"}

    improvements = 0
    regressions = 0
    for row in cold:
        if row.get("progressive_shell"):
            improvements += 1
        if row.get("full_page_spinner_only_detected"):
            regressions += 1
        # P4 should be fast shell
        if row["surface"] == "P4_Properties" and (row.get("primary_content_ms") or 99999) < 15000:
            improvements += 1

    warm = browser.get("warm_navigation") or []
    stale_probe = browser.get("stale_refresh_disclosure_probe") or {}

    # Charter gate: stale banner must be observed — never inferred from fast warm revisit alone.
    stale_refresh_disclosed_in_browser = (
        any(r.get("stale_banner_seen") for r in warm)
        or any(r.get("stale_banner_seen") for r in cold)
        or stale_probe.get("stale_banner_seen") is True
    )

    warm_revisit_fast = any(
        (r.get("primary_content_ms") or 99999) < 5000
        for r in warm
        if "revisit" in r.get("surface", "")
    )

    unacceptable_backend = any(
        (r.get("primary_content_ms") or 0) > 60000
        for r in cold
        if r["surface"] in ("P1_Today", "P2_CommandCentre")
    )

    verified = (
        deploy_ok
        and improvements >= 4
        and regressions == 0
        and browser.get("login_status") == 200
    )
    if unacceptable_backend and verified:
        classification = "PARTIAL"
        reason = "progressive UX verified but backend latency remains unacceptable on Today/Command Centre"
    elif verified and stale_refresh_disclosed_in_browser:
        classification = "VERIFIED_OPERATIONALLY"
        reason = (
            "deploy markers present; progressive shell verified; "
            "stale-while-refresh banner disclosed in browser"
        )
    elif verified:
        classification = "PARTIAL"
        reason = (
            "progressive loading verified; stale-refresh banner not observed in browser "
            "(fast warm revisit alone is insufficient for operational verification)"
        )
    elif deploy_ok and improvements >= 2:
        classification = "PARTIAL"
        reason = "deploy present with partial progressive improvement"
    else:
        classification = "BLOCKED" if not deploy_ok else "PARTIAL"
        reason = "deploy or browser thresholds not met"

    return {
        "classification": classification,
        "verified_operationally": classification == "VERIFIED_OPERATIONALLY",
        "reason": reason,
        "improvement_signals": improvements,
        "regression_signals": regressions,
        "stale_refresh_disclosed_in_browser": stale_refresh_disclosed_in_browser,
        "warm_revisit_fast": warm_revisit_fast,
        "unacceptable_backend_latency": unacceptable_backend,
    }


def main() -> int:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    deploy = verify_deploy()
    browser = run_browser()
    classification = classify(deploy, browser)

    (BUNDLE / "deployment_verification.json").write_text(json.dumps(deploy, indent=2), encoding="utf-8")

    timings = {
        "verified_at_utc": utc_now(),
        "expected_commit": EXPECTED_COMMIT,
        "cold_navigation": browser.get("cold_navigation", []),
        "warm_navigation": browser.get("warm_navigation", []),
        "auth_error_surface": browser.get("auth_error_surface"),
        "stale_refresh_disclosure_probe": browser.get("stale_refresh_disclosure_probe"),
        "login_status": browser.get("login_status"),
        "browser_attempted": browser.get("attempted"),
    }
    (BUNDLE / "browser_navigation_timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")

    cls_path = BUNDLE / "classifications.json"
    cls_existing = json.loads(cls_path.read_text(encoding="utf-8")) if cls_path.exists() else {}
    cls_existing.update(classification)
    cls_existing["post_deploy_verified_at_utc"] = utc_now()
    cls_path.write_text(json.dumps(cls_existing, indent=2), encoding="utf-8")

    print(json.dumps({"deploy": deploy, "classification": classification, "cold_sample": (browser.get("cold_navigation") or [])[:2]}, indent=2))
    return 0 if classification.get("verified_operationally") else 1


if __name__ == "__main__":
    raise SystemExit(main())
