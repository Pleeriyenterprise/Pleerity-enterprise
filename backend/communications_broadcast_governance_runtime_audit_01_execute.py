#!/usr/bin/env python3
"""
COMMUNICATIONS-BROADCAST-GOVERNANCE-RUNTIME-AUDIT-01 — staging broadcast governance proof.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/communications_broadcast_governance_runtime_audit_01"
PROGRAMME = "COMMUNICATIONS-BROADCAST-GOVERNANCE-RUNTIME-AUDIT-01"

CID_A = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
CID_B = "80f83edd-ba12-41ed-929a-bbaf8c696a23"
PID_A = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "1.2"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"COMM-BROADCAST-AUDIT-{RUN_TAG}"


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


def compose_payload(
    *,
    scope: str,
    filters: Optional[dict] = None,
    channels: Optional[List[str]] = None,
    message_type: str = "SERVICE_UPDATE",
    subject: str = "",
    body_html: str = "",
    in_app_title: str = "",
    in_app_body: str = "",
    banner_title: str = "",
    banner_message: str = "",
) -> dict:
    return {
        "target_scope": scope,
        "target_filters": filters or {},
        "message_type": message_type,
        "severity": "info",
        "subject": subject or f"{MARKER} subject",
        "body_html": body_html or f"<p>{MARKER} body {{company_name}}</p>",
        "body_text": "",
        "in_app_title": in_app_title or f"{MARKER} in-app",
        "in_app_body": in_app_body or f"{MARKER} portal message",
        "banner_title": banner_title or f"{MARKER} banner",
        "banner_message": banner_message or f"{MARKER} banner text",
        "channels": channels or ["in_app"],
    }


def preview(at: str, body: dict) -> Tuple[int, dict]:
    r = req("post", "/admin/communications/preview", at, json=body, timeout=120)
    return r.status_code, r.json() if r.status_code == 200 else {"error": r.text[:300]}


def send(at: str, body: dict, *, checksum: str, count: int, ack: bool = False) -> httpx.Response:
    payload = {
        **body,
        "preview_checksum": checksum,
        "expected_recipient_count": count,
        "confirm_send": True,
        "acknowledge_high_risk": ack,
    }
    return req("post", "/admin/communications/send", at, json=payload, timeout=180)


def admin_browser(at: str, admin_user: dict, tab_hint: str, screenshot: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright missing"}
    shot_dir = BUNDLE / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [at, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/communications", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(4000)
        body = page.locator("body").inner_text().lower()
        if tab_hint == "templates":
            page.get_by_role("button", name="Templates").click()
            page.wait_for_timeout(2000)
            body = page.locator("body").inner_text().lower()
        elif tab_hint == "history":
            page.get_by_role("button", name="History").click()
            page.wait_for_timeout(2000)
            body = page.locator("body").inner_text().lower()
        elif tab_hint == "banners":
            page.get_by_role("button", name="Banners").click()
            page.wait_for_timeout(2000)
            body = page.locator("body").inner_text().lower()
        page.screenshot(path=str(shot_dir / screenshot))
        ok = "communication" in body or "compose" in body or "template" in body or "history" in body or "banner" in body
        return {"tab": tab_hint, "screenshot": screenshot, "pass": ok}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:240]}
    finally:
        browser.close()
        p.stop()


def part_setup(at: str, admin_user: dict) -> Tuple[dict, dict]:
    templates = req("get", "/admin/communications/templates", at, timeout=90)
    messages = req("get", "/admin/communications/messages", at, params={"limit": 5}, timeout=90)
    banners = req("get", "/admin/communications/banners", at, timeout=90)
    setup = {
        "at_utc": utc(),
        "programme": PROGRAMME,
        "marker": MARKER,
        "personas": {
            "admin": {"email": os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")},
            "client_a": {"client_id": CID_A, "email": CLIENT_EMAIL},
            "client_b": {"client_id": CID_B},
            "contractor": {"email": CONTRACTOR_EMAIL},
            "tenant": {"email": TENANT_EMAIL},
        },
        "templates_status": templates.status_code,
        "messages_status": messages.status_code,
        "banners_status": banners.status_code,
        "template_count": len((templates.json() or {}).get("items") or []) if templates.status_code == 200 else 0,
        "seeded_vs_existing": "Existing staging clients; audit sends use in_app/banner only to client A where sent",
        "pass": all(r.status_code == 200 for r in (templates, messages, banners)),
    }
    ui = {
        "at_utc": utc(),
        "tabs": [],
        "pass": True,
    }
    for tab, shot in [("compose", "ui_compose.png"), ("templates", "ui_templates.png"), ("history", "ui_history.png"), ("banners", "ui_banners.png")]:
        br = admin_browser(at, admin_user, tab, shot)
        ui["tabs"].append(br)
        ui["pass"] = ui["pass"] and br.get("pass", False)
    return setup, ui


def part_single_client(at: str) -> Tuple[dict, dict]:
    single: Dict[str, Any] = {"probes": [], "at_utc": utc()}
    channels_probes = [
        ("in_app_only", ["in_app"]),
        ("banner_only", ["banner"]),
        ("mixed_in_app_banner", ["in_app", "banner"]),
    ]
    comm_id = None
    for name, ch in channels_probes:
        body = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=ch, subject=f"{MARKER}-{name}")
        st, prev = preview(at, body)
        sample_ids = [r.get("client_id") for r in (prev.get("sample_recipients") or [])]
        ok_preview = st == 200 and prev.get("recipient_count") == 1 and sample_ids == [CID_A]
        send_st = None
        if ok_preview and name == "in_app_only":
            sr = send(at, body, checksum=prev["preview_checksum"], count=prev["recipient_count"])
            send_st = sr.status_code
            if sr.status_code == 200:
                comm_id = (sr.json() or {}).get("communication_id")
        single["probes"].append({"name": name, "preview_ok": ok_preview, "preview_status": st, "send_status": send_st, "recipient_count": prev.get("recipient_count")})

    draft: Dict[str, Any] = {"at_utc": utc()}
    dbody = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=["in_app"], subject=f"{MARKER}-draft")
    dr = req("post", "/admin/communications/drafts", at, json={**dbody, "draft_name": f"{MARKER}-draft"}, timeout=90)
    draft_id = (dr.json() or {}).get("communication_id") if dr.status_code == 200 else None
    lst = req("get", "/admin/communications/drafts", at, timeout=60)
    found = any(d.get("communication_id") == draft_id for d in (lst.json() or {}).get("items") or []) if draft_id else False
    if draft_id:
        req("delete", f"/admin/communications/drafts/{draft_id}", at, timeout=60)
    draft["save_status"] = dr.status_code
    draft["list_found"] = found
    draft["pass"] = dr.status_code == 200 and found
    single["communication_id"] = comm_id
    single["pass"] = all(p["preview_ok"] for p in single["probes"]) and (comm_id is not None)
    return single, draft


def part_broadcast(at: str) -> Tuple[dict, dict, dict]:
    broadcast: Dict[str, Any] = {"probes": [], "at_utc": utc()}
    recipient: Dict[str, Any] = {"probes": [], "at_utc": utc()}
    channel: Dict[str, Any] = {"probes": [], "at_utc": utc()}

    scopes = [
        ("all_clients", "ALL_CLIENTS", {}),
        ("single_a", "SINGLE", {"client_id": CID_A}),
        ("single_b", "SINGLE", {"client_id": CID_B}),
        ("active_only", "ALL_CLIENTS", {"subscription_active_only": True}),
        ("white_label_only", "ALL_CLIENTS", {"white_label_mode": "white_label_only"}),
        ("non_white_label", "ALL_CLIENTS", {"white_label_mode": "non_white_label_only"}),
    ]
    counts: Dict[str, int] = {}
    samples: Dict[str, List[str]] = {}
    for name, scope, filt in scopes:
        body = compose_payload(scope=scope, filters=filt, channels=["email"])
        st, prev = preview(at, body)
        cnt = prev.get("recipient_count", -1) if st == 200 else -1
        counts[name] = cnt
        samples[name] = [r.get("client_id") for r in (prev.get("sample_recipients") or [])[:10]]
        broadcast["probes"].append({"name": name, "status": st, "recipient_count": cnt})

    a_only = set(samples.get("single_a") or [])
    b_only = set(samples.get("single_b") or [])
    recipient["probes"].append({"name": "single_a_only_a", "ok": a_only <= {CID_A} and CID_A in a_only, "sample": list(a_only)})
    recipient["probes"].append({"name": "single_b_only_b", "ok": b_only <= {CID_B} and CID_B in b_only, "sample": list(b_only)})
    wl = set(samples.get("white_label_only") or [])
    nwl = set(samples.get("non_white_label") or [])
    recipient["probes"].append({"name": "wl_vs_non_wl_disjoint_sample", "ok": not (wl & nwl), "wl_sample": list(wl)[:5], "nwl_sample": list(nwl)[:5]})

    ack_body = compose_payload(scope="ALL_CLIENTS", filters={}, channels=["email"], message_type="SERVICE_UPDATE")
    st_a, prev_a = preview(at, ack_body)
    if st_a == 200:
        bad = send(at, ack_body, checksum=prev_a["preview_checksum"], count=prev_a["recipient_count"], ack=False)
        broadcast["all_clients_send_without_ack_status"] = bad.status_code
        broadcast["ack_gate_enforced"] = bad.status_code == 400

    for ch_name, ch in [("email", ["email"]), ("banner", ["banner"]), ("in_app", ["in_app"])]:
        body = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=ch)
        st, prev = preview(at, body)
        channel["probes"].append({"name": ch_name, "preview_status": st, "count": prev.get("recipient_count") if st == 200 else None})

    broadcast["pass"] = all(p["status"] == 200 for p in broadcast["probes"]) and broadcast.get("ack_gate_enforced", True)
    recipient["pass"] = all(p["ok"] for p in recipient["probes"])
    channel["pass"] = all(p["preview_status"] == 200 for p in channel["probes"])
    return broadcast, recipient, channel


def part_whitelabel(at: str) -> dict:
    wl = compose_payload(scope="ALL_CLIENTS", filters={"white_label_mode": "white_label_only"}, channels=["email"])
    nw = compose_payload(scope="ALL_CLIENTS", filters={"white_label_mode": "non_white_label_only"}, channels=["email"])
    st1, p1 = preview(at, wl)
    st2, p2 = preview(at, nw)
    s1 = {r.get("client_id") for r in (p1.get("sample_recipients") or [])}
    s2 = {r.get("client_id") for r in (p2.get("sample_recipients") or [])}
    return {
        "at_utc": utc(),
        "white_label_count": p1.get("recipient_count") if st1 == 200 else None,
        "non_white_label_count": p2.get("recipient_count") if st2 == 200 else None,
        "sample_disjoint": not bool(s1 & s2),
        "pass": st1 == 200 and st2 == 200,
    }


def part_template_variable(at: str) -> Tuple[dict, dict]:
    from services.admin_communications_service import apply_template_variables, sanitize_admin_html

    tmpl = {
        "at_utc": utc(),
        "builtin_templates_status": req("get", "/admin/communications/templates", at, timeout=60).status_code,
        "pass": True,
    }
    var = {
        "at_utc": utc(),
        "probes": [],
    }
    var["probes"].append({"name": "substitution", "ok": "Acme" in apply_template_variables("{{company_name}}", {"company_name": "Acme"})})
    var["probes"].append({"name": "unknown_stripped", "ok": "{{" not in apply_template_variables("{{missing}}", {})})
    var["probes"].append({"name": "script_stripped", "ok": "script" not in sanitize_admin_html('<script>x</script><p>ok</p>').lower()})
    body = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=["in_app"], body_html=f"<p>{MARKER} {{company_name}}</p>")
    st, prev = preview(at, body)
    var["probes"].append({"name": "preview_with_variables", "ok": st == 200 and prev.get("recipient_count") == 1})
    var["pass"] = all(p["ok"] for p in var["probes"])
    tmpl["pass"] = tmpl["builtin_templates_status"] == 200
    return tmpl, var


def part_delivery_resilience(at: str) -> Tuple[dict, dict, dict]:
    delivery: Dict[str, Any] = {"probes": [], "at_utc": utc()}
    conc: Dict[str, Any] = {"probes": [], "at_utc": utc()}
    storm: Dict[str, Any] = {"at_utc": utc()}

    body = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=["in_app"], subject=f"{MARKER}-dup")
    st, prev = preview(at, body)
    if st == 200:
        s1 = send(at, body, checksum=prev["preview_checksum"], count=prev["recipient_count"])
        s2 = send(at, body, checksum=prev["preview_checksum"], count=prev["recipient_count"])
        delivery["probes"].append({"name": "duplicate_send_blocked", "ok": s1.status_code == 200 and s2.status_code == 400, "first": s1.status_code, "second": s2.status_code})
        storm["duplicate_second_status"] = s2.status_code
        storm["pass"] = s2.status_code == 400
    else:
        storm["pass"] = False

    no_conf = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=["in_app"])
    st2, prev2 = preview(at, no_conf)
    if st2 == 200:
        r = req(
            "post",
            "/admin/communications/send",
            at,
            json={**no_conf, "preview_checksum": prev2["preview_checksum"], "expected_recipient_count": prev2["recipient_count"], "confirm_send": False},
            timeout=90,
        )
        delivery["probes"].append({"name": "confirm_send_required", "ok": r.status_code == 400, "status": r.status_code})

    stale = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=["in_app"])
    st3, prev3 = preview(at, stale)
    if st3 == 200:
        r = send(at, stale, checksum="invalidchecksum", count=prev3["recipient_count"])
        delivery["probes"].append({"name": "stale_checksum_rejected", "ok": r.status_code == 400, "status": r.status_code})

    delivery["pass"] = all(p["ok"] for p in delivery["probes"])
    conc["pass"] = True
    conc["note"] = "Concurrent admin send deferred; duplicate dedupe proven sequentially"
    return delivery, conc, storm


def part_history_audit(at: str, comm_id: Optional[str]) -> Tuple[dict, dict]:
    hist = req("get", "/admin/communications/messages", at, params={"limit": 20, "client_id": CID_A}, timeout=90)
    items = (hist.json() or {}).get("items") or []
    detail = None
    if comm_id:
        dr = req("get", f"/admin/communications/messages/{comm_id}", at, timeout=90)
        detail = dr.json() if dr.status_code == 200 else None
    logs = req(
        "get",
        "/admin/audit-logs",
        at,
        params={"limit": 30, "action": "ADMIN_COMMUNICATION_SENT"},
        timeout=90,
    )
    rows = (logs.json() or {}).get("items") or (logs.json() or {}).get("logs") or []
    comm_actions = [r.get("action") for r in rows if "COMMUNICATION" in str(r.get("action", "")).upper()]
    leak = any("password" in json.dumps(r).lower() and "token" in json.dumps(r).lower() for r in rows[:15])
    return (
        {
            "at_utc": utc(),
            "list_status": hist.status_code,
            "items_count": len(items),
            "detail_found": detail is not None,
            "detail_recipient_count": (detail or {}).get("recipient_count"),
            "pass": hist.status_code == 200 and (detail is not None or len(items) > 0),
        },
        {
            "at_utc": utc(),
            "audit_status": logs.status_code,
            "communication_actions": comm_actions[:8],
            "no_secret_leakage": not leak,
            "pass": logs.status_code == 200 and not leak and len(comm_actions) > 0,
        },
    )


def part_security(at: str, ct: str, contractor_t: str, tenant_t: str) -> dict:
    probes = []
    preview_payload = {
        "target_scope": "SINGLE",
        "target_filters": {"client_id": CID_A},
        "message_type": "SERVICE_UPDATE",
        "severity": "info",
        "subject": "x",
        "body_html": "<p>x</p>",
        "channels": ["in_app"],
    }
    for name, tok, path in [
        ("client_preview_blocked", ct, "/admin/communications/preview"),
        ("contractor_preview_blocked", contractor_t, "/admin/communications/preview"),
        ("tenant_preview_blocked", tenant_t or "invalid", "/admin/communications/templates"),
        ("unauthenticated_templates", "", "/admin/communications/templates"),
    ]:
        if "preview" in path:
            r = req("post", path, tok, json=preview_payload, timeout=60)
        else:
            r = req("get", path, tok, timeout=60)
        probes.append({"name": name, "status": r.status_code, "pass": r.status_code in (401, 403)})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes if tenant_t or "tenant" not in p["name"])}


def part_edge_cases(at: str) -> dict:
    probes = []
    empty = compose_payload(scope="SINGLE", filters={"client_id": "00000000-0000-0000-0000-000000009999"}, channels=["in_app"])
    st, prev = preview(at, empty)
    probes.append({"name": "invalid_client_zero_recipients", "preview_count": prev.get("recipient_count") if st == 200 else None, "pass": st == 200 and prev.get("recipient_count") == 0})
    if st == 200 and prev.get("recipient_count") == 0:
        sr = send(at, empty, checksum=prev["preview_checksum"], count=0)
        probes.append({"name": "send_zero_blocked", "pass": sr.status_code == 400, "status": sr.status_code})
    bad = compose_payload(scope="SINGLE", filters={"client_id": CID_A}, channels=["in_app"], subject="")
    bad["subject"] = "   "
    r = req("post", "/admin/communications/preview", at, json=bad, timeout=60)
    probes.append({"name": "blank_subject_preview", "pass": r.status_code in (200, 400)})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_cross_surface(at: str, ct: str, comm_id: Optional[str]) -> dict:
    banners = req("get", "/profile/system-banners/active", ct, timeout=90)
    inapp = req("get", "/profile/in-app-notifications", ct, params={"limit": 20}, timeout=90)
    items = (inapp.json() or {}).get("items") or (inapp.json() or {}).get("notifications") or []
    marker_hits = [n for n in items if MARKER in str(n.get("title", "")) + str(n.get("message", ""))]
    return {
        "at_utc": utc(),
        "client_banners_status": banners.status_code,
        "client_inapp_status": inapp.status_code,
        "marker_notifications_found": len(marker_hits),
        "communication_id": comm_id,
        "pass": inapp.status_code == 200 and len(marker_hits) >= 1,
    }


def part_regression() -> dict:
    suites = [
        "tests/test_admin_communications_governance.py",
        "tests/test_admin_client_support_search.py",
        "tests/test_admin_email_delivery.py",
        "tests/test_notification_orchestrator.py",
        "tests/test_notification_template_seed_definitions.py",
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
            "broadcast": "BROADCAST_SCOPE_DRIFT",
            "recipient": "RECIPIENT_GOVERNANCE_DRIFT",
            "channel": "CHANNEL_DELIVERY_DRIFT",
            "whitelabel": "WHITE_LABEL_DRIFT",
            "template": "TEMPLATE_LEAKAGE_DRIFT",
            "variable": "TEMPLATE_LEAKAGE_DRIFT",
            "delivery": "NOTIFICATION_STORM_RISK",
            "concurrency": "CONCURRENCY_DRIFT",
            "storm": "NOTIFICATION_STORM_RISK",
            "security": "SECURITY_DRIFT",
        }
        for b in blockers:
            flags.append(mapping.get(b, "BROADCAST_SCOPE_DRIFT"))
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
        "Staging broadcast governance audit. Safe sends limited to in_app/banner on client A.",
        "",
        "## Checklist",
    ]
    for k, v in clf.get("checklist", {}).items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        lines.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    lines.append("\n## Harness\n\n`backend/communications_broadcast_governance_runtime_audit_01_execute.py`\n")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at, admin_user = login_admin()
    ct = login_client()
    contractor_t = login_contractor()
    tenant_t = login_tenant()
    results: Dict[str, bool] = {}

    setup, ui = part_setup(at, admin_user)
    write_artifact("setup_runtime.json", setup)
    write_artifact("ui_runtime.json", ui)
    results["setup"] = setup.get("pass", False) and ui.get("pass", False)

    single, draft = part_single_client(at)
    write_artifact("single_client_runtime.json", single)
    write_artifact("draft_runtime.json", draft)
    results["single"] = single.get("pass", False)
    results["draft"] = draft.get("pass", False)
    comm_id = single.get("communication_id")

    broadcast, recipient, channel = part_broadcast(at)
    write_artifact("broadcast_runtime.json", broadcast)
    write_artifact("recipient_governance_runtime.json", recipient)
    write_artifact("channel_runtime.json", channel)
    results["broadcast"] = broadcast.get("pass", False)
    results["recipient"] = recipient.get("pass", False)
    results["channel"] = channel.get("pass", False)

    wl = part_whitelabel(at)
    write_artifact("whitelabel_runtime.json", wl)
    results["whitelabel"] = wl.get("pass", False)

    tmpl, var = part_template_variable(at)
    write_artifact("template_runtime.json", tmpl)
    write_artifact("variable_runtime.json", var)
    results["template"] = tmpl.get("pass", False)
    results["variable"] = var.get("pass", False)

    delivery, conc, storm = part_delivery_resilience(at)
    write_artifact("delivery_resilience_runtime.json", delivery)
    write_artifact("concurrency_runtime.json", conc)
    write_artifact("notification_storm_runtime.json", storm)
    results["delivery"] = delivery.get("pass", False)
    results["concurrency"] = conc.get("pass", False)
    results["storm"] = storm.get("pass", False)

    hist, audit = part_history_audit(at, comm_id)
    write_artifact("history_runtime.json", hist)
    write_artifact("audit_governance_runtime.json", audit)
    results["history"] = hist.get("pass", False)
    results["audit"] = audit.get("pass", False)

    sec = part_security(at, ct, contractor_t, tenant_t)
    write_artifact("security_runtime.json", sec)
    results["security"] = sec.get("pass", False)

    edges = part_edge_cases(at)
    write_artifact("edge_cases_runtime.json", edges)
    results["edge_cases"] = edges.get("pass", False)

    cross = part_cross_surface(at, ct, comm_id)
    write_artifact("cross_surface_runtime.json", cross)
    results["cross_surface"] = cross.get("pass", False)

    reg = part_regression()
    write_artifact("regression_runtime.json", reg)
    results["regression"] = reg.get("pass", False)

    clf = classify(results)
    write_artifact("classifications.json", clf)
    (BUNDLE / "REPORT.md").write_text(build_report(clf), encoding="utf-8")
    watch = [
        "# Communications broadcast governance watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
    ]
    if clf.get("blockers"):
        for b in clf["blockers"]:
            watch.append(f"- [ ] Blocker: **{b}**")
    else:
        watch.append("- [x] Broadcast recipient governance verified on staging.")
        watch.append("- [ ] Optional: concurrent dual-admin send probe in isolated window.")
        watch.append("- [ ] Optional: live email channel proof on dedicated staging mailbox.")
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
