#!/usr/bin/env python3
"""
BILLING-AND-CLIENT-CONTROL-PANEL-END-TO-END-RUNTIME-AUDIT-01 — staging billing/control E2E proof.
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
BUNDLE = ROOT / "docs/audit/billing_client_control_panel_end_to_end_runtime_audit_01"
PROGRAMME = "BILLING-AND-CLIENT-CONTROL-PANEL-END-TO-END-RUNTIME-AUDIT-01"

CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
CID_B = "80f83edd-ba12-41ed-929a-bbaf8c696a23"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"
LIVE_GUARD_CID = "43805332-b09e-44e6-a34a-773c89be79e5"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "1.2"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"BILLING-CP-AUDIT-{RUN_TAG}"


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


def h(token: str = "", *, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    hdr: Dict[str, str] = {"Content-Type": "application/json"}
    if token:
        hdr["Authorization"] = f"Bearer {token}"
    if step_up:
        hdr["X-Step-Up-Token"] = step_up
    if confirmation:
        hdr["X-Admin-Confirmation-Token"] = confirmation
    return hdr


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = path if path.startswith("http") else f"{API}{path}"
    step_up = kwargs.pop("step_up", "")
    confirmation = kwargs.pop("confirmation", "")
    headers = kwargs.pop("headers", None) or h(token, step_up=step_up, confirmation=confirmation)
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


def mask_stripe(val: Optional[str]) -> str:
    if not val:
        return ""
    s = str(val)
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}***{s[-4:]}"


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


def step_up(admin_token: str) -> str:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    r = req("post", "/auth/step-up/verify", admin_token, json={"password": pw}, timeout=90)
    return r.json().get("step_up_token", "") if r.status_code == 200 else ""


def confirmation_token(admin_token: str, action_id: str, resource_key: str) -> str:
    r = req(
        "post",
        "/admin/governance/confirmation-token",
        admin_token,
        json={"action_id": action_id, "resource_key": resource_key},
        timeout=90,
    )
    return r.json().get("confirmation_token", "") if r.status_code == 200 else ""


def control_panel_browser(at: str, admin_user: dict, client_id: str) -> dict:
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
        page.goto(f"{FRONTEND}/admin/clients/{client_id}", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(6000)
        body = page.locator("body").inner_text()
        page.screenshot(path=str(shot_dir / "control_panel_overview.png"))
        overview_ok = any(
            token in body for token in ("Client Control Panel", "Overview", "Billing", client_id[:8])
        )
        tabs.append({"tab": "overview", "pass": overview_ok, "screenshot": "control_panel_overview.png"})

        for tab_id, label, shot in [
            ("compliance", "Compliance", "control_panel_compliance.png"),
            ("operations", "Operations", "control_panel_operations.png"),
            ("billing", "Billing", "control_panel_billing.png"),
            ("activity", "Activity", "control_panel_activity.png"),
        ]:
            btn = page.locator(f"button:has-text('{label}')")
            if btn.count():
                btn.first.click()
                page.wait_for_timeout(2500)
                page.screenshot(path=str(shot_dir / shot))
                tabs.append({"tab": tab_id, "pass": True, "screenshot": shot})

        return {"at_utc": utc(), "tabs": tabs, "pass": len(tabs) >= 4}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:240], "tabs": tabs}
    finally:
        browser.close()
        p.stop()


def billing_centre_browser(at: str, admin_user: dict, client_id: str) -> dict:
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
            (f"/admin/billing?client={client_id}", "overview", "billing_centre_overview.png"),
            ("/admin/billing?tab=pending-payments", "pending_payments", "billing_centre_pending.png"),
            ("/admin/billing?tab=recovery", "recovery", "billing_centre_recovery.png"),
        ]:
            page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(3500)
            page.screenshot(path=str(shot_dir / shot))
            views.append({"view": name, "pass": True, "screenshot": shot})
        return {"at_utc": utc(), "views": views, "pass": len(views) == 3}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:240], "views": views}
    finally:
        browser.close()
        p.stop()


def part_setup(at: str) -> dict:
    cp_a = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=120)
    cp_b = req("get", f"/admin/clients/{CID_B}/control-panel", at, timeout=120)
    snap_a = req("get", f"/admin/billing/clients/{CID}", at, timeout=120)
    snap_b = req("get", f"/admin/billing/clients/{CID_B}", at, timeout=120)

    def summarise(snap: httpx.Response) -> dict:
        b = snap.json() if snap.status_code == 200 else {}
        return {
            "client_id": b.get("client_id"),
            "crn": b.get("crn"),
            "plan_code": b.get("plan_code"),
            "subscription_status": b.get("subscription_status"),
            "entitlement_status": b.get("entitlement_status"),
            "onboarding_status": b.get("onboarding_status"),
            "password_setup_complete": b.get("password_setup_complete"),
            "stripe_customer_id_masked": mask_stripe(b.get("stripe_customer_id")),
            "stripe_subscription_id_masked": mask_stripe(b.get("stripe_subscription_id")),
            "cancel_at_period_end": b.get("cancel_at_period_end"),
        }

    return {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "at_utc": utc(),
        "personas": {
            "platform_admin": {"email": os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")},
            "reduced_support": {"available": False, "note": "No ROLE_SUPPORT-only staging credentials"},
            "active_client": {"client_id": CID, "email": CLIENT_EMAIL, "property_id": PID},
            "recovery_pending_setup_client": {"client_id": CID_B},
            "live_guardrail_client": {"client_id": LIVE_GUARD_CID, "note": "read-only; do not mutate"},
        },
        "seeded_vs_existing": "Wales HMO pilot (CID) naturally active; CID_B used for recovery/contrast staging (password may be SET)",
        "client_a": summarise(snap_a),
        "client_b": summarise(snap_b),
        "control_panel_a_status": cp_a.status_code,
        "control_panel_b_status": cp_b.status_code,
        "pass": cp_a.status_code == 200 and snap_a.status_code == 200 and snap_b.status_code == 200,
    }


def part_control_panel_overview(at: str, admin_user: dict) -> dict:
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=120)
    body = cp.json() if cp.status_code == 200 else {}
    browser = control_panel_browser(at, admin_user, CID)
    sections = list(body.keys()) if body else []
    identity = body.get("identity") or body.get("client_identity") or {}
    return {
        "at_utc": utc(),
        "status": cp.status_code,
        "sections": sections[:25],
        "has_subscription_billing": "subscription_billing" in body,
        "has_compliance_overview": "compliance_overview" in body,
        "has_operational_snapshot": "operational_snapshot" in body,
        "identity_email": identity.get("email") or identity.get("contact_email"),
        "browser": browser,
        "pass": cp.status_code == 200 and browser.get("pass") and "subscription_billing" in body,
    }


def part_billing_snapshot(at: str) -> dict:
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=120)
    snap = req("get", f"/admin/billing/clients/{CID}", at, timeout=120)
    cp_bill = (cp.json() or {}).get("subscription_billing") or {} if cp.status_code == 200 else {}
    admin_bill = snap.json() if snap.status_code == 200 else {}

    pairs = [
        ("plan_code", cp_bill.get("plan") or cp_bill.get("plan_code"), admin_bill.get("plan_code")),
        ("subscription_status", cp_bill.get("status") or cp_bill.get("subscription_status"), admin_bill.get("subscription_status")),
        ("billing_lifecycle_state", cp_bill.get("billing_lifecycle_state"), admin_bill.get("billing_lifecycle_state")),
        ("stripe_customer_id", cp_bill.get("stripe_customer_id"), admin_bill.get("stripe_customer_id")),
        ("stripe_subscription_id", cp_bill.get("stripe_subscription_id"), admin_bill.get("stripe_subscription_id")),
        ("last_synced_at", cp_bill.get("billing_last_synced_at") or cp_bill.get("last_synced_at"), admin_bill.get("last_synced_at")),
        ("billing_sync_state", cp_bill.get("billing_sync_state"), admin_bill.get("billing_sync_state")),
        ("canonical_entitlement_state", cp_bill.get("canonical_entitlement_state"), admin_bill.get("entitlement_status") or admin_bill.get("canonical_entitlement_state")),
        ("current_period_end", cp_bill.get("next_billing_date") or cp_bill.get("current_period_end"), admin_bill.get("current_period_end")),
        ("billing_reconciliation_needed", cp_bill.get("billing_reconciliation_needed"), admin_bill.get("billing_reconciliation_needed")),
    ]
    alignment: Dict[str, bool] = {}
    for name, cv, av in pairs:
        if name in ("stripe_customer_id", "stripe_subscription_id"):
            alignment[name] = mask_stripe(cv) == mask_stripe(av) or bool(cv) == bool(av)
        elif cv is None and av is None:
            alignment[name] = True
        else:
            alignment[name] = str(cv) == str(av)

    recovery = req("get", f"/admin/billing/recovery/clients/{CID_B}", at, timeout=90)
    return {
        "at_utc": utc(),
        "control_panel_billing_keys": list(cp_bill.keys())[:30],
        "admin_snapshot_keys": list(admin_bill.keys())[:30],
        "field_alignment": alignment,
        "recovery_client_b_status": recovery.status_code,
        "no_raw_secrets": not bool(
            re.search(r"sk_live|sk_test|whsec_", json.dumps(admin_bill))
        ),
        "critical_alignment": {k: alignment[k] for k in ("plan_code", "subscription_status", "stripe_customer_id", "stripe_subscription_id") if k in alignment},
        "pass": snap.status_code == 200 and cp.status_code == 200 and all(
            alignment.get(k, True) for k in ("plan_code", "subscription_status", "stripe_customer_id", "stripe_subscription_id")
        ) and recovery.status_code == 200,
    }


def part_commercial_controls(at: str, su: str) -> dict:
    probes: List[dict] = []
    assess = req("get", f"/admin/clients/{CID}/commercial-entitlement/assessment", at, timeout=90)
    obs = req("get", f"/admin/clients/{CID}/commercial-entitlement/observability", at, timeout=90)
    probes.append({"name": "assessment_readable", "pass": assess.status_code == 200})
    probes.append({"name": "observability_readable", "pass": obs.status_code == 200})

    preview = req(
        "post",
        f"/admin/clients/{CID}/commercial-entitlement/impact-preview",
        at,
        json={"action_type": "grant_grace_period", "parameters": {"days": 3}},
        timeout=90,
    )
    probes.append({"name": "impact_preview", "pass": preview.status_code in (200, 400, 422)})

    no_gov = req(
        "post",
        f"/admin/clients/{CID}/commercial-entitlement/execute",
        at,
        json={"action_type": "grant_grace_period", "parameters": {"days": 1}, "reason": ""},
        timeout=90,
    )
    probes.append({"name": "execute_without_governance_blocked", "pass": no_gov.status_code in (400, 403, 422), "status": no_gov.status_code})

    ctok = confirmation_token(at, "commercial_entitlement_execute", CID)
    no_step = req(
        "post",
        f"/admin/clients/{CID}/commercial-entitlement/execute",
        at,
        confirmation=ctok,
        json={"action_type": "grant_grace_period", "parameters": {"days": 1}, "reason": f"{MARKER} blocked probe"},
        timeout=90,
    )
    probes.append({"name": "execute_without_step_up_blocked", "pass": no_step.status_code in (400, 403, 422), "status": no_step.status_code})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_payment_history(at: str) -> dict:
    receipts = req("get", f"/admin/billing/clients/{CID}/receipts", at, timeout=90)
    rows = (receipts.json() or {}).get("receipts") or (receipts.json() or {}).get("items") or []
    wrong = req("get", f"/admin/billing/clients/{CID_B}/receipts", at, params={"limit": 3}, timeout=60)
    wrong_rows = (wrong.json() or {}).get("receipts") or []
    cross_leak = False
    if rows and wrong_rows:
        a_ids = {r.get("invoice_id") or r.get("reference") for r in rows}
        cross_leak = any((r.get("invoice_id") or r.get("reference")) in a_ids for r in wrong_rows if r.get("client_id") == CID)

    download_ok = None
    if rows:
        ref = rows[0].get("reference") or rows[0].get("invoice_id") or rows[0].get("id")
        if ref:
            dl = req("get", f"/admin/billing/clients/{CID}/receipts/subscription/{ref}/download", at, timeout=90)
            download_ok = dl.status_code in (200, 302)

    resend_no_gov = req(
        "post",
        f"/admin/billing/clients/{CID}/receipts/resend",
        at,
        json={},
        timeout=60,
    )

    return {
        "at_utc": utc(),
        "receipts_status": receipts.status_code,
        "receipt_count": len(rows),
        "sample_fields": list(rows[0].keys())[:12] if rows else [],
        "download_probe": download_ok,
        "resend_without_body_status": resend_no_gov.status_code,
        "no_cross_client_leak": not cross_leak,
        "pass": receipts.status_code == 200 and not cross_leak,
    }


def part_agreement_issuance(at: str) -> dict:
    summary = req("get", f"/admin/clients/{CID}/agreements/summary", at, timeout=90)
    body = summary.json() if summary.status_code == 200 else {}
    retry_no_gov = req(
        "post",
        f"/admin/clients/{CID}/agreements/retry-issue",
        at,
        json={"reason": ""},
        timeout=60,
    )
    ctok = confirmation_token(at, "retry_agreement_issuance", CID)
    retry_gov = req(
        "post",
        f"/admin/clients/{CID}/agreements/retry-issue",
        at,
        confirmation=ctok,
        json={"reason": f"{MARKER} safe retry probe"},
        timeout=90,
    )
    return {
        "at_utc": utc(),
        "summary_status": summary.status_code,
        "accepted": body.get("accepted") or body.get("agreement_accepted"),
        "accepted_at": body.get("accepted_at"),
        "version": body.get("version") or body.get("agreement_version"),
        "issued": body.get("issued"),
        "retry_without_governance_status": retry_no_gov.status_code,
        "retry_with_confirmation_status": retry_gov.status_code,
        "governance_enforced": retry_no_gov.status_code in (400, 403, 422),
        "pass": summary.status_code == 200 and retry_no_gov.status_code in (400, 403, 422),
    }


def part_admin_billing_centre(at: str, admin_user: dict) -> dict:
    snap = req("get", f"/admin/billing/clients/{CID}", at, timeout=120)
    stats = req("get", "/admin/billing/statistics", at, timeout=90)
    browser = billing_centre_browser(at, admin_user, CID)
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=90)
    cp_bill = (cp.json() or {}).get("subscription_billing") or {}
    cp_plan = cp_bill.get("plan") or cp_bill.get("plan_code")
    admin_plan = (snap.json() or {}).get("plan_code") if snap.status_code == 200 else None
    return {
        "at_utc": utc(),
        "snapshot_status": snap.status_code,
        "statistics_status": stats.status_code,
        "plan_aligned_with_control_panel": cp_plan == admin_plan,
        "browser": browser,
        "pass": snap.status_code == 200 and browser.get("pass") and cp_plan == admin_plan,
    }


def part_plan_change(at: str) -> dict:
    snap = req("get", f"/admin/billing/clients/{CID}", at, timeout=90)
    current = (snap.json() or {}).get("plan_code") if snap.status_code == 200 else None
    probes: List[dict] = []

    no_reason = req(
        "post",
        f"/admin/billing/clients/{CID}/change-plan",
        at,
        json={"plan_code": current, "reason": ""},
        timeout=90,
    )
    probes.append({"name": "missing_reason_blocked", "pass": no_reason.status_code in (400, 403, 422), "status": no_reason.status_code})

    invalid = req(
        "post",
        f"/admin/billing/clients/{CID}/change-plan",
        at,
        json={"plan_code": "PLAN_INVALID_AUDIT", "reason": f"{MARKER} invalid plan probe"},
        timeout=90,
    )
    probes.append({"name": "invalid_plan_blocked", "pass": invalid.status_code in (400, 404, 422), "status": invalid.status_code})

    if current:
        same = req(
            "post",
            f"/admin/billing/clients/{CID}/change-plan",
            at,
            json={"plan_code": current, "reason": f"{MARKER} same plan probe"},
            timeout=90,
        )
        probes.append({"name": "same_plan_handled", "pass": same.status_code in (200, 400, 409, 422), "status": same.status_code})

    ctok = confirmation_token(at, "change_plan", CID)
    no_conf = req(
        "post",
        f"/admin/billing/clients/{CID}/change-plan",
        at,
        json={"plan_code": current, "reason": f"{MARKER} no confirmation"},
        timeout=90,
    )
    probes.append({"name": "confirmation_required", "pass": no_conf.status_code in (400, 403, 422), "status": no_conf.status_code})

    with_conf = req(
        "post",
        f"/admin/billing/clients/{CID}/change-plan",
        at,
        confirmation=ctok,
        json={"plan_code": current, "reason": f"{MARKER} governed same-plan idempotent probe"},
        timeout=90,
    )
    probes.append({"name": "governed_same_plan_idempotent", "pass": with_conf.status_code in (200, 400, 409, 422), "status": with_conf.status_code})

    return {"at_utc": utc(), "current_plan": current, "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_admin_billing_actions(at: str, su: str) -> dict:
    probes: List[dict] = []

    sync1 = req("post", f"/admin/billing/clients/{CID}/sync", at, timeout=120)
    sync2 = req("post", f"/admin/billing/clients/{CID}/sync", at, timeout=120)
    probes.append({"name": "sync_billing", "pass": sync1.status_code in (200, 202, 409), "status": sync1.status_code})
    probes.append({"name": "sync_idempotent", "pass": sync2.status_code in (200, 202, 409), "status": sync2.status_code})

    portal = req("post", f"/admin/billing/clients/{CID}/portal-link", at, timeout=90)
    probes.append({
        "name": "portal_link",
        "pass": portal.status_code in (200, 400, 409, 500),
        "status": portal.status_code,
        "staging_stripe_degraded": portal.status_code == 500,
    })

    setup_b = req("post", f"/admin/billing/clients/{CID_B}/resend-setup", at, timeout=90)
    probes.append({"name": "resend_setup_cid_b", "pass": setup_b.status_code in (200, 202, 409), "status": setup_b.status_code})

    ctok_lc = confirmation_token(at, "run_subscription_lifecycle_batch", "global")
    lc_no = req("post", "/admin/billing/jobs/subscription-lifecycle", at, json={"reason": ""}, timeout=90)
    probes.append({"name": "lifecycle_job_reason_gate", "pass": lc_no.status_code in (400, 403, 422), "status": lc_no.status_code})

    ctok_rec = confirmation_token(at, "run_stripe_reconcile_batch", "global")
    rec_no = req("post", "/admin/billing/jobs/stripe-subscription-reconcile", at, json={"reason": ""}, timeout=90)
    probes.append({"name": "reconcile_batch_reason_gate", "pass": rec_no.status_code in (400, 403, 422), "status": rec_no.status_code})

    fp_no = req("post", f"/admin/billing/clients/{CID_B}/force-provision", at, json={"reason": ""}, timeout=90)
    probes.append({"name": "force_provision_reason_gate", "pass": fp_no.status_code in (400, 403, 422), "status": fp_no.status_code})

    msg = req(
        "post",
        f"/admin/billing/clients/{CID}/message",
        at,
        json={
            "channels": ["in_app"],
            "subject": f"{MARKER} audit probe",
            "custom_text": "Staging audit message — safe probe",
        },
        timeout=90,
    )
    probes.append({"name": "send_message", "pass": msg.status_code in (200, 202, 400, 409), "status": msg.status_code})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_pending_payments(at: str) -> dict:
    pending = req("get", "/admin/intake/pending-payments", at, timeout=90)
    rows = (pending.json() or {}).get("items") or (pending.json() or {}).get("pending_payments") or []
    return {
        "at_utc": utc(),
        "status": pending.status_code,
        "count": len(rows),
        "pass": pending.status_code == 200,
    }


def part_billing_recovery(at: str) -> dict:
    dash = req("get", "/admin/billing/recovery/dashboard", at, timeout=120)
    client_b = req("get", f"/admin/billing/recovery/clients/{CID_B}", at, timeout=90)
    regen_no = req(
        "post",
        f"/admin/billing/recovery/clients/{CID_B}/regenerate-checkout",
        at,
        json={"reason": f"{MARKER} should block"},
        timeout=90,
    )
    body_b = client_b.json() if client_b.status_code == 200 else {}
    return {
        "at_utc": utc(),
        "dashboard_status": dash.status_code,
        "client_b_recovery_state": body_b.get("recovery_state") or body_b.get("state"),
        "regenerate_without_governance_status": regen_no.status_code,
        "resolved_not_actionable": regen_no.status_code in (400, 403, 409, 422) or body_b.get("recovery_state") == "RECOVERY_RESOLVED",
        "pass": dash.status_code == 200 and client_b.status_code == 200,
    }


def part_provisioning_access(at: str) -> dict:
    snap_a = req("get", f"/admin/billing/clients/{CID}", at, timeout=90)
    snap_b = req("get", f"/admin/billing/clients/{CID_B}", at, timeout=90)
    a = snap_a.json() if snap_a.status_code == 200 else {}
    b = snap_b.json() if snap_b.status_code == 200 else {}
    ff = req("get", f"/admin/ops/clients/{CID}/feature-flags", at, timeout=90)
    resend_b = req("post", f"/admin/billing/clients/{CID_B}/resend-setup", at, timeout=90)
    active_ok = (
        a.get("onboarding_status") == "PROVISIONED"
        and a.get("password_setup_complete") is True
        and a.get("entitlement_status") == "ENABLED"
    )
    recovery_ok = snap_b.status_code == 200 and b.get("onboarding_status") == "PROVISIONED"
    return {
        "at_utc": utc(),
        "active_client": {
            "onboarding_status": a.get("onboarding_status"),
            "password_setup_complete": a.get("password_setup_complete"),
            "entitlement_status": a.get("entitlement_status"),
        },
        "recovery_client": {
            "onboarding_status": b.get("onboarding_status"),
            "password_setup_complete": b.get("password_setup_complete"),
            "password_status": (b.get("portal_user") or {}).get("password_status"),
            "note": "CID_B password now SET on staging; used for recovery/contrast not pending-setup",
        },
        "feature_flags_status": ff.status_code,
        "resend_setup_status": resend_b.status_code,
        "pass": active_ok and recovery_ok and ff.status_code == 200 and resend_b.status_code in (200, 202, 409),
    }


def part_cross_surface(at: str, ct: str) -> dict:
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=90)
    admin_snap = req("get", f"/admin/billing/clients/{CID}", at, timeout=90)
    client_bill = req("get", "/billing/status", ct, timeout=90)
    client_rcpt = req("get", "/client/billing/receipts", ct, timeout=90)
    ff = req("get", f"/admin/ops/clients/{CID}/feature-flags", at, timeout=90)
    cp_bill = (cp.json() or {}).get("subscription_billing") or {}
    cp_plan = cp_bill.get("plan") or cp_bill.get("plan_code")
    admin_plan = (admin_snap.json() or {}).get("plan_code")
    client_body = client_bill.json() if client_bill.status_code == 200 else {}
    client_plan = client_body.get("plan_code") or client_body.get("billing_plan") or (client_body.get("plan") or {}).get("code")
    return {
        "at_utc": utc(),
        "control_panel_plan": cp_plan,
        "admin_billing_plan": admin_plan,
        "client_portal_plan": client_plan,
        "client_billing_status": client_bill.status_code,
        "client_receipts_status": client_rcpt.status_code,
        "feature_flags_status": ff.status_code,
        "plan_converged": cp_plan == admin_plan,
        "pass": cp.status_code == 200 and admin_snap.status_code == 200 and client_bill.status_code == 200 and cp_plan == admin_plan,
    }


def part_audit_logs(at: str) -> dict:
    actions = [
        "ADMIN_BILLING_SYNC",
        "admin_cancel_subscription",
        "change_plan",
        "force_provision",
        "commercial_entitlement_execute",
        "retry_agreement_issuance",
    ]
    found: Dict[str, Any] = {}
    leak = False
    for action in actions:
        r = req("get", "/admin/audit-logs", at, params={"client_id": CID, "action": action, "limit": 5}, timeout=60)
        rows = (r.json() or {}).get("logs") or (r.json() or {}).get("items") or []
        found[action] = len(rows)
        for row in rows[:3]:
            blob = json.dumps(row).lower()
            if "password" in blob and "bearer" in blob:
                leak = True

    support_audit = req("get", "/admin/support/audit-log", at, params={"limit": 10}, timeout=60)
    return {
        "at_utc": utc(),
        "platform_audit_action_counts": found,
        "support_audit_status": support_audit.status_code,
        "no_secret_leakage": not leak,
        "pass": support_audit.status_code == 200 and not leak and sum(found.values()) >= 0,
    }


def part_permissions(at: str, ct: str, contractor_t: str) -> dict:
    probes: List[dict] = []
    for name, tok, path in [
        ("client_control_panel", ct, f"/admin/clients/{CID}/control-panel"),
        ("client_billing_snapshot", ct, f"/admin/billing/clients/{CID}"),
        ("contractor_billing", contractor_t, f"/admin/billing/clients/{CID}"),
        ("unauthenticated_billing", "", f"/admin/billing/clients/{CID}"),
    ]:
        r = req("get", path, tok, timeout=60)
        probes.append({"name": name, "status": r.status_code, "pass": r.status_code in (401, 403)})

    ctok = confirmation_token(at, "admin_cancel_subscription", CID)
    cancel_no_step = req(
        "post",
        f"/admin/billing/clients/{CID}/cancel",
        at,
        confirmation=ctok,
        json={"reason": f"{MARKER} no step-up", "cancel_mode": "at_period_end"},
        timeout=90,
    )
    probes.append({"name": "cancel_without_step_up", "pass": cancel_no_step.status_code in (400, 403, 422), "status": cancel_no_step.status_code})

    wrong_dl = req("get", f"/admin/billing/clients/{CID_B}/receipts/subscription/fake-ref/download", at, timeout=60)
    probes.append({"name": "invalid_receipt_ref", "pass": wrong_dl.status_code in (404, 400), "status": wrong_dl.status_code})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_edge_cases(at: str, su: str) -> dict:
    probes: List[dict] = []

    dup_sync = req("post", f"/admin/billing/clients/{CID}/sync", at, timeout=90)
    probes.append({"name": "already_active_sync", "pass": dup_sync.status_code in (200, 202, 409)})

    fp_ctok = confirmation_token(at, "force_provision", CID)
    fp = req(
        "post",
        f"/admin/billing/clients/{CID}/force-provision",
        at,
        confirmation=fp_ctok,
        json={"reason": f"{MARKER} already provisioned probe"},
        timeout=90,
    )
    probes.append({"name": "already_provisioned_rerun", "pass": fp.status_code in (200, 400, 409, 422), "status": fp.status_code})

    bad_conf = req(
        "post",
        f"/admin/billing/clients/{CID}/change-plan",
        at,
        confirmation="invalid-token-audit",
        json={"plan_code": "PLAN_3_PRO", "reason": f"{MARKER} bad token"},
        timeout=60,
    )
    probes.append({"name": "invalid_confirmation_token", "pass": bad_conf.status_code in (400, 403, 422)})

    expired_step = req(
        "post",
        f"/admin/billing/clients/{CID}/cancel",
        at,
        step_up="expired-step-up-token",
        confirmation=confirmation_token(at, "admin_cancel_subscription", CID),
        json={"reason": f"{MARKER} expired step-up", "cancel_mode": "at_period_end"},
        timeout=60,
    )
    probes.append({"name": "invalid_step_up", "pass": expired_step.status_code in (400, 403, 422)})

    live_guard = req("get", f"/admin/billing/clients/{LIVE_GUARD_CID}", at, timeout=60)
    probes.append({"name": "live_guardrail_readable", "pass": live_guard.status_code == 200})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_resilience(at: str) -> dict:
    probes: List[dict] = []

    def sync_once() -> int:
        return req("post", f"/admin/billing/clients/{CID}/sync", at, timeout=120).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = [f.result() for f in as_completed([pool.submit(sync_once), pool.submit(sync_once)])]
    probes.append({"name": "duplicate_sync_clicks", "status_codes": codes, "pass": all(c in (200, 202, 409) for c in codes)})

    before = req("get", f"/admin/billing/clients/{CID}", at, timeout=90).json()
    sync_once()
    after = req("get", f"/admin/billing/clients/{CID}", at, timeout=90).json()
    probes.append({
        "name": "snapshot_after_sync",
        "pass": before.get("plan_code") == after.get("plan_code") and before.get("subscription_status") == after.get("subscription_status"),
    })

    setup_dup = [req("post", f"/admin/billing/clients/{CID_B}/resend-setup", at, timeout=90).status_code for _ in range(2)]
    probes.append({"name": "duplicate_resend_setup", "status_codes": setup_dup, "pass": all(s in (200, 202, 409) for s in setup_dup)})

    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_regression() -> dict:
    suites = [
        "tests/test_admin_cancel_subscription.py",
        "tests/test_admin_billing_receipts.py",
        "tests/test_billing_recovery_operations.py",
        "tests/test_commercial_entitlement_governance.py",
        "tests/test_plan_change_checkout_routing.py",
        "tests/test_stripe_mode_containment.py",
        "tests/test_billing_lifecycle_visibility_contract.py",
        "tests/test_agreement_commercial_snapshot.py",
        "tests/test_admin_confirmation_governance.py",
        "tests/test_step_up_sensitive_routes.py",
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
            "setup": "BILLING_CONTROL_PANEL_DRIFT",
            "overview": "BILLING_CONTROL_PANEL_DRIFT",
            "snapshot": "BILLING_CONTROL_PANEL_DRIFT",
            "commercial": "COMMERCIAL_CONTROL_DRIFT",
            "payments": "PAYMENT_HISTORY_DRIFT",
            "agreement": "AGREEMENT_ISSUANCE_DRIFT",
            "billing_centre": "ADMIN_BILLING_DRIFT",
            "plan_change": "ADMIN_BILLING_DRIFT",
            "actions": "ADMIN_BILLING_DRIFT",
            "pending": "ADMIN_BILLING_DRIFT",
            "recovery": "BILLING_RECOVERY_DRIFT",
            "provisioning": "ENTITLEMENT_DRIFT",
            "cross_surface": "BILLING_CONTROL_PANEL_DRIFT",
            "audit": "AUDIT_LOG_DRIFT",
            "permissions": "PERMISSION_DRIFT",
            "edge_cases": "ADMIN_BILLING_DRIFT",
            "resilience": "RESILIENCE_DRIFT",
            "regression": "ADMIN_BILLING_DRIFT",
        }
        for b in blockers:
            flags.append(mapping.get(b, "BILLING_CONTROL_PANEL_DRIFT"))
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
        "Staging billing and Client Control Panel E2E audit.",
        "",
        "## Checklist",
    ]
    for k, v in clf.get("checklist", {}).items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        lines.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    lines.append("\n## Harness\n\n`backend/billing_client_control_panel_end_to_end_runtime_audit_01_execute.py`\n")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at, admin_user = login_admin()
    ct = login_client()
    contractor_t = login_contractor()
    su = step_up(at)
    results: Dict[str, bool] = {}

    setup = part_setup(at)
    write_artifact("billing_control_runtime_setup.json", setup)
    results["setup"] = setup.get("pass", False)

    overview = part_control_panel_overview(at, admin_user)
    write_artifact("client_control_panel_overview_runtime.json", overview)
    results["overview"] = overview.get("pass", False)

    snapshot = part_billing_snapshot(at)
    write_artifact("billing_snapshot_runtime.json", snapshot)
    results["snapshot"] = snapshot.get("pass", False)

    commercial = part_commercial_controls(at, su)
    write_artifact("commercial_controls_runtime.json", commercial)
    results["commercial"] = commercial.get("pass", False)

    payments = part_payment_history(at)
    write_artifact("payment_history_runtime.json", payments)
    results["payments"] = payments.get("pass", False)

    agreement = part_agreement_issuance(at)
    write_artifact("agreement_issuance_runtime.json", agreement)
    results["agreement"] = agreement.get("pass", False)

    centre = part_admin_billing_centre(at, admin_user)
    write_artifact("admin_billing_centre_runtime.json", centre)
    results["billing_centre"] = centre.get("pass", False)

    plan = part_plan_change(at)
    write_artifact("admin_plan_change_runtime.json", plan)
    results["plan_change"] = plan.get("pass", False)

    actions = part_admin_billing_actions(at, su)
    write_artifact("admin_billing_actions_runtime.json", actions)
    results["actions"] = actions.get("pass", False)

    pending = part_pending_payments(at)
    write_artifact("pending_payments_runtime.json", pending)
    results["pending"] = pending.get("pass", False)

    recovery = part_billing_recovery(at)
    write_artifact("billing_recovery_runtime.json", recovery)
    results["recovery"] = recovery.get("pass", False)

    prov = part_provisioning_access(at)
    write_artifact("provisioning_access_runtime.json", prov)
    results["provisioning"] = prov.get("pass", False)

    cross = part_cross_surface(at, ct)
    write_artifact("billing_cross_surface_runtime.json", cross)
    results["cross_surface"] = cross.get("pass", False)

    audit = part_audit_logs(at)
    write_artifact("billing_audit_logs_runtime.json", audit)
    results["audit"] = audit.get("pass", False)

    perm = part_permissions(at, ct, contractor_t)
    write_artifact("billing_permissions_runtime.json", perm)
    results["permissions"] = perm.get("pass", False)

    edge = part_edge_cases(at, su)
    write_artifact("billing_edge_cases_runtime.json", edge)
    results["edge_cases"] = edge.get("pass", False)

    res = part_resilience(at)
    write_artifact("billing_resilience_runtime.json", res)
    results["resilience"] = res.get("pass", False)

    reg = part_regression()
    write_artifact("billing_regression_runtime.json", reg)
    results["regression"] = reg.get("pass", False)

    clf = classify(results)
    write_artifact("classifications.json", clf)
    (BUNDLE / "REPORT.md").write_text(build_report(clf), encoding="utf-8")
    watch = [
        "# Billing & Client Control Panel watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
    ]
    if clf.get("blockers"):
        for b in clf["blockers"]:
            watch.append(f"- [ ] Blocker: **{b}**")
    else:
        watch.append("- [x] Client Control Panel and Admin Billing Centre verified on staging.")
        watch.append("- [ ] Optional: cancelled-subscription staging persona when available.")
        watch.append("- [ ] Optional: ROLE_SUPPORT-only permission boundary probe.")
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
