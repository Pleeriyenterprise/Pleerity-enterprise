#!/usr/bin/env python3
"""Browser verification for PRELAUNCH-PERFORMANCE-BACKEND-REMEDIATION-02 post-deploy."""
from __future__ import annotations

import json
import os
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
OUT = ROOT / "docs" / "audit" / "performance_backend_remediation_02"
FRONTEND = "https://pleerityenterprise.co.uk"
API = "https://pleerity-enterprise.onrender.com/api"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
FALLBACK_PW = "OpsVerify01!StagingWalk"

SURFACES = [
    ("P1_Today", "/today", "client-tasks-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P2_CommandCentre", "/command-center", "command-center-root", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P3_Dashboard", "/dashboard", "client-dashboard", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P4_Properties", "/properties", "properties-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P5_Requirements", "/requirements", "requirements-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
    ("P6_Documents", "/documents", "documents-page", ["portal-section-skeleton"], "portal-stale-refresh-banner"),
]

PROPERTY_DETAIL_PATH = os.environ.get("OPS_PROPERTY_DETAIL_PATH", "")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def measure_surface(page, name: str, path: str, root_testid: str, skeleton_ids: list, stale_banner: str, *, warm: bool) -> dict[str, Any]:
    t0 = time.perf_counter()
    page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=180_000)
    t_dom = _ms(t0)
    t_shell = None
    t_primary = None
    t_stale = None
    deadline = time.perf_counter() + 120
    while time.perf_counter() < deadline:
        elapsed = _ms(t0)
        if t_shell is None:
            if _visible(page, root_testid, 300) or (page.locator("h1").count() > 0 and page.locator("h1").first.is_visible()):
                t_shell = elapsed
            elif any(_visible(page, s, 200) for s in skeleton_ids):
                t_shell = elapsed
        if t_primary is None and _visible(page, root_testid, 300):
            if page.locator('[data-testid="portal-section-skeleton"]').count() == 0 or elapsed > 3000:
                t_primary = elapsed
        if t_stale is None and _visible(page, stale_banner, 200):
            t_stale = elapsed
        if t_primary and elapsed > t_primary + 2000:
            break
        page.wait_for_timeout(250)
    return {
        "surface": name,
        "path": path,
        "warm": warm,
        "dom_content_loaded_ms": t_dom,
        "shell_visible_ms": t_shell,
        "primary_content_ms": t_primary,
        "stale_refresh_banner_ms": t_stale,
        "observation_window_ms": _ms(t0),
        "stale_banner_seen": t_stale is not None,
        "progressive_shell": t_shell is not None and (t_shell < (t_primary or 999999)),
    }


def run_browser_timings() -> dict[str, Any]:
    out: dict[str, Any] = {"verified_at_utc": utc_now(), "attempted": False}
    if sync_playwright is None:
        out["error"] = "playwright not installed"
        return out
    pw = FALLBACK_PW
    if PW_FILE.is_file():
        pw = PW_FILE.read_text(encoding="utf-8").strip() or pw
    login = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
    if login.status_code != 200:
        out["login_status"] = login.status_code
        out["login_detail"] = login.text[:200]
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
        warm.append(
            measure_surface(
                page,
                "P5_Requirements_revisit",
                "/requirements",
                "requirements-page",
                ["portal-section-skeleton"],
                "portal-stale-refresh-banner",
                warm=True,
            )
        )
        # Property detail: first property from properties list link if present
        page.goto(f"{FRONTEND}/properties", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        link = page.locator('[data-testid="properties-page"] a[href*="/properties/"]').first
        if link.count():
            href = link.get_attribute("href") or ""
            if href:
                cold.append(
                    measure_surface(
                        page,
                        "P_property_detail",
                        href if href.startswith("/") else f"/properties/{href}",
                        "property-detail-page",
                        ["portal-section-skeleton"],
                        "portal-stale-refresh-banner",
                        warm=False,
                    )
                )
        browser.close()
    out["cold_navigation"] = cold
    out["warm_navigation"] = warm
    out["surfaces"] = cold + warm
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    result = run_browser_timings()
    print(json.dumps(result, indent=2))
