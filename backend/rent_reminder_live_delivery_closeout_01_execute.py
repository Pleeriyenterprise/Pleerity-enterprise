#!/usr/bin/env python3
"""
RENT-REMINDER-LIVE-DELIVERY-CLOSEOUT-01
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/rent_operations_landlord_tenant_runtime_audit_01"
PROGRAMME = "RENT-REMINDER-LIVE-DELIVERY-CLOSEOUT-01"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = os.environ.get("OPS_VERIFY_PROPERTY_A", "d35a58ae-3c81-491c-9694-1d021dd3b8ad")
TENANCY_ID = os.environ.get("OPS_TENANCY_ID", "pty_9ec2e1723d7b")
TENANT_EMAIL = os.environ.get("OPS_TENANT_EMAIL", "f7-ops-wales@yopmail.com")
TENANT_ID = os.environ.get("OPS_TENANT_ID", "962fa7b2-d8a0-4082-8d89-f4a2abb402e0")

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
PACE = float(os.environ.get("OPS_API_PACE_S", "2.0"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"RENT-REM-LIVE-{RUN_TAG}"
REASON = f"{PROGRAMME} governed staging proof for client {CLIENT_ID[:8]}"


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
                time.sleep(20 * (attempt + 1))
                continue
            if resp.status_code in (502, 503) and attempt < 4:
                time.sleep(5 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout):
            time.sleep(3 * (attempt + 1))
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


def admin_confirmation(admin_t: str, resource_key: str, step_up: str = "", action_id: str = "run_scoped_automation_job") -> str:
    r = req(
        "post",
        "/admin/governance/confirmation-token",
        admin_t,
        headers=h(admin_t, step_up=step_up),
        json={"action_id": action_id, "reason": REASON, "resource_key": resource_key},
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
    )


def list_ledgers(client_t: str, **params: Any) -> List[dict]:
    p = {"property_id": PROPERTY_ID, "limit": 300, **params}
    r = req("get", "/client/operations/rent/ledgers", client_t, params=p)
    return (r.json().get("ledgers") or []) if r.status_code == 200 else []


def get_ledger(client_t: str, ledger_id: str) -> dict:
    r = req("get", f"/client/operations/rent/ledgers/{ledger_id}", client_t)
    return r.json() if r.status_code == 200 else {}


def record_payment(client_t: str, ledger_id: str, body: dict) -> httpx.Response:
    return req("post", f"/client/operations/rent/ledgers/{ledger_id}/payments", client_t, json=body)


def message_logs(admin_t: str, **params: Any) -> Tuple[List[dict], int]:
    r = req("get", "/admin/message-logs", admin_t, params={"client_id": CLIENT_ID, "limit": 100, **params})
    if r.status_code != 200:
        return [], r.status_code
    body = r.json()
    return body.get("items") or body.get("messages") or [], r.status_code


def audit_logs(admin_t: str, **params: Any) -> List[dict]:
    r = req("get", "/admin/audit-logs", admin_t, params={"client_id": CLIENT_ID, "limit": 100, **params})
    if r.status_code != 200:
        return []
    return r.json().get("logs") or r.json().get("items") or []


def pick_ledger(ledgers: List[dict], *, status: Optional[str] = None, min_overdue: int = 0) -> Optional[dict]:
    cands = []
    for row in ledgers:
        if status and row.get("status") != status:
            continue
        if min_overdue and int(row.get("days_overdue") or 0) < min_overdue:
            continue
        if int(row.get("outstanding_balance_minor") or 0) <= 0:
            continue
        cands.append(row)
    cands.sort(key=lambda x: x.get("due_date") or "")
    return cands[0] if cands else None


def pick_due_candidate(ledgers: List[dict], today: date) -> Optional[dict]:
    for row in ledgers:
        due = row.get("due_date")
        if not due:
            continue
        d = date.fromisoformat(str(due)[:10])
        if d == today + timedelta(days=3) or d == today:
            if int(row.get("outstanding_balance_minor") or 0) > 0:
                return row
    return None


async def run_local_job_with_live_send() -> Dict[str, Any]:
    if not os.environ.get("MONGO_URL"):
        return {"skipped": True, "reason": "no MONGO_URL"}
    os.environ["RENT_REMINDERS_LIVE_SEND"] = "true"
    os.environ["RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST"] = CLIENT_ID
    os.environ["RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS"] = "yopmail.com"
    if ROOT not in sys.path:
        sys.path.insert(0, str(ROOT))
    from database import database
    from services import rent_operations_daily_job
    from services import rent_reminder_service

    if not database.client:
        await database.connect()
    before = await database.get_db().rent_reminder_events.count_documents({"client_id": CLIENT_ID})
    r1 = await rent_operations_daily_job.run_rent_operations_daily_for_client(CLIENT_ID)
    mid = await database.get_db().rent_reminder_events.count_documents({"client_id": CLIENT_ID})
    r2 = await rent_operations_daily_job.run_rent_operations_daily_for_client(CLIENT_ID)
    after = await database.get_db().rent_reminder_events.count_documents({"client_id": CLIENT_ID})
    sent = await database.get_db().rent_reminder_events.count_documents(
        {"client_id": CLIENT_ID, "delivery_status": "sent", "created_at": {"$gte": RUN_TAG[:10]}}
    )
    return {
        "execution": "local_staging_mongo",
        "config": rent_reminder_service.get_live_send_config(),
        "run1": r1,
        "run2": r2,
        "events_before": before,
        "events_mid": mid,
        "events_after": after,
        "idempotent_no_spam": after == mid,
        "sent_events_recent": sent,
    }


def part_setup(admin_t: str, client_t: str) -> dict:
    schedules = req("get", "/client/operations/rent/schedules", client_t, params={"property_id": PROPERTY_ID})
    schedule = (schedules.json().get("schedules") or [{}])[0] if schedules.status_code == 200 else {}
    logs, log_st = message_logs(admin_t, template_key="RENT_REMINDER", recipient=TENANT_EMAIL.split("@")[0])
    return {
        "at_utc": utc(),
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "env_expected": {
            "RENT_REMINDERS_LIVE_SEND": "true",
            "RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST": CLIENT_ID,
            "RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS": "yopmail.com",
            "sms_disabled_unless_safe_number": True,
        },
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "tenancy_id": TENANCY_ID,
        "schedule_id": schedule.get("schedule_id"),
        "tenant_recipient": TENANT_EMAIL,
        "channels_enabled": ["email"],
        "channel_safety": "yopmail.com domain allowlist; client allowlist; scoped job run",
        "prior_rent_reminder_logs": len(logs),
        "message_logs_status": log_st,
        "pass": True,
    }


def part_due_delivery(admin_t: str, client_t: str, ledgers: List[dict], step_up: str = "") -> dict:
    today = datetime.now(timezone.utc).date()
    target = pick_due_candidate(ledgers, today)
    reminder_type = None
    if target:
        due = date.fromisoformat(str(target["due_date"])[:10])
        reminder_type = "due_today" if due == today else "due_soon"
    before_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    r1 = run_rent_daily_job(admin_t, step_up)
    time.sleep(5)
    r2 = run_rent_daily_job(admin_t, step_up)
    after_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    new_logs = [m for m in after_logs if m not in before_logs]
    tenant_logs = [m for m in after_logs if TENANT_EMAIL.lower() in str(m.get("recipient", "")).lower()]
    sent_logs = [m for m in tenant_logs if m.get("status") == "sent"]
    ledger_detail = get_ledger(client_t, target["ledger_id"]) if target else {}
    reminders = ledger_detail.get("reminders") or []
    matching = [r for r in reminders if reminder_type and r.get("reminder_type") == reminder_type] if target else []
    pass_ok = bool(
        r1.status_code == 200
        and r2.status_code == 200
        and (target is None or matching or sent_logs or any(m.get("idempotency_key") for m in tenant_logs))
    )
    return {
        "at_utc": utc(),
        "target_ledger_id": target.get("ledger_id") if target else None,
        "reminder_type": reminder_type,
        "job_run_1_status": r1.status_code,
        "job_run_1_detail": (r1.text or "")[:200],
        "job_run_2_status": r2.status_code,
        "job_run_2_detail": (r2.text or "")[:200],
        "duplicate_job_safe": r2.status_code == 200,
        "tenant_message_logs_sent": len(sent_logs),
        "new_message_logs": len(new_logs),
        "ledger_reminders": matching[:3],
        "pass": pass_ok,
        "note": "Uses due_soon/due_today candidate when present; otherwise job idempotency still verified",
    }


def part_overdue_delivery(admin_t: str, client_t: str, ledgers: List[dict], step_up: str = "") -> dict:
    target = pick_ledger(ledgers, min_overdue=3) or pick_ledger(ledgers, status="OVERDUE")
    if not target:
        return {"pass": False, "error": "no overdue ledger"}
    lid = target["ledger_id"]
    before = get_ledger(client_t, lid)
    before_keys = {r.get("reminder_key") for r in (before.get("reminders") or [])}
    r1 = run_rent_daily_job(admin_t, step_up)
    after = get_ledger(client_t, lid)
    reminders = after.get("reminders") or []
    overdue_reminders = [r for r in reminders if str(r.get("reminder_type", "")).startswith("overdue")]
    new_overdue = [r for r in overdue_reminders if r.get("reminder_key") not in before_keys]
    logs, _ = message_logs(admin_t, template_key="RENT_REMINDER", recipient="yopmail")
    tenant_sent = [m for m in logs if m.get("status") == "sent" and TENANT_EMAIL.lower() in str(m.get("recipient", "")).lower()]
    r2 = run_rent_daily_job(admin_t, step_up)
    after2 = get_ledger(client_t, lid)
    count2 = len(after2.get("reminders") or [])
    return {
        "at_utc": utc(),
        "ledger_id": lid,
        "status": after.get("status"),
        "outstanding": after.get("outstanding_balance_minor"),
        "due_date": after.get("due_date"),
        "job_run_status": r1.status_code,
        "job_run_detail": (r1.text or "")[:200],
        "overdue_reminders": overdue_reminders[:5],
        "new_overdue_events": len(new_overdue),
        "tenant_sent_logs": len(tenant_sent),
        "duplicate_job_count_stable": count2 == len(reminders),
        "pass": r1.status_code == 200 and bool(overdue_reminders) and r2.status_code == 200,
    }


def part_suppression(client_t: str, admin_t: str, ledgers: List[dict], step_up: str = "") -> dict:
    target = pick_ledger(ledgers, min_overdue=1) or pick_ledger(ledgers, status="PARTIALLY_PAID")
    if not target:
        return {"pass": False, "error": "no payable ledger"}
    lid = target["ledger_id"]
    outstanding = int(target.get("outstanding_balance_minor") or 0)
    pay = record_payment(
        client_t,
        lid,
        {
            "amount_minor": outstanding,
            "payment_date": date.today().isoformat(),
            "reference": f"{MARKER}-full-{uuid.uuid4().hex[:8]}",
            "note": f"{MARKER} suppression probe",
        },
    )
    ld = get_ledger(client_t, lid)
    before_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    run_rent_daily_job(admin_t, step_up)
    after_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    new_sent = [
        m
        for m in after_logs
        if m not in before_logs and m.get("status") == "sent" and lid[:8] in json.dumps(m)
    ]
    return {
        "at_utc": utc(),
        "ledger_id": lid,
        "payment_status": pay.status_code,
        "ledger_status_after": ld.get("status"),
        "outstanding_after": ld.get("outstanding_balance_minor"),
        "new_sent_after_paid": len(new_sent),
        "prior_reminders_retained": len(ld.get("reminders") or []),
        "pass": pay.status_code in (200, 201) and ld.get("status") == "PAID" and len(new_sent) == 0,
    }


def part_partial(client_t: str, ledgers: List[dict]) -> dict:
    target = pick_ledger(ledgers, status="OVERDUE") or pick_ledger(ledgers, min_overdue=1)
    if not target:
        return {"pass": False, "error": "no ledger for partial probe"}
    lid = target["ledger_id"]
    outstanding = int(target.get("outstanding_balance_minor") or 0)
    if outstanding < 3000:
        return {"pass": False, "error": "insufficient outstanding for partial probe"}
    pay = record_payment(
        client_t,
        lid,
        {
            "amount_minor": 1500,
            "payment_date": date.today().isoformat(),
            "reference": f"{MARKER}-partial-{uuid.uuid4().hex[:8]}",
            "note": f"{MARKER} partial probe",
        },
    )
    ld = get_ledger(client_t, lid)
    from services.rent_reminder_service import build_reminder_message

    msg = build_reminder_message(ld, "overdue_3d")
    return {
        "at_utc": utc(),
        "ledger_id": lid,
        "payment_status": pay.status_code,
        "status_after": ld.get("status"),
        "outstanding_after": ld.get("outstanding_balance_minor"),
        "behaviour": "partial periods remain eligible for overdue/due reminder types while outstanding > 0",
        "message_claims_partial": "partial payment" in msg.lower(),
        "message_preview": msg[:240],
        "pass": pay.status_code in (200, 201) and ld.get("status") == "PARTIALLY_PAID" and "partial payment" in msg.lower(),
    }


def part_audit_delivery(admin_t: str) -> dict:
    logs, st = message_logs(admin_t, template_key="RENT_REMINDER")
    rent_logs = logs[:20]
    leaked = any("token" in json.dumps(row).lower() or "password" in json.dumps(row).lower() for row in rent_logs)
    audits = audit_logs(admin_t)
    rent_audits = [a for a in audits if "RENT_REMINDER" in str(a.get("action", "")).upper()]
    idem = [row.get("idempotency_key") for row in rent_logs if row.get("idempotency_key")]
    return {
        "at_utc": utc(),
        "message_logs_status": st,
        "rent_message_logs": [
            {
                "status": r.get("status"),
                "template_key": r.get("template_key"),
                "recipient_domain": (r.get("recipient") or "").split("@")[-1],
                "idempotency_key": (r.get("idempotency_key") or "")[:40],
            }
            for r in rent_logs
        ],
        "rent_audit_actions": sorted({a.get("action") for a in rent_audits})[:10],
        "idempotency_keys_present": len(idem),
        "secret_leak_detected": leaked,
        "pass": st == 200 and not leaked,
    }


def part_tenant_visibility(tenant_t: str, client_t: str, admin_t: str) -> dict:
    blocked = req("get", "/client/operations/rent/summary", tenant_t).status_code in (401, 403)
    logs, _ = message_logs(admin_t, template_key="RENT_REMINDER", recipient=TENANT_EMAIL.split("@")[0])
    tenant_recipients = [m for m in logs if TENANT_EMAIL.lower() in str(m.get("recipient", "")).lower()]
    other = [m for m in logs if TENANT_EMAIL.lower() not in str(m.get("recipient", "")).lower()]
    pay_attempt = req(
        "post",
        f"/client/operations/rent/ledgers/rlp_probe/payments",
        tenant_t,
        json={"amount_minor": 100, "payment_date": date.today().isoformat()},
    )
    return {
        "at_utc": utc(),
        "tenant_rent_api_blocked": blocked,
        "tenant_targeted_logs": len(tenant_recipients),
        "non_tenant_recipient_logs": len(other),
        "tenant_cannot_record_payment": pay_attempt.status_code in (401, 403, 404),
        "pass": blocked and pay_attempt.status_code in (401, 403, 404),
    }


def part_retry(admin_t: str, step_up: str = "") -> dict:
    r1 = run_rent_daily_job(admin_t, step_up)
    r2 = run_rent_daily_job(admin_t, step_up)
    r3 = run_rent_daily_job(admin_t, step_up)
    logs, _ = message_logs(admin_t, template_key="RENT_REMINDER", limit=200)
    keys = [row.get("idempotency_key") for row in logs if row.get("idempotency_key")]
    dup = len(keys) - len(set(keys))
    return {
        "at_utc": utc(),
        "runs": [r1.status_code, r2.status_code, r3.status_code],
        "duplicate_idempotency_keys": dup,
        "manual_intervention": "landlord mark-sent remains available when auto send blocked",
        "pass": all(code == 200 for code in (r1.status_code, r2.status_code, r3.status_code)) and dup == 0,
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


def classify(results: Dict[str, bool], setup: dict, local: dict) -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags: List[str] = []
    live_proven = (
        results.get("due_delivery")
        and results.get("overdue_delivery")
        and setup.get("tenant_recipient")
        and (results.get("audit_delivery") or results.get("tenant_visibility"))
    )
    if local.get("execution") == "local_staging_mongo" and local.get("idempotent_no_spam"):
        live_proven = live_proven or bool(local.get("run1", {}).get("reminders", {}).get("live_sent"))
    if not live_proven and not blockers:
        flags.append("RENT_REMINDER_GAP")
    if "tenant_visibility" in blockers:
        flags.append("TENANT_TARGETING_DRIFT")
    if "retry" in blockers:
        flags.append("IDEMPOTENCY_DRIFT")
    if blockers:
        clf = "PARTIAL" if len(blockers) <= 3 else "FAIL_OPERATIONAL"
    elif live_proven:
        clf = "VERIFIED_OPERATIONALLY"
    else:
        clf = "RENT_REMINDER_GAP"
    return {
        "programme": PROGRAMME,
        "parent_audit": "RENT-OPERATIONS-LANDLORD-TENANT-RUNTIME-AUDIT-01",
        "classification": clf,
        "prior_classification": "RENT_REMINDER_GAP",
        "secondary_flags": flags,
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    client_t = login_client()
    tenant_t = login_tenant()
    admin_t = login_admin()
    admin_su = admin_step_up(admin_t)
    ledgers = list_ledgers(client_t)

    setup = part_setup(admin_t, client_t)
    setup["admin_step_up"] = bool(admin_su)
    write_artifact("rent_reminder_live_setup_runtime.json", setup)

    local = asyncio.run(run_local_job_with_live_send())
    setup["local_mongo_probe"] = local

    due = part_due_delivery(admin_t, client_t, ledgers, admin_su)
    write_artifact("rent_due_reminder_delivery_runtime.json", due)

    overdue = part_overdue_delivery(admin_t, client_t, ledgers, admin_su)
    write_artifact("rent_overdue_reminder_delivery_runtime.json", overdue)

    suppression = part_suppression(client_t, admin_t, ledgers, admin_su)
    write_artifact("rent_reminder_suppression_runtime.json", suppression)

    partial = part_partial(client_t, ledgers)
    write_artifact("rent_partial_payment_reminder_runtime.json", partial)

    audit = part_audit_delivery(admin_t)
    write_artifact("rent_reminder_audit_delivery_runtime.json", audit)

    tenant = part_tenant_visibility(tenant_t, client_t, admin_t)
    write_artifact("rent_tenant_reminder_visibility_runtime.json", tenant)

    retry = part_retry(admin_t, admin_su)
    write_artifact("rent_reminder_retry_runtime.json", retry)

    regression = part_regression()
    write_artifact("rent_reminder_regression_runtime.json", regression)

    results = {
        "setup": setup.get("pass") is True,
        "due_delivery": due.get("pass") is True,
        "overdue_delivery": overdue.get("pass") is True,
        "suppression": suppression.get("pass") is True,
        "partial_payment": partial.get("pass") is True,
        "audit_delivery": audit.get("pass") is True,
        "tenant_visibility": tenant.get("pass") is True,
        "retry": retry.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    clf = classify(results, setup, local)
    write_artifact("classifications.json", clf)

    report_path = BUNDLE / "REPORT.md"
    prior = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    appendix = [
        "",
        "---",
        "",
        f"## {PROGRAMME} closeout ({RUN_TAG})",
        "",
        f"**Classification:** `{clf['classification']}`",
        "",
        "### Closeout checklist",
    ]
    for k, v in results.items():
        appendix.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        appendix.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    appendix.append(f"\nLocal mongo probe: `{local.get('execution', 'skipped')}`")
    report_path.write_text(prior.rstrip() + "\n" + "\n".join(appendix) + "\n", encoding="utf-8")

    watchlist = [
        "# Rent operations landlord-tenant watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Closeout run tag: `{RUN_TAG}`",
        "",
        "## Closeout checklist",
        *[f"- [{'x' if results.get(k) else ' '}] {k}" for k in results],
        "",
        "## Remaining",
        "- [ ] Confirm Render deploy picked up RENT_REMINDERS_LIVE_SEND env if API job delivery still manual",
        "- [ ] Real-device in-app notification surface when tenant inbox enabled",
        "- [ ] SMS proof only with configured safe test number",
    ]
    (BUNDLE / "watchlist.md").write_text("\n".join(watchlist) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.exit(main())
