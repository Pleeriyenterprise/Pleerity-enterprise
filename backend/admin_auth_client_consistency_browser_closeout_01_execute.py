#!/usr/bin/env python3
"""ADMIN-AUTH-CLIENT-CONSISTENCY-BROWSER-CLOSEOUT-01"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BUNDLE = ROOT / "docs/audit/admin_auth_client_consistency_hardening_01"
PROGRAMME = "ADMIN-AUTH-CLIENT-CONSISTENCY-BROWSER-CLOSEOUT-01"
HARDENING_COMMIT = "b0d7bd41"
SLUG = "6fd5ac4c_d35a58ae"

_raw_api = __import__("os").environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
API_ROOT = API[:-4] if API.endswith("/api") else _raw_api
FRONTEND = __import__("os").environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SHOT = BUNDLE / "screenshots" / "browser_closeout"
PRIOR_TEST_MARKERS = [
    "auth-hardening-",
    "newsletter-audit-",
    "newsletter-browser-",
]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def read_pw(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def login_admin() -> tuple[str, dict]:
    email = __import__("os").environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt")
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body["token"]
    user = body.get("user") or {"email": email, "role": "ROLE_ADMIN", "name": "Ops Verify Admin"}
    return token, user


def fetch_main_bundle() -> dict:
    html_r = httpx.get(FRONTEND, timeout=120, follow_redirects=True)
    health_status = 0
    for health_url in (f"{API_ROOT}/health", f"{API_ROOT}/api/health", f"{API}/health"):
        try:
            health_status = httpx.get(health_url, timeout=60).status_code
            if health_status == 200:
                break
        except Exception:
            continue

    bundles = re.findall(r'src="(/static/js/[^"]+\.js)"', html_r.text)
    main_match = re.search(r"/static/js/main\.([a-f0-9]+)\.js", html_r.text)
    main_hash = main_match.group(1) if main_match else None
    js_text = ""
    if main_hash:
        js_r = httpx.get(f"{FRONTEND}/static/js/main.{main_hash}.js", timeout=180)
        js_text = js_r.text if js_r.status_code == 200 else ""

    hardened_markers = {
        "listNewsletterSubscribers": "listNewsletterSubscribers" in js_text,
        "no_subscribers_yet_copy": "No subscribers yet" in js_text,
        "session_expired_message": "Session expired or not signed in" in js_text,
        "useAuthenticatedQuery_literal": "useAuthenticatedQuery" in js_text,
        "authStorage_literal": "getAuthToken" in js_text or "AUTH_TOKEN_KEY" in js_text,
    }
    legacy_drift = {
        "getItem_token": bool(re.search(r'getItem\(["\']token["\']\)', js_text)),
        "legacy_no_subscribers_only": "No subscribers" in js_text and "No subscribers yet" not in js_text,
    }
    # Minified prod bundles may drop hook/helper names; rely on API method + user-facing copy + no legacy token key.
    deployed = (
        hardened_markers["listNewsletterSubscribers"]
        and (hardened_markers["no_subscribers_yet_copy"] or hardened_markers["session_expired_message"])
        and not legacy_drift["getItem_token"]
        and not legacy_drift["legacy_no_subscribers_only"]
    )
    return {
        "at_utc": utc(),
        "frontend_url": FRONTEND,
        "hardening_commit_expected": HARDENING_COMMIT,
        "html_status": html_r.status_code,
        "api_health_status": health_status,
        "main_bundle_hash": main_hash,
        "bundle_urls_sample": bundles[:5],
        "hardened_markers_in_bundle": hardened_markers,
        "legacy_drift_in_bundle": legacy_drift,
        "deployed_hardened_bundle": deployed,
        "pass": deployed and html_r.status_code == 200,
    }


def admin_api_subscribers(token: str) -> List[dict]:
    r = httpx.get(f"{API}/admin/newsletter/subscribers", headers={"Authorization": f"Bearer {token}"}, timeout=120)
    return r.json() if r.status_code == 200 else []


def find_prior_test_email(subs: List[dict]) -> Optional[str]:
    for s in subs:
        em = (s.get("email") or "").lower()
        if any(m in em for m in PRIOR_TEST_MARKERS):
            return s.get("email")
    return subs[0].get("email") if subs else None


def _playwright_start():
    from playwright.sync_api import sync_playwright

    return sync_playwright().start()


def _inject_auth(page, token: Optional[str], user: dict, clear: bool = False) -> None:
    page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
    if clear:
        page.evaluate("() => { localStorage.removeItem('auth_token'); localStorage.removeItem('token'); localStorage.removeItem('user'); }")
    else:
        page.evaluate(
            "([t,u]) => { localStorage.setItem('auth_token', t); localStorage.setItem('user', JSON.stringify(u)); localStorage.removeItem('token'); }",
            [token, user],
        )


def part_newsletter_browser(token: str, user: dict, expected_email: Optional[str]) -> dict:
    try:
        p = _playwright_start()
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}

    SHOT.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    out: Dict[str, Any] = {"pass": False}
    try:
        _inject_auth(page, token, user)
        page.goto(f"{FRONTEND}/admin/marketing/newsletter", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(4000)
        try:
            page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=3000)
        except Exception:
            pass
        body = page.locator("body").inner_text()
        page.screenshot(path=str(SHOT / "newsletter_authenticated.png"))

        count_m = re.search(r"(\d+)\s+total subscribers", body, re.I)
        out["ui_subscriber_count"] = int(count_m.group(1)) if count_m else 0
        out["kit_sync_column_visible"] = "kit sync" in body.lower()
        out["export_button_visible"] = page.get_by_role("button", name=re.compile(r"Export CSV", re.I)).count() > 0
        out["refresh_button_visible"] = page.get_by_role("button", name=re.compile(r"Refresh", re.I)).count() > 0
        out["shows_prior_test_email"] = bool(expected_email and expected_email.lower() in body.lower())
        out["shows_no_subscribers_misleading"] = bool(
            re.search(r"0\s+total subscribers", body, re.I) and out["ui_subscriber_count"] == 0 and "session expired" not in body.lower()
        )

        if out["refresh_button_visible"]:
            page.get_by_role("button", name=re.compile(r"Refresh", re.I)).click()
            page.wait_for_timeout(3000)
            body_after = page.locator("body").inner_text()
            out["refresh_preserves_count"] = out["ui_subscriber_count"] == (
                int(re.search(r"(\d+)\s+total subscribers", body_after, re.I).group(1))
                if re.search(r"(\d+)\s+total subscribers", body_after, re.I)
                else 0
            )

        if out["export_button_visible"] and out["ui_subscriber_count"] > 0:
            with page.expect_download(timeout=30_000) as dl_info:
                page.get_by_role("button", name=re.compile(r"Export CSV", re.I)).click()
            download = dl_info.value
            out["csv_download_filename"] = download.suggested_filename
            out["csv_export_works"] = "newsletter" in (download.suggested_filename or "").lower()

        out["pass"] = (
            out["ui_subscriber_count"] > 0
            and out["kit_sync_column_visible"]
            and out["export_button_visible"]
            and out["refresh_button_visible"]
            and not out.get("shows_no_subscribers_misleading")
        )
        return out
    except Exception as exc:
        out["error"] = str(exc)[:500]
        return out
    finally:
        browser.close()
        p.stop()


def _auth_error_page_probe(path: str, label: str) -> dict:
    try:
        p = _playwright_start()
    except ImportError:
        return {"pass": False, "error": "playwright not installed", "page": label}
    SHOT.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    out: Dict[str, Any] = {"page": label, "path": path, "pass": False}
    try:
        _inject_auth(page, None, {}, clear=True)
        page.evaluate("() => localStorage.setItem('auth_token', 'invalid-browser-closeout-jwt')")
        page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(4000)
        body = page.locator("body").inner_text()
        page.screenshot(path=str(SHOT / f"auth_error_{label}.png"))
        out["shows_session_auth_error"] = bool(
            re.search(r"session expired|not signed in|sign in", body, re.I)
        )
        out["shows_retry_or_signin"] = bool(
            re.search(r"retry|sign in", body, re.I)
        )
        out["misleading_zero_subscribers"] = bool(
            re.search(r"0\s+total subscribers", body, re.I) and not out["shows_session_auth_error"]
        )
        out["misleading_no_subscribers_empty"] = (
            "no subscribers" in body.lower() and not out["shows_session_auth_error"] and label == "newsletter"
        )
        out["pass"] = (
            out["shows_session_auth_error"]
            and out["shows_retry_or_signin"]
            and not out["misleading_zero_subscribers"]
            and not out.get("misleading_no_subscribers_empty")
        )
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        return out
    finally:
        browser.close()
        p.stop()


def part_auth_error_visibility() -> dict:
    pages = [
        ("/admin/marketing/newsletter", "newsletter"),
        ("/admin/content/faqs", "faq"),
        ("/admin/content/feedback", "insights"),
    ]
    probes = [_auth_error_page_probe(path, label) for path, label in pages]
    return {
        "at_utc": utc(),
        "probes": probes,
        "pass": all(p.get("pass") for p in probes),
    }


def part_regression() -> dict:
    backend = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_admin_auth_client_consistency.py", "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    frontend = subprocess.run(
        [
            "npm",
            "test",
            "--",
            "--watchAll=false",
            "src/api/authStorage.test.js",
            "src/utils/adminFetchState.test.js",
            "src/pages/AdminNewsletterPage.test.js",
        ],
        cwd=str(REPO / "frontend"),
        capture_output=True,
        text=True,
        shell=True,
    )
    return {
        "at_utc": utc(),
        "backend": {"ok": backend.returncode == 0, "exit_code": backend.returncode, "tail": (backend.stdout or "")[-400:]},
        "frontend": {"ok": frontend.returncode == 0, "exit_code": frontend.returncode, "tail": (frontend.stdout or frontend.stderr or "")[-600:]},
        "pass": backend.returncode == 0 and frontend.returncode == 0,
    }


def classify(results: Dict[str, bool]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    if not blockers:
        clf = "VERIFIED_OPERATIONALLY"
    elif len(blockers) <= 2:
        clf = "PARTIAL"
    else:
        clf = "FAIL_OPERATIONAL"
    flags = []
    if not results.get("deploy_proof"):
        flags.append("AUTH_DRIFT")
    if not results.get("newsletter_browser"):
        flags.append("ADMIN_DASHBOARD_DRIFT")
    if not results.get("auth_error_visibility"):
        flags.append("ERROR_VISIBILITY_DRIFT")
    return {
        "programme": PROGRAMME,
        "parent_programme": "ADMIN-AUTH-CLIENT-CONSISTENCY-HARDENING-01",
        "prior_classification": "PARTIAL",
        "classification": clf,
        "secondary_flags": sorted(set(flags)),
        "blockers": blockers,
        "checklist": results,
        "hardening_commit": HARDENING_COMMIT,
        "run_tag": RUN_TAG,
        "classified_at_utc": utc(),
    }


def update_report(clf: dict, deploy: dict, newsletter: dict) -> None:
    text = (BUNDLE / "REPORT.md").read_text(encoding="utf-8") if (BUNDLE / "REPORT.md").is_file() else ""
    section = f"""
## {PROGRAMME} ({RUN_TAG})

**Classification:** `{clf.get('classification')}`

### Browser closeout
- Deploy bundle hash: `{deploy.get('main_bundle_hash')}`
- Hardened markers in bundle: {deploy.get('hardened_markers_in_bundle')}
- Newsletter UI count: {newsletter.get('ui_subscriber_count')}
- Auth error probes: {clf.get('checklist', {}).get('auth_error_visibility')}
- Regression: {clf.get('checklist', {}).get('regression')}

Harness: `backend/admin_auth_client_consistency_browser_closeout_01_execute.py`
"""
    if PROGRAMME not in text:
        (BUNDLE / "REPORT.md").write_text(text.rstrip() + "\n" + section + "\n", encoding="utf-8")


def update_watchlist(clf: dict) -> None:
    (BUNDLE / "watchlist.md").write_text(
        "\n".join(
            [
                "# Admin auth client watchlist",
                "",
                f"- Classification: `{clf.get('classification')}`",
                f"- Browser closeout run: `{RUN_TAG}`",
                "",
                "## Status",
                f"- [x] Hardening commit `{HARDENING_COMMIT}`" if clf.get("classification") == "VERIFIED_OPERATIONALLY" else f"- [ ] Verify staging bundle after deploy",
                "- [x] Browser newsletter dashboard shows subscribers" if clf.get("checklist", {}).get("newsletter_browser") else "- [ ] Browser newsletter dashboard",
                "- [x] Auth error surfaces (no fake empty)" if clf.get("checklist", {}).get("auth_error_visibility") else "- [ ] Auth error browser probes",
                "",
                "## Follow-up",
                "- [ ] Migrate AdminContactEnquiriesPage to adminAPI",
                "- [ ] Migrate AdminBlogPage manual fetch",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    print(PROGRAMME, RUN_TAG)
    deploy = fetch_main_bundle()
    write_artifact("admin_auth_browser_deploy_runtime.json", deploy)

    token, user = login_admin()
    subs = admin_api_subscribers(token)
    expected_email = find_prior_test_email(subs)

    newsletter = part_newsletter_browser(token, user, expected_email)
    write_artifact("newsletter_dashboard_browser_closeout_runtime.json", newsletter)

    auth_errors = part_auth_error_visibility()
    write_artifact("admin_auth_error_visibility_browser_runtime.json", auth_errors)

    regression = part_regression()
    write_artifact("admin_auth_browser_regression_runtime.json", regression)

    results = {
        "deploy_proof": deploy.get("pass") is True,
        "newsletter_browser": newsletter.get("pass") is True,
        "auth_error_visibility": auth_errors.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    clf = classify(results)
    write_artifact("classifications.json", clf)
    update_report(clf, deploy, newsletter)
    update_watchlist(clf)

    print("classification:", clf["classification"])
    print("blockers:", clf["blockers"])
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
