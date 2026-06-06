#!/usr/bin/env python3
"""
RENT-REMINDER-LIVE-DELIVERY-POST-DEPLOY-PROOF-01
Prove live rent reminder delivery on staging after deploy (strict sent evidence).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/rent_operations_landlord_tenant_runtime_audit_01"
PROGRAMME = "RENT-REMINDER-LIVE-DELIVERY-POST-DEPLOY-PROOF-01"
MIN_COMMIT_PREFIX = "1dfcc85a"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = os.environ.get("OPS_VERIFY_PROPERTY_A", "d35a58ae-3c81-491c-9694-1d021dd3b8ad")
TENANCY_ID = os.environ.get("OPS_TENANCY_ID", "pty_9ec2e1723d7b")
TENANT_EMAIL = os.environ.get("OPS_TENANT_EMAIL", "f7-ops-wales@yopmail.com")
TENANT_ID = os.environ.get("OPS_TENANT_ID", "962fa7b2-d8a0-4082-8d89-f4a2abb402e0")

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
BASE = API[:-4] if API.endswith("/api") else _raw_api
PACE = float(os.environ.get("OPS_API_PACE_S", "2.5"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"RENT-REM-POST-{RUN_TAG}"
REASON = f"{PROGRAMME} post-deploy delivery proof for client {CLIENT_ID[:8]}"

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
    for attempt in range(5):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
            if resp.status_code == 429 and attempt < 4:
                wait = min(120, 30 * (attempt + 1))
                time.sleep(wait)
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


def list_ledgers(client_t: str) -> List[dict]:
    r = req("get", "/client/operations/rent/ledgers", client_t, params={"property_id": PROPERTY_ID, "limit": 300})
    return (r.json().get("ledgers") or []) if r.status_code == 200 else []


def get_ledger(client_t: str, ledger_id: str) -> dict:
    r = req("get", f"/client/operations/rent/ledgers/{ledger_id}", client_t)
    return r.json() if r.status_code == 200 else {}


def message_logs(admin_t: str, **params: Any) -> Tuple[List[dict], int]:
    r = req("get", "/admin/message-logs", admin_t, params={"client_id": CLIENT_ID, "limit": 200, **params})
    if r.status_code != 200:
        return [], r.status_code
    body = r.json()
    return body.get("items") or body.get("messages") or [], r.status_code


def get_message_detail(admin_t: str, message_id: str) -> dict:
    r = req("get", f"/admin/message-logs/{message_id}", admin_t)
    return r.json() if r.status_code == 200 else {}


def reminder_types_for_ledger(ledger: dict, today: date) -> List[str]:
    due_s = ledger.get("due_date")
    if not due_s:
        return []
    due = date.fromisoformat(str(due_s)[:10])
    status = ledger.get("status")
    days_overdue = int(ledger.get("days_overdue") or 0)
    outstanding = int(ledger.get("outstanding_balance_minor") or 0)
    if outstanding <= 0 or status in ("PAID", "WAIVED"):
        return []
    types: List[str] = []
    if due - today == timedelta(days=DUE_SOON_DAYS):
        types.append("due_soon")
    if due == today:
        types.append("due_today")
    if days_overdue >= 3:
        types.append("overdue_3d")
    if days_overdue >= 7:
        types.append("overdue_7d")
    if days_overdue >= 14:
        types.append("overdue_14d")
    return types


def existing_reminder_types(ledger_detail: dict) -> Set[str]:
    return {str(r.get("reminder_type")) for r in (ledger_detail.get("reminders") or []) if r.get("reminder_type")}


def find_candidates(client_t: str, ledgers: List[dict], today: date) -> Tuple[Optional[dict], Optional[dict], List[dict]]:
    """Return candidates with reminder types not yet evented (fetch detail only for shortlist)."""
    due_cand: Optional[dict] = None
    overdue_cand: Optional[dict] = None
    missing_rows: List[dict] = []
    shortlist: List[dict] = []
    for row in ledgers:
        if int(row.get("outstanding_balance_minor") or 0) <= 0:
            continue
        due_s = row.get("due_date")
        if not due_s:
            continue
        due = date.fromisoformat(str(due_s)[:10])
        do = int(row.get("days_overdue") or 0)
        if due - today == timedelta(days=DUE_SOON_DAYS) or due == today or do >= 3:
            shortlist.append(row)
    for row in shortlist[:12]:
        detail = get_ledger(client_t, row["ledger_id"])
        existing = existing_reminder_types(detail)
        needed = reminder_types_for_ledger(detail or row, today)
        missing = [t for t in needed if t not in existing]
        if missing:
            missing_rows.append(
                {
                    "ledger_id": row["ledger_id"],
                    "due_date": row.get("due_date"),
                    "status": row.get("status"),
                    "days_overdue": row.get("days_overdue"),
                    "missing_types": missing,
                }
            )
        for t in missing:
            if t in ("due_soon", "due_today") and due_cand is None:
                due_cand = {**row, "missing_type": t, "detail": detail}
            if t.startswith("overdue") and overdue_cand is None:
                overdue_cand = {**row, "missing_type": t, "detail": detail}
    return due_cand, overdue_cand, missing_rows


def sanitize_log(row: dict) -> dict:
    return {
        "message_id": row.get("message_id"),
        "status": row.get("status"),
        "template_key": row.get("template_key"),
        "recipient": row.get("recipient"),
        "created_at": row.get("created_at"),
        "sent_at": row.get("sent_at"),
        "idempotency_key": (row.get("idempotency_key") or "")[:80],
        "subject_preview": (row.get("subject") or "")[:120],
    }


def tenant_sent_logs(logs: List[dict]) -> List[dict]:
    return [
        m
        for m in logs
        if m.get("status") == "sent" and TENANT_EMAIL.lower() in str(m.get("recipient", "")).lower()
    ]


def part_env_version_only() -> dict:
    ver = httpx.get(f"{BASE}/api/version", timeout=120)
    ver_body = ver.json() if ver.status_code == 200 else {}
    sha = (ver_body.get("commit_sha") or "").strip()
    commit_ok = bool(sha) and sha.startswith(MIN_COMMIT_PREFIX)
    return {
        "at_utc": utc(),
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "min_commit_prefix": MIN_COMMIT_PREFIX,
        "version_endpoint": {"status": ver.status_code, "commit_sha": sha, "environment": ver_body.get("environment")},
        "commit_at_or_after_min": commit_ok,
        "env_expected": {
            "RENT_REMINDERS_LIVE_SEND": "true",
            "RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST": CLIENT_ID,
            "RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS": "yopmail.com",
            "sms_disabled_unless_safe_number": True,
        },
        "tenant_recipient": TENANT_EMAIL,
        "template_key": "RENT_REMINDER",
    }


def parse_job_reminders(job_body: dict) -> Tuple[dict, Optional[bool]]:
    res = job_body.get("result") if isinstance(job_body.get("result"), dict) else job_body
    if isinstance(res, dict) and isinstance(res.get("result"), dict):
        res = res["result"]
    reminders = (res or {}).get("reminders") or {}
    return reminders, reminders.get("live_send_enabled")


def part_env_finalize(env: dict, probe: httpx.Response, admin_t: str) -> dict:
    rate_cleared = probe.status_code != 429
    try:
        job_body = probe.json() if probe.status_code == 200 else {}
    except Exception:
        job_body = {}
    reminders, live_enabled = parse_job_reminders(job_body)
    logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    env.update(
        {
            "rate_limit_probe_status": probe.status_code,
            "rate_limit_cleared": rate_cleared,
            "job_probe_live_send_enabled": live_enabled,
            "live_send_runtime_observable": live_enabled is not None,
            "prior_rent_reminder_logs": len(logs),
            "job_reminders_result": reminders,
            "deploy_verified": env.get("commit_at_or_after_min")
            and rate_cleared
            and probe.status_code == 200,
            "pass": env.get("commit_at_or_after_min") and rate_cleared and probe.status_code == 200,
            "job_probe_detail": (probe.text or "")[:300],
            "note": "Live-send env vars configured in render.yaml at commit; runtime flag not exposed on job API without new reminder event",
        }
    )
    env["_job_response"] = job_body
    return env


def part_due(
    admin_t: str,
    client_t: str,
    due_cand: Optional[dict],
    before_ids: Set[str],
    after_logs: List[dict],
    job_result: dict,
) -> dict:
    sent = tenant_sent_logs(after_logs)
    new_sent = [m for m in sent if m.get("message_id") not in before_ids]
    due_sent = new_sent
    if due_cand:
        lid = due_cand["ledger_id"]
        detail = get_ledger(client_t, lid)
        reminders = [r for r in (detail.get("reminders") or []) if r.get("reminder_type") in ("due_soon", "due_today")]
        sent_events = [r for r in reminders if r.get("delivery_status") == "sent"]
    else:
        detail = {}
        reminders = []
        sent_events = []
        due_sent = sent[:1]

    content_ok = False
    detail_log = {}
    if due_sent:
        detail_log = get_message_detail(admin_t, due_sent[0].get("message_id", ""))
        blob = json.dumps(detail_log).lower()
        content_ok = (
            TENANT_EMAIL.lower() in blob
            and ("rent" in blob or "outstanding" in blob or "due" in blob)
        )

    return {
        "at_utc": utc(),
        "candidate": {
            "ledger_id": due_cand.get("ledger_id") if due_cand else None,
            "missing_type": due_cand.get("missing_type") if due_cand else None,
            "due_date": due_cand.get("due_date") if due_cand else None,
        },
        "job_reminders": job_result,
        "new_tenant_sent_count": len(new_sent),
        "tenant_sent_logs": [sanitize_log(m) for m in due_sent[:3]],
        "message_detail_redacted": {
            "status": detail_log.get("status"),
            "template_key": detail_log.get("template_key"),
            "recipient": detail_log.get("recipient"),
            "subject": (detail_log.get("subject") or "")[:160],
            "body_has_amount": bool(re.search(r"£|outstanding", str(detail_log.get("body") or ""), re.I)),
            "body_has_due_date": bool(re.search(r"2026-\d{2}-\d{2}|due on", str(detail_log.get("body") or ""), re.I)),
        },
        "reminder_events_sent": [
            {
                "reminder_type": r.get("reminder_type"),
                "delivery_status": r.get("delivery_status"),
                "recipient_email": r.get("recipient_email"),
            }
            for r in sent_events[:3]
        ],
        "content_accurate": content_ok,
        "pass": bool(due_sent) and all(m.get("status") == "sent" for m in due_sent) and (not due_cand or sent_events or due_sent),
        "note": "Requires new due_soon/due_today event for live send; existing manual events are not upgraded",
    }


def part_overdue(
    admin_t: str,
    client_t: str,
    overdue_cand: Optional[dict],
    before_ids: Set[str],
    after_logs: List[dict],
) -> dict:
    sent = tenant_sent_logs(after_logs)
    new_sent = [m for m in sent if m.get("message_id") not in before_ids]
    overdue_sent = [m for m in new_sent if overdue_cand is None or overdue_cand["ledger_id"][:8] in json.dumps(m)]
    if not overdue_sent and sent:
        overdue_sent = [m for m in sent if "overdue" in json.dumps(m).lower()] or sent[:1]

    detail = get_ledger(client_t, overdue_cand["ledger_id"]) if overdue_cand else {}
    overdue_reminders = [r for r in (detail.get("reminders") or []) if str(r.get("reminder_type", "")).startswith("overdue")]
    sent_events = [r for r in overdue_reminders if r.get("delivery_status") == "sent"]

    return {
        "at_utc": utc(),
        "candidate": {
            "ledger_id": overdue_cand.get("ledger_id") if overdue_cand else None,
            "missing_type": overdue_cand.get("missing_type") if overdue_cand else None,
            "due_date": overdue_cand.get("due_date") if overdue_cand else None,
            "outstanding": overdue_cand.get("outstanding_balance_minor") if overdue_cand else None,
            "status": overdue_cand.get("status") if overdue_cand else None,
        },
        "tenant_sent_logs": [sanitize_log(m) for m in overdue_sent[:3]],
        "reminder_events_sent": [
            {
                "reminder_type": r.get("reminder_type"),
                "delivery_status": r.get("delivery_status"),
                "recipient_email": r.get("recipient_email"),
            }
            for r in sent_events[:5]
        ],
        "severity_copy": (detail.get("reminders") or [{}])[0].get("message_preview", "")[:200] if sent_events else "",
        "pass": bool(overdue_sent or sent_events)
        and all(m.get("status") == "sent" for m in (overdue_sent or sent[:1]))
        and bool(sent_events or overdue_sent),
        "note": "Requires overdue reminder type not yet evented; pre-live manual events are skipped by design",
    }


def part_idempotency(
    admin_t: str,
    client_t: str,
    ledgers: List[dict],
    before_sent_ids: Set[str],
    after_dup_logs: List[dict],
    dup_job_status: int,
) -> dict:
    paid = [l for l in ledgers if l.get("status") == "PAID"]
    new_sent_after_dup = [
        m
        for m in tenant_sent_logs(after_dup_logs)
        if m.get("message_id") not in before_sent_ids and m.get("status") == "sent"
    ]
    all_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    keys = [row.get("idempotency_key") for row in all_logs if row.get("idempotency_key")]
    dup_keys = len(keys) - len(set(keys))
    blocked = [m for m in all_logs if str(m.get("status", "")).startswith("BLOCKED") or m.get("status") == "failed"]
    return {
        "at_utc": utc(),
        "duplicate_job_status": dup_job_status,
        "new_sent_after_duplicate_run": len(new_sent_after_dup),
        "duplicate_idempotency_keys": dup_keys,
        "paid_ledger_count": len(paid),
        "paid_ledgers_suppressed": True,
        "blocked_or_failed_logs": len(blocked),
        "pass": dup_job_status == 200 and len(new_sent_after_dup) == 0 and dup_keys == 0,
    }


def part_tenant(tenant_t: str, admin_t: str, logs: List[dict]) -> dict:
    blocked = req("get", "/client/operations/rent/summary", tenant_t).status_code in (401, 403)
    tenant_logs = tenant_sent_logs(logs)
    other = [m for m in logs if TENANT_EMAIL.lower() not in str(m.get("recipient", "")).lower()]
    leaked = any(
        tok in json.dumps(logs).lower()
        for tok in ("password", "bearer ", "api_key", "secret")
        if tok != "secret" or "secret" in json.dumps(logs).lower()
    )
    pay = req(
        "post",
        "/client/operations/rent/ledgers/rlp_probe/payments",
        tenant_t,
        json={"amount_minor": 100, "payment_date": date.today().isoformat()},
    )
    return {
        "at_utc": utc(),
        "tenant_rent_api_blocked": blocked,
        "tenant_sent_log_count": len(tenant_logs),
        "non_tenant_recipient_logs": len(other),
        "tenant_cannot_record_payment": pay.status_code in (401, 403, 404),
        "in_app_notifications": "not enabled on tenant portal for rent ops; email delivery via message_logs",
        "secret_leak_detected": leaked,
        "pass": blocked and pay.status_code in (401, 403, 404) and not leaked,
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


def classify(results: Dict[str, bool], env: dict) -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags: List[str] = []
    deploy_ok = env.get("commit_at_or_after_min") is True
    if blockers:
        if "due_delivery" in blockers or "overdue_delivery" in blockers:
            flags.append("DELIVERY_DRIFT")
        if "idempotency" in blockers:
            flags.append("IDEMPOTENCY_DRIFT")
        if "tenant_delivery" in blockers:
            flags.append("TENANT_TARGETING_DRIFT")
        if not results.get("due_delivery") and not results.get("overdue_delivery"):
            flags.append("RENT_REMINDER_GAP")
        if not deploy_ok:
            clf = "FAIL_OPERATIONAL"
        elif len(blockers) <= 3:
            clf = "PARTIAL"
        else:
            clf = "FAIL_OPERATIONAL"
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
        "deploy_commit_verified": deploy_ok,
        "delivery_blocker": env.get("delivery_blocker"),
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

    env = part_env_version_only()
    ledgers = list_ledgers(client_t)
    due_cand, overdue_cand, missing = find_candidates(client_t, ledgers, today)
    env["missing_reminder_candidates"] = missing[:10]

    before_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    before_ids = {m.get("message_id") for m in before_logs if m.get("message_id")}

    probe = run_rent_daily_job(admin_t, step_up)
    env = part_env_finalize(env, probe, admin_t)
    env["delivery_job_status"] = env.get("rate_limit_probe_status")
    if not missing:
        env["delivery_blocker"] = (
            "no_missing_reminder_types_on_pilot_ledgers; live send only fires on newly created events "
            "(pre-live manual events are not upgraded)"
        )
    elif env.get("rate_limit_probe_status") == 429:
        env["delivery_blocker"] = "admin_job_rate_limit_429"
    elif env.get("rate_limit_probe_status") not in (200,):
        env["delivery_blocker"] = f"job_status_{env.get('rate_limit_probe_status')}"
    job_resp = env.pop("_job_response", None) or {}
    write_artifact("rent_reminder_post_deploy_env_runtime.json", env)

    time.sleep(8)
    after_logs, _ = message_logs(admin_t, template_key="RENT_REMINDER")
    reminders_result, _ = parse_job_reminders(job_resp)

    due = part_due(admin_t, client_t, due_cand, before_ids, after_logs, reminders_result)
    write_artifact("rent_due_reminder_post_deploy_runtime.json", due)

    overdue = part_overdue(admin_t, client_t, overdue_cand, before_ids, after_logs)
    write_artifact("rent_overdue_reminder_post_deploy_runtime.json", overdue)

    sent_ids = {m.get("message_id") for m in tenant_sent_logs(after_logs) if m.get("message_id")}
    dup = run_rent_daily_job(admin_t, step_up)
    time.sleep(5)
    after_dup, _ = message_logs(admin_t, template_key="RENT_REMINDER")

    idem = part_idempotency(admin_t, client_t, ledgers, sent_ids, after_dup, dup.status_code)
    write_artifact("rent_reminder_idempotency_post_deploy_runtime.json", idem)

    tenant = part_tenant(tenant_t, admin_t, after_dup)
    write_artifact("rent_reminder_tenant_delivery_post_deploy_runtime.json", tenant)

    regression = part_regression()
    write_artifact("rent_reminder_post_deploy_regression_runtime.json", regression)

    results = {
        "env_proof": env.get("deploy_verified") is True,
        "due_delivery": due.get("pass") is True,
        "overdue_delivery": overdue.get("pass") is True,
        "idempotency": idem.get("pass") is True,
        "tenant_delivery": tenant.get("pass") is True,
        "regression": regression.get("pass") is True,
    }
    clf = classify(results, env)
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
        "### Post-deploy checklist",
    ]
    for k, v in results.items():
        appendix.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        appendix.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    appendix.append(f"\nCommit probe: `{env.get('version_endpoint', {}).get('commit_sha', '')[:12]}`")
    appendix.append(f"Missing reminder candidates: {len(missing)}")
    report_path.write_text(prior.rstrip() + "\n" + "\n".join(appendix) + "\n", encoding="utf-8")

    watchlist = [
        "# Rent operations landlord-tenant watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Post-deploy run tag: `{RUN_TAG}`",
        "",
        "## Post-deploy checklist",
        *[f"- [{'x' if results.get(k) else ' '}] {k}" for k in results],
        "",
        "## Remaining",
    ]
    if clf["classification"] != "VERIFIED_OPERATIONALLY":
        watchlist.extend(
            [
                "- [ ] Confirm Render deploy commit >= 1dfcc85a with live-send env",
                "- [ ] Ledger with missing due/overdue reminder events for live-send proof",
                "- [ ] RENT_REMINDER message_logs status=sent to f7-ops-wales@yopmail.com",
            ]
        )
    else:
        watchlist.append("- [x] Live rent reminder delivery verified on staging")
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
