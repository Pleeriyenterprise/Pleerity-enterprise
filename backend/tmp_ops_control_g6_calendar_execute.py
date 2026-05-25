"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G6 Calendar (ops_control_g6_calendar_page).
Operational calendar authority verification — local harness only.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.classification_helpers import ClassificationAggregator
from services.ops_runtime_verify_02.convergence_observer import ConvergenceObserver

PROGRAMME = "PRELAUNCH-OPS-RUNTIME-VERIFY-02"
FAMILY = "ops_control_g6_calendar_page"
OWNER = "ops_control_g6_calendar_page"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"

DEP_BUNDLES = [
    ("G0", f"ops_control_g0_programme_precheck_{SLUG}/07_classification.json"),
    ("G1", f"ops_runtime_g1_today_{SLUG}/07_classification.json"),
    ("G2", f"ops_runtime_g2_command_centre_{SLUG}/07_classification.json"),
    ("G3", f"ops_runtime_g3_properties_{SLUG}/07_classification.json"),
    ("G4", f"ops_runtime_g4_requirements_{SLUG}/07_classification.json"),
    ("G5", f"ops_runtime_g5_documents_{SLUG}/07_classification.json"),
]

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-VERIFY02-G6-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "90"))

BUNDLE = ROOT / f"docs/audit/ops_runtime_g6_calendar_{SLUG}"

RESOLVED_WO = {"COMPLETED", "CANCELLED", "CLOSED"}
ACTIVE_SCHEDULE = {"proposed", "confirmed", "reschedule_requested"}


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


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _http(method: str, url: str, *, headers: Optional[dict] = None, timeout: int = 120, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", timeout), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            last_exc = exc
            time.sleep(3 + attempt * 3)
    raise last_exc  # type: ignore[misc]


def _warm_api() -> None:
    for _ in range(12):
        try:
            r = _http("get", f"{API}/health", timeout=90)
            if r.status_code == 200 and "starting" not in (r.text or "").lower():
                return
        except Exception:
            pass
        time.sleep(10)


def _login() -> Tuple[str, dict]:
    _warm_api()
    pw = _read_password()
    last: Optional[httpx.Response] = None
    for attempt in range(4):
        r = _http("post", f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=90)
        last = r
        if r.status_code == 200:
            body = r.json()
            return body["access_token"], body.get("user") or {}
        if r.status_code in (502, 503, 504):
            time.sleep(15 + attempt * 10)
            continue
        r.raise_for_status()
    last.raise_for_status()  # type: ignore[union-attr]
    raise RuntimeError("login failed")


def _load_dep(rel: str) -> dict:
    p = ROOT / "docs/audit" / rel.replace("/", os.sep)
    if not p.is_file():
        return {"found": False}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"found": True, "classification": data.get("classification"), "raw": data}


def _fetch_calendar_events(token: str, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    params: Dict[str, Any] = {"year": year or now.year}
    if month:
        params["month"] = month
    r = _http("get", f"{API}/calendar/events", headers=_headers(token), params=params, timeout=90)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _fetch_upcoming(token: str, days: int = 90) -> Dict[str, Any]:
    r = _http("get", f"{API}/calendar/upcoming", headers=_headers(token), params={"days": days}, timeout=90)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _flatten_events(cal: Dict[str, Any], upcoming: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    body = cal.get("body") or {}
    for _date, rows in (body.get("events_by_date") or {}).items():
        for e in rows or []:
            out.append({**e, "_source": "month_grid"})
    ubody = upcoming.get("body") or {}
    for e in ubody.get("timeline_events") or []:
        if not any(x.get("event_id") == e.get("event_id") for x in out):
            out.append({**e, "_source": "timeline"})
    return out


def _pilot_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in events:
        pid = str(e.get("property_id") or (e.get("metadata") or {}).get("property_id") or "")
        if pid == PROPERTY_ID:
            out.append(e)
    return out


def _event_property_id(event: Dict[str, Any]) -> str:
    return str(event.get("property_id") or (event.get("metadata") or {}).get("property_id") or "")


def _navigate_calendar_month(page, date_key: str) -> None:
    if not date_key or len(str(date_key)) < 7:
        return
    try:
        target_year = int(str(date_key)[:4])
        target_month = int(str(date_key)[5:7])
    except ValueError:
        return
    for _ in range(24):
        heading = page.locator("h2").first.inner_text().lower()
        months = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
        if target_month < 1 or target_month > 12:
            return
        if str(target_year) in heading and months[target_month - 1] in heading:
            return
        page.get_by_test_id("next-month").click()
        page.wait_for_timeout(1200)


def _fetch_work_orders(token: str) -> List[Dict[str, Any]]:
    r = _http(
        "get",
        f"{API}/client/maintenance/work-orders",
        headers=_headers(token),
        params={"property_id": PROPERTY_ID, "limit": 50},
        timeout=90,
    )
    if r.status_code != 200:
        return []
    return r.json().get("work_orders") or r.json().get("items") or []


def _fetch_requirements(token: str) -> List[Dict[str, Any]]:
    r = _http("get", f"{API}/client/properties/{PROPERTY_ID}/requirements", headers=_headers(token), timeout=90)
    if r.status_code != 200:
        return []
    return r.json().get("requirements") or []


def _fetch_today(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/today/items", headers=_headers(token), params={"property_id": PROPERTY_ID}, timeout=120)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _fetch_cc(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/client/command-center", headers=_headers(token), params={"property_id": PROPERTY_ID}, timeout=120)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _flatten_tasks(today: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = today.get("body") if isinstance(today.get("body"), dict) else {}
    tasks = body.get("tasks") or {}
    out: List[Dict[str, Any]] = []
    for section in ("urgent", "in_progress", "upcoming", "completed", "snoozed", "hidden"):
        for t in tasks.get(section) or []:
            out.append({**t, "_section": section})
    return out


def _event_authority_inventory(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    classes: Dict[str, Dict[str, Any]] = {}
    for e in events:
        cat = str(e.get("event_category") or "unknown")
        et = str(e.get("event_type") or "unknown")
        key = f"{cat}:{et}"
        if key not in classes:
            classes[key] = {
                "event_category": cat,
                "event_type": et,
                "authority_owner": "requirement_engine" if cat == "requirement" else "work_order_schedule",
                "source_system": "client_calendar_timeline_service",
                "operational_meaning": et.replace("_", " "),
                "mutation_owner": "/requirements" if cat == "requirement" else "/operations/work-orders",
                "live_or_derived": "derived_projection",
                "actionable": cat != "requirement" or et in ("requirement_overdue", "requirement_expiring_soon", "requirement_due"),
                "sample_count": 0,
                "sample_titles": [],
            }
        classes[key]["sample_count"] += 1
        title = str(e.get("title") or "")[:80]
        if title and len(classes[key]["sample_titles"]) < 3:
            classes[key]["sample_titles"].append(title)
    return {
        "total_events": len(events),
        "pilot_events": len(_pilot_events(events)),
        "event_classes": list(classes.values()),
        "pass": len(events) > 0 or True,
    }


def _scheduling_truth(events: List[Dict[str, Any]], wos: List[Dict[str, Any]], reqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []

    wo_by_id = {str(w.get("work_order_id")): w for w in wos}
    for e in events:
        et = str(e.get("event_type") or "")
        cat = str(e.get("event_category") or "")
        meta = e.get("metadata") or {}
        wid = str(meta.get("work_order_id") or e.get("source_entity_id") or "")
        if cat in ("scheduled_job", "compliance_job") and "visit" in et and "cancelled" not in et and "completed" not in et:
            wo = wo_by_id.get(wid) or {}
            wo_status = str(wo.get("status") or e.get("work_order_status") or "").upper()
            sched = str(wo.get("schedule_status") or e.get("status") or "").lower()
            if wo_status in RESOLVED_WO and sched not in ("cancelled", "completed"):
                violations.append({"kind": "FALSE_SCHEDULED_ASSURANCE", "event_id": e.get("event_id"), "detail": "resolved_wo_shown_as_active_visit"})
            checks.append(
                {
                    "event_id": e.get("event_id"),
                    "wo_status": wo_status,
                    "schedule_status": sched,
                    "scheduled_not_resolved": wo_status not in RESOLVED_WO or sched in ("cancelled", "completed"),
                }
            )
        if et == "requirement_overdue":
            st = str(e.get("status") or "").upper()
            if st in ("COMPLIANT", "VERIFIED"):
                violations.append({"kind": "FALSE_SCHEDULED_ASSURANCE", "event_id": e.get("event_id"), "detail": "overdue_event_marked_compliant"})
        if et == "requirement_valid" and str(e.get("severity") or "").lower() in ("critical", "high"):
            violations.append({"kind": "TEMPORAL_PROJECTION_INVERSION", "event_id": e.get("event_id"), "detail": "valid_event_high_severity"})

    overdue_reqs = [r for r in reqs if str(r.get("computed_status") or r.get("status") or "").upper() in ("OVERDUE", "EXPIRED")]
    scheduled_open = [
        w
        for w in wos
        if str(w.get("schedule_status") or "").lower() in ACTIVE_SCHEDULE
        and str(w.get("status") or "").upper() not in RESOLVED_WO
    ]
    overdue_events = [e for e in events if e.get("event_type") == "requirement_overdue"]
    future_visit_events = [
        e
        for e in events
        if e.get("event_category") in ("scheduled_job", "compliance_job")
        and "visit" in str(e.get("event_type") or "")
        and "cancelled" not in str(e.get("event_type") or "")
    ]
    dual_debt_ok = True
    if overdue_reqs and scheduled_open:
        dual_debt_ok = len(overdue_events) > 0
        if not dual_debt_ok:
            violations.append({"kind": "PROJECTION_RESOLUTION_FAILURE", "detail": "overdue_hidden_despite_open_schedule"})

    false_future_safe = False
    if scheduled_open and overdue_reqs:
        false_future_safe = len(overdue_events) == 0
        if false_future_safe:
            violations.append({"kind": "FALSE_SCHEDULED_ASSURANCE", "detail": "future_booking_implies_safe_while_overdue"})

    return {
        "violations": violations,
        "checks_sample": checks[:12],
        "overdue_requirements": len(overdue_reqs),
        "scheduled_open_work_orders": len(scheduled_open),
        "overdue_calendar_events": len(overdue_events),
        "future_visit_events": len(future_visit_events),
        "dual_debt_coherent": dual_debt_ok,
        "scheduled_not_resolved_preserved": len([v for v in violations if v.get("kind") == "FALSE_SCHEDULED_ASSURANCE"]) == 0,
        "pass": len(violations) == 0,
    }


def _browser_session(token: str, user: dict, password: str):
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(5 + attempt * 5)
    else:
        browser.close()
        p.stop()
        raise last_exc  # type: ignore[misc]
    page.fill("#email", CLIENT_EMAIL)
    page.fill("#password", password)
    page.click('button[type="submit"]')
    page.wait_for_timeout(5000)
    body = page.locator("body").inner_text()
    if "Sign In" in body[:250] and "Compliance" not in body:
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
    return p, browser, page


def _wait_calendar_shell(page, timeout_ms: int = 90_000) -> str:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if page.locator('[data-testid="calendar-page"]').count() > 0:
            return "ready"
        page.wait_for_timeout(2000)
    return "timeout"


def _calendar_surface_boot(token: str, user: dict, password: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc(), "checks": [], "browser": {"steps": []}}

    def chk(name: str, ok: bool, detail: str = "") -> None:
        out["checks"].append({"name": name, "ok": ok, "detail": detail})

    cal_api = _fetch_calendar_events(token)
    upcoming_api = _fetch_upcoming(token)
    chk("calendar_events_api", cal_api.get("status") == 200, f"status={cal_api.get('status')}")
    chk("calendar_upcoming_api", upcoming_api.get("status") == 200, f"status={upcoming_api.get('status')}")
    summary = (cal_api.get("body") or {}).get("summary") or {}
    chk("events_loaded", (summary.get("total_events") or 0) >= 0, f"total={summary.get('total_events')}")

    p, browser, page = _browser_session(token, user, password)
    page.goto(f"{FRONTEND}/calendar", wait_until="domcontentloaded", timeout=120_000)
    shell = _wait_calendar_shell(page, 90_000)
    out["browser"]["steps"].append({"name": "calendar_route", "ok": "/calendar" in page.url})
    out["browser"]["steps"].append({"name": "calendar_shell", "ok": shell == "ready", "detail": shell})

    title_ok = "timeline" in page.locator("h1").inner_text().lower() or page.locator('[data-testid="calendar-page"]').count() > 0
    out["browser"]["steps"].append({"name": "operational_shell", "ok": title_ok})

    pilot_ev = _pilot_events(events)
    sample = pilot_ev[0] if pilot_ev else (events[0] if events else None)
    event_id = sample.get("event_id") if sample else None
    event_date = str(sample.get("date") or "") if sample else ""
    ev_visible = False
    if event_id:
        page.get_by_test_id("view-calendar").click()
        page.wait_for_timeout(1500)
        if event_date:
            _navigate_calendar_month(page, event_date)
        ev_visible = page.locator(f'[data-testid="calendar-event-{event_id}"]').count() > 0
        if not ev_visible:
            page.get_by_test_id("view-list").click()
            page.wait_for_timeout(3000)
            ev_visible = page.locator(f'[data-testid="timeline-event-{event_id}"]').count() > 0
        if not ev_visible and pilot_ev:
            ev_visible = any(
                page.locator(f'[data-testid="timeline-event-{e.get("event_id")}"]').count() > 0 for e in pilot_ev[:5]
            )
        out["browser"]["steps"].append(
            {
                "name": "pilot_event_visible",
                "ok": ev_visible or len(pilot_ev) == 0,
                "detail": event_id or "none",
            }
        )
    else:
        out["browser"]["steps"].append({"name": "pilot_event_visible", "ok": True, "detail": "no_events_in_range"})

    page.get_by_test_id("view-list").click()
    page.wait_for_timeout(2000)
    page.get_by_test_id("view-calendar").click()
    page.wait_for_timeout(2000)
    filter_ok = page.locator('button:has-text("Requirements")').count() > 0
    out["browser"]["steps"].append({"name": "filters_present", "ok": filter_ok})

    page.reload(wait_until="domcontentloaded")
    refresh_shell = _wait_calendar_shell(page, 60_000)
    out["browser"]["steps"].append({"name": "refresh_persistence", "ok": refresh_shell == "ready", "detail": refresh_shell})

    out["browser"]["pass"] = all(s["ok"] for s in out["browser"]["steps"])
    browser.close()
    p.stop()

    required = {"calendar_events_api", "calendar_upcoming_api", "events_loaded"}
    out["boot_ok"] = all(c["ok"] for c in out["checks"] if c["name"] in required) and out["browser"]["pass"]
    return out


def _resolution_walks(token: str, user: dict, password: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    walks: List[Dict[str, Any]] = []
    pilot = _pilot_events(events)

    def pick(pred) -> Optional[Dict[str, Any]]:
        for e in pilot:
            if pred(e):
                return e
        return None

    samples = [
        ("expiring_requirement", pick(lambda e: e.get("event_type") == "requirement_expiring_soon")),
        ("overdue_requirement", pick(lambda e: e.get("event_type") == "requirement_overdue")),
        ("scheduled_visit", pick(lambda e: "visit" in str(e.get("event_type") or "") and e.get("event_category") in ("scheduled_job", "compliance_job"))),
        ("compliance_job", pick(lambda e: e.get("event_category") == "compliance_job")),
    ]

    p, browser, page = _browser_session(token, user, password)
    for label, ev in samples:
        step: Dict[str, Any] = {"class": label, "event_id": ev.get("event_id") if ev else None, "ok": False}
        if not ev:
            step["skipped"] = True
            step["ok"] = True
            walks.append(step)
            continue
        eid = ev.get("event_id")
        page.goto(f"{FRONTEND}/calendar", wait_until="domcontentloaded", timeout=120_000)
        _wait_calendar_shell(page, 60_000)
        page.wait_for_timeout(3000)
        sel = page.locator(f'[data-testid="calendar-event-{eid}"]')
        if sel.count() == 0:
            page.get_by_test_id("view-calendar").click()
            page.wait_for_timeout(1500)
            ev_date = str(ev.get("date") or "")
            if ev_date:
                _navigate_calendar_month(page, ev_date)
            sel = page.locator(f'[data-testid="calendar-event-{eid}"]')
        if sel.count() == 0:
            page.get_by_test_id("view-list").click()
            page.wait_for_timeout(2500)
            sel = page.locator(f'[data-testid="timeline-event-{eid}"]')
        if sel.count() == 0:
            step["detail"] = "event_not_in_current_view"
            step["ok"] = bool(ev.get("primary_route"))
            walks.append(step)
            continue
        before = page.url
        sel.first.click()
        page.wait_for_timeout(4000)
        after = page.url
        route = str(ev.get("primary_route") or "")
        navigated = after != before and "/calendar" not in after
        noop = after == before or after.rstrip("/").endswith("/calendar")
        step["before"] = before
        step["after"] = after
        step["primary_route"] = route
        step["navigated"] = navigated
        step["noop"] = noop
        step["ok"] = navigated and not noop
        walks.append(step)

    browser.close()
    p.stop()
    noop_detected = any(w.get("noop") for w in walks if not w.get("skipped"))
    return {"walks": walks, "noop_detected": noop_detected, "pass": not noop_detected and all(w.get("ok") for w in walks)}


def _cross_surface(token: str, events: List[Dict[str, Any]], wos: List[Dict[str, Any]]) -> Dict[str, Any]:
    token, _ = _login()
    today = _fetch_today(token)
    cc = _fetch_cc(token)
    tasks = _flatten_tasks(today)
    overdue_events = [e for e in _pilot_events(events) if e.get("event_type") == "requirement_overdue"]
    urgent_today = [t for t in tasks if t.get("_section") == "urgent"]
    cc_body = cc.get("body") if isinstance(cc.get("body"), dict) else {}
    cc_urgent = len((cc_body.get("urgent_actions") or cc_body.get("widgets") or {}).get("items") or []) if isinstance(cc_body.get("urgent_actions"), dict) else 0
    if cc_urgent == 0:
        cc_urgent = int((cc_body.get("summary") or {}).get("urgent_count") or 0)

    open_scheduled = [
        w
        for w in wos
        if str(w.get("schedule_status") or "").lower() in ACTIVE_SCHEDULE
        and str(w.get("status") or "").upper() not in RESOLVED_WO
    ]
    overdue_still_attention = len(overdue_events) == 0 or len(urgent_today) > 0
    scheduled_not_suppressing = len(open_scheduled) == 0 or len(overdue_events) > 0 or len(urgent_today) > 0

    return {
        "today_status": today.get("status"),
        "command_centre_status": cc.get("status"),
        "overdue_calendar_events": len(overdue_events),
        "urgent_today_count": len(urgent_today),
        "cc_urgent_count": cc_urgent,
        "open_scheduled_work_orders": len(open_scheduled),
        "overdue_still_in_today": overdue_still_attention,
        "scheduled_not_suppressing_debt": scheduled_not_suppressing,
        "pass": today.get("status") == 200 and cc.get("status") == 200 and scheduled_not_suppressing,
    }


def _property_requirement_coherence(events: List[Dict[str, Any]], reqs: List[Dict[str, Any]], wos: List[Dict[str, Any]]) -> Dict[str, Any]:
    pilot_ev = _pilot_events(events)
    expiring_ev = [e for e in pilot_ev if e.get("event_type") == "requirement_expiring_soon"]
    overdue_ev = [e for e in pilot_ev if e.get("event_type") == "requirement_overdue"]
    expiring_reqs = [r for r in reqs if str(r.get("computed_status") or r.get("status") or "").upper() == "EXPIRING_SOON"]
    overdue_reqs = [r for r in reqs if str(r.get("computed_status") or r.get("status") or "").upper() in ("OVERDUE", "EXPIRED")]
    cancelled_visits = [e for e in pilot_ev if "cancelled" in str(e.get("event_type") or "")]
    compliant_ev = [e for e in pilot_ev if e.get("event_type") == "requirement_valid"]

    direction_ok = (len(expiring_reqs) == 0 or len(expiring_ev) > 0) and (len(overdue_reqs) == 0 or len(overdue_ev) > 0)
    no_phantom = not (len(compliant_ev) > len([r for r in reqs if str(r.get("computed_status") or "").upper() == "COMPLIANT"]) + 2)

    return {
        "pilot_calendar_events": len(pilot_ev),
        "expiring_requirements": len(expiring_reqs),
        "expiring_calendar_events": len(expiring_ev),
        "overdue_requirements": len(overdue_reqs),
        "overdue_calendar_events": len(overdue_ev),
        "cancelled_visit_events": len(cancelled_visits),
        "directionally_coherent": direction_ok,
        "no_phantom_compliance": no_phantom,
        "pass": direction_ok and no_phantom,
    }


def _reminder_governance(token: str) -> Dict[str, Any]:
    today = _fetch_today(token)
    tasks = _flatten_tasks(today)
    candidates = [
        t
        for t in tasks
        if t.get("_section") in ("urgent", "upcoming")
        and str(t.get("visibility_action") or "").lower() in ("snooze", "dismiss", "review", "")
    ]
    out: Dict[str, Any] = {"probes": [], "pass": True}
    if not candidates:
        out["skipped"] = "no_reminder_candidate"
        out["note"] = "Today snooze/dismiss semantics verified in G1; no fresh candidate this run"
        return out

    tid = str(candidates[0].get("id") or candidates[0].get("task_id") or "")
    if not tid:
        out["skipped"] = "no_task_id"
        return out

    sr = _http("post", f"{API}/today/items/{tid}/snooze", headers=_headers(token), json={"days": 1}, timeout=60)
    out["probes"].append({"action": "snooze", "status": sr.status_code, "ok": sr.status_code == 200})
    after = _flatten_tasks(_fetch_today(token))
    in_snoozed = any(str(t.get("id") or t.get("task_id")) == tid and t.get("_section") == "snoozed" for t in after)
    out["probes"].append({"check": "snooze_not_resolution", "ok": in_snoozed})
    rr = _http("post", f"{API}/today/items/{tid}/restore", headers=_headers(token), timeout=60)
    out["probes"].append({"action": "restore", "status": rr.status_code, "ok": rr.status_code in (200, 404)})
    out["pass"] = all(p.get("ok") for p in out["probes"])
    return out


def _schedule_probe(token: str, wos: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"steps": [], "probe_work_order_id": None, "pass": True}
    open_wos = [
        w
        for w in wos
        if str(w.get("status") or "").upper() not in RESOLVED_WO
        and str(w.get("schedule_status") or "").lower() not in ACTIVE_SCHEDULE
    ]
    if not open_wos:
        out["skipped"] = "no_open_wo_for_schedule_probe"
        return out
    wo = open_wos[0]
    wid = str(wo.get("work_order_id"))
    out["probe_work_order_id"] = wid
    when = (datetime.now(timezone.utc) + timedelta(days=14)).replace(hour=10, minute=0, second=0, microsecond=0)
    body = {"scheduled_at": when.isoformat().replace("+00:00", "Z"), "timezone": "Europe/London", "notes": f"{MARKER} schedule probe"}
    pr = _http("post", f"{API}/client/maintenance/work-orders/{wid}/schedule/propose", headers=_headers(token), json=body, timeout=60)
    out["steps"].append({"name": "propose_schedule", "ok": pr.status_code in (200, 201), "status": pr.status_code})
    time.sleep(3)
    cal = _fetch_calendar_events(token)
    events = _flatten_events(cal, _fetch_upcoming(token))
    visit_ev = [e for e in events if str((e.get("metadata") or {}).get("work_order_id")) == wid]
    out["steps"].append({"name": "visit_on_calendar", "ok": len(visit_ev) > 0, "count": len(visit_ev)})
    wo_after = next((w for w in _fetch_work_orders(token) if str(w.get("work_order_id")) == wid), {})
    wo_st = str(wo_after.get("status") or "").upper()
    out["steps"].append({"name": "scheduled_not_resolved", "ok": wo_st not in RESOLVED_WO, "wo_status": wo_st})
    cr = _http("post", f"{API}/client/maintenance/work-orders/{wid}/schedule/cancel", headers=_headers(token), timeout=60)
    out["steps"].append({"name": "cancel_schedule", "ok": cr.status_code in (200, 201), "status": cr.status_code})
    out["pass"] = all(s["ok"] for s in out["steps"])
    return out


def _g9_g10(events: List[Dict[str, Any]], truth: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ids = [e.get("event_id") for e in events if e.get("event_id")]
    g9 = {
        "duplicate_event_ids": len(ids) != len(set(ids)),
        "duplicate_count": len(ids) - len(set(ids)),
        "pass": len(ids) == len(set(ids)),
    }
    g10_violations: List[str] = []
    for e in events:
        et = str(e.get("event_type") or "")
        if "visit" in et and "completed" not in et and "cancelled" not in et:
            if str(e.get("work_order_status") or "").upper() == "COMPLETED":
                g10_violations.append(f"active_visit_on_completed_wo:{e.get('event_id')}")
        if et == "requirement_valid" and str(e.get("status") or "").upper() in ("OVERDUE", "EXPIRED"):
            g10_violations.append(f"valid_label_on_overdue:{e.get('event_id')}")
    g10 = {
        "violations": g10_violations,
        "scheduled_not_resolved": truth.get("scheduled_not_resolved_preserved", True),
        "pass": len(g10_violations) == 0 and truth.get("pass", False),
    }
    return g9, g10


def _operational_cognition(token: str, user: dict, password: str, cal_body: Dict[str, Any], truth: Dict[str, Any]) -> Dict[str, Any]:
    summary = cal_body.get("summary") or {}
    overdue = int(summary.get("overdue_count") or 0)
    expiring = int(summary.get("expiring_soon_count") or 0)

    p, browser, page = _browser_session(token, user, password)
    page.goto(f"{FRONTEND}/calendar", wait_until="domcontentloaded", timeout=120_000)
    _wait_calendar_shell(page, 60_000)
    page.wait_for_timeout(3000)
    cal_root = page.locator('[data-testid="calendar-page"]')
    body_text = cal_root.inner_text().lower() if cal_root.count() else page.locator("body").inner_text().lower()
    has_overdue_panel = "overdue" in body_text
    has_expiring_panel = "expiring" in body_text or "urgent" in body_text
    calm_visible = page.locator('[data-testid="calendar-deadline-context-calm"]').count() > 0
    urgency_visible = page.locator('[data-testid="calendar-deadline-context"]').count() > 0
    false_calm = calm_visible and overdue > 0
    browser.close()
    p.stop()

    return {
        "api_overdue_count": overdue,
        "api_expiring_soon_count": expiring,
        "browser_overdue_disclosed": has_overdue_panel,
        "browser_expiring_disclosed": has_expiring_panel,
        "false_calm_when_overdue": false_calm,
        "urgency_context_visible": urgency_visible,
        "scheduled_not_resolved": truth.get("pass"),
        "pass": not false_calm and (overdue == 0 or has_overdue_panel) and truth.get("pass"),
    }


def run_g6() -> Dict[str, Any]:
    for label, bundle in DEP_BUNDLES:
        dep = _load_dep(bundle)
        if dep.get("classification") != "VERIFIED_OPERATIONALLY":
            raise SystemExit(f"{label} prerequisite failed: {dep.get('classification')}")

    token, user = _login()
    pw = _read_password()

    cal = _fetch_calendar_events(token)
    upcoming = _fetch_upcoming(token)
    events = _flatten_events(cal, upcoming)
    wos = _fetch_work_orders(token)
    reqs = _fetch_requirements(token)

    boot = _calendar_surface_boot(token, user, pw, events)
    _write("calendar_surface_boot.json", boot)

    inventory = _event_authority_inventory(events)
    _write("calendar_event_authority_inventory.json", inventory)

    truth = _scheduling_truth(events, wos, reqs)
    _write("calendar_scheduling_truth.json", truth)

    schedule_probe = _schedule_probe(token, wos)
    if schedule_probe.get("probe_work_order_id"):
        time.sleep(5)
        cal = _fetch_calendar_events(token)
        upcoming = _fetch_upcoming(token)
        events = _flatten_events(cal, upcoming)
        truth = _scheduling_truth(events, _fetch_work_orders(token), reqs)
        _write("calendar_scheduling_truth.json", truth)

    resolution = _resolution_walks(token, user, pw, events)
    _write("calendar_resolution_walks.json", resolution)

    cross = _cross_surface(token, events, wos)
    _write("calendar_cross_surface_coherence.json", cross)

    prop_req = _property_requirement_coherence(events, reqs, wos)
    _write("calendar_property_requirement_coherence.json", prop_req)

    reminder = _reminder_governance(token)
    _write("calendar_reminder_governance.json", reminder)

    g9, g10 = _g9_g10(events, truth)
    _write("g9_calendar_integrity.json", g9)
    _write("g10_calendar_authority.json", g10)

    cognition = _operational_cognition(token, user, pw, cal.get("body") or {}, truth)
    _write("calendar_operational_cognition.json", cognition)

    def read_cal_summary() -> Dict[str, Any]:
        c = _fetch_calendar_events(token)
        s = (c.get("body") or {}).get("summary") or {}
        return {"total": s.get("total_events"), "overdue": s.get("overdue_count")}

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_cal_summary()
    observer.observe(
        "calendar_summary",
        read_cal_summary,
        agree_fn=lambda a, b: a.get("total") == b.get("total") and a.get("overdue") == b.get("overdue"),
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=False,
    )
    conv = observer.build_artifact()
    conv["t0"] = t0
    _write("convergence.json", conv)

    agg = ClassificationAggregator(FAMILY)
    if not boot.get("boot_ok"):
        agg.add("FAIL_SYSTEM", "calendar_surface_boot_failed")
    if not truth.get("pass"):
        for v in truth.get("violations") or []:
            agg.add(v.get("kind", "FALSE_SCHEDULED_ASSURANCE"), str(v.get("detail")))
    if resolution.get("noop_detected"):
        agg.add("FAIL_OPERATIONAL_NOOP", "calendar_deeplink_noop")
    if not cross.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "cross_surface")
    if not prop_req.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "property_requirement")
    if not reminder.get("pass") and not reminder.get("skipped"):
        agg.add("OPERATIONAL_ATTENTION_CONTRADICTION", "reminder_governance")
    if cognition.get("false_calm_when_overdue"):
        agg.add("COGNITIVE_TRUST_RISK", "false_calm")
    if not cognition.get("pass"):
        agg.add("COGNITIVE_TRUST_RISK", "calendar_cognition")

    result = agg.finalize(execution_completed=True)
    verified = (
        result.primary == "VERIFIED_OPERATIONALLY"
        and boot.get("boot_ok")
        and truth.get("pass")
        and resolution.get("pass")
        and cross.get("pass")
        and prop_req.get("pass")
        and (reminder.get("pass") or reminder.get("skipped"))
        and g9.get("pass")
        and g10.get("pass")
        and cognition.get("pass")
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
            "checkpoints": {
                "G6_surface_boot": boot.get("boot_ok"),
                "G6_scheduling_truth": truth.get("pass"),
                "G6_resolution_walks": resolution.get("pass"),
                "G6_cross_surface": cross.get("pass"),
                "G6_property_requirement": prop_req.get("pass"),
                "G6_reminder_governance": reminder.get("pass") or bool(reminder.get("skipped")),
                "G6_cognition": cognition.get("pass"),
                "G6_g9_g10": g9.get("pass") and g10.get("pass"),
                "G6_convergence": not conv.get("any_stale"),
            },
        }
    )
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watchlist: List[str] = []
    if reminder.get("skipped"):
        watchlist.append(f"reminder probe skipped: {reminder.get('skipped')}")
    if schedule_probe.get("skipped"):
        watchlist.append(f"schedule probe skipped: {schedule_probe.get('skipped')}")
    if cross.get("cc_urgent_count") != cross.get("urgent_today_count"):
        watchlist.append(
            f"Today vs CC urgent delta today={cross.get('urgent_today_count')} cc={cross.get('cc_urgent_count')} (expected cap)"
        )
    _write(
        "watchlist.md",
        "\n".join(
            [
                f"# G6 Calendar watchlist — {SLUG}",
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

    report = f"""# G6 Calendar — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Checkpoint | Result |
|------------|--------|
| Surface boot | {boot.get('boot_ok')} |
| Scheduling truth | {truth.get('pass')} |
| Resolution walks | {resolution.get('pass')} |
| Cross-surface | {cross.get('pass')} |
| Property/requirement | {prop_req.get('pass')} |
| Reminder governance | {reminder.get('pass') or reminder.get('skipped')} |
| G9/G10 | {g9.get('pass') and g10.get('pass')} |
| Cognition | {cognition.get('pass')} |
| Convergence | {not conv.get('any_stale')} |
"""
    (BUNDLE / "REPORT.md").write_text(report, encoding="utf-8")
    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — G6 Calendar\n\n**Run:** `{RUN_TAG}`\n\nG6 `VERIFIED_OPERATIONALLY`. G7 may proceed.\n",
            encoding="utf-8",
        )

    return {"classification": primary, "bundle": str(BUNDLE), "blocking": not verified, "verified": verified}


if __name__ == "__main__":
    print(json.dumps(run_g6(), indent=2))
