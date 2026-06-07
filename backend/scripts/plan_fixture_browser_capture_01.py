#!/usr/bin/env python3
"""Browser capture helper for PLAN-BASED-BUSINESS-OUTCOME-FIXTURE-CLOSEOUT-01."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/plan_based_business_outcome_runtime_audit_01"
SHOT = OUT / "closeout_screenshots"
API = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
if not API.endswith("/api"):
    API = f"{API}/api"
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerityenterprise.co.uk").rstrip("/")

TARGETS = [
    ("solo_all_ref", "10b2ddba-e952-4484-91d1-a8f0299d0824", "Sophie Walker — Solo all-satisfied reference"),
    ("solo_partial", "616258a5-51a6-4def-aa00-baa1598b2557", "David Harrison — Solo partial"),
    ("portfolio_partial", "6bcc43c0-16f4-46a5-adf4-26693a0919d0", "David Miller — Portfolio partial mixed"),
    ("pro_partial", "6fd5ac4c-3fd4-4112-ade7-156977deb49f", "Nancy — Professional partial mixed"),
]


def _pw() -> str:
    p = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
    return p.read_text(encoding="utf-8").strip()


def _login() -> tuple[str, str]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = _pw()
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    t = r.json()["access_token"]
    su = httpx.post(f"{API}/auth/step-up/verify", headers={"Authorization": f"Bearer {t}"}, json={"password": pw}, timeout=120)
    step = su.json().get("step_up_token", "") if su.status_code == 200 else ""
    return t, step


def _impersonate(admin_t: str, step: str, client_id: str) -> str:
    headers = {"Authorization": f"Bearer {admin_t}"}
    if step:
        headers["X-Step-Up-Token"] = step
    r = httpx.post(
        f"{API}/admin/clients/{client_id}/impersonation/start",
        headers=headers,
        params={"ttl_minutes": 15},
        json={"reason": "PLAN-FIXTURE-CLOSEOUT browser capture batch"},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> None:
    SHOT.mkdir(parents=True, exist_ok=True)
    captures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for slug, cid, label in TARGETS:
            admin_t, step = _login()
            token = _impersonate(admin_t, step, cid)
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            user_blob = json.dumps({"client_id": cid, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
            ctx.add_init_script(
                f"localStorage.setItem('auth_token', {json.dumps(token)});"
                f"localStorage.setItem('user', {json.dumps(user_blob)});"
            )
            page = ctx.new_page()
            entry = {"slug": slug, "client_id": cid, "label": label, "pages": []}
            try:
                for pid, route, shot in [
                    ("dashboard", "/dashboard", f"{slug}_dashboard.png"),
                    ("today", "/today", f"{slug}_today.png"),
                    ("requirements", "/requirements", f"{slug}_requirements.png"),
                    ("properties", "/properties", f"{slug}_properties.png"),
                    ("compliance_score", "/compliance-score", f"{slug}_compliance_score.png"),
                    ("reports", "/reports", f"{slug}_reports.png"),
                    ("billing", "/billing", f"{slug}_billing.png"),
                ]:
                    page.goto(f"{FRONTEND}{route}", wait_until="domcontentloaded", timeout=120_000)
                    page.wait_for_timeout(2500)
                    page.screenshot(path=str(SHOT / shot))
                    entry["pages"].append({"page": pid, "screenshot": shot})
                entry["pass"] = len(entry["pages"]) >= 6
            except Exception as exc:
                entry["pass"] = False
                entry["error"] = str(exc)[:200]
            finally:
                page.close()
                ctx.close()
            captures.append(entry)
            time.sleep(5)
        browser.close()
    out = {
        "programme": "PLAN-BASED-BUSINESS-OUTCOME-FIXTURE-CLOSEOUT-01",
        "captures": captures,
        "pass": all(c.get("pass") for c in captures),
        "screenshot_dir": str(SHOT.relative_to(ROOT)),
    }
    (OUT / "plan_browser_closeout_runtime.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"browser_pass": out["pass"], "count": len(captures)}, indent=2))


if __name__ == "__main__":
    main()
