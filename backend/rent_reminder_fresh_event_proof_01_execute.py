#!/usr/bin/env python3
"""
RENT-REMINDER-FRESH-EVENT-PROOF-01
Create fresh rent ledger periods (no prior reminder events) and prove live delivery.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/rent_operations_landlord_tenant_runtime_audit_01"
PROGRAMME = "RENT-REMINDER-FRESH-EVENT-PROOF-01"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = os.environ.get("OPS_VERIFY_PROPERTY_A", "d35a58ae-3c81-491c-9694-1d021dd3b8ad")
TENANCY_ID = os.environ.get("OPS_TENANCY_ID", "pty_9ec2e1723d7b")
TENANT_EMAIL = os.environ.get("OPS_TENANT_EMAIL", "f7-ops-wales@yopmail.com")
TENANT_ID = os.environ.get("OPS_TENANT_ID", "962fa7b2-d8a0-4082-8d89-f4a2abb402e0")

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
PACE = float(os.environ.get("OPS_API_PACE_S", "2.5"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"RENT-FRESH-{RUN_TAG}"
REASON = f"{PROGRAMME} fresh event live delivery proof for client {CLIENT_ID[:8]}"
DUE_SOON_DAYS = 3


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


def h(token: str = "", confirmation: str = "", step_up: str = "") -> Dict[str, str]:
    base: Dict[str, str] = {"Content-Type": "application/json"}
    if token:
        base["Authorization"] = f"Bearer {token}"
    if confirmation:
        base["X-Admin-Confirmation-Token"] = confirmation
    if step_up:
        base["X-Step-Up-Token"] = step_up
    return base


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = path if path.startswith("http") else f"{API}{path}"
    headers = kwargs.pop("headers", None) or (h(token) if token else h())
    timeout = kwargs.pop("timeout", 120)
    for attempt in range(5):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=timeout, **kwargs)
            if resp.status_code == 429 and attempt < 4:
                time.sleep(min(120, 30 * (attempt + 1)))
                continue
            if resp.status_code in (502, 503) and attempt < 4:
                time.sleep(8 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"request failed: {method} {path}")


def login_client() -> str:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = req("post", "/auth/login", json={"email": "nancy@yopmail.com", "password": pw})
    r.raise_for_status()
    return r.json()["access_token"]


def login_tenant() -> str:
    pw = read_pw(f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt", "OPS_TENANT_PASSWORD")
    if not pw:
        pw = os.environ.get("OPS_TENANT_PASSWORD", "F7OpsWales!Staging2026")
    r = req("post", "/auth/tenant-login", json={"email": TENANT_EMAIL, "password": pw})
    if r.status_code != 200:
        r = req("post", "/auth/login", json={"email": TENANT_EMAIL, "password": pw})
    r.raise_for_status()
    return r.json().get("access_token") or r.json()["token"]


def login_admin() -> str:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    r = req("post", "/auth/admin/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["access_token"]


def admin_step_up(admin_t: str) -> str:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    r = req("post", "/auth/step-up/verify", admin_t, json={"password": pw})
    return r.json().get("step_up_token", "") if r.status_code == 200 else ""


def admin_confirmation(admin_t: str, resource_key: str, step_up: str = "") -> str:
    r = req(
        "post",
        "/admin/governance/confirmation-token",
        admin_t,
        headers=h(admin_t, step_up=step_up),
        json={"action_id": "run_scoped_automation_job", "reason": REASON, "resource_key": resource_key},
    )
    return r.json().get("token", "") if r.status_code == 200 else ""


def run_rent_daily_job(admin_t: str, step_up: str = "") -> httpx.Response:
    resource_key = f"rent_operations_daily_job:{CLIENT_ID}"
    conf = admin_confirmation(admin_t, resource_key, step_up=step_up)
    return req(
        "post",
        "/admin/jobs/run",
        admin_t,
        headers=h(admin_t, conf, step_up),
        json={"job": "rent_operations_daily_job", "client_id": CLIENT_ID, "reason": REASON},
        timeout=300,
    )


def get_ledger(client_t: str, ledger_id: str) -> dict:
    r = req("get", f"/client/operations/rent/ledgers/{ledger_id}", client_t)
    return r.json() if r.status_code == 200 else {}


def list_ledgers(client_t: str, **params: Any) -> List[dict]:
    p = {"property_id": PROPERTY_ID, "tenancy_id": TENANCY_ID, "limit": 300, **params}
    r = req("get", "/client/operations/rent/ledgers", client_t, params=p)
    return (r.json().get("ledgers") or []) if r.status_code == 200 else []


def create_schedule(client_t: str, body: dict) -> Tuple[dict, int]:
    r = req("post", "/client/operations/rent/schedules", client_t, json=body, timeout=180)
    return (r.json() if r.status_code in (200, 201) else {"error": (r.text or "")[:300]}), r.status_code


def record_payment(client_t: str, ledger_id: str, body: dict) -> httpx.Response:
    return req("post", f"/client/operations/rent/ledgers/{ledger_id}/payments", client_t, json=body)


def message_logs(admin_t: str, **params: Any) -> Tuple[List[dict], int]:
    r = req("get", "/admin/message-logs", admin_t, params={"client_id": CLIENT_ID, "limit": 200, **params})
    if r.status_code != 200:
        return [], r.status_code
    body = r.json()
    return body.get("items") or body.get("messages") or [], r.status_code


def get_message_detail(admin_t: str, message_id: str) -> dict:
    r = req("get", f"/admin/message-logs/{message_id}", admin_t)
    return r.json() if r.status_code == 200 else {}


def tenant_sent_logs(logs: List[dict]) -> List[dict]:
    return [
        m
        for m in logs
        if m.get("status") == "sent" and TENANT_EMAIL.lower() in str(m.get("recipient", "")).lower()
    ]


def sanitize_log(row: dict) -> dict:
    return {
        "message_id": row.get("message_id"),
        "status": row.get("status"),
        "template_key": row.get("template_key"),
        "recipient": row.get("recipient"),
        "created_at": row.get("created_at"),
        "idempotency_key": (row.get("idempotency_key") or "")[:80],
    }


def due_schedule_params(today: date) -> Tuple[dict, str]:
    if today.day <= 28:
        return {"start_date": today.isoformat(), "due_day": today.day}, "due_today"
    soon = today + timedelta(days=DUE_SOON_DAYS)
    return {"start_date": soon.isoformat(), "due_day": min(soon.day, 28)}, "due_soon"


def find_fresh_ledger(
    client_t: str,
    ledgers: List[dict],
    *,
    schedule_id: Optional[str] = None,
    due_match: Optional[date] = None,
    min_overdue: int = 0,
    marker_in_notes: bool = True,
) -> Optional[dict]:
    for row in sorted(ledgers, key=lambda x: x.get("due_date") or ""):
        if int(row.get("outstanding_balance_minor") or 0) <= 0:
            continue
        if schedule_id and row.get("schedule_id") != schedule_id:
            continue
        if due_match and str(row.get("due_date", ""))[:10] != due_match.isoformat():
            continue
        if min_overdue and int(row.get("days_overdue") or 0) < min_overdue:
            continue
        if marker_in_notes and MARKER not in str(row.get("notes") or ""):
            continue
        detail = get_ledger(client_t, row["ledger_id"])
        if detail.get("reminders"):
            continue
        return detail
    return None


def part_fixture(client_t: str, today: date) -> dict:
    overdue_start = (today - timedelta(days=100)).replace(day=1)
    overdue_body = {
        "property_id": PROPERTY_ID,
        "tenancy_id": TENANCY_ID,
        "expected_amount_minor": 118500,
        "due_day": 1,
        "start_date": overdue_start.isoformat(),
        "rent_frequency": "monthly",
        "tenant_name": "mat",
        "notes": f"{MARKER} overdue fixture",
        "idempotency_key": f"{MARKER}-overdue-sched",
    }
    overdue_sched, overdue_st = create_schedule(client_t, overdue_body)
    overdue_sid = overdue_sched.get("schedule_id")

    due_params, expect_type = due_schedule_params(today)
    due_body = {
        "property_id": PROPERTY_ID,
        "tenancy_id": TENANCY_ID,
        "expected_amount_minor": 125000,
        "rent_frequency": "monthly",
        "tenant_name": "mat",
        "notes": f"{MARKER} due fixture",
        "idempotency_key": f"{MARKER}-due-sched",
        **due_params,
    }
    due_sched, due_st = create_schedule(client_t, due_body)
    due_sid = due_sched.get("schedule_id")

    ledgers = list_ledgers(client_t)
    due_match = today if expect_type == "due_today" else today + timedelta(days=DUE_SOON_DAYS)
    due_ledger = find_fresh_ledger(client_t, ledgers, schedule_id=due_sid, due_match=due_match, marker_in_notes=False)
    if not due_ledger:
        due_ledger = find_fresh_ledger(client_t, ledgers, schedule_id=due_sid, marker_in_notes=False)
    overdue_ledger = find_fresh_ledger(client_t, ledgers, schedule_id=overdue_sid, min_overdue=3, marker_in_notes=False)
    if not overdue_ledger:
        overdue_ledger = find_fresh_ledger(client_t, ledgers, min_overdue=3, marker_in_notes=False)

    return {
        "at_utc": utc(),
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "tenancy_id": TENANCY_ID,
        "tenant_recipient": TENANT_EMAIL,
        "overdue_schedule": {"status": overdue_st, "schedule_id": overdue_sid, "body": overdue_sched},
        "due_schedule": {"status": due_st, "schedule_id": due_sid, "expected_reminder_type": expect_type, "body": due_sched},
        "due_ledger_id": due_ledger.get("ledger_id") if due_ledger else None,
        "overdue_ledger_id": overdue_ledger.get("ledger_id") if overdue_ledger else None,
        "due_ledger": {
            "due_date": due_ledger.get("due_date"),
            "outstanding": due_ledger.get("outstanding_balance_minor"),
            "prior_reminders": len(due_ledger.get("reminders") or []) if due_ledger else None,
        }
        if due_ledger
        else None,
        "overdue_ledger": {
            "due_date": overdue_ledger.get("due_date"),
            "outstanding": overdue_ledger.get("outstanding_balance_minor"),
            "days_overdue": overdue_ledger.get("days_overdue"),
            "prior_reminders": len(overdue_ledger.get("reminders") or []) if overdue_ledger else None,
        }
        if overdue_ledger
        else None,
        "pass": bool(due_ledger and overdue_ledger and overdue_st in (200, 201) and due_st in (200, 201)),
    }


def verify_delivery(
    admin_t: str,
    client_t: str,
    ledger_id: Optional[str],
    before_ids: Set[str],
    logs: List[dict],
    expect_types: Tuple[str, ...],
) -> dict:
    detail = get_ledger(client_t, ledger_id) if ledger_id else {}
    reminders = detail.get("reminders") or []
    matching = [r for r in reminders if r.get("reminder_type") in expect_types or str(r.get("reminder_type", "")).startswith("overdue")]
    sent_events = [r for r in matching if r.get("delivery_status") == "sent"]
    tenant_logs = tenant_sent_logs(logs)
    new_sent = [m for m in tenant_logs if m.get("message_id") not in before_ids]
    detail_log = {}
    content_ok = False
    if new_sent:
        detail_log = get_message_detail(admin_t, new_sent[0].get("message_id", ""))
        blob = json.dumps(detail_log).lower()
        content_ok = (
            TENANT_EMAIL.lower() in blob
            and bool(re.search(r"£|outstanding|rent", blob, re.I))
            and bool(re.search(r"due|overdue", blob, re.I))
        )
    return {
        "ledger_id": ledger_id,
        "reminder_events": [
            {
                "reminder_type": r.get("reminder_type"),
                "delivery_status": r.get("delivery_status"),
                "recipient_email": r.get("recipient_email"),
                "reminder_key": r.get("reminder_key"),
            }
            for r in matching[:5]
        ],
        "sent_events": sent_events,
        "live_send_inferred": bool(sent_events) or any(r.get("delivery_status") == "sent" for r in matching),
        "created_as_manual": bool(matching) and all(r.get("delivery_status") == "manual" for r in matching),
        "new_tenant_sent_logs": [sanitize_log(m) for m in new_sent[:3]],
        "message_detail": {
            "status": detail_log.get("status"),
            "template_key": detail_log.get("template_key"),
            "recipient": detail_log.get("recipient"),
            "subject": (detail_log.get("subject") or "")[:160],
        },
        "content_accurate": content_ok,
        "pass": bool(sent_events) and any(m.get("status") == "sent" for m in new_sent) and detail_log.get("template_key") == "RENT_REMINDER",
    }


def part_regression() -> dict:
    tests = [
        "tests/test_rent_operations.py",
        "tests/test_client_rent_operations_http.py",
        "tests/test_notification_orchestrator.py",
    ]
    env = {**os.environ, "CI": "true", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no", "-k", "rent or reminder or idempotency"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )
    return {
        "at_utc": utc(),
        "exit_code": proc.returncode,
        "tail": (proc.stdout + proc.stderr)[-2500:],
        "pass": proc.returncode == 0,
    }


def classify(results: Dict[str, bool], delivery_note: str = "") -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags: List[str] = []
    if blockers:
        if "due_delivery" in blockers or "overdue_delivery" in blockers:
            flags.append("DELIVERY_DRIFT")
        if "dedupe" in blockers:
            flags.append("IDEMPOTENCY_DRIFT")
        if "tenant_targeting" in blockers:
            flags.append("TENANT_TARGETING_DRIFT")
        if "due_delivery" in blockers and "overdue_delivery" in blockers:
            flags.append("RENT_REMINDER_GAP")
        clf = "VERIFIED_OPERATIONALLY" if not blockers else ("PARTIAL" if len(blockers) <= 3 else "FAIL_OPERATIONAL")
    else:
        clf = "VERIFIED_OPERATIONALLY"
    return {
        "programme": PROGRAMME,
        "parent_audit": "RENT-OPERATIONS-LANDLORD-TENANT-RUNTIME-AUDIT-01",
        "prior_classification": "PARTIAL",
        "classification": clf,
        "secondary_flags": flags,
        "blockers": blockers,
        "checklist": results,
        "delivery_note": delivery_note,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG, flush=True)
    today = datetime.now(timezone.utc).date()
    client_t = login_client()
    tenant_t = login_tenant()
    admin_t = login_admin()
    step_up = admin_step_up(admin_t)

    fixture = part_fixture(client_t, today)
    write_artifact("fresh_reminder_fixture_runtime.json", fixture)

    before_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    before_ids = {m.get("message_id") for m in before_logs if m.get("message_id")}

    job1 = run_rent_daily_job(admin_t, step_up)
    time.sleep(10)
    after_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")

    expect_due = (fixture.get("due_schedule") or {}).get("expected_reminder_type") or "due_today"
    due = verify_delivery(
        admin_t,
        client_t,
        fixture.get("due_ledger_id"),
        before_ids,
        after_logs,
        (expect_due,),
    )
    due["job_run_status"] = job1.status_code
    write_artifact("fresh_due_delivery_runtime.json", due)

    overdue = verify_delivery(
        admin_t,
        client_t,
        fixture.get("overdue_ledger_id"),
        before_ids,
        after_logs,
        ("overdue_3d", "overdue_7d", "overdue_14d"),
    )
    overdue["job_run_status"] = job1.status_code
    write_artifact("fresh_overdue_delivery_runtime.json", overdue)

    sent_ids = {m.get("message_id") for m in tenant_sent_logs(after_logs) if m.get("message_id")}
    job2 = run_rent_daily_job(admin_t, step_up)
    time.sleep(8)
    dup_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    new_after_dup = [m for m in tenant_sent_logs(dup_logs) if m.get("message_id") not in sent_ids and m.get("status") == "sent"]
    due_after = get_ledger(client_t, fixture.get("due_ledger_id") or "")
    overdue_after = get_ledger(client_t, fixture.get("overdue_ledger_id") or "")
    dedupe = {
        "at_utc": utc(),
        "duplicate_job_status": job2.status_code,
        "new_sent_after_duplicate": len(new_after_dup),
        "due_reminder_count": len(due_after.get("reminders") or []),
        "overdue_reminder_count": len(overdue_after.get("reminders") or []),
        "pass": job2.status_code == 200 and len(new_after_dup) == 0,
    }
    write_artifact("fresh_reminder_dedupe_runtime.json", dedupe)

    overdue_lid = fixture.get("overdue_ledger_id")
    partial_out = int((fixture.get("overdue_ledger") or {}).get("outstanding") or 118500)
    if overdue_lid and partial_out >= 3000:
        ppay = record_payment(
            client_t,
            overdue_lid,
            {
                "amount_minor": 1500,
                "payment_date": today.isoformat(),
                "reference": f"{MARKER}-partial-{uuid.uuid4().hex[:8]}",
                "note": f"{MARKER} partial copy probe",
            },
        )
        partial_detail = get_ledger(client_t, overdue_lid)
        if ROOT not in sys.path:
            sys.path.insert(0, str(ROOT))
        from services.rent_reminder_service import build_reminder_message

        msg = build_reminder_message(partial_detail, "overdue_3d")
        partial = {
            "at_utc": utc(),
            "ledger_id": overdue_lid,
            "payment_status": ppay.status_code,
            "status_after": partial_detail.get("status"),
            "outstanding_after": partial_detail.get("outstanding_balance_minor"),
            "message_claims_partial": "partial payment" in msg.lower(),
            "message_preview": msg[:280],
            "pass": ppay.status_code in (200, 201)
            and partial_detail.get("status") == "PARTIALLY_PAID"
            and "partial payment" in msg.lower(),
        }
    else:
        partial = {"pass": False, "error": "no overdue ledger for partial probe"}
    write_artifact("fresh_partial_payment_copy_runtime.json", partial)

    outstanding = int((fixture.get("overdue_ledger") or {}).get("outstanding") or 0)
    partial_paid = int(partial.get("outstanding_after") or outstanding)
    pay = record_payment(
        client_t,
        overdue_lid,
        {
            "amount_minor": partial_paid,
            "payment_date": today.isoformat(),
            "reference": f"{MARKER}-full-{uuid.uuid4().hex[:8]}",
            "note": f"{MARKER} suppression",
        },
    ) if overdue_lid and partial_paid else None
    job3 = run_rent_daily_job(admin_t, step_up)
    time.sleep(8)
    suppress_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    paid_detail = get_ledger(client_t, overdue_lid) if overdue_lid else {}
    new_after_paid = [
        m
        for m in tenant_sent_logs(suppress_logs)
        if m.get("message_id") not in sent_ids and m.get("status") == "sent" and overdue_lid and overdue_lid[:8] in json.dumps(m)
    ]
    suppression = {
        "at_utc": utc(),
        "ledger_id": overdue_lid,
        "payment_status": pay.status_code if pay else None,
        "ledger_status_after": paid_detail.get("status"),
        "outstanding_after": paid_detail.get("outstanding_balance_minor"),
        "prior_reminders_retained": len(paid_detail.get("reminders") or []),
        "new_sent_after_paid": len(new_after_paid),
        "job_after_payment_status": job3.status_code,
        "pass": (pay.status_code in (200, 201) if pay else False)
        and paid_detail.get("status") == "PAID"
        and len(new_after_paid) == 0,
    }
    write_artifact("fresh_payment_suppression_runtime.json", suppression)

    due_lid = fixture.get("due_ledger_id")
    logs_all, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    blocked = req("get", "/client/operations/rent/summary", tenant_t).status_code in (401, 403)
    tenant_logs = tenant_sent_logs(logs_all)
    other = [m for m in logs_all if TENANT_EMAIL.lower() not in str(m.get("recipient", "")).lower() and m.get("status") == "sent"]
    leaked = any(tok in json.dumps(logs_all).lower() for tok in ("password", "bearer ", "api_key", "postmark_token"))
    pay_block = req(
        "post",
        f"/client/operations/rent/ledgers/{due_lid or 'rlp_probe'}/payments",
        tenant_t,
        json={"amount_minor": 100, "payment_date": today.isoformat()},
    )
    tenant = {
        "at_utc": utc(),
        "tenant_rent_api_blocked": blocked,
        "tenant_sent_log_count": len(tenant_logs),
        "non_tenant_sent_logs": len(other),
        "tenant_cannot_record_payment": pay_block.status_code in (401, 403, 404),
        "sms_sent_logs": len([m for m in logs_all if m.get("channel") == "sms" and m.get("status") == "sent"]),
        "secret_leak_detected": leaked,
        "pass": blocked and pay_block.status_code in (401, 403, 404) and not leaked and len(other) == 0,
    }
    write_artifact("fresh_tenant_targeting_runtime.json", tenant)

    regression = part_regression()
    write_artifact("fresh_reminder_regression_runtime.json", regression)

    results = {
        "fixture": fixture.get("pass") is True,
        "due_delivery": due.get("pass") is True,
        "overdue_delivery": overdue.get("pass") is True,
        "dedupe": dedupe.get("pass") is True,
        "payment_suppression": suppression.get("pass") is True,
        "partial_payment_copy": partial.get("pass") is True,
        "tenant_targeting": tenant.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    delivery_note = ""
    if due.get("created_as_manual") or overdue.get("created_as_manual"):
        delivery_note = (
            "Fresh reminder events created with delivery_status=manual — "
            "RENT_REMINDERS_LIVE_SEND not active on staging runtime; set env on Render service and re-run with new marker"
        )
    clf = classify(results, delivery_note)
    write_artifact("classifications.json", clf)

    report_path = BUNDLE / "REPORT.md"
    prior = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    appendix = [
        "",
        "---",
        "",
        f"## {PROGRAMME} ({RUN_TAG})",
        "",
        f"**Classification:** `{clf['classification']}`",
        "",
        "### Fresh event checklist",
    ]
    for k, v in results.items():
        appendix.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        appendix.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    report_path.write_text(prior.rstrip() + "\n" + "\n".join(appendix) + "\n", encoding="utf-8")

    watchlist = [
        "# Rent operations landlord-tenant watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Fresh event run tag: `{RUN_TAG}`",
        "",
        "## Fresh event checklist",
        *[f"- [{'x' if results.get(k) else ' '}] {k}" for k in results],
        "",
        "## Remaining",
    ]
    if clf["classification"] != "VERIFIED_OPERATIONALLY":
        watchlist.append("- [ ] Re-run fresh event proof if delivery blocked (template, rate limit, recipient)")
    else:
        watchlist.append("- [x] Live rent reminder delivery verified via fresh event fixture")
    watchlist.extend(
        [
            "- [ ] Tenant in-app notification surface when enabled",
            "- [ ] SMS proof only with configured safe test number",
        ]
    )
    (BUNDLE / "watchlist.md").write_text("\n".join(watchlist) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"), flush=True)
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
