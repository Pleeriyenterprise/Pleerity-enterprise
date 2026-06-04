#!/usr/bin/env python3
"""
OPERATIONS-FAMILY-END-TO-END-RUNTIME-AUDIT-01 — unified landlord/contractor/tenant ops proof.

Local harness only. Writes artifacts to docs/audit/operations_family_end_to_end_runtime_audit_01/
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROGRAMME = "OPERATIONS-FAMILY-END-TO-END-RUNTIME-AUDIT-01"
BUNDLE = ROOT / "docs/audit/operations_family_end_to_end_runtime_audit_01"

CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
SLUG = "6fd5ac4c_d35a58ae"
LANDLORD_EMAIL = "nancy@yopmail.com"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "2.5"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-E2E-01-{RUN_TAG}"

STATE: Dict[str, Any] = {}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> Path:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    p = BUNDLE / name
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return p


def pace() -> None:
    time.sleep(PACE)


def h(token: str, *, step_up: str = "") -> Dict[str, str]:
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if step_up:
        hdr["X-Step-Up-Token"] = step_up
    return hdr


def http(method: str, path: str, token: str, **kwargs) -> httpx.Response:
    pace()
    url = path if path.startswith("http") else f"{API}{path}"
    return getattr(httpx, method)(url, headers=h(token, step_up=kwargs.pop("step_up", "")), **kwargs)


def read_pw(rel: str, env_key: str = "") -> str:
    if env_key and os.environ.get(env_key):
        return os.environ[env_key].strip()
    p = ROOT / rel
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(rel)


def login_landlord() -> Tuple[str, dict]:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = httpx.post(f"{API}/auth/login", json={"email": LANDLORD_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def login_contractor() -> Tuple[str, dict]:
    pw = read_pw(
        f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt",
        "OPS_CONTRACTOR_PASSWORD",
    )
    r = httpx.post(f"{API}/auth/contractor-login", json={"email": CONTRACTOR_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def login_tenant() -> Tuple[str, dict]:
    pw_path = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt"
    pw = os.environ.get("OPS_TENANT_PASSWORD") or (
        pw_path.read_text(encoding="utf-8").strip() if pw_path.is_file() else "F7OpsWales!Staging2026"
    )
    r = httpx.post(f"{API}/auth/login", json={"email": TENANT_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def step_up_token(client_token: str) -> Optional[str]:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = httpx.post(
        f"{API}/auth/step-up/verify",
        headers=h(client_token),
        json={"password": pw},
        timeout=60,
    )
    if r.status_code == 200:
        return r.json().get("step_up_token")
    return None


def seed_issue_wo(client_tok: str, desc: str, *, category: str = "heating") -> Tuple[Optional[str], Optional[str], List[dict]]:
    steps: List[dict] = []

    def log(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"step": name, "ok": ok, "detail": detail, "at_utc": utc()})

    cr = http("post", "/client/maintenance/issues", client_tok, json={"property_id": PID, "description": desc, "category": category}, timeout=120)
    issue_id = cr.json().get("issue_id") if cr.status_code == 200 else None
    log("create_issue", cr.status_code == 200 and bool(issue_id), f"status={cr.status_code} id={issue_id}")

    wo_id = None
    if issue_id:
        wr = http("post", f"/client/maintenance/issues/{issue_id}/create-work-order", client_tok, timeout=120)
        wo_id = wr.json().get("work_order_id") if wr.status_code == 200 else None
        log("create_work_order", wr.status_code == 200 and bool(wo_id), f"status={wr.status_code} wo={wo_id}")
        dup = http("post", f"/client/maintenance/issues/{issue_id}/create-work-order", client_tok, timeout=120)
        log("duplicate_create_wo_blocked", dup.status_code in (400, 409) or dup.json().get("work_order_id") == wo_id, f"status={dup.status_code}")

    return issue_id, wo_id, steps


def assign_quote_accept(client_tok: str, contractor_tok: str, wo_id: str) -> List[dict]:
    steps: List[dict] = []

    def log(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"step": name, "ok": ok, "detail": detail, "at_utc": utc()})

    ar = http("post", f"/jobs/{wo_id}/assign-contractor", client_tok, json={"contractor_id": CONTRACTOR_ID}, timeout=90)
    log("assign_contractor", ar.status_code in (200, 201), f"status={ar.status_code}")

    qr = http(
        "post",
        f"/jobs/{wo_id}/submit-quote",
        contractor_tok,
        json={"amount": 185.0, "currency": "GBP", "notes": f"{MARKER} quote"},
        timeout=90,
    )
    log("contractor_submit_quote", qr.status_code in (200, 201), f"status={qr.status_code}")
    apr = http("post", f"/jobs/{wo_id}/approve-quote", client_tok, timeout=90)
    log("landlord_approve_quote", apr.status_code in (200, 201), f"status={apr.status_code}")

    ac = http("post", f"/contractor/work-orders/{wo_id}/accept", contractor_tok, timeout=90)
    log("contractor_accept", ac.status_code in (200, 201), f"status={ac.status_code} st={ac.json().get('status') if ac.status_code==200 else ''}")

    cl = http("get", "/contractor/work-orders", contractor_tok, params={"limit": 50}, timeout=90)
    visible = any(w.get("work_order_id") == wo_id for w in (cl.json().get("work_orders") or [])) if cl.status_code == 200 else False
    log("contractor_sees_job", visible, f"list={cl.status_code}")

    gc = http("get", f"/client/maintenance/work-orders/{wo_id}", client_tok, timeout=90)
    log("landlord_sees_accepted", gc.status_code == 200, f"st={gc.json().get('status') if gc.status_code==200 else ''}")
    return steps


def assign_quote_decline(client_tok: str, contractor_tok: str, wo_id: str) -> List[dict]:
    steps: List[dict] = []

    def log(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"step": name, "ok": ok, "detail": detail, "at_utc": utc()})

    ar = http("post", f"/jobs/{wo_id}/assign-contractor", client_tok, json={"contractor_id": CONTRACTOR_ID}, timeout=90)
    log("assign_contractor", ar.status_code in (200, 201), f"status={ar.status_code}")
    qr = http(
        "post",
        f"/jobs/{wo_id}/submit-quote",
        contractor_tok,
        json={"amount": 190.0, "currency": "GBP", "notes": f"{MARKER} decline-path quote"},
        timeout=90,
    )
    log("contractor_submit_quote", qr.status_code in (200, 201), f"status={qr.status_code}")
    apr = http("post", f"/jobs/{wo_id}/approve-quote", client_tok, timeout=90)
    log("landlord_approve_quote", apr.status_code in (200, 201), f"status={apr.status_code}")

    dr = http("post", f"/contractor/work-orders/{wo_id}/decline", contractor_tok, timeout=90)
    log("contractor_decline", dr.status_code in (200, 201), f"status={dr.status_code}")

    gw = http("get", f"/client/maintenance/work-orders/{wo_id}", client_tok, timeout=90)
    st = (gw.json().get("status") or "").upper() if gw.status_code == 200 else ""
    cid = gw.json().get("contractor_id") if gw.status_code == 200 else "n/a"
    log("landlord_sees_reassignable", st in ("OPEN", "ASSIGNED", "QUOTED") or not cid, f"status={st} contractor={cid}")
    return steps


def complete_job_with_evidence(client_tok: str, contractor_tok: str, wo_id: str) -> List[dict]:
    steps: List[dict] = []

    def log(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"step": name, "ok": ok, "detail": detail, "at_utc": utc()})

    ip = http("patch", f"/contractor/work-orders/{wo_id}", contractor_tok, json={"status": "IN_PROGRESS"}, timeout=90)
    log("in_progress", ip.status_code == 200, f"st={ip.json().get('status') if ip.status_code==200 else ''}")

    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    pace()
    ev = httpx.post(
        f"{API}/contractor/work-orders/{wo_id}/evidence",
        headers={"Authorization": f"Bearer {contractor_tok}"},
        files={"file": ("completion-proof.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        timeout=120,
    )
    ev_keys = []
    if ev.status_code == 200:
        ev_keys = (ev.json().get("work_order") or {}).get("evidence_keys") or ev.json().get("evidence_keys") or []
    log("upload_evidence", ev.status_code == 200 and len(ev_keys) > 0, f"status={ev.status_code} keys={len(ev_keys)}")

    cp = http(
        "patch",
        f"/contractor/work-orders/{wo_id}",
        contractor_tok,
        json={"status": "COMPLETED", "completion_notes": f"{MARKER} completion notes"},
        timeout=90,
    )
    log("mark_completed", cp.status_code == 200 and (cp.json().get("status") or "").upper() == "COMPLETED", f"st={cp.json().get('status')}")

    gc = http("get", f"/client/maintenance/work-orders/{wo_id}", client_tok, timeout=90)
    log("landlord_sees_completed", (gc.json().get("status") or "").upper() == "COMPLETED" if gc.status_code == 200 else False, "")

    close1 = http("post", f"/jobs/{wo_id}/close", client_tok, timeout=90)
    verified = False
    if close1.status_code == 200:
        verified = (close1.json().get("status") or "").upper() in ("VERIFIED", "CLOSED")
    log("landlord_close_with_evidence", close1.status_code == 200 and verified, f"status={close1.status_code} body_st={(close1.json().get('status') if close1.status_code==200 else '')}")
    return steps


def invoice_flow(client_tok: str, contractor_tok: str, wo_id: str) -> List[dict]:
    steps: List[dict] = []

    def log(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"step": name, "ok": ok, "detail": detail, "at_utc": utc()})

    inv_pre = http(
        "post",
        "/contractor/invoices",
        contractor_tok,
        json={
            "work_order_id": wo_id,
            "reference": f"{MARKER}-inv",
            "submitted_amount": 185.0,
            "currency": "GBP",
            "description": f"{MARKER} invoice",
        },
        timeout=90,
    )
    log("contractor_submit_invoice", inv_pre.status_code in (200, 201), f"status={inv_pre.status_code} detail={inv_pre.text[:120]}")

    invoice_id = inv_pre.json().get("invoice_id") if inv_pre.status_code in (200, 201) else None
    STATE["invoice_id"] = invoice_id

    lst = http("get", "/client/approvals", client_tok, params={"workOrderId": wo_id, "limit": 20}, timeout=90)
    found = False
    if lst.status_code == 200:
        items = lst.json().get("items") or lst.json().get("approvals") or []
        found = any((i.get("invoice_id") == invoice_id or i.get("work_order_id") == wo_id) for i in items)
    log("landlord_lists_invoice", lst.status_code == 200 and (found or invoice_id), f"status={lst.status_code}")

    su = step_up_token(client_tok) or ""
    if invoice_id and su:
        appr = httpx.patch(
            f"{API}/client/approvals/{invoice_id}",
            headers=h(client_tok, step_up=su),
            json={"action": "approved", "notes": f"{MARKER} approved"},
            timeout=90,
        )
        log("landlord_approve_invoice", appr.status_code == 200, f"status={appr.status_code} inv_st={appr.json().get('status') if appr.status_code==200 else ''}")

        paid = httpx.patch(
            f"{API}/client/approvals/{invoice_id}",
            headers=h(client_tok, step_up=su),
            json={"action": "mark_paid", "payment_method": "bank_transfer", "payment_reference": f"{MARKER}-pay"},
            timeout=90,
        )
        log("landlord_mark_paid", paid.status_code == 200 and (paid.json().get("status") or "").lower() == "paid", f"status={paid.status_code}")
    else:
        log("landlord_approve_invoice", False, "missing invoice_id or step_up")
        log("landlord_mark_paid", False, "skipped")
    return steps


def rent_operations_flow(client_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"steps": [], "marker": MARKER}
    cap = http("get", "/client/operations/rent/capabilities", client_tok, timeout=90)
    out["capabilities_status"] = cap.status_code
    out["rent_enabled"] = cap.status_code == 200

    ten = http("get", "/client/operations/rent/tenancies", client_tok, params={"property_id": PID, "limit": 20}, timeout=90)
    tenancies = ten.json().get("tenancies") or [] if ten.status_code == 200 else []
    out["tenancy_count"] = len(tenancies)
    tenancy_id = tenancies[0].get("tenancy_id") if tenancies else None
    out["tenancy_id"] = tenancy_id
    out["tenancy_source"] = "existing" if tenancy_id else "none"

    if not tenancy_id and cap.status_code == 200:
        body = {
            "property_id": PID,
            "tenant_display_name": f"{MARKER} Tenant",
            "rent_amount_minor": 95000,
            "currency": "GBP",
            "rent_frequency": "monthly",
            "due_day": 1,
            "start_date": (date.today() - timedelta(days=60)).isoformat(),
        }
        cr = http("post", "/client/operations/rent/tenancies", client_tok, json=body, timeout=120)
        out["create_tenancy_status"] = cr.status_code
        tenancy_id = cr.json().get("tenancy_id") if cr.status_code in (200, 201) else None
        out["tenancy_id"] = tenancy_id
        out["tenancy_source"] = "seeded_this_run" if tenancy_id else "create_failed"

    ledgers_r = http("get", "/client/operations/rent/ledgers", client_tok, params={"property_id": PID, "limit": 30}, timeout=90)
    ledgers = ledgers_r.json().get("ledgers") or [] if ledgers_r.status_code == 200 else []
    out["ledger_count"] = len(ledgers)
    target = next((L for L in ledgers if (L.get("status") or "") not in ("PAID", "WAIVED")), None) or (ledgers[0] if ledgers else None)
    out["target_ledger"] = {k: target.get(k) for k in ("ledger_id", "status", "outstanding_balance_minor")} if target else None

    if target and target.get("ledger_id"):
        lid = target["ledger_id"]
        outstanding = int(target.get("outstanding_balance_minor") or 0)
        if outstanding > 0:
            partial = max(outstanding // 2, 1000)
            pr = http(
                "post",
                f"/client/operations/rent/ledgers/{lid}/payments",
                client_tok,
                json={
                    "amount_minor": partial,
                    "payment_date": date.today().isoformat(),
                    "reference": f"{MARKER}-partial",
                    "note": f"{MARKER} partial payment",
                },
                timeout=120,
            )
            out["partial_payment_status"] = pr.status_code
            gr = http("get", f"/client/operations/rent/ledgers/{lid}", client_tok, timeout=90)
            if gr.status_code == 200:
                out["after_partial_status"] = gr.json().get("status")
                out["after_partial_overdue"] = gr.json().get("is_overdue")

        overdue_ledger = next((L for L in ledgers if L.get("is_overdue")), None)
        out["has_overdue_in_list"] = overdue_ledger is not None

    summary = http("get", "/client/operations/rent/summary", client_tok, timeout=90)
    out["summary_status"] = summary.status_code
    if summary.status_code == 200:
        s = summary.json()
        out["rent_summary"] = {k: s.get(k) for k in ("overdue_count", "partial_overdue_count", "upcoming_count", "collected_this_month_minor") if k in s or True}

    out["pass"] = cap.status_code == 200 and ten.status_code == 200 and bool(tenancy_id) and ledgers_r.status_code == 200
    return out


def risk_signal_audit(client_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"signals": [], "validations": [], "pass": False}
    pr = http("get", f"/client/maintenance/properties/{PID}/risk-signals", client_tok, timeout=90)
    port = http("get", "/client/maintenance/risk-signals", client_tok, params={"limit": 50}, timeout=90)
    out["property_api_status"] = pr.status_code
    out["portfolio_api_status"] = port.status_code
    signals = []
    if pr.status_code == 200:
        signals = pr.json().get("signals") or pr.json().get("risk_signals") or []
    elif port.status_code == 200:
        signals = port.json().get("signals") or port.json().get("risk_signals") or []

    for sig in signals[:8]:
        sid = sig.get("signal_id") or sig.get("risk_signal_id")
        row = {
            "signal_id": sid,
            "risk_type": sig.get("risk_type") or sig.get("signal_type"),
            "signal_category": sig.get("signal_category"),
            "risk_level": sig.get("risk_level"),
            "status": sig.get("status"),
            "property_id": sig.get("property_id"),
            "reasons_sample": (sig.get("reasons") or [])[:2],
            "source": sig.get("source"),
            "stable_key": sig.get("stable_key"),
        }
        out["signals"].append(row)
        out["validations"].append(
            {
                "signal_id": sid,
                "has_risk_type": bool(row["risk_type"]),
                "has_level": bool(row["risk_level"]),
                "property_matches_pilot": row["property_id"] in (None, PID),
                "pass": bool(sid) and bool(row["risk_type"]),
            }
        )

    ack_id = next(
        (s.get("signal_id") or s.get("risk_signal_id") for s in signals if (s.get("status") or "").lower() == "active"),
        None,
    )
    if ack_id:
        ar = http(
            "patch",
            f"/client/maintenance/risk-signals/{ack_id}",
            client_tok,
            json={"status": "acknowledged"},
            timeout=90,
        )
        out["acknowledge_probe"] = {"risk_signal_id": ack_id, "status": ar.status_code, "pass": ar.status_code == 200}
    else:
        out["acknowledge_probe"] = {"skipped": True, "reason": "no active signal"}

    out["pass"] = pr.status_code == 200 or port.status_code == 200
    if out["validations"]:
        out["pass"] = out["pass"] and all(v["pass"] for v in out["validations"][:3])
    return out


def cross_surface_check(client_tok: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"surfaces": {}, "consistency": []}
    issues = http("get", "/client/maintenance/issues", client_tok, params={"property_id": PID, "limit": 200}, timeout=90)
    wos = http("get", "/client/maintenance/work-orders", client_tok, params={"property_id": PID, "limit": 200}, timeout=90)
    snap = http("get", "/client/protection-snapshot", client_tok, params={"property_id": PID}, timeout=90)
    risks = http("get", "/client/maintenance/risk-signals", client_tok, params={"property_id": PID, "limit": 200}, timeout=90)
    rent_sum = http("get", "/client/operations/rent/summary", client_tok, timeout=90)
    prop = http("get", f"/client/properties/{PID}", client_tok, timeout=90)

    open_issues_api = len([i for i in (issues.json().get("issues") or []) if (i.get("status") or "").lower() not in ("closed", "resolved", "cancelled")]) if issues.status_code == 200 else None
    open_wos = len([w for w in (wos.json().get("work_orders") or []) if (w.get("status") or "").upper() not in ("CLOSED", "CANCELLED")]) if wos.status_code == 200 else None
    snap_open = (snap.json().get("operations") or {}).get("open_maintenance_issues") if snap.status_code == 200 else None
    risk_active = (snap.json().get("risk") or {}).get("active_risk_signals_count") if snap.status_code == 200 else None

    out["surfaces"] = {
        "issues_list_open": open_issues_api,
        "work_orders_open": open_wos,
        "protection_snapshot_open_issues": snap_open,
        "protection_snapshot_risk_active": risk_active,
        "risk_signals_list_status": risks.status_code,
        "rent_summary_status": rent_sum.status_code,
        "property_status": prop.status_code,
    }
    if open_issues_api is not None and snap_open is not None:
        delta = abs(open_issues_api - snap_open)
        out["consistency"].append(
            {
                "check": "open_issues_vs_protection_snapshot",
                "pass": delta <= 2,
                "api_list": open_issues_api,
                "snapshot": snap_open,
                "delta": delta,
            }
        )
    out["pass"] = issues.status_code == 200 and wos.status_code == 200 and snap.status_code == 200
    if out["consistency"]:
        out["pass"] = out["pass"] and all(c["pass"] for c in out["consistency"])
    return out


def audit_trail_check(client_tok: str, issue_id: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"events": [], "expected_actions": [], "pass": False}
    if not issue_id:
        out["blocked"] = "no issue_id"
        return out
    tl = http("get", f"/client/maintenance/issues/{issue_id}/timeline", client_tok, params={"limit": 80}, timeout=90)
    out["timeline_status"] = tl.status_code
    events = tl.json().get("items") or tl.json().get("events") or tl.json().get("timeline") or [] if tl.status_code == 200 else []
    types = {e.get("event_type") or e.get("action") or e.get("type") for e in events}
    out["event_type_sample"] = sorted(x for x in types if x)[:25]
    out["event_count"] = len(events)
    expected = ["issue", "work_order", "contractor", "quote", "complete", "invoice", "payment", "rent", "risk"]
    found = []
    blob = json.dumps(events, default=str).lower()
    for kw in expected:
        found.append({"keyword": kw, "present": kw in blob})
    out["expected_actions"] = found
    out["pass"] = tl.status_code == 200 and len(events) >= 2 and any(f["present"] for f in found[:4])
    return out


def permissions_check(client_tok: str, contractor_tok: str, tenant_tok: str, wo_id: Optional[str]) -> Dict[str, Any]:
    probes: List[dict] = []

    def probe(name: str, method: str, path: str, token: str, expect_forbidden: bool) -> None:
        r = http(method, path, token, timeout=60) if method != "get" else http("get", path, token, timeout=60)
        ok = (r.status_code in (401, 403, 404) if expect_forbidden else r.status_code in (200, 201))
        probes.append({"name": name, "status": r.status_code, "expect_forbidden": expect_forbidden, "pass": ok})

    probe("landlord_can_list_issues", "get", "/client/maintenance/issues", client_tok, False)
    probe("contractor_cannot_list_client_issues", "get", "/client/maintenance/issues", contractor_tok, True)
    probe("tenant_cannot_list_client_issues", "get", "/client/maintenance/issues", tenant_tok, True)
    if wo_id:
        probe("contractor_can_view_assigned_wo", "get", f"/contractor/work-orders/{wo_id}", contractor_tok, False)
        probe("contractor_cannot_view_fake_wo", "get", "/contractor/work-orders/00000000-0000-0000-0000-000000000099", contractor_tok, True)
        probe("tenant_cannot_view_contractor_wo", "get", f"/contractor/work-orders/{wo_id}", tenant_tok, True)
    return {"probes": probes, "pass": all(p["pass"] for p in probes)}


def edge_cases(client_tok: str, contractor_tok: str) -> Dict[str, Any]:
    probes: List[dict] = []
    _, wo_early, _ = seed_issue_wo(client_tok, f"{MARKER} edge early invoice", category="general")
    if wo_early:
        http("post", f"/jobs/{wo_early}/assign-contractor", client_tok, json={"contractor_id": CONTRACTOR_ID}, timeout=90)
        http(
            "post",
            f"/jobs/{wo_early}/submit-quote",
            contractor_tok,
            json={"amount": 120.0, "currency": "GBP", "notes": f"{MARKER} edge quote"},
            timeout=90,
        )
        http("post", f"/jobs/{wo_early}/approve-quote", client_tok, timeout=90)
        http("post", f"/contractor/work-orders/{wo_early}/accept", contractor_tok, timeout=90)
        inv = http(
            "post",
            "/contractor/invoices",
            contractor_tok,
            json={"work_order_id": wo_early, "submitted_amount": 50.0, "currency": "GBP"},
            timeout=90,
        )
        probes.append(
            {
                "name": "invoice_before_completion_blocked",
                "pass": inv.status_code in (400, 403),
                "status": inv.status_code,
                "detail": inv.text[:100],
            }
        )
    _, wo_no_ev, _ = seed_issue_wo(client_tok, f"{MARKER} edge no evidence complete")
    if wo_no_ev:
        assign_quote_accept(client_tok, contractor_tok, wo_no_ev)
        cp = http("patch", f"/contractor/work-orders/{wo_no_ev}", contractor_tok, json={"status": "COMPLETED"}, timeout=90)
        cl = http("post", f"/jobs/{wo_no_ev}/close", client_tok, timeout=90)
        probes.append(
            {
                "name": "close_without_evidence_blocked",
                "pass": cl.status_code in (400, 403) or cp.status_code != 200,
                "close_status": cl.status_code,
            }
        )
    return {"probes": probes, "pass": all(p.get("pass") for p in probes) if probes else False}


def run_browser_landlord(token: str, user: dict, issue_id: Optional[str], wo_id: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"role": "landlord", "available": False, "steps": []}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        out["error"] = f"playwright_missing: {exc}"
        return out
    out["available"] = True
    shot = BUNDLE / "screenshots"
    shot.mkdir(parents=True, exist_ok=True)

    def log(step: str, ok: bool, detail: str = "") -> None:
        out["steps"].append({"step": step, "ok": ok, "detail": detail, "at_utc": utc()})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
        page.goto(f"{FRONTEND}/operations/issues", wait_until="networkidle", timeout=120_000)
        body = page.locator("body").inner_text()
        log("issues_page_loads", "issue" in body.lower() or MARKER[:12] in body, body[:60])
        page.screenshot(path=str(shot / "landlord_issues.png"))
        if issue_id:
            page.goto(f"{FRONTEND}/operations/issues/{issue_id}", wait_until="networkidle", timeout=120_000)
            log("issue_detail", MARKER[:12] in page.locator("body").inner_text() or issue_id[:8] in page.content(), "")
            page.screenshot(path=str(shot / "landlord_issue_detail.png"))
        if wo_id:
            page.goto(f"{FRONTEND}/operations/jobs/{wo_id}", wait_until="networkidle", timeout=120_000)
            log("job_detail", wo_id[:8] in page.content() or MARKER[:12] in page.locator("body").inner_text(), "")
            page.screenshot(path=str(shot / "landlord_job_detail.png"))
        page.goto(f"{FRONTEND}/properties/{PID}", wait_until="networkidle", timeout=120_000)
        log("property_operating_tab", "maintenance" in page.locator("body").inner_text().lower() or "job" in page.locator("body").inner_text().lower(), "")
        page.screenshot(path=str(shot / "landlord_property.png"))
        browser.close()
    out["pass"] = out["available"] and any(s["ok"] for s in out["steps"])
    return out


def run_browser_contractor(token: str, user: dict, wo_id: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"role": "contractor", "available": False, "steps": []}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        out["error"] = f"playwright_missing: {exc}"
        return out
    out["available"] = True
    shot = BUNDLE / "screenshots"
    shot.mkdir(parents=True, exist_ok=True)

    def log(step: str, ok: bool, detail: str = "") -> None:
        out["steps"].append({"step": step, "ok": ok, "detail": detail, "at_utc": utc()})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{FRONTEND}/contractor/login", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('contractor_token',t);localStorage.setItem('contractor_user',JSON.stringify(u));}",
            [token, user],
        )
        page.goto(f"{FRONTEND}/contractor", wait_until="networkidle", timeout=120_000)
        body = page.locator("body").inner_text()
        log("contractor_portal_loads", len(body) > 50, body[:80])
        page.screenshot(path=str(shot / "contractor_portal.png"))
        if wo_id:
            page.goto(f"{FRONTEND}/contractor/jobs/{wo_id}", wait_until="networkidle", timeout=120_000)
            log("contractor_job_detail", wo_id[:8] in page.content() or "job" in body.lower(), "")
            page.screenshot(path=str(shot / "contractor_job.png"))
        browser.close()
    out["pass"] = out["available"] and any(s["ok"] for s in out["steps"])
    return out


def run_regression_tests() -> Dict[str, Any]:
    suites = [
        "tests/test_contractor_lifecycle.py",
        "tests/test_contractor_evidence_and_decline.py",
        "tests/test_client_maintenance_contractor_routing_http.py",
        "tests/test_rent_operations.py",
        "tests/test_client_rent_operations_http.py",
        "tests/test_workflow_contractors_http.py",
    ]
    results = []
    for suite in suites:
        started = time.time()
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", suite, "-q", "--tb=no"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        results.append(
            {
                "suite": suite,
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "elapsed_s": round(time.time() - started, 1),
                "stdout_tail": (proc.stdout or "")[-400:],
                "stderr_tail": (proc.stderr or "")[-200:],
            }
        )
    return {"suites": results, "pass": all(r["ok"] for r in results)}


def classify(results: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    flags: List[str] = []

    checks = [
        ("setup", results.get("setup", {}).get("pass")),
        ("issue_job", results.get("issue_job", {}).get("pass")),
        ("contractor_assignment", results.get("contractor_assignment", {}).get("pass")),
        ("job_completion", results.get("job_completion", {}).get("pass")),
        ("invoice", results.get("invoice", {}).get("pass")),
        ("rent", results.get("rent", {}).get("pass")),
        ("risk", results.get("risk", {}).get("pass")),
        ("cross_surface", results.get("cross_surface", {}).get("pass")),
        ("audit_trail", results.get("audit_trail", {}).get("pass")),
        ("permissions", results.get("permissions", {}).get("pass")),
        ("edge_cases", results.get("edge_cases", {}).get("pass")),
        ("regression", results.get("regression", {}).get("pass")),
        ("browser_landlord", results.get("browser_landlord", {}).get("pass")),
        ("browser_contractor", results.get("browser_contractor", {}).get("pass")),
    ]
    for name, ok in checks:
        if ok is False:
            blockers.append(name)

    if not results.get("browser_landlord", {}).get("pass") or not results.get("browser_contractor", {}).get("pass"):
        flags.append("BROWSER_PROOF_GAP")

    if not results.get("contractor_assignment", {}).get("decline_pass"):
        flags.append("CONTRACTOR_WORKFLOW_DRIFT")
        blockers.append("contractor_decline")

    classification = "VERIFIED_OPERATIONALLY"
    if blockers:
        if len(blockers) <= 3 and results.get("issue_job", {}).get("pass"):
            classification = "PARTIAL"
        else:
            classification = "FAIL_OPERATIONAL"
    if "contractor_decline" in blockers:
        classification = "CONTRACTOR_WORKFLOW_DRIFT" if classification != "FAIL_OPERATIONAL" else classification
    if not results.get("rent", {}).get("pass"):
        flags.append("RENT_OPERATIONS_DRIFT")
    if not results.get("risk", {}).get("pass"):
        flags.append("RISK_SIGNAL_DRIFT")
    if not results.get("audit_trail", {}).get("pass"):
        flags.append("AUDIT_TRAIL_DRIFT")
    if not results.get("permissions", {}).get("pass"):
        flags.append("PERMISSION_DRIFT")

    return {
        "programme": PROGRAMME,
        "classification": classification,
        "secondary_flags": flags,
        "blockers": blockers,
        "classified_at_utc": utc(),
        "proof_mode": "operational_api_and_browser",
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "checklist": dict(checks),
    }


def build_report(results: Dict[str, Any], clf: Dict[str, Any]) -> str:
    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        f"**Marker:** `{MARKER}`",
        f"**API:** `{API}`",
        f"**Frontend:** `{FRONTEND}`",
        "",
        "## Summary",
        "",
    ]
    for key in ("setup", "issue_job", "contractor_assignment", "job_completion", "invoice", "rent", "risk", "cross_surface", "audit_trail", "permissions", "edge_cases", "regression"):
        r = results.get(key, {})
        status = "PASS" if r.get("pass") else "FAIL"
        lines.append(f"- **{key}:** {status}")
    lines.extend(["", "## Blockers", ""])
    for b in clf.get("blockers") or []:
        lines.append(f"- {b}")
    lines.extend(["", "## Personas", ""])
    s = results.get("setup", {})
    lines.append(f"- Landlord: `{LANDLORD_EMAIL}` client `{CID}`")
    lines.append(f"- Contractor: `{CONTRACTOR_EMAIL}` id `{CONTRACTOR_ID}`")
    lines.append(f"- Property: `{PID}`")
    lines.append(f"- Tenant: `{TENANT_EMAIL}`")
    lines.append(f"- Tenancy source: `{s.get('tenancy_source', 'n/a')}`")
    return "\n".join(lines) + "\n"


def build_watchlist(clf: Dict[str, Any]) -> str:
    items = clf.get("blockers") or []
    flags = clf.get("secondary_flags") or []
    lines = ["# Operations E2E watchlist", ""]
    if not items and not flags:
        lines.append("- No open blockers from this run.")
    for i in items:
        lines.append(f"- [ ] Resolve blocker: **{i}**")
    for f in flags:
        lines.append(f"- [ ] Secondary flag: **{f}**")
    return "\n".join(lines) + "\n"


async def main_async() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    results: Dict[str, Any] = {}

    # PART 1 — setup
    setup: Dict[str, Any] = {"at_utc": utc(), "seeded_vs_natural": {}}
    try:
        lt, lu = login_landlord()
        ct, cu = login_contractor()
        tt, tu = login_tenant()
        setup["landlord_session"] = {"email": LANDLORD_EMAIL, "client_id": lu.get("client_id"), "role": lu.get("role")}
        setup["contractor_session"] = {"email": CONTRACTOR_EMAIL, "contractor_id": cu.get("contractor_id")}
        setup["tenant_session"] = {"email": TENANT_EMAIL, "role": tu.get("role")}
        ent = http("get", "/client/entitlements", lt, timeout=90)
        setup["entitlements_status"] = ent.status_code
        if ent.status_code == 200:
            feats = ent.json().get("features") or {}
            setup["maintenance_workflows"] = (feats.get("maintenance_workflows") or {}).get("enabled")
            setup["invoicing"] = (feats.get("invoicing") or feats.get("INVOICING") or {}).get("enabled") if isinstance(feats.get("invoicing"), dict) else feats.get("invoicing")
            setup["rent_operations"] = (feats.get("rent_operations") or {}).get("enabled")
            setup["predictive_maintenance"] = (feats.get("predictive_maintenance") or {}).get("enabled")
        props = http("get", "/client/properties", lt, timeout=90)
        prop = next((p for p in (props.json().get("properties") or []) if p.get("property_id") == PID), None) if props.status_code == 200 else None
        setup["property"] = {"property_id": PID, "label": (prop or {}).get("nickname"), "jurisdiction": (prop or {}).get("jurisdiction")}
        setup["account_ids"] = {"client_id": CID, "property_id": PID, "contractor_id": CONTRACTOR_ID}
        setup["seeded_vs_natural"] = {
            "landlord": "natural_staging_account",
            "contractor": "pilot_fixture_documented_in_ops_runtime_03",
            "property": "charter_wales_hmo_pilot",
            "tenant": "ops_runtime_07_tenant_portal_fixture",
        }
        setup["pass"] = lu.get("client_id") == CID and ent.status_code == 200 and bool(setup.get("maintenance_workflows"))
        STATE["lt"], STATE["lu"], STATE["ct"], STATE["cu"], STATE["tt"], STATE["tu"] = lt, lu, ct, cu, tt, tu
    except Exception as exc:
        setup["error"] = str(exc)[:400]
        setup["pass"] = False
    write_artifact("operations_runtime_setup.json", setup)
    results["setup"] = setup
    if not setup.get("pass"):
        clf = classify(results)
        write_artifact("classifications.json", clf)
        (BUNDLE / "REPORT.md").write_text(build_report(results, clf), encoding="utf-8")
        (BUNDLE / "watchlist.md").write_text(build_watchlist(clf), encoding="utf-8")
        return 1

    lt, ct, tt = STATE["lt"], STATE["ct"], STATE["tt"]

    # PART 2 — issue → job
    issue_steps: List[dict] = []
    issue_id, wo_id, issue_steps = seed_issue_wo(lt, f"{MARKER} — E2E issue/job path")
    li = http("get", "/client/maintenance/issues", lt, params={"property_id": PID, "limit": 50}, timeout=90)
    listed = any(i.get("issue_id") == issue_id for i in (li.json().get("issues") or [])) if li.status_code == 200 else False
    issue_steps.append({"step": "issue_in_list", "ok": listed, "at_utc": utc()})
    lw = http("get", "/client/maintenance/work-orders", lt, params={"property_id": PID, "limit": 50}, timeout=90)
    wo_listed = any(w.get("work_order_id") == wo_id for w in (lw.json().get("work_orders") or [])) if lw.status_code == 200 else False
    issue_steps.append({"step": "job_in_list", "ok": wo_listed, "at_utc": utc()})
    tl = http("get", f"/client/maintenance/issues/{issue_id}/timeline", lt, timeout=90) if issue_id else None
    tl_items = (tl.json().get("items") or tl.json().get("events") or []) if tl and tl.status_code == 200 else []
    issue_steps.append({"step": "timeline_updated", "ok": tl.status_code == 200 and len(tl_items) >= 1 if tl else False, "at_utc": utc(), "detail": f"items={len(tl_items)}"})
    STATE["primary_issue_id"] = issue_id
    STATE["primary_wo_id"] = wo_id
    issue_job = {"issue_id": issue_id, "work_order_id": wo_id, "steps": issue_steps, "pass": bool(issue_id and wo_id) and all(s["ok"] for s in issue_steps)}
    write_artifact("issue_job_runtime.json", issue_job)
    results["issue_job"] = issue_job

    # PART 3 — contractor assignment (accept + decline jobs)
    _, wo_accept, steps_a = seed_issue_wo(lt, f"{MARKER} — accept path")
    assign_steps = assign_quote_accept(lt, ct, wo_accept) if wo_accept else []
    _, wo_decline, _ = seed_issue_wo(lt, f"{MARKER} — decline path")
    decline_steps = assign_quote_decline(lt, ct, wo_decline) if wo_decline else []
    ca = {
        "accept_work_order_id": wo_accept,
        "decline_work_order_id": wo_decline,
        "accept_steps": steps_a + assign_steps,
        "decline_steps": decline_steps,
        "pass": bool(wo_accept) and all(s["ok"] for s in assign_steps),
        "decline_pass": bool(wo_decline) and all(s["ok"] for s in decline_steps),
    }
    write_artifact("contractor_assignment_runtime.json", ca)
    results["contractor_assignment"] = ca
    STATE["completion_wo_id"] = wo_accept

    # PART 4 — completion on accept path
    comp_steps = complete_job_with_evidence(lt, ct, wo_accept) if wo_accept else []
    jc = {"work_order_id": wo_accept, "steps": comp_steps, "pass": bool(wo_accept) and all(s["ok"] for s in comp_steps)}
    write_artifact("job_completion_runtime.json", jc)
    results["job_completion"] = jc

    # PART 5 — invoice
    inv_steps = invoice_flow(lt, ct, wo_accept) if wo_accept else []
    inv = {"work_order_id": wo_accept, "invoice_id": STATE.get("invoice_id"), "steps": inv_steps, "pass": all(s["ok"] for s in inv_steps) if inv_steps else False}
    write_artifact("contractor_invoice_runtime.json", inv)
    results["invoice"] = inv

    # PART 6 — rent
    rent = rent_operations_flow(lt)
    write_artifact("rent_operations_runtime.json", rent)
    results["rent"] = rent
    setup["tenancy_source"] = rent.get("tenancy_source")
    write_artifact("operations_runtime_setup.json", setup)

    # PART 7 — risk
    risk = risk_signal_audit(lt)
    write_artifact("risk_signal_runtime.json", risk)
    results["risk"] = risk

    # PART 8 — cross surface
    cross = cross_surface_check(lt)
    write_artifact("operations_cross_surface_runtime.json", cross)
    results["cross_surface"] = cross

    # PART 9 — audit trail
    audit = audit_trail_check(lt, issue_id)
    write_artifact("operations_audit_trail_runtime.json", audit)
    results["audit_trail"] = audit

    # PART 10 — permissions
    perm = permissions_check(lt, ct, tt, wo_accept)
    write_artifact("operations_permissions_runtime.json", perm)
    results["permissions"] = perm

    # PART 11 — edge cases
    edge = edge_cases(lt, ct)
    write_artifact("operations_edge_cases_runtime.json", edge)
    results["edge_cases"] = edge

    # Browser proofs
    bl = await asyncio.to_thread(run_browser_landlord, lt, STATE["lu"], issue_id, wo_accept)
    bc = await asyncio.to_thread(run_browser_contractor, ct, STATE["cu"], wo_accept)
    results["browser_landlord"] = bl
    results["browser_contractor"] = bc

    # PART 12 — regression
    reg = run_regression_tests()
    write_artifact("operations_regression_runtime.json", reg)
    results["regression"] = reg

    # PART 13 — classification
    clf = classify(results)
    write_artifact("classifications.json", clf)
    (BUNDLE / "REPORT.md").write_text(build_report(results, clf), encoding="utf-8")
    (BUNDLE / "watchlist.md").write_text(build_watchlist(clf), encoding="utf-8")

    print("CLASSIFICATION", clf["classification"])
    print("BLOCKERS", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
