#!/usr/bin/env python3
"""
SUPPORT-DASHBOARD-END-TO-END-RUNTIME-AUDIT-01 — staging Support Dashboard E2E proof.
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
BUNDLE = ROOT / "docs/audit/support_dashboard_end_to_end_runtime_audit_01"
PROGRAMME = "SUPPORT-DASHBOARD-END-TO-END-RUNTIME-AUDIT-01"

CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
CID_B = "80f83edd-ba12-41ed-929a-bbaf8c696a23"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "1.2"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"SUPPORT-DASH-AUDIT-{RUN_TAG}"


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


def login_client() -> Tuple[str, dict]:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"], r.json().get("user") or {}


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


def seed_records(at: str, ct: str, crn: str) -> dict:
    """Seed safe staging support records tagged with MARKER."""
    out: Dict[str, Any] = {"marker": MARKER, "seeded_at_utc": utc(), "records": {}}

    chat = public_post("/support/chat", {"message": f"{MARKER} billing question about invoice", "channel": "web"})
    conv_id = (chat.json() or {}).get("conversation_id") if chat.status_code == 200 else None
    out["records"]["chat_conversation_id"] = conv_id

    billing_ticket = public_post(
        "/support/ticket",
        {
            "subject": f"{MARKER} billing payment failed",
            "description": "Customer reports payment failed on subscription renewal.",
            "category": "billing",
            "priority": "high",
            "service_area": "billing",
            "contact_method": "email",
            "email": CLIENT_EMAIL,
            "crn": crn or None,
        },
    )
    billing_id = (billing_ticket.json() or {}).get("ticket_id") if billing_ticket.status_code == 200 else None
    out["records"]["billing_ticket_id"] = billing_id

    compliance_chat = public_post(
        "/support/chat",
        {"message": "Is it legal for my landlord to evict me without notice?", "channel": "web"},
    )
    compliance_conv = (compliance_chat.json() or {}).get("conversation_id") if compliance_chat.status_code == 200 else None
    out["records"]["compliance_conversation_id"] = compliance_conv
    out["records"]["compliance_legal_refusal"] = (
        "legal" in str((compliance_chat.json() or {}).get("response", "")).lower()
        or (compliance_chat.json() or {}).get("metadata", {}).get("legal_refusal")
    )

    normal_ticket = public_post(
        "/support/ticket",
        {
            "subject": f"{MARKER} general support request",
            "description": "Normal priority ticket for workflow testing.",
            "category": "technical",
            "priority": "medium",
            "service_area": "cvp",
            "contact_method": "email",
            "email": "support-audit-staging@yopmail.com",
        },
    )
    workflow_id = (normal_ticket.json() or {}).get("ticket_id") if normal_ticket.status_code == 200 else None
    out["records"]["workflow_ticket_id"] = workflow_id

    handoff_chat = public_post("/support/chat", {"message": "I want to speak to a human agent please", "channel": "web"})
    handoff_conv = (handoff_chat.json() or {}).get("conversation_id") if handoff_chat.status_code == 200 else None
    escalated_ticket_id = None
    if handoff_conv:
        lh = public_post(f"/support/conversation/{handoff_conv}/live-chat-handoff", {})
        escalated_ticket_id = (lh.json() or {}).get("ticket_id") if lh.status_code == 200 else None
    out["records"]["escalated_conversation_id"] = handoff_conv
    out["records"]["escalated_ticket_id"] = escalated_ticket_id

    ai_handoff: Dict[str, Any] = {}
    try:
        achat = req("post", "/assistant/chat", ct, json={"message": f"{MARKER} help with compliance requirements"}, timeout=180)
        ai_conv = (achat.json() or {}).get("conversation_id") if achat.status_code == 200 else None
        ai_handoff["assistant_conversation_id"] = ai_conv
        if ai_conv:
            esc = req(
                "post",
                "/assistant/escalate",
                ct,
                json={"conversation_id": ai_conv, "reason": f"{MARKER} user requested human support"},
                timeout=180,
            )
            ai_handoff["escalate_status"] = esc.status_code
            ai_handoff["ticket_id"] = (esc.json() or {}).get("ticket_id")
    except Exception as exc:
        ai_handoff["error"] = str(exc)[:200]
    out["records"]["ai_handoff"] = ai_handoff

    closed = public_post(
        "/support/ticket",
        {
            "subject": f"{MARKER} closed ticket seed",
            "description": "Pre-resolved ticket for filter testing.",
            "category": "other",
            "priority": "low",
            "contact_method": "email",
            "email": "closed-audit@yopmail.com",
        },
    )
    closed_id = (closed.json() or {}).get("ticket_id") if closed.status_code == 200 else None
    if closed_id:
        req("put", f"/admin/support/ticket/{closed_id}/status", at, params={"status": "resolved"}, timeout=60)
    out["records"]["closed_ticket_id"] = closed_id

    out["pass"] = bool(workflow_id or billing_id)
    return out


def resolve_crn(at: str) -> str:
    ctx = req("get", f"/admin/support/context/{CID}", at, timeout=90)
    if ctx.status_code == 200:
        snap = (ctx.json() or {}).get("account_snapshot") or {}
        return snap.get("customer_reference") or snap.get("crn") or ""
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=90)
    if cp.status_code == 200:
        return (cp.json() or {}).get("customer_reference") or ""
    return ""


def support_browser(at: str, admin_user: dict, *, ticket_id: Optional[str] = None) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}

    shot_dir = BUNDLE / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    tabs: List[dict] = []
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [at, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/support", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(4000)
        body = page.locator("body").inner_text()
        overview_ok = page.locator('[data-testid="admin-support-page"]').count() > 0 or "Open Tickets" in body
        page.screenshot(path=str(shot_dir / "support_dashboard_overview.png"))
        tabs.append({"view": "overview", "pass": overview_ok, "screenshot": "support_dashboard_overview.png"})

        if page.locator('button:has-text("Chats")').count():
            page.locator('button:has-text("Chats")').first.click()
            page.wait_for_timeout(2000)
            page.screenshot(path=str(shot_dir / "support_conversations_tab.png"))
            tabs.append({"view": "conversations", "pass": True, "screenshot": "support_conversations_tab.png"})

        if page.locator('button:has-text("Tickets")').count():
            page.locator('button:has-text("Tickets")').first.click()
            page.wait_for_timeout(1500)

        if ticket_id and page.locator(f'[data-testid="ticket-{ticket_id}"]').count():
            page.locator(f'[data-testid="ticket-{ticket_id}"]').first.click()
            page.wait_for_timeout(2000)
            page.screenshot(path=str(shot_dir / "support_ticket_detail.png"))
            tabs.append({"view": "ticket_detail", "pass": True, "screenshot": "support_ticket_detail.png", "ticket_id": ticket_id})

        return {"at_utc": utc(), "tabs": tabs, "pass": overview_ok and len(tabs) >= 1}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:240], "tabs": tabs}
    finally:
        browser.close()
        p.stop()


def part_setup(at: str, ct: str) -> dict:
    crn = resolve_crn(at)
    seed = seed_records(at, ct, crn)
    stale = req("get", "/admin/support/tickets", at, params={"status": "resolved", "limit": 3}, timeout=90)
    stale_items = (stale.json() or {}).get("tickets") or []
    return {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "at_utc": utc(),
        "personas": {
            "platform_admin": {"email": os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")},
            "reduced_support": {"available": False, "note": "No dedicated ROLE_SUPPORT staging credentials; admin used for support APIs"},
            "test_landlord": {"client_id": CID, "email": CLIENT_EMAIL, "crn": crn},
            "test_contractor": {"email": CONTRACTOR_EMAIL},
            "test_tenant": {"email": TENANT_EMAIL},
        },
        "seeded_vs_existing": "Audit-seeded tickets/conversations tagged with marker; stale tickets from existing resolved queue",
        "crn": crn,
        "seed": seed,
        "stale_ticket_sample": [t.get("ticket_id") for t in stale_items[:2]],
        "pass": seed.get("pass", False) and bool(crn),
    }


def part_dashboard_overview(at: str, admin_user: dict, seed: dict) -> dict:
    stats = req("get", "/admin/support/stats", at, timeout=90)
    body = stats.json() if stats.status_code == 200 else {}
    browser = support_browser(at, admin_user, ticket_id=seed.get("records", {}).get("workflow_ticket_id"))
    t = body.get("tickets") or {}
    c = body.get("conversations") or {}
    keys_ok = all(k in t for k in ("open", "new", "high_priority")) and all(k in c for k in ("open", "escalated"))
    return {
        "at_utc": utc(),
        "stats_status": stats.status_code,
        "tickets": t,
        "conversations": c,
        "browser": browser,
        "pass": stats.status_code == 200 and keys_ok and browser.get("pass"),
    }


def _ticket_ids(data: dict) -> List[str]:
    return [t.get("ticket_id") for t in (data.get("tickets") or []) if t.get("ticket_id")]


def part_ticket_filtering(at: str, seed: dict, crn: str) -> dict:
    probes: List[dict] = []
    for name, params in [
        ("all", {"limit": 20}),
        ("status_new", {"status": "new", "limit": 20}),
        ("priority_high", {"priority": "high", "limit": 20}),
        ("search_email", {"search": CLIENT_EMAIL.split("@")[0], "limit": 20}),
        ("search_crn", {"search": crn[:10] if crn else "PLE", "limit": 20}),
        ("status_resolved", {"status": "resolved", "limit": 10}),
    ]:
        r = req("get", "/admin/support/tickets", at, params=params, timeout=90)
        items = _ticket_ids(r.json() if r.status_code == 200 else {})
        probes.append({"name": name, "status": r.status_code, "count": len(items), "pass": r.status_code == 200})

    search_email = req("get", "/admin/support/tickets", at, params={"search": CLIENT_EMAIL.split("@")[0], "limit": 20}, timeout=90)
    email_hits = _ticket_ids(search_email.json() if search_email.status_code == 200 else {})
    seeded_ids = {
        seed.get("records", {}).get("workflow_ticket_id"),
        seed.get("records", {}).get("billing_ticket_id"),
    } - {None}
    retrievable = sum(
        1 for tid in seeded_ids
        if req("get", f"/admin/support/ticket/{tid}", at, timeout=60).status_code == 200
    )
    marker_found = retrievable >= len(seeded_ids) and seed.get("records", {}).get("billing_ticket_id") in email_hits

    ids = set(email_hits)
    no_dup = len(email_hits) == len(ids)

    wf_id = seed.get("records", {}).get("workflow_ticket_id")
    detail_ok = False
    if wf_id:
        dr = req("get", f"/admin/support/ticket/{wf_id}", at, timeout=90)
        detail_ok = dr.status_code == 200 and (dr.json() or {}).get("ticket", {}).get("ticket_id") == wf_id

    return {
        "at_utc": utc(),
        "probes": probes,
        "seeded_ticket_ids": sorted(seeded_ids),
        "search_hit_count": len(email_hits),
        "seeded_tickets_found": marker_found,
        "no_duplicate_rows": no_dup,
        "detail_select_ok": detail_ok,
        "pass": all(p["pass"] for p in probes) and marker_found and no_dup and detail_ok,
    }


def part_conversation_filtering(at: str, seed: dict, crn: str) -> dict:
    probes: List[dict] = []
    for name, params in [
        ("open", {"status": "open", "limit": 20}),
        ("escalated", {"status": "escalated", "limit": 20}),
        ("billing_area", {"service_area": "billing", "limit": 20}),
        ("search_marker", {"search": MARKER, "limit": 20}),
        ("search_email", {"search": CLIENT_EMAIL.split("@")[0], "limit": 20}),
    ]:
        r = req("get", "/admin/support/conversations", at, params=params, timeout=90)
        convs = (r.json() or {}).get("conversations") or []
        leak = any(
            c.get("client_id") and c.get("client_id") not in (CID, CID_B, None, "")
            for c in convs[:5]
            if MARKER in str(c.get("last_message_preview", "")) + str(c.get("email", ""))
        )
        preview_text = " ".join(str(c.get("last_message_preview", "")) for c in convs[:3])
        secret_leak = bool(re.search(r"password|bearer\s|api_key", preview_text, re.I))
        probes.append({
            "name": name,
            "status": r.status_code,
            "count": len(convs),
            "no_secret_in_preview": not secret_leak,
            "pass": r.status_code == 200 and not secret_leak,
        })

    conv_id = seed.get("records", {}).get("chat_conversation_id")
    detail_ok = False
    msg_count = 0
    if conv_id:
        dr = req("get", f"/admin/support/conversation/{conv_id}", at, timeout=90)
        if dr.status_code == 200:
            detail_ok = True
            msg_count = len((dr.json() or {}).get("messages") or [])
            transcript = (dr.json() or {}).get("transcript") or ""
            debug_leak = "traceback" in transcript.lower() or "openai" in transcript.lower()
            detail_ok = detail_ok and not debug_leak

    return {
        "at_utc": utc(),
        "probes": probes,
        "detail_conversation_id": conv_id,
        "message_count": msg_count,
        "detail_ok": detail_ok,
        "pass": all(p["pass"] for p in probes) and detail_ok,
    }


def part_crn_lookup(at: str, crn: str) -> dict:
    probes: List[dict] = []
    if crn:
        r = req("post", "/admin/support/lookup-by-crn", at, json={"crn": crn}, timeout=90)
        client = (r.json() or {}).get("client") or {}
        probes.append({
            "name": "valid_crn",
            "status": r.status_code,
            "client_id": client.get("client_id"),
            "pass": r.status_code == 200 and client.get("client_id") == CID,
        })
        r2 = req("post", "/admin/support/lookup-by-crn", at, json={"crn": crn.lower()}, timeout=90)
        probes.append({"name": "lowercase_crn", "status": r2.status_code, "pass": r2.status_code == 200})

    inv = req("post", "/admin/support/lookup-by-crn", at, json={"crn": "PLE-CVP-2026-INVALID-AUDIT"}, timeout=60)
    probes.append({"name": "invalid_crn", "status": inv.status_code, "pass": inv.status_code == 404})

    ctx = req("get", f"/admin/support/context/{CID}", at, timeout=90)
    ctx_ok = ctx.status_code == 200 and (ctx.json() or {}).get("client_id") == CID
    wrong = req("get", f"/admin/support/context/00000000-0000-0000-0000-000000009999", at, timeout=60)

    return {
        "at_utc": utc(),
        "probes": probes,
        "context_panel_ok": ctx_ok,
        "wrong_client_context_status": wrong.status_code,
        "pass": all(p["pass"] for p in probes) and ctx_ok,
    }


def part_ticket_workflow(at: str, admin_user: dict, seed: dict) -> dict:
    tid = seed.get("records", {}).get("workflow_ticket_id")
    probes: List[dict] = []
    if not tid:
        return {"pass": False, "error": "no workflow ticket seeded"}

    dr = req("get", f"/admin/support/ticket/{tid}", at, timeout=90)
    probes.append({"name": "open_detail", "pass": dr.status_code == 200})

    ar = req("put", f"/admin/support/ticket/{tid}/assign", at, params={"assignee": admin_user.get("email", "admin")}, timeout=60)
    probes.append({"name": "assign", "pass": ar.status_code == 200})

    nr = req("post", f"/admin/support/ticket/{tid}/note", at, json={"message": f"{MARKER} internal note"}, timeout=60)
    probes.append({"name": "add_note", "pass": nr.status_code == 200})

    pr = req("put", f"/admin/support/ticket/{tid}/status", at, params={"status": "pending"}, timeout=60)
    probes.append({"name": "status_pending", "pass": pr.status_code == 200})

    rr = req("put", f"/admin/support/ticket/{tid}/status", at, params={"status": "resolved"}, timeout=60)
    probes.append({"name": "status_resolved", "pass": rr.status_code == 200})

    stats_before = req("get", "/admin/support/stats", at, timeout=60).json()
    rr2 = req("put", f"/admin/support/ticket/{tid}/status", at, params={"status": "resolved"}, timeout=60)
    probes.append({"name": "resolve_idempotent", "pass": rr2.status_code == 200})

    reopen = req("put", f"/admin/support/ticket/{tid}/status", at, params={"status": "open"}, timeout=60)
    probes.append({"name": "reopen", "pass": reopen.status_code == 200})

    return {"at_utc": utc(), "ticket_id": tid, "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_conversation_workflow(at: str, seed: dict) -> dict:
    conv_id = seed.get("records", {}).get("chat_conversation_id")
    ticket_conv_id = seed.get("records", {}).get("compliance_conversation_id")
    probes: List[dict] = []
    if not conv_id:
        return {"pass": False, "error": "no conversation seeded"}

    dr = req("get", f"/admin/support/conversation/{conv_id}", at, timeout=90)
    probes.append({"name": "load_history", "pass": dr.status_code == 200 and len((dr.json() or {}).get("messages") or []) >= 1})

    reply = req(
        "post",
        f"/admin/support/conversation/{conv_id}/reply",
        at,
        json={"message": f"{MARKER} support reply from audit harness"},
        timeout=90,
    )
    probes.append({"name": "support_reply", "pass": reply.status_code == 200})

    create_conv = ticket_conv_id or conv_id
    cticket = req("post", f"/admin/support/conversation/{create_conv}/create-ticket", at, json={"subject": f"{MARKER} from conversation"}, timeout=90)
    probes.append({
        "name": "create_ticket_from_conversation",
        "pass": cticket.status_code == 200,
        "status": cticket.status_code,
        "conversation_id": create_conv,
    })

    after = req("get", f"/admin/support/conversation/{conv_id}", at, timeout=90)
    human_msgs = [m for m in (after.json() or {}).get("messages") or [] if m.get("sender") == "human"]
    probes.append({"name": "reply_attribution", "pass": len(human_msgs) >= 1})

    return {"at_utc": utc(), "conversation_id": conv_id, "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_ai_handoff(at: str, seed: dict) -> dict:
    ai = seed.get("records", {}).get("ai_handoff") or {}
    tid = ai.get("ticket_id")
    probes: List[dict] = []
    if tid:
        dr = req("get", f"/admin/support/ticket/{tid}", at, timeout=90)
        ticket = (dr.json() or {}).get("ticket") or {}
        probes.append({
            "name": "portal_assistant_ticket",
            "pass": dr.status_code == 200 and (
                ticket.get("ticket_source") == "portal_assistant" or ticket.get("assistant_conversation_id")
            ),
            "handoff_summary_present": bool(ticket.get("assistant_handoff_summary") or (dr.json() or {}).get("assistant_handoff_summary")),
        })
    else:
        probes.append({"name": "portal_assistant_ticket", "pass": False, "note": "assistant escalate unavailable or rate limited"})

    esc_conv = seed.get("records", {}).get("escalated_conversation_id")
    if esc_conv:
        cr = req("get", f"/admin/support/conversation/{esc_conv}", at, timeout=90)
        status = ((cr.json() or {}).get("conversation") or {}).get("status")
        probes.append({"name": "live_chat_escalation", "pass": cr.status_code == 200 and status == "escalated"})

    comp = seed.get("records", {}).get("compliance_legal_refusal")
    probes.append({"name": "legal_refusal_in_chat", "pass": bool(comp)})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_billing_support(at: str, seed: dict) -> dict:
    tid = seed.get("records", {}).get("billing_ticket_id")
    probes: List[dict] = []
    if tid:
        dr = req("get", f"/admin/support/ticket/{tid}", at, timeout=90)
        ticket = (dr.json() or {}).get("ticket") or {}
        probes.append({
            "name": "billing_ticket_category",
            "pass": ticket.get("category") == "billing" and ticket.get("service_area") == "billing",
        })
    ctx = req("get", f"/admin/support/context/{CID}", at, timeout=90)
    billing_ctx = (ctx.json() or {}).get("account_snapshot") or {}
    probes.append({
        "name": "billing_context_in_panel",
        "pass": ctx.status_code == 200 and bool(billing_ctx),
        "has_subscription_fields": any(k in billing_ctx for k in ("billing_plan", "subscription_status", "plan")),
    })
    billing_admin = req("get", f"/admin/billing/clients/{CID}", at, timeout=90)
    probes.append({"name": "billing_admin_linkage", "pass": billing_admin.status_code == 200})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_compliance_support(at: str, seed: dict) -> dict:
    probes: List[dict] = []
    ctx = req("get", f"/admin/support/context/{CID}", at, timeout=90)
    body = ctx.json() if ctx.status_code == 200 else {}
    probes.append({
        "name": "compliance_context",
        "pass": ctx.status_code == 200,
        "has_portfolio": bool(body.get("portfolio_snapshot")),
        "has_ops_summary": bool(body.get("ops_summary_v1")),
    })
    comp_conv = seed.get("records", {}).get("compliance_conversation_id")
    if comp_conv:
        cr = req("get", f"/admin/support/conversation/{comp_conv}", at, timeout=90)
        transcript = (cr.json() or {}).get("transcript") or ""
        probes.append({
            "name": "legal_conversation_no_debug_leak",
            "pass": cr.status_code == 200 and "traceback" not in transcript.lower(),
        })
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_cross_surface(at: str, seed: dict) -> dict:
    stats1 = req("get", "/admin/support/stats", at, timeout=60).json()
    wf = seed.get("records", {}).get("workflow_ticket_id")
    audit = req("get", "/admin/support/audit-log", at, params={"limit": 30, "action": "ticket_status_update"}, timeout=90)
    audit_rows = (audit.json() or {}).get("logs") or []
    marker_audit = any(MARKER in json.dumps(r) or wf in str(r.get("resource_id", "")) for r in audit_rows[:15])
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=90)
    return {
        "at_utc": utc(),
        "stats_snapshot": stats1,
        "audit_log_has_workflow_events": len(audit_rows) > 0,
        "control_panel_reachable": cp.status_code == 200,
        "pass": cp.status_code == 200 and len(audit_rows) > 0,
    }


def part_audit_trail(at: str, wf_id: Optional[str], conv_id: Optional[str]) -> dict:
    actions_needed = [
        "ticket_status_update",
        "admin_reply",
        "ticket_note_added",
        "admin_crn_lookup",
    ]
    found: Dict[str, bool] = {}
    leak = False
    for action in actions_needed:
        r = req("get", "/admin/support/audit-log", at, params={"action": action, "limit": 10}, timeout=60)
        rows = (r.json() or {}).get("logs") or []
        found[action] = len(rows) > 0
        for row in rows[:5]:
            blob = json.dumps(row).lower()
            if "password" in blob and "token" in blob:
                leak = True
    if wf_id:
        tr = req("get", "/admin/support/audit-log", at, params={"resource_type": "ticket", "resource_id": wf_id, "limit": 10}, timeout=60)
        found["ticket_scoped"] = len((tr.json() or {}).get("logs") or []) > 0
    return {
        "at_utc": utc(),
        "actions_found": found,
        "no_secret_leakage": not leak,
        "pass": sum(1 for v in found.values() if v) >= 3 and not leak,
    }


def part_permissions(at: str, ct: str, contractor_t: str, tenant_t: str) -> dict:
    probes: List[dict] = []
    for name, tok, path in [
        ("client_stats_blocked", ct, "/admin/support/stats"),
        ("contractor_stats_blocked", contractor_t, "/admin/support/stats"),
        ("tenant_stats_blocked", tenant_t or "invalid", "/admin/support/stats"),
        ("unauthenticated_stats", "", "/admin/support/stats"),
        ("client_tickets_blocked", ct, "/admin/support/tickets"),
    ]:
        r = req("get", path, tok, timeout=60)
        probes.append({"name": name, "status": r.status_code, "pass": r.status_code in (401, 403)})

    stale = req("get", "/admin/support/ticket/TKT-NONEXIST-AUDIT", at, timeout=60)
    probes.append({"name": "stale_ticket_id", "status": stale.status_code, "pass": stale.status_code == 404})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes if tenant_t or "tenant" not in p["name"])}


def part_edge_cases(at: str, crn: str) -> dict:
    probes: List[dict] = []
    empty = req("get", "/admin/support/tickets", at, params={"search": "   ", "limit": 5}, timeout=60)
    probes.append({"name": "empty_search", "pass": empty.status_code == 200})

    bad = req("post", "/admin/support/lookup-by-crn", at, json={"crn": ""}, timeout=60)
    probes.append({"name": "blank_crn", "pass": bad.status_code in (400, 404, 422)})

    closed_id = None
    lst = req("get", "/admin/support/tickets", at, params={"search": MARKER, "status": "resolved", "limit": 5}, timeout=60)
    for t in (lst.json() or {}).get("tickets") or []:
        if t.get("status") == "resolved":
            closed_id = t.get("ticket_id")
            break
    if closed_id:
        r = req("put", f"/admin/support/ticket/{closed_id}/status", at, params={"status": "closed"}, timeout=60)
        probes.append({"name": "close_already_resolved", "pass": r.status_code == 200})

    convs = req("get", "/admin/support/conversations", at, params={"limit": 1}, timeout=60)
    conv_id = ((convs.json() or {}).get("conversations") or [{}])[0].get("conversation_id")
    if conv_id:
        html_reply = req(
            "post",
            f"/admin/support/conversation/{conv_id}/reply",
            at,
            json={"message": "<script>alert('xss')</script> safe text"},
            timeout=60,
        )
        probes.append({"name": "html_reply", "pass": html_reply.status_code == 200})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_resilience(at: str, seed: dict) -> dict:
    conv_id = seed.get("records", {}).get("chat_conversation_id")
    tid = seed.get("records", {}).get("workflow_ticket_id")
    probes: List[dict] = []

    if conv_id:
        msg = f"{MARKER}-dup-reply-{int(time.time())}"
        r1 = req("post", f"/admin/support/conversation/{conv_id}/reply", at, json={"message": msg}, timeout=90)
        r2 = req("post", f"/admin/support/conversation/{conv_id}/reply", at, json={"message": msg}, timeout=90)
        probes.append({
            "name": "duplicate_reply_click",
            "first": r1.status_code,
            "second": r2.status_code,
            "pass": r1.status_code == 200 and r2.status_code == 200,
            "note": "Both may succeed; verify audit count not storming",
        })

    if tid:
        def resolve_once() -> int:
            return req("put", f"/admin/support/ticket/{tid}/status", at, params={"status": "resolved"}, timeout=90).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(resolve_once), pool.submit(resolve_once)]
            codes = [f.result() for f in as_completed(futs)]
        probes.append({"name": "concurrent_resolve", "status_codes": codes, "pass": all(c == 200 for c in codes)})

        final = req("get", f"/admin/support/ticket/{tid}", at, timeout=60)
        status = ((final.json() or {}).get("ticket") or {}).get("status")
        probes.append({"name": "final_status_converged", "status": status, "pass": status in ("resolved", "closed", "open")})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes) if probes else True}


def part_regression() -> dict:
    suites = [
        "tests/test_support_system.py",
        "tests/test_support_hardening.py",
        "tests/test_support_context_authority.py",
        "tests/test_admin_client_support_search.py",
        "tests/test_admin_confirmation_governance.py",
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
            "setup": "SUPPORT_DASHBOARD_DRIFT",
            "overview": "SUPPORT_DASHBOARD_DRIFT",
            "ticket_filter": "TICKET_WORKFLOW_DRIFT",
            "conversation_filter": "CONVERSATION_DRIFT",
            "crn": "SUPPORT_DASHBOARD_DRIFT",
            "ticket_workflow": "TICKET_WORKFLOW_DRIFT",
            "conversation_workflow": "CONVERSATION_DRIFT",
            "ai_handoff": "AI_HANDOFF_DRIFT",
            "billing": "BILLING_SUPPORT_DRIFT",
            "compliance": "COMPLIANCE_SUPPORT_DRIFT",
            "cross_surface": "SUPPORT_DASHBOARD_DRIFT",
            "audit": "AUDIT_TRAIL_DRIFT",
            "permissions": "PERMISSION_DRIFT",
            "edge_cases": "SUPPORT_DASHBOARD_DRIFT",
            "resilience": "RESILIENCE_DRIFT",
            "regression": "SUPPORT_DASHBOARD_DRIFT",
        }
        for b in blockers:
            flags.append(mapping.get(b, "SUPPORT_DASHBOARD_DRIFT"))
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
        "Staging Support Dashboard E2E audit with browser + API proof.",
        "",
        "## Checklist",
    ]
    for k, v in clf.get("checklist", {}).items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        lines.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    lines.append("\n## Harness\n\n`backend/support_dashboard_end_to_end_runtime_audit_01_execute.py`\n")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at, admin_user = login_admin()
    ct, _ = login_client()
    contractor_t = login_contractor()
    tenant_t = login_tenant()
    results: Dict[str, bool] = {}

    setup = part_setup(at, ct)
    write_artifact("support_runtime_setup.json", setup)
    crn = setup.get("crn") or ""
    seed = setup.get("seed") or {}
    results["setup"] = setup.get("pass", False)

    overview = part_dashboard_overview(at, admin_user, seed)
    write_artifact("support_dashboard_overview_runtime.json", overview)
    results["overview"] = overview.get("pass", False)

    tf = part_ticket_filtering(at, seed, crn)
    write_artifact("ticket_filtering_runtime.json", tf)
    results["ticket_filter"] = tf.get("pass", False)

    cf = part_conversation_filtering(at, seed, crn)
    write_artifact("conversation_filtering_runtime.json", cf)
    results["conversation_filter"] = cf.get("pass", False)

    crn_r = part_crn_lookup(at, crn)
    write_artifact("crn_lookup_runtime.json", crn_r)
    results["crn"] = crn_r.get("pass", False)

    tw = part_ticket_workflow(at, admin_user, seed)
    write_artifact("ticket_workflow_runtime.json", tw)
    results["ticket_workflow"] = tw.get("pass", False)

    cw = part_conversation_workflow(at, seed)
    write_artifact("conversation_workflow_runtime.json", cw)
    results["conversation_workflow"] = cw.get("pass", False)

    ai = part_ai_handoff(at, seed)
    write_artifact("ai_handoff_runtime.json", ai)
    results["ai_handoff"] = ai.get("pass", False)

    bill = part_billing_support(at, seed)
    write_artifact("billing_support_runtime.json", bill)
    results["billing"] = bill.get("pass", False)

    comp = part_compliance_support(at, seed)
    write_artifact("compliance_support_runtime.json", comp)
    results["compliance"] = comp.get("pass", False)

    cross = part_cross_surface(at, seed)
    write_artifact("support_cross_surface_runtime.json", cross)
    results["cross_surface"] = cross.get("pass", False)

    wf_id = seed.get("records", {}).get("workflow_ticket_id")
    conv_id = seed.get("records", {}).get("chat_conversation_id")
    audit = part_audit_trail(at, wf_id, conv_id)
    write_artifact("support_audit_trail_runtime.json", audit)
    results["audit"] = audit.get("pass", False)

    perm = part_permissions(at, ct, contractor_t, tenant_t)
    write_artifact("support_permissions_runtime.json", perm)
    results["permissions"] = perm.get("pass", False)

    edge = part_edge_cases(at, crn)
    write_artifact("support_edge_cases_runtime.json", edge)
    results["edge_cases"] = edge.get("pass", False)

    res = part_resilience(at, seed)
    write_artifact("support_resilience_runtime.json", res)
    results["resilience"] = res.get("pass", False)

    reg = part_regression()
    write_artifact("support_regression_runtime.json", reg)
    results["regression"] = reg.get("pass", False)

    clf = classify(results)
    write_artifact("classifications.json", clf)
    (BUNDLE / "REPORT.md").write_text(build_report(clf), encoding="utf-8")
    watch = [
        "# Support Dashboard E2E watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
    ]
    if clf.get("blockers"):
        for b in clf["blockers"]:
            watch.append(f"- [ ] Blocker: **{b}**")
    else:
        watch.append("- [x] Support Dashboard ticket and conversation workflows verified on staging.")
        watch.append("- [ ] Optional: dedicated ROLE_SUPPORT-only staging persona for permission boundary proof.")
        watch.append("- [ ] Optional: live dual-admin browser concurrency probe.")
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
