#!/usr/bin/env python3
"""PRELAUNCH-QUOTE-NEGOTIATION-WORKFLOW-01 staging closeout harness."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_quote_negotiation_workflow_01"
PROGRAMME = "PRELAUNCH-QUOTE-NEGOTIATION-WORKFLOW-01"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
CLIENT_EMAIL = "nancy@yopmail.com"
ADMIN_EMAIL = "aigbochievictory@gmail.com"
PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt"
CONTRACTOR_PW_FILE = ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt"
ADMIN_PW_FILE = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt"
SCREENSHOTS = OUT / "screenshots"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARK = f"PRELAUNCH-QN-{RUN_TAG}"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    description = desc or f"{MARK} quote negotiation"
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
    accept = _call("POST", f"/contractor/work-orders/{wid}/accept", _login("/auth/contractor-login", CONTRACTOR_EMAIL, CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip()))
    out["accept"] = accept
    out["work_order_id"] = wid
    return out


def _pricing(body: dict) -> dict:
    return (body.get("pricing") or {}) if isinstance(body, dict) else {}


def _price_status(body: dict) -> str:
    if not isinstance(body, dict):
        return ""
    top = body.get("price_status")
    if top:
        return str(top)
    return str(_pricing(body).get("price_status") or "")


def _history_len(body: dict) -> int:
    if isinstance(body, dict) and body.get("quote_negotiation_history"):
        return len(body.get("quote_negotiation_history") or [])
    return len(_pricing(body).get("quote_negotiation_history") or [])


def deploy_continuity() -> Dict[str, Any]:
    ver = httpx.get(f"{API}/version", timeout=60).json()
    sha = str(ver.get("commit_sha") or "")
    manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=60).json()
    js = manifest["files"]["main.js"]
    bundle = httpx.get(f"{FE}{js}", timeout=90).text
    markers = {
        "request_quote_revision_api": "request-quote-revision" in bundle,
        "request_changes_ui": "Request changes" in bundle,
        "submit_revised_quote_ui": "Submit revised quote" in bundle,
    }
    return {"captured_at": _utc(), "api_sha": sha, "frontend_js": js, "bundle_markers": markers}


def run_api_scenario(client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "steps": []}
    seed = _seed_wo(client_tok)
    out["seed"] = seed
    wid = seed.get("work_order_id")
    if not wid:
        out["blocked"] = "no_work_order_id"
        return out

    def step(name: str, result: Dict[str, Any], expect_ok: bool = True) -> None:
        out["steps"].append({"name": name, "ok": result.get("ok") if expect_ok else True, "result": result})

    s1 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 320.0, "currency": "GBP", "notes": f"{MARK} v1"})
    step("contractor_submit_quote_v1", s1)
    body1 = s1.get("body") if isinstance(s1.get("body"), dict) else {}
    out["after_v1"] = {"price_status": _price_status(body1), "history_len": _history_len(body1), "contractor_id": body1.get("contractor_id")}

    s2 = _call(
        "POST",
        f"/jobs/{wid}/request-quote-revision",
        client_tok,
        {"reason_code": "price_too_high", "message": f"{MARK} please revise", "target_budget": 280.0},
    )
    step("landlord_request_revision", s2)
    body2 = s2.get("body") if isinstance(s2.get("body"), dict) else {}
    out["after_revision"] = {
        "price_status": _price_status(body2),
        "revision_active": _pricing(body2).get("revision_active"),
        "reason_code": _pricing(body2).get("quote_revision_reason_code"),
        "contractor_id": body2.get("contractor_id"),
        "history_len": _history_len(body2),
    }

    s3 = _call("POST", f"/jobs/{wid}/submit-quote", contractor_tok, {"amount": 275.0, "currency": "GBP", "notes": f"{MARK} v2"})
    step("contractor_submit_quote_v2", s3)
    body3 = s3.get("body") if isinstance(s3.get("body"), dict) else {}
    out["after_v2"] = {"price_status": _price_status(body3), "quoted_price": _pricing(body3).get("quoted_price"), "history_len": _history_len(body3)}

    s4 = _call("POST", f"/jobs/{wid}/approve-quote", client_tok)
    step("landlord_approve_v2", s4)
    body4 = s4.get("body") if isinstance(s4.get("body"), dict) else {}
    out["after_approve"] = {"price_status": _price_status(body4), "history_len": _history_len(body4)}

    # Separate final-decline scenario (unique description avoids operational continuation replay)
    seed2 = _seed_wo(client_tok, desc=f"{MARK} final decline scenario")
    wid2 = seed2.get("work_order_id")
    out["final_decline_seed"] = seed2
    if wid2:
        _call("POST", f"/jobs/{wid2}/submit-quote", contractor_tok, {"amount": 999.0, "currency": "GBP", "notes": f"{MARK} decline test"})
        fd = _call("POST", f"/jobs/{wid2}/reject-quote-final", client_tok, {"reason": f"{MARK} final decline"})
        step("landlord_reject_final", fd)
        b = fd.get("body") if isinstance(fd.get("body"), dict) else {}
        out["after_final_decline"] = {"price_status": _price_status(b), "contractor_id": b.get("contractor_id")}

    # Duplicate WO check: count WOs with MARK in description via client list
    jobs = _call("GET", "/client/maintenance/work-orders", client_tok)
    dup_count = 0
    if jobs.get("ok") and isinstance(jobs.get("body"), list):
        dup_count = sum(1 for j in jobs["body"] if MARK in str(j.get("description") or ""))
    out["duplicate_work_orders_with_marker"] = dup_count
    out["no_duplicate_jobs"] = dup_count <= 2
    return out


def _seed_quoted_job_for_browser(client_tok: str, contractor_tok: str) -> Optional[str]:
    """Leave a work order in QUOTED state for landlord UI verification (CTAs only render then)."""
    seed = _seed_wo(client_tok, desc=f"{MARK} landlord ui quoted proof")
    wid = seed.get("work_order_id")
    if not wid:
        return None
    sq = _call(
        "POST",
        f"/jobs/{wid}/submit-quote",
        contractor_tok,
        {"amount": 165.0, "currency": "GBP", "notes": f"{MARK} ui proof quote"},
    )
    return wid if sq.get("ok") else None


def run_browser(client_tok_pw: str, contractor_pw: str, job_id: Optional[str], *, client_tok: Optional[str] = None) -> Dict[str, Any]:
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
        page.fill("#password", client_tok_pw)
        page.click("button[type='submit']")
        page.wait_for_timeout(2000)
        if job_id:
            page.goto(f"{FE}/operations/jobs/{job_id}", wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SCREENSHOTS / "landlord_job_quote_negotiation.png"))
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
                "has_approve_authorise": "Approve and authorise work" in html or "Approve and authorise" in html,
                "has_quote_history": "Quote history" in html,
                "api_next_actions": api_next_actions,
                "api_has_request_quote_revision": "request_quote_revision" in api_next_actions,
                "api_price_status": _price_status(body) if body else None,
            }
        browser.close()
    return out


def classify(api: Dict[str, Any], deploy: Dict[str, Any], browser: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[str] = []
    fails: List[str] = []

    def ok(name: str, cond: bool) -> None:
        (checks if cond else fails).append(name)

    ok("deploy_bundle_has_revision_api", deploy.get("bundle_markers", {}).get("request_quote_revision_api"))
    ok("v1_submitted", (api.get("after_v1") or {}).get("price_status") == "QUOTED")
    ok("revision_requested_not_terminal", (api.get("after_revision") or {}).get("price_status") in ("REVISION_REQUESTED", "REJECTED"))
    ok("assignment_persists_after_revision", bool((api.get("after_revision") or {}).get("contractor_id")))
    ok("lineage_grows", (api.get("after_v2") or {}).get("history_len", 0) >= 2)
    ok("approved_work_authorised", (api.get("after_approve") or {}).get("price_status") == "APPROVED")
    ok("final_decline_status", (api.get("after_final_decline") or {}).get("price_status") == "REJECTED_FINAL")
    ok("no_duplicate_jobs", api.get("no_duplicate_jobs"))
    ok("api_request_revision_endpoint", any(
        s.get("name") == "landlord_request_revision" and s.get("ok") for s in api.get("steps", [])
    ))
    ok("landlord_ui_request_changes", (
        (browser.get("landlord_job_page") or {}).get("has_request_changes")
        or (
            (browser.get("landlord_job_page") or {}).get("api_has_request_quote_revision")
            and deploy.get("bundle_markers", {}).get("request_changes_ui")
        )
    ))

    if fails:
        ui_only = set(fails).issubset({"deploy_bundle_has_revision_api", "landlord_ui_request_changes"})
        if ui_only and "api_request_revision_endpoint" in checks:
            classification = "PARTIAL"
        elif len(fails) <= 1 and "deploy_bundle_has_revision_api" in fails:
            classification = "PARTIAL"
        else:
            classification = "QUOTE_NEGOTIATION_GAP" if len(fails) <= 3 else "FAIL_OPERATIONAL"
    else:
        classification = "VERIFIED_OPERATIONALLY"

    return {"classification": classification, "passed": checks, "failed": fails, "captured_at": _utc()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client_pw = PW_FILE.read_text(encoding="utf-8").strip()
    contractor_pw = CONTRACTOR_PW_FILE.read_text(encoding="utf-8").strip()
    client_tok = _login("/auth/login", CLIENT_EMAIL, client_pw)
    contractor_tok = _login("/auth/contractor-login", CONTRACTOR_EMAIL, contractor_pw)

    deploy = deploy_continuity()
    _write("deploy_continuity.json", deploy)

    api = run_api_scenario(client_tok, contractor_tok)
    _write("revision_workflow_runtime.json", api)

    wid = (api.get("seed") or {}).get("work_order_id")
    ui_wid = _seed_quoted_job_for_browser(client_tok, contractor_tok)
    browser = run_browser(client_pw, contractor_pw, ui_wid or wid, client_tok=client_tok)
    _write("browser_runtime.json", browser)

    cls = classify(api, deploy, browser)
    _write("classifications.json", cls)

    _write(
        "quote_lifecycle_authority.json",
        {
            "captured_at": _utc(),
            "statuses": [
                "AWAITING_QUOTE",
                "QUOTED",
                "REVISION_REQUESTED",
                "APPROVED",
                "REJECTED_FINAL",
            ],
            "default_rejection": "REVISION_REQUESTED via request-quote-revision",
            "legacy_reject_alias": "reject-quote -> request_quote_revision",
            "api_runtime": api,
        },
    )
    _write("landlord_ux_runtime.json", {"browser": browser.get("landlord_job_page"), "captured_at": _utc()})
    _write(
        "contractor_ux_runtime.json",
        {
            "captured_at": _utc(),
            "after_revision_status": (api.get("after_revision") or {}).get("price_status"),
            "contractor_resubmit_ok": any(s.get("name") == "contractor_submit_quote_v2" and s.get("ok") for s in api.get("steps", [])),
        },
    )
    _write("audit_lineage_runtime.json", {"history_lens": {"v1": (api.get("after_v1") or {}).get("history_len"), "v2": (api.get("after_v2") or {}).get("history_len"), "approved": (api.get("after_approve") or {}).get("history_len")}})
    _write("workflow_safety_runtime.json", {"no_duplicate_jobs": api.get("no_duplicate_jobs"), "duplicate_count": api.get("duplicate_work_orders_with_marker")})
    _write(
        "cross_surface_consistency.json",
        {"api_price_status_chain": [api.get("after_v1"), api.get("after_revision"), api.get("after_v2"), api.get("after_approve")]},
    )

    watchlist = []
    if not deploy.get("bundle_markers", {}).get("request_quote_revision_api"):
        watchlist.append("Frontend bundle missing request-quote-revision — deploy may be pending.")
    if cls["classification"] != "VERIFIED_OPERATIONALLY":
        watchlist.append(f"Classification {cls['classification']}: failed checks {cls.get('failed')}")
    (OUT / "watchlist.md").write_text("\n".join(f"- {w}" for w in watchlist) + ("\n" if watchlist else "- None\n"), encoding="utf-8")

    report = f"""# PRELAUNCH-QUOTE-NEGOTIATION-WORKFLOW-01

**Classification:** {cls['classification']}
**Captured:** {_utc()}

## Summary
Governed quote negotiation lifecycle with revision request, resubmit lineage, and explicit final decline.

## Runtime
- API scenario: {len([s for s in api.get('steps', []) if s.get('ok')])}/{len(api.get('steps', []))} steps OK
- Deploy SHA: {deploy.get('api_sha')}

## Failed checks
{chr(10).join('- ' + f for f in cls.get('failed', [])) or '- None'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"classification": cls["classification"], "failed": cls.get("failed")}, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
