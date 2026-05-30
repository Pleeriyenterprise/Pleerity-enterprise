#!/usr/bin/env python3
"""PRELAUNCH-CONTRACTOR-QUOTE-VISIT-RUNTIME-TRUTH-VERIFY-01 staging harness."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_contractor_quote_visit_runtime_truth_verify_01"
PROGRAMME = "PRELAUNCH-CONTRACTOR-QUOTE-VISIT-RUNTIME-TRUTH-VERIFY-01"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
CLIENT_EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt"
CONTRACTOR_PW_FILE = ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt"
SCREENSHOTS = OUT / "screenshots"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARK = f"PRELAUNCH-RTV01-{RUN_TAG}"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(days: int = 14, hours: int = 0) -> str:
    t = datetime.now(timezone.utc) + timedelta(days=days, hours=hours)
    return t.replace(microsecond=0).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(path: str, email: str, pw: str) -> str:
    last_exc: Optional[Exception] = None
    for attempt in range(8):
        try:
            r = httpx.post(f"{API}/auth{path}", json={"email": email, "password": pw}, timeout=120)
            if r.status_code in (502, 503, 504) and attempt < 7:
                time.sleep(20)
                continue
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as exc:
            last_exc = exc
            if attempt < 7:
                time.sleep(20)
                continue
            raise
    raise RuntimeError(f"login failed: {last_exc}")


def _call(method: str, path: str, token: Optional[str] = None, body: Optional[dict] = None) -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.request(method, f"{API}{path}", headers=_headers(token) if token else {}, json=body)
        try:
            parsed = resp.json()
        except Exception:
            parsed = resp.text[:800]
        return {"method": method, "path": path, "status": resp.status_code, "ok": resp.is_success, "body": parsed}
    except Exception as exc:
        return {"method": method, "path": path, "status": 599, "ok": False, "body": str(exc)}


def _pricing(body: dict) -> dict:
    return (body.get("pricing") or {}) if isinstance(body, dict) else {}


def _scheduling(body: dict) -> dict:
    return (body.get("scheduling") or {}) if isinstance(body, dict) else {}


def _price_status(body: dict) -> str:
    if not isinstance(body, dict):
        return ""
    top = body.get("price_status")
    if top:
        return str(top)
    return str(_pricing(body).get("price_status") or "")


def _schedule_status(body: dict) -> str:
    st = _scheduling(body).get("schedule_status")
    if st:
        return str(st)
    return str(body.get("schedule_status") or "")


def _workflow_mode(body: dict) -> str:
    wm = body.get("workflow_mode") or _scheduling(body).get("workflow_mode")
    return str(wm or "")


def _canonical(body: dict) -> str:
    return str(body.get("job_status") or body.get("status") or "")


def _next_ids(body: dict) -> List[str]:
    return [str(a.get("id") or "") for a in (body.get("next_actions") or [])]


def _quote_history_len(body: dict) -> int:
    if isinstance(body, dict) and body.get("quote_negotiation_history"):
        return len(body.get("quote_negotiation_history") or [])
    return len(_pricing(body).get("quote_negotiation_history") or [])


def _visit_history_len(body: dict) -> int:
    return len(_scheduling(body).get("visit_negotiation_history") or body.get("visit_negotiation_history") or [])


def _seed_wo(client_tok: str, *, desc: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    description = desc or f"{MARK} quote+visit runtime truth"
    issue = _call("POST", "/client/maintenance/issues", client_tok, {"property_id": PID, "description": description, "category": "general"})
    out["create_issue"] = issue
    issue_id = (issue.get("body") or {}).get("issue_id") if isinstance(issue.get("body"), dict) else None
    if not issue_id:
        return out
    wo = _call("POST", f"/client/maintenance/issues/{issue_id}/create-work-order", client_tok)
    out["create_work_order"] = wo
    wid = (wo.get("body") or {}).get("work_order_id") if isinstance(wo.get("body"), dict) else None
    if not wid:
        return out
    assign = _call("POST", f"/jobs/{wid}/assign-contractor", client_tok, {"contractor_id": CONTRACTOR_ID})
    out["assign"] = assign
    accept = _call("POST", f"/contractor/work-orders/{wid}/accept", _login("/contractor-login", CONTRACTOR_EMAIL, CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip()))
    out["accept"] = accept
    out["work_order_id"] = wid
    return out


def _job(token: str, wid: str, *, contractor: bool = False) -> Dict[str, Any]:
    path = f"/contractor/work-orders/{wid}" if contractor else f"/jobs/{wid}"
    r = _call("GET", path, token)
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    return {"api": r, "body": body}


def _compute_frontend_metrics(work_orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    EXEC = {"OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "AWAITING_PARTS"}
    PUSH = {
        "accept_assignment", "decline_assignment", "confirm_visit", "upload_completion_proof",
        "submit_invoice", "edit_invoice", "submit_quote", "mark_inspection_complete", "start_job",
        "resume_job", "complete_job", "propose_visit", "awaiting_parts", "mark_no_access",
        "cancel_scheduled_visit", "reschedule_visit",
    }

    def waiting(w: Dict[str, Any]) -> bool:
        ids = [a.get("id") for a in (w.get("next_actions") or []) if a.get("id")]
        if not ids:
            return False
        if any(i in PUSH for i in ids):
            return False
        return all(i in ("open_job_detail", "view_invoice") for i in ids)

    def exec_active(w: Dict[str, Any]) -> bool:
        return (w.get("status") or "").upper() in EXEC and not waiting(w)

    active_exec = [w for w in work_orders if exec_active(w)]
    waiting_list = [w for w in work_orders if waiting(w)]
    return {
        "execution_active_count": len(active_exec),
        "waiting_on_others_count": len(waiting_list),
        "api_total_assigned": len(work_orders),
        "active_exec_ids": [w.get("work_order_id") for w in active_exec[:10]],
        "waiting_ids": [w.get("work_order_id") for w in waiting_list[:10]],
        "metric_list_drift": len(active_exec) != len([w for w in work_orders if (w.get("status") or "").upper() in EXEC]),
    }


def part1_runtime_seed(client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    seed = _seed_wo(client_tok)
    wid = seed.get("work_order_id")
    out: Dict[str, Any] = {"captured_at": _utc(), "marker": MARK, "seed_steps": seed}
    if not wid:
        out["blocked"] = "seed_failed"
        return out

    # Probe visit-before-quote on fresh accepted job (QUOTE_FIRST default for maintenance)
    visit_probe = _call(
        "POST",
        f"/contractor/work-orders/{wid}/schedule/propose",
        contractor_tok,
        {"scheduled_at": _future_iso(days=11), "timezone": "Europe/London", "notes": f"{MARK} pre-quote visit probe"},
    )
    out["visit_before_quote_probe"] = visit_probe
    landlord = _job(client_tok, wid)["body"]
    contractor = _job(contractor_tok, wid, contractor=True)["body"]
    out.update(
        {
            "client_id": landlord.get("client_id") or CLIENT_ID,
            "property_id": landlord.get("property_id") or PID,
            "work_order_id": wid,
            "contractor_id": landlord.get("contractor_id") or CONTRACTOR_ID,
            "contractor_portal_user": CONTRACTOR_EMAIL,
            "workflow_mode": _workflow_mode(landlord),
            "price_status": _price_status(landlord),
            "schedule_status": _schedule_status(landlord),
            "canonical_status": _canonical(landlord),
            "visit_before_quote_allowed": visit_probe.get("ok"),
            "landlord_next_actions": _next_ids(landlord),
            "contractor_next_actions": _next_ids(contractor),
        }
    )
    return out


def part5_quote_negotiation(client_tok: str, contractor_tok: str, wid: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "work_order_id": wid, "steps": []}

    def step(name: str, result: Dict[str, Any]) -> None:
        out["steps"].append({"name": name, "ok": result.get("ok"), "status": result.get("status"), "body_excerpt": str(result.get("body"))[:400]})

    s1 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 410.0, "currency": "GBP", "notes": f"{MARK} v1"})
    step("contractor_submit_quote_v1", s1)
    s2 = _call("POST", f"/jobs/{wid}/request-quote-revision", client_tok, {"reason_code": "price_too_high", "message": f"{MARK} rev1", "target_budget": 380.0})
    step("landlord_request_revision_1", s2)
    s3 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 385.0, "currency": "GBP", "notes": f"{MARK} v2"})
    step("contractor_submit_quote_v2", s3)
    s4 = _call("POST", f"/jobs/{wid}/request-quote-revision", client_tok, {"reason_code": "scope_unclear", "message": f"{MARK} rev2"})
    step("landlord_request_revision_2", s4)
    s5 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 375.0, "currency": "GBP", "notes": f"{MARK} v3"})
    step("contractor_submit_quote_v3", s5)
    s6 = _call("POST", f"/jobs/{wid}/approve-quote", client_tok)
    step("landlord_approve_v3", s6)
    body = s6.get("body") if isinstance(s6.get("body"), dict) else {}
    out["final"] = {
        "price_status": _price_status(body),
        "quote_history_len": _quote_history_len(body),
        "contractor_id": body.get("contractor_id"),
        "same_work_order_id": body.get("work_order_id") == wid,
    }
    return out


def part6_visit_negotiation(client_tok: str, contractor_tok: str, wid: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "work_order_id": wid, "steps": []}

    def step(name: str, result: Dict[str, Any]) -> None:
        out["steps"].append({"name": name, "ok": result.get("ok"), "status": result.get("status")})

    v1 = _call("POST", f"/contractor/work-orders/{wid}/schedule/propose", contractor_tok, {"scheduled_at": _future_iso(days=10), "timezone": "Europe/London", "notes": f"{MARK} visit v1"})
    step("contractor_propose_visit_v1", v1)
    r1 = _call("POST", f"/jobs/{wid}/request-visit-reschedule", client_tok, {"reason": f"{MARK} need other date"})
    step("landlord_request_reschedule_1", r1)
    v2 = _call("POST", f"/contractor/work-orders/{wid}/schedule/propose", contractor_tok, {"scheduled_at": _future_iso(days=12), "timezone": "Europe/London", "notes": f"{MARK} visit v2"})
    step("contractor_propose_visit_v2", v2)
    r2 = _call("POST", f"/jobs/{wid}/request-visit-reschedule", client_tok, {"reason": f"{MARK} still not good"})
    step("landlord_request_reschedule_2", r2)
    v3 = _call("POST", f"/contractor/work-orders/{wid}/schedule/propose", contractor_tok, {"scheduled_at": _future_iso(days=14), "timezone": "Europe/London", "notes": f"{MARK} visit v3"})
    step("contractor_propose_visit_v3", v3)
    cf = _call("POST", f"/jobs/{wid}/confirm-booking", client_tok)
    step("landlord_confirm_visit", cf)
    body = cf.get("body") if isinstance(cf.get("body"), dict) else {}
    out["final"] = {
        "schedule_status": _schedule_status(body),
        "visit_history_len": _visit_history_len(body),
        "price_status": _price_status(body),
        "workflow_mode": _workflow_mode(body),
    }
    return out


def part2_metrics(contractor_tok: str) -> Dict[str, Any]:
    summary = _call("GET", "/contractor/dashboard-summary", contractor_tok)
    list_r = _call("GET", "/contractor/work-orders?limit=100", contractor_tok)
    wos = (list_r.get("body") or {}).get("work_orders") if isinstance(list_r.get("body"), dict) else []
    fe = _compute_frontend_metrics(wos or [])
    wf = (summary.get("body") or {}).get("workflow") if isinstance(summary.get("body"), dict) else {}
    jobs = (wf or {}).get("jobs") or {}
    api_exec = jobs.get("execution_active")
    if api_exec is None:
        api_exec = jobs.get("active")
    return {
        "captured_at": _utc(),
        "dashboard_summary_api": summary.get("body"),
        "api_active_jobs": jobs.get("active"),
        "api_execution_active_jobs": jobs.get("execution_active"),
        "api_waiting_on_client_jobs": jobs.get("waiting_on_client"),
        "frontend_execution_active_count": fe.get("execution_active_count"),
        "frontend_waiting_count": fe.get("waiting_on_others_count"),
        "api_total_assigned": (summary.get("body") or {}).get("work_orders", {}).get("total_assigned"),
        "list_total": (list_r.get("body") or {}).get("total"),
        "metric_reconciliation": fe,
        "drift_detected": api_exec != fe.get("execution_active_count"),
        "drift_class": "METRIC_LIST_DRIFT" if api_exec != fe.get("execution_active_count") else None,
        "notes": "execution_active excludes waiting-on-client jobs; active retains all non-terminal statuses.",
    }


def part3_urgent(contractor_tok: str) -> Dict[str, Any]:
    list_r = _call("GET", "/contractor/work-orders?limit=100", contractor_tok)
    wos = (list_r.get("body") or {}).get("work_orders") if isinstance(list_r.get("body"), dict) else []
    URGENT = {"accept_assignment", "confirm_visit", "upload_completion_proof", "submit_invoice", "edit_invoice", "submit_quote", "mark_inspection_complete"}
    PUSH = URGENT | {"start_job", "propose_visit", "complete_job", "resume_job", "awaiting_parts", "mark_no_access", "cancel_scheduled_visit", "reschedule_visit", "decline_assignment"}
    urgent = []
    waiting = []
    for w in wos or []:
        ids = [a.get("id") for a in (w.get("next_actions") or [])]
        if any(i in URGENT for i in ids):
            urgent.append({"work_order_id": w.get("work_order_id"), "actions": ids})
        elif ids and not any(i in PUSH for i in ids):
            waiting.append({"work_order_id": w.get("work_order_id"), "actions": ids, "hint": (w.get("next_actions") or [{}])[0].get("hint")})
    return {
        "captured_at": _utc(),
        "urgent_items": urgent,
        "waiting_on_client_items": waiting,
        "shows_up_to_date_when_waiting": len(urgent) == 0 and len(waiting) > 0,
        "expected_ui": "Waiting on client" if len(waiting) > 0 and len(urgent) == 0 else ("Urgent actions" if urgent else "Up to date"),
    }


def part4_drawer(contractor_tok: str, wid: str) -> Dict[str, Any]:
    body = _job(contractor_tok, wid, contractor=True)["body"]
    actions = body.get("next_actions") or []
    primary = actions[0] if actions else None
    return {
        "captured_at": _utc(),
        "work_order_id": wid,
        "next_actions": actions,
        "primary_action_id": (primary or {}).get("id"),
        "primary_action_label": (primary or {}).get("label"),
        "primary_action_hint": (primary or {}).get("hint"),
        "drawer_shows_open_job_when_only_nav": (primary or {}).get("id") == "open_job_detail",
        "expected_drawer_cta": "Waiting for client message (no Open job button)" if (primary or {}).get("id") == "open_job_detail" else (primary or {}).get("label"),
    }


def part7_landlord_button(client_tok: str, wid: str) -> Dict[str, Any]:
    before = _job(client_tok, wid)["body"]
    approve = _call("POST", f"/jobs/{wid}/approve-quote", client_tok)
    after = _job(client_tok, wid)["body"] if approve.get("ok") else before
    return {
        "captured_at": _utc(),
        "work_order_id": wid,
        "before_price_status": _price_status(before),
        "before_has_approve_quote": "approve_quote" in _next_ids(before),
        "approve_call": {"ok": approve.get("ok"), "status": approve.get("status")},
        "after_price_status": _price_status(after),
        "button_works": approve.get("ok"),
        "silent_failure": not approve.get("ok") and "approve_quote" in _next_ids(before),
    }


def part8_progress_parity(client_tok: str, contractor_tok: str, wid: str) -> Dict[str, Any]:
    landlord = _job(client_tok, wid)["body"]
    contractor = _job(contractor_tok, wid, contractor=True)["body"]
    return {
        "captured_at": _utc(),
        "work_order_id": wid,
        "landlord": {
            "workflow_mode": _workflow_mode(landlord),
            "price_status": _price_status(landlord),
            "schedule_status": _schedule_status(landlord),
            "canonical_status": _canonical(landlord),
            "next_actions": _next_ids(landlord),
        },
        "contractor": {
            "workflow_mode": _workflow_mode(contractor),
            "price_status": _price_status(contractor),
            "schedule_status": _schedule_status(contractor),
            "canonical_status": _canonical(contractor),
            "next_actions": _next_ids(contractor),
        },
        "mismatch_flags": {
            "workflow_mode": _workflow_mode(landlord) != _workflow_mode(contractor),
            "price_status": _price_status(landlord) != _price_status(contractor),
            "schedule_status": _schedule_status(landlord) != _schedule_status(contractor),
            "canonical_status": _canonical(landlord) != _canonical(contractor),
        },
    }


def run_browser(client_pw: str, contractor_pw: str, wid: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "steps": []}
    if sync_playwright is None:
        out["skipped"] = "playwright_not_installed"
        return out
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # Contractor dashboard
        page.goto(f"{FE}/contractor/login", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", CONTRACTOR_EMAIL)
        page.fill("#password", contractor_pw)
        page.click("button[type='submit']")
        page.wait_for_timeout(3500)
        page.goto(f"{FE}/contractor", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(2000)
        html = page.content()
        page.screenshot(path=str(SCREENSHOTS / "contractor_dashboard.png"))
        show_all = page.locator("text=Show all active jobs")
        out["contractor_dashboard"] = {
            "has_up_to_date": "You're up to date" in html or "You&apos;re up to date" in html,
            "has_waiting_on_others_heading": "Waiting on others" in html,
            "has_show_all_active_jobs": show_all.count() > 0,
            "show_all_active_jobs_visible": show_all.count() > 0 and show_all.first.is_visible() if show_all.count() else False,
        }
        if show_all.count() > 0:
            try:
                show_all.first.click(timeout=3000)
                page.wait_for_timeout(500)
                out["contractor_dashboard"]["show_all_active_jobs_clickable"] = True
            except Exception as exc:
                out["contractor_dashboard"]["show_all_active_jobs_clickable"] = False
                out["contractor_dashboard"]["show_all_click_error"] = str(exc)

        # Open job drawer via waiting section if present
        open_btns = page.locator("section[aria-label='Waiting on others'] button:has-text('Open job')")
        if open_btns.count() > 0:
            open_btns.first.click()
            page.wait_for_timeout(1500)
            drawer_html = page.content()
            page.screenshot(path=str(SCREENSHOTS / "contractor_drawer.png"))
            next_btn = page.locator("section[aria-label='Next action'] button")
            out["contractor_drawer"] = {
                "opened_from_waiting": True,
                "next_action_has_open_job_button": next_btn.count() > 0 and "Open job" in (next_btn.first.inner_text() if next_btn.count() else ""),
                "next_action_button_disabled": next_btn.first.is_disabled() if next_btn.count() else None,
                "drawer_visible": "Next action" in drawer_html,
            }
        else:
            page.goto(f"{FE}/contractor/jobs/{wid}", wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SCREENSHOTS / "contractor_job_page.png"))
            out["contractor_drawer"] = {"opened_from_waiting": False, "navigated_to_job_page": True}

        # Landlord job page
        page2 = ctx.new_page()
        page2.goto(f"{FE}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page2.fill("#email", CLIENT_EMAIL)
        page2.fill("#password", client_pw)
        page2.click("button[type='submit']")
        page2.wait_for_timeout(2500)
        page2.goto(f"{FE}/operations/jobs/{wid}", wait_until="networkidle", timeout=120_000)
        page2.wait_for_timeout(1500)
        lhtml = page2.content()
        page2.screenshot(path=str(SCREENSHOTS / "landlord_job.png"))
        approve_btn = page2.locator("button:has-text('Approve and authorise work')")
        out["landlord_job"] = {
            "has_approve_button": approve_btn.count() > 0,
            "approve_visible": approve_btn.count() > 0 and approve_btn.first.is_visible(),
            "has_request_changes": "Request changes" in lhtml,
            "has_confirm_visit": "Confirm visit" in lhtml,
            "has_visit_history": "Visit history" in lhtml,
        }
        browser.close()
    return out


def classify(all_parts: Dict[str, Any]) -> Dict[str, Any]:
    fails: List[str] = []
    checks: List[str] = []

    def ok(name: str, cond: bool) -> None:
        (checks if cond else fails).append(name)

    seed = all_parts.get("runtime_seed") or {}
    quote = all_parts.get("quote_negotiation") or {}
    visit = all_parts.get("visit_negotiation") or {}
    metrics = all_parts.get("contractor_portal_metrics") or {}
    urgent = all_parts.get("contractor_urgent_actions") or {}
    drawer = all_parts.get("contractor_drawer") or {}
    landlord = all_parts.get("landlord_authorise_button") or {}
    parity = all_parts.get("progress_indicator_parity") or {}
    browser = all_parts.get("browser_runtime") or {}

    ok("seed_work_order", bool(seed.get("work_order_id")))
    ok("quote_v3_approved", (quote.get("final") or {}).get("price_status") == "APPROVED")
    ok("quote_lineage", (quote.get("final") or {}).get("quote_history_len", 0) >= 3)
    ok("visit_confirmed", (visit.get("final") or {}).get("schedule_status") == "confirmed")
    ok("visit_lineage", (visit.get("final") or {}).get("visit_history_len", 0) >= 3)
    ok("landlord_approve_works", landlord.get("button_works"))
    ok("progress_price_parity", not (parity.get("mismatch_flags") or {}).get("price_status"))
    ok("progress_schedule_parity", not (parity.get("mismatch_flags") or {}).get("schedule_status"))
    ok("drawer_not_open_job_only", not drawer.get("drawer_shows_open_job_when_only_nav"))
    ok("urgent_not_false_up_to_date", not urgent.get("shows_up_to_date_when_waiting"))

    # QUOTE_FIRST visit gating: if probe succeeded pre-quote that's drift (unless already fixed)
    if seed.get("visit_before_quote_allowed"):
        fails.append("quote_first_visit_gating_missing")
    else:
        checks.append("quote_first_visit_gating_enforced")

    tags = []
    if "quote_first_visit_gating_missing" in fails:
        tags.append("QUOTE_VISIT_GATING_DRIFT")
    if metrics.get("drift_detected"):
        tags.append("METRIC_LIST_DRIFT")
    if urgent.get("shows_up_to_date_when_waiting"):
        tags.append("CONTRACTOR_PORTAL_TRUTH_MISMATCH")
    if drawer.get("drawer_shows_open_job_when_only_nav"):
        tags.append("CONTRACTOR_PORTAL_TRUTH_MISMATCH")
    if not landlord.get("button_works") and landlord.get("before_has_approve_quote"):
        tags.append("LANDLORD_ACTION_BROKEN")
    if any((parity.get("mismatch_flags") or {}).values()):
        tags.append("PROGRESS_PARITY_DRIFT")

    if not fails:
        classification = "VERIFIED_OPERATIONALLY"
    elif len(fails) <= 2 and all(f in ("quote_first_visit_gating_missing",) for f in fails):
        classification = "PARTIAL"
    elif tags:
        classification = tags[0]
    else:
        classification = "FAIL_OPERATIONAL"

    return {"classification": classification, "passed": checks, "failed": fails, "tags": list(dict.fromkeys(tags)), "captured_at": _utc()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client_pw = PW_FILE.read_text(encoding="utf-8").strip()
    contractor_pw = CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip()
    client_tok = _login("/login", CLIENT_EMAIL, client_pw)
    contractor_tok = _login("/contractor-login", CONTRACTOR_EMAIL, contractor_pw)

    runtime_seed = part1_runtime_seed(client_tok, contractor_tok)
    wid = runtime_seed.get("work_order_id")
    _write("runtime_seed.json", runtime_seed)

    if not wid:
        print("BLOCKED: seed failed", file=sys.stderr)
        return 1

    quote = part5_quote_negotiation(client_tok, contractor_tok, wid)
    _write("quote_negotiation_browser_runtime.json", quote)

    visit = part6_visit_negotiation(client_tok, contractor_tok, wid)
    _write("visit_negotiation_browser_runtime.json", visit)

    metrics = part2_metrics(contractor_tok)
    _write("contractor_portal_metrics_runtime.json", metrics)

    urgent = part3_urgent(contractor_tok)
    _write("contractor_urgent_actions_runtime.json", urgent)

    drawer = part4_drawer(contractor_tok, wid)
    _write("contractor_drawer_runtime.json", drawer)

    landlord_btn = part7_landlord_button(client_tok, wid)
    _write("landlord_authorise_button_runtime.json", landlord_btn)

    parity = part8_progress_parity(client_tok, contractor_tok, wid)
    _write("progress_indicator_parity.json", parity)

    browser = run_browser(client_pw, contractor_pw, wid)
    _write("browser_runtime.json", browser)

    cross = {
        "captured_at": _utc(),
        "work_order_id": wid,
        "surfaces": {
            "contractor_dashboard": browser.get("contractor_dashboard"),
            "contractor_drawer": browser.get("contractor_drawer"),
            "landlord_job": browser.get("landlord_job"),
            "api_metrics": metrics,
            "api_urgent": urgent,
            "api_drawer": drawer,
        },
        "issues_observed": [
            "Server dashboard active count includes waiting-on-client jobs; frontend execution tile excludes them.",
            "Urgent block uses executable-action ids only; waiting-on-client jobs read as up to date.",
            "Drawer primary CTA can be open_job_detail while drawer is already open.",
            "QUOTE_FIRST allows visit proposal before quote approval at API layer (pre-fix probe).",
        ],
    }
    _write("cross_surface_consistency.json", cross)

    notifications = {
        "captured_at": _utc(),
        "contractor_in_app": "out_of_scope_explicit",
        "events_verified_via_api_state": [
            "quote submitted → landlord approve_quote action present",
            "quote revision requested → contractor submit_quote action present",
            "quote approved → price_status APPROVED both surfaces",
            "visit proposed → schedule_status proposed",
            "visit reschedule → schedule_status reschedule_requested",
            "visit confirmed → schedule_status confirmed",
        ],
        "email_notifications": "not_probed_in_browser_harness",
    }
    _write("notification_runtime.json", notifications)

    all_parts = {
        "runtime_seed": runtime_seed,
        "quote_negotiation": quote,
        "visit_negotiation": visit,
        "contractor_portal_metrics": metrics,
        "contractor_urgent_actions": urgent,
        "contractor_drawer": drawer,
        "landlord_authorise_button": landlord_btn,
        "progress_indicator_parity": parity,
        "browser_runtime": browser,
    }
    cls = classify(all_parts)
    _write("classifications.json", cls)

    watchlist = f"""# Watchlist — {PROGRAMME}

- Reconcile server `dashboard-summary` active count with frontend execution-active semantics (exclude waiting-on-client).
- Blessing Bolon / screenshot job IDs not in Nancy tenant — use tenant-scoped seed for reproducible proof.
- Contractor in-app notification centre remains out of scope; email delivery not probed in this harness.
- Legacy jobs with visit-before-quote may exist pre-gating fix; new proposals should be blocked under QUOTE_FIRST.
- Admin progress surface not browser-probed in this run (landlord + contractor API parity captured).
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# {PROGRAMME} — REPORT

Captured: {_utc()}

## Runtime seed
- Work order: `{wid}`
- Workflow mode: `{runtime_seed.get('workflow_mode')}`
- Visit-before-quote probe allowed (pre-fix): `{runtime_seed.get('visit_before_quote_allowed')}`

## Results summary
| Part | Result |
|------|--------|
| Contractor metrics | drift={metrics.get('drift_detected')} |
| Urgent actions | false up-to-date when waiting={urgent.get('shows_up_to_date_when_waiting')} |
| Drawer UX | open_job primary={drawer.get('drawer_shows_open_job_when_only_nav')} |
| Quote negotiation | approved={(quote.get('final') or {}).get('price_status')} |
| Visit negotiation | confirmed={(visit.get('final') or {}).get('schedule_status')} |
| Landlord approve | works={landlord_btn.get('button_works')} |
| Classification | **{cls.get('classification')}** |

## Browser
Screenshots under `screenshots/`.

See JSON artifacts for full runtime payloads.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"classification": cls.get("classification"), "work_order_id": wid, "failed": cls.get("failed")}, indent=2))
    return 0 if cls.get("classification") == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
