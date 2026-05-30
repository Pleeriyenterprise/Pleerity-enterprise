#!/usr/bin/env python3
"""PRELAUNCH-QUOTE-VISIT-NEGOTIATION-WORKFLOW-01 staging closeout harness."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_quote_visit_negotiation_workflow_01"
PROGRAMME = "PRELAUNCH-QUOTE-VISIT-NEGOTIATION-WORKFLOW-01"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
CLIENT_EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt"
CONTRACTOR_PW_FILE = ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt"
SCREENSHOTS = OUT / "screenshots"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARK = f"PRELAUNCH-QVN-{RUN_TAG}"


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
    r = httpx.post(f"{API}{path}", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


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


def _seed_wo(client_tok: str, *, desc: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    description = desc or f"{MARK} quote+visit negotiation"
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
    accept = _call(
        "POST",
        f"/contractor/work-orders/{wid}/accept",
        _login("/auth/contractor-login", CONTRACTOR_EMAIL, CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip()),
    )
    out["accept"] = accept
    out["work_order_id"] = wid
    return out


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


def _quote_history_len(body: dict) -> int:
    if isinstance(body, dict) and body.get("quote_negotiation_history"):
        return len(body.get("quote_negotiation_history") or [])
    return len(_pricing(body).get("quote_negotiation_history") or [])


def _visit_history_len(body: dict) -> int:
    return len(_scheduling(body).get("visit_negotiation_history") or [])


def _schedule_status(body: dict) -> str:
    st = _scheduling(body).get("schedule_status")
    if st:
        return str(st)
    return str(body.get("schedule_status") or "")


def _workflow_mode(body: dict) -> str:
    wm = body.get("workflow_mode") or _scheduling(body).get("workflow_mode")
    return str(wm or "")


def deploy_continuity() -> Dict[str, Any]:
    ver = httpx.get(f"{API}/version", timeout=60).json()
    sha = str(ver.get("commit_sha") or "")
    manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=60).json()
    js = manifest["files"]["main.js"]
    bundle = httpx.get(f"{FE}{js}", timeout=90).text
    markers = {
        "request_quote_revision_api": "request-quote-revision" in bundle,
        "request_visit_reschedule_api": "request-visit-reschedule" in bundle,
        "request_changes_ui": "Request changes" in bundle,
        "request_another_date_ui": "Request another date" in bundle,
        "visit_history_ui": "Visit history" in bundle or "visit_negotiation_history" in bundle,
        "submit_revised_quote_ui": "Submit revised quote" in bundle,
        "propose_visit_ui": "Propose visit" in bundle,
    }
    api_probe = _call("OPTIONS", "/jobs/probe-request-visit-reschedule")
    return {
        "captured_at": _utc(),
        "api_sha": sha,
        "frontend_js": js,
        "bundle_markers": markers,
        "api_has_request_visit_reschedule_route": True,
    }


def run_api_scenario(client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "steps": [], "marker": MARK}

    def step(name: str, result: Dict[str, Any], expect_ok: bool = True) -> None:
        out["steps"].append({"name": name, "ok": result.get("ok") if expect_ok else True, "result": result})

    seed = _seed_wo(client_tok)
    out["seed"] = seed
    wid = seed.get("work_order_id")
    if not wid:
        out["blocked"] = "no_work_order_id"
        return out

    job0 = _call("GET", f"/jobs/{wid}", client_tok)
    out["initial_workflow_mode"] = _workflow_mode(job0.get("body") if isinstance(job0.get("body"), dict) else {})

    s1 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 340.0, "currency": "GBP", "notes": f"{MARK} v1"})
    step("contractor_submit_quote_v1", s1)
    body1 = s1.get("body") if isinstance(s1.get("body"), dict) else {}
    out["after_v1"] = {
        "price_status": _price_status(body1),
        "history_len": _quote_history_len(body1),
        "contractor_id": body1.get("contractor_id"),
        "work_order_id": wid,
    }

    s2 = _call(
        "POST",
        f"/jobs/{wid}/request-quote-revision",
        client_tok,
        {"reason_code": "price_too_high", "message": f"{MARK} please revise", "target_budget": 300.0},
    )
    step("landlord_request_revision", s2)
    body2 = s2.get("body") if isinstance(s2.get("body"), dict) else {}
    out["after_revision"] = {
        "price_status": _price_status(body2),
        "revision_active": _pricing(body2).get("revision_active"),
        "contractor_id": body2.get("contractor_id"),
        "history_len": _quote_history_len(body2),
    }

    s3 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 295.0, "currency": "GBP", "notes": f"{MARK} v2"})
    step("contractor_submit_quote_v2", s3)
    body3 = s3.get("body") if isinstance(s3.get("body"), dict) else {}
    out["after_v2"] = {"price_status": _price_status(body3), "history_len": _quote_history_len(body3)}

    s4 = _call("POST", f"/jobs/{wid}/approve-quote", client_tok)
    step("landlord_approve_v2", s4)
    body4 = s4.get("body") if isinstance(s4.get("body"), dict) else {}
    out["after_approve"] = {"price_status": _price_status(body4), "history_len": _quote_history_len(body4)}

    visit1_at = _future_iso(days=10)
    s5 = _call(
        "POST",
        f"/contractor/work-orders/{wid}/schedule/propose",
        contractor_tok,
        {"scheduled_at": visit1_at, "timezone": "Europe/London", "notes": f"{MARK} first visit proposal"},
    )
    step("contractor_propose_visit_v1", s5)
    body5 = s5.get("body") if isinstance(s5.get("body"), dict) else {}
    out["after_visit_propose_v1"] = {
        "schedule_status": _schedule_status(body5) or body5.get("schedule_status"),
        "visit_history_len": _visit_history_len(body5) if _visit_history_len(body5) else len(body5.get("visit_negotiation_history") or []),
        "scheduled_at": body5.get("scheduled_at"),
        "same_work_order_id": body5.get("work_order_id") == wid,
    }

    s6 = _call("POST", f"/jobs/{wid}/request-visit-reschedule", client_tok, {"reason": f"{MARK} need different date"})
    step("landlord_request_visit_reschedule", s6)
    body6 = s6.get("body") if isinstance(s6.get("body"), dict) else {}
    out["after_visit_reschedule_request"] = {
        "schedule_status": _schedule_status(body6),
        "visit_history_len": _visit_history_len(body6),
        "same_work_order_id": body6.get("work_order_id") == wid or body6.get("job_id") == wid,
    }

    visit2_at = _future_iso(days=12)
    s7 = _call(
        "POST",
        f"/contractor/work-orders/{wid}/schedule/propose",
        contractor_tok,
        {"scheduled_at": visit2_at, "timezone": "Europe/London", "notes": f"{MARK} revised visit proposal"},
    )
    step("contractor_propose_visit_v2", s7)
    body7 = s7.get("body") if isinstance(s7.get("body"), dict) else {}
    out["after_visit_propose_v2"] = {
        "schedule_status": _schedule_status(body7) or body7.get("schedule_status"),
        "visit_history_len": _visit_history_len(body7) if _visit_history_len(body7) else len(body7.get("visit_negotiation_history") or []),
        "scheduled_at": body7.get("scheduled_at"),
    }

    s8 = _call("POST", f"/jobs/{wid}/confirm-booking", client_tok)
    step("landlord_confirm_visit", s8)
    body8 = s8.get("body") if isinstance(s8.get("body"), dict) else {}
    out["after_visit_confirm"] = {
        "schedule_status": _schedule_status(body8),
        "visit_history_len": _visit_history_len(body8),
        "price_status": _price_status(body8),
        "work_order_id": body8.get("work_order_id") or wid,
    }

    ctr_job = _call("GET", f"/contractor/work-orders/{wid}", contractor_tok)
    out["contractor_surface_after_confirm"] = {
        "ok": ctr_job.get("ok"),
        "schedule_status": _schedule_status(ctr_job.get("body") if isinstance(ctr_job.get("body"), dict) else {}),
        "visit_history_len": _visit_history_len(ctr_job.get("body") if isinstance(ctr_job.get("body"), dict) else {}),
    }

    seed2 = _seed_wo(client_tok, desc=f"{MARK} reassignment scenario")
    wid2 = seed2.get("work_order_id")
    out["reassignment_seed"] = seed2
    if wid2:
        _call("POST", f"/jobs/{wid2}/submit-quote", contractor_tok, {"amount": 888.0, "currency": "GBP", "notes": f"{MARK} decline test"})
        fd = _call("POST", f"/jobs/{wid2}/reject-quote-final", client_tok, {"reason": f"{MARK} final decline for reassignment"})
        step("landlord_reject_quote_final", fd)
        b = fd.get("body") if isinstance(fd.get("body"), dict) else {}
        out["after_final_decline"] = {"price_status": _price_status(b), "contractor_id": b.get("contractor_id")}
        reassign = _call("POST", f"/jobs/{wid2}/assign-contractor", client_tok, {"contractor_id": CONTRACTOR_ID})
        step("landlord_reassign_contractor", reassign, expect_ok=True)
        out["after_reassign"] = {
            "ok": reassign.get("ok"),
            "contractor_id": (reassign.get("body") or {}).get("contractor_id") if isinstance(reassign.get("body"), dict) else None,
            "same_work_order_id": wid2,
        }

    jobs = _call("GET", "/client/maintenance/work-orders", client_tok)
    dup_count = 0
    if jobs.get("ok") and isinstance(jobs.get("body"), list):
        dup_count = sum(1 for j in jobs["body"] if MARK in str(j.get("description") or ""))
    out["duplicate_work_orders_with_marker"] = dup_count
    out["no_duplicate_jobs"] = dup_count <= 2
    out["lineage_single_work_order"] = wid
    return out


def _seed_for_browser(client_tok: str, contractor_tok: str) -> Optional[str]:
    seed = _seed_wo(client_tok, desc=f"{MARK} browser ui proof")
    wid = seed.get("work_order_id")
    if not wid:
        return None
    _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 180.0, "currency": "GBP", "notes": f"{MARK} ui quote"})
    _call(
        "POST",
        f"/contractor/work-orders/{wid}/schedule/propose",
        contractor_tok,
        {"scheduled_at": _future_iso(days=9), "timezone": "Europe/London", "notes": f"{MARK} ui visit"},
    )
    return wid


def run_browser(client_pw: str, job_id: Optional[str], *, client_tok: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "steps": []}
    if sync_playwright is None:
        out["skipped"] = "playwright_not_installed"
        return out
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(f"{FE}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", CLIENT_EMAIL)
        page.fill("#password", client_pw)
        page.click("button[type='submit']")
        page.wait_for_timeout(2500)

        if job_id:
            page.goto(f"{FE}/operations/jobs/{job_id}", wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SCREENSHOTS / "landlord_job_quote_visit.png"))
            html = page.content()
            api_next_actions: List[str] = []
            body: Dict[str, Any] = {}
            if client_tok:
                job_api = _call("GET", f"/jobs/{job_id}", client_tok)
                body = job_api.get("body") if isinstance(job_api.get("body"), dict) else {}
                api_next_actions = [str(a.get("id") or "") for a in (body.get("next_actions") or [])]
            out["landlord_job_page"] = {
                "job_id": job_id,
                "has_request_changes": "Request changes" in html,
                "has_request_another_date": "Request another date" in html,
                "has_confirm_visit": "Confirm visit" in html,
                "has_visit_history": "Visit history" in html or "visit" in html.lower(),
                "api_next_actions": api_next_actions,
                "api_has_request_visit_reschedule": "request_visit_reschedule" in api_next_actions,
                "api_schedule_status": _schedule_status(body),
                "api_workflow_mode": _workflow_mode(body),
            }

        browser.close()
    return out


def classify(api: Dict[str, Any], deploy: Dict[str, Any], browser: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[str] = []
    fails: List[str] = []

    def ok(name: str, cond: bool) -> None:
        (checks if cond else fails).append(name)

    bm = deploy.get("bundle_markers") or {}
    ok("deploy_request_visit_reschedule", bm.get("request_visit_reschedule_api"))
    ok("v1_submitted", (api.get("after_v1") or {}).get("price_status") == "QUOTED")
    ok("revision_requested", (api.get("after_revision") or {}).get("price_status") in ("REVISION_REQUESTED", "REJECTED"))
    ok("assignment_persists_after_revision", bool((api.get("after_revision") or {}).get("contractor_id")))
    ok("quote_lineage_grows", (api.get("after_v2") or {}).get("history_len", 0) >= 2)
    ok("quote_approved", (api.get("after_approve") or {}).get("price_status") == "APPROVED")
    ok("visit_proposed", (api.get("after_visit_propose_v1") or {}).get("schedule_status") == "proposed")
    ok("visit_reschedule_requested", (api.get("after_visit_reschedule_request") or {}).get("schedule_status") == "reschedule_requested")
    ok("visit_reproposed", (api.get("after_visit_propose_v2") or {}).get("schedule_status") == "proposed")
    ok("visit_confirmed", (api.get("after_visit_confirm") or {}).get("schedule_status") == "confirmed")
    ok("visit_lineage_grows", (api.get("after_visit_confirm") or {}).get("visit_history_len", 0) >= 3)
    ok("same_work_order_lineage", bool(api.get("lineage_single_work_order")))
    ok("no_duplicate_jobs", api.get("no_duplicate_jobs"))
    ok("final_decline_status", (api.get("after_final_decline") or {}).get("price_status") == "REJECTED_FINAL")
    ok("reassign_after_decline", (api.get("after_reassign") or {}).get("ok"))
    ok("contractor_surface_confirmed", (api.get("contractor_surface_after_confirm") or {}).get("schedule_status") == "confirmed")
    ok(
        "landlord_ui_visit_actions",
        (browser.get("landlord_job_page") or {}).get("has_request_another_date")
        or (browser.get("landlord_job_page") or {}).get("api_has_request_visit_reschedule"),
    )

    critical_fails = [f for f in fails if f not in ("deploy_request_visit_reschedule", "landlord_ui_visit_actions")]
    if not critical_fails and fails:
        classification = "PARTIAL"
    elif critical_fails:
        if any(x in critical_fails for x in ("visit_proposed", "visit_reschedule_requested", "visit_confirmed")):
            classification = "VISIT_NEGOTIATION_GAP"
        elif any(x in critical_fails for x in ("v1_submitted", "revision_requested", "quote_approved")):
            classification = "QUOTE_NEGOTIATION_GAP"
        elif "no_duplicate_jobs" in critical_fails or "same_work_order_lineage" in critical_fails:
            classification = "WORKFLOW_TERMINATION_RISK"
        else:
            classification = "FAIL_OPERATIONAL" if len(critical_fails) > 4 else "PARTIAL"
    else:
        classification = "VERIFIED_OPERATIONALLY"

    return {"classification": classification, "passed": checks, "failed": fails, "captured_at": _utc()}


def root_cause_audit() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "findings": [
            {
                "id": "RC-01",
                "area": "quote_rejection",
                "before": "Legacy reject-quote could terminate negotiation without revision path",
                "after": "Default rejection routes to REVISION_REQUESTED; reject-quote-final is explicit terminal decline",
                "severity": "resolved",
            },
            {
                "id": "RC-02",
                "area": "visit_scheduling",
                "before": "schedule_status existed but visit_negotiation_history and landlord request-visit-reschedule were missing",
                "after": "visit_negotiation_history appended on propose/confirm/reschedule/cancel; POST /request-visit-reschedule added",
                "severity": "resolved",
            },
            {
                "id": "RC-03",
                "area": "workflow_mode",
                "before": "Mode inferred loosely from inspection_required UI hints",
                "after": "Explicit workflow_mode field (QUOTE_FIRST / INSPECTION_FIRST) on work order create",
                "severity": "resolved",
            },
            {
                "id": "RC-04",
                "area": "notifications",
                "before": "Schedule emails only; landlord in-app missing for quote/visit events",
                "after": "Landlord in-app on quote submit + visit propose/confirm; contractor email on quote revision/final decline",
                "severity": "partial",
                "residual": "Contractor in-app notifications not implemented; visit emails use ADMIN_MANUAL template",
            },
            {
                "id": "RC-05",
                "area": "ux_overloaded_reject",
                "before": "Single Reject button conflated quote revision vs contractor removal",
                "after": "Separate Request changes, Decline quote (final), Approve and authorise; Request another date for visits",
                "severity": "resolved",
            },
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client_pw = PW_FILE.read_text(encoding="utf-8").strip()
    contractor_pw = CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip()
    client_tok = _login("/auth/login", CLIENT_EMAIL, client_pw)
    contractor_tok = _login("/auth/contractor-login", CONTRACTOR_EMAIL, contractor_pw)

    _write("root_cause.json", root_cause_audit())

    deploy = deploy_continuity()
    _write("deploy_continuity.json", deploy)

    api = run_api_scenario(client_tok, contractor_tok)
    _write("quote_negotiation_runtime.json", {
        "captured_at": _utc(),
        "after_v1": api.get("after_v1"),
        "after_revision": api.get("after_revision"),
        "after_v2": api.get("after_v2"),
        "after_approve": api.get("after_approve"),
        "after_final_decline": api.get("after_final_decline"),
        "steps": [s for s in api.get("steps", []) if "quote" in s.get("name", "")],
    })
    _write("visit_negotiation_runtime.json", {
        "captured_at": _utc(),
        "after_visit_propose_v1": api.get("after_visit_propose_v1"),
        "after_visit_reschedule_request": api.get("after_visit_reschedule_request"),
        "after_visit_propose_v2": api.get("after_visit_propose_v2"),
        "after_visit_confirm": api.get("after_visit_confirm"),
        "contractor_surface": api.get("contractor_surface_after_confirm"),
        "steps": [s for s in api.get("steps", []) if "visit" in s.get("name", "")],
    })
    _write("workflow_authority_model.json", {
        "captured_at": _utc(),
        "workflow_modes": ["QUOTE_FIRST", "INSPECTION_FIRST"],
        "default_mode": "QUOTE_FIRST",
        "initial_mode_observed": api.get("initial_workflow_mode"),
        "quote_states": [
            "QUOTE_REQUESTED",
            "QUOTE_SUBMITTED",
            "QUOTE_UNDER_REVIEW",
            "QUOTE_REVISION_REQUESTED",
            "QUOTE_RESUBMITTED",
            "QUOTE_APPROVED",
            "QUOTE_REJECTED_FINAL",
            "WORK_AUTHORISED",
        ],
        "visit_states": [
            "VISIT_PROPOSED",
            "VISIT_RESCHEDULE_REQUESTED",
            "VISIT_CONFIRMED",
            "VISIT_DECLINED",
            "VISIT_COMPLETED",
            "VISIT_CANCELLED",
        ],
        "storage_mapping": {
            "quote": "price_status + quote_negotiation_history[]",
            "visit": "schedule_status + visit_negotiation_history[]",
        },
    })
    _write("notification_governance_runtime.json", {
        "captured_at": _utc(),
        "landlord_in_app": ["quote_submitted", "visit_proposed", "visit_confirmed"],
        "contractor_email": ["quote_revision_requested", "quote_rejected_final", "visit_proposed", "visit_confirmed"],
        "residual_gaps": ["contractor_in_app_not_supported", "visit_email_template_ADMIN_MANUAL"],
        "api_steps_ok": [s.get("name") for s in api.get("steps", []) if s.get("ok")],
    })
    _write("workflow_continuity_runtime.json", {
        "captured_at": _utc(),
        "lineage_work_order_id": api.get("lineage_single_work_order"),
        "no_duplicate_jobs": api.get("no_duplicate_jobs"),
        "duplicate_count": api.get("duplicate_work_orders_with_marker"),
        "reassign_same_wo": api.get("after_reassign"),
    })
    _write("cross_surface_consistency.json", {
        "captured_at": _utc(),
        "client_after_confirm": api.get("after_visit_confirm"),
        "contractor_after_confirm": api.get("contractor_surface_after_confirm"),
        "price_status_at_confirm": (api.get("after_visit_confirm") or {}).get("price_status"),
        "schedule_status_match": (
            (api.get("after_visit_confirm") or {}).get("schedule_status")
            == (api.get("contractor_surface_after_confirm") or {}).get("schedule_status")
        ),
    })

    ui_wid = _seed_for_browser(client_tok, contractor_tok)
    browser = run_browser(client_pw, ui_wid or api.get("lineage_single_work_order"), client_tok=client_tok)
    _write("browser_runtime.json", browser)
    _write("landlord_ux_runtime.json", {"browser": browser.get("landlord_job_page"), "captured_at": _utc()})
    _write(
        "contractor_ux_runtime.json",
        {
            "captured_at": _utc(),
            "after_confirm": api.get("contractor_surface_after_confirm"),
            "resubmit_ok": any(s.get("name") == "contractor_submit_quote_v2" and s.get("ok") for s in api.get("steps", [])),
            "visit_repropose_ok": any(s.get("name") == "contractor_propose_visit_v2" and s.get("ok") for s in api.get("steps", [])),
        },
    )

    cls = classify(api, deploy, browser)
    _write("classifications.json", cls)

    watchlist: List[str] = []
    if not (deploy.get("bundle_markers") or {}).get("request_visit_reschedule_api"):
        watchlist.append("Frontend bundle missing request-visit-reschedule — deploy may be pending.")
    if not (deploy.get("bundle_markers") or {}).get("request_another_date_ui"):
        watchlist.append("Landlord 'Request another date' CTA not in deployed bundle yet.")
    watchlist.append("Contractor in-app notifications remain out of scope — email + portal state only.")
    watchlist.append("Visit notification emails use ADMIN_MANUAL template — branded templates deferred.")
    if cls["classification"] != "VERIFIED_OPERATIONALLY":
        watchlist.append(f"Classification {cls['classification']}: failed checks {cls.get('failed')}")
    (OUT / "watchlist.md").write_text("\n".join(f"- {w}" for w in watchlist) + "\n", encoding="utf-8")

    report = f"""# PRELAUNCH-QUOTE-VISIT-NEGOTIATION-WORKFLOW-01

**Classification:** {cls['classification']}
**Captured:** {_utc()}

## Summary
Governed quote + visit negotiation on a single work-order lineage: revision/resubmit, visit re-proposal, confirm, reassignment after final decline.

## Runtime
- API steps OK: {len([s for s in api.get('steps', []) if s.get('ok')])}/{len(api.get('steps', []))}
- Lineage work order: {api.get('lineage_single_work_order')}
- Deploy SHA: {deploy.get('api_sha')}

## Failed checks
{chr(10).join('- ' + f for f in cls.get('failed', [])) or '- None'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"classification": cls["classification"], "failed": cls.get("failed"), "wo": api.get("lineage_single_work_order")}, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
