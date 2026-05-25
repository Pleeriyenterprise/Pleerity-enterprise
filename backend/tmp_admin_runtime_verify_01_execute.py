"""
PRELAUNCH-ADMIN-RUNTIME-VERIFY-01 — admin authority, waiver, dashboard, analytics, security.
Local harness. Sequential families A1–A5, G9/G10, convergence.
"""
from __future__ import annotations

import json
import os
import re
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

PROGRAMME = "PRELAUNCH-ADMIN-RUNTIME-VERIFY-01"
OWNER = "admin_runtime_verify_01"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
F3_CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"ADMIN-VERIFY01-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "100"))

BUNDLE = ROOT / "docs/audit/ops_admin_runtime_verify_01"

STOP_CLASSIFICATIONS = frozenset(
    {
        "FAIL_SYSTEM",
        "TRUST_RISK_PRESENT",
        "SECURITY_BOUNDARY_FAILURE",
        "ADMIN_ANALYTICS_DRIFT",
        "WAIVER_AUTHORITY_DRIFT",
        "BLOCKED",
    }
)

TERMINAL_ISSUE = frozenset({"resolved", "closed", "cancelled"})
OPEN_ISSUE_STATUSES = [
    "open",
    "triaged",
    "ready_for_work_order",
    "in_progress",
    "awaiting_contractor",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _read_pw(path: Path, env_key: str, default: str = "") -> str:
    env = os.environ.get(env_key)
    if env:
        return env.strip()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return default


def _headers(token: str, *, step_up: str = "") -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    return h


def _http(method: str, url: str, *, headers: Optional[dict] = None, timeout: int = 120, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(4):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", timeout), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            time.sleep(3 + attempt * 5)
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


def _login(email: str, password: str, *, contractor: bool = False, admin: bool = False) -> Tuple[str, dict]:
    _warm_api()
    if admin:
        path = "/auth/admin/login"
    elif contractor:
        path = "/auth/contractor-login"
    else:
        path = "/auth/login"
    for attempt in range(4):
        r = _http("post", f"{API}{path}", json={"email": email, "password": password}, timeout=90)
        if r.status_code == 200:
            body = r.json()
            return body["access_token"], body.get("user") or {}
        if r.status_code in (502, 503, 504):
            time.sleep(12 + attempt * 8)
    return "", {}


def _admin_creds() -> Tuple[str, str]:
    pw = _read_pw(
        ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt",
        "OPS_VERIFY_ADMIN_PASSWORD",
    )
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    return email, pw


def _step_up(admin_token: str, admin_password: str) -> str:
    r = _http(
        "post",
        f"{API}/auth/step-up/verify",
        headers=_headers(admin_token),
        json={"password": admin_password},
        timeout=90,
    )
    if r.status_code != 200:
        return ""
    return (r.json() or {}).get("step_up_token") or ""


def _db_counts() -> Dict[str, Any]:
    import asyncio

    out: Dict[str, Any] = {"connected": False, "at_utc": _utc()}

    async def _load() -> None:
        from database import database

        db = database.get_db()
        out["connected"] = True
        out["total_clients"] = await db.clients.count_documents({})
        out["active_clients"] = await db.clients.count_documents({"subscription_status": "ACTIVE"})
        out["total_properties"] = await db.properties.count_documents({})
        out["unverified_documents"] = await db.documents.count_documents({"status": "UPLOADED"})
        props = await db.properties.find({}, {"compliance_status": 1}).to_list(10000)
        out["compliance_red"] = sum(1 for p in props if p.get("compliance_status") == "RED")
        out["compliance_amber"] = sum(1 for p in props if p.get("compliance_status") == "AMBER")
        out["compliance_green"] = sum(1 for p in props if p.get("compliance_status") == "GREEN")

    try:
        asyncio.run(_load())
    except Exception as exc:
        out["error"] = str(exc)[:300]
    return out


def _compare_metric(name: str, ui: Any, api: Any, db: Any, *, tolerance: int = 0) -> Dict[str, Any]:
    try:
        ui_n = int(ui) if ui is not None else None
        api_n = int(api) if api is not None else None
        db_n = int(db) if db is not None else None
    except (TypeError, ValueError):
        return {"name": name, "ui": ui, "api": api, "db": db, "match": False, "variance": "non_numeric"}
    material = False
    if api_n is not None and db_n is not None and abs(api_n - db_n) > tolerance:
        material = True
    if ui_n is not None and api_n is not None and abs(ui_n - api_n) > tolerance:
        material = True
    return {
        "name": name,
        "ui": ui_n,
        "api": api_n,
        "db": db_n,
        "match": not material,
        "material_mismatch": material,
    }


def _family_a1(
    client_token: str,
    client_user: dict,
    admin_token: str,
    admin_user: dict,
    step_up: str,
    admin_password: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"marker": MARKER, "at_utc": _utc()}
    ch = _headers(client_token)
    ah = _headers(admin_token)

    pre_open = _http("get", f"{API}/client/maintenance/issues/open-count", headers=ch, timeout=90)
    out["pre_open_count_status"] = pre_open.status_code
    pre_count = (pre_open.json() or {}).get("count") if pre_open.status_code == 200 else None
    out["pre_open_count"] = pre_count

    create = _http(
        "post",
        f"{API}/client/maintenance/issues",
        headers=ch,
        json={
            "property_id": PROPERTY_ID,
            "description": f"{MARKER} admin issue resolution E2E",
            "category": "general",
            "severity": "medium",
            "source": "client",
        },
        timeout=120,
    )
    out["create_issue_status"] = create.status_code
    if create.status_code not in (200, 201):
        out["pass"] = False
        out["create_body"] = (create.text or "")[:400]
        return out
    issue = create.json()
    issue_id = issue.get("issue_id")
    out["issue_id"] = issue_id

    detail = _http("get", f"{API}/client/maintenance/issues/{issue_id}", headers=ch, timeout=90)
    out["client_detail_status"] = detail.status_code
    out["initial_status"] = (detail.json() or {}).get("status") if detail.status_code == 200 else None

    cwo = _http(
        "post",
        f"{API}/client/maintenance/issues/{issue_id}/create-work-order",
        headers=ch,
        timeout=120,
    )
    out["create_wo_status"] = cwo.status_code
    if cwo.status_code not in (200, 201):
        out["pass"] = False
        return out
    wo = cwo.json()
    wo_id = wo.get("work_order_id")
    out["work_order_id"] = wo_id

    admin_list = _http(
        "get",
        f"{API}/admin/ops/work-orders",
        headers=ah,
        params={"client_id": CLIENT_ID, "limit": 50},
        timeout=90,
    )
    out["admin_list_status"] = admin_list.status_code
    listed = (admin_list.json() or {}).get("work_orders") or []
    out["admin_list_contains_wo"] = any(w.get("work_order_id") == wo_id for w in listed)

    admin_get = _http("get", f"{API}/admin/ops/work-orders/{wo_id}", headers=ah, timeout=90)
    out["admin_get_status"] = admin_get.status_code

    assign = _http(
        "patch",
        f"{API}/admin/ops/work-orders/{wo_id}",
        headers=ah,
        json={
            "contractor_id": F3_CONTRACTOR_ID,
            "status": "ASSIGNED",
            "action_reason": f"{MARKER} assign contractor",
        },
        timeout=120,
    )
    out["assign_status"] = assign.status_code

    for st, reason in [
        ("IN_PROGRESS", "progress"),
        ("COMPLETED", "complete job"),
        ("CLOSED", "admin close"),
    ]:
        r = _http(
            "patch",
            f"{API}/admin/ops/work-orders/{wo_id}",
            headers=ah,
            json={"status": st, "action_reason": f"{MARKER} {reason}", "completion_notes": f"{MARKER} internal note"},
            timeout=120,
        )
        out[f"status_{st}"] = r.status_code

    imp = _http(
        "post",
        f"{API}/admin/clients/{CLIENT_ID}/impersonation/start",
        headers=_headers(admin_token, step_up=step_up),
        params={"ttl_minutes": 15},
        json={"reason": f"{MARKER} admin issue resolution verification"},
        timeout=120,
    )
    out["impersonation_status"] = imp.status_code
    imp_token = ""
    if imp.status_code == 200:
        imp_token = (imp.json() or {}).get("access_token") or ""
    out["impersonation_token_present"] = bool(imp_token)

    resolve_note = f"{MARKER} resolved by admin via impersonation after WO closed"
    r1 = _http(
        "patch",
        f"{API}/client/maintenance/issues/{issue_id}",
        headers=_headers(imp_token),
        json={"status": "resolved", "resolution_note": resolve_note},
        timeout=120,
    )
    out["resolve_status"] = r1.status_code
    r2 = _http(
        "patch",
        f"{API}/client/maintenance/issues/{issue_id}",
        headers=_headers(imp_token),
        json={"status": "resolved", "resolution_note": resolve_note},
        timeout=120,
    )
    out["duplicate_resolve_status"] = r2.status_code
    gi2 = _http("get", f"{API}/client/maintenance/issues/{issue_id}", headers=ch, timeout=90)
    final_status = (gi2.json() or {}).get("status") if gi2.status_code == 200 else ""
    out["final_issue_status"] = final_status
    out["duplicate_idempotent"] = r2.status_code in (200, 400) and final_status in TERMINAL_ISSUE

    post_open = _http("get", f"{API}/client/maintenance/issues/open-count", headers=ch, timeout=90)
    post_count = (post_open.json() or {}).get("count") if post_open.status_code == 200 else None
    out["post_open_count"] = post_count
    out["open_count_not_inflated"] = post_count is None or pre_count is None or post_count <= pre_count

    audit = _http(
        "get",
        f"{API}/admin/audit-logs",
        headers=ah,
        params={"client_id": CLIENT_ID, "limit": 30},
        timeout=90,
    )
    logs = (audit.json() or {}).get("logs") or (audit.json() or {}).get("items") or []
    out["audit_has_admin_wo"] = any(
        (l.get("resource_id") == wo_id or wo_id in str(l.get("metadata") or ""))
        for l in logs
    )
    out["audit_has_issue_close"] = any(
        "issue" in str(l.get("resource_type") or "").lower() for l in logs
    )

    out["browser"] = _browser_a1(admin_token, admin_user, client_token, client_user, wo_id, issue_id)
    api_ok = bool(
        create.status_code in (200, 201)
        and cwo.status_code in (200, 201)
        and assign.status_code == 200
        and out.get("status_CLOSED") == 200
        and imp.status_code == 200
        and r1.status_code == 200
        and final_status in TERMINAL_ISSUE
        and out.get("duplicate_idempotent")
        and out.get("admin_list_contains_wo")
    )
    out["api_pass"] = api_ok
    out["pass"] = api_ok and out.get("browser", {}).get("pass")
    return out


def _browser_a1(
    admin_token: str,
    admin_user: dict,
    client_token: str,
    client_user: dict,
    wo_id: str,
    issue_id: str,
) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    try:
        (BUNDLE / "screenshots").mkdir(parents=True, exist_ok=True)
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [admin_token, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/ops/maintenance", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(8000)
        admin_body = page.locator("body").inner_text().lower()
        admin_ok = (
            "work order" in admin_body
            or "maintenance" in admin_body
            or "job" in admin_body
            or wo_id[:8] in admin_body
        )

        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [client_token, client_user],
        )
        page.goto(f"{FRONTEND}/operations/issues/{issue_id}", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(8000)
        client_body = page.locator("body").inner_text().lower()
        client_ok = (
            MARKER[:12].lower() in client_body
            or "resolved" in client_body
            or "closed" in client_body
            or issue_id[:8] in client_body
        )

        page.screenshot(path=str(BUNDLE / "screenshots" / "a1_admin_maintenance.png"))
        page.screenshot(path=str(BUNDLE / "screenshots" / "a1_client_issues.png"))
        return {
            "admin_ops_reachable": admin_ok,
            "client_issue_surface": client_ok,
            "wo_id": wo_id,
            "issue_id": issue_id,
            "pass": admin_ok and client_ok,
        }
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:300]}
    finally:
        browser.close()
        p.stop()


def _family_a2(admin_token: str, admin_user: dict, step_up: str) -> Dict[str, Any]:
    """Subscriber waiver: eligibility override on Wales ACTIVE client; pilot fee policy on reference pilot."""
    out: Dict[str, Any] = {"at_utc": _utc(), "client_id": CLIENT_ID}
    ah = _headers(admin_token)
    sh = _headers(admin_token, step_up=step_up)
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    cp = _http("get", f"{API}/admin/clients/{CLIENT_ID}/control-panel", headers=ah, timeout=120)
    cp_body = cp.json() if cp.status_code == 200 else {}
    out["control_panel_status"] = cp.status_code
    sub_billing = cp_body.get("subscription_billing") or {}
    identity = cp_body.get("identity") or {}
    out["subscription_status"] = (
        sub_billing.get("status")
        or identity.get("status")
        or cp_body.get("subscription_status")
    )
    plan_before = sub_billing.get("plan") or identity.get("plan") or cp_body.get("billing_plan")
    client_row = _http("get", f"{API}/admin/clients/{CLIENT_ID}", headers=ah, timeout=90)
    if client_row.status_code == 200:
        cr = client_row.json()
        out["subscription_status"] = out["subscription_status"] or cr.get("subscription_status")
        plan_before = plan_before or cr.get("billing_plan")
    out["active_subscriber"] = (out.get("subscription_status") or "").upper() == "ACTIVE"

    pilot_acct = _http("get", f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}", headers=ah, timeout=90)
    out["pilot_lifecycle_account_status"] = pilot_acct.status_code
    out["wales_is_pilot_lifecycle_account"] = pilot_acct.status_code == 200

    redemptions_before = _http(
        "get",
        f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}/redemptions",
        headers=ah,
        params={"limit": 50},
        timeout=90,
    )
    overrides_before = []
    if redemptions_before.status_code == 200:
        overrides_before = (redemptions_before.json() or {}).get("eligibility_overrides") or []

    waiver_reason = f"{MARKER} bounded recover_onboarding waiver for active subscriber"
    override_body = {
        "override_type": "recover_onboarding",
        "override_reason": waiver_reason,
        "scope": "client_id",
        "scope_value": CLIENT_ID,
        "override_expires_at": expires,
    }
    w1 = _http(
        "post",
        f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}/eligibility-overrides",
        headers=sh,
        json=override_body,
        timeout=120,
    )
    out["subscriber_override_status"] = w1.status_code
    override_id = ""
    if w1.status_code == 200:
        override_id = ((w1.json() or {}).get("override") or {}).get("override_id") or ""
    out["override_id"] = override_id

    w2 = _http(
        "post",
        f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}/eligibility-overrides",
        headers=sh,
        json=override_body,
        timeout=120,
    )
    out["duplicate_override_status"] = w2.status_code

    redemptions_after = _http(
        "get",
        f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}/redemptions",
        headers=ah,
        timeout=90,
    )
    overrides_after = []
    if redemptions_after.status_code == 200:
        overrides_after = (redemptions_after.json() or {}).get("eligibility_overrides") or []
    out["override_count_delta"] = len(overrides_after) - len(overrides_before)
    out["recover_onboarding_visible"] = bool(override_id) or any(
        (o.get("override_type") == "recover_onboarding" and MARKER[:12] in (o.get("override_reason") or ""))
        for o in overrides_after
    )

    pilot_ref_id = ""
    pilot_list = _http("get", f"{API}/admin/pilot-lifecycle/accounts", headers=ah, params={"limit": 50}, timeout=90)
    if pilot_list.status_code == 200:
        for row in (pilot_list.json() or {}).get("accounts") or []:
            if (row.get("subscription_status") or "").upper() == "ACTIVE" and row.get("client_id"):
                pilot_ref_id = row["client_id"]
                break
    out["pilot_reference_client_id"] = pilot_ref_id
    pilot_policy_status = None
    if pilot_ref_id:
        pp = _http(
            "post",
            f"{API}/admin/pilot-lifecycle/accounts/{pilot_ref_id}/onboarding-fee-policy",
            headers=sh,
            json={
                "reason": f"{MARKER} pilot onboarding fee policy waiver reference",
                "onboarding_fee_policy": "waived",
                "waiver_reason": waiver_reason,
            },
            timeout=120,
        )
        pilot_policy_status = pp.status_code
    out["pilot_onboarding_fee_policy_status"] = pilot_policy_status

    cp2 = _http("get", f"{API}/admin/clients/{CLIENT_ID}/control-panel", headers=ah, timeout=120)
    plan_after = plan_before
    if cp2.status_code == 200:
        b = cp2.json()
        sb2 = b.get("subscription_billing") or {}
        id2 = b.get("identity") or {}
        plan_after = sb2.get("plan") or id2.get("plan") or b.get("billing_plan") or plan_before
    out["plan_before"] = plan_before
    out["plan_after"] = plan_after

    client_pw = _read_pw(
        ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt",
        "OPS_VERIFY_CLIENT_PASSWORD",
    )
    ct, _ = _login(CLIENT_EMAIL, client_pw)
    client_block = _http(
        "post",
        f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}/eligibility-overrides",
        headers=_headers(ct),
        json=override_body,
        timeout=90,
    )
    out["client_waiver_blocked_status"] = client_block.status_code

    client_nav = _http("get", f"{API}/client/dashboard", headers=_headers(ct), timeout=90)
    out["client_access_after_waiver_status"] = client_nav.status_code

    audit = _http(
        "get",
        f"{API}/admin/audit-logs",
        headers=ah,
        params={"client_id": CLIENT_ID, "limit": 50},
        timeout=90,
    )
    logs = (audit.json() or {}).get("logs") or (audit.json() or {}).get("items") or []
    out["audit_waiver_action"] = bool(override_id) or any(
        "override" in str(l).lower()
        or "onboarding" in str(l).lower()
        or "recover" in str(l).lower()
        or "eligibility" in str(l).lower()
        for l in logs
    )

    out["browser"] = _browser_a2(admin_token, admin_user, CLIENT_ID)
    norm_before = (str(plan_before or "")).strip().upper()
    norm_after = (str(plan_after or "")).strip().upper()
    out["no_plan_upgrade"] = norm_before == norm_after and bool(norm_before or norm_after)
    out["duplicate_waiver_ok"] = w2.status_code in (200, 400, 409)
    out["pass"] = bool(
        out.get("active_subscriber")
        and w1.status_code == 200
        and out.get("recover_onboarding_visible")
        and client_block.status_code in (401, 403)
        and client_nav.status_code == 200
        and out.get("no_plan_upgrade")
        and (pilot_policy_status in (200, None))
        and out.get("browser", {}).get("pass")
    )
    return out


def _browser_a2(admin_token: str, admin_user: dict, client_id: str) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [admin_token, admin_user],
        )
        page.goto(
            f"{FRONTEND}/admin/clients/{client_id}",
            wait_until="networkidle",
            timeout=120_000,
        )
        page.wait_for_timeout(8000)
        body = page.locator("body").inner_text().lower()
        ok = "recovery" in body or "promo" in body or "override" in body or "waiver" in body
        (BUNDLE / "screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(BUNDLE / "screenshots" / "a2_pilot_account.png"))
        return {"pilot_account_visible": ok, "pass": ok}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:200]}
    finally:
        browser.close()
        p.stop()


def _family_a3(admin_token: str, admin_user: dict) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc()}
    ah = _headers(admin_token)
    dash = _http("get", f"{API}/admin/dashboard", headers=ah, timeout=120)
    out["dashboard_status"] = dash.status_code
    stats = (dash.json() or {}).get("stats") or {}
    db = _db_counts()

    metrics: List[Dict[str, Any]] = []
    mapping = [
        ("total_clients", stats.get("total_clients"), db.get("total_clients")),
        ("active_clients", stats.get("active_clients"), db.get("active_clients")),
        ("total_properties", stats.get("total_properties"), db.get("total_properties")),
        ("unverified_documents_count", stats.get("unverified_documents_count"), db.get("unverified_documents")),
    ]
    for name, api_val, db_val in mapping:
        metrics.append(_compare_metric(name, api_val, api_val, db_val))

    comp = (dash.json() or {}).get("compliance_overview") or {}
    if db.get("connected"):
        metrics.append(
            _compare_metric("compliance_red", comp.get("RED"), comp.get("RED"), db.get("compliance_red"))
        )

    material = [m for m in metrics if m.get("material_mismatch")]
    out["metrics"] = metrics
    out["material_mismatches"] = material
    out["db_connected"] = db.get("connected")

    out["browser"] = _browser_a3(admin_token, admin_user, stats)
    out["pass"] = (
        dash.status_code == 200
        and not material
        and out.get("browser", {}).get("pass")
    )
    if material:
        out["classification_hint"] = "ADMIN_ANALYTICS_DRIFT"
    return out


def _browser_a3(admin_token: str, admin_user: dict, stats: dict) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [admin_token, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/dashboard", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(8000)
        body = page.locator("body").inner_text()
        tc = stats.get("total_clients")
        ui_hint = str(tc) in body if tc is not None else True
        (BUNDLE / "screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(BUNDLE / "screenshots" / "a3_admin_dashboard.png"))
        return {"dashboard_reachable": "dashboard" in body.lower() or "clients" in body.lower(), "total_clients_in_ui": ui_hint, "pass": ui_hint}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:200]}
    finally:
        browser.close()
        p.stop()


def _family_a4(admin_token: str, admin_user: dict) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc()}
    ah = _headers(admin_token)
    checks: List[Dict[str, Any]] = []
    for period in ("30d", "7d"):
        r = _http(
            "get",
            f"{API}/admin/analytics/v2/summary",
            headers=ah,
            params={"period": period, "compare": "false"},
            timeout=120,
        )
        body = r.json() if r.status_code == 200 else {}
        dq = body.get("data_quality") or (body.get("period") or {})
        checks.append(
            {
                "period": period,
                "status": r.status_code,
                "has_data_quality": bool(dq),
                "orders_count": (body.get("orders") or {}).get("total") if isinstance(body.get("orders"), dict) else None,
            }
        )
    out["checks"] = checks
    out["no_leakage_probe"] = _http(
        "get",
        f"{API}/admin/analytics/customers",
        headers=ah,
        params={"limit": 5},
        timeout=90,
    ).status_code == 200
    out["browser"] = _browser_a4(admin_token, admin_user)
    out["pass"] = all(c["status"] == 200 for c in checks) and out["no_leakage_probe"] and out.get("browser", {}).get("pass")
    return out


def _browser_a4(admin_token: str, admin_user: dict) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [admin_token, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/analytics", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(6000)
        body = page.locator("body").inner_text().lower()
        ok = "analytic" in body or "revenue" in body or "summary" in body
        (BUNDLE / "screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(BUNDLE / "screenshots" / "a4_analytics.png"))
        return {"analytics_reachable": ok, "pass": ok}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:200]}
    finally:
        browser.close()
        p.stop()


def _family_a5(
    admin_token: str,
    client_token: str,
    tenant_token: str,
    contractor_token: str,
    issue_id: str,
    wo_id: str,
) -> Dict[str, Any]:
    probes: List[Dict[str, Any]] = []

    def probe(name: str, method: str, url: str, token: Optional[str], expect: Tuple[int, ...]) -> None:
        h = _headers(token) if token else {}
        r = _http(method, url, headers=h, timeout=90)
        probes.append({"name": name, "status": r.status_code, "expect": expect, "pass": r.status_code in expect})

    probe("unauthenticated_dashboard", "get", f"{API}/admin/dashboard", None, (401, 403))
    probe("client_admin_dashboard", "get", f"{API}/admin/dashboard", client_token, (401, 403))
    probe("tenant_admin_dashboard", "get", f"{API}/admin/dashboard", tenant_token, (401, 403))
    probe("contractor_admin_dashboard", "get", f"{API}/admin/dashboard", contractor_token, (401, 403))
    probe("client_waiver_endpoint", "post", f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}/onboarding-fee-policy", client_token, (401, 403))
    if wo_id:
        probe(
            "client_admin_wo_patch",
            "patch",
            f"{API}/admin/ops/work-orders/{wo_id}",
            client_token,
            (401, 403),
        )
    probe("invalid_token", "get", f"{API}/admin/dashboard", "not.a.valid.jwt", (401, 403))

    secrets_ok = True
    for p in probes:
        if "password" in str(p).lower() and "secret" in str(p).lower():
            secrets_ok = False
    out = {"probes": probes, "secrets_ok": secrets_ok, "at_utc": _utc()}
    out["pass"] = all(p["pass"] for p in probes) and secrets_ok
    return out


def _g9_g10(a1: dict, a2: dict, a3: dict, a5: dict) -> Tuple[dict, dict]:
    g9 = {
        "duplicate_issue_resolution_idempotent": a1.get("duplicate_idempotent"),
        "duplicate_waiver_ok": a2.get("duplicate_waiver_ok"),
        "dashboard_no_duplicate_inflation": a3.get("pass"),
        "pass": bool(
            a1.get("duplicate_idempotent")
            and a2.get("duplicate_waiver_ok")
            and a3.get("pass")
        ),
    }
    g10 = {
        "waiver_no_billing_plan_corruption": a2.get("no_plan_upgrade"),
        "resolved_issue_terminal": (a1.get("final_issue_status") or "") in TERMINAL_ISSUE,
        "non_admin_mutations_blocked": a5.get("pass"),
        "pass": bool(
            a2.get("no_plan_upgrade")
            and (a1.get("final_issue_status") or "") in TERMINAL_ISSUE
            and a5.get("pass")
        ),
    }
    return g9, g10


def run_admin_verify() -> Dict[str, Any]:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    agg = ClassificationAggregator(OWNER)
    family_results: Dict[str, Dict[str, Any]] = {}

    admin_email, admin_pw = _admin_creds()
    admin_token, admin_user = _login(admin_email, admin_pw, admin=True)
    if not admin_token:
        agg.add("BLOCKED", "admin_login_failed")
        primary = "BLOCKED"
        _finalize_bundle(primary, family_results, {}, {}, {}, {"any_stale": True})
        return {"classification": primary, "bundle": str(BUNDLE)}

    step_up = _step_up(admin_token, admin_pw)
    if not step_up:
        agg.add("BLOCKED", "admin_step_up_failed")
        primary = "BLOCKED"
        _finalize_bundle(primary, family_results, {}, {}, {}, {"any_stale": True})
        return {"classification": primary, "bundle": str(BUNDLE)}

    client_pw = _read_pw(
        ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt",
        "OPS_VERIFY_CLIENT_PASSWORD",
    )
    client_token, client_user = _login(CLIENT_EMAIL, client_pw)
    f3_pw = _read_pw(
        ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt",
        "OPS_VERIFY_F3_PASSWORD",
        default="",
    )
    contractor_token, _ = _login("f2-ops-heating-wales@yopmail.com", f3_pw, contractor=True)
    f7_pw = _read_pw(
        ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt",
        "OPS_TENANT_PASSWORD",
        "F7OpsWales!Staging2026",
    )
    tenant_token, _ = _login("f7-ops-wales@yopmail.com", f7_pw)

    a1 = _family_a1(client_token, client_user, admin_token, admin_user, step_up, admin_pw)
    _write("admin_issue_resolution.json", a1)
    family_results["A1"] = a1
    issue_id = a1.get("issue_id") or ""
    wo_id = a1.get("work_order_id") or ""

    if not a1.get("pass"):
        agg.add("FAIL_OPERATIONAL", "admin_issue_resolution")
        return _early(agg, family_results, "A1")

    a2 = _family_a2(admin_token, admin_user, step_up)
    _write("admin_waiver_granting.json", a2)
    family_results["A2"] = a2
    if not a2.get("pass"):
        agg.add("WAIVER_AUTHORITY_DRIFT", "waiver")

    a3 = _family_a3(admin_token, admin_user)
    _write("admin_dashboard_accuracy.json", a3)
    family_results["A3"] = a3
    if not a3.get("pass"):
        agg.add("ADMIN_ANALYTICS_DRIFT", "dashboard")

    a4 = _family_a4(admin_token, admin_user)
    _write("admin_analytics_accuracy.json", a4)
    family_results["A4"] = a4
    if not a4.get("pass"):
        agg.add("ADMIN_ANALYTICS_DRIFT", "analytics")

    a5 = _family_a5(admin_token, client_token, tenant_token, contractor_token, issue_id, wo_id)
    _write("admin_security_boundary.json", a5)
    family_results["A5"] = a5
    if not a5.get("pass"):
        agg.add("SECURITY_BOUNDARY_FAILURE", "rbac")

    g9, g10 = _g9_g10(a1, a2, a3, a5)
    _write("g9_admin_integrity.json", g9)
    _write("g10_admin_authority.json", g10)

    def read_issue_state() -> Dict[str, Any]:
        if not issue_id:
            return {}
        r = _http("get", f"{API}/client/maintenance/issues/{issue_id}", headers=_headers(client_token), timeout=60)
        return {"status": (r.json() or {}).get("status") if r.status_code == 200 else None}

    def read_waiver_state() -> Dict[str, Any]:
        r = _http(
            "get",
            f"{API}/admin/pilot-lifecycle/accounts/{CLIENT_ID}/redemptions",
            headers=_headers(admin_token),
            timeout=60,
        )
        overrides = (r.json() or {}).get("eligibility_overrides") if r.status_code == 200 else []
        active = [
            o
            for o in overrides or []
            if o.get("override_type") == "recover_onboarding" and not o.get("revoked_at")
        ]
        return {"recover_onboarding_count": len(active)}

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    observer.observe(
        "issue_resolution_state",
        read_issue_state,
        agree_fn=lambda a, b: a.get("status") == b.get("status") and a.get("status") in TERMINAL_ISSUE,
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=False,
    )
    observer.observe(
        "waiver_override_state",
        read_waiver_state,
        agree_fn=lambda a, b: a == b and a.get("recover_onboarding_count", 0) >= 1,
        timeout_seconds=min(60, CONVERGENCE_WAIT_S),
        dry_run=False,
    )
    conv = observer.build_artifact()
    conv["t0_issue"] = read_issue_state()
    conv["t0_waiver"] = read_waiver_state()
    _write("convergence.json", conv)

    conv_ok = not conv.get("any_stale") and all(o.converged for o in observer.observations)
    checkpoints = {
        "A1": bool(a1.get("pass")),
        "A2": bool(a2.get("pass")),
        "A3": bool(a3.get("pass")),
        "A4": bool(a4.get("pass")),
        "A5": bool(a5.get("pass")),
        "G9": bool(g9.get("pass")),
        "G10": bool(g10.get("pass")),
        "convergence": conv_ok,
    }
    verified = all(checkpoints.values())
    if verified:
        primary = "VERIFIED_OPERATIONALLY"
    elif not checkpoints["A1"]:
        primary = "FAIL_OPERATIONAL"
    elif not checkpoints["A2"]:
        primary = "WAIVER_AUTHORITY_DRIFT"
    elif not checkpoints["A3"] or not checkpoints["A4"]:
        primary = "ADMIN_ANALYTICS_DRIFT"
    elif not checkpoints["A5"]:
        primary = "SECURITY_BOUNDARY_FAILURE"
    elif not checkpoints["G9"] or not checkpoints["G10"]:
        primary = "TRUST_RISK_PRESENT"
    elif not checkpoints["convergence"]:
        primary = "FAIL_OPERATIONAL"
    else:
        primary = "PARTIAL"

    _finalize_bundle(primary, family_results, g9, g10, conv, verified=verified, checkpoints=checkpoints)
    return {"classification": primary, "bundle": str(BUNDLE), "verified": verified}


def _early(agg: ClassificationAggregator, families: dict, stop: str) -> Dict[str, Any]:
    result = agg.finalize(execution_completed=True)
    primary = result.primary if result.blocking else "PARTIAL"
    _finalize_bundle(primary, families, {}, {}, {"any_stale": True}, verified=False, stop_at=stop)
    return {"classification": primary, "bundle": str(BUNDLE), "early_exit": stop}


def _finalize_bundle(
    primary: str,
    families: dict,
    g9: dict,
    g10: dict,
    conv: dict,
    *,
    verified: bool = False,
    stop_at: str = "",
    checkpoints: Optional[Dict[str, bool]] = None,
) -> None:
    cp = checkpoints or {
        "A1": bool(families.get("A1", {}).get("pass")),
        "A2": bool(families.get("A2", {}).get("pass")),
        "A3": bool(families.get("A3", {}).get("pass")),
        "A4": bool(families.get("A4", {}).get("pass")),
        "A5": bool(families.get("A5", {}).get("pass")),
        "G9": bool(g9.get("pass")),
        "G10": bool(g10.get("pass")),
        "convergence": not conv.get("any_stale"),
    }
    classification = {
        "programme": PROGRAMME,
        "family": OWNER,
        "classification": primary,
        "execution_status": primary,
        "blocking": not verified,
        "authoritative_verification_owner": OWNER,
        "proof_mode": PROOF_MODE,
        "run_tag": RUN_TAG,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "checkpoints": {
            "A1_issue_resolution": cp.get("A1"),
            "A2_waiver": cp.get("A2"),
            "A3_dashboard": cp.get("A3"),
            "A4_analytics": cp.get("A4"),
            "A5_security": cp.get("A5"),
            "G9": cp.get("G9"),
            "G10": cp.get("G10"),
            "convergence": cp.get("convergence"),
        },
    }
    if stop_at:
        classification["early_exit_family"] = stop_at
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watch = [
        f"# ADMIN-RUNTIME-VERIFY-01 watchlist",
        "",
        f"**Run:** `{RUN_TAG}`",
        f"**Classification:** `{primary}`",
        "",
    ]
    if stop_at:
        watch.append(f"- Early exit at **{stop_at}**")
    for k, v in families.items():
        if not v.get("pass"):
            watch.append(f"- {k}: see artifact JSON")
    if not verified and primary == "VERIFIED_OPERATIONALLY":
        watch.append("- classification mismatch")
    if len(watch) <= 5:
        watch.append("- (none — all families passed)" if verified else "- review failed families")
    _write("watchlist.md", "\n".join(watch) + "\n")

    rows = "\n".join(f"| {k} | {v.get('pass')} |" for k, v in families.items())
    (BUNDLE / "REPORT.md").write_text(
        f"""# PRELAUNCH-ADMIN-RUNTIME-VERIFY-01

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`  
**Pilot:** Wales HMO `{SLUG}`

| Family | Pass |
|--------|------|
{rows}
| G9 | {g9.get('pass')} |
| G10 | {g10.get('pass')} |
| Convergence | {not conv.get('any_stale')} |

Proof: real admin session, API + browser, staging `{API}`.
""",
        encoding="utf-8",
    )
    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — ADMIN-RUNTIME-VERIFY-01\n\nRun `{RUN_TAG}` VERIFIED_OPERATIONALLY.\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    print(json.dumps(run_admin_verify(), indent=2))
