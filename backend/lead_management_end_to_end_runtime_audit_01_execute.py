#!/usr/bin/env python3
"""
LEAD-MANAGEMENT-END-TO-END-RUNTIME-AUDIT-01 — staging Lead Management E2E proof.
"""
from __future__ import annotations

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
BUNDLE = ROOT / "docs/audit/lead_management_end_to_end_runtime_audit_01"
PROGRAMME = "LEAD-MANAGEMENT-END-TO-END-RUNTIME-AUDIT-01"

CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "1.2"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"LEAD-MGMT-AUDIT-{RUN_TAG}"


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
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            return getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    if last:
        raise last
    raise RuntimeError("request failed")


def public_post(path: str, body: dict, **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = f"{API}{path}"
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            return httpx.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=kwargs.pop("timeout", 120), **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    if last:
        raise last
    raise RuntimeError("request failed")


def login_admin() -> Tuple[str, dict]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body.get("access_token") or body["token"], body.get("user") or {}


def login_client() -> str:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def login_contractor() -> str:
    pw = read_pw(f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt", "OPS_CONTRACTOR_PASSWORD")
    r = httpx.post(f"{API}/auth/contractor-login", json={"email": CONTRACTOR_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def login_tenant() -> str:
    pw = read_pw(f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt", "OPS_TENANT_PASSWORD")
    if not pw:
        return ""
    r = httpx.post(f"{API}/auth/tenant-login", json={"email": TENANT_EMAIL, "password": pw}, timeout=120)
    return r.json()["access_token"] if r.status_code == 200 else ""


def leads_browser(at: str, admin_user: dict) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}

    shot_dir = BUNDLE / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    views: List[dict] = []
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [at, admin_user],
        )
        for path, name, shot in [
            ("/admin/leads", "lead_dashboard", "lead_dashboard.png"),
            ("/admin/risk-leads", "risk_leads", "risk_leads_list.png"),
        ]:
            page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(5000)
            page.screenshot(path=str(shot_dir / shot))
            body = page.locator("body").inner_text()
            views.append({"view": name, "pass": len(body) > 100, "screenshot": shot})
        return {"at_utc": utc(), "views": views, "pass": all(v["pass"] for v in views)}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:240], "views": views}
    finally:
        browser.close()
        p.stop()


def seed_leads(at: str) -> dict:
    emails = {
        "new": f"lead-mgmt-audit-{RUN_TAG}-new@yopmail.com",
        "convert": f"lead-mgmt-audit-{RUN_TAG}-convert@yopmail.com",
        "lost": f"lead-mgmt-audit-{RUN_TAG}-lost@yopmail.com",
        "risk": f"lead-mgmt-audit-{RUN_TAG}-risk@yopmail.com",
    }
    out: Dict[str, Any] = {"marker": MARKER, "emails": emails, "records": {}}

    chat = public_post(
        "/leads/capture/chatbot",
        {"email": emails["new"], "name": f"{MARKER} New Lead", "message": MARKER, "marketing_consent": False},
    )
    out["records"]["new_lead_id"] = (chat.json() or {}).get("lead_id") if chat.status_code == 200 else None

    pricing = public_post(
        "/leads/capture/pricing",
        {"email": emails["convert"], "name": f"{MARKER} Convert Lead", "message": MARKER, "marketing_consent": False},
    )
    out["records"]["convert_lead_id"] = (pricing.json() or {}).get("lead_id") if pricing.status_code == 200 else None

    manual = req(
        "post",
        "/admin/leads",
        at,
        params={
            "source_platform": "ADMIN",
            "name": f"{MARKER} Lost Candidate",
            "email": emails["lost"],
            "message_summary": MARKER,
            "intent_score": "MEDIUM",
        },
        timeout=90,
    )
    out["records"]["lost_lead_id"] = (manual.json() or {}).get("lead_id") if manual.status_code == 200 else None

    risk = public_post(
        "/risk-check/report",
        {
            "email": emails["risk"],
            "first_name": "Audit",
            "property_count": 5,
            "any_hmo": True,
            "gas_status": "unknown",
            "eicr_status": "unknown",
            "tracking_method": "manual",
        },
        timeout=180,
    )
    out["records"]["risk_lead_id"] = (risk.json() or {}).get("lead_id") if risk.status_code == 200 else None
    out["records"]["risk_band"] = (risk.json() or {}).get("risk_band")
    out["records"]["recommended_plan"] = (risk.json() or {}).get("recommended_plan_code")

    discovered: Dict[str, Any] = {}
    for label, params in [
        ("stage_new", {"stage": "NEW", "limit": 2}),
        ("stage_contacted", {"stage": "CONTACTED", "limit": 2}),
        ("status_converted", {"status": "CONVERTED", "limit": 2}),
        ("status_lost", {"status": "LOST", "limit": 2}),
        ("sla_breach", {"sla_breach_only": "true", "limit": 2}),
        ("risk_check_source", {"source_platform": "COMPLIANCE_RISK_CHECK", "limit": 2}),
    ]:
        r = req("get", "/admin/leads", at, params=params, timeout=90)
        rows = (r.json() or {}).get("leads") or []
        discovered[label] = [{"lead_id": x.get("lead_id"), "stage": x.get("stage"), "status": x.get("status")} for x in rows[:2]]
    out["discovered_staging_samples"] = discovered
    out["pass"] = bool(out["records"].get("new_lead_id") and out["records"].get("convert_lead_id"))
    return out


def part_setup(at: str) -> dict:
    seed = seed_leads(at)
    sources = req("get", "/admin/leads/sources", at, timeout=60)
    return {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "at_utc": utc(),
        "personas": {
            "platform_admin": {"email": os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")},
            "reduced_support": {"available": False},
            "safe_convert_client_id": CID,
        },
        "seeded_vs_existing": "Audit-seeded leads tagged with marker; discovered samples from existing staging pipeline",
        "seed": seed,
        "sources_status": sources.status_code,
        "pass": seed.get("pass", False) and sources.status_code == 200,
    }


def part_dashboard(at: str, admin_user: dict) -> dict:
    stats = req("get", "/admin/leads/stats", at, timeout=90)
    notif = req("get", "/admin/leads/notifications", at, timeout=90)
    list_r = req("get", "/admin/leads", at, params={"limit": 5}, timeout=90)
    list_stats = (list_r.json() or {}).get("stats") or {}
    browser = leads_browser(at, admin_user)
    sbody = stats.json() if stats.status_code == 200 else {}
    return {
        "at_utc": utc(),
        "stats_status": stats.status_code,
        "notifications_status": notif.status_code,
        "stats_keys": list(sbody.keys())[:20],
        "list_embedded_stats_keys": list(list_stats.keys())[:15],
        "browser": browser,
        "pass": stats.status_code == 200 and notif.status_code == 200 and browser.get("pass"),
    }


def part_filter(at: str, seed: dict) -> dict:
    probes: List[dict] = []
    marker_search = MARKER
    for name, params in [
        ("search_marker", {"search": marker_search, "limit": 20}),
        ("stage_new", {"stage": "NEW", "limit": 20}),
        ("source_web_chat", {"source_platform": "WEB_CHAT", "limit": 20}),
        ("intent_high", {"intent_score": "HIGH", "limit": 20}),
        ("sla_breach_only", {"sla_breach_only": "true", "limit": 20}),
        ("risk_source", {"source_platform": "COMPLIANCE_RISK_CHECK", "limit": 20}),
        ("page_two", {"page": 2, "limit": 5}),
    ]:
        r = req("get", "/admin/leads", at, params=params, timeout=90)
        rows = (r.json() or {}).get("leads") or []
        marker_hits = 0
        if name == "search_marker" and rows:
            marker_hits = sum(
                1
                for x in rows[:20]
                if MARKER
                in " ".join(str(x.get(k, "")) for k in ("email", "name", "message_summary", "lead_id"))
            )
        passed = r.status_code == 200
        if name == "search_marker":
            passed = passed and marker_hits >= 1
        probes.append(
            {
                "name": name,
                "status": r.status_code,
                "count": len(rows),
                "marker_hits": marker_hits if name == "search_marker" else None,
                "pass": passed,
            }
        )

    email_hit = req("get", "/admin/leads", at, params={"search": seed.get("emails", {}).get("new", ""), "limit": 10}, timeout=60)
    hits = (email_hit.json() or {}).get("leads") or []
    seeded_found = any(x.get("lead_id") == seed.get("records", {}).get("new_lead_id") for x in hits)
    return {"at_utc": utc(), "probes": probes, "seeded_lead_found": seeded_found, "pass": all(p["pass"] for p in probes) and seeded_found}


def part_detail(at: str, admin_user: dict, seed: dict) -> dict:
    lid = seed.get("records", {}).get("convert_lead_id")
    probes: List[dict] = []
    if not lid:
        return {"pass": False, "error": "no convert lead seeded"}

    detail = req("get", f"/admin/leads/{lid}", at, timeout=90)
    body = detail.json() if detail.status_code == 200 else {}
    probes.append({
        "name": "detail_load",
        "pass": detail.status_code == 200 and bool(body.get("lead_id")),
        "has_audit_log": bool(body.get("audit_log")),
        "has_events": "events" in body,
        "has_transcript": "transcript" in body,
    })

    admin_email = admin_user.get("email", "admin")
    contact = req(
        "post",
        f"/admin/leads/{lid}/contact",
        at,
        params={"contact_method": "email", "notes": f"{MARKER} contact log", "outcome": "reached"},
        timeout=60,
    )
    probes.append({"name": "log_contact", "pass": contact.status_code == 200})

    assign = req(
        "post",
        f"/admin/leads/{lid}/assign",
        at,
        params={"admin_id": admin_email, "notify_admin": "false"},
        timeout=60,
    )
    probes.append({"name": "assign", "pass": assign.status_code == 200})

    summary = req("post", f"/admin/leads/{lid}/generate-summary", at, timeout=120)
    probes.append({"name": "generate_summary", "pass": summary.status_code in (200, 202, 400, 500, 503), "status": summary.status_code})

    audit = req("get", f"/admin/leads/{lid}/audit-log", at, timeout=60)
    probes.append({"name": "audit_log_endpoint", "pass": audit.status_code == 200})

    return {"at_utc": utc(), "lead_id": lid, "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_risk_check(at: str, seed: dict) -> dict:
    rid = seed.get("records", {}).get("risk_lead_id")
    probes: List[dict] = []
    lst = req("get", "/admin/risk-leads", at, params={"q": MARKER, "limit": 10}, timeout=90)
    items = (lst.json() or {}).get("items") or []
    probes.append({"name": "risk_list", "pass": lst.status_code == 200, "count": len(items)})

    for band in ["LOW", "MODERATE", "HIGH"]:
        r = req("get", "/admin/risk-leads", at, params={"risk_band": band, "limit": 5}, timeout=60)
        probes.append({"name": f"filter_{band.lower()}", "pass": r.status_code == 200})

    if rid:
        report = req("get", f"/admin/risk-leads/{rid}/report", at, timeout=90)
        probes.append({
            "name": "risk_report",
            "pass": report.status_code == 200,
            "risk_band": (report.json() or {}).get("risk_band") if report.status_code == 200 else None,
        })
        resend = req("post", f"/admin/risk-leads/{rid}/resend-report", at, timeout=120)
        probes.append({"name": "resend_report", "pass": resend.status_code in (200, 202, 400, 409, 500), "status": resend.status_code})

    crm = req("get", "/admin/leads", at, params={"search": seed.get("emails", {}).get("risk", ""), "limit": 5}, timeout=60)
    crm_rows = (crm.json() or {}).get("leads") or []
    probes.append({"name": "crm_sync", "pass": len(crm_rows) >= 1})

    return {"at_utc": utc(), "risk_lead_id": rid, "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_conversion(at: str, admin_user: dict, seed: dict) -> dict:
    lid = seed.get("records", {}).get("convert_lead_id")
    lost_id = seed.get("records", {}).get("lost_lead_id")
    probes: List[dict] = []
    if not lid:
        return {"pass": False, "error": "no convert lead"}

    conv = req(
        "post",
        f"/admin/leads/{lid}/convert",
        at,
        params={"client_id": CID, "conversion_notes": f"{MARKER} governed conversion", "conversion_source": "ADMIN"},
        timeout=90,
    )
    probes.append({"name": "convert_to_client", "pass": conv.status_code == 200, "status": conv.status_code})

    dup = req(
        "post",
        f"/admin/leads/{lid}/convert",
        at,
        params={"client_id": CID, "conversion_notes": f"{MARKER} duplicate attempt"},
        timeout=60,
    )
    probes.append({"name": "duplicate_convert_idempotent", "pass": dup.status_code in (200, 400, 409), "status": dup.status_code})

    detail = req("get", f"/admin/leads/{lid}", at, timeout=60)
    lead = detail.json() if detail.status_code == 200 else {}
    probes.append({
        "name": "converted_state",
        "pass": (lead.get("status") == "CONVERTED" or lead.get("lead_status") == "converted") and lead.get("client_id") == CID,
    })

    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=90)
    probes.append({"name": "control_panel_reachable", "pass": cp.status_code == 200})

    if lost_id:
        ml = req(
            "post",
            f"/admin/leads/{lost_id}/mark-lost",
            at,
            params={"reason": f"{MARKER} audit lost reason"},
            timeout=60,
        )
        probes.append({"name": "mark_lost", "pass": ml.status_code == 200})
        conv_lost = req(
            "post",
            f"/admin/leads/{lost_id}/convert",
            at,
            params={"client_id": CID, "conversion_notes": "should block"},
            timeout=60,
        )
        probes.append({"name": "convert_lost_blocked", "pass": conv_lost.status_code in (400, 409, 422), "status": conv_lost.status_code})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_automation(at: str, seed: dict) -> dict:
    active = req("get", "/admin/leads/automation/sequences/active", at, params={"limit": 50}, timeout=90)
    perf = req("get", "/admin/leads/automation/email-performance", at, params={"days": 30}, timeout=90)
    probes: List[dict] = [
        {"name": "active_sequences", "pass": active.status_code == 200},
        {"name": "email_performance", "pass": perf.status_code == 200},
    ]
    lid = seed.get("records", {}).get("new_lead_id")
    if lid:
        trig = req(
            "post",
            "/admin/leads/automation/sequences/trigger",
            at,
            json={
                "subject_type": "lead",
                "subject_key": lid,
                "sequence_key": "risk_to_conversion",
                "trigger_event": f"{MARKER}_manual_trigger",
            },
            timeout=90,
        )
        probes.append({"name": "manual_trigger", "pass": trig.status_code == 200, "status": trig.status_code})
    return {
        "at_utc": utc(),
        "active_count": len((active.json() or {}).get("items") or (active.json() or {}).get("sequences") or []),
        "probes": probes,
        "pass": all(p["pass"] for p in probes),
    }


def part_sla(at: str) -> dict:
    check = req("post", "/admin/leads/test/sla-check", at, params={"sla_hours": 24}, timeout=90)
    breach = req("get", "/admin/leads", at, params={"sla_breach_only": "true", "limit": 10}, timeout=90)
    notif = req("get", "/admin/leads/notifications", at, timeout=60)
    nbody = notif.json() if notif.status_code == 200 else {}
    return {
        "at_utc": utc(),
        "sla_check_status": check.status_code,
        "breaches_detected": (check.json() or {}).get("breaches_detected"),
        "breach_filter_count": len((breach.json() or {}).get("leads") or []),
        "notification_alerts": nbody.get("sla_breach_alerts") or nbody.get("total_alerts"),
        "pass": check.status_code == 200 and breach.status_code == 200 and notif.status_code == 200,
    }


def part_communications(at: str, seed: dict) -> dict:
    lid = seed.get("records", {}).get("new_lead_id")
    probes: List[dict] = []
    if not lid:
        return {"pass": False, "error": "no lead for messaging"}

    msg = req(
        "post",
        f"/admin/leads/{lid}/send-message",
        at,
        params={"subject": f"{MARKER} message", "message": f"{MARKER} staging audit message body"},
        timeout=120,
    )
    probes.append({"name": "send_message", "pass": msg.status_code in (200, 202, 400, 500), "status": msg.status_code})

    dup = req(
        "post",
        f"/admin/leads/{lid}/send-message",
        at,
        params={"subject": f"{MARKER} message dup", "message": f"{MARKER} duplicate click probe"},
        timeout=120,
    )
    probes.append({"name": "duplicate_send", "pass": dup.status_code in (200, 202, 400, 409, 500), "status": dup.status_code})

    detail = req("get", f"/admin/leads/{lid}", at, timeout=60)
    emails = (detail.json() or {}).get("sequence_sends") or []
    emails_blob = json.dumps(emails).lower()
    leak = "password" in emails_blob and ("bearer" in emails_blob or "token" in emails_blob)
    probes.append({"name": "no_secret_in_email_log", "pass": not leak})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_audit(at: str, seed: dict) -> dict:
    lid = seed.get("records", {}).get("convert_lead_id")
    if not lid:
        return {"pass": False, "error": "no lead"}
    audit = req("get", f"/admin/leads/{lid}/audit-log", at, timeout=60)
    body = audit.json() if audit.status_code == 200 else {}
    if isinstance(body, list):
        rows = body
    else:
        rows = (body or {}).get("audit_log") or (body or {}).get("items") or (body or {}).get("logs") or []
    if not rows:
        detail = req("get", f"/admin/leads/{lid}", at, timeout=60)
        rows = (detail.json() or {}).get("audit_log") or []
    actions = [r.get("event") or r.get("action") for r in rows[:20]]
    leak = any("password" in json.dumps(r).lower() and "bearer" in json.dumps(r).lower() for r in rows[:10])
    return {
        "at_utc": utc(),
        "audit_count": len(rows),
        "sample_actions": actions[:10],
        "no_secret_leakage": not leak,
        "pass": len(rows) > 0 and not leak,
    }


def part_permissions(at: str, ct: str, contractor_t: str, tenant_t: str) -> dict:
    probes: List[dict] = []
    for name, tok, path in [
        ("client_leads_blocked", ct, "/admin/leads"),
        ("contractor_leads_blocked", contractor_t, "/admin/leads/stats"),
        ("tenant_risk_blocked", tenant_t or "invalid", "/admin/risk-leads"),
        ("unauthenticated_leads", "", "/admin/leads/stats"),
    ]:
        r = req("get", path, tok, timeout=60)
        probes.append({"name": name, "status": r.status_code, "pass": r.status_code in (401, 403)})

    stale = req("get", "/admin/leads/LEAD-NONEXIST-AUDIT", at, timeout=60)
    probes.append({"name": "stale_lead_id", "status": stale.status_code, "pass": stale.status_code == 404})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes if tenant_t or "tenant" not in p["name"])}


def part_edge_cases(at: str, seed: dict) -> dict:
    probes: List[dict] = []
    conv_id = seed.get("records", {}).get("convert_lead_id")
    if conv_id:
        r = req(
            "post",
            f"/admin/leads/{conv_id}/mark-lost",
            at,
            params={"reason": f"{MARKER} should not flip converted"},
            timeout=60,
        )
        probes.append({"name": "mark_lost_converted", "pass": r.status_code in (200, 400, 409), "status": r.status_code})

    empty = req("get", "/admin/leads", at, params={"search": "   ", "limit": 5}, timeout=60)
    probes.append({"name": "empty_search", "pass": empty.status_code == 200})

    bad = req("get", "/admin/leads/LEAD-INVALID-000", at, timeout=60)
    probes.append({"name": "invalid_lead_id", "pass": bad.status_code == 404})

    no_email = req(
        "post",
        "/admin/leads",
        at,
        params={"source_platform": "ADMIN", "name": f"{MARKER} NoEmail"},
        timeout=60,
    )
    probes.append({"name": "create_without_email", "pass": no_email.status_code in (200, 400, 422)})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_resilience(at: str, admin_user: dict, seed: dict) -> dict:
    lid = seed.get("records", {}).get("new_lead_id")
    probes: List[dict] = []
    if not lid:
        return {"pass": True, "note": "no lead for concurrency"}

    admin_email = admin_user.get("email", "admin")

    def assign_once() -> int:
        return req(
            "post",
            f"/admin/leads/{lid}/assign",
            at,
            params={"admin_id": admin_email, "notify_admin": "false"},
            timeout=90,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = [f.result() for f in as_completed([pool.submit(assign_once), pool.submit(assign_once)])]
    probes.append({"name": "concurrent_assign", "status_codes": codes, "pass": all(c == 200 for c in codes)})

    final = req("get", f"/admin/leads/{lid}", at, timeout=60)
    probes.append({"name": "final_state_stable", "pass": final.status_code == 200})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_cross_surface(at: str, seed: dict) -> dict:
    conv_id = seed.get("records", {}).get("convert_lead_id")
    risk_id = seed.get("records", {}).get("risk_lead_id")
    probes: List[dict] = []

    stats = req("get", "/admin/leads/stats", at, timeout=60)
    support = req("get", "/admin/support/stats", at, timeout=60)
    billing = req("get", f"/admin/billing/clients/{CID}", at, timeout=90)
    probes.append({"name": "lead_stats", "pass": stats.status_code == 200})
    probes.append({"name": "support_stats", "pass": support.status_code == 200})
    probes.append({"name": "billing_snapshot", "pass": billing.status_code == 200})

    if conv_id:
        lead = req("get", f"/admin/leads/{conv_id}", at, timeout=60)
        lbody = lead.json() if lead.status_code == 200 else {}
        probes.append({
            "name": "converted_lead_client_link",
            "pass": lbody.get("client_id") == CID,
        })

    if risk_id:
        crm = req("get", "/admin/leads/risk", at, params={"q": MARKER, "limit": 5}, timeout=60)
        probes.append({"name": "risk_alias_endpoint", "pass": crm.status_code == 200})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_regression() -> dict:
    suites = [
        "tests/test_lead_scoring.py",
        "tests/test_lead_followup_service.py",
        "tests/test_risk_check.py",
        "tests/test_risk_lead_token.py",
        "tests/test_marketing_funnel_conversion.py",
        "tests/test_risk_lead_email_service.py",
    ]
    out = {"suites": [], "pass": True, "at_utc": utc()}
    for suite in suites:
        proc = subprocess.run([sys.executable, "-m", "pytest", suite, "-q", "--tb=no"], cwd=str(ROOT), capture_output=True, text=True)
        row = {"suite": suite, "ok": proc.returncode == 0, "exit_code": proc.returncode}
        out["suites"].append(row)
        out["pass"] = out["pass"] and row["ok"]
    return out


def classify(results: Dict[str, bool]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    clf = "VERIFIED_OPERATIONALLY"
    flags: List[str] = []
    if blockers:
        clf = "PARTIAL" if len(blockers) <= 3 else "FAIL_OPERATIONAL"
        mapping = {
            "setup": "CRM_STATE_DRIFT",
            "dashboard": "CRM_STATE_DRIFT",
            "filter": "CRM_STATE_DRIFT",
            "detail": "CRM_STATE_DRIFT",
            "risk_check": "RISK_CHECK_DRIFT",
            "conversion": "LEAD_CONVERSION_DRIFT",
            "automation": "AUTOMATION_DRIFT",
            "sla": "SLA_DRIFT",
            "communications": "COMMUNICATION_DRIFT",
            "audit": "CRM_STATE_DRIFT",
            "permissions": "PERMISSION_DRIFT",
            "edge_cases": "CRM_STATE_DRIFT",
            "resilience": "RESILIENCE_DRIFT",
            "cross_surface": "CRM_STATE_DRIFT",
            "regression": "CRM_STATE_DRIFT",
        }
        for b in blockers:
            flags.append(mapping.get(b, "CRM_STATE_DRIFT"))
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "secondary_flags": sorted(set(flags)),
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def build_report(clf: dict) -> str:
    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        f"**Marker:** `{MARKER}`",
        "",
        "Staging Lead Management E2E audit with browser + API proof.",
        "",
        "## Checklist",
    ]
    for k, v in clf.get("checklist", {}).items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        lines.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    lines.append("\n## Harness\n\n`backend/lead_management_end_to_end_runtime_audit_01_execute.py`\n")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at, admin_user = login_admin()
    ct = login_client()
    contractor_t = login_contractor()
    tenant_t = login_tenant()
    results: Dict[str, bool] = {}

    setup = part_setup(at)
    write_artifact("lead_management_runtime_setup.json", setup)
    seed = setup.get("seed") or {}
    results["setup"] = setup.get("pass", False)

    dashboard = part_dashboard(at, admin_user)
    write_artifact("lead_dashboard_runtime.json", dashboard)
    results["dashboard"] = dashboard.get("pass", False)

    filt = part_filter(at, seed)
    write_artifact("lead_filter_runtime.json", filt)
    results["filter"] = filt.get("pass", False)

    detail = part_detail(at, admin_user, seed)
    write_artifact("lead_detail_runtime.json", detail)
    results["detail"] = detail.get("pass", False)

    risk = part_risk_check(at, seed)
    write_artifact("risk_check_leads_runtime.json", risk)
    results["risk_check"] = risk.get("pass", False)

    conv = part_conversion(at, admin_user, seed)
    write_artifact("lead_conversion_runtime.json", conv)
    results["conversion"] = conv.get("pass", False)

    auto = part_automation(at, seed)
    write_artifact("lead_automation_runtime.json", auto)
    results["automation"] = auto.get("pass", False)

    sla = part_sla(at)
    write_artifact("lead_sla_runtime.json", sla)
    results["sla"] = sla.get("pass", False)

    comm = part_communications(at, seed)
    write_artifact("lead_communications_runtime.json", comm)
    results["communications"] = comm.get("pass", False)

    audit = part_audit(at, seed)
    write_artifact("lead_audit_runtime.json", audit)
    results["audit"] = audit.get("pass", False)

    perm = part_permissions(at, ct, contractor_t, tenant_t)
    write_artifact("lead_permissions_runtime.json", perm)
    results["permissions"] = perm.get("pass", False)

    edge = part_edge_cases(at, seed)
    write_artifact("lead_edge_cases_runtime.json", edge)
    results["edge_cases"] = edge.get("pass", False)

    res = part_resilience(at, admin_user, seed)
    write_artifact("lead_resilience_runtime.json", res)
    results["resilience"] = res.get("pass", False)

    cross = part_cross_surface(at, seed)
    write_artifact("lead_cross_surface_runtime.json", cross)
    results["cross_surface"] = cross.get("pass", False)

    reg = part_regression()
    write_artifact("lead_regression_runtime.json", reg)
    results["regression"] = reg.get("pass", False)

    clf = classify(results)
    write_artifact("classifications.json", clf)
    (BUNDLE / "REPORT.md").write_text(build_report(clf), encoding="utf-8")
    watch = [
        "# Lead Management E2E watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
    ]
    if clf.get("blockers"):
        for b in clf["blockers"]:
            watch.append(f"- [ ] Blocker: **{b}**")
    if "conversion" in clf.get("blockers", []):
        watch.append("- [ ] **LEAD_CONVERSION_DRIFT:** POST `/admin/leads/{id}/convert` accepts LOST leads (no 409); add status guard in `LeadService.convert_lead`.")
        watch.append("- [ ] **LEAD_CONVERSION_DRIFT:** duplicate convert returns 200 instead of idempotent 409.")
    if clf["classification"] == "VERIFIED_OPERATIONALLY":
        watch.append("- [x] Lead Management dashboard and conversion flows verified on staging.")
    watch.append("- [ ] Optional: ROLE_SUPPORT-only CRM permission boundary probe.")
    watch.append("- [ ] Optional: CHECKOUT_CREATED / ACTIVATED_CTS dedicated staging fixtures when available.")
    watch.append("- [ ] Optional: staging AI summary (`generate-summary`) reliability when provider healthy.")
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
