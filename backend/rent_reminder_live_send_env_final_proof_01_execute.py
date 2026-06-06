#!/usr/bin/env python3
"""
RENT-REMINDER-LIVE-SEND-ENV-FINAL-PROOF-01
Prove live rent reminder delivery after Render env activation.
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
PROGRAMME = "RENT-REMINDER-LIVE-SEND-ENV-FINAL-PROOF-01"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = os.environ.get("OPS_VERIFY_PROPERTY_A", "d35a58ae-3c81-491c-9694-1d021dd3b8ad")
TENANCY_ID = os.environ.get("OPS_TENANCY_ID", "pty_9ec2e1723d7b")
TENANT_EMAIL = os.environ.get("OPS_TENANT_EMAIL", "f7-ops-wales@yopmail.com")

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
BASE = API[:-4] if API.endswith("/api") else _raw_api
PACE = float(os.environ.get("OPS_API_PACE_S", "2.5"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"RENT-LIVE-ENV-{RUN_TAG}"
REASON = f"{PROGRAMME} live send final proof for client {CLIENT_ID[:8]}"
DUE_SOON_DAYS = 3

CODE_ENV = {
    "RENT_REMINDERS_LIVE_SEND": "true",
    "RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST": CLIENT_ID,
    "RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS": "yopmail.com",
    "SMS_ENABLED": "false (absent or false)",
}


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
        detail = get_ledger(client_t, row["ledger_id"])
        if detail.get("reminders"):
            continue
        return detail
    return None


def create_fixtures(client_t: str, today: date) -> dict:
    overdue_start = (today - timedelta(days=100)).replace(day=1)
    overdue_sched, overdue_st = create_schedule(
        client_t,
        {
            "property_id": PROPERTY_ID,
            "tenancy_id": TENANCY_ID,
            "expected_amount_minor": 119900,
            "due_day": 1,
            "start_date": overdue_start.isoformat(),
            "rent_frequency": "monthly",
            "tenant_name": "mat",
            "notes": f"{MARKER} overdue",
            "idempotency_key": f"{MARKER}-overdue",
        },
    )
    due_params, expect_type = due_schedule_params(today)
    due_sched, due_st = create_schedule(
        client_t,
        {
            "property_id": PROPERTY_ID,
            "tenancy_id": TENANCY_ID,
            "expected_amount_minor": 126500,
            "rent_frequency": "monthly",
            "tenant_name": "mat",
            "notes": f"{MARKER} due",
            "idempotency_key": f"{MARKER}-due",
            **due_params,
        },
    )
    ledgers = list_ledgers(client_t)
    due_match = today if expect_type == "due_today" else today + timedelta(days=DUE_SOON_DAYS)
    due_ledger = find_fresh_ledger(client_t, ledgers, schedule_id=due_sched.get("schedule_id"), due_match=due_match)
    if not due_ledger:
        due_ledger = find_fresh_ledger(client_t, ledgers, schedule_id=due_sched.get("schedule_id"))
    overdue_ledger = find_fresh_ledger(
        client_t, ledgers, schedule_id=overdue_sched.get("schedule_id"), min_overdue=3
    )
    return {
        "overdue_schedule_id": overdue_sched.get("schedule_id"),
        "due_schedule_id": due_sched.get("schedule_id"),
        "expected_due_type": expect_type,
        "due_ledger_id": due_ledger.get("ledger_id") if due_ledger else None,
        "overdue_ledger_id": overdue_ledger.get("ledger_id") if overdue_ledger else None,
        "due_ledger": due_ledger,
        "overdue_ledger": overdue_ledger,
        "schedule_status": {"overdue": overdue_st, "due": due_st},
        "pass": bool(due_ledger and overdue_ledger and overdue_st in (200, 201) and due_st in (200, 201)),
    }


def verify_send(
    admin_t: str,
    client_t: str,
    ledger_id: Optional[str],
    before_ids: Set[str],
    logs: List[dict],
    expect_types: Tuple[str, ...],
) -> dict:
    detail = get_ledger(client_t, ledger_id) if ledger_id else {}
    reminders = detail.get("reminders") or []
    matching = [
        r
        for r in reminders
        if r.get("reminder_type") in expect_types or str(r.get("reminder_type", "")).startswith("overdue")
    ]
    sent_events = [r for r in matching if r.get("delivery_status") == "sent"]
    new_sent = [m for m in tenant_sent_logs(logs) if m.get("message_id") not in before_ids]
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
        "at_utc": utc(),
        "ledger_id": ledger_id,
        "ledger_due_date": detail.get("due_date"),
        "ledger_outstanding": detail.get("outstanding_balance_minor"),
        "reminder_events": [
            {
                "reminder_type": r.get("reminder_type"),
                "delivery_status": r.get("delivery_status"),
                "recipient_email": r.get("recipient_email"),
                "reminder_key": r.get("reminder_key"),
            }
            for r in matching[:5]
        ],
        "sent_events_count": len(sent_events),
        "created_as_manual": bool(matching) and all(r.get("delivery_status") == "manual" for r in matching),
        "tenant_sent_logs": [sanitize_log(m) for m in new_sent[:5]],
        "message_detail": {
            "status": detail_log.get("status"),
            "template_key": detail_log.get("template_key"),
            "recipient": detail_log.get("recipient"),
            "subject": (detail_log.get("subject") or "")[:160],
            "body_preview": (detail_log.get("body") or "")[:240],
        },
        "content_accurate": content_ok,
        "non_tenant_sent": len([m for m in logs if m.get("status") == "sent" and TENANT_EMAIL.lower() not in str(m.get("recipient", "")).lower()]),
        "pass": bool(sent_events)
        and any(m.get("status") == "sent" for m in new_sent)
        and detail_log.get("template_key") == "RENT_REMINDER",
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


def classify(results: Dict[str, bool], note: str = "") -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags: List[str] = []
    if blockers:
        if "env_proof" in blockers or "due_live_send" in blockers or "overdue_live_send" in blockers:
            flags.append("RENT_REMINDER_GAP")
        if "due_live_send" in blockers or "overdue_live_send" in blockers:
            flags.append("DELIVERY_DRIFT")
        if "dedupe" in blockers:
            flags.append("IDEMPOTENCY_DRIFT")
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
        "note": note,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG, flush=True)
    today = datetime.now(timezone.utc).date()
    ver = httpx.get(f"{BASE}/api/version", timeout=120)
    ver_body = ver.json() if ver.status_code == 200 else {}
    commit_sha = (ver_body.get("commit_sha") or "").strip()

    client_t = login_client()
    tenant_t = login_tenant()
    admin_t = login_admin()
    step_up = admin_step_up(admin_t)

    fixture = create_fixtures(client_t, today)
    before_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    before_ids = {m.get("message_id") for m in before_logs if m.get("message_id")}

    job1 = run_rent_daily_job(admin_t, step_up)
    time.sleep(12)
    after_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")

    expect_due = fixture.get("expected_due_type") or "due_today"
    due = verify_send(admin_t, client_t, fixture.get("due_ledger_id"), before_ids, after_logs, (expect_due,))
    due["job_run_status"] = job1.status_code
    write_artifact("rent_due_live_send_final_runtime.json", due)

    overdue = verify_send(
        admin_t,
        client_t,
        fixture.get("overdue_ledger_id"),
        before_ids,
        after_logs,
        ("overdue_3d", "overdue_7d", "overdue_14d"),
    )
    overdue["job_run_status"] = job1.status_code
    write_artifact("rent_overdue_live_send_final_runtime.json", overdue)

    live_active = not due.get("created_as_manual") and not overdue.get("created_as_manual") and (
        due.get("sent_events_count", 0) > 0 or overdue.get("sent_events_count", 0) > 0
    )
    sms_sent = len([m for m in after_logs if m.get("channel") == "sms" and m.get("status") == "sent"])
    tenant_blocked = req("get", "/client/operations/rent/summary", tenant_t).status_code in (401, 403)
    env_proof = {
        "at_utc": utc(),
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "commit_sha": commit_sha,
        "environment": ver_body.get("environment"),
        "code_env_expected": CODE_ENV,
        "render_aliases_note": {
            "RENT_REMINDERS_LIVE_CLIENT_ALLOWLIST": "use RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST in code",
            "RENT_REMINDERS_SAFE_EMAIL_DOMAINS": "use RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS in code",
            "RENT_REMINDERS_SMS_ENABLED": "use SMS_ENABLED=false or unset in code",
        },
        "client_id": CLIENT_ID,
        "tenant_recipient": TENANT_EMAIL,
        "fixture": {
            "due_ledger_id": fixture.get("due_ledger_id"),
            "overdue_ledger_id": fixture.get("overdue_ledger_id"),
            "due_schedule_id": fixture.get("due_schedule_id"),
            "overdue_schedule_id": fixture.get("overdue_schedule_id"),
        },
        "job_run_1_status": job1.status_code,
        "job_run_1_detail": (job1.text or "")[:300],
        "live_send_inferred_active": live_active,
        "sms_sent_logs": sms_sent,
        "tenant_api_blocked": tenant_blocked,
        "prior_message_logs": len(before_logs),
        "after_message_logs": len(after_logs),
        "tenant_sent_after_job": len(tenant_sent_logs(after_logs)),
        "pass": fixture.get("pass") and live_active and job1.status_code == 200 and sms_sent == 0,
    }
    write_artifact("rent_reminder_live_env_final_runtime.json", env_proof)

    sent_ids = {m.get("message_id") for m in tenant_sent_logs(after_logs) if m.get("message_id")}
    job2 = run_rent_daily_job(admin_t, step_up)
    time.sleep(8)
    dup_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    new_dup = [m for m in tenant_sent_logs(dup_logs) if m.get("message_id") not in sent_ids and m.get("status") == "sent"]
    keys = [m.get("idempotency_key") for m in dup_logs if m.get("idempotency_key")]
    dedupe = {
        "at_utc": utc(),
        "duplicate_job_status": job2.status_code,
        "new_sent_after_duplicate": len(new_dup),
        "duplicate_idempotency_keys": len(keys) - len(set(keys)),
        "message_log_count_before": len(after_logs),
        "message_log_count_after": len(dup_logs),
        "pass": job2.status_code == 200 and len(new_dup) == 0,
    }
    write_artifact("rent_live_send_dedupe_final_runtime.json", dedupe)

    overdue_lid = fixture.get("overdue_ledger_id")
    outstanding = int((fixture.get("overdue_ledger") or {}).get("outstanding_balance_minor") or 0)
    pay = record_payment(
        client_t,
        overdue_lid,
        {
            "amount_minor": outstanding,
            "payment_date": today.isoformat(),
            "reference": f"{MARKER}-paid-{uuid.uuid4().hex[:8]}",
            "note": f"{MARKER} suppression",
        },
    ) if overdue_lid and outstanding else None
    job3 = run_rent_daily_job(admin_t, step_up)
    time.sleep(8)
    paid_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    paid_detail = get_ledger(client_t, overdue_lid) if overdue_lid else {}
    new_after_paid = [
        m
        for m in tenant_sent_logs(paid_logs)
        if m.get("message_id") not in sent_ids and m.get("status") == "sent"
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
    write_artifact("rent_live_send_payment_suppression_final_runtime.json", suppression)

    regression = part_regression()
    write_artifact("rent_live_send_final_regression_runtime.json", regression)

    note = ""
    if due.get("created_as_manual") or overdue.get("created_as_manual"):
        note = "Events still manual — verify Render env uses code keys: RENT_REMINDERS_LIVE_SEND, RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST, RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS"

    results = {
        "env_proof": env_proof.get("pass") is True,
        "due_live_send": due.get("pass") is True,
        "overdue_live_send": overdue.get("pass") is True,
        "dedupe": dedupe.get("pass") is True,
        "payment_suppression": suppression.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    clf = classify(results, note)
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
        "### Live-send final checklist",
    ]
    for k, v in results.items():
        appendix.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        appendix.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    if note:
        appendix.append(f"\n**Note:** {note}")
    report_path.write_text(prior.rstrip() + "\n" + "\n".join(appendix) + "\n", encoding="utf-8")

    watchlist = [
        "# Rent operations landlord-tenant watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Live-send final run tag: `{RUN_TAG}`",
        "",
        "## Live-send final checklist",
        *[f"- [{'x' if results.get(k) else ' '}] {k}" for k in results],
        "",
        "## Remaining",
    ]
    if clf["classification"] == "VERIFIED_OPERATIONALLY":
        watchlist.append("- [x] Live rent reminder email delivery verified on staging")
    else:
        watchlist.extend(
            [
                "- [ ] Set Render env: RENT_REMINDERS_LIVE_SEND=true",
                "- [ ] RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST=6fd5ac4c-3fd4-4112-ade7-156977deb49f",
                "- [ ] RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS=yopmail.com",
                "- [ ] SMS_ENABLED unset or false; redeploy; re-run harness",
            ]
        )
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
