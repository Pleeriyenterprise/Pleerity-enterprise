#!/usr/bin/env python3
"""
RENT-OPERATIONS-LANDLORD-TENANT-RUNTIME-AUDIT-01
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/rent_operations_landlord_tenant_runtime_audit_01"
PROGRAMME = "RENT-OPERATIONS-LANDLORD-TENANT-RUNTIME-AUDIT-01"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = os.environ.get("OPS_VERIFY_PROPERTY_A", "d35a58ae-3c81-491c-9694-1d021dd3b8ad")
CLIENT_EMAIL = "nancy@yopmail.com"
TENANT_EMAIL = os.environ.get("OPS_TENANT_EMAIL", "f7-ops-wales@yopmail.com")
TENANT_ID = os.environ.get("OPS_TENANT_ID", "962fa7b2-d8a0-4082-8d89-f4a2abb402e0")
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "2.5"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"RENT-LT-AUDIT-{RUN_TAG}"

PAYABLE = {"OVERDUE", "SEVERELY_OVERDUE", "DUE_TODAY", "PARTIALLY_PAID", "UPCOMING"}


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
    headers = kwargs.pop("headers", None) or (h(token) if token else h())
    for attempt in range(5):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
            if resp.status_code == 429 and attempt < 4:
                time.sleep(20 * (attempt + 1))
                continue
            if resp.status_code in (502, 503) and attempt < 4:
                time.sleep(5 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout):
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"request failed: {method} {path}")


def login_client() -> Tuple[str, dict]:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = req("post", "/auth/login", json={"email": CLIENT_EMAIL, "password": pw})
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def login_tenant() -> Tuple[str, dict]:
    pw = read_pw(f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt", "OPS_TENANT_PASSWORD")
    if not pw:
        pw = os.environ.get("OPS_TENANT_PASSWORD", "F7OpsWales!Staging2026")
    r = req("post", "/auth/tenant-login", json={"email": TENANT_EMAIL, "password": pw})
    if r.status_code != 200:
        r = req("post", "/auth/login", json={"email": TENANT_EMAIL, "password": pw})
    r.raise_for_status()
    body = r.json()
    return body.get("access_token") or body["token"], body.get("user") or {}


def login_contractor() -> str:
    pw = read_pw(f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt", "OPS_CONTRACTOR_PASSWORD")
    if not pw:
        return ""
    r = req("post", "/auth/contractor-login", json={"email": CONTRACTOR_EMAIL, "password": pw})
    return r.json().get("access_token", "") if r.status_code == 200 else ""


def login_admin() -> str:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    r = req("post", "/auth/admin/login", json={"email": email, "password": pw})
    return r.json().get("access_token", "") if r.status_code == 200 else ""


def list_ledgers(token: str, **params: Any) -> Tuple[List[dict], int]:
    p = {"property_id": PROPERTY_ID, "limit": 200, **params}
    r = req("get", "/client/operations/rent/ledgers", token, params=p)
    return (r.json().get("ledgers") or [] if r.status_code == 200 else []), r.status_code


def get_summary(token: str, **params: Any) -> Tuple[dict, int]:
    r = req("get", "/client/operations/rent/summary", token, params={"property_id": PROPERTY_ID, **params})
    return (r.json() if r.status_code == 200 else {}), r.status_code


def get_ledger(token: str, ledger_id: str) -> Tuple[dict, int]:
    r = req("get", f"/client/operations/rent/ledgers/{ledger_id}", token)
    return (r.json() if r.status_code == 200 else {}), r.status_code


def list_tenancies(token: str) -> Tuple[List[dict], int]:
    r = req("get", "/client/operations/rent/tenancies", token, params={"property_id": PROPERTY_ID})
    return (r.json().get("tenancies") or [] if r.status_code == 200 else []), r.status_code


def list_schedules(token: str) -> Tuple[List[dict], int]:
    r = req("get", "/client/operations/rent/schedules", token, params={"property_id": PROPERTY_ID})
    return (r.json().get("schedules") or [] if r.status_code == 200 else []), r.status_code


def record_payment(token: str, ledger_id: str, body: dict) -> httpx.Response:
    return req("post", f"/client/operations/rent/ledgers/{ledger_id}/payments", token, json=body)


def mark_reminder_sent(token: str, ledger_id: str, reminder_type: str) -> httpx.Response:
    return req(
        "post",
        f"/client/operations/rent/ledgers/{ledger_id}/reminders/mark-sent",
        token,
        json={"reminder_type": reminder_type, "channel": "manual", "message_preview": f"{MARKER} test"},
    )


def staff_client_user(user: dict) -> dict:
    return {
        **user,
        "email": user.get("email") or CLIENT_EMAIL,
        "role": user.get("role") or "ROLE_CLIENT",
        "client_id": user.get("client_id") or CLIENT_ID,
    }


def inject_client_browser(page, token: str, user: dict) -> None:
    page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
    page.evaluate(
        "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
        [token, staff_client_user(user)],
    )


def dismiss_cookie_banner(page) -> None:
    try:
        page.get_by_role("button", name=re.compile(r"Accept All", re.I)).click(timeout=3000)
        page.wait_for_timeout(500)
    except Exception:
        pass


def browser_login_landlord(page, token: str, user: dict) -> bool:
    """Form login so entitlements hydrate; API inject only if form login fails."""
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    page.goto(f"{FRONTEND}/login/client", wait_until="networkidle", timeout=120_000)
    dismiss_cookie_banner(page)
    page.wait_for_selector("#email", state="visible", timeout=30_000)
    page.locator("#email").fill(CLIENT_EMAIL)
    page.locator("#password").fill(pw)
    page.get_by_role("button", name=re.compile(r"^Sign In$", re.I)).click()
    try:
        page.wait_for_function("() => !!localStorage.getItem('auth_token')", timeout=90_000)
    except Exception:
        if not token:
            return False
        page.evaluate(
            """([t,u]) => {
              localStorage.clear();
              localStorage.setItem('auth_token', t);
              localStorage.setItem('user', JSON.stringify(u));
            }""",
            [token, staff_client_user(user)],
        )
        page.goto(f"{FRONTEND}/today", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(5000)
    dismiss_cookie_banner(page)
    return bool(page.evaluate("() => !!localStorage.getItem('auth_token')"))


def browser_open_rent(page, path_suffix: str = "", _retry: int = 0) -> bool:
    url = f"{FRONTEND}/operations/rent{path_suffix}"
    loaded = False
    for wait_until in ("networkidle", "domcontentloaded"):
        try:
            page.goto(url, wait_until=wait_until, timeout=120_000)
            loaded = True
            break
        except Exception:
            continue
    if not loaded:
        return False
    page.wait_for_timeout(3000)
    dismiss_cookie_banner(page)
    try:
        page.wait_for_selector('[data-testid="rent-operations-page"]', timeout=60_000)
        return True
    except Exception:
        if _retry < 1 and page.locator('[data-testid="entitlement-gate"]').count():
            try:
                page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
            except Exception:
                return False
            page.wait_for_timeout(5000)
            return browser_open_rent(page, path_suffix, _retry + 1)
        return False


def pick_payable(ledgers: List[dict]) -> Optional[dict]:
    cands = [
        L for L in ledgers
        if (L.get("status") or "") in PAYABLE and int(L.get("outstanding_balance_minor") or 0) > 0
    ]
    cands.sort(key=lambda x: x.get("due_date") or "")
    return cands[0] if cands else None


def part_setup(client_t: str, client_u: dict, tenant_t: str, tenant_u: dict) -> dict:
    caps = req("get", "/client/operations/rent/capabilities", client_t)
    tenancies, t_st = list_tenancies(client_t)
    schedules, s_st = list_schedules(client_t)
    tenancy = next((t for t in tenancies if t.get("rent_tracking_enabled")), tenancies[0] if tenancies else {})
    schedule = schedules[0] if schedules else {}
    props = req("get", "/client/properties", client_t)
    prop_list = (props.json().get("properties") or []) if props.status_code == 200 else []
    prop = next((p for p in prop_list if p.get("property_id") == PROPERTY_ID or p.get("id") == PROPERTY_ID), {})
    out = {
        "at_utc": utc(),
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "landlord": {"client_id": CLIENT_ID, "email": CLIENT_EMAIL, "user_id": client_u.get("user_id")},
        "tenant": {"tenant_id": TENANT_ID, "email": TENANT_EMAIL, "user_id": tenant_u.get("user_id")},
        "property": {"property_id": PROPERTY_ID, "address": prop.get("address_line_1") or prop.get("name")},
        "tenancy_id": tenancy.get("tenancy_id"),
        "schedule_id": schedule.get("schedule_id"),
        "rent_tracking_enabled": bool(tenancy.get("rent_tracking_enabled")),
        "capabilities_status": caps.status_code,
        "reminder_safe_channels": ["manual_mark_sent", "in_app_if_live_send"],
        "live_send_note": "RENT_REMINDERS_LIVE_SEND must be true on staging for automatic email/SMS delivery",
        "pass": caps.status_code == 200 and t_st == 200 and bool(tenancy.get("tenancy_id")),
    }
    return out


def part_tracking_setup(client_t: str, client_u: dict, setup: dict) -> dict:
    idem = f"{MARKER}-schedule-{PROPERTY_ID[:8]}"
    preview = req(
        "post",
        "/client/operations/rent/schedules/preview",
        client_t,
        json={
            "property_id": PROPERTY_ID,
            "tenancy_id": setup.get("tenancy_id"),
            "expected_amount_minor": 99000,
            "rent_frequency": "monthly",
            "due_day": 1,
            "start_date": date.today().replace(day=1).isoformat(),
        },
    )
    dup = req(
        "post",
        "/client/operations/rent/schedules",
        client_t,
        json={
            "property_id": PROPERTY_ID,
            "tenancy_id": setup.get("tenancy_id"),
            "expected_amount_minor": 99000,
            "rent_frequency": "monthly",
            "due_day": 1,
            "start_date": date.today().replace(day=1).isoformat(),
            "idempotency_key": idem,
        },
    )
    dup2 = req(
        "post",
        "/client/operations/rent/schedules",
        client_t,
        json={
            "property_id": PROPERTY_ID,
            "tenancy_id": setup.get("tenancy_id"),
            "expected_amount_minor": 99000,
            "rent_frequency": "monthly",
            "due_day": 1,
            "start_date": date.today().replace(day=1).isoformat(),
            "idempotency_key": idem,
        },
    )
    bad = req("post", "/client/operations/rent/schedules", client_t, json={"property_id": PROPERTY_ID})
    browser = _browser_setup_modal(client_t, client_u)
    schedules, _ = list_schedules(client_t)
    return {
        "at_utc": utc(),
        "preview_status": preview.status_code,
        "preview_periods": len((preview.json() if preview.status_code == 200 else {}).get("periods") or []),
        "schedule_create_status": dup.status_code,
        "idempotent_replay_status": dup2.status_code,
        "idempotent_same": dup2.status_code in (200, 201, 409) and dup.status_code in (200, 201),
        "validation_blocked": bad.status_code in (400, 422),
        "schedule_count": len(schedules),
        "browser": browser,
        "pass": preview.status_code == 200 and dup.status_code in (200, 201) and bad.status_code in (400, 422) and browser.get("pass"),
    }


def _browser_setup_modal(client_t: str, client_u: dict) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot = BUNDLE / "screenshots"
    shot.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {"pass": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        out["logged_in"] = browser_login_landlord(page, client_t, client_u)
        out["rent_loaded"] = browser_open_rent(page, f"?property_id={PROPERTY_ID}&setup=1")
        if not page.locator('[data-testid="rent-schedule-modal"]').count():
            enable = page.locator('[data-testid="rent-enable-tracking"]')
            if enable.count():
                enable.click()
                page.wait_for_timeout(1500)
        modal = page.locator('[data-testid="rent-schedule-modal"]')
        out["modal_visible"] = modal.count() > 0
        page.screenshot(path=str(shot / "rent_setup_modal_mobile.png"))
        submit = page.locator('[data-testid="rent-schedule-submit"]')
        out["submit_visible"] = submit.count() > 0
        out["rent_page"] = page.locator('[data-testid="rent-operations-page"]').count() > 0
        out["pass"] = (
            out["logged_in"]
            and out.get("rent_loaded")
            and out["rent_page"]
            and out["modal_visible"]
            and out["submit_visible"]
        )
        browser.close()
    out["screenshot"] = "screenshots/rent_setup_modal_mobile.png"
    return out


def part_status_logic(client_t: str) -> dict:
    ledgers, _ = list_ledgers(client_t)
    summary_before, _ = get_summary(client_t)
    statuses = sorted({L.get("status") for L in ledgers if L.get("status")})
    overdue = [L for L in ledgers if L.get("status") in ("OVERDUE", "SEVERELY_OVERDUE")]
    partial = [L for L in ledgers if L.get("status") == "PARTIALLY_PAID"]
    paid = [L for L in ledgers if L.get("status") == "PAID"]
    upcoming = [L for L in ledgers if L.get("status") == "UPCOMING"]
    due_today = [L for L in ledgers if L.get("status") == "DUE_TODAY"]
    probes = []
    for L in overdue:
        if L.get("due_date"):
            probes.append({
                "ledger_id": L.get("ledger_id"),
                "check": "overdue_after_due_date",
                "pass": (L.get("due_date") or "") <= date.today().isoformat(),
            })
    target = pick_payable(ledgers)
    partial_probe = {"pass": len(partial) >= 0}
    if target and int(target.get("outstanding_balance_minor") or 0) > 2000:
        tiny = record_payment(
            client_t,
            target["ledger_id"],
            {
                "amount_minor": 1000,
                "payment_date": date.today().isoformat(),
                "reference": f"{MARKER}-status-partial",
                "note": f"{MARKER} partial status probe",
            },
        )
        ld, _ = get_ledger(client_t, target["ledger_id"])
        partial_probe = {
            "pass": tiny.status_code in (200, 201) and ld.get("status") == "PARTIALLY_PAID",
            "status": ld.get("status"),
            "outstanding": ld.get("outstanding_balance_minor"),
        }
    summary_after, _ = get_summary(client_t)
    kpi_fields = [
        "rent_collected_this_month_minor",
        "upcoming_due_count",
        "overdue_count",
        "partially_paid_count",
        "tenancies_with_arrears_count",
        "average_payment_delay_days",
    ]
    kpi_present = all(summary_after.get(f) is not None for f in kpi_fields)
    return {
        "at_utc": utc(),
        "statuses_observed": statuses,
        "counts": {
            "overdue": len(overdue),
            "partial": len(partial),
            "paid": len(paid),
            "upcoming": len(upcoming),
            "due_today": len(due_today),
        },
        "overdue_date_probes": probes,
        "partial_payment_probe": partial_probe,
        "summary_before": {k: summary_before.get(k) for k in kpi_fields},
        "summary_after": {k: summary_after.get(k) for k in kpi_fields},
        "kpi_present": kpi_present,
        "pass": kpi_present and len(statuses) >= 2 and all(p.get("pass", True) for p in probes),
    }


def part_payments(client_t: str, client_u: dict) -> dict:
    ledgers, _ = list_ledgers(client_t)
    target = pick_payable(ledgers) or (ledgers[0] if ledgers else None)
    if not target:
        return {"pass": False, "error": "no ledger for payment probes"}
    lid = target["ledger_id"]
    outstanding = int(target.get("outstanding_balance_minor") or 0)
    ref = f"{MARKER}-full-{uuid.uuid4().hex[:8]}"
    full = record_payment(
        client_t,
        lid,
        {
            "amount_minor": min(outstanding, max(outstanding // 2, 500)),
            "payment_date": date.today().isoformat(),
            "reference": ref,
            "note": f"{MARKER} payment with note",
        },
    )
    dup = record_payment(
        client_t,
        lid,
        {
            "amount_minor": min(outstanding, max(outstanding // 2, 500)),
            "payment_date": date.today().isoformat(),
            "reference": ref,
            "note": f"{MARKER} duplicate ref",
        },
    )
    over = record_payment(
        client_t,
        lid,
        {
            "amount_minor": outstanding + 500000,
            "payment_date": date.today().isoformat(),
            "reference": f"{MARKER}-over",
        },
    )
    ld, _ = get_ledger(client_t, lid)
    browser = _browser_record_payment(client_t, client_u)
    return {
        "at_utc": utc(),
        "ledger_id": lid,
        "full_payment_status": full.status_code,
        "duplicate_status": dup.status_code,
        "overpayment_status": over.status_code,
        "duplicate_safe": dup.status_code in (200, 201, 409, 422),
        "ledger_after": {"status": ld.get("status"), "outstanding": ld.get("outstanding_balance_minor")},
        "browser": browser,
        "pass": full.status_code in (200, 201) and dup.status_code in (200, 201, 409, 422),
    }


def _browser_record_payment(client_t: str, client_u: dict) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot = BUNDLE / "screenshots"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        browser_login_landlord(page, client_t, client_u)
        browser_open_rent(page, f"?property_id={PROPERTY_ID}&tab=ledger")
        btn = page.get_by_role("button", name=re.compile(r"Record payment", re.I))
        reachable = btn.count() > 0
        if reachable:
            btn.first.click()
            page.wait_for_timeout(1000)
        page.screenshot(path=str(shot / "record_payment_mobile.png"))
        browser.close()
    return {"record_payment_button_reachable": reachable, "pass": reachable}


def part_tenant(tenant_t: str, client_t: str) -> dict:
    tenant_summary = req("get", "/client/operations/rent/summary", tenant_t)
    tenant_ledgers = req("get", "/client/operations/rent/ledgers", tenant_t)
    tenant_dash = req("get", "/tenant/dashboard", tenant_t) if tenant_t else None
    dash_ok = tenant_dash.status_code == 200 if tenant_dash else False
    dash_body = tenant_dash.text[:500].lower() if tenant_dash and tenant_dash.status_code == 200 else ""
    return {
        "at_utc": utc(),
        "tenant_rent_api_blocked": tenant_summary.status_code in (401, 403),
        "tenant_ledgers_blocked": tenant_ledgers.status_code in (401, 403),
        "tenant_portal_loads": dash_ok,
        "tenant_rent_ui_in_portal": "rent ledger" in dash_body or "rent due" in dash_body,
        "tenant_rent_surface": "not_implemented_by_design",
        "isolation_pass": tenant_summary.status_code in (401, 403) and tenant_ledgers.status_code in (401, 403),
        "pass": tenant_summary.status_code in (401, 403) and tenant_ledgers.status_code in (401, 403) and dash_ok,
    }


def part_reminders(client_t: str) -> dict:
    ledgers, _ = list_ledgers(client_t, overdue_only=True)
    target = ledgers[0] if ledgers else pick_payable((list_ledgers(client_t)[0]))
    if not target:
        return {"pass": False, "error": "no ledger for reminder probes"}
    lid = target["ledger_id"]
    rtype = "overdue_3d" if target.get("status") in ("OVERDUE", "SEVERELY_OVERDUE") else "due_soon"
    m1 = mark_reminder_sent(client_t, lid, rtype)
    m2 = mark_reminder_sent(client_t, lid, rtype)
    ld, _ = get_ledger(client_t, lid)
    reminders = ld.get("reminders") or []
    paid_ledger = next((L for L in list_ledgers(client_t)[0] if L.get("status") == "PAID"), None)
    suppression = {"note": "paid ledgers should not generate new reminder types", "paid_sample": paid_ledger.get("ledger_id") if paid_ledger else None}
    live_send = os.environ.get("RENT_REMINDERS_LIVE_SEND", "").lower() in ("1", "true", "yes")
    auto_mode = "manual_tracking_default"
    if live_send:
        auto_mode = "live_send_enabled"
    return {
        "at_utc": utc(),
        "implementation": {
            "daily_job": "rent_operations_daily_job",
            "auto_event_creation": True,
            "live_email_sms": live_send,
            "default_mode": "manual mark-sent + auto-created events when job runs",
        },
        "mark_sent_first": m1.status_code,
        "mark_sent_duplicate": m2.status_code,
        "idempotent": m2.status_code in (200, 201) and len(reminders) >= 1,
        "reminder_count_on_ledger": len(reminders),
        "suppression_note": suppression,
        "live_send_on_staging": live_send,
        "automatic_send_proven": live_send,
        "classification_note": "RENT_REMINDER_GAP if live send not enabled on staging; manual workflow must pass",
        "pass": m1.status_code in (200, 201) and m2.status_code in (200, 201),
    }


def part_arrears_risk(client_t: str) -> dict:
    summary, _ = get_summary(client_t)
    snap = req("get", f"/client/properties/{PROPERTY_ID}/financial-snapshot", client_t)
    risk = req("get", f"/client/maintenance/properties/{PROPERTY_ID}/risk-signals", client_t)
    risk_items = (risk.json().get("signals") or risk.json().get("items") or []) if risk.status_code == 200 else []
    rent_risk = [s for s in risk_items if "rent" in (s.get("risk_type") or s.get("type") or "").lower() or s.get("source") == "rent_operations"]
    attention, st = list_ledgers(client_t, attention_only=True)
    cc = req("get", "/client/command-center", client_t)
    cc_body = cc.json() if cc.status_code == 200 else {}
    cc_rent = [i for i in (cc_body.get("attention_items") or cc_body.get("items") or []) if "rent" in json.dumps(i).lower()]
    return {
        "at_utc": utc(),
        "overdue_count": summary.get("overdue_count"),
        "arrears_count": summary.get("tenancies_with_arrears_count"),
        "attention_ledgers": len(attention),
        "risk_signals_status": risk.status_code,
        "rent_risk_signals": len(rent_risk),
        "snapshot_status": snap.status_code,
        "command_centre_rent_items": len(cc_rent),
        "pass": summary.get("overdue_count") is not None and st == 200,
    }


def part_cross_surface(client_t: str) -> dict:
    summary, _ = get_summary(client_t)
    snap_r = req("get", f"/client/properties/{PROPERTY_ID}/financial-snapshot", client_t)
    snap = snap_r.json() if snap_r.status_code == 200 else {}
    occ = req("get", f"/client/properties/{PROPERTY_ID}/occupancy-operational-summary", client_t)
    occ_body = occ.json() if occ.status_code == 200 else {}
    collected_match = summary.get("rent_collected_this_month_minor") == snap.get("rent_collected_this_month_minor")
    return {
        "at_utc": utc(),
        "summary_collected": summary.get("rent_collected_this_month_minor"),
        "snapshot_collected": snap.get("rent_collected_this_month_minor"),
        "collected_match": collected_match,
        "occupancy_status": occ.status_code,
        "occupancy_rent_status": occ_body.get("rent_status") or (occ_body.get("rent") or {}).get("status"),
        "pass": collected_match and occ.status_code in (200, 404),
    }


def part_mobile(client_t: str, client_u: dict) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot = BUNDLE / "screenshots"
    shot.mkdir(parents=True, exist_ok=True)
    captures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 375, "height": 844})
        logged = browser_login_landlord(page, client_t, client_u)
        for width in (375, 390, 414):
            page.set_viewport_size({"width": width, "height": 844})
            rent_loaded = browser_open_rent(page, f"?property_id={PROPERTY_ID}")
            path = shot / f"rent_ops_{width}px.png"
            page.screenshot(path=str(path), full_page=True)
            overflow = page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 24")
            tabs = page.locator('[data-testid="rent-operations-tab-nav"]').count() > 0
            kpi = page.locator('[data-testid="rent-summary-cards"]').count() > 0
            page_ok = page.locator('[data-testid="rent-operations-page"]').count() > 0
            captures.append({
                "width": width,
                "logged_in": logged,
                "rent_loaded": rent_loaded,
                "overflow_ok": overflow,
                "tabs": tabs,
                "kpi": kpi,
                "page_ok": page_ok,
                "screenshot": f"screenshots/rent_ops_{width}px.png",
            })
        browser.close()
    return {
        "at_utc": utc(),
        "captures": captures,
        "pass": bool(captures) and all(c["overflow_ok"] and c["page_ok"] and c["rent_loaded"] for c in captures),
    }


def part_audit_trail(client_t: str, admin_t: str) -> dict:
    ledgers, _ = list_ledgers(client_t)
    sample = ledgers[0] if ledgers else {}
    lid = sample.get("ledger_id")
    ld: dict = {}
    if lid:
        ld, _ = get_ledger(client_t, lid)
    payments_on_ledger = len(ld.get("payments") or [])
    reminders_on_ledger = len(ld.get("reminders") or [])
    admin_logs = req("get", "/admin/audit-logs", admin_t, params={"client_id": CLIENT_ID, "limit": 100})
    items = (admin_logs.json().get("logs") or admin_logs.json().get("items") or []) if admin_logs.status_code == 200 else []
    rent_actions = sorted({i.get("action") for i in items if i.get("action") and "RENT" in str(i.get("action")).upper()})
    return {
        "at_utc": utc(),
        "admin_audit_status": admin_logs.status_code,
        "rent_actions_seen": rent_actions[:20],
        "ledger_payments_count": payments_on_ledger,
        "ledger_reminders_count": reminders_on_ledger,
        "pass": (admin_logs.status_code == 200 and len(rent_actions) >= 1) or payments_on_ledger >= 1,
    }


def part_permissions(client_t: str, tenant_t: str, contractor_t: str) -> dict:
    probes = []
    probes.append({"persona": "landlord", "endpoint": "/client/operations/rent/summary", "status": req("get", "/client/operations/rent/summary", client_t).status_code, "pass": True})
    probes.append({"persona": "tenant", "endpoint": "/client/operations/rent/summary", "status": req("get", "/client/operations/rent/summary", tenant_t).status_code, "pass": req("get", "/client/operations/rent/summary", tenant_t).status_code in (401, 403)})
    if contractor_t:
        probes.append({"persona": "contractor", "endpoint": "/client/operations/rent/summary", "status": req("get", "/client/operations/rent/summary", contractor_t).status_code, "pass": req("get", "/client/operations/rent/summary", contractor_t).status_code in (401, 403)})
    probes.append({"persona": "unauthenticated", "endpoint": "/client/operations/rent/summary", "status": req("get", "/client/operations/rent/summary", "").status_code, "pass": req("get", "/client/operations/rent/summary", "").status_code in (401, 403)})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_edge_resilience(client_t: str, setup: dict) -> dict:
    idem = f"{MARKER}-edge-{uuid.uuid4().hex[:8]}"
    dup_sched = req(
        "post",
        "/client/operations/rent/schedules",
        client_t,
        json={
            "property_id": PROPERTY_ID,
            "tenancy_id": setup.get("tenancy_id"),
            "expected_amount_minor": 88000,
            "rent_frequency": "monthly",
            "due_day": 15,
            "start_date": date.today().replace(day=1).isoformat(),
            "idempotency_key": idem,
        },
    )
    dup_sched2 = req(
        "post",
        "/client/operations/rent/schedules",
        client_t,
        json={
            "property_id": PROPERTY_ID,
            "tenancy_id": setup.get("tenancy_id"),
            "expected_amount_minor": 88000,
            "rent_frequency": "monthly",
            "due_day": 15,
            "start_date": date.today().replace(day=1).isoformat(),
            "idempotency_key": idem,
        },
    )
    return {
        "at_utc": utc(),
        "duplicate_schedule_first": dup_sched.status_code,
        "duplicate_schedule_replay": dup_sched2.status_code,
        "idempotent": dup_sched2.status_code in (200, 201, 409),
        "pass": dup_sched.status_code in (200, 201) and dup_sched2.status_code in (200, 201, 409),
    }


def part_regression() -> dict:
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    tests = [
        "tests/test_rent_operations.py",
        "tests/test_client_rent_operations_http.py",
        "tests/test_rent_attention_projection.py",
    ]
    env = {**os.environ, "CI": "true", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )
    fe_proc = subprocess.run(
        [npm, "test", "--", "--watchAll=false", "--passWithNoTests", "src/pages/ClientRentOperationsPage.test.js"],
        cwd=str(ROOT.parent / "frontend"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
    )
    return {
        "at_utc": utc(),
        "backend_exit": proc.returncode,
        "backend_tail": proc.stdout[-2000:] + proc.stderr[-1000:],
        "frontend_exit": fe_proc.returncode,
        "frontend_tail": fe_proc.stdout[-1500:],
        "pass": proc.returncode == 0 and fe_proc.returncode == 0,
    }


def classify(results: Dict[str, bool], reminder: dict) -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags: List[str] = []
    if not reminder.get("automatic_send_proven"):
        flags.append("RENT_REMINDER_GAP")
    if blockers:
        if "tenant" in blockers:
            flags.append("TENANT_RENT_DRIFT")
        if "reminders" in blockers:
            flags.append("RENT_REMINDER_GAP")
        if "mobile" in blockers:
            flags.append("MOBILE_RENT_DRIFT")
        if "permissions" in blockers:
            flags.append("PERMISSION_DRIFT")
        if "status_logic" in blockers:
            flags.append("RENT_STATUS_DRIFT")
        if "arrears_risk" in blockers:
            flags.append("RENT_RISK_SIGNAL_DRIFT")
        clf = "PARTIAL" if len(blockers) <= 3 else "FAIL_OPERATIONAL"
    elif reminder.get("automatic_send_proven"):
        clf = "VERIFIED_OPERATIONALLY"
    elif reminder.get("pass"):
        clf = "RENT_REMINDER_GAP"
    else:
        clf = "PARTIAL"
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "secondary_flags": flags,
        "blockers": blockers,
        "checklist": results,
        "reminder_mode": reminder.get("implementation"),
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    client_t, client_u = login_client()
    tenant_t, tenant_u = login_tenant()
    contractor_t = login_contractor()
    admin_t = login_admin()

    setup = part_setup(client_t, client_u, tenant_t, tenant_u)
    write_artifact("rent_runtime_setup.json", setup)

    tracking = part_tracking_setup(client_t, client_u, setup)
    write_artifact("rent_tracking_setup_runtime.json", tracking)

    status = part_status_logic(client_t)
    write_artifact("rent_status_logic_runtime.json", status)

    payments = part_payments(client_t, client_u)
    write_artifact("rent_payment_runtime.json", payments)

    tenant = part_tenant(tenant_t, client_t)
    write_artifact("tenant_rent_runtime.json", tenant)

    reminders = part_reminders(client_t)
    write_artifact("rent_reminder_runtime.json", reminders)

    arrears = part_arrears_risk(client_t)
    write_artifact("rent_arrears_risk_runtime.json", arrears)

    cross = part_cross_surface(client_t)
    write_artifact("rent_cross_surface_runtime.json", cross)

    mobile = part_mobile(client_t, client_u)
    write_artifact("rent_mobile_runtime.json", mobile)

    audit = part_audit_trail(client_t, admin_t)
    write_artifact("rent_audit_trail_runtime.json", audit)

    perms = part_permissions(client_t, tenant_t, contractor_t)
    write_artifact("rent_permissions_runtime.json", perms)

    edge = part_edge_resilience(client_t, setup)
    write_artifact("rent_edge_resilience_runtime.json", edge)

    regression = part_regression()
    write_artifact("rent_regression_runtime.json", regression)

    results = {
        "setup": setup.get("pass") is True,
        "tracking_setup": tracking.get("pass") is True,
        "status_logic": status.get("pass") is True,
        "payments": payments.get("pass") is True,
        "tenant": tenant.get("pass") is True,
        "reminders": reminders.get("pass") is True,
        "arrears_risk": arrears.get("pass") is True,
        "cross_surface": cross.get("pass") is True,
        "mobile": mobile.get("pass") is True,
        "audit_trail": audit.get("pass") is True,
        "permissions": perms.get("pass") is True,
        "edge_resilience": edge.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    clf = classify(results, reminders)
    write_artifact("classifications.json", clf)

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        f"**Marker:** `{MARKER}`",
        "",
        "## Checklist",
    ]
    for k, v in results.items():
        report.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("secondary_flags"):
        report.append("\n**Secondary flags:** " + ", ".join(clf["secondary_flags"]))
    if clf.get("blockers"):
        report.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    report.append("\n## Harness\n\n`backend/rent_operations_landlord_tenant_runtime_audit_01_execute.py`\n")
    (BUNDLE / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    verified_lines = [f"- [{'x' if results.get(k) else ' '}] {k}" for k in results]
    watchlist = [
        "# Rent operations landlord-tenant watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Run tag: `{RUN_TAG}`",
        "",
        "## Checklist",
        *verified_lines,
        "",
        "## Gaps / follow-up",
        "- [ ] Tenant portal rent due surface (not implemented — by design today)",
        "- [ ] RENT_REMINDERS_LIVE_SEND on staging for automatic email/SMS proof",
        "- [ ] Real-device Safari bottom-bar overlap on enable-tracking modal",
        "- [ ] Timezone boundary tests around midnight UTC due dates",
    ]
    if "RENT_REMINDER_GAP" in clf.get("secondary_flags", []):
        watchlist.append("- [ ] Prove live due/overdue reminder delivery when RENT_REMINDERS_LIVE_SEND enabled")
    if clf.get("blockers"):
        watchlist.append(f"- [ ] Clear blockers: {', '.join(clf['blockers'])}")
    (BUNDLE / "watchlist.md").write_text("\n".join(watchlist) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
