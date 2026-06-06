#!/usr/bin/env python3
"""ADMIN-AUTH-CLIENT-CONSISTENCY-HARDENING-01 closeout harness."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
FRONTEND_SRC = REPO / "frontend" / "src"
BUNDLE = ROOT / "docs/audit/admin_auth_client_consistency_hardening_01"
PROGRAMME = "ADMIN-AUTH-CLIENT-CONSISTENCY-HARDENING-01"
SLUG = "6fd5ac4c_d35a58ae"

_raw_api = __import__("os").environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
API_ROOT = API[:-4] if API.endswith("/api") else _raw_api
FRONTEND = __import__("os").environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
TEST_EMAIL = f"auth-hardening-{RUN_TAG.lower()}@yopmail.com"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def read_pw(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def login_admin() -> str:
    email = __import__("os").environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt")
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json().get("access_token") or r.json()["token"]


def scan_token_usage() -> dict:
    legacy = re.compile(r"""localStorage\.getItem\(\s*['"]token['"]\s*\)""")
    auth_reads = re.compile(r"""localStorage\.getItem\(\s*['"]auth_token['"]\s*\)""")
    manual_bearer = re.compile(r"""Authorization['"]\s*:\s*[`'"]Bearer\s*\$\{localStorage""")
    entries: List[dict] = []
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in {".js", ".jsx"}:
            continue
        rel = str(path.relative_to(REPO)).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        if legacy.search(text):
            entries.append({"file": rel, "classification": "drift", "pattern": "legacy_token_key"})
        elif "adminAPI." in text and "Admin" in path.name:
            entries.append({"file": rel, "classification": "correct", "pattern": "centralized_admin_api"})
        elif auth_reads.search(text) and manual_bearer.search(text):
            entries.append({"file": rel, "classification": "risky_duplication", "pattern": "manual_fetch_auth_token"})
        elif rel.endswith("api/authStorage.js"):
            entries.append({"file": rel, "classification": "correct", "pattern": "auth_layer"})
        elif rel.endswith("api/client.js"):
            entries.append({"file": rel, "classification": "correct", "pattern": "axios_interceptor"})
    drift_count = sum(1 for e in entries if e["classification"] == "drift")
    return {
        "at_utc": utc(),
        "entries_sample": entries[:40],
        "drift_count": drift_count,
        "drift_files": [e["file"] for e in entries if e["classification"] == "drift"],
        "pass": drift_count == 0,
    }


def part_auth_client_hardening() -> dict:
    checks = {
        "authStorage_js": (FRONTEND_SRC / "api" / "authStorage.js").is_file(),
        "adminFetchState_js": (FRONTEND_SRC / "utils" / "adminFetchState.js").is_file(),
        "useAuthenticatedQuery": (FRONTEND_SRC / "hooks" / "useAuthenticatedQuery.js").is_file(),
        "AdminFetchStatePanel": (FRONTEND_SRC / "components" / "admin" / "AdminFetchStatePanel.jsx").is_file(),
        "adminAPI_newsletter": "listNewsletterSubscribers" in (FRONTEND_SRC / "api" / "client.js").read_text(encoding="utf-8"),
        "client_uses_authStorage": "from './authStorage'" in (FRONTEND_SRC / "api" / "client.js").read_text(encoding="utf-8"),
    }
    return {"at_utc": utc(), "checks": checks, "pass": all(checks.values())}


def part_admin_page_hardening() -> dict:
    pages = ["AdminNewsletterPage.jsx", "AdminFAQPage.jsx", "AdminInsightsFeedbackPage.jsx"]
    rows = []
    for name in pages:
        text = (FRONTEND_SRC / "pages" / name).read_text(encoding="utf-8")
        rows.append({
            "page": name,
            "uses_adminAPI": "adminAPI." in text,
            "uses_useAuthenticatedQuery": "useAuthenticatedQuery" in text,
            "legacy_token": "getItem('token')" in text or 'getItem("token")' in text,
            "has_error_surface": "error" in text and ("AdminFetchStatePanel" in text or "error.message" in text),
        })
    return {
        "at_utc": utc(),
        "pages": rows,
        "pass": all(r["uses_adminAPI"] and not r["legacy_token"] and r["has_error_surface"] for r in rows),
    }


def part_newsletter_closeout(at: str) -> dict:
    before = httpx.get(f"{API}/admin/newsletter/subscribers", headers={"Authorization": f"Bearer {at}"}, timeout=120)
    before_count = len(before.json()) if before.status_code == 200 else 0
    sub = httpx.post(
        f"{API_ROOT}/api/newsletter/subscribe",
        params={"email": TEST_EMAIL, "source": "newsletter_page"},
        timeout=120,
    )
    dup = httpx.post(
        f"{API_ROOT}/api/newsletter/subscribe",
        params={"email": TEST_EMAIL, "source": "newsletter_page"},
        timeout=120,
    )
    after = httpx.get(f"{API}/admin/newsletter/subscribers", headers={"Authorization": f"Bearer {at}"}, timeout=120)
    subs = after.json() if after.status_code == 200 else []
    row = next((s for s in subs if (s.get("email") or "").lower() == TEST_EMAIL.lower()), None)
    browser = _browser_newsletter(at)
    return {
        "at_utc": utc(),
        "test_email": TEST_EMAIL,
        "subscribe_status": sub.status_code,
        "duplicate_message": dup.json().get("message") if dup.status_code == 200 else None,
        "admin_api_before": before_count,
        "admin_api_after": len(subs),
        "test_row_kit_sync": (row or {}).get("kit_sync_status"),
        "browser": browser,
        "pass": sub.status_code == 200 and row is not None and after.status_code == 200,
    }


def _browser_newsletter(at: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    admin_user = {"email": "admin@test", "role": "ROLE_ADMIN", "name": "Audit Admin"}
    shot_dir = BUNDLE / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    out: Dict[str, Any] = {"pass": False}
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [at, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/marketing/newsletter", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(5000)
        body = page.locator("body").inner_text()
        page.screenshot(path=str(shot_dir / "newsletter_after_hardening.png"))
        import re as _re

        m = _re.search(r"(\d+)\s+total subscribers", body, _re.I)
        out["ui_count"] = int(m.group(1)) if m else 0
        out["shows_test_email"] = TEST_EMAIL.lower() in body.lower()
        out["shows_auth_error"] = "session expired" in body.lower() or "sign in" in body.lower()
        out["shows_no_subscribers_empty"] = "no subscribers yet" in body.lower()
        out["note"] = "Staging bundle may lag until frontend deploy; source+API+unit tests are primary proof"
        out["pass"] = out["ui_count"] > 0 and out["shows_test_email"]
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        return out
    finally:
        browser.close()
        p.stop()


def part_error_visibility() -> dict:
    admin_pages = sorted(FRONTEND_SRC.glob("pages/Admin*.jsx")) + sorted(FRONTEND_SRC.glob("pages/Admin*.js"))
    rows = []
    for path in admin_pages:
        if path.name.endswith(".test.js"):
            continue
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(REPO)).replace("\\", "/")
        silent = "catch (e) {}" in text or ("if (res.ok)" in text and "setError" not in text and "error" not in text.lower())
        legacy_token = "getItem('token')" in text
        uses_central = "adminAPI." in text or "useAuthenticatedQuery" in text
        if legacy_token:
            clf = "AUTH_DRIFT"
        elif silent and "fetch(" in text:
            clf = "MISLEADING_EMPTY_STATE"
        elif uses_central:
            clf = "SAFE"
        else:
            clf = "NETWORK_DRIFT" if "fetch(" in text else "SAFE"
        rows.append({"file": rel, "classification": clf})
    return {
        "at_utc": utc(),
        "pages_audited": len(rows),
        "summary": {
            c: sum(1 for r in rows if r["classification"] == c)
            for c in ["SAFE", "MISLEADING_EMPTY_STATE", "AUTH_DRIFT", "NETWORK_DRIFT"]
        },
        "sample": rows[:25],
        "pass": sum(1 for r in rows if r["classification"] == "AUTH_DRIFT") == 0,
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
        "backend": {"ok": backend.returncode == 0, "tail": (backend.stdout or backend.stderr or "")[-500:]},
        "frontend": {"ok": frontend.returncode == 0, "tail": (frontend.stdout or frontend.stderr or "")[-800:]},
        "pass": backend.returncode == 0 and frontend.returncode == 0,
    }


def classify(results: Dict[str, bool], newsletter: dict) -> dict:
    blockers = [k for k, v in results.items() if not v]
    browser_ok = (newsletter.get("browser") or {}).get("pass") is True
    if blockers:
        clf = "PARTIAL" if len(blockers) <= 2 else "FAIL_OPERATIONAL"
    elif not browser_ok:
        clf = "PARTIAL"
        blockers = ["staging_browser_deploy"]
    else:
        clf = "VERIFIED_OPERATIONALLY"
    flags = []
    if not results.get("token_audit"):
        flags.append("AUTH_DRIFT")
    if not results.get("newsletter_closeout"):
        flags.append("ADMIN_DASHBOARD_DRIFT")
    if not browser_ok:
        flags.append("ERROR_VISIBILITY_DRIFT")
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "secondary_flags": flags,
        "blockers": blockers,
        "checklist": results,
        "run_tag": RUN_TAG,
        "classified_at_utc": utc(),
    }


def main() -> int:
    print(PROGRAMME, RUN_TAG)
    token_audit = scan_token_usage()
    write_artifact("auth_token_usage_inventory.json", token_audit)

    auth_client = part_auth_client_hardening()
    write_artifact("auth_client_hardening_runtime.json", auth_client)

    admin_pages = part_admin_page_hardening()
    write_artifact("admin_page_hardening_runtime.json", admin_pages)

    at = login_admin()
    newsletter = part_newsletter_closeout(at)
    write_artifact("newsletter_dashboard_closeout_runtime.json", newsletter)

    visibility = part_error_visibility()
    write_artifact("admin_error_visibility_runtime.json", visibility)

    regression = part_regression()
    write_artifact("auth_client_regression_runtime.json", regression)

    results = {
        "token_audit": token_audit.get("pass"),
        "auth_client": auth_client.get("pass"),
        "admin_pages": admin_pages.get("pass"),
        "newsletter_closeout": newsletter.get("pass"),
        "error_visibility": visibility.get("pass"),
        "regression": regression.get("pass"),
    }
    clf = classify(results, newsletter)
    write_artifact("classifications.json", clf)

    (BUNDLE / "REPORT.md").write_text(
        "\n".join(
            [
                "# Admin Auth Client Consistency Hardening",
                "",
                f"**Programme:** {PROGRAMME}",
                f"**Run tag:** `{RUN_TAG}`",
                f"**Classification:** `{clf['classification']}`",
                "",
                "## Changes",
                "",
                "- Added `authStorage.js` canonical token helpers",
                "- Hardened `api/client.js` interceptor to use authStorage",
                "- Added `useAuthenticatedQuery`, `AdminFetchStatePanel`, `adminFetchState`",
                "- Refactored AdminNewsletterPage, AdminFAQPage, AdminInsightsFeedbackPage onto adminAPI",
                "",
                "## Token drift",
                "",
                f"- Legacy `token` key reads: **{token_audit.get('drift_count')}**",
                "",
                f"Harness: `backend/admin_auth_client_consistency_hardening_01_execute.py`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (BUNDLE / "watchlist.md").write_text(
        "\n".join(
            [
                "# Admin auth client watchlist",
                "",
                f"- Classification: `{clf['classification']}`",
                "",
                "## Remaining",
                "- [ ] Migrate AdminContactEnquiriesPage / AdminBlogPage manual fetch to adminAPI",
                "- [ ] Deploy frontend bundle for staging browser closeout",
                "- [ ] Remove AdminOrdersPage.old.js dead code",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print("classification:", clf["classification"])
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
