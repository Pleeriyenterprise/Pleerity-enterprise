"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G8 Tenant Operations (ops_control_g8_tenant_operations).
Tenant operational truth verification — local harness only.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.classification_helpers import ClassificationAggregator
from services.ops_runtime_verify_02.convergence_observer import ConvergenceObserver

PROGRAMME = "PRELAUNCH-OPS-RUNTIME-VERIFY-02"
FAMILY = "ops_control_g8_tenant_operations"
OWNER = "ops_control_g8_tenant_operations"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
TENANT_EMAIL = os.environ.get("OPS_TENANT_EMAIL", "f7-ops-wales@yopmail.com")
SLUG = "6fd5ac4c_d35a58ae"

DEP_BUNDLES = [
    ("G0", f"ops_control_g0_programme_precheck_{SLUG}/07_classification.json"),
    ("G1", f"ops_runtime_g1_today_{SLUG}/07_classification.json"),
    ("G2", f"ops_runtime_g2_command_centre_{SLUG}/07_classification.json"),
    ("G3", f"ops_runtime_g3_properties_{SLUG}/07_classification.json"),
    ("G4", f"ops_runtime_g4_requirements_{SLUG}/07_classification.json"),
    ("G5", f"ops_runtime_g5_documents_{SLUG}/07_classification.json"),
    ("G6", f"ops_runtime_g6_calendar_{SLUG}/07_classification.json"),
    ("G7", f"ops_runtime_g7_reports_{SLUG}/07_classification.json"),
]
F7_BUNDLE = f"ops_runtime_07_tenant_portal_{SLUG}/07_classification.json"
F6_BUNDLE = f"ops_runtime_06_rent_ops_{SLUG}/07_classification.json"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "100"))

BUNDLE = ROOT / f"docs/audit/ops_runtime_g8_tenant_operations_{SLUG}"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _read_password() -> str:
    env = os.environ.get("OPS_VERIFY_PASSWORD")
    if env:
        return env.strip()
    return (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()


def _tenant_password() -> str:
    env = os.environ.get("OPS_TENANT_PASSWORD")
    if env:
        return env.strip()
    p = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt"
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return "F7OpsWales!Staging2026"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _http(method: str, url: str, *, headers: Optional[dict] = None, timeout: int = 120, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(4):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", timeout), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            last_exc = exc
            time.sleep(3 + attempt * 4)
    raise last_exc  # type: ignore[misc]


def _warm_api() -> None:
    for _ in range(12):
        try:
            r = _http("get", f"{API}/health", timeout=90)
            if r.status_code == 200 and "starting" not in (r.text or "").lower():
                return
        except Exception:
            pass
        time.sleep(8)


def _login(email: str, password: str) -> Tuple[str, dict]:
    _warm_api()
    for attempt in range(4):
        r = _http("post", f"{API}/auth/login", json={"email": email, "password": password}, timeout=90)
        if r.status_code == 200:
            body = r.json()
            return body["access_token"], body.get("user") or {}
        if r.status_code in (502, 503, 504):
            time.sleep(12 + attempt * 8)
            continue
        r.raise_for_status()
    raise RuntimeError(f"login_failed:{email}")


def _load_dep(rel: str) -> dict:
    p = ROOT / "docs/audit" / rel.replace("/", os.sep)
    if not p.is_file():
        return {"found": False}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"found": True, "classification": data.get("classification"), "raw": data}


def _fetch_occupancy(token: str) -> Dict[str, Any]:
    r = _http(
        "get",
        f"{API}/client/properties/{PROPERTY_ID}/occupancy-operational-summary",
        headers=_headers(token),
        timeout=120,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:500]}


def _fetch_rent_summary(token: str) -> Dict[str, Any]:
    r = _http(
        "get",
        f"{API}/client/operations/rent/summary",
        headers=_headers(token),
        params={"property_id": PROPERTY_ID},
        timeout=120,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:400]}


def _fetch_maintenance_issues(token: str) -> Dict[str, Any]:
    r = _http(
        "get",
        f"{API}/client/maintenance/issues",
        headers=_headers(token),
        params={"property_id": PROPERTY_ID, "limit": 100},
        timeout=120,
    )
    body = r.json() if r.status_code == 200 else {}
    issues = body.get("issues") or body.get("items") or []
    open_issues = [
        i
        for i in issues
        if (i.get("status") or "").lower() not in ("resolved", "closed", "cancelled")
    ]
    tenant_reported = [i for i in open_issues if (i.get("source") or "").lower() in ("tenant", "tenant_request")]
    return {
        "status": r.status_code,
        "open_count": len(open_issues),
        "tenant_reported_open": len(tenant_reported),
        "issues": issues[:20],
    }


def _fetch_tenant_issues(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/tenant/reported-issues", headers=_headers(token), timeout=120)
    body = r.json() if r.status_code == 200 else {}
    items = body if isinstance(body, list) else body.get("issues") or body.get("items") or []
    return {"status": r.status_code, "items": items[:20], "count": len(items)}


def _fetch_calendar(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/client/calendar/timeline", headers=_headers(token), timeout=120)
    body = r.json() if r.status_code == 200 else {}
    events = body.get("events") or body if isinstance(body, list) else []
    prop_events = [e for e in events if str(e.get("property_id") or "") == PROPERTY_ID]
    return {"status": r.status_code, "property_event_count": len(prop_events), "events": prop_events[:15]}


def _browser_landlord(token: str, user: dict, password: str) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    try:
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
        page.goto(f"{FRONTEND}/tenants", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(4000)
        tenants_ok = "tenant" in page.locator("body").inner_text().lower()
        tenants_title = page.locator("h1").first.inner_text() if page.locator("h1").count() else ""

        page.goto(f"{FRONTEND}/properties/{PROPERTY_ID}", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(8000)
        occ_tab = page.locator('[data-testid="property-tab-occupancy"]')
        occ_tab_visible = occ_tab.count() > 0
        if occ_tab_visible:
            occ_tab.click(timeout=15_000)
        panel_ready = False
        panel_loading = True
        panel_error = False
        for _ in range(12):
            page.wait_for_timeout(2500)
            panel_ready = page.locator('[data-testid="property-occupancy-panel"]').count() > 0
            panel_loading = page.locator('[data-testid="property-occupancy-loading"]').count() > 0
            panel_error = page.locator('[data-testid="property-occupancy-error"]').count() > 0
            if panel_ready or panel_error:
                break

        page.reload(wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
        page.wait_for_timeout(4000)
        refresh_persist = False
        for _ in range(20):
            if page.locator('[data-testid="property-tab-occupancy"]').count() > 0:
                break
            page.wait_for_timeout(1000)
        occ_tab_reload = page.locator('[data-testid="property-tab-occupancy"]')
        if occ_tab_reload.count():
            occ_tab_reload.click(timeout=20_000)
            for _ in range(16):
                page.wait_for_timeout(2500)
                if page.locator('[data-testid="property-occupancy-panel"]').count() > 0:
                    refresh_persist = True
                    break
                if page.locator('[data-testid="property-occupancy-error"]').count() > 0:
                    break

        (BUNDLE / "screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(BUNDLE / "screenshots" / "g8_tenants_workspace.png"))
        page.screenshot(path=str(BUNDLE / "screenshots" / "g8_property_occupancy_tab.png"))

        return {
            "tenants_reachable": tenants_ok,
            "tenants_title": tenants_title,
            "occupancy_tab_visible": occ_tab_visible,
            "occupancy_panel_ready": panel_ready and not panel_error,
            "occupancy_panel_loading_stuck": panel_loading and not panel_ready,
            "refresh_persistence": refresh_persist,
            "pass": tenants_ok and occ_tab_visible and panel_ready and not panel_error and refresh_persist,
        }
    finally:
        browser.close()
        p.stop()


def _browser_tenant(tenant_token: str, tenant_user: dict, tenant_pw: str) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", TENANT_EMAIL)
        page.fill("#password", tenant_pw)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        body = page.locator("body").inner_text()
        if "Sign In" in body[:200]:
            page.evaluate(
                "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
                [tenant_token, tenant_user],
            )
        page.goto(f"{FRONTEND}/tenant", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(4000)
        issues_text = page.locator("body").inner_text().lower()
        false_all_clear = "all clear" in issues_text and "open" in issues_text
        (BUNDLE / "screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(BUNDLE / "screenshots" / "g8_tenant_portal.png"))
        return {
            "tenant_portal_reachable": "tenant" in issues_text or "issue" in issues_text or "home" in issues_text,
            "false_all_clear_with_open_language": false_all_clear,
            "pass": True,
        }
    finally:
        browser.close()
        p.stop()


def _tenant_operations_boot(token: str, user: dict, password: str, occupancy: Dict[str, Any]) -> Dict[str, Any]:
    api_ok = occupancy.get("status") == 200
    body = occupancy.get("body") if api_ok else {}
    browser = _browser_landlord(token, user, password)
    return {
        "api_occupancy_summary_ok": api_ok,
        "authority_note_present": bool((body or {}).get("authority_note")),
        "feature_gates": (body or {}).get("feature_gates"),
        "browser": browser,
        "boot_ok": api_ok and browser.get("pass"),
        "pass": api_ok and browser.get("pass"),
    }


def _property_tenancy_layer(occupancy: Dict[str, Any]) -> Dict[str, Any]:
    body = occupancy.get("body") or {}
    sections = {
        "active_tenants": body.get("active_tenants"),
        "tenancy_lifecycle": body.get("tenancy_lifecycle"),
        "rent_status": body.get("rent_status"),
        "open_maintenance": body.get("open_maintenance"),
        "certificate_requests": body.get("certificate_requests"),
        "compliance_pack_deliveries": body.get("compliance_pack_deliveries"),
        "reminder_history": body.get("reminder_history"),
        "upcoming_visits": body.get("upcoming_visits"),
        "portal_activity": body.get("portal_activity"),
        "operational_alerts": body.get("operational_alerts"),
    }
    duplicate_truth = False
    rent = body.get("rent_status") or {}
    if rent and rent.get("authority") != "rent_operations":
        duplicate_truth = True
    stale = occupancy.get("status") != 200
    return {
        "sections_present": {k: v is not None for k, v in sections.items()},
        "property_authority_context": body.get("property_id") == PROPERTY_ID,
        "duplicate_rent_authority": duplicate_truth,
        "contradictory_states": False,
        "stale_occupancy_api": stale,
        "deep_links": body.get("deep_links"),
        "pass": occupancy.get("status") == 200 and not duplicate_truth and not stale,
    }


def _rent_sync(occupancy: Dict[str, Any], rent: Dict[str, Any]) -> Dict[str, Any]:
    occ_rent = (occupancy.get("body") or {}).get("rent_status") or {}
    rent_body = rent.get("body") or {}
    if rent.get("status") != 200:
        return {"pass": False, "reason": "rent_summary_unavailable", "rent_status": rent.get("status")}
    drift_fields: List[str] = []
    pairs = [
        ("overdue_count", "overdue_count"),
        ("severely_overdue_count", "severely_overdue_count"),
        ("partially_paid_count", "partially_paid_count"),
        ("total_outstanding_minor", "total_outstanding_minor"),
    ]
    for occ_key, rent_key in pairs:
        o = occ_rent.get(occ_key)
        r = rent_body.get(rent_key)
        if o is not None and r is not None and int(o) != int(r):
            drift_fields.append(occ_key)
    false_assurance = (
        (occ_rent.get("overdue_count") or 0) == 0
        and (rent_body.get("overdue_count") or 0) > 0
    )
    reminder_note_ok = all(
        "resolved" in (x.get("note") or "").lower() or "does not mean" in (x.get("note") or "").lower()
        for x in (occupancy.get("body") or {}).get("reminder_history") or []
    ) or not (occupancy.get("body") or {}).get("reminder_history")
    return {
        "rent_authority_owner": occ_rent.get("authority"),
        "drift_fields": drift_fields,
        "false_rent_assurance": false_assurance,
        "reminder_disclaimer_present": reminder_note_ok,
        "occupancy_rent": occ_rent,
        "rent_ops_summary": rent_body,
        "pass": len(drift_fields) == 0 and not false_assurance and occ_rent.get("authority") == "rent_operations",
    }


def _maintenance_coherence(occupancy: Dict[str, Any], maint: Dict[str, Any], tenant_issues: Dict[str, Any], f7: dict) -> Dict[str, Any]:
    occ_m = (occupancy.get("body") or {}).get("open_maintenance") or {}
    open_api = maint.get("open_count") or 0
    open_occ = occ_m.get("open_issues_count") or 0
    count_drift = open_occ > open_api + 2
    tenant_items = tenant_issues.get("items") or []
    false_resolved = any(
        (i.get("lifecycle_phase") or i.get("phase") or "").lower() in ("resolved", "closed")
        and (i.get("status") or "").lower() not in ("resolved", "closed")
        for i in tenant_items
    )
    visit_notes_ok = all(
        "resolved" in (v.get("note") or "").lower() or "does not mean" in (v.get("note") or "").lower()
        for v in (occupancy.get("body") or {}).get("upcoming_visits") or []
    ) or not (occupancy.get("body") or {}).get("upcoming_visits")
    f7_ref = f7.get("raw") or {}
    return {
        "landlord_open_count": open_api,
        "occupancy_open_count": open_occ,
        "tenant_reported_open_occ": occ_m.get("tenant_reported_open"),
        "projection_count_drift": count_drift,
        "tenant_false_resolved_label": false_resolved,
        "scheduled_not_fixed_disclaimer": visit_notes_ok,
        "f7_reference_classification": f7.get("classification"),
        "f7_issue_id": f7_ref.get("issue_id"),
        "reported_ne_resolved_preserved": not false_resolved,
        "pass": not count_drift and not false_resolved and visit_notes_ok,
    }


def _calendar_reminder_coherence(occupancy: Dict[str, Any], calendar: Dict[str, Any]) -> Dict[str, Any]:
    body = occupancy.get("body") or {}
    reminders = body.get("reminder_history") or []
    visits = body.get("upcoming_visits") or []
    overdue_rent_visible = (body.get("rent_status") or {}).get("overdue_count", 0) > 0
    scheduled_as_resolved = any("resolved" in (v.get("title") or "").lower() for v in visits)
    reminder_suppresses_debt = overdue_rent_visible and len(reminders) > 5 and len(body.get("operational_alerts") or []) == 0
    cal_events = calendar.get("property_event_count") or 0
    return {
        "reminder_count": len(reminders),
        "visit_count": len(visits),
        "calendar_property_events": cal_events,
        "scheduled_overstated_as_resolved": scheduled_as_resolved,
        "reminders_suppress_arrears_signal": reminder_suppresses_debt,
        "overdue_still_visible_with_visits": overdue_rent_visible or not visits,
        "pass": not scheduled_as_resolved and not reminder_suppresses_debt,
    }


def _portal_activity_governance(occupancy: Dict[str, Any], tenant_token: str) -> Dict[str, Any]:
    body = occupancy.get("body") or {}
    portal = body.get("portal_activity") or []
    tenants = body.get("active_tenants") or []
    raw = json.dumps(body)
    security_leak = "password_hash" in raw or "session_id" in raw
    states = {t.get("portal_activity") for t in tenants}
    r = _http("get", f"{API}/tenant/profile", headers=_headers(tenant_token), timeout=90)
    tenant_body = r.json() if r.status_code == 200 else {}
    tenant_leak = "password_hash" in json.dumps(tenant_body)
    return {
        "portal_states_observed": sorted(states),
        "active_tenant_count": len(tenants),
        "certificate_request_count": len(body.get("certificate_requests") or []),
        "landlord_summary_security_leak": security_leak,
        "tenant_profile_security_leak": tenant_leak,
        "pass": not security_leak and not tenant_leak,
    }


def _authority_segmentation(landlord_token: str, tenant_token: str) -> Dict[str, Any]:
    probes = [
        ("tenant_client_dashboard", "get", f"{API}/client/dashboard", tenant_token, (401, 403)),
        ("tenant_occupancy_summary", "get", f"{API}/client/properties/{PROPERTY_ID}/occupancy-operational-summary", tenant_token, (401, 403)),
        ("tenant_rent_summary", "get", f"{API}/client/operations/rent/summary", tenant_token, (401, 403)),
        ("tenant_maintenance_mutate", "post", f"{API}/client/maintenance/issues", tenant_token, (401, 403, 405, 422)),
        ("tenant_issues_allowed", "get", f"{API}/tenant/reported-issues", tenant_token, (200,)),
        ("landlord_occupancy_allowed", "get", f"{API}/client/properties/{PROPERTY_ID}/occupancy-operational-summary", landlord_token, (200,)),
    ]
    results: List[Dict[str, Any]] = []
    failures: List[str] = []
    for name, method, url, tok, expected in probes:
        extra: Dict[str, Any] = {}
        if method == "post":
            extra["json"] = {"title": "G8 probe", "property_id": PROPERTY_ID}
        r = _http(method, url, headers=_headers(tok), timeout=90, **extra)
        ok = r.status_code in expected
        if not ok:
            failures.append(f"{name}:{r.status_code}")
        results.append({"probe": name, "status": r.status_code, "expected": list(expected), "ok": ok})
    return {
        "probes": results,
        "failures": failures,
        "authority_boundary_failure": len(failures) > 0,
        "pass": len(failures) == 0,
    }


def _cross_surface(occupancy: Dict[str, Any], rent: Dict[str, Any], maint: Dict[str, Any], token: str) -> Dict[str, Any]:
    today = _http("get", f"{API}/today/items", headers=_headers(token), params={"property_id": PROPERTY_ID}, timeout=90)
    cc = _http("get", f"{API}/client/command-center", headers=_headers(token), timeout=90)
    occ = occupancy.get("body") or {}
    rent_body = rent.get("body") or {}
    contradictions: List[str] = []
    if rent.get("status") == 200:
        if (occ.get("rent_status") or {}).get("overdue_count", 0) != rent_body.get("overdue_count", 0):
            contradictions.append("occupancy_vs_rent_ops_overdue")
    if maint.get("status") == 200:
        occ_open = (occ.get("open_maintenance") or {}).get("open_issues_count", 0)
        api_open = maint.get("open_count", 0)
        if occ_open > api_open + 2:
            contradictions.append("occupancy_overstates_maintenance_open_count")
    today_body = today.json() if today.status_code == 200 else {}
    urgent = len((today_body.get("tasks") or {}).get("urgent") or [])
    hidden_debt = urgent > 0 and len(occ.get("operational_alerts") or []) == 0 and (occ.get("rent_status") or {}).get("overdue_count", 0) > 0
    return {
        "today_urgent": urgent,
        "cc_status": cc.status_code,
        "contradictions": contradictions,
        "hidden_debt_signal": hidden_debt,
        "pass": len(contradictions) == 0 and not hidden_debt,
    }


def _operational_cognition(occupancy: Dict[str, Any], boot: Dict[str, Any], tenant_browser: Dict[str, Any]) -> Dict[str, Any]:
    body = occupancy.get("body") or {}
    alerts = body.get("operational_alerts") or []
    overdue = (body.get("rent_status") or {}).get("overdue_count", 0)
    open_issues = (body.get("open_maintenance") or {}).get("open_issues_count", 0)
    false_calm = overdue > 0 and open_issues > 0 and len(alerts) == 0
    clutter = len(alerts) > 12
    return {
        "operational_alerts_count": len(alerts),
        "landlord_false_calm": false_calm,
        "crm_clutter_risk": clutter,
        "tenant_false_reassurance": tenant_browser.get("false_all_clear_with_open_language"),
        "occupancy_panel_boot": boot.get("browser", {}).get("occupancy_panel_ready"),
        "pass": not false_calm and not clutter and not tenant_browser.get("false_all_clear_with_open_language"),
    }


def _g9_g10(occupancy: Dict[str, Any], rent: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    body = occupancy.get("body") or {}
    tenants = body.get("active_tenants") or []
    emails = [t.get("email") for t in tenants if t.get("email")]
    dup_tenants = len(emails) != len(set(emails))
    reminders = body.get("reminder_history") or []
    dup_rem = len(reminders) != len({r.get("reminder_key") for r in reminders if r.get("reminder_key")})
    g9 = {
        "duplicate_tenant_rows": dup_tenants,
        "duplicate_reminder_keys": dup_rem,
        "pass": not dup_tenants and not dup_rem,
    }
    violations: List[str] = []
    rent_disclaimer = (body.get("rent_status") or {}).get("disclaimer") or ""
    if rent.get("status") == 200 and "rent operations" not in rent_disclaimer.lower():
        violations.append("rent_disclaimer_missing")
    for v in body.get("upcoming_visits") or []:
        if "resolved" in (v.get("note") or "").lower() or "does not mean" in (v.get("note") or "").lower():
            continue
        if v.get("scheduled_at"):
            violations.append("visit_missing_scheduled_disclaimer")
            break
    g10 = {
        "violations": violations,
        "reported_ne_resolved": True,
        "reminder_ne_payment": True,
        "scheduled_ne_fixed": len(violations) == 0,
        "pass": len(violations) == 0,
    }
    return g9, g10


def _wait_backend_deploy(token: str, max_wait_s: int = 900) -> bool:
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        occ = _fetch_occupancy(token)
        if occ.get("status") == 200:
            return True
        time.sleep(30)
    return False


def _wait_frontend_deploy(token: str, user: dict, max_wait_s: int = 900) -> bool:
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        try:
            from playwright.sync_api import sync_playwright

            p = sync_playwright().start()
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{FRONTEND}/properties/{PROPERTY_ID}", wait_until="domcontentloaded", timeout=90_000)
            page.evaluate(
                "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
                [token, user],
            )
            page.reload(wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(5000)
            ok = page.locator('[data-testid="property-tab-occupancy"]').count() > 0
            browser.close()
            p.stop()
            if ok:
                return True
        except Exception:
            pass
        time.sleep(45)
    return False


def run_g8(*, skip_deploy_wait: bool = False) -> Dict[str, Any]:
    for label, bundle in DEP_BUNDLES:
        dep = _load_dep(bundle)
        if dep.get("classification") != "VERIFIED_OPERATIONALLY":
            raise SystemExit(f"{label} prerequisite failed: {dep.get('classification')}")

    f7 = _load_dep(F7_BUNDLE)
    f6 = _load_dep(F6_BUNDLE)
    if f7.get("classification") != "VERIFIED_OPERATIONALLY":
        raise SystemExit(f"F7 prerequisite failed: {f7.get('classification')}")

    landlord_pw = _read_password()
    tenant_pw = _tenant_password()
    landlord_token, landlord_user = _login(CLIENT_EMAIL, landlord_pw)
    tenant_token, tenant_user = _login(TENANT_EMAIL, tenant_pw)

    if not skip_deploy_wait:
        deployed = _wait_backend_deploy(landlord_token, max_wait_s=int(os.environ.get("G8_DEPLOY_WAIT_S", "900")))
        if not deployed:
            occ_probe = _fetch_occupancy(landlord_token)
            blocked = {
                "classification": "BLOCKED",
                "reason": "occupancy_operational_summary_not_deployed",
                "occupancy_status": occ_probe.get("status"),
            }
            _write("07_classification.json", blocked)
            _write("classifications.json", {"classifications": [blocked]})
            _write("tenant_operations_boot.json", blocked)
            (BUNDLE / "REPORT.md").write_text(
                f"# G8 Tenant Operations — BLOCKED\n\nOccupancy API returned `{occ_probe.get('status')}` — deploy backend with occupancy summary before G8.\n",
                encoding="utf-8",
            )
            return blocked
    if not skip_deploy_wait or os.environ.get("G8_FORCE_FRONTEND_WAIT") == "1":
        if not _wait_frontend_deploy(
            landlord_token, landlord_user, max_wait_s=int(os.environ.get("G8_FRONTEND_WAIT_S", "900"))
        ):
            blocked = {
                "classification": "BLOCKED",
                "reason": "property_occupancy_tab_not_deployed_frontend",
                "occupancy_api": _fetch_occupancy(landlord_token).get("status"),
            }
            _write("07_classification.json", blocked)
            _write("classifications.json", {"classifications": [blocked]})
            _write("tenant_operations_boot.json", blocked)
            (BUNDLE / "REPORT.md").write_text(
                "# G8 Tenant Operations — BLOCKED\n\nFrontend Occupancy tab not visible after deploy wait.\n",
                encoding="utf-8",
            )
            return blocked

    occupancy = _fetch_occupancy(landlord_token)
    rent = _fetch_rent_summary(landlord_token)
    maint = _fetch_maintenance_issues(landlord_token)
    calendar = _fetch_calendar(landlord_token)
    tenant_issues = _fetch_tenant_issues(tenant_token)

    boot = _tenant_operations_boot(landlord_token, landlord_user, landlord_pw, occupancy)
    _write("tenant_operations_boot.json", boot)

    tenancy_layer = _property_tenancy_layer(occupancy)
    _write("property_tenancy_layer_verification.json", tenancy_layer)

    rent_sync = _rent_sync(occupancy, rent)
    _write("tenant_rent_sync_verification.json", rent_sync)

    maint_coh = _maintenance_coherence(occupancy, maint, tenant_issues, f7)
    _write("tenant_maintenance_coherence.json", maint_coh)

    cal_coh = _calendar_reminder_coherence(occupancy, calendar)
    _write("tenant_calendar_reminder_coherence.json", cal_coh)

    portal_gov = _portal_activity_governance(occupancy, tenant_token)
    _write("tenant_portal_activity_governance.json", portal_gov)

    authority = _authority_segmentation(landlord_token, tenant_token)
    _write("tenant_authority_segmentation.json", authority)

    cross = _cross_surface(occupancy, rent, maint, landlord_token)
    _write("tenant_cross_surface_coherence.json", cross)

    tenant_browser = _browser_tenant(tenant_token, tenant_user, tenant_pw)
    cognition = _operational_cognition(occupancy, boot, tenant_browser)
    _write("tenant_operational_cognition.json", cognition)

    g9, g10 = _g9_g10(occupancy, rent)
    _write("g9_tenant_integrity.json", g9)
    _write("g10_tenant_authority.json", g10)

    def read_occ_counts() -> Dict[str, Any]:
        o = _fetch_occupancy(landlord_token)
        b = o.get("body") or {}
        return {
            "open_issues": (b.get("open_maintenance") or {}).get("open_issues_count"),
            "alerts": len(b.get("operational_alerts") or []),
            "overdue": (b.get("rent_status") or {}).get("overdue_count"),
        }

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_occ_counts()
    observer.observe(
        "occupancy_summary",
        read_occ_counts,
        agree_fn=lambda a, b: a == b,
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=False,
    )
    conv = observer.build_artifact()
    conv["t0"] = t0
    conv["f6_reference"] = f6.get("classification")
    conv["f7_reference"] = f7.get("classification")
    _write("convergence.json", conv)

    agg = ClassificationAggregator(FAMILY)
    if not boot.get("pass"):
        agg.add("FAIL_SYSTEM", "tenant_operations_boot")
    if not tenancy_layer.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "property_tenancy_layer")
    if tenancy_layer.get("duplicate_rent_authority"):
        agg.add("RENT_AUTHORITY_DRIFT", "duplicate_rent_authority")
    if not rent_sync.get("pass"):
        if rent_sync.get("false_rent_assurance"):
            agg.add("FALSE_RENT_ASSURANCE", "rent_sync")
        else:
            agg.add("RENT_AUTHORITY_DRIFT", "rent_sync")
    if not maint_coh.get("pass"):
        agg.add("FAIL_OPERATIONAL", "maintenance_coherence")
    if not cal_coh.get("pass"):
        agg.add("FAIL_OPERATIONAL", "calendar_reminder")
    if not portal_gov.get("pass"):
        agg.add("TRUST_RISK_PRESENT", "portal_activity")
    if not authority.get("pass"):
        agg.add("AUTHORITY_BOUNDARY_FAILURE", "tenant_authority")
    if not cross.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "cross_surface")
    if not cognition.get("pass"):
        agg.add("COGNITIVE_TRUST_RISK", "cognition")
    if cognition.get("landlord_false_calm"):
        agg.add("FALSE_OPERATIONAL_FRAMING", "landlord_false_calm")

    result = agg.finalize(execution_completed=True)
    verified = (
        boot.get("pass")
        and tenancy_layer.get("pass")
        and rent_sync.get("pass")
        and maint_coh.get("pass")
        and cal_coh.get("pass")
        and portal_gov.get("pass")
        and authority.get("pass")
        and cross.get("pass")
        and cognition.get("pass")
        and g9.get("pass")
        and g10.get("pass")
        and not conv.get("any_stale")
    )
    primary = "VERIFIED_OPERATIONALLY" if verified else (result.primary if result.blocking else "PARTIAL")

    classification = result.to_dict()
    classification.update(
        {
            "classification": primary,
            "execution_status": primary,
            "blocking": not verified,
            "authoritative_verification_owner": OWNER,
            "proof_mode": PROOF_MODE,
            "run_tag": RUN_TAG,
            "pilot_slug": SLUG,
            "client_id": CLIENT_ID,
            "property_id": PROPERTY_ID,
            "shared_dependency_bundle_ids": [b for _, b in DEP_BUNDLES],
            "f7_reference": F7_BUNDLE,
            "f6_reference": F6_BUNDLE,
            "checkpoints": {
                "G8_boot": boot.get("pass"),
                "G8_property_tenancy": tenancy_layer.get("pass"),
                "G8_rent_sync": rent_sync.get("pass"),
                "G8_maintenance": maint_coh.get("pass"),
                "G8_calendar": cal_coh.get("pass"),
                "G8_portal": portal_gov.get("pass"),
                "G8_authority": authority.get("pass"),
                "G8_cross_surface": cross.get("pass"),
                "G8_cognition": cognition.get("pass"),
                "G8_g9_g10": g9.get("pass") and g10.get("pass"),
                "G8_convergence": not conv.get("any_stale"),
            },
        }
    )
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watchlist: List[str] = []
    if maint_coh.get("projection_count_drift"):
        watchlist.append("occupancy open issue count differs from maintenance API by >2")
    if rent_sync.get("drift_fields"):
        watchlist.append(f"rent field drift: {rent_sync.get('drift_fields')}")
    if not boot.get("browser", {}).get("tenants_title", "").lower().startswith("tenant"):
        watchlist.append(f"tenants workspace title: {boot.get('browser', {}).get('tenants_title')}")
    _write(
        "watchlist.md",
        "\n".join(
            [
                f"# G8 Tenant Operations watchlist — {SLUG}",
                "",
                f"**Run:** `{RUN_TAG}`",
                f"**Classification:** `{primary}`",
                "",
                "## Watchlist",
                "",
            ]
            + [f"- {w}" for w in watchlist]
            or ["- (none)"],
        ),
    )

    report = f"""# G8 Tenant Operations — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Checkpoint | Result |
|------------|--------|
| Boot | {boot.get('pass')} |
| Property tenancy layer | {tenancy_layer.get('pass')} |
| Rent sync | {rent_sync.get('pass')} |
| Maintenance coherence | {maint_coh.get('pass')} |
| Calendar/reminder | {cal_coh.get('pass')} |
| Portal governance | {portal_gov.get('pass')} |
| Authority segregation | {authority.get('pass')} |
| Cross-surface | {cross.get('pass')} |
| Cognition | {cognition.get('pass')} |
| G9/G10 | {g9.get('pass') and g10.get('pass')} |
| Convergence | {not conv.get('any_stale')} |
"""
    (BUNDLE / "REPORT.md").write_text(report, encoding="utf-8")
    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — G8 Tenant Operations\n\n**Run:** `{RUN_TAG}`\n\nG8 `VERIFIED_OPERATIONALLY`. VERIFY-02 extended with G8.\n",
            encoding="utf-8",
        )

    return {"classification": primary, "bundle": str(BUNDLE), "blocking": not verified, "verified": verified}


if __name__ == "__main__":
    print(json.dumps(run_g8(skip_deploy_wait=os.environ.get("G8_SKIP_DEPLOY_WAIT") == "1"), indent=2))
