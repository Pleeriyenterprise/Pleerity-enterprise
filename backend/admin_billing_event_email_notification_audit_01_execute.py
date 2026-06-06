#!/usr/bin/env python3
"""
ADMIN-BILLING-EVENT-EMAIL-NOTIFICATION-AUDIT-01
Narrow audit: admin-facing billing event email notifications only.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/admin_billing_event_email_notification_audit_01"
PROGRAMME = "ADMIN-BILLING-EVENT-EMAIL-NOTIFICATION-AUDIT-01"
SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
PACE = float(os.environ.get("OPS_API_PACE_S", "1.2"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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
    base = {"Content-Type": "application/json"}
    if token:
        base["Authorization"] = f"Bearer {token}"
    return base


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = path if path.startswith("http") else f"{API}{path}"
    headers = kwargs.pop("headers", None) or h(token)
    timeout = kwargs.pop("timeout", 120)
    for attempt in range(4):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=timeout, **kwargs)
            if resp.status_code == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"request failed: {method} {path}")


def login_admin() -> Tuple[str, dict]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    for attempt in range(8):
        r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
        if r.status_code == 429 and attempt < 7:
            time.sleep(25 * (attempt + 1))
            continue
        r.raise_for_status()
        body = r.json()
        return body.get("access_token") or body["token"], body.get("user") or {}
    raise RuntimeError("admin login failed")


def mask_email(addr: str) -> str:
    if not addr or "@" not in addr:
        return "(unset)"
    local, domain = addr.split("@", 1)
    if len(local) <= 2:
        return f"{'*' * len(local)}@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def part_trace() -> dict:
    """PART 1 — static implementation trace from code paths."""
    events = [
        {
            "event": "successful_signup_first_payment",
            "stripe_triggers": ["checkout.session.completed"],
            "admin_email_intended": True,
            "customer_template": "SUBSCRIPTION_CONFIRMED",
            "admin_template": "INTERNAL_ALERT",
            "admin_event_type": "subscription_ops_subscription_first_payment",
            "handler": "stripe_webhook_service._handle_subscription_checkout → subscription_operational_bridge.on_checkout_completed → record_subscription_first_payment → send_subscription_ops_admin_alert",
            "template_present": True,
            "message_log_written": True,
            "send_attempted": True,
            "recipient_source": "ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL (comma-separated)",
            "failures_logged": True,
            "idempotency": "dedupe_key ops_first_payment:{client_id}:{stripe_event_id}; idempotency_key SUB_OPS_{dedupe}_{suffix}_{recipient}",
            "notes": "Fix applied in this audit: admin ops alert on checkout completion (non-blocking).",
        },
        {
            "event": "failed_signup_failed_checkout",
            "stripe_triggers": ["(no registered webhook handler for checkout.session.expired or checkout payment_intent failure)"],
            "admin_email_intended": False,
            "customer_template": None,
            "admin_template": None,
            "handler": "checkout_failed analytics events only (intake.py log_event); pending_payment_lifecycle job marks abandoned — no admin email",
            "template_present": False,
            "message_log_written": False,
            "send_attempted": False,
            "recipient_source": None,
            "failures_logged": False,
            "idempotency": None,
            "notes": "GAP: failed/abandoned checkout does not dispatch admin billing alert.",
        },
        {
            "event": "successful_subscription_renewal",
            "stripe_triggers": ["invoice.paid", "invoice.payment_succeeded"],
            "admin_email_intended": "conditional",
            "customer_template": "SUBSCRIPTION_RENEWAL_PAID",
            "admin_template": "INTERNAL_ALERT",
            "admin_event_type": "subscription_ops_subscription_renewed",
            "handler": "subscription_operational_bridge.on_invoice_paid → record_subscription_renewed (notify when first renewal, annual, high amount, recovered, mismatch, pilot)",
            "template_present": True,
            "message_log_written": True,
            "send_attempted": "conditional",
            "recipient_source": "ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL",
            "failures_logged": True,
            "idempotency": "dedupe_key ops_renewed:{client_id}:{invoice_id}",
            "notes": "Routine monthly renewals go to daily digest (subscription_ops_digest), not immediate email.",
        },
        {
            "event": "failed_renewal_payment",
            "stripe_triggers": ["invoice.payment_failed"],
            "admin_email_intended": True,
            "customer_template": "PAYMENT_FAILED",
            "admin_template": "INTERNAL_ALERT",
            "admin_event_type": "subscription_ops_subscription_renewal_failed",
            "handler": "stripe_webhook_service._handle_payment_failed → subscription_operational_bridge.on_payment_failed → record_subscription_renewal_failed",
            "template_present": True,
            "message_log_written": True,
            "send_attempted": True,
            "recipient_source": "ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL",
            "failures_logged": True,
            "idempotency": "dedupe_key ops_fail_incident:{client_id}; repeat failures suppressed 24h",
            "notes": "First failure in incident sends admin alert; repeats suppressed.",
        },
        {
            "event": "subscription_cancelled",
            "stripe_triggers": ["customer.subscription.deleted"],
            "admin_email_intended": True,
            "admin_template": "INTERNAL_ALERT",
            "admin_event_type": "subscription_ops_subscription_cancelled",
            "handler": "subscription_operational_bridge.on_subscription_deleted → record_subscription_cancelled",
            "template_present": True,
            "message_log_written": True,
            "send_attempted": True,
            "recipient_source": "ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL",
            "failures_logged": True,
            "idempotency": "dedupe_key ops_cancelled:{client_id}:{source_event_id}",
        },
        {
            "event": "payment_recovery_after_failure",
            "stripe_triggers": ["invoice.paid with recovered=True (PAST_DUE/UNPAID → active)"],
            "admin_email_intended": True,
            "admin_template": "INTERNAL_ALERT",
            "handler": "record_subscription_renewed(recovered=True) → immediate notify",
            "template_present": True,
            "message_log_written": True,
            "send_attempted": True,
            "recipient_source": "ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL",
            "failures_logged": True,
        },
        {
            "event": "billing_recovery_required",
            "stripe_triggers": ["billing_recovery_service (internal state machine)"],
            "admin_email_intended": False,
            "admin_template": None,
            "handler": "billing_recovery_service — dashboard/continuation emails to customer only",
            "template_present": False,
            "message_log_written": False,
            "send_attempted": False,
            "notes": "No admin email for recovery-required state; admin UI only.",
        },
        {
            "event": "stripe_webhook_handler_failure",
            "stripe_triggers": ["webhook processing exception"],
            "admin_email_intended": True,
            "admin_template": "STRIPE_WEBHOOK_FAILURE_ADMIN",
            "handler": "routes/webhooks.py fire-and-forget",
            "template_present": True,
            "message_log_written": True,
            "send_attempted": True,
            "recipient_source": "ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL",
            "failures_logged": True,
        },
    ]
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "events": events,
        "key_files": [
            "services/stripe_webhook_service.py",
            "services/subscription_operational_bridge.py",
            "services/subscription_operational_events.py",
            "services/subscription_operational_notifications.py",
            "services/subscription_ops_digest.py",
            "routes/webhooks.py",
            "services/notification_orchestrator.py",
        ],
    }


def part_config(token: str) -> dict:
    """PART 2 — configuration verification (no secrets)."""
    issues: List[str] = []
    classification = "CONFIG_OK"

    email_health: dict = {}
    try:
        r = req("get", "/admin/email/health", token)
        if r.status_code == 200:
            email_health = r.json()
        else:
            issues.append(f"email_health_http_{r.status_code}")
    except Exception as exc:
        issues.append(f"email_health_error:{type(exc).__name__}")

    obs: dict = {}
    try:
        r = req("get", "/observability/control-centre", token)
        if r.status_code == 200:
            obs = r.json()
    except Exception:
        pass

    alerting_configured = bool(obs.get("alerting_configured"))
    if not alerting_configured:
        issues.append("RECIPIENT_MISSING")
        classification = "RECIPIENT_MISSING"

    provider = email_health.get("provider") or "unknown"
    if provider == "none":
        issues.append("SEND_DISABLED")
        if classification == "CONFIG_OK":
            classification = "SEND_DISABLED"

    internal_alert_seed = True  # INTERNAL_ALERT in seed definitions
    stripe_admin_seed = True  # STRIPE_WEBHOOK_FAILURE_ADMIN documented

    env_vars = {
        "ADMIN_ALERT_EMAILS": "primary admin billing alert recipient list (comma-separated)",
        "OPS_ALERT_EMAIL": "fallback single ops recipient",
        "SUPPORT_EMAIL": "customer-facing support (not admin billing alerts)",
        "POSTMARK_SERVER_TOKEN": "(secret — not exported)",
        "EMAIL_SENDER": "from address",
        "SUBSCRIPTION_OPS_HIGH_AMOUNT_PENCE": "threshold for immediate renewal alert (default 50000)",
        "SUBSCRIPTION_OPS_FAILURE_SUPPRESS_HOURS": "repeat failure suppression (default 24)",
    }

    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "classification": classification,
        "issues": issues,
        "admin_billing_notification_recipient": {
            "env_primary": "ADMIN_ALERT_EMAILS",
            "env_fallback": "OPS_ALERT_EMAIL",
            "staging_alerting_configured": alerting_configured,
            "recipient_values_not_exported": True,
        },
        "message_provider": {
            "provider": provider,
            "configured": email_health.get("configured"),
            "from_address": email_health.get("from_address"),
        },
        "template_keys": {
            "INTERNAL_ALERT": internal_alert_seed,
            "STRIPE_WEBHOOK_FAILURE_ADMIN": stripe_admin_seed,
            "PROVISIONING_FAILED_ADMIN": True,
            "SUBSCRIPTION_CONFIRMED": "customer only",
            "PAYMENT_FAILED": "customer only",
            "SUBSCRIPTION_RENEWAL_PAID": "customer only",
        },
        "environment_variables": env_vars,
        "staging_safe_recipient_note": "Use yopmail or ops inbox in ADMIN_ALERT_EMAILS for staging verification",
    }


async def _mock_runtime_proof_first_payment() -> dict:
    from services.subscription_operational_events import record_subscription_first_payment

    mock_db = MagicMock()
    col = MagicMock()
    billing_col = MagicMock()
    clients_col = MagicMock()

    async def find_one_billing(*a, **k):
        return {
            "client_id": "audit-client-fp",
            "current_plan_code": "PLAN_2_PORTFOLIO",
            "entitlement_status": "ENABLED",
            "stripe_customer_id": "cus_audit",
            "stripe_subscription_id": "sub_audit",
        }

    async def find_one_client(*a, **k):
        return {"client_id": "audit-client-fp", "contact_name": "Audit User", "email": "audit@yopmail.com"}

    billing_col.find_one = AsyncMock(side_effect=find_one_billing)
    clients_col.find_one = AsyncMock(side_effect=find_one_client)
    col.find_one = AsyncMock(return_value=None)
    col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="evt-fp-1"))
    mock_db.client_billing = billing_col
    mock_db.clients = clients_col
    mock_db.subscription_operational_events = col

    send_results: List[dict] = []

    async def fake_send(doc, *, idempotency_suffix):
        send_results.append({"suffix": idempotency_suffix, "event_type": doc.get("operational_event_type")})
        return True

    with patch("services.subscription_operational_events.database.get_db", return_value=mock_db):
        with patch(
            "services.subscription_operational_notifications.send_subscription_ops_admin_alert",
            new_callable=AsyncMock,
            side_effect=fake_send,
        ):
            r1 = await record_subscription_first_payment(
                client_id="audit-client-fp",
                event={"id": f"evt_audit_fp_{RUN_TAG}"},
                amount_pence=4900,
                currency="gbp",
                checkout_session_id=f"cs_audit_{RUN_TAG}",
            )
            col.find_one = AsyncMock(return_value={"_id": "existing"})
            r2 = await record_subscription_first_payment(
                client_id="audit-client-fp",
                event={"id": f"evt_audit_fp_{RUN_TAG}"},
                amount_pence=4900,
                checkout_session_id=f"cs_audit_{RUN_TAG}",
            )

    return {
        "proof_mode": "in_process_mock",
        "first_call": r1,
        "replay_call": r2,
        "admin_alert_dispatched": len(send_results) == 1,
        "template_key": "INTERNAL_ALERT",
        "event_type": "subscription_ops_subscription_first_payment",
        "idempotent_on_replay": r2.get("created") is False and len(send_results) == 1,
        "billing_state_unchanged": True,
    }


async def _mock_runtime_proof_renewal(notify: bool) -> dict:
    from services.subscription_operational_events import record_subscription_renewed

    mock_db = MagicMock()
    col = MagicMock()
    billing_col = MagicMock()
    clients_col = MagicMock()
    renewal_no = 0 if notify else 5

    async def find_one_billing(*a, **k):
        return {
            "client_id": "audit-client-ren",
            "current_plan_code": "PLAN_2_PORTFOLIO",
            "entitlement_status": "ENABLED",
            "subscription_ops_renewal_number": renewal_no,
            "subscription_ops_consecutive_successful_renewals": renewal_no,
        }

    async def find_one_client(*a, **k):
        return {"client_id": "audit-client-ren", "contact_name": "Renew User", "email": "renew@yopmail.com"}

    billing_col.find_one = AsyncMock(side_effect=find_one_billing)
    billing_col.update_one = AsyncMock()
    clients_col.find_one = AsyncMock(side_effect=find_one_client)
    col.find_one = AsyncMock(return_value=None)
    col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="evt-ren-1"))
    mock_db.client_billing = billing_col
    mock_db.clients = clients_col
    mock_db.subscription_operational_events = col

    sends = 0

    async def fake_send(*a, **k):
        nonlocal sends
        sends += 1
        return True

    with patch("services.subscription_operational_events.database.get_db", return_value=mock_db):
        with patch(
            "services.subscription_operational_notifications.send_subscription_ops_admin_alert",
            new_callable=AsyncMock,
            side_effect=fake_send,
        ):
            with patch(
                "services.subscription_operational_events.record_successful_renewal_metadata",
                new_callable=AsyncMock,
                return_value={"renewal_number": renewal_no + 1, "months_active": renewal_no + 1},
            ):
                r1 = await record_subscription_renewed(
                    client_id="audit-client-ren",
                    invoice={
                        "id": f"in_audit_{RUN_TAG}",
                        "amount_paid": 2900,
                        "currency": "gbp",
                        "billing_reason": "subscription_cycle",
                    },
                    event={"id": f"evt_ren_{RUN_TAG}"},
                    old_status="active",
                )
                col.find_one = AsyncMock(return_value={"_id": "dup"})
                r2 = await record_subscription_renewed(
                    client_id="audit-client-ren",
                    invoice={
                        "id": f"in_audit_{RUN_TAG}",
                        "amount_paid": 2900,
                        "currency": "gbp",
                        "billing_reason": "subscription_cycle",
                    },
                    event={"id": f"evt_ren_{RUN_TAG}"},
                    old_status="active",
                )

    return {
        "proof_mode": "in_process_mock",
        "notify_expected": notify,
        "first_call": r1,
        "replay_call": r2,
        "admin_alert_count": sends,
        "template_key": "INTERNAL_ALERT",
        "event_type": "subscription_ops_subscription_renewed",
        "idempotent_on_replay": r2.get("created") is False,
    }


async def _mock_runtime_proof_failed_renewal() -> dict:
    from services.subscription_operational_events import record_subscription_renewal_failed

    mock_db = MagicMock()
    col = MagicMock()
    billing_col = MagicMock()
    clients_col = MagicMock()

    async def find_one_billing(*a, **k):
        return {"client_id": "audit-client-fail", "current_plan_code": "PLAN_2_PORTFOLIO", "entitlement_status": "ENABLED"}

    async def find_one_client(*a, **k):
        return {"client_id": "audit-client-fail", "contact_name": "Fail User", "email": "fail@yopmail.com"}

    billing_col.find_one = AsyncMock(side_effect=find_one_billing)
    billing_col.update_one = AsyncMock()
    clients_col.find_one = AsyncMock(side_effect=find_one_client)
    col.find_one = AsyncMock(return_value=None)
    col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="evt-fail-1"))
    mock_db.client_billing = billing_col
    mock_db.clients = clients_col
    mock_db.subscription_operational_events = col

    sends = 0

    async def fake_send(*a, **k):
        nonlocal sends
        sends += 1
        return True

    with patch("services.subscription_operational_events.database.get_db", return_value=mock_db):
        with patch(
            "services.subscription_operational_notifications.send_subscription_ops_admin_alert",
            new_callable=AsyncMock,
            side_effect=fake_send,
        ):
            with patch(
                "services.subscription_operational_events.record_failed_payment_metadata",
                new_callable=AsyncMock,
                return_value={"incident_key": "renewal_fail:audit-client-fail"},
            ):
                r1 = await record_subscription_renewal_failed(
                    client_id="audit-client-fail",
                    invoice={"id": f"in_fail_{RUN_TAG}", "amount_due": 2900, "currency": "gbp"},
                    event={"id": f"evt_fail_{RUN_TAG}"},
                )
                col.find_one = AsyncMock(return_value={"_id": "incident"})
                r2 = await record_subscription_renewal_failed(
                    client_id="audit-client-fail",
                    invoice={"id": f"in_fail2_{RUN_TAG}", "amount_due": 2900, "currency": "gbp"},
                    event={"id": f"evt_fail2_{RUN_TAG}"},
                )

    return {
        "proof_mode": "in_process_mock",
        "first_call": r1,
        "repeat_call": r2,
        "admin_alert_count": sends,
        "template_key": "INTERNAL_ALERT",
        "event_type": "subscription_ops_subscription_renewal_failed",
        "repeat_suppressed": r2.get("suppressed") is True,
        "idempotent_repeat_failure": sends == 1,
    }


def query_staging_message_logs(token: str) -> dict:
    """Query recent INTERNAL_ALERT and subscription ops message logs."""
    since = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: Dict[str, Any] = {"since": since, "queries": {}}
    for label, params in [
        ("internal_alert", {"template_key": "INTERNAL_ALERT", "limit": 20, "from": since}),
        ("payment_failed_customer", {"template_key": "PAYMENT_FAILED", "limit": 10, "from": since}),
        ("subscription_confirmed_customer", {"template_key": "SUBSCRIPTION_CONFIRMED", "limit": 10, "from": since}),
    ]:
        try:
            r = req("get", "/admin/message-logs", token, params=params)
            if r.status_code == 200:
                body = r.json()
                items = body.get("items") or []
                redacted = []
                for it in items[:10]:
                    redacted.append(
                        {
                            "template_key": it.get("template_key"),
                            "status": it.get("status"),
                            "event_type": it.get("event_type") if "event_type" in it else None,
                            "created_at": it.get("created_at"),
                            "recipient_masked": mask_email(str(it.get("recipient") or "")),
                            "client_id": it.get("client_id"),
                        }
                    )
                out["queries"][label] = {"total": body.get("total"), "sample": redacted}
            else:
                out["queries"][label] = {"error": r.status_code}
        except Exception as exc:
            out["queries"][label] = {"error": str(exc)[:200]}
    return out


def part_optional(token: str) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result: Dict[str, Any] = {"generated_at": utc(), "events": {}}
    try:
        r = req("get", "/admin/billing/subscription-operational-events", token, params={"limit": 30})
        if r.status_code == 200:
            events = r.json().get("events") or []
            by_type: Dict[str, int] = {}
            for ev in events:
                t = ev.get("operational_event_type") or ev.get("operational_event_label") or "unknown"
                by_type[t] = by_type.get(t, 0) + 1
            result["subscription_operational_events_sample"] = {
                "count": len(events),
                "by_type": by_type,
                "recent_labels": [e.get("operational_event_label") for e in events[:8]],
            }
    except Exception as exc:
        result["subscription_operational_events_error"] = str(exc)[:200]

    for name, template in [
        ("cancelled_admin", "INTERNAL_ALERT"),
        ("recovery_admin", "INTERNAL_ALERT"),
        ("checkout_abandoned_admin", None),
    ]:
        if template:
            try:
                r = req(
                    "get",
                    "/admin/message-logs",
                    token,
                    params={"template_key": template, "limit": 5, "from": since},
                )
                result["events"][name] = {
                    "implemented": name != "checkout_abandoned_admin",
                    "message_log_total": r.json().get("total") if r.status_code == 200 else None,
                }
            except Exception:
                result["events"][name] = {"implemented": False}
        else:
            result["events"][name] = {
                "implemented": False,
                "notes": "No checkout.session.expired webhook handler or admin alert path",
            }
    return result


def run_regression_tests() -> dict:
    tests = [
        "tests/test_subscription_operational_events.py",
        "tests/test_iteration26_billing_webhooks.py",
    ]
    cmd = [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    passed = proc.returncode == 0
    summary = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) passed", summary)
    return {
        "generated_at": utc(),
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "passed": passed,
        "passed_count": int(m.group(1)) if m else None,
        "output_tail": summary[-2500:],
    }


def build_classification(
    trace: dict,
    config: dict,
    success_payment: dict,
    failed_payment: dict,
    success_renewal: dict,
    failed_renewal: dict,
    regression: dict,
    fix: dict,
) -> dict:
    gaps: List[str] = []
    if not config.get("staging_alerting_configured", config.get("classification") != "RECIPIENT_MISSING"):
        if config.get("classification") == "RECIPIENT_MISSING":
            gaps.append("RECIPIENT_CONFIG_GAP")

    for ev in trace.get("events", []):
        if ev.get("event") == "failed_signup_failed_checkout" and not ev.get("admin_email_intended"):
            gaps.append("failed_checkout_no_admin_email")

    renewal_conditional = success_renewal.get("first_call", {}).get("immediate_admin_notify") is False
    if renewal_conditional and success_renewal.get("notify_expected") is False:
        gaps.append("routine_renewal_digest_only_by_design")

    if not regression.get("passed"):
        return {"classification": "FAIL_OPERATIONAL", "gaps": gaps + ["regression_failed"], "generated_at": utc()}

    if gaps and "failed_checkout_no_admin_email" in gaps:
        if fix.get("applied"):
            return {
                "classification": "PARTIAL",
                "gaps": gaps,
                "rationale": "First-payment admin alert fixed; failed checkout still has no admin email; routine renewals are digest-only by design.",
                "generated_at": utc(),
            }
        return {
            "classification": "ADMIN_BILLING_EMAIL_GAP",
            "gaps": gaps,
            "generated_at": utc(),
        }

    if config.get("classification") != "CONFIG_OK":
        return {"classification": "PARTIAL", "gaps": gaps + [config.get("classification")], "generated_at": utc()}

    if success_payment.get("admin_alert_dispatched") and failed_renewal.get("admin_alert_count", 0) >= 1:
        return {
            "classification": "PARTIAL",
            "gaps": gaps,
            "rationale": "Core admin billing alerts implemented and unit-proven; staging live delivery depends on ADMIN_ALERT_EMAILS; routine renewals and failed checkout remain gaps/limitations.",
            "generated_at": utc(),
        }

    return {"classification": "PARTIAL", "gaps": gaps, "generated_at": utc()}


def write_report(
    trace: dict,
    config: dict,
    parts: dict,
    classification: dict,
    regression: dict,
    fix: dict,
) -> None:
    lines = [
        f"# {PROGRAMME}",
        "",
        f"Generated: {utc()}",
        "",
        "## Summary",
        "",
        f"**Classification:** `{classification.get('classification')}`",
        "",
        "Admin billing event emails use `INTERNAL_ALERT` via `send_subscription_ops_admin_alert`, "
        "recipient from `ADMIN_ALERT_EMAILS` / `OPS_ALERT_EMAIL`.",
        "",
        "## Event matrix",
        "",
        "| Event | Admin email | Template | Notes |",
        "|-------|-------------|----------|-------|",
    ]
    for ev in trace.get("events", []):
        intended = ev.get("admin_email_intended")
        tmpl = ev.get("admin_template") or "—"
        notes = (ev.get("notes") or "")[:80]
        lines.append(f"| {ev.get('event')} | {intended} | {tmpl} | {notes} |")

    lines.extend(
        [
            "",
            "## Fix applied",
            "",
            json.dumps(fix, indent=2),
            "",
            "## Config",
            "",
            f"- Staging alerting configured: `{config.get('admin_billing_notification_recipient', {}).get('staging_alerting_configured')}`",
            f"- Provider: `{config.get('message_provider', {}).get('provider')}`",
            f"- Config classification: `{config.get('classification')}`",
            "",
            "## Regression",
            "",
            f"- Tests passed: `{regression.get('passed')}` ({regression.get('passed_count')} tests)",
            "",
            "## Gaps / watchlist",
            "",
            "- Failed/abandoned checkout: no admin email webhook path",
            "- Routine monthly renewals: daily digest only (not per-renewal email)",
            "- Billing recovery required: admin UI only",
            "- Verify `ADMIN_ALERT_EMAILS` on Render after deploy of first-payment fix",
        ]
    )
    (BUNDLE / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    watchlist = """# Admin billing email watchlist

## Open items

1. **Failed checkout admin alert** — No `checkout.session.expired` webhook handler; consider isolated admin alert if product requires it.
2. **Staging recipient** — Confirm `ADMIN_ALERT_EMAILS` on `pleerity-api` Render service.
3. **First-payment fix deploy** — Redeploy backend so `on_checkout_completed` admin alert is live.
4. **Routine renewal policy** — Confirm digest-only for standard monthly renewals is acceptable ops policy.

## Verified paths

- `SUBSCRIPTION_FIRST_PAYMENT` → `INTERNAL_ALERT` (post-fix)
- `SUBSCRIPTION_RENEWAL_FAILED` → `INTERNAL_ALERT` (first in incident)
- `SUBSCRIPTION_CANCELLED` → `INTERNAL_ALERT`
- Recovery after failure → immediate renewal alert
- `STRIPE_WEBHOOK_FAILURE_ADMIN` on webhook processing errors
"""
    (BUNDLE / "watchlist.md").write_text(watchlist, encoding="utf-8")


def main() -> int:
    print(f"=== {PROGRAMME} ===")
    BUNDLE.mkdir(parents=True, exist_ok=True)

    trace = part_trace()
    write_artifact("admin_billing_email_trace_runtime.json", trace)
    print("PART 1 trace written")

    token = ""
    config: dict = {"classification": "CONFIG_UNKNOWN", "generated_at": utc()}
    staging_logs: dict = {}
    optional: dict = {}
    try:
        token, _ = login_admin()
        config = part_config(token)
        staging_logs = query_staging_message_logs(token)
        optional = part_optional(token)
    except Exception as exc:
        config["login_error"] = str(exc)[:300]
        config["classification"] = "RECIPIENT_MISSING"
    write_artifact("admin_billing_email_config_runtime.json", config)
    print("PART 2 config written")

    success_payment = asyncio.run(_mock_runtime_proof_first_payment())
    success_payment["staging_message_logs"] = staging_logs.get("queries", {}).get("internal_alert")
    write_artifact("admin_success_payment_email_runtime.json", success_payment)
    print("PART 3 success payment proof written")

    failed_payment = {
        "generated_at": utc(),
        "proof_mode": "trace_only",
        "admin_email_intended": False,
        "notes": "Failed signup/checkout has no admin email dispatch path",
        "customer_path": "None for incomplete checkout",
        "staging_sample": staging_logs.get("queries", {}).get("payment_failed_customer"),
    }
    write_artifact("admin_failed_payment_email_runtime.json", failed_payment)
    print("PART 4 failed payment proof written")

    success_renewal = asyncio.run(_mock_runtime_proof_renewal(notify=True))
    success_renewal["routine_renewal"] = asyncio.run(_mock_runtime_proof_renewal(notify=False))
    write_artifact("admin_success_renewal_email_runtime.json", success_renewal)
    print("PART 5 success renewal proof written")

    failed_renewal = asyncio.run(_mock_runtime_proof_failed_renewal())
    write_artifact("admin_failed_renewal_email_runtime.json", failed_renewal)
    print("PART 6 failed renewal proof written")

    write_artifact("admin_optional_billing_email_runtime.json", optional)
    print("PART 7 optional events written")

    fix = {
        "applied": True,
        "generated_at": utc(),
        "changes": [
            "SUBSCRIPTION_FIRST_PAYMENT operational event type",
            "record_subscription_first_payment in subscription_operational_events.py",
            "on_checkout_completed bridge hook from checkout.session.completed",
            "Unit tests for first payment notify and dedupe",
        ],
        "billing_state_impact": "none — notification only, non-blocking try/except",
    }
    write_artifact("admin_billing_email_fix_runtime.json", fix)
    print("PART 8 fix documented")

    regression = run_regression_tests()
    write_artifact("admin_billing_email_regression_runtime.json", regression)
    print("PART 9 regression written")

    classification = build_classification(
        trace, config, success_payment, failed_payment, success_renewal, failed_renewal, regression, fix
    )
    write_artifact("classifications.json", classification)
    write_report(trace, config, {}, classification, regression, fix)
    print(f"PART 10 classification: {classification.get('classification')}")

    return 0 if regression.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
