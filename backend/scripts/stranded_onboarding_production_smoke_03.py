#!/usr/bin/env python3
"""CHECKOUT-SUCCESS-ROUTE-FIX-03 — production smoke (no billing mutations)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "audit" / "checkout_success_03"
SHOTS = OUT_DIR / "screenshots"
OUT = OUT_DIR / "production_smoke_03.json"
FE = "https://pleerityenterprise.co.uk"
API = "https://api.pleerityenterprise.co.uk/api"
UA = {"User-Agent": "so03-production-smoke"}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _launch_browser(playwright):
    last = None
    for kwargs in (
        {"headless": True, "channel": "chrome"},
        {"headless": True, "channel": "msedge"},
        {"headless": True},
    ):
        try:
            return playwright.chromium.launch(**kwargs)
        except Exception as exc:
            last = exc
    raise RuntimeError(f"chromium launch failed: {last}")


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    results = {
        "programme": "CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03",
        "started_at": _utc(),
        "frontend": FE,
        "api": API,
    }
    ver = httpx.get(f"{API}/version", timeout=60, headers=UA)
    results["api_version"] = {"status": ver.status_code, "body": ver.json()}
    health = httpx.get(f"{API}/health", timeout=60, headers=UA)
    results["api_health"] = {"status": health.status_code, "body": health.json()}

    public = {}
    for path in ("/", "/login", "/login/admin", "/checkout/success"):
        r = httpx.get(FE + path, timeout=60, follow_redirects=True, headers=UA)
        public[path] = {"status": r.status_code, "url": str(r.url)[:180]}
    results["public_pages"] = public

    home = httpx.get(FE + "/", timeout=60, follow_redirects=True, headers=UA)
    scripts = re.findall(r'src="(/static/js/main[^"]+\.js)"', home.text)
    results["bundle_path"] = scripts[0] if scripts else None
    bundle_text = ""
    if scripts:
        bundle_text = httpx.get(FE + scripts[0], timeout=120, headers=UA).text
        results["bundle"] = {
            "path": scripts[0],
            "len": len(bundle_text),
            "checkout-success-page": "checkout-success-page" in bundle_text,
            "checkout-success-missing-session": "checkout-success-missing-session" in bundle_text,
            "release_and_restart": "release_and_restart" in bundle_text,
            "preserve_existing": "preserve_existing" in bundle_text,
            "apply_selected": "apply_selected" in bundle_text,
            "allow_promotion_codes": "allow_promotion_codes" in bundle_text,
            "staging_api_onrender": "pleerity-enterprise.onrender.com" in bundle_text,
            "production_api_host": "api.pleerityenterprise.co.uk" in bundle_text,
            "pk_live_present": bool(re.search(r"pk_live_[A-Za-z0-9]+", bundle_text)),
            "pk_test_present": bool(re.search(r"pk_test_[A-Za-z0-9]+", bundle_text)),
        }

    from playwright.sync_api import sync_playwright

    routes = {}
    with sync_playwright() as p:
        browser = _launch_browser(p)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        for name, path in (
            ("missing", "/checkout/success"),
            ("session", "/checkout/success?session_id=cs_test_safe_reference_0001"),
            ("malformed", "/checkout/success?session_id=not-a-session"),
        ):
            console_errors.clear()
            page.goto(FE + path, wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(1500)
            body = page.inner_text("body")[:2000]
            html_has_page = page.locator("[data-testid='checkout-success-page']").count() > 0
            hero = page.locator("[data-testid='hero-cta-primary']").count()
            testids = page.locator("[data-testid]").evaluate_all(
                "els => els.map(e => e.getAttribute('data-testid'))"
            )
            shot = f"prod_route_{name}.png"
            page.screenshot(path=str(SHOTS / shot), full_page=True)
            routes[name] = {
                "final_url": page.url,
                "has_success_page": html_has_page,
                "hero_cta_count": hero,
                "testids": testids,
                "text_preview": body[:900],
                "screenshot": shot,
                "console_error_count": len(console_errors),
                "pass": html_has_page and hero == 0 and "/checkout/success" in page.url,
            }
        browser.close()
    results["direct_routes"] = routes
    results["route_ok"] = all(v.get("pass") for v in routes.values())
    results["finished_at"] = _utc()
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"route_ok": results["route_ok"], "bundle": results.get("bundle"), "health": results["api_health"]["body"].get("status")}, indent=2))
    return 0 if results["route_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
