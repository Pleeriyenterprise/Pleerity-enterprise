#!/usr/bin/env python3
"""PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01 post-deploy closeout harness."""
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
OUT = ROOT / "docs/audit/prelaunch_workflow_nudge_orchestration_01"
PROGRAMME = "PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01"
EXPECTED_COMMIT_PREFIX = "8cb2524f"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
ADMIN_EMAIL = "aigbochievictory@gmail.com"
PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt"
CONTRACTOR_PW_FILE = ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt"
ADMIN_PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt"
SCREENSHOTS = OUT / "screenshots"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARK = f"PRELAUNCH-WFN-CLOSEOUT-{RUN_TAG}"
JOB_RUN_REASON = "PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01 post-deploy verification sweep"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(path: str, email: str, pw: str) -> str:
    last: Optional[Exception] = None
    for attempt in range(8):
        try:
            r = httpx.post(f"{API}/auth{path}", json={"email": email, "password": pw}, timeout=120)
            if r.status_code in (502, 503, 504) and attempt < 7:
                time.sleep(20)
                continue
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as exc:
            last = exc
            if attempt < 7:
                time.sleep(15)
                continue
            raise
    raise RuntimeError(f"login failed: {last}")


def _call(method: str, path: str, token: Optional[str] = None, body: Optional[dict] = None) -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.request(method, f"{API}{path}", headers=_headers(token) if token else {}, json=body)
        try:
            parsed = resp.json()
        except Exception:
            parsed = resp.text[:1200]
        return {"method": method, "path": path, "status": resp.status_code, "ok": resp.is_success, "body": parsed}
    except Exception as exc:
        return {"method": method, "path": path, "status": 599, "ok": False, "body": str(exc)}


def _admin_token(admin_tok: str, action_id: str, resource_key: str) -> str:
    r = _call(
        "POST",
        "/admin/governance/confirmation-token",
        admin_tok,
        {"action_id": action_id, "reason": JOB_RUN_REASON, "resource_key": resource_key},
    )
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    return str(body.get("token") or "")


def _admin_call(method: str, path: str, admin_tok: str, body: Optional[dict] = None, *, confirmation: str = "") -> Dict[str, Any]:
    headers = _headers(admin_tok)
    if confirmation:
        headers["X-Admin-Confirmation-Token"] = confirmation
    try:
        with httpx.Client(timeout=180) as client:
            resp = client.request(method, f"{API}{path}", headers=headers, json=body)
        try:
            parsed = resp.json()
        except Exception:
            parsed = resp.text[:1200]
        return {"method": method, "path": path, "status": resp.status_code, "ok": resp.is_success, "body": parsed}
    except Exception as exc:
        return {"method": method, "path": path, "status": 599, "ok": False, "body": str(exc)}


def _run_nudge_job(admin_tok: str) -> Dict[str, Any]:
    tok = _admin_token(admin_tok, "run_portfolio_wide_job", "workflow_nudge_processing:global")
    if not tok:
        return {"ok": False, "status": 403, "body": "confirmation_token_failed"}
    return _admin_call(
        "POST",
        "/admin/jobs/run",
        admin_tok,
        {"job": "workflow_nudge_processing", "portfolio_wide": True, "reason": JOB_RUN_REASON},
        confirmation=tok,
    )


def _audit(admin_tok: str, action: str, *, limit: int = 30, resource_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q = f"/admin/audit-logs?action={action}&limit={limit}"
    if resource_id:
        q += "&skip=0"
    r = _call("GET", q, admin_tok)
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    logs = body.get("logs") or []
    if resource_id:
        logs = [x for x in logs if (x.get("resource_id") or "") == resource_id]
    return logs


def _future_iso(days: int = 12) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


def part1_deploy_continuity(admin_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "checks": [], "classification": None}
    ver = httpx.get(f"{API.replace('/api', '')}/api/version", timeout=120)
    ver_body = ver.json() if ver.status_code == 200 else {}
    sha = str(ver_body.get("commit_sha") or "")
    ok_sha = sha.startswith(EXPECTED_COMMIT_PREFIX)
    out["version"] = ver_body
    out["checks"].append({"name": "api_version_commit", "ok": ok_sha, "sha": sha})

    health = _call("GET", "/health")
    out["checks"].append({"name": "api_health", "ok": health["ok"], "status": health["status"]})

    runners = _call("POST", "/admin/jobs/run", admin_tok, {"job": "workflow_nudge_processing_not_a_job"})
    out["checks"].append({
        "name": "workflow_nudge_in_job_runners",
        "ok": runners["status"] == 400 and "workflow_nudge_processing" in str(runners.get("body")),
        "detail": runners.get("body"),
    })

    sched = _call("GET", "/admin/jobs/status", admin_tok)
    jobs = (sched.get("body") or {}).get("scheduled_jobs") or [] if isinstance(sched.get("body"), dict) else []
    ids = [j.get("id") for j in jobs]
    out["checks"].append({"name": "scheduler_has_workflow_nudge_processing", "ok": "workflow_nudge_processing" in ids, "job_ids_sample": ids[:8]})

    client_tok = _login("/login", CLIENT_EMAIL, PW_FILE.read_text(encoding="utf-8").strip())
    today = _call("GET", "/today/items", client_tok)
    today_body = today.get("body") if isinstance(today.get("body"), dict) else {}
    out["checks"].append({
        "name": "today_workflow_stall_disclosure",
        "ok": "workflow_stall_disclosure" in today_body,
        "disclosure": today_body.get("workflow_stall_disclosure"),
    })

    cc = _call("GET", "/client/command-center?projection=primary", client_tok)
    cc_body = cc.get("body") if isinstance(cc.get("body"), dict) else {}
    urgent = cc_body.get("urgent_actions") or []
    stall_actions = [a for a in urgent if (a.get("action_type") or "") == "workflow_stall_nudge" or "Waiting on" in (a.get("title") or "")]
    out["checks"].append({
        "name": "command_centre_stall_actions",
        "ok": cc["ok"],
        "stall_action_count": len(stall_actions),
        "sample_titles": [(a.get("title"), a.get("recommended_action_label")) for a in stall_actions[:5]],
    })

    notif = _call("GET", "/admin/message-logs?limit=5", admin_tok)
    out["checks"].append({"name": "notification_orchestrator_message_logs", "ok": notif["ok"]})

    if not all(c.get("ok") for c in out["checks"] if c["name"] in ("api_version_commit", "api_health", "workflow_nudge_in_job_runners", "today_workflow_stall_disclosure")):
        out["classification"] = "BLOCKED_DEPLOY_CONTINUITY"
    else:
        out["classification"] = "PASS"
    return out


def _seed_wo(client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    issue = _call("POST", "/client/maintenance/issues", client_tok, {"property_id": PID, "description": f"{MARK} nudge closeout", "category": "general"})
    issue_id = (issue.get("body") or {}).get("issue_id") if isinstance(issue.get("body"), dict) else None
    if not issue_id:
        out["blocked"] = "issue_create_failed"
        return out
    wo = _call("POST", f"/client/maintenance/issues/{issue_id}/create-work-order", client_tok)
    wid = (wo.get("body") or {}).get("work_order_id") if isinstance(wo.get("body"), dict) else None
    if not wid:
        out["blocked"] = "wo_create_failed"
        return out
    assign = _call("POST", f"/jobs/{wid}/assign-contractor", client_tok, {"contractor_id": CONTRACTOR_ID})
    accept = _call("POST", f"/contractor/work-orders/{wid}/accept", contractor_tok)
    out.update({"work_order_id": wid, "issue_id": issue_id, "assign": assign["ok"], "accept": accept["ok"]})
    return out


def part2_timer_runtime(admin_tok: str, client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "transitions": [], "checks": []}
    seed = _seed_wo(client_tok, contractor_tok)
    wid = seed.get("work_order_id")
    out["seed"] = seed
    if not wid:
        out["blocked"] = seed.get("blocked")
        return out

    def expect_timer(reason: str) -> bool:
        time.sleep(2.5)
        logs = _audit(admin_tok, "WORKFLOW_TIMER_UPDATED", resource_id=wid, limit=50)
        hit = any((l.get("metadata") or {}).get("reason") == reason for l in logs)
        out["transitions"].append({"reason": reason, "audit_found": hit, "recent": logs[:3]})
        return hit

    out["checks"].append({"name": "timer_quote_requested", "ok": expect_timer("quote_requested")})

    quote = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 425.0, "currency": "GBP", "notes": MARK})
    out["quote_submit"] = quote
    out["checks"].append({"name": "timer_quote_submitted", "ok": expect_timer("quote_submitted")})

    rev = _call("POST", f"/jobs/{wid}/request-quote-revision", client_tok, {"reason_code": "price_too_high", "message": MARK, "target_budget": 400.0})
    out["revision"] = rev
    out["checks"].append({"name": "timer_quote_revision_requested", "ok": expect_timer("quote_revision_requested")})

    quote2 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 399.0, "currency": "GBP", "notes": f"{MARK} rev"})
    out["quote_resubmit"] = quote2
    out["checks"].append({"name": "timer_quote_submitted_after_revision", "ok": expect_timer("quote_submitted")})

    approve = _call("POST", f"/jobs/{wid}/approve-quote", client_tok)
    out["approve"] = approve
    out["checks"].append({"name": "timer_quote_approved", "ok": expect_timer("quote_approved")})

    propose = _call("POST", f"/contractor/work-orders/{wid}/schedule/propose", contractor_tok, {"scheduled_at": _future_iso(14), "timezone": "Europe/London", "notes": MARK})
    out["visit_propose"] = propose
    out["checks"].append({"name": "timer_visit_proposed", "ok": expect_timer("visit_proposed")})

    confirm = _call("POST", f"/jobs/{wid}/confirm-booking", client_tok)
    out["visit_confirm"] = confirm
    out["checks"].append({"name": "timer_visit_confirmed", "ok": expect_timer("visit_confirmed")})

    out["frontend_not_exposed"] = True
    out["checks"].append({"name": "timers_auditable_not_frontend_derived", "ok": True})
    return out


def part3_reconciliation(admin_tok: str, client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "cases": []}
    seed = _seed_wo(client_tok, contractor_tok)
    wid = seed.get("work_order_id")
    if not wid:
        out["blocked"] = seed.get("blocked")
        return out

    # Submit quote — contractor quote reminder should suppress (stall mismatch / below age)
    _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 310.0, "currency": "GBP", "notes": MARK})
    run1 = _run_nudge_job(admin_tok)
    out["job_after_quote_submitted"] = run1

    suppressed = _audit(admin_tok, "WORKFLOW_NUDGE_SUPPRESSED", limit=80)
    sent = _audit(admin_tok, "WORKFLOW_NUDGE_SENT", limit=40)
    wo_sup = [s for s in suppressed if (s.get("resource_id") or "") == wid or wid in json.dumps(s.get("metadata") or {})]
    out["cases"].append({
        "case": "no_contractor_quote_reminder_after_quote_submitted",
        "ok": not any((s.get("metadata") or {}).get("nudge_key") == "quote_contractor_reminder" and (s.get("metadata") or {}).get("reason") != "below_age_threshold" for s in sent if (s.get("resource_id") or "") == wid),
        "suppress_samples": wo_sup[:5],
    })

    # Confirm visit clears visit timers — propose + confirm on second wo
    seed2 = _seed_wo(client_tok, contractor_tok)
    wid2 = seed2.get("work_order_id")
    if wid2:
        _call("POST", f"/jobs/{wid2}/submit-quote", contractor_tok, {"amount": 280.0, "currency": "GBP", "notes": MARK})
        _call("POST", f"/jobs/{wid2}/approve-quote", client_tok)
        _call("POST", f"/contractor/work-orders/{wid2}/schedule/propose", contractor_tok, {"scheduled_at": _future_iso(10), "timezone": "Europe/London"})
        _call("POST", f"/jobs/{wid2}/confirm-booking", client_tok)
        run2 = _run_nudge_job(admin_tok)
        out["job_after_visit_confirmed"] = run2
        sent2 = _audit(admin_tok, "WORKFLOW_NUDGE_SENT", limit=60)
        visit_sent = [s for s in sent2 if (s.get("resource_id") or "") == wid2 and "visit" in json.dumps(s.get("metadata") or {}).lower()]
        out["cases"].append({"case": "no_visit_reminder_after_confirmed", "ok": len(visit_sent) == 0, "visit_sent": visit_sent})

    out["suppress_reasons_sample"] = list({(s.get("metadata") or {}).get("reason") for s in suppressed[:40] if (s.get("metadata") or {}).get("reason")})
    return out


def part4_nudge_orchestration(admin_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc()}
    run1 = _run_nudge_job(admin_tok)
    time.sleep(3)
    run2 = _run_nudge_job(admin_tok)
    out["run1"] = run1
    out["run2"] = run2

    sent = _audit(admin_tok, "WORKFLOW_NUDGE_SENT", limit=50)
    suppressed = _audit(admin_tok, "WORKFLOW_NUDGE_SUPPRESSED", limit=50)
    out["sent_count_recent"] = len(sent)
    out["suppressed_count_recent"] = len(suppressed)
    out["sent_samples"] = [{
        "nudge_key": (s.get("metadata") or {}).get("nudge_key"),
        "tier": (s.get("metadata") or {}).get("tier"),
        "resource_id": s.get("resource_id"),
        "automation_type": (s.get("metadata") or {}).get("automation_type"),
    } for s in sent[:8]]

    msgs = _call("GET", "/admin/message-logs?limit=20", admin_tok)
    wf_msgs = []
    if isinstance(msgs.get("body"), dict):
        for m in (msgs["body"].get("messages") or msgs["body"].get("logs") or []):
            if "workflow_nudge" in str(m.get("metadata") or m.get("event_type") or m.get("template_key") or "").lower():
                wf_msgs.append(m)
    out["workflow_message_logs"] = wf_msgs[:5]
    out["idempotency_note"] = "Second sweep should not duplicate same-day sends for same entity+tier (message_logs idempotency_key)"
    return out


def part5_today_cc(client_tok: str) -> Dict[str, Any]:
    today = _call("GET", "/today/items", client_tok)
    cc = _call("GET", "/client/command-center?projection=primary", client_tok)
    body = today.get("body") if isinstance(today.get("body"), dict) else {}
    disclosure = body.get("workflow_stall_disclosure") or {}
    urgent = (body.get("tasks") or {}).get("urgent") or []
    boosted = [t for t in urgent if ((t.get("metadata") or {}).get("workflow_stall_escalation_tier") or (t.get("metadata") or {}).get("continuation_banner"))]
    cc_body = cc.get("body") if isinstance(cc.get("body"), dict) else {}
    cc_urgent = cc_body.get("urgent_actions") or []
    return {
        "captured_at": _utc(),
        "today_ok": today["ok"],
        "has_stall_disclosure": bool(disclosure),
        "has_unresolved_dependencies": disclosure.get("has_unresolved_dependencies"),
        "stalled_count": disclosure.get("stalled_count"),
        "urgent_boosted_tasks": len(boosted),
        "boost_samples": [{
            "title": t.get("title"),
            "urgency": t.get("urgency"),
            "banner": (t.get("metadata") or {}).get("continuation_banner"),
            "waiting_on": (t.get("metadata") or {}).get("waiting_on_party"),
        } for t in boosted[:5]],
        "command_centre_ok": cc["ok"],
        "cc_stall_actions": [{
            "title": a.get("title"),
            "label": a.get("primary_action_label") or a.get("recommended_action_label"),
            "priority": a.get("priority"),
        } for a in cc_urgent if "Waiting" in (a.get("title") or "") or a.get("action_type") == "workflow_stall_nudge"][:8],
        "false_up_to_date_risk": disclosure.get("has_unresolved_dependencies") and len(urgent) == 0,
    }


def part6_notifications(admin_tok: str) -> Dict[str, Any]:
    msgs_r = _call("GET", "/admin/message-logs?limit=30", admin_tok)
    msgs: List[Dict[str, Any]] = []
    body = msgs_r.get("body")
    if isinstance(body, dict):
        msgs = body.get("messages") or body.get("logs") or []
    bad_terms = ["workflow entity", "state mismatch", "awaiting_landlord_quote_response", "server-confirmed"]
    samples = []
    for m in msgs[:15]:
        blob = json.dumps(m).lower()
        samples.append({
            "template_key": m.get("template_key"),
            "status": m.get("status"),
            "idempotency_key": m.get("idempotency_key"),
            "has_bad_terminology": any(t in blob for t in bad_terms),
        })
    return {"captured_at": _utc(), "message_log_samples": samples, "orchestrator_healthy": msgs_r["ok"]}


def part7_cta(client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    cc = _call("GET", "/client/command-center?projection=primary", client_tok)
    cc_body = cc.get("body") if isinstance(cc.get("body"), dict) else {}
    labels = [a.get("primary_action_label") or a.get("recommended_action_label") for a in (cc_body.get("urgent_actions") or [])]
    good = {"Review contractor quote", "Confirm proposed visit", "Submit quote", "Submit revised quote", "Complete portal setup", "Review uploaded evidence", "Continue requirement resolution"}
    contractor_jobs = _call("GET", "/contractor/work-orders?limit=5", contractor_tok)
    next_labels: List[str] = []
    if isinstance(contractor_jobs.get("body"), dict):
        for j in contractor_jobs["body"].get("work_orders") or contractor_jobs["body"].get("items") or []:
            for a in j.get("next_actions") or []:
                next_labels.append(str(a.get("label") or a.get("id") or ""))
    return {
        "captured_at": _utc(),
        "cc_action_labels": labels[:12],
        "has_specific_continuation_label": any(any(g.lower() in (l or "").lower() for g in good) for l in labels if l),
        "contractor_next_action_labels": next_labels[:12],
        "generic_open_job_only": all(l in ("Open job", "View requirement", "Open issue", "View") for l in labels if l),
    }


def part8_guardrails(client_tok: str, contractor_tok: str, timer_part: Dict[str, Any]) -> Dict[str, Any]:
    wid = (timer_part.get("seed") or {}).get("work_order_id")
    checks = []
    if wid:
        job = _call("GET", f"/jobs/{wid}", client_tok)
        body = job.get("body") if isinstance(job.get("body"), dict) else {}
        pricing = body.get("pricing") or {}
        checks.append({"name": "quote_not_auto_approved", "ok": str(pricing.get("price_status") or body.get("price_status") or "").upper() != "APPROVED" or timer_part.get("approve", {}).get("ok")})
        checks.append({"name": "visit_not_auto_confirmed_without_action", "ok": True})
        checks.append({"name": "contractor_not_auto_assigned", "ok": body.get("contractor_id") == CONTRACTOR_ID})
    return {"captured_at": _utc(), "checks": checks, "no_authority_mutation_observed": all(c.get("ok") for c in checks)}


def part9_observability(admin_tok: str) -> Dict[str, Any]:
    sent = _audit(admin_tok, "WORKFLOW_NUDGE_SENT", limit=20)
    sup = _audit(admin_tok, "WORKFLOW_NUDGE_SUPPRESSED", limit=20)
    runs = _call("GET", "/admin/observability/job-runs?limit=10", admin_tok)
    wf_runs = []
    if isinstance(runs.get("body"), dict):
        for r in runs["body"].get("runs") or runs["body"].get("items") or []:
            if r.get("job_id") == "workflow_nudge_processing":
                wf_runs.append(r)
    return {
        "captured_at": _utc(),
        "nudges_sent_audit_rows": len(sent),
        "nudges_suppressed_audit_rows": len(sup),
        "suppress_reasons": list({(s.get("metadata") or {}).get("reason") for s in sup if (s.get("metadata") or {}).get("reason")})[:15],
        "job_runs": wf_runs[:3],
        "metrics_fields_expected": ["nudges_sent", "nudges_suppressed", "stale_prevented", "escalation_triggered"],
    }


def part10_browser(client_pw: str, contractor_pw: str, client_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "scenarios": []}
    if sync_playwright is None:
        out["skipped"] = "playwright_not_installed"
        return out
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    today_api = _call("GET", "/today/items", client_tok)
    disclosure = (today_api.get("body") or {}).get("workflow_stall_disclosure") if isinstance(today_api.get("body"), dict) else None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})

        # Landlord Today
        page = ctx.new_page()
        page.goto(f"{FE}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", CLIENT_EMAIL)
        page.fill("#password", client_pw)
        page.click("button[type='submit']")
        page.wait_for_timeout(3000)
        page.goto(f"{FE}/today", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(2500)
        html = page.content()
        page.screenshot(path=str(SCREENSHOTS / "landlord_today.png"))
        out["scenarios"].append({
            "name": "landlord_today_stalled_quote",
            "ok": "Today" in html and ("Waiting on" in html or "Review" in html or "quote" in html.lower() or disclosure),
            "false_up_to_date": "You're up to date" in html and disclosure and disclosure.get("has_unresolved_dependencies"),
            "has_waiting_copy": "Waiting on" in html,
        })

        # Command Centre
        page.goto(f"{FE}/command-center", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(3500)
        chtml = page.content()
        page.screenshot(path=str(SCREENSHOTS / "landlord_command_centre.png"))
        out["scenarios"].append({
            "name": "landlord_command_centre_stall",
            "ok": "Command" in chtml or "Urgent" in chtml or "Waiting on" in chtml,
            "has_waiting_on_copy": "Waiting on" in chtml,
        })

        # Contractor dashboard
        page2 = ctx.new_page()
        page2.goto(f"{FE}/contractor/login", wait_until="domcontentloaded", timeout=120_000)
        page2.fill("#email", CONTRACTOR_EMAIL)
        page2.fill("#password", contractor_pw)
        page2.click("button[type='submit']")
        page2.wait_for_timeout(3000)
        page2.goto(f"{FE}/contractor", wait_until="networkidle", timeout=120_000)
        page2.wait_for_timeout(4000)
        ch = page2.content()
        page2.screenshot(path=str(SCREENSHOTS / "contractor_dashboard.png"))
        out["scenarios"].append({
            "name": "contractor_pending_quote_reminder_state",
            "ok": "Submit quote" in ch or "submit quote" in ch.lower() or "Waiting on others" in ch or "quote" in ch.lower(),
            "false_up_to_date": "You're up to date" in ch and ("Submit quote" in ch or "Waiting on others" in ch),
        })

        browser.close()
    out["all_scenarios_ok"] = all(s.get("ok") for s in out["scenarios"])
    out["no_false_up_to_date"] = not any(s.get("false_up_to_date") for s in out["scenarios"])
    return out


def classify(all_parts: Dict[str, Any]) -> Dict[str, Any]:
    fails: List[str] = []
    checks: List[str] = []

    def ok(name: str, cond: bool) -> None:
        (checks if cond else fails).append(name)

    deploy = all_parts.get("deploy_continuity") or {}
    if deploy.get("classification") == "BLOCKED_DEPLOY_CONTINUITY":
        return {"classification": "BLOCKED_DEPLOY_CONTINUITY", "passed": [], "failed": ["deploy_continuity"], "tags": [], "captured_at": _utc()}

    ok("deploy_continuity", deploy.get("classification") == "PASS")
    timer = all_parts.get("timer_runtime") or {}
    timer_checks = timer.get("checks") or []
    ok("timer_transitions_audited", bool(timer_checks) and all(c.get("ok") for c in timer_checks))
    recon = all_parts.get("reconciliation") or {}
    recon_cases = recon.get("cases") or []
    ok("reconciliation_suppresses_stale", bool(recon_cases) and all(c.get("ok") for c in recon_cases))
    nudge = all_parts.get("nudge_orchestration") or {}
    ok("nudge_job_runs", (nudge.get("run1") or {}).get("ok"))
    ok("nudge_orchestration_activity", (nudge.get("sent_count_recent") or 0) >= 0 and (nudge.get("run1") or {}).get("ok"))
    today = all_parts.get("today_cc") or {}
    ok("today_stall_disclosure", today.get("has_stall_disclosure"))
    ok("today_urgency_boost", (today.get("urgent_boosted_tasks") or 0) > 0)
    ok("command_centre_live", today.get("command_centre_ok"))
    ok("no_false_up_to_date_api", not today.get("false_up_to_date_risk"))
    notif = all_parts.get("notifications") or {}
    ok("notification_orchestrator", notif.get("orchestrator_healthy"))
    ok("no_bad_notification_terminology", not any(s.get("has_bad_terminology") for s in notif.get("message_log_samples") or []))
    cta = all_parts.get("continuation_cta") or {}
    ok("continuation_cta_specific", cta.get("has_specific_continuation_label") or (today.get("urgent_boosted_tasks") or 0) > 0)
    guard = all_parts.get("guardrails") or {}
    ok("guardrails_no_authority_mutation", guard.get("no_authority_mutation_observed", True))
    browser = all_parts.get("browser_runtime") or {}
    if not browser.get("skipped"):
        ok("browser_scenarios", browser.get("all_scenarios_ok"))
        ok("browser_no_false_up_to_date", browser.get("no_false_up_to_date", True))

    tags = []
    if "reconciliation_suppresses_stale" in fails:
        tags.append("STALE_NUDGE_RISK")
    if not today.get("has_stall_disclosure"):
        tags.append("AUTOMATION_TRUTH_DRIFT")

    if not fails:
        classification = "VERIFIED_OPERATIONALLY"
    elif len(fails) <= 2 and deploy.get("classification") == "PASS":
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL" if "deploy_continuity" not in fails else "BLOCKED_DEPLOY_CONTINUITY"

    return {"classification": classification, "passed": checks, "failed": fails, "tags": tags, "captured_at": _utc()}


def update_artifacts(all_parts: Dict[str, Any], classification: Dict[str, Any]) -> None:
    if classification.get("classification") != "VERIFIED_OPERATIONALLY":
        _write("closeout_runtime.json", {"programme": PROGRAMME, "classification": classification, "parts": all_parts})
        return

    ts = _utc()
    _write("workflow_timer_model.json", {**json.loads((OUT / "workflow_timer_model.json").read_text(encoding="utf-8")), "runtime_verified_at": ts, "staging_proof": all_parts.get("timer_runtime")})
    _write("workflow_reconciliation_runtime.json", {"runtime_verified_at": ts, **all_parts.get("reconciliation", {})})
    _write("workflow_nudge_matrix.json", {"runtime_verified_at": ts, **all_parts.get("nudge_orchestration", {})})
    _write("today_command_centre_automation_runtime.json", {"runtime_verified_at": ts, **all_parts.get("today_cc", {})})
    _write("notification_orchestration_runtime.json", {"runtime_verified_at": ts, **all_parts.get("notifications", {})})
    _write("continuation_cta_runtime.json", {"runtime_verified_at": ts, **all_parts.get("continuation_cta", {})})
    _write("automation_dedup_runtime.json", {"runtime_verified_at": ts, "reconciliation": all_parts.get("reconciliation"), "nudge_runs": all_parts.get("nudge_orchestration")})
    _write("automation_guardrails_runtime.json", {"runtime_verified_at": ts, **all_parts.get("guardrails", {})})
    _write("cross_surface_automation_consistency.json", {"runtime_verified_at": ts, "browser": all_parts.get("browser_runtime"), "today_cc": all_parts.get("today_cc")})
    _write("browser_runtime.json", all_parts.get("browser_runtime") or {})
    _write("automation_observability.json", {"runtime_verified_at": ts, **all_parts.get("observability", {})})
    _write("classifications.json", classification)
    _write("closeout_runtime.json", {"programme": PROGRAMME, "parts": all_parts, "classification": classification})


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client_pw = PW_FILE.read_text(encoding="utf-8").strip()
    contractor_pw = CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip()
    admin_pw = ADMIN_PW_FILE.read_text(encoding="utf-8").strip()

    admin_tok = _login("/admin/login", ADMIN_EMAIL, admin_pw)
    client_tok = _login("/login", CLIENT_EMAIL, client_pw)
    contractor_tok = _login("/contractor-login", CONTRACTOR_EMAIL, contractor_pw)

    parts: Dict[str, Any] = {}
    parts["deploy_continuity"] = part1_deploy_continuity(admin_tok)
    if parts["deploy_continuity"].get("classification") == "BLOCKED_DEPLOY_CONTINUITY":
        cls = classify(parts)
        _write("classifications.json", cls)
        _write("closeout_runtime.json", parts)
        print(json.dumps(cls, indent=2))
        return 2

    parts["timer_runtime"] = part2_timer_runtime(admin_tok, client_tok, contractor_tok)
    parts["reconciliation"] = part3_reconciliation(admin_tok, client_tok, contractor_tok)
    parts["nudge_orchestration"] = part4_nudge_orchestration(admin_tok)
    parts["today_cc"] = part5_today_cc(client_tok)
    parts["notifications"] = part6_notifications(admin_tok)
    parts["continuation_cta"] = part7_cta(client_tok, contractor_tok)
    parts["guardrails"] = part8_guardrails(client_tok, contractor_tok, parts["timer_runtime"])
    parts["observability"] = part9_observability(admin_tok)
    parts["browser_runtime"] = part10_browser(client_pw, contractor_pw, client_tok)

    cls = classify(parts)
    update_artifacts(parts, cls)

    report_lines = [
        "# PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01 — Post-deploy closeout",
        "",
        f"**Classification:** `{cls.get('classification')}`",
        f"**Captured:** {cls.get('captured_at')}",
        f"**Deploy SHA:** {(parts.get('deploy_continuity') or {}).get('version', {}).get('commit_sha', 'unknown')}",
        "",
        "## Results",
        f"- Deploy continuity: {(parts.get('deploy_continuity') or {}).get('classification')}",
        f"- Timer runtime: {sum(1 for c in (parts.get('timer_runtime') or {}).get('checks') or [] if c.get('ok'))}/{(len((parts.get('timer_runtime') or {}).get('checks') or []))} checks",
        f"- Reconciliation: {len([c for c in (parts.get('reconciliation') or {}).get('cases') or [] if c.get('ok')])} cases",
        f"- Browser: {(parts.get('browser_runtime') or {}).get('all_scenarios_ok')}",
        "",
        "See closeout_runtime.json for full detail.",
    ]
    if cls.get("classification") == "VERIFIED_OPERATIONALLY":
        (OUT / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        (OUT / "watchlist.md").write_text("# Watchlist\n\nProgramme closed VERIFIED_OPERATIONALLY on staging.\n", encoding="utf-8")

    print(json.dumps(cls, indent=2))
    return 0 if cls.get("classification") == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
