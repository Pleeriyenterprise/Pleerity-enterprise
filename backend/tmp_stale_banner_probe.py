import json
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

FRONTEND = "https://pleerityenterprise.co.uk"
API = "https://pleerity-enterprise.onrender.com/api"
pw = Path("docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt").read_text().strip()
body = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": pw}, timeout=120).json()

with sync_playwright() as p:
    page = p.chromium.launch(headless=True).new_page()
    page.goto(f"{FRONTEND}/login/client", timeout=120_000)
    page.evaluate(
        """([t,u]) => {
          localStorage.setItem('auth_token', t);
          localStorage.setItem('user', JSON.stringify(u));
        }""",
        [body["access_token"], body["user"]],
    )
    page.goto(f"{FRONTEND}/properties", timeout=180_000, wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="properties-page"]', timeout=180_000)
    page.goto(f"{FRONTEND}/dashboard", timeout=60_000, wait_until="domcontentloaded")
    page.wait_for_timeout(46_000)
    t0 = time.perf_counter()
    page.goto(f"{FRONTEND}/properties", timeout=180_000, wait_until="domcontentloaded")
    out = {"stale_banner_ms": None, "stale_text": None}
    for _ in range(50):
        loc = page.locator('[data-testid="portal-stale-refresh-banner"]')
        if loc.count() and loc.first.is_visible():
            out["stale_banner_ms"] = int((time.perf_counter() - t0) * 1000)
            out["stale_text"] = loc.first.inner_text()
            break
        page.wait_for_timeout(100)
    out["shell_h1_ms"] = int((time.perf_counter() - t0) * 1000)
    out["has_properties_page"] = page.locator('[data-testid="properties-page"]').count() > 0
    print(json.dumps(out, indent=2))
