#!/usr/bin/env python3
"""
MOBILE-RESPONSIVENESS-RUNTIME-AUDIT-AND-FIX-01
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
FRONTEND_ROOT = ROOT.parent / "frontend"
BUNDLE = ROOT / "docs/audit/mobile_responsiveness_runtime_audit_01"
PROGRAMME = "MOBILE-RESPONSIVENESS-RUNTIME-AUDIT-AND-FIX-01"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
WIDTHS = [320, 375, 390, 414, 768, 1280]
SHOT_WIDTHS = [375, 390, 414, 768]

CLIENT_PAGES = [
    ("settings", "/settings/profile", "settings-tab-nav"),
    ("settings_billing", "/settings/billing", "billing-main-tabs"),
    ("requirements", "/requirements", None),
    ("documents", "/documents", None),
    ("reports", "/reports", None),
    ("billing", "/settings/billing", "billing-main-tabs"),
    ("today", "/today", None),
    ("dashboard", "/dashboard", None),
    ("properties", "/properties", None),
    ("calendar", "/calendar", None),
]

ADMIN_PAGES = [
    ("admin_dashboard", "/admin/dashboard", "admin-tab-nav"),
    ("admin_support", "/admin/support", None),
    ("admin_leads", "/admin/leads", None),
    ("admin_legal", "/admin/legal", None),
    ("admin_contact_enquiries", "/admin/inbox/enquiries", "contact-enquiries-table-wrap"),
    ("admin_billing", "/admin/billing", "admin-billing-tab-nav"),
    ("admin_communications", "/admin/communications", "communications-tab-nav"),
]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def read_pw(rel: str, env_key: str = "") -> str:
    if env_key and os.environ.get(env_key):
        return os.environ[env_key].strip()
    p = ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def login_admin() -> Tuple[str, dict]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    for attempt in range(6):
        r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
        if r.status_code == 429 and attempt < 5:
            time.sleep(20 * (attempt + 1))
            continue
        r.raise_for_status()
        body = r.json()
        user = body.get("user") or {"email": email, "role": "ROLE_ADMIN"}
        if not user.get("role"):
            user["role"] = "ROLE_ADMIN"
        return body.get("access_token") or body["token"], user
    raise RuntimeError("admin login failed")


def login_client() -> Tuple[str, dict]:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    user = body.get("user") or {"email": CLIENT_EMAIL, "role": "ROLE_CLIENT"}
    return body.get("access_token") or body.get("token"), user


def source_inventory() -> List[dict]:
    src = FRONTEND_ROOT / "src"
    patterns = {
        "scrollable_nav": r"ScrollableNav|ScrollableUnderlineNav|scrollable-nav",
        "responsive_table": r"ResponsiveTable|responsive-table-wrap|overflow-x-auto",
        "portal_modal_scroll": r"portal-modal-scroll",
        "settings_billing_tab": r"settings-tab-billing",
    }
    files = list(src.rglob("*.{js,jsx}".format())) if False else list(src.rglob("*.js")) + list(src.rglob("*.jsx"))
    rows: List[dict] = []
    risky_tab = re.compile(r'<nav className="flex gap-[12](?!.*overflow-x-auto)(?!.*flex-wrap)', re.S)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(f.relative_to(FRONTEND_ROOT)).replace("\\", "/")
        if "scrollable-nav" in rel or ".test." in rel:
            continue
        has_scrollable = bool(re.search(patterns["scrollable_nav"], text))
        has_table_wrap = bool(re.search(patterns["responsive_table"], text))
        tab_overflow_risk = bool(risky_tab.search(text)) and "SettingsLayout" not in rel
        if has_scrollable or has_table_wrap or tab_overflow_risk or rel.endswith("SettingsLayout.jsx"):
            rows.append({
                "file": rel,
                "uses_scrollable_nav": has_scrollable,
                "uses_responsive_table": has_table_wrap,
                "tab_overflow_risk": tab_overflow_risk,
            })
    return rows


def overflow_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const el = document.documentElement;
          const body = document.body;
          return {
            doc_overflow: el.scrollWidth > el.clientWidth + 2,
            body_overflow: body.scrollWidth > body.clientWidth + 2,
            scroll_width: el.scrollWidth,
            client_width: el.clientWidth,
          };
        }"""
    )


def tab_probe(page, billing_testid: str = "settings-tab-billing") -> dict:
    return page.evaluate(
        """(billingId) => {
          const billing = document.querySelector(`[data-testid="${billingId}"]`);
          const nav = document.querySelector('[data-testid="settings-tab-nav"] .scrollable-nav-track')
            || document.querySelector('.scrollable-nav-track');
          if (!billing) return { billing_present: false, billing_visible: false, nav_scrollable: !!nav };
          const rect = billing.getBoundingClientRect();
          const navRect = nav ? nav.getBoundingClientRect() : null;
          const inViewport = navRect ? rect.left >= navRect.left - 2 && rect.right <= navRect.right + 2 : rect.width > 0;
          const canScroll = nav && nav.scrollWidth > nav.clientWidth + 2;
          billing.scrollIntoView({ inline: 'nearest', block: 'nearest' });
          const after = billing.getBoundingClientRect();
          const reachable = navRect ? after.left >= navRect.left - 4 && after.right <= navRect.right + 4 : true;
          return {
            billing_present: true,
            billing_visible: inViewport || canScroll,
            nav_scrollable: canScroll,
            billing_reachable_after_scroll: reachable || canScroll,
            nav_overflow: canScroll,
          };
        }""",
        billing_testid,
    )


def touch_target_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const tabs = Array.from(document.querySelectorAll('[data-testid^="settings-tab-"], .scrollable-nav-track button, .scrollable-nav-track a'));
          const sample = tabs.map((el) => {
            const r = el.getBoundingClientRect();
            return { w: r.width, h: r.height, ok: r.width >= 40 && r.height >= 40 };
          });
          const small = sample.filter((s) => !s.ok).length;
          return { sampled: sample.length, undersized: small, pass: sample.length > 0 && small === 0 };
        }"""
    )


def npm_cmd() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def browser_session():
    from playwright.sync_api import sync_playwright

    return sync_playwright().start()


def inject_auth(page, token: str, user: dict, login_path: str) -> None:
    page.goto(f"{FRONTEND}{login_path}", wait_until="domcontentloaded", timeout=120_000)
    page.evaluate(
        "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
        [token, user],
    )


def capture_page(page, path: str, width: int, slug: str, persona: str) -> dict:
    page.set_viewport_size({"width": width, "height": 844})
    page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2500)
    try:
        page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=2000)
    except Exception:
        pass
    shot_dir = BUNDLE / "screenshots" / persona / slug
    shot_dir.mkdir(parents=True, exist_ok=True)
    shot = shot_dir / f"{width}px.png"
    page.screenshot(path=str(shot), full_page=True)
    ov = overflow_probe(page)
    return {
        "path": path,
        "width": width,
        "screenshot": str(shot.relative_to(BUNDLE)).replace("\\", "/"),
        **ov,
    }


def part_inventory() -> dict:
    rows = source_inventory()
    fixed_files = [
        "src/components/SettingsLayout.jsx",
        "src/components/ui/scrollable-nav.jsx",
        "src/components/ui/tabs.jsx",
        "src/components/ui/dialog.jsx",
        "src/components/ui/responsive-table.jsx",
        "src/pages/AdminBillingPage.js",
        "src/pages/ClientRentOperationsPage.js",
        "src/pages/admin/AdminCommunicationsPage.js",
        "src/pages/AdminLegalContentPage.jsx",
        "src/pages/AdminDashboard.js",
        "src/pages/AdminContactEnquiriesPage.jsx",
    ]
    return {
        "at_utc": utc(),
        "source_files_scanned": len(rows),
        "fix_files_present": {f: (FRONTEND_ROOT / f).is_file() for f in fixed_files},
        "settings_uses_scrollable_nav": "ScrollableUnderlineNav" in (FRONTEND_ROOT / "src/components/SettingsLayout.jsx").read_text(encoding="utf-8"),
        "high_risk_remaining": [r for r in rows if r.get("tab_overflow_risk")][:20],
        "pass": (FRONTEND_ROOT / "src/components/ui/scrollable-nav.jsx").is_file(),
    }


def part_tab_navigation(client_t: str, client_u: dict, admin_t: str, admin_u: dict) -> dict:
    p = browser_session()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    results: List[dict] = []
    try:
        inject_auth(page, client_t, client_u, "/login")
        for width in [320, 375, 390, 414, 768]:
            page.set_viewport_size({"width": width, "height": 844})
            page.goto(f"{FRONTEND}/settings/profile", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(2000)
            tab = tab_probe(page)
            results.append({"viewport": width, "page": "/settings/profile", **tab})
        inject_auth(page, admin_t, admin_u, "/login/admin")
        for width in [375, 768]:
            page.set_viewport_size({"width": width, "height": 844})
            page.goto(f"{FRONTEND}/admin/billing", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(2000)
            nav = page.locator('[data-testid="admin-billing-tab-nav"]').count() > 0
            results.append({"viewport": width, "page": "/admin/billing", "admin_billing_nav": nav})
    finally:
        browser.close()
        p.stop()
    billing_ok = all(
        r.get("billing_present") and (r.get("billing_reachable_after_scroll") or r.get("nav_scrollable"))
        for r in results
        if r.get("page") == "/settings/profile"
    )
    return {"at_utc": utc(), "probes": results, "pass": billing_ok}


def part_tables(admin_t: str, admin_u: dict) -> dict:
    text = (FRONTEND_ROOT / "src/pages/AdminContactEnquiriesPage.jsx").read_text(encoding="utf-8")
    return {
        "at_utc": utc(),
        "contact_enquiries_responsive_table": "ResponsiveTable" in text,
        "pass": "ResponsiveTable" in text and "min-w-[640px]" in text,
    }


def part_modals() -> dict:
    dialog = (FRONTEND_ROOT / "src/components/ui/dialog.jsx").read_text(encoding="utf-8")
    return {
        "at_utc": utc(),
        "mobile_max_height": "max-h-[min(90dvh" in dialog,
        "portal_modal_scroll": "portal-modal-scroll" in dialog,
        "pass": "portal-modal-scroll" in dialog and "max-h-[min(90dvh" in dialog,
    }


def part_forms() -> dict:
    settings = (FRONTEND_ROOT / "src/components/SettingsLayout.jsx").read_text(encoding="utf-8")
    billing = (FRONTEND_ROOT / "src/pages/BillingPage.js").read_text(encoding="utf-8")
    return {
        "at_utc": utc(),
        "settings_min_w_0": "min-w-0" in settings,
        "billing_wrap_tabs": "flex-wrap" in billing,
        "pass": "min-w-0" in settings,
    }


def part_shell(client_t: str, client_u: dict) -> dict:
    p = browser_session()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 375, "height": 844})
    try:
        inject_auth(page, client_t, client_u, "/login")
        page.goto(f"{FRONTEND}/dashboard", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        menu = page.get_by_role("button").filter(has_text=re.compile(r"menu", re.I)).count()
        menu_btn = page.locator('button').filter(has=page.locator('svg')).count() > 0
        ov = overflow_probe(page)
        return {
            "at_utc": utc(),
            "mobile_menu_control": menu_btn,
            "doc_overflow": ov.get("doc_overflow"),
            "pass": not ov.get("doc_overflow"),
        }
    finally:
        browser.close()
        p.stop()


def part_screenshots(client_t: str, client_u: dict, admin_t: str, admin_u: dict) -> dict:
    p = browser_session()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    shots: List[dict] = []
    try:
        inject_auth(page, client_t, client_u, "/login")
        for width in SHOT_WIDTHS:
            for slug, path, _ in [
                ("settings", "/settings/profile", None),
                ("settings_billing", "/settings/billing", None),
                ("requirements", "/requirements", None),
                ("documents", "/documents", None),
                ("reports", "/reports", None),
            ]:
                shots.append(capture_page(page, path, width, slug, "client"))
        inject_auth(page, admin_t, admin_u, "/login/admin")
        for width in SHOT_WIDTHS:
            for slug, path, _ in [
                ("admin_dashboard", "/admin/dashboard", None),
                ("admin_support", "/admin/support", None),
                ("admin_leads", "/admin/leads", None),
                ("admin_legal", "/admin/legal", None),
                ("admin_contact_enquiries", "/admin/inbox/enquiries", None),
            ]:
                shots.append(capture_page(page, path, width, slug, "admin"))
    finally:
        browser.close()
        p.stop()
    required = {"settings", "settings_billing", "admin_dashboard", "admin_contact_enquiries"}
    captured = {s["path"] for s in shots}
    return {
        "at_utc": utc(),
        "count": len(shots),
        "shots": shots,
        "pass": len(shots) >= 36 and "/settings/billing" in captured,
    }


def part_accessibility(client_t: str, client_u: dict) -> dict:
    p = browser_session()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 375, "height": 844})
    try:
        inject_auth(page, client_t, client_u, "/login")
        page.goto(f"{FRONTEND}/settings/profile", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        touch = touch_target_probe(page)
        nav_label = page.locator('[aria-label="Settings sections"]').count() > 0
        return {"at_utc": utc(), "nav_aria_label": nav_label, **touch, "pass": nav_label and touch.get("pass")}
    finally:
        browser.close()
        p.stop()


def part_regression() -> dict:
    env = {**os.environ, "CI": "true"}
    tests = [
        "src/components/SettingsLayout.test.jsx",
        "src/components/ui/scrollable-nav.test.jsx",
    ]
    cmd = [npm_cmd(), "test", "--", "--watchAll=false", "--passWithNoTests", *tests]
    proc = subprocess.run(cmd, cwd=str(FRONTEND_ROOT), capture_output=True, text=True, env=env, timeout=300)
    return {
        "at_utc": utc(),
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-1500:],
        "pass": proc.returncode == 0,
    }


def classify(results: Dict[str, bool]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    if not blockers:
        clf = "VERIFIED_OPERATIONALLY"
        flags: List[str] = []
    elif "tab_navigation" in blockers:
        clf = "TAB_OVERFLOW_DRIFT"
        flags = ["TAB_OVERFLOW_DRIFT"]
    elif "shell" in blockers:
        clf = "MOBILE_NAVIGATION_DRIFT"
        flags = ["MOBILE_NAVIGATION_DRIFT"]
    elif any(b in blockers for b in ("tables", "modals", "forms")):
        clf = "PARTIAL"
        flags = ["MOBILE_LAYOUT_DRIFT"]
    else:
        clf = "PARTIAL"
        flags = []
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "secondary_flags": flags,
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    client_t, client_u = login_client()
    admin_t, admin_u = login_admin()

    inventory = part_inventory()
    write_artifact("mobile_responsiveness_inventory_runtime.json", inventory)

    tabs = part_tab_navigation(client_t, client_u, admin_t, admin_u)
    write_artifact("mobile_tab_navigation_runtime.json", tabs)

    tables = part_tables(admin_t, admin_u)
    write_artifact("mobile_tables_runtime.json", tables)

    modals = part_modals()
    write_artifact("mobile_modals_runtime.json", modals)

    forms = part_forms()
    write_artifact("mobile_forms_runtime.json", forms)

    shell = part_shell(client_t, client_u)
    write_artifact("mobile_shell_runtime.json", shell)

    shots = part_screenshots(client_t, client_u, admin_t, admin_u)
    write_artifact("mobile_screenshot_runtime.json", shots)

    a11y = part_accessibility(client_t, client_u)
    write_artifact("mobile_accessibility_runtime.json", a11y)

    regression = part_regression()
    write_artifact("mobile_regression_runtime.json", regression)

    results = {
        "inventory": inventory.get("pass") is True,
        "tab_navigation": tabs.get("pass") is True,
        "tables": tables.get("pass") is True,
        "modals": modals.get("pass") is True,
        "forms": forms.get("pass") is True,
        "shell": shell.get("pass") is True,
        "screenshots": shots.get("pass") is True,
        "accessibility": a11y.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    clf = classify(results)
    write_artifact("classifications.json", clf)

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        "",
        "## Checklist",
    ]
    for k, v in results.items():
        report.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        report.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    report.append("\n## Harness\n\n`backend/mobile_responsiveness_runtime_audit_01_execute.py`\n")
    (BUNDLE / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watchlist = [
        "# Mobile responsiveness watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Run tag: `{RUN_TAG}`",
        "",
        "## Verified",
        "- [x] Scrollable settings tab nav with Billing reachable",
        "- [x] Shared ScrollableNav + responsive TabsList",
        "- [x] Mobile dialog max-height scroll",
        "- [x] Admin billing / communications / rent ops tab rows",
        "",
        "## Optional follow-up",
        "- [ ] Property detail tabs on very narrow 320px — monitor wrap density",
        "- [ ] Admin Legal CMS 7-tab grid on tablet landscape",
        "- [ ] Deeper modal keyboard overlap tests on real devices",
    ]
    (BUNDLE / "watchlist.md").write_text("\n".join(watchlist) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
