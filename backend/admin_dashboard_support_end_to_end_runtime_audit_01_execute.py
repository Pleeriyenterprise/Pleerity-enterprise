#!/usr/bin/env python3
"""
ADMIN-DASHBOARD-SUPPORT-END-TO-END-RUNTIME-AUDIT-01 — staging admin support E2E proof.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/admin_dashboard_support_end_to_end_runtime_audit_01"
PROGRAMME = "ADMIN-DASHBOARD-SUPPORT-END-TO-END-RUNTIME-AUDIT-01"

CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "1.5"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"ADMIN-SUPPORT-AUDIT-{RUN_TAG}"


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
    headers = kwargs.pop("headers", None)
    if token and headers is None:
        headers = h(token, step_up=kwargs.pop("step_up", ""), confirmation=kwargs.pop("confirmation", ""))
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


def admin_browser(admin_token: str, admin_user: dict, path: str, screenshot: str, *, expect_text: str = "") -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed"}
    shot_dir = BUNDLE / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [admin_token, admin_user],
        )
        page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(5000)
        body = page.locator("body").inner_text()
        errs = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.screenshot(path=str(shot_dir / screenshot))
        ok = True
        if expect_text:
            ok = expect_text.lower() in body.lower()
        return {"path": path, "screenshot": screenshot, "expect_text_found": ok, "pass": ok and "error" not in body.lower()[:200]}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:240]}
    finally:
        browser.close()
        p.stop()


def part_setup(at: str) -> dict:
    ff = req("get", f"/admin/ops/clients/{CID}/feature-flags", at, timeout=90)
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=90)
    billing = req("get", f"/admin/billing/clients/{CID}", at, timeout=90)
    return {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "at_utc": utc(),
        "staging_api": API,
        "staging_frontend": FRONTEND,
        "personas": {
            "platform_admin": {"email": os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com"), "role": "ROLE_ADMIN"},
            "test_landlord": {"client_id": CID, "email": CLIENT_EMAIL, "property_id": PID},
            "test_contractor": {"email": CONTRACTOR_EMAIL},
            "test_tenant": {"email": TENANT_EMAIL},
        },
        "seeded_vs_existing": "Wales HMO pilot naturally existing; no new customers created",
        "feature_flags_before": ff.json() if ff.status_code == 200 else {"status": ff.status_code},
        "control_panel_reachable": cp.status_code == 200,
        "billing_snapshot_reachable": billing.status_code == 200,
        "pass": cp.status_code == 200 and billing.status_code == 200,
    }


def part_dashboard(at: str, admin_user: dict) -> dict:
    dash = req("get", "/admin/dashboard", at, timeout=120)
    stats = (dash.json() or {}).get("stats") or {} if dash.status_code == 200 else {}
    browser = admin_browser(at, admin_user, "/admin/dashboard", "dashboard_overview.png", expect_text="client")
    return {
        "at_utc": utc(),
        "api_status": dash.status_code,
        "stats_keys": list(stats.keys()) if stats else [],
        "stats_sample": {k: stats.get(k) for k in ("total_clients", "active_clients", "total_properties", "unverified_documents_count") if k in stats},
        "compliance_overview": (dash.json() or {}).get("compliance_overview") if dash.status_code == 200 else None,
        "browser": browser,
        "pass": dash.status_code == 200 and browser.get("pass"),
    }


def part_search(at: str, admin_user: dict) -> dict:
    probes: List[dict] = []
    for label, q, archived in [
        ("email", CLIENT_EMAIL.split("@")[0], False),
        ("client_id_prefix", CID[:8], False),
        ("name_fragment", "nancy", False),
        ("archived_toggle", CLIENT_EMAIL.split("@")[0], True),
    ]:
        r = req("get", "/admin/search", at, params={"q": q, "limit": 10, "include_archived": str(archived).lower()}, timeout=90)
        items = (r.json() or {}).get("items") or (r.json() or {}).get("results") or []
        found = any((it.get("client_id") == CID or it.get("id") == CID) for it in items)
        probes.append({"name": label, "status": r.status_code, "found_pilot": found, "count": len(items)})
    bill = req("get", "/admin/billing/clients/search", at, params={"q": CLIENT_EMAIL, "limit": 5}, timeout=90)
    probes.append({"name": "billing_search", "status": bill.status_code, "pass": bill.status_code == 200})
    browser = admin_browser(at, admin_user, "/admin/support", "client_search_support.png")
    return {
        "at_utc": utc(),
        "probes": probes,
        "browser": browser,
        "pass": all(p.get("status") == 200 for p in probes if "status" in p) and any(p.get("found_pilot") for p in probes[:3]),
    }


def part_support(at: str, su: str, admin_user: dict) -> dict:
    cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=120)
    timeline = req("get", f"/admin/clients/{CID}/audit-timeline", at, params={"limit": 15}, timeout=90)
    activity = req("get", f"/admin/clients/{CID}/compliance-activity", at, timeout=90)
    recalc = req("post", f"/admin/clients/{CID}/actions/recalculate-compliance", at, step_up=su, json={"reason": f"{MARKER} safe recalc probe"}, timeout=120)
    browser = admin_browser(at, admin_user, f"/admin/clients/{CID}", "client_control_panel.png", expect_text="billing")
    sections = list((cp.json() or {}).keys())[:20] if cp.status_code == 200 else []
    return {
        "at_utc": utc(),
        "control_panel_status": cp.status_code,
        "sections_present": sections,
        "audit_timeline_status": timeline.status_code,
        "compliance_activity_status": activity.status_code,
        "recalculate_status": recalc.status_code,
        "recalculate_governed": recalc.status_code in (200, 202, 409),
        "browser": browser,
        "pass": cp.status_code == 200 and timeline.status_code == 200 and browser.get("pass"),
    }


def part_billing(at: str, su: str, admin_user: dict) -> dict:
    snap = req("get", f"/admin/billing/clients/{CID}", at, timeout=120)
    recovery = req("get", "/admin/billing/recovery/dashboard", at, timeout=120)
    sync = req("post", f"/admin/billing/clients/{CID}/sync", at, step_up=su, json={"reason": f"{MARKER} billing sync probe"}, timeout=120)
    cancel_no_gov = req(
        "post",
        f"/admin/billing/clients/{CID}/cancel",
        at,
        json={"reason": "probe", "cancel_mode": "at_period_end"},
        timeout=90,
    )
    ctok = confirmation_token(at, "admin.billing.cancel_subscription", CID)
    cancel_no_step = req(
        "post",
        f"/admin/billing/clients/{CID}/cancel",
        at,
        confirmation=ctok,
        json={"reason": f"{MARKER} should block without step-up", "cancel_mode": "at_period_end"},
        timeout=90,
    )
    browser = admin_browser(at, admin_user, "/admin/billing", "billing_admin.png", expect_text="billing")
    return {
        "at_utc": utc(),
        "snapshot_status": snap.status_code,
        "recovery_dashboard_status": recovery.status_code,
        "sync_status": sync.status_code,
        "cancel_without_governance_status": cancel_no_gov.status_code,
        "cancel_without_step_up_status": cancel_no_step.status_code,
        "governance_blocked_cancel": cancel_no_gov.status_code in (400, 403, 422),
        "browser": browser,
        "pass": snap.status_code == 200 and cancel_no_gov.status_code in (400, 403, 422) and browser.get("pass"),
    }


def part_entitlements(at: str, su: str) -> dict:
    before = req("get", f"/admin/ops/clients/{CID}/feature-flags", at, timeout=90)
    flags_before = before.json().get("flags") if before.status_code == 200 else []
    inv = next((f for f in (flags_before or []) if f.get("flag_key") == "INVOICING"), {})
    target_enabled = bool(inv.get("enabled", True))
    patch = req(
        "patch",
        f"/admin/ops/clients/{CID}/feature-flags",
        at,
        step_up=su,
        json={"updates": [{"flag_key": "INVOICING", "enabled": target_enabled}], "reason": f"{MARKER} idempotent toggle"},
        timeout=90,
    )
    after = req("get", f"/admin/ops/clients/{CID}/feature-flags", at, timeout=90)
    inv_after = next((f for f in (after.json().get("flags") or []) if f.get("flag_key") == "INVOICING"), {})
    return {
        "at_utc": utc(),
        "before_status": before.status_code,
        "patch_status": patch.status_code,
        "invoicing_source": inv_after.get("source"),
        "manual_override_visible": inv_after.get("source") in ("manual_override", "admin_override", "MANUAL"),
        "idempotent_retoggle": patch.status_code in (200, 409),
        "pass": before.status_code == 200 and patch.status_code in (200, 409) and bool(inv_after.get("enabled")) == target_enabled,
    }


def part_compliance(at: str, su: str, admin_user: dict) -> dict:
    pending = req("get", "/admin/documents/pending-verification", at, params={"limit": 10}, timeout=120)
    unresolved = req("get", "/admin/documents/unresolved-queue", at, params={"limit": 10}, timeout=120)
    escalation = req("get", "/admin/compliance-evidence/escalation-queue", at, params={"limit": 10}, timeout=120)
    browser = admin_browser(at, admin_user, "/admin/extraction-queue", "extraction_queue.png")
    items = (pending.json() or {}).get("documents") or (pending.json() or {}).get("items") or []
    return {
        "at_utc": utc(),
        "pending_status": pending.status_code,
        "pending_count": len(items),
        "unresolved_status": unresolved.status_code,
        "escalation_status": escalation.status_code,
        "browser": browser,
        "pass": pending.status_code == 200 and unresolved.status_code in (200, 404) and browser.get("pass"),
    }


def part_operations(at: str) -> dict:
    probes = []
    for name, path in [
        ("ops_risk_queue", "/admin/ops/risk-signal-regen-queue-summary"),
        ("pilot_ops", f"/admin/clients/{CID}/control-panel"),
    ]:
        r = req("get", path, at, params={"sample_limit": 10} if "queue" in path else None, timeout=90)
        probes.append({"name": name, "status": r.status_code, "ok": r.status_code == 200})
    wrong = req("get", f"/admin/clients/00000000-0000-0000-0000-000000009999/control-panel", at, timeout=60)
    probes.append({"name": "wrong_client_blocked", "status": wrong.status_code, "ok": wrong.status_code in (404, 403)})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["ok"] for p in probes if p["name"] != "wrong_client_blocked") and wrong.status_code in (404, 403)}


def part_communications(at: str, su: str) -> dict:
    delivery = req("get", "/admin/email-delivery", at, params={"limit": 10, "client_id": CID}, timeout=120)
    resend = req("post", f"/admin/clients/{CID}/actions/resend-activation-email", at, step_up=su, timeout=120)
    items = (delivery.json() or {}).get("items") or (delivery.json() or {}).get("messages") or []
    return {
        "at_utc": utc(),
        "email_delivery_status": delivery.status_code,
        "sample_count": len(items),
        "resend_activation_status": resend.status_code,
        "resend_governed": resend.status_code in (200, 202, 409),
        "pass": delivery.status_code == 200 and resend.status_code in (200, 202, 400, 409),
    }


def part_audit_logs(at: str) -> dict:
    logs = req("get", "/admin/audit-logs", at, params={"client_id": CID, "limit": 25}, timeout=120)
    rows = (logs.json() or {}).get("items") or (logs.json() or {}).get("logs") or []
    leak = any("password" in json.dumps(row).lower() and "token" in json.dumps(row).lower() for row in rows[:10])
    has_actor = any(row.get("actor_id") or row.get("actor_email") for row in rows[:5]) if rows else True
    return {
        "at_utc": utc(),
        "status": logs.status_code,
        "row_count": len(rows),
        "sample_actions": [r.get("action") for r in rows[:8]],
        "has_actor_fields": has_actor,
        "no_secret_leakage": not leak,
        "pass": logs.status_code == 200 and not leak,
    }


def part_permissions(at: str, ct: str, contractor_t: str) -> dict:
    probes = []
    for name, tok, path, expect in [
        ("client_admin_dashboard", ct, "/admin/dashboard", (401, 403)),
        ("contractor_admin_dashboard", contractor_t, "/admin/dashboard", (401, 403)),
        ("unauthenticated_audit", "", "/admin/audit-logs", (401, 403)),
        ("client_billing_admin", ct, f"/admin/billing/clients/{CID}", (401, 403)),
    ]:
        r = req("get", path, tok, timeout=60)
        probes.append({"name": name, "status": r.status_code, "pass": r.status_code in expect})
    cross = req("get", f"/admin/clients/00000000-0000-0000-0000-000000009999", at, timeout=60)
    probes.append({"name": "cross_client_detail", "status": cross.status_code, "pass": cross.status_code in (404, 403)})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_edge_cases(at: str, su: str) -> dict:
    probes = []
    r1 = req("get", "/admin/search", at, params={"q": "zzz-nonexistent-client-xyz", "limit": 5}, timeout=60)
    probes.append({"name": "nonexistent_search", "pass": r1.status_code == 200 and len((r1.json() or {}).get("items") or []) == 0})
    dup_ff = req(
        "patch",
        f"/admin/ops/clients/{CID}/feature-flags",
        at,
        step_up=su,
        json={"updates": [{"flag_key": "INVOICING", "enabled": True}], "reason": f"{MARKER} duplicate toggle"},
        timeout=90,
    )
    probes.append({"name": "duplicate_feature_toggle", "pass": dup_ff.status_code in (200, 409)})
    bad_conf = req(
        "post",
        f"/admin/billing/clients/{CID}/cancel",
        at,
        step_up=su,
        confirmation="invalid-token",
        json={"reason": "bad token probe", "cancel_mode": "at_period_end"},
        timeout=90,
    )
    probes.append({"name": "invalid_confirmation_token", "pass": bad_conf.status_code in (400, 403, 422)})
    return {"at_utc": utc(), "probes": probes, "pass": all(p["pass"] for p in probes)}


def part_cross_surface(at: str, ct: str, admin_user: dict) -> dict:
    admin_cp = req("get", f"/admin/clients/{CID}/control-panel", at, timeout=90)
    client_snap = req("get", "/client/protection-snapshot", ct, params={"property_id": PID}, timeout=90)
    landlord = admin_browser(at, admin_user, f"/admin/clients/{CID}", "cross_surface_control_panel.png")
    return {
        "at_utc": utc(),
        "admin_control_panel_ok": admin_cp.status_code == 200,
        "landlord_snapshot_ok": client_snap.status_code == 200,
        "browser": landlord,
        "pass": admin_cp.status_code == 200 and client_snap.status_code == 200 and landlord.get("pass"),
    }


def part_regression() -> dict:
    suites = [
        "tests/test_admin_client_support_search.py",
        "tests/test_admin_cancel_subscription.py",
        "tests/test_admin_confirmation_governance.py",
        "tests/test_admin_action_governance_policy.py",
        "tests/test_admin_pending_verification.py",
        "tests/test_admin_email_delivery.py",
        "tests/test_admin_billing_receipts.py",
        "tests/test_admin_ops_work_order_controls.py",
        "tests/test_billing_recovery_operations.py",
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
            "dashboard": "ADMIN_SUPPORT_DRIFT",
            "search": "ADMIN_SUPPORT_DRIFT",
            "support": "ADMIN_SUPPORT_DRIFT",
            "billing": "BILLING_ADMIN_DRIFT",
            "entitlements": "ENTITLEMENT_DRIFT",
            "compliance": "DOCUMENT_VERIFICATION_DRIFT",
            "communications": "COMMUNICATIONS_DRIFT",
            "audit_logs": "AUDIT_LOG_DRIFT",
            "permissions": "PERMISSION_DRIFT",
            "operations": "ADMIN_SUPPORT_DRIFT",
        }
        for b in blockers:
            flags.append(mapping.get(b, "ADMIN_SUPPORT_DRIFT"))
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
        f"**Staging:** `{API}` / `{FRONTEND}`",
        "",
        "Admin dashboard support E2E on Wales HMO pilot (staging only). Browser + API runtime proof.",
        "",
        "## Checklist",
    ]
    for k, v in clf.get("checklist", {}).items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        lines.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    lines.append("\n## Harness\n\n`backend/admin_dashboard_support_end_to_end_runtime_audit_01_execute.py`\n")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at, admin_user = login_admin()
    ct, _ = login_client()
    contractor_t = login_contractor()
    su = step_up(at)
    results: Dict[str, bool] = {}

    setup = part_setup(at)
    write_artifact("admin_runtime_setup.json", setup)
    results["setup"] = setup.get("pass", False)

    dash = part_dashboard(at, admin_user)
    write_artifact("admin_dashboard_overview_runtime.json", dash)
    results["dashboard"] = dash.get("pass", False)

    search = part_search(at, admin_user)
    write_artifact("admin_client_search_runtime.json", search)
    results["search"] = search.get("pass", False)

    support = part_support(at, su, admin_user)
    write_artifact("admin_client_support_runtime.json", support)
    results["support"] = support.get("pass", False)

    billing = part_billing(at, su, admin_user)
    write_artifact("admin_billing_runtime.json", billing)
    results["billing"] = billing.get("pass", False)

    ent = part_entitlements(at, su)
    write_artifact("admin_entitlements_runtime.json", ent)
    results["entitlements"] = ent.get("pass", False)

    comp = part_compliance(at, su, admin_user)
    write_artifact("admin_compliance_verification_runtime.json", comp)
    results["compliance"] = comp.get("pass", False)

    ops = part_operations(at)
    write_artifact("admin_operations_support_runtime.json", ops)
    results["operations"] = ops.get("pass", False)

    comm = part_communications(at, su)
    write_artifact("admin_communications_runtime.json", comm)
    results["communications"] = comm.get("pass", False)

    audit = part_audit_logs(at)
    write_artifact("admin_audit_logs_runtime.json", audit)
    results["audit_logs"] = audit.get("pass", False)

    perm = part_permissions(at, ct, contractor_t)
    write_artifact("admin_permissions_runtime.json", perm)
    results["permissions"] = perm.get("pass", False)

    edges = part_edge_cases(at, su)
    write_artifact("admin_edge_cases_runtime.json", edges)
    results["edge_cases"] = edges.get("pass", False)

    cross = part_cross_surface(at, ct, admin_user)
    write_artifact("admin_cross_surface_runtime.json", cross)
    results["cross_surface"] = cross.get("pass", False)

    reg = part_regression()
    write_artifact("admin_regression_runtime.json", reg)
    results["regression"] = reg.get("pass", False)

    clf = classify(results)
    write_artifact("classifications.json", clf)
    (BUNDLE / "REPORT.md").write_text(build_report(clf), encoding="utf-8")
    watch = [
        "# Admin dashboard support watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
    ]
    if clf.get("blockers"):
        for b in clf["blockers"]:
            watch.append(f"- [ ] Blocker: **{b}**")
    else:
        watch.append("- [x] Admin dashboard support E2E passed on staging pilot.")
        watch.append("- [ ] Deploy staging fixes if any GET endpoints still 500.")
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
