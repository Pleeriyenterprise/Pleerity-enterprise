#!/usr/bin/env python3
"""Browser + API verification for admin legal content preview."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/legal_content_management_publication_runtime_audit_01"
PROGRAMME = "LEGAL-CONTENT-ADMIN-PREVIEW-VERIFY-01"
SLUG = "6fd5ac4c_d35a58ae"
_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
TEST_SLUG = "careers"
DIRTY = "# Careers Preview Test\n\n**Bold line**\n\n<script>alert('strip')</script>\n\nVisible paragraph."


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def read_pw(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def login_admin() -> Tuple[str, dict]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt")
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body.get("access_token") or body["token"], body.get("user") or {}


def part_api_preview(token: str) -> dict:
    r = httpx.post(
        f"{API}/admin/legal-content/{TEST_SLUG}/preview",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": "Careers", "content": DIRTY},
        timeout=120,
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    clean = body.get("content") or ""
    return {
        "status": r.status_code,
        "sanitization_applied": body.get("sanitization_applied"),
        "script_stripped": "<script>" not in clean.lower(),
        "markdown_preserved": "**Bold line**" in clean,
        "content_length": len(clean.strip()),
        "pass": r.status_code == 200 and body.get("sanitization_applied") is True and "<script>" not in clean.lower() and "**Bold line**" in clean,
    }


def part_browser_preview(token: str, admin_user: dict) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}

    shot_dir = BUNDLE / "screenshots" / "admin_preview"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    out: Dict[str, Any] = {"pass": False, "checks": {}}
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/settings/legal", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(3000)

        preview_btn = page.get_by_role("button", name="Preview")
        live_link = page.get_by_role("link", name="View live page")
        out["checks"]["preview_button"] = preview_btn.count() > 0
        out["checks"]["live_page_link"] = live_link.count() > 0

        page.get_by_role("tab", name="Careers").click()
        page.wait_for_timeout(1500)

        textarea = page.locator("textarea").first
        textarea.fill(DIRTY)
        preview_btn.first.click()
        page.wait_for_timeout(4000)

        body = page.locator("body").inner_text()
        out["checks"]["preview_mode_copy"] = "same markdown renderer" in body.lower()
        out["checks"]["sanitization_warning"] = "unsafe html was removed" in body.lower()
        out["checks"]["bold_rendered"] = page.locator(".legal-content-markdown strong").count() > 0
        out["checks"]["script_not_rendered"] = page.locator(".legal-content-markdown script").count() == 0
        preview_text = page.locator(".legal-content-markdown").inner_text()
        out["checks"]["visible_paragraph"] = "Visible paragraph" in preview_text

        page.screenshot(path=str(shot_dir / "admin_preview_careers.png"))
        out["screenshot"] = "screenshots/admin_preview/admin_preview_careers.png"

        required = [
            "preview_button",
            "live_page_link",
            "preview_mode_copy",
            "sanitization_warning",
            "bold_rendered",
            "script_not_rendered",
            "visible_paragraph",
        ]
        out["pass"] = all(out["checks"].get(k) for k in required)
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        return out
    finally:
        browser.close()
        p.stop()


def classify(results: Dict[str, bool]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    clf = "VERIFIED_OPERATIONALLY" if not blockers else ("PARTIAL" if len(blockers) == 1 else "FAIL_OPERATIONAL")
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "prior_classification": "VERIFIED_OPERATIONALLY",
        "prior_programme": "LEGAL-CONTENT-ADMIN-HYDRATION-CLOSEOUT-01",
        "feature": "admin_legal_content_preview",
        "secondary_flags": ["ADMIN_PREVIEW_DRIFT"] if blockers else [],
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, RUN_TAG)
    token, admin_user = login_admin()
    api = part_api_preview(token)
    browser = part_browser_preview(token, admin_user)
    results = {"api_preview": api.get("pass") is True, "browser_preview": browser.get("pass") is True}
    payload = {"at_utc": utc(), "run_tag": RUN_TAG, "api": api, "browser": browser, "pass": all(results.values())}
    write_artifact("admin_preview_verify_runtime.json", payload)

    clf = classify(results)
    existing = BUNDLE / "classifications.json"
    merged = json.loads(existing.read_text(encoding="utf-8")) if existing.is_file() else {}
    merged["admin_preview_verify"] = clf
    merged["admin_preview_verified_at_utc"] = utc() if clf["classification"] == "VERIFIED_OPERATIONALLY" else None
    write_artifact("classifications.json", merged)

    report_lines = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        "",
        "## Checks",
        f"- API preview sanitisation: {'PASS' if results['api_preview'] else 'FAIL'}",
        f"- Browser preview UI: {'PASS' if results['browser_preview'] else 'FAIL'}",
        "",
        "Artifact: `admin_preview_verify_runtime.json`",
    ]
    (BUNDLE / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    watch = BUNDLE / "watchlist.md"
    if watch.is_file():
        text = watch.read_text(encoding="utf-8")
        if clf["classification"] == "VERIFIED_OPERATIONALLY" and "Admin legal preview" not in text:
            text += "\n## Admin preview\n- [x] Server-sanitised draft preview in admin legal editor\n- [x] Public markdown renderer in preview pane\n- [x] View live page link for published comparison\n"
            watch.write_text(text, encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
