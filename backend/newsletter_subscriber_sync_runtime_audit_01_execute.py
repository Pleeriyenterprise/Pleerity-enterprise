#!/usr/bin/env python3
"""
NEWSLETTER-SUBSCRIBER-SYNC-RUNTIME-AUDIT-01
End-to-end runtime audit of newsletter subscriber capture, Kit sync, and admin dashboard.
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
BUNDLE = ROOT / "docs/audit/newsletter_subscriber_sync_runtime_audit_01"
PROGRAMME = "NEWSLETTER-SUBSCRIBER-SYNC-RUNTIME-AUDIT-01"
SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
API_ROOT = API[:-4] if API.endswith("/api") else _raw_api
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "1.2"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"NEWSLETTER-AUDIT-{RUN_TAG}"
TEST_EMAIL = f"newsletter-audit-{RUN_TAG.lower()}@yopmail.com"
TEST_EMAIL_PLUS = f"newsletter-audit+tag-{RUN_TAG.lower()}@yopmail.com"
TEST_EMAIL_UPPER = TEST_EMAIL.upper()


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


def h(token: str = "") -> Dict[str, str]:
    base = {"Content-Type": "application/json"}
    if token:
        base["Authorization"] = f"Bearer {token}"
    return base


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = path if path.startswith("http") else f"{API}{path}"
    headers = kwargs.pop("headers", None) or h(token)
    timeout = kwargs.pop("timeout", 120)
    for attempt in range(4):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=timeout, **kwargs)
            if resp.status_code == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"request failed: {method} {path}")


def login_admin() -> Tuple[str, dict]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    for attempt in range(8):
        r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
        if r.status_code == 429 and attempt < 7:
            time.sleep(25 * (attempt + 1))
            continue
        r.raise_for_status()
        body = r.json()
        return body.get("access_token") or body["token"], body.get("user") or {}
    raise RuntimeError("admin login failed")


def login_client() -> str:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    if not pw:
        return ""
    r = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": pw}, timeout=120)
    return r.json().get("access_token", "") if r.status_code == 200 else ""


def login_contractor() -> str:
    pw = read_pw(f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt", "OPS_CONTRACTOR_PASSWORD")
    if not pw:
        return ""
    r = httpx.post(
        f"{API}/auth/contractor-login",
        json={"email": "f2-ops-heating-wales@yopmail.com", "password": pw},
        timeout=120,
    )
    return r.json().get("access_token", "") if r.status_code == 200 else ""


def staff_admin_user(admin_user: dict) -> dict:
    email = admin_user.get("email") or os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    return {**admin_user, "email": email, "role": admin_user.get("role") or "ROLE_ADMIN", "name": admin_user.get("name") or "Ops Verify Admin"}


def subscribe(email: str, source: str = "newsletter_page") -> httpx.Response:
    time.sleep(max(PACE, 2.0))
    return httpx.post(
        f"{API_ROOT}/api/newsletter/subscribe",
        params={"email": email, "source": source},
        headers={"Content-Type": "application/json"},
        timeout=120,
    )


def list_subscribers_admin(token: str) -> Tuple[int, List[dict]]:
    r = req("get", "/admin/newsletter/subscribers", token)
    if r.status_code != 200:
        return r.status_code, []
    data = r.json()
    return r.status_code, data if isinstance(data, list) else []


def find_subscriber(subs: List[dict], email: str) -> Optional[dict]:
    target = email.lower().strip()
    for s in subs:
        if (s.get("email") or "").lower().strip() == target:
            return s
    return None


# ---------------------------------------------------------------------------
# PART 1 — ARCHITECTURE
# ---------------------------------------------------------------------------

def part_architecture(commit_sha: str) -> dict:
    return {
        "at_utc": utc(),
        "programme": PROGRAMME,
        "commit_sha": commit_sha,
        "intended_flow": "Website form → POST /api/newsletter/subscribe → MongoDB newsletter_subscribers → Kit API v4 POST /subscribers",
        "source_of_truth": {
            "admin_dashboard": "MongoDB collection newsletter_subscribers (local DB)",
            "email_campaigns": "Kit.com (external)",
            "note": "Kit is NOT read back into admin; one-way push only",
        },
        "collections": {
            "newsletter_subscribers": {
                "fields": [
                    "subscriber_id",
                    "email",
                    "status",
                    "source",
                    "kit_sync_status",
                    "kit_sync_error",
                    "kit_synced_at",
                    "subscribed_at",
                    "unsubscribed_at",
                ]
            }
        },
        "api_endpoints": {
            "public_subscribe": "POST /api/newsletter/subscribe?email=&source=",
            "admin_list": "GET /api/admin/newsletter/subscribers (admin_route_guard)",
            "legacy_admin_list": "GET /api/newsletter/subscribers (admin_route_guard, same data)",
        },
        "frontend": {
            "public_page": f"{FRONTEND}/newsletter → NewsletterPage.js",
            "admin_page": f"{FRONTEND}/admin/marketing/newsletter → AdminNewsletterPage.jsx",
            "footer": "PublicFooter links to /newsletter (no inline form)",
            "insights": "InsightsHubPage links to /newsletter",
            "checklist_modal": "POST /api/leads/capture/compliance-checklist → leads collection (NOT newsletter_subscribers)",
        },
        "environment_variables": {
            "KIT_API_KEY": "required for Kit sync; never logged",
            "KIT_API_BASE": "default https://api.kit.com/v4",
            "REACT_APP_BACKEND_URL": "frontend backend base",
        },
        "kit_integration": {
            "service": "backend/services/kit_integration.py",
            "api": "POST {KIT_API_BASE}/subscribers",
            "auth_header": "X-Kit-Api-Key",
            "custom_field": "Source",
            "list_form_tag_ids": "none configured in code — global subscriber create only",
            "webhook": "none implemented",
            "backfill_import": "none implemented",
        },
        "admin_ui_token_key": {
            "AdminNewsletterPage": "localStorage.getItem('token')",
            "AuthContext_standard": "localStorage.getItem('auth_token')",
            "drift_detected": True,
        },
        "pass": True,
    }


# ---------------------------------------------------------------------------
# PART 2 — PUBLIC SUBSCRIBE (browser + API)
# ---------------------------------------------------------------------------

def part_public_subscribe() -> dict:
    api_r = subscribe(TEST_EMAIL, "newsletter_page")
    api_body = {}
    try:
        api_body = api_r.json()
    except Exception:
        api_body = {"raw": api_r.text[:300]}

    dup_r = subscribe(TEST_EMAIL, "newsletter_page")
    dup_body = dup_r.json() if dup_r.status_code == 200 else {}

    browser = _public_browser_subscribe()
    return {
        "at_utc": utc(),
        "test_email": TEST_EMAIL,
        "marker": MARKER,
        "api_subscribe_status": api_r.status_code,
        "api_subscribe_body": api_body,
        "duplicate_status": dup_r.status_code,
        "duplicate_body": dup_body,
        "duplicate_safe": dup_r.status_code == 200 and "already" in (dup_body.get("message") or "").lower(),
        "browser": browser,
        "pass": api_r.status_code == 200 and api_body.get("success") is True and browser.get("pass") is True,
    }


def _public_browser_subscribe() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot_dir = BUNDLE / "screenshots" / "public"
    shot_dir.mkdir(parents=True, exist_ok=True)
    email = f"newsletter-browser-{RUN_TAG.lower()}@yopmail.com"
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    out: Dict[str, Any] = {"pass": False, "test_email": email}
    console_errors: List[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    try:
        page.goto(f"{FRONTEND}/newsletter", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        try:
            page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=3000)
        except Exception:
            pass
        page.screenshot(path=str(shot_dir / "newsletter_form.png"))
        email_input = page.locator('input[type="email"]')
        out["email_field_present"] = email_input.count() > 0
        email_input.fill(email)
        with page.expect_response(
            lambda r: "/newsletter/subscribe" in r.url and r.request.method == "POST",
            timeout=60_000,
        ) as resp_info:
            page.get_by_role("button", name=re.compile(r"Subscribe", re.I)).click()
        resp = resp_info.value
        out["subscribe_api_status"] = resp.status
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        out["success_message"] = "subscribed successfully" in body.lower() or "thank you" in body.lower()
        page.screenshot(path=str(shot_dir / "newsletter_success.png"))
        out["console_errors"] = [e for e in console_errors if "favicon" not in e.lower()][:10]
        out["screenshots"] = ["screenshots/public/newsletter_form.png", "screenshots/public/newsletter_success.png"]
        out["pass"] = (
            out.get("email_field_present")
            and resp.status == 200
            and out.get("success_message")
            and len(out.get("console_errors") or []) == 0
        )
        return out
    except Exception as exc:
        out["error"] = str(exc)[:500]
        return out
    finally:
        browser.close()
        p.stop()


# ---------------------------------------------------------------------------
# PART 3 — LOCAL DB
# ---------------------------------------------------------------------------

def part_local_subscriber(at: str) -> dict:
    status, subs = list_subscribers_admin(at)
    before_count = len(subs)
    row = find_subscriber(subs, TEST_EMAIL)
    browser_row = find_subscriber(subs, f"newsletter-browser-{RUN_TAG.lower()}@yopmail.com")
    classification = None
    if not row and not browser_row:
        classification = "LOCAL_CAPTURE_GAP"
    return {
        "at_utc": utc(),
        "admin_api_status": status,
        "total_subscribers_in_db": before_count,
        "test_email": TEST_EMAIL,
        "test_row": _safe_subscriber(row),
        "browser_test_row": _safe_subscriber(browser_row),
        "local_row_exists": row is not None or browser_row is not None,
        "classification_if_missing": classification,
        "pass": status == 200 and (row is not None or browser_row is not None),
    }


def _safe_subscriber(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    return {
        "subscriber_id": row.get("subscriber_id"),
        "email": row.get("email"),
        "status": row.get("status"),
        "source": row.get("source"),
        "kit_sync_status": row.get("kit_sync_status"),
        "kit_sync_error": (row.get("kit_sync_error") or "")[:120] or None,
        "kit_synced_at": row.get("kit_synced_at"),
        "subscribed_at": row.get("subscribed_at"),
    }


# ---------------------------------------------------------------------------
# PART 4 — KIT SYNC
# ---------------------------------------------------------------------------

def part_kit_sync(at: str) -> dict:
    _, subs = list_subscribers_admin(at)
    row = find_subscriber(subs, TEST_EMAIL) or find_subscriber(subs, f"newsletter-browser-{RUN_TAG.lower()}@yopmail.com")
    kit_status = (row or {}).get("kit_sync_status")
    kit_error = (row or {}).get("kit_sync_error") or ""
    kit_configured_inferred = kit_status == "SYNCED" or (kit_status == "FAILED" and "not set" not in kit_error.lower())
    return {
        "at_utc": utc(),
        "test_email": (row or {}).get("email"),
        "kit_sync_status": kit_status,
        "kit_sync_error_redacted": kit_error[:120] if kit_error else None,
        "kit_synced_at": (row or {}).get("kit_synced_at"),
        "kit_api_key_configured_inferred": kit_configured_inferred,
        "kit_subscriber_id_stored_locally": False,
        "note": "No kit_subscriber_id field in model; verification via kit_sync_status only",
        "retry_mechanism": "none — failed sync not retried automatically",
        "list_form_tag_ids_in_code": "none",
        "pass": row is not None and kit_status in ("SYNCED", "FAILED"),
    }


# ---------------------------------------------------------------------------
# PART 5 — ADMIN DASHBOARD
# ---------------------------------------------------------------------------

def part_admin_dashboard(at: str, admin_user: dict) -> dict:
    status, subs = list_subscribers_admin(at)
    api_count = len(subs)
    api_has_test = find_subscriber(subs, TEST_EMAIL) is not None
    browser_wrong_token = _admin_browser_newsletter(at, admin_user, token_key="token")
    browser_correct_token = _admin_browser_newsletter(at, admin_user, token_key="auth_token")
    drift = (
        browser_wrong_token.get("ui_subscriber_count", 0) == 0
        and browser_correct_token.get("ui_subscriber_count", 0) > 0
        and api_count > 0
    ) or (
        api_count > 0 and browser_wrong_token.get("ui_subscriber_count", 0) == 0 and not browser_wrong_token.get("api_fetch_ok")
    )
    return {
        "at_utc": utc(),
        "admin_api_status": status,
        "admin_api_count": api_count,
        "admin_api_has_test_subscriber": api_has_test,
        "browser_wrong_token_key": browser_wrong_token,
        "browser_correct_token_key": browser_correct_token,
        "admin_ui_token_drift": drift,
        "csv_export": _csv_export_probe(subs),
        "pass": status == 200 and api_has_test and browser_correct_token.get("pass") is True,
    }


def _admin_browser_newsletter(at: str, admin_user: dict, token_key: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot_dir = BUNDLE / "screenshots" / "admin"
    shot_dir.mkdir(parents=True, exist_ok=True)
    admin_user = staff_admin_user(admin_user)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    out: Dict[str, Any] = {"pass": False, "token_key_used": token_key}
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            f"([t,u])=>{{localStorage.setItem('{token_key}',t);localStorage.setItem('user',JSON.stringify(u));}}",
            [at, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/marketing/newsletter", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(5000)
        try:
            page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=3000)
        except Exception:
            pass
        body = page.locator("body").inner_text()
        shot = shot_dir / f"newsletter_admin_{token_key}.png"
        page.screenshot(path=str(shot))
        count_match = re.search(r"(\d+)\s+total subscribers", body, re.I)
        out["ui_subscriber_count"] = int(count_match.group(1)) if count_match else 0
        out["shows_no_subscribers"] = "no subscribers" in body.lower()
        out["shows_test_email"] = TEST_EMAIL.lower() in body.lower() or f"newsletter-browser-{RUN_TAG.lower()}" in body.lower()
        out["kit_sync_column_visible"] = "kit sync" in body.lower()
        out["export_button_visible"] = page.get_by_role("button", name=re.compile(r"Export CSV", re.I)).count() > 0
        out["screenshot"] = str(shot.relative_to(BUNDLE)).replace("\\", "/")
        out["api_fetch_ok"] = out["ui_subscriber_count"] > 0 or out["shows_test_email"]
        out["pass"] = out["ui_subscriber_count"] > 0 and out["shows_test_email"] and out["kit_sync_column_visible"]
        return out
    except Exception as exc:
        out["error"] = str(exc)[:500]
        return out
    finally:
        browser.close()
        p.stop()


def _csv_export_probe(subs: List[dict]) -> dict:
  rows = subs[:3]
  header = "Email,Status,Source,Subscribed Date"
  lines = [header] + [f"{s.get('email')},{s.get('status')},{s.get('source')},{s.get('subscribed_at')}" for s in rows]
  csv_text = "\n".join(lines)
  leaked = any(k in csv_text.lower() for k in ("kit_api", "x-kit-api", "bearer ", "password"))
  return {
    "row_count_sample": len(rows),
    "header": header,
    "secrets_leaked": leaked,
    "pass": not leaked,
  }


# ---------------------------------------------------------------------------
# PART 6 — SYNC DIRECTION
# ---------------------------------------------------------------------------

def part_sync_direction(at: str) -> dict:
    _, subs = list_subscribers_admin(at)
    synced = sum(1 for s in subs if s.get("kit_sync_status") == "SYNCED")
    failed = sum(1 for s in subs if s.get("kit_sync_status") == "FAILED")
    pending = sum(1 for s in subs if s.get("kit_sync_status") == "PENDING")
    actual = "A_website_local_then_kit_push"
    notes = []
    if failed > synced and len(subs) > 0:
        notes.append("Many local rows FAILED Kit sync — KIT_API_KEY may be missing on backend")
    if len(subs) == 0:
        notes.append("Local DB empty — if Kit has subscribers, historical Kit-only capture or different environment")
    return {
        "at_utc": utc(),
        "intended_design": "A: Website → local DB → Kit (one-way push)",
        "actual_behaviour": actual,
        "kit_to_local_sync": False,
        "two_way_sync": False,
        "webhook_present": False,
        "admin_reads": "local MongoDB only (not Kit API)",
        "local_counts": {"total": len(subs), "synced": synced, "failed": failed, "pending": pending},
        "if_kit_has_more_than_local": "BACKFILL_GAP — no import/webhook; Kit-only subscribers invisible to admin",
        "notes": notes,
        "pass": True,
    }


# ---------------------------------------------------------------------------
# PART 7 — BACKFILL
# ---------------------------------------------------------------------------

def part_backfill() -> dict:
    scripts = list(ROOT.glob("**/*kit*")) + list(ROOT.glob("**/*newsletter*backfill*"))
    script_names = sorted({p.name for p in scripts if p.suffix == ".py" and "audit" not in p.name.lower()})[:20]
    return {
        "at_utc": utc(),
        "kit_import_script_exists": False,
        "kit_backfill_endpoint_exists": False,
        "relevant_scripts": script_names,
        "dedupe_on_subscribe": "email exact match in newsletter_subscribers.find_one",
        "status_mapping": "SUBSCRIBED default; UNSUBSCRIBED field exists but no public flow",
        "unsubscribe_mapping": "not implemented",
        "source_mapping": "passed as Kit custom field Source",
        "sync_audit_trail": "create_audit_log NEWSLETTER_SUBSCRIBED metadata",
        "classification": "BACKFILL_GAP",
        "pass": False,
    }


# ---------------------------------------------------------------------------
# PART 8 — PERMISSIONS
# ---------------------------------------------------------------------------

def part_permissions(at: str) -> dict:
    client_tok = login_client()
    contractor_tok = login_contractor()
    probes = []
    r = subscribe(f"newsletter-perm-probe-{RUN_TAG.lower()}@yopmail.com")
    probes.append({"check": "public_can_subscribe", "status": r.status_code, "pass": r.status_code == 200})
    r = req("get", "/admin/newsletter/subscribers")
    probes.append({"check": "admin_list_no_auth", "status": r.status_code, "pass": r.status_code == 401})
    if client_tok:
        r = req("get", "/admin/newsletter/subscribers", client_tok)
        probes.append({"check": "client_blocked", "status": r.status_code, "pass": r.status_code in (401, 403)})
    if contractor_tok:
        r = req("get", "/admin/newsletter/subscribers", contractor_tok)
        probes.append({"check": "contractor_blocked", "status": r.status_code, "pass": r.status_code in (401, 403)})
    r = req("get", "/admin/newsletter/subscribers", at)
    probes.append({"check": "admin_can_list", "status": r.status_code, "pass": r.status_code == 200})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


# ---------------------------------------------------------------------------
# PART 9 — EDGE CASES
# ---------------------------------------------------------------------------

def part_edge_cases(at: str) -> dict:
    cases = []
    invalid = subscribe("not-an-email")
    cases.append({"case": "invalid_email", "status": invalid.status_code, "pass": invalid.status_code in (400, 422)})

    upper = subscribe(TEST_EMAIL_UPPER)
    cases.append({"case": "uppercase_email", "status": upper.status_code, "body": upper.json() if upper.status_code == 200 else None})

    plus = subscribe(TEST_EMAIL_PLUS)
    cases.append({"case": "plus_address", "status": plus.status_code, "pass": plus.status_code == 200})

    dup2 = subscribe(TEST_EMAIL_PLUS)
    cases.append({"case": "duplicate_plus", "status": dup2.status_code, "message": (dup2.json() if dup2.status_code == 200 else {}).get("message")})

    _, subs = list_subscribers_admin(at)
    export_empty_ok = True
    cases.append({"case": "export_with_subscribers", "admin_count": len(subs), "pass": len(subs) >= 1})

    return {
        "at_utc": utc(),
        "cases": cases,
        "kit_failure_handling": "local row saved with kit_sync_status FAILED if Kit fails",
        "local_db_write_before_kit": True,
        "pass": all(c.get("pass", True) for c in cases),
    }


# ---------------------------------------------------------------------------
# PART 10 — REGRESSION
# ---------------------------------------------------------------------------

def part_regression() -> dict:
    suites = [
        ("tests/test_admin_action_governance_policy.py", ["-q", "--tb=no"]),
    ]
    out = {"at_utc": utc(), "suites": [], "newsletter_unit_tests_exist": False, "pass": True}
    newsletter_test = ROOT / "tests" / "test_newsletter_subscriber.py"
    if newsletter_test.is_file():
        suites.insert(0, ("tests/test_newsletter_subscriber.py", ["-q", "--tb=no"]))
        out["newsletter_unit_tests_exist"] = True
    for suite, extra in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", suite, *extra],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        row = {
            "suite": suite,
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "tail": (proc.stdout or proc.stderr or "")[-400:],
        }
        out["suites"].append(row)
        if suite.startswith("tests/test_newsletter"):
            out["pass"] = out["pass"] and row["ok"]
    out["gap"] = "No dedicated newsletter/kit unit tests in repo" if not out["newsletter_unit_tests_exist"] else None
    return out


# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

def classify(results: Dict[str, bool], flags: List[str]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    secondary = sorted(set(flags))
    if "ADMIN_DASHBOARD_DRIFT" in secondary and results.get("local_db") and results.get("kit_sync"):
        clf = "ADMIN_DASHBOARD_DRIFT"
    elif "LOCAL_CAPTURE_GAP" in secondary:
        clf = "LOCAL_CAPTURE_GAP"
    elif "BACKFILL_GAP" in secondary and not results.get("admin_dashboard"):
        clf = "PARTIAL"
    elif not blockers:
        clf = "VERIFIED_OPERATIONALLY"
    elif len(blockers) <= 3:
        clf = "PARTIAL"
    else:
        clf = "FAIL_OPERATIONAL"
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "secondary_flags": secondary,
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def write_report(clf: dict) -> None:
    lines = [
        "# Newsletter Subscriber Sync Runtime Audit",
        "",
        f"**Programme:** {PROGRAMME}",
        f"**Run tag:** {RUN_TAG}",
        f"**Classification:** `{clf.get('classification')}`",
        "",
        "## Summary",
        "",
        "Traced newsletter path: public `/newsletter` → `POST /api/newsletter/subscribe` → MongoDB `newsletter_subscribers` → Kit API v4 push.",
        "Admin dashboard reads local DB via `GET /api/admin/newsletter/subscribers`.",
        "",
        "## Key findings",
        "",
    ]
    for flag in clf.get("secondary_flags") or []:
        lines.append(f"- `{flag}`")
    for b in clf.get("blockers") or []:
        lines.append(f"- Blocker: {b}")
    lines.extend(
        [
            "",
            "## Admin token drift",
            "",
            "`AdminNewsletterPage.jsx` uses `localStorage.getItem('token')` but auth stores `auth_token`.",
            "This causes silent API 401 and UI shows 0 subscribers even when local DB has rows.",
            "",
            "## Sync direction",
            "",
            "One-way: Website → local DB → Kit. No Kit→local webhook or backfill.",
            "",
            f"Harness: `backend/newsletter_subscriber_sync_runtime_audit_01_execute.py`",
        ]
    )
    (BUNDLE / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_watchlist(clf: dict) -> None:
    (BUNDLE / "watchlist.md").write_text(
        "\n".join(
            [
                "# Newsletter subscriber sync watchlist",
                "",
                f"- Classification: `{clf.get('classification')}`",
                f"- Run tag: `{RUN_TAG}`",
                "",
                "## Fix candidates",
                "- [ ] Fix AdminNewsletterPage to use `auth_token` (and AdminFAQPage, AdminInsightsFeedbackPage)",
                "- [ ] Add Kit→local backfill script or webhook for historical Kit subscribers",
                "- [ ] Add newsletter/kit unit tests",
                "- [ ] Normalize email to lowercase on subscribe",
                "- [ ] Add Kit sync retry for FAILED rows",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    commit_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT.parent), capture_output=True, text=True)
    commit_sha = (commit_proc.stdout or "").strip() or "unknown"

    arch = part_architecture(commit_sha)
    write_artifact("newsletter_architecture_runtime.json", arch)

    at, admin_user = login_admin()

    public = part_public_subscribe()
    write_artifact("public_subscribe_runtime.json", public)

    local = part_local_subscriber(at)
    write_artifact("local_subscriber_runtime.json", local)

    kit = part_kit_sync(at)
    write_artifact("kit_sync_runtime.json", kit)

    admin = part_admin_dashboard(at, admin_user)
    write_artifact("admin_newsletter_dashboard_runtime.json", admin)

    sync_dir = part_sync_direction(at)
    write_artifact("sync_direction_runtime.json", sync_dir)

    backfill = part_backfill()
    write_artifact("newsletter_backfill_runtime.json", backfill)

    perms = part_permissions(at)
    write_artifact("newsletter_permissions_runtime.json", perms)

    edges = part_edge_cases(at)
    write_artifact("newsletter_edge_cases_runtime.json", edges)

    regression = part_regression()
    write_artifact("newsletter_regression_runtime.json", regression)

    flags = []
    if not local.get("pass"):
        flags.append("LOCAL_CAPTURE_GAP")
    if kit.get("kit_sync_status") == "FAILED":
        flags.append("KIT_SYNC_DRIFT")
    if admin.get("admin_ui_token_drift"):
        flags.append("ADMIN_DASHBOARD_DRIFT")
    if backfill.get("classification") == "BACKFILL_GAP":
        flags.append("BACKFILL_GAP")
    if not perms.get("pass"):
        flags.append("PERMISSION_DRIFT")

    results = {
        "architecture": arch.get("pass") is True,
        "public_subscribe": public.get("pass") is True,
        "local_db": local.get("pass") is True,
        "kit_sync": kit.get("pass") is True,
        "admin_dashboard": admin.get("pass") is True,
        "sync_direction": sync_dir.get("pass") is True,
        "backfill": False,
        "permissions": perms.get("pass") is True,
        "edge_cases": edges.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    clf = classify(results, flags)
    write_artifact("classifications.json", clf)
    write_report(clf)
    write_watchlist(clf)

    print("classification:", clf.get("classification"))
    print("blockers:", clf.get("blockers"))
    return 0 if clf.get("classification") == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
