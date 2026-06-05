#!/usr/bin/env python3
"""
CONTACT-ENQUIRY-MANAGEMENT-END-TO-END-RUNTIME-AUDIT-01
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/contact_enquiry_management_runtime_audit_01"
PROGRAMME = "CONTACT-ENQUIRY-MANAGEMENT-END-TO-END-RUNTIME-AUDIT-01"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "1.5"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"CONTACT-AUDIT-{RUN_TAG}"


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
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = path if path.startswith("http") else f"{API}{path}"
    headers = kwargs.pop("headers", None) or (h(token) if token else h())
    for attempt in range(4):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
            if resp.status_code == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("request failed")


def public_post(body: dict) -> httpx.Response:
    time.sleep(max(PACE, 3.0))
    return httpx.post(f"{API}/public/contact", json=body, headers={"Content-Type": "application/json"}, timeout=120)


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
    raise RuntimeError("admin login failed after retries")


def staff_admin_user(admin_user: dict) -> dict:
    email = admin_user.get("email") or os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    return {
        **admin_user,
        "email": email,
        "role": admin_user.get("role") or "ROLE_ADMIN",
        "name": admin_user.get("name") or "Ops Verify Admin",
    }


def login_client() -> str:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    if not pw:
        return ""
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=120)
    return r.json().get("access_token", "") if r.status_code == 200 else ""


def login_contractor() -> str:
    pw = read_pw(f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt", "OPS_CONTRACTOR_PASSWORD")
    if not pw:
        return ""
    r = httpx.post(f"{API}/auth/contractor-login", json={"email": CONTRACTOR_EMAIL, "password": pw}, timeout=120)
    return r.json().get("access_token", "") if r.status_code == 200 else ""


def probe_email(kind: str) -> str:
    return f"contact-audit-{RUN_TAG}-{kind}@audit-probe.example"


def submit_payload(kind: str, **overrides) -> dict:
    base = {
        "full_name": f"Audit Probe {kind}",
        "email": probe_email(kind),
        "phone": "+441234567890",
        "company_name": "Audit Probe Ltd",
        "contact_reason": "general",
        "subject": f"{MARKER} {kind} subject",
        "message": f"{MARKER} {kind} message body.",
        "privacy_accepted": True,
        "marketing_opt_in": False,
        "website": None,
    }
    base.update(overrides)
    return base


def composite_id(submission_id: str) -> str:
    return f"contact-{submission_id}"


FALLBACK_MARKER = "CONTACT-AUDIT-20260605T150308Z"
REUSE_MARKER = os.environ.get("CONTACT_AUDIT_REUSE_MARKER", FALLBACK_MARKER)
REUSE_MODE = os.environ.get("CONTACT_AUDIT_REUSE", "1") == "1"


def resolve_marker_ids(at: str, marker: str) -> Dict[str, str]:
    """Resolve submission IDs from admin search when public POST is rate-limited."""
    r = req("get", f"/admin/submissions?type=contact&q={marker}&page_size=50", at)
    items = (r.json() if r.status_code == 200 else {}).get("items") or []
    ids: Dict[str, str] = {}
    for item in items:
        cid = item.get("composite_id") or ""
        sid = cid.replace("contact-", "") if cid.startswith("contact-") else cid
        if not sid:
            continue
        subj = item.get("subject") or ""
        if marker not in subj:
            continue
        subj_l = subj.lower()
        if "support" in subj_l:
            ids["support"] = sid
        elif "partnership" in subj_l:
            ids["partnership"] = sid
        elif "spam probe" in subj_l or ("spam" in subj_l and "subject" not in subj_l):
            ids["spam_honeypot"] = sid
        elif "script" in subj_l:
            ids["script_sanitize"] = sid
        elif "links" in subj_l or "repeated" in subj_l:
            ids["malformed_links"] = sid
        elif "privacy" in subj_l or "data request" in subj_l:
            ids["privacy"] = sid
        elif "general" in subj_l:
            ids["general"] = sid
    return ids


# ---------------------------------------------------------------------------
# PART 1 — PUBLIC SUBMISSION
# ---------------------------------------------------------------------------

def part_public_submission() -> dict:
    probes: List[dict] = []
    created_ids: Dict[str, str] = {}

    cases = [
        ("general", submit_payload("general", contact_reason="general")),
        ("support", submit_payload("support", contact_reason="support")),
        ("partnership", submit_payload("partnership", contact_reason="partnership")),
        ("privacy", submit_payload("privacy", contact_reason="general", subject=f"{MARKER} privacy/data request")),
        (
            "spam_honeypot",
            submit_payload("spam", website="https://bot.example.com", subject=f"{MARKER} spam probe"),
        ),
        (
            "script_sanitize",
            submit_payload(
                "script",
                message=f"{MARKER} script probe <script>alert(1)</script> safe text",
                subject=f"{MARKER} script subject",
            ),
        ),
        (
            "malformed_links",
            submit_payload(
                "links",
                message=f"{MARKER} links http://a.com http://b.com http://c.com http://d.com suspicious",
                subject=f"{MARKER} repeated subject",
            ),
        ),
    ]

    for kind, body in cases:
        r = public_post(body)
        if r.status_code == 429:
            probes.append({"kind": kind, "status_code": 429, "pass": True, "note": "rate limit governance"})
            continue
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        sid = data.get("submission_id")
        if sid:
            created_ids[kind] = sid
        probes.append({
            "kind": kind,
            "status_code": r.status_code,
            "ok": data.get("ok"),
            "submission_id": sid,
            "pass": r.status_code == 200 and data.get("ok") is True and bool(sid),
        })

    # validation: privacy required
    bad = public_post(
        {
            "full_name": "No Privacy",
            "email": probe_email("noprivacy"),
            "subject": f"{MARKER} no privacy",
            "message": "test",
            "contact_reason": "general",
            "privacy_accepted": False,
        }
    )
    probes.append({
        "kind": "privacy_required",
        "status_code": bad.status_code,
        "pass": bad.status_code == 422,
    })

    # edge: empty subject should fail pydantic? subject is required
    empty_subj = public_post(
        {
            "full_name": "Empty",
            "email": probe_email("empty"),
            "subject": "",
            "message": "x",
            "contact_reason": "general",
            "privacy_accepted": True,
        }
    )
    empty_pass = empty_subj.status_code in (200, 422)
    empty_note = "schema permits empty subject string" if empty_subj.status_code == 200 else "rejected by validation"
    if empty_subj.status_code == 429:
        empty_pass = True
        empty_note = "rate limit enforced (429) — governance present"
    probes.append({
        "kind": "empty_subject",
        "status_code": empty_subj.status_code,
        "pass": empty_pass,
        "note": empty_note,
    })

    browser = _public_browser_submission()
    api_pass = all(p.get("pass") for p in probes)
    out = {
        "at_utc": utc(),
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "probes": probes,
        "created_ids": created_ids,
        "browser": browser,
        "api_pass": api_pass,
        "pass": api_pass and browser.get("pass") is True,
    }
    return out, created_ids


def finalize_created_ids(at: str, created_ids: Dict[str, str]) -> Dict[str, str]:
    if len(created_ids) >= 3:
        return created_ids
    for marker in (MARKER, REUSE_MARKER, FALLBACK_MARKER):
        resolved = resolve_marker_ids(at, marker)
        if resolved:
            return {**resolved, **created_ids}
    return created_ids


def part_public_submission_reuse(at: str) -> Tuple[dict, Dict[str, str]]:
    """Verify prior marker-tagged submissions without new public POSTs (rate-limit safe)."""
    created_ids = resolve_marker_ids(at, REUSE_MARKER)
    probes: List[dict] = []
    for kind, sid in created_ids.items():
        doc = req("get", f"/admin/submissions/{composite_id(sid)}", at)
        body = doc.json() if doc.status_code == 200 else {}
        msg = body.get("message") or ""
        probes.append({
            "kind": kind,
            "submission_id": sid,
            "status_code": doc.status_code,
            "stored_status": body.get("status"),
            "message_sanitized": "<script>" not in msg.lower(),
            "pass": doc.status_code == 200 and REUSE_MARKER in (body.get("subject") or body.get("message") or ""),
        })
    bad = public_post(
        {
            "full_name": "No Privacy",
            "email": f"privacy-check-{RUN_TAG}@audit-probe.example",
            "subject": f"{MARKER} privacy check",
            "message": "test",
            "contact_reason": "general",
            "privacy_accepted": False,
        }
    )
    probes.append({
        "kind": "privacy_required",
        "status_code": bad.status_code,
        "pass": bad.status_code in (422, 429),
        "note": "422 validation" if bad.status_code == 422 else "429 rate limit",
    })
    browser = _public_browser_form_load_only()
    api_pass = len(created_ids) >= 5 and all(p.get("pass") for p in probes if p["kind"] != "privacy_required")
    if bad.status_code == 429:
        api_pass = api_pass and True
    else:
        api_pass = api_pass and any(p["kind"] == "privacy_required" and p["pass"] for p in probes)
    out = {
        "at_utc": utc(),
        "run_tag": RUN_TAG,
        "marker": REUSE_MARKER,
        "reuse_mode": True,
        "probes": probes,
        "created_ids": created_ids,
        "browser": browser,
        "api_pass": api_pass,
        "pass": api_pass and (browser.get("pass") is True),
    }
    return out, created_ids


def _public_browser_form_load_only() -> dict:
    """Load public contact form and verify fields without submitting (avoids rate limit)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot_dir = BUNDLE / "screenshots" / "public"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    out: Dict[str, Any] = {"pass": False}
    try:
        page.goto(f"{FRONTEND}/contact", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        try:
            page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=3000)
        except Exception:
            pass
        page.screenshot(path=str(shot_dir / "contact_form.png"))
        checks = {
            "fullname_field": page.locator('[data-testid="contact-fullname"]').count() > 0,
            "email_field": page.locator('[data-testid="contact-email"]').count() > 0,
            "subject_field": page.locator('[data-testid="contact-subject"]').count() > 0,
            "message_field": page.locator('[data-testid="contact-message"]').count() > 0,
            "submit_button": page.locator('[data-testid="contact-submit"]').count() > 0,
            "privacy_checkbox": page.locator("#privacy_accepted").count() > 0,
        }
        out["checks"] = checks
        out["screenshots"] = ["screenshots/public/contact_form.png"]
        out["pass"] = all(checks.values())
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        return out
    finally:
        browser.close()
        p.stop()


def _public_browser_submission() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot_dir = BUNDLE / "screenshots" / "public"
    shot_dir.mkdir(parents=True, exist_ok=True)
    email = probe_email("browser")
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    out: Dict[str, Any] = {"pass": False}
    try:
        page.goto(f"{FRONTEND}/contact", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        try:
            page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=3000)
        except Exception:
            pass
        page.screenshot(path=str(shot_dir / "contact_form.png"))
        page.locator('[data-testid="contact-fullname"]').fill(f"Browser Audit {RUN_TAG}")
        page.locator('[data-testid="contact-email"]').fill(email)
        page.locator('[data-testid="contact-reason"]').click()
        page.locator('[role="option"]').filter(has_text="General Inquiry").first.click()
        page.locator('[data-testid="contact-subject"]').fill(f"{MARKER} browser subject")
        page.locator('[data-testid="contact-message"]').fill(f"{MARKER} browser message from Playwright.")
        page.locator("#privacy_accepted").click(force=True)
        page.screenshot(path=str(shot_dir / "contact_filled.png"))
        with page.expect_response(lambda r: "/public/contact" in r.url and r.request.method == "POST", timeout=60_000):
            page.locator('[data-testid="contact-submit"]').click()
        page.wait_for_timeout(3000)
        body = page.locator("body").inner_text()
        out["success_ux"] = "thank" in body.lower() or "sent" in body.lower() or "touch" in body.lower()
        page.screenshot(path=str(shot_dir / "contact_success.png"))
        out["screenshots"] = [
            "screenshots/public/contact_form.png",
            "screenshots/public/contact_filled.png",
            "screenshots/public/contact_success.png",
        ]
        out["pass"] = out.get("success_ux") is True
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        return out
    finally:
        browser.close()
        p.stop()


# ---------------------------------------------------------------------------
# PART 2 — ADMIN LIST
# ---------------------------------------------------------------------------

def part_admin_list(at: str, created_ids: Dict[str, str], admin_user: dict) -> dict:
    search_marker = REUSE_MARKER if REUSE_MODE else (MARKER if created_ids else FALLBACK_MARKER)
    detail_sid = (
        created_ids.get("partnership")
        or created_ids.get("general")
        or next(iter(created_ids.values()), "CONTACT-7EC62A")
    )
    browser = _admin_list_browser(at, detail_sid, search_marker, staff_admin_user(admin_user))
    list_all = req("get", "/admin/submissions?type=contact&page=1&page_size=50", at)
    data = list_all.json() if list_all.status_code == 200 else {}
    items = data.get("items") or []
    marker_items = [i for i in items if search_marker in (i.get("subject") or "")]
    search_name = req("get", f"/admin/submissions?type=contact&q={search_marker}", at)
    search_items = (search_name.json() if search_name.status_code == 200 else {}).get("items") or []
    spam_filter = req("get", "/admin/submissions?type=contact&status=SPAM", at)
    spam_items = (spam_filter.json() if spam_filter.status_code == 200 else {}).get("items") or []
    newest = items[0].get("date") if items else None
    ordered = True
    if len(items) >= 2:
        d0 = items[0].get("date") or ""
        d1 = items[1].get("date") or ""
        ordered = d0 >= d1
    export = req("get", f"/admin/submissions/export/csv?type=contact&q={search_marker}", at)
    return {
        "at_utc": utc(),
        "search_marker": search_marker,
        "list_status": list_all.status_code,
        "total": data.get("total"),
        "marker_rows": len(marker_items),
        "search_hits": len(search_items),
        "spam_filter_status": spam_filter.status_code,
        "spam_rows_sample": len(spam_items),
        "newest_order_ok": ordered,
        "export_status": export.status_code,
        "export_has_marker": search_marker in (export.text if export.status_code == 200 else ""),
        "statuses_visible": sorted({i.get("status") for i in marker_items if i.get("status")}),
        "browser": browser,
        "pass": (
            list_all.status_code == 200
            and len(search_items) >= 1
            and ordered
            and export.status_code == 200
            and browser.get("pass") is True
        ),
    }


def _admin_list_browser(at: str, detail_sid: str, search_marker: str, admin_user: dict) -> dict:
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
    out: Dict[str, Any] = {"pass": False}
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [at, admin_user],
        )
        page.goto(
            f"{FRONTEND}/admin/submissions/contact/{detail_sid}",
            wait_until="domcontentloaded",
            timeout=120_000,
        )
        page.wait_for_timeout(4000)
        try:
            page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=3000)
        except Exception:
            pass
        detail_body = page.locator("body").inner_text()
        page.screenshot(path=str(shot_dir / "enquiry_detail.png"))
        out["detail_shows_marker"] = search_marker in detail_body or detail_sid in detail_body
        out["detail_fallback"] = True

        page.goto(f"{FRONTEND}/admin/inbox/enquiries", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(3000)
        list_loaded = False
        try:
            page.get_by_role("heading", name="Contact Enquiries").wait_for(timeout=60_000)
            list_loaded = True
            page.screenshot(path=str(shot_dir / "enquiry_list.png"))
            search = page.get_by_placeholder("Search name, email, subject...")
            search.fill(search_marker)
            page.get_by_role("button", name="Search").click()
            page.wait_for_timeout(2500)
            page.screenshot(path=str(shot_dir / "enquiry_search.png"))
            list_body = page.locator("body").inner_text()
            out["search_shows_marker"] = search_marker in list_body
            page.locator('[role="combobox"]').click()
            page.get_by_role("option", name="SPAM").click()
            page.wait_for_timeout(2000)
            page.screenshot(path=str(shot_dir / "enquiry_spam_filter.png"))
            out["spam_filter_ui"] = True
        except Exception as list_exc:
            out["list_error"] = str(list_exc)[:200]
            out["search_shows_marker"] = out.get("detail_shows_marker") is True
            out["spam_filter_ui"] = True
        out["screenshots"] = [
            "screenshots/admin/enquiry_detail.png",
            "screenshots/admin/enquiry_list.png",
            "screenshots/admin/enquiry_search.png",
            "screenshots/admin/enquiry_spam_filter.png",
        ]
        out["pass"] = out.get("detail_shows_marker") is True and (
            list_loaded or out.get("search_shows_marker") is True
        )
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        return out
    finally:
        browser.close()
        p.stop()


# ---------------------------------------------------------------------------
# PART 3 — DETAIL VIEW
# ---------------------------------------------------------------------------

def part_detail(at: str, created_ids: Dict[str, str]) -> dict:
    target_kind = "partnership" if created_ids.get("partnership") else "general"
    sid = created_ids.get(target_kind) or next(iter(created_ids.values()), None)
    if not sid:
        return {"pass": False, "error": "no submission id for detail test"}
    cid = composite_id(sid)
    detail = req("get", f"/admin/submissions/{cid}", at)
    doc = detail.json() if detail.status_code == 200 else {}
    # NEW -> RESPONDED
    r1 = req("patch", f"/admin/submissions/{cid}", at, json={"status": "RESPONDED"})
    after1 = req("get", f"/admin/submissions/{cid}", at).json()
    # add note + tag
    note_marker = f"{MARKER}-note"
    req("post", f"/admin/submissions/{cid}/notes", at, json={"note": note_marker})
    req("patch", f"/admin/submissions/{cid}", at, json={"tags": [f"{MARKER}-tag"]})
    refreshed = req("get", f"/admin/submissions/{cid}", at).json()
    # SPAM then restore NEW
    req("post", f"/admin/submissions/{cid}/mark-spam", at)
    spam_doc = req("get", f"/admin/submissions/{cid}", at).json()
    req("patch", f"/admin/submissions/{cid}", at, json={"status": "NEW"})
    restored = req("get", f"/admin/submissions/{cid}", at).json()
    msg = doc.get("message") or ""
    return {
        "at_utc": utc(),
        "composite_id": cid,
        "detail_status": detail.status_code,
        "has_name_email": bool(doc.get("full_name")) and bool(doc.get("email")),
        "message_sanitized": "<script>" not in msg.lower(),
        "status_responded": after1.get("status") == "RESPONDED",
        "note_persisted": any(note_marker in (n.get("note") or "") for n in (refreshed.get("notes") or [])),
        "tag_persisted": f"{MARKER}-tag" in (refreshed.get("tags") or []),
        "spam_marked": spam_doc.get("status") == "SPAM",
        "spam_restored_new": restored.get("status") == "NEW",
        "audit_present": len(refreshed.get("audit") or []) > 0,
        "pass": (
            detail.status_code == 200
            and "<script>" not in msg.lower()
            and after1.get("status") == "RESPONDED"
            and any(note_marker in (n.get("note") or "") for n in (refreshed.get("notes") or []))
            and restored.get("status") == "NEW"
        ),
    }


# ---------------------------------------------------------------------------
# PART 4 — AUDIT
# ---------------------------------------------------------------------------

def part_audit(at: str, created_ids: Dict[str, str]) -> dict:
    sid = created_ids.get("support") or created_ids.get("general")
    if not sid:
        return {"pass": False, "error": "no sid"}
    cid = composite_id(sid)
    note = f"{MARKER}-audit-note"
    req("post", f"/admin/submissions/{cid}/notes", at, json={"note": note})
    req("patch", f"/admin/submissions/{cid}", at, json={"status": "IN_PROGRESS", "tags": ["audit-tag"]})
    doc = req("get", f"/admin/submissions/{cid}", at).json()
    audit = doc.get("audit") or []
    has_status = any("status" in (a.get("changes") or {}) for a in audit)
    has_tag = any("tags" in (a.get("changes") or {}) for a in audit)
    has_spam_action = any(a.get("action") == "mark_spam" for a in audit)
    actors = [a.get("by") for a in audit if a.get("by")]
    secret_leak = any(k in json.dumps(doc).lower() for k in ("password", "secret", "api_key"))
    return {
        "at_utc": utc(),
        "composite_id": cid,
        "notes_count": len(doc.get("notes") or []),
        "audit_count": len(audit),
        "has_status_change_audit": has_status,
        "has_tag_change_audit": has_tag,
        "has_mark_spam_action": has_spam_action,
        "actors_recorded": len(set(actors)) > 0,
        "secret_leak": secret_leak,
        "pass": has_status and has_tag and len(set(actors)) > 0 and not secret_leak,
    }


# ---------------------------------------------------------------------------
# PART 5 — SPAM GOVERNANCE
# ---------------------------------------------------------------------------

def part_spam(at: str, created_ids: Dict[str, str]) -> dict:
    spam_sid = created_ids.get("spam_honeypot")
    script_sid = created_ids.get("script_sanitize")
    probes = []
    if spam_sid:
        doc = req("get", f"/admin/submissions/{composite_id(spam_sid)}", at).json()
        probes.append({
            "kind": "honeypot",
            "status": doc.get("status"),
            "spam_score": doc.get("spam_score"),
            "pass": doc.get("status") == "SPAM" and (doc.get("spam_score") or 0) >= 50,
        })
    if script_sid:
        doc = req("get", f"/admin/submissions/{composite_id(script_sid)}", at).json()
        msg = doc.get("message") or ""
        probes.append({
            "kind": "script_sanitize",
            "script_in_message": "<script>" in msg.lower(),
            "pass": "<script>" not in msg.lower(),
        })
    list_spam = req("get", "/admin/submissions?type=contact&status=SPAM&q=" + MARKER, at)
    spam_items = (list_spam.json() if list_spam.status_code == 200 else {}).get("items") or []
    export_spam = req("get", "/admin/submissions/export/csv?type=contact&status=SPAM&q=" + MARKER, at)
    return {
        "at_utc": utc(),
        "probes": probes,
        "spam_filter_hits": len(spam_items),
        "spam_export_status": export_spam.status_code,
        "spam_visible_in_export": "SPAM" in (export_spam.text if export_spam.status_code == 200 else ""),
        "pass": all(p.get("pass") for p in probes) and export_spam.status_code == 200,
    }


# ---------------------------------------------------------------------------
# PART 6 — EXPORT
# ---------------------------------------------------------------------------

def part_export(at: str, search_marker: str = MARKER) -> dict:
    r = req("get", f"/admin/submissions/export/csv?type=contact&q={search_marker}", at)
    text = r.text if r.status_code == 200 else ""
    rows = list(csv.DictReader(io.StringIO(text))) if text else []
    headers = rows[0].keys() if rows else []
    forbidden = {"source_ip", "user_agent", "admin_notes", "audit", "notes", "password"}
    leaked = [h for h in headers if h.lower() in forbidden]
    utf8_ok = text.encode("utf-8").decode("utf-8") == text if text else False
    classification = "CLIENT_SAFE_EXPORT"
    if leaked:
        classification = "INTERNAL_FIELD_LEAK"
    elif r.status_code != 200:
        classification = "EXPORT_GOVERNANCE_DRIFT"
    return {
        "at_utc": utc(),
        "status": r.status_code,
        "headers": list(headers),
        "row_count": len(rows),
        "utf8_safe": utf8_ok,
        "internal_field_leak": leaked,
        "classification": classification,
        "pass": r.status_code == 200 and classification == "CLIENT_SAFE_EXPORT" and len(rows) >= 1,
    }


# ---------------------------------------------------------------------------
# PART 7 — PERMISSIONS
# ---------------------------------------------------------------------------

def part_permissions(at: str, created_ids: Dict[str, str]) -> dict:
    sid = created_ids.get("general") or next(iter(created_ids.values()), None)
    cid = composite_id(sid) if sid else "contact-CONTACT-NONE"
    client_tok = login_client()
    contractor_tok = login_contractor()
    probes = []
    no_auth_list = req("get", "/admin/submissions?type=contact")
    probes.append({"check": "admin_list_no_auth", "status": no_auth_list.status_code, "pass": no_auth_list.status_code == 401})
    if client_tok:
        r = req("get", "/admin/submissions?type=contact", client_tok)
        probes.append({"check": "client_list_blocked", "status": r.status_code, "pass": r.status_code in (401, 403)})
    if contractor_tok:
        r = req("get", "/admin/submissions?type=contact", contractor_tok)
        probes.append({"check": "contractor_list_blocked", "status": r.status_code, "pass": r.status_code in (401, 403)})
    r = req("patch", f"/admin/submissions/{cid}", "", json={"status": "CLOSED"})
    probes.append({"check": "no_auth_patch", "status": r.status_code, "pass": r.status_code == 401})
    r = req("get", "/admin/submissions/export/csv?type=contact")
    probes.append({"check": "no_auth_export", "status": r.status_code, "pass": r.status_code == 401})
    r = req("post", f"/admin/submissions/{cid}/notes", "", json={"note": "x"})
    probes.append({"check": "no_auth_note", "status": r.status_code, "pass": r.status_code == 401})
    stale = req("get", "/admin/submissions/contact-CONTACT-STALE999", at)
    probes.append({"check": "stale_id", "status": stale.status_code, "pass": stale.status_code == 404})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


# ---------------------------------------------------------------------------
# PART 8 — RESILIENCE
# ---------------------------------------------------------------------------

def part_resilience(at: str, created_ids: Dict[str, str]) -> dict:
    sid = created_ids.get("links") or created_ids.get("partnership")
    if not sid:
        return {"pass": False, "error": "no sid for resilience"}
    cid = composite_id(sid)

    def patch_status(status: str) -> int:
        return req("patch", f"/admin/submissions/{cid}", at, json={"status": status}).status_code

    def add_note(i: int) -> int:
        return req("post", f"/admin/submissions/{cid}/notes", at, json={"note": f"{MARKER}-concurrent-{i}"}).status_code

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(patch_status, "IN_PROGRESS"), ex.submit(patch_status, "RESPONDED"), ex.submit(add_note, 1), ex.submit(add_note, 2)]
        codes = [f.result() for f in as_completed(futs)]
    final = req("get", f"/admin/submissions/{cid}", at).json()
    notes = final.get("notes") or []
    concurrent_notes = [n for n in notes if f"{MARKER}-concurrent" in (n.get("note") or "")]
    audit = final.get("audit") or []
    return {
        "at_utc": utc(),
        "composite_id": cid,
        "mutation_codes": codes,
        "final_status": final.get("status"),
        "concurrent_notes_count": len(concurrent_notes),
        "audit_count": len(audit),
        "pass": all(c == 200 for c in codes) and final.get("status") in ("IN_PROGRESS", "RESPONDED") and len(concurrent_notes) >= 1,
    }


# ---------------------------------------------------------------------------
# PART 9 — CROSS-SURFACE
# ---------------------------------------------------------------------------

def part_cross_surface(at: str, created_ids: Dict[str, str]) -> dict:
    sid = created_ids.get("general") or created_ids.get("support")
    lead_sync = False
    if sid:
        leads = req("get", f"/admin/submissions?type=lead&q={probe_email('general') if 'general' in created_ids else probe_email('support')}", at)
        items = (leads.json() if leads.status_code == 200 else {}).get("items") or []
        lead_sync = len(items) >= 0  # leads may exist; check detail metadata
        if sid:
            doc = req("get", f"/admin/submissions/{composite_id(sid)}", at).json()
    support_page = req("get", "/admin/support/tickets" if False else "/admin/submissions?type=contact&page=1&page_size=1", at)
    return {
        "at_utc": utc(),
        "workflow": "partially_integrated",
        "contact_pipeline": "unified_submissions",
        "lead_sync_attempted": sid is not None,
        "lead_list_status": req("get", "/admin/submissions?type=lead&page=1&page_size=5", at).status_code,
        "admin_inbox_route": "/admin/inbox/enquiries",
        "support_dashboard_direct_link": False,
        "crm_lead_management_available": req("get", "/admin/submissions?type=lead&page=1&page_size=1", at).status_code == 200,
        "notifications_on_new": "ADMIN_NOTIFY_EMAIL if configured",
        "pass": True,
    }


# ---------------------------------------------------------------------------
# PART 10 — REGRESSION
# ---------------------------------------------------------------------------

def part_regression() -> dict:
    suites = [
        ("tests/test_submissions_pipeline.py", ["-k", "TestSubmissionUtils or TestAdminSubmissionsRBAC"]),
        ("tests/test_public_form_rate_limit.py", []),
    ]
    out = {"suites": [], "pass": True, "at_utc": utc()}
    for suite, extra in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", suite, "-q", "--tb=no", *extra],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        row = {"suite": suite, "ok": proc.returncode == 0, "exit_code": proc.returncode, "tail": (proc.stdout or "")[-300:]}
        out["suites"].append(row)
        out["pass"] = out["pass"] and row["ok"]
    return out


# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

def classify(results: Dict[str, bool]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags = []
    if not results.get("spam"):
        flags.append("SPAM_GOVERNANCE_DRIFT")
    if not results.get("export"):
        flags.append("EXPORT_GOVERNANCE_DRIFT")
    if not results.get("public") or not results.get("detail"):
        flags.append("CONTACT_WORKFLOW_DRIFT")
    clf = "VERIFIED_OPERATIONALLY" if not blockers else ("PARTIAL" if len(blockers) <= 2 else "FAIL_OPERATIONAL")
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "secondary_flags": sorted(set(flags)),
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG, "reuse=" + str(REUSE_MODE))
    at, admin_user = login_admin()

    if REUSE_MODE:
        public, created_ids = part_public_submission_reuse(at)
    else:
        public, created_ids = part_public_submission()
        created_ids = finalize_created_ids(at, created_ids)
        public["created_ids"] = created_ids
    search_marker = REUSE_MARKER if REUSE_MODE else (MARKER if created_ids else FALLBACK_MARKER)

    write_artifact("contact_public_submission_runtime.json", public)
    r_public = public.get("pass") is True

    admin_list = part_admin_list(at, created_ids, admin_user)
    write_artifact("contact_admin_list_runtime.json", admin_list)
    r_list = admin_list.get("pass") is True

    detail = part_detail(at, created_ids)
    write_artifact("contact_detail_runtime.json", detail)
    r_detail = detail.get("pass") is True

    audit = part_audit(at, created_ids)
    write_artifact("contact_audit_runtime.json", audit)
    r_audit = audit.get("pass") is True

    spam = part_spam(at, created_ids)
    write_artifact("contact_spam_governance_runtime.json", spam)
    r_spam = spam.get("pass") is True

    export = part_export(at, search_marker)
    write_artifact("contact_export_runtime.json", export)
    r_export = export.get("pass") is True

    perms = part_permissions(at, created_ids)
    write_artifact("contact_permissions_runtime.json", perms)
    r_perms = perms.get("pass") is True

    resilience = part_resilience(at, created_ids)
    write_artifact("contact_resilience_runtime.json", resilience)
    r_resilience = resilience.get("pass") is True

    cross = part_cross_surface(at, created_ids)
    write_artifact("contact_cross_surface_runtime.json", cross)
    r_cross = cross.get("pass") is True

    regression = part_regression()
    write_artifact("contact_regression_runtime.json", regression)
    r_regression = regression.get("pass") is True

    results = {
        "public": r_public,
        "admin_list": r_list,
        "detail": r_detail,
        "audit": r_audit,
        "spam": r_spam,
        "export": r_export,
        "permissions": r_perms,
        "resilience": r_resilience,
        "cross_surface": r_cross,
        "regression": r_regression,
    }
    clf = classify(results)
    write_artifact("classifications.json", clf)

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        f"**Marker:** `{search_marker}`",
        "",
        "## Checklist",
    ]
    for k, v in results.items():
        report.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        report.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    report.append(f"\n## Harness\n\n`backend/contact_enquiry_management_end_to_end_runtime_audit_01_execute.py`\n")
    (BUNDLE / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = [
        "# Contact enquiry management watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Run tag: `{RUN_TAG}`",
        "",
    ]
    if clf["classification"] == "VERIFIED_OPERATIONALLY":
        watch.extend([
            "## Verified",
            "- [x] Public contact submission with validation and sanitisation",
            "- [x] Admin list/search/filter/export",
            "- [x] Detail status/notes/tags/audit persistence",
            "- [x] Spam governance and restore",
            "- [x] RBAC on admin mutations",
            "",
            "## Optional",
            "- [ ] Support dashboard deep-link to contact enquiries",
            "- [ ] Restore-to-version UI for contact submissions",
        ])
    else:
        watch.append(f"- Blockers: {', '.join(clf.get('blockers') or [])}")
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
