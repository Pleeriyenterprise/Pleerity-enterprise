"""Customer Operations Centre Phase 2 — read models extending lifecycle operations (no new authority)."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.account_background_runtime_authority import evaluate_background_runtime
from services.account_customer_communication_authority import evaluate_customer_communication
from services.account_lifecycle_runtime_contract import (
    CACHE_TTL_SECONDS,
    compare_runtime_with_legacy,
    peek_cached_runtime_contract,
)

_HEALTH_LEVELS = ("healthy", "warning", "critical", "unknown")
_CHAIN_LEVELS = ("healthy", "waiting", "drift_detected", "failed", "unknown")

_BACKGROUND_JOB_SAMPLES = (
    "daily_reminders",
    "monthly_digest",
    "renewal_reminders",
    "compliance_monitoring",
    "queue_processing",
)

_COMM_TEMPLATE_SAMPLES = (
    ("SUBSCRIPTION_GRACE_REMINDER", "Recovery / grace reminder"),
    ("SUBSCRIPTION_RENEWAL_7D", "Renewal reminder (7d)"),
    ("SUBSCRIPTION_RENEWAL_3D", "Renewal reminder (3d)"),
)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _age_minutes(value: Any, now: datetime) -> Optional[float]:
    dt = _parse_dt(value)
    if not dt:
        return None
    return round((now - dt).total_seconds() / 60.0, 1)


def _indicator(level: str, explanation: str) -> Dict[str, str]:
    return {"status": level if level in _HEALTH_LEVELS else "unknown", "explanation": explanation}


def _worst_level(levels: List[str]) -> str:
    order = {"critical": 0, "warning": 1, "unknown": 2, "healthy": 3}
    if not levels:
        return "unknown"
    return min(levels, key=lambda x: order.get(x, 2))


def _chain_stage(
    stage: str,
    authority: str,
    status: str,
    explanation: str,
    *,
    mirror: bool = False,
) -> Dict[str, Any]:
    return {
        "stage": stage,
        "authority": authority,
        "status": status if status in _CHAIN_LEVELS else "unknown",
        "explanation": explanation,
        "mirror": mirror,
    }


def build_health_indicators(
    *,
    contract: Dict[str, Any],
    billing: Dict[str, Any],
    client: Dict[str, Any],
    failed_webhook_count: int,
    background_summary: Dict[str, Any],
    communications_summary: Dict[str, Any],
    drift_flags: List[str],
    now: datetime,
) -> Dict[str, Dict[str, str]]:
    lifecycle_state = str(contract.get("lifecycle_state") or "UNKNOWN").upper()
    portal_mode = str(contract.get("portal_mode") or "")
    transition_pending = bool((contract.get("lifecycle_context") or {}).get("transition_pending"))

    if lifecycle_state in ("SUSPENDED", "SUBSCRIPTION_EXPIRED", "ACCOUNT_DELETED"):
        lifecycle = _indicator("critical", f"Lifecycle state is {lifecycle_state}")
    elif lifecycle_state in ("GRACE_PERIOD", "BILLING_RECOVERY", "PAYMENT_REQUIRED", "CANCELLATION_SCHEDULED"):
        lifecycle = _indicator("warning", f"Lifecycle state {lifecycle_state} requires attention")
    elif transition_pending:
        lifecycle = _indicator("warning", "Lifecycle transition is pending convergence")
    elif lifecycle_state == "ACTIVE":
        lifecycle = _indicator("healthy", f"Lifecycle ACTIVE with portal mode {portal_mode or 'default'}")
    else:
        lifecycle = _indicator("unknown", f"Lifecycle state {lifecycle_state}")

    recon_needed = bool(billing.get("billing_reconciliation_needed"))
    stale_cancel = bool(billing.get("stale_scheduled_cancellation_mirror"))
    stripe_mode_missing = not billing.get("stripe_mode")
    period_past = bool(billing.get("current_period_end_past"))

    if recon_needed or stale_cancel:
        billing_ind = _indicator(
            "critical",
            billing.get("billing_reconciliation_reason") or "Billing reconciliation required",
        )
    elif stripe_mode_missing or period_past:
        billing_ind = _indicator(
            "warning",
            "Stripe mode missing or period end appears past — verify mirror freshness",
        )
    elif billing.get("stripe_subscription_id"):
        billing_ind = _indicator("healthy", "Billing mirror present with subscription")
    elif billing.get("stripe_customer_id") or client.get("stripe_customer_id"):
        billing_ind = _indicator("warning", "Stripe customer without active subscription mirror")
    else:
        billing_ind = _indicator("unknown", "No Stripe billing mirror on record")

    contract_warnings = list(contract.get("warnings") or [])
    if contract_warnings:
        runtime_ind = _indicator("warning", "; ".join(str(w) for w in contract_warnings[:3]))
    elif contract.get("runtime_version"):
        runtime_ind = _indicator("healthy", f"Runtime Contract resolved (v{contract.get('runtime_version')})")
    else:
        runtime_ind = _indicator("unknown", "Runtime Contract version unavailable")

    caps = contract.get("capabilities") or {}
    denied = sum(1 for v in caps.values() if v == "DENY")
    if denied > 20:
        capabilities = _indicator("warning", f"{denied} capabilities denied — expected for restricted states")
    elif caps:
        capabilities = _indicator("healthy", f"Capability matrix evaluated ({len(caps)} entries)")
    else:
        capabilities = _indicator("unknown", "No capability matrix available")

    if billing.get("stripe_subscription_id") and billing.get("stripe_customer_id"):
        stripe_ind = _indicator("healthy", "Stripe customer and subscription linked")
    elif billing.get("stripe_customer_id") or client.get("stripe_customer_id"):
        stripe_ind = _indicator("warning", "Stripe customer without subscription ID on mirror")
    else:
        stripe_ind = _indicator("unknown", "No Stripe customer on record")

    if failed_webhook_count > 0:
        webhooks = _indicator("critical", f"{failed_webhook_count} failed webhook event(s) for this client")
    elif billing.get("stripe_webhook_last_received_at"):
        webhooks = _indicator("healthy", "Recent webhook activity recorded on billing mirror")
    elif billing.get("stripe_subscription_id"):
        webhooks = _indicator("warning", "Subscription present but no recent webhook timestamp on mirror")
    else:
        webhooks = _indicator("unknown", "No webhook activity recorded")

    if recon_needed:
        reconciliation = _indicator("critical", "Reconciliation flag set on billing mirror")
    elif stale_cancel:
        reconciliation = _indicator("warning", "Stale scheduled-cancellation mirror — reconcile from Stripe")
    else:
        reconciliation = _indicator("healthy", "No reconciliation flags on billing mirror")

    bg_paused = background_summary.get("paused_count", 0)
    bg_terminated = background_summary.get("terminated_count", 0)
    if bg_terminated > 0:
        background_jobs = _indicator("critical", f"{bg_terminated} background job group(s) terminated for this lifecycle")
    elif bg_paused > 0:
        background_jobs = _indicator("warning", f"{bg_paused} background job group(s) paused or skipped")
    else:
        background_jobs = _indicator("healthy", "Sampled background job groups allowed to continue")

    suppressed = communications_summary.get("suppressed_channels") or []
    if len(suppressed) >= 2:
        communications = _indicator("warning", f"Communications suppressed: {', '.join(suppressed[:4])}")
    elif communications_summary.get("last_sent_at"):
        communications = _indicator("healthy", "Recent customer communication on record")
    else:
        communications = _indicator("unknown", "No recent communications in message log window")

    if drift_flags:
        data_integrity = _indicator("warning", f"Runtime drift flags: {', '.join(drift_flags[:4])}")
    else:
        data_integrity = _indicator("healthy", "No runtime vs legacy drift flags detected")

    return {
        "lifecycle": lifecycle,
        "billing": billing_ind,
        "runtime_contract": runtime_ind,
        "capabilities": capabilities,
        "stripe": stripe_ind,
        "webhook_processing": webhooks,
        "reconciliation": reconciliation,
        "background_jobs": background_jobs,
        "communications": communications,
        "data_integrity": data_integrity,
    }


def build_customer_health_summary(indicators: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    levels = [v["status"] for v in indicators.values()]
    worst = _worst_level(levels)
    if worst == "critical":
        overall = "Critical"
        headline = "Critical operational issues detected — review authority chain and governed actions"
    elif worst == "warning":
        overall = "Attention Required"
        headline = "One or more operational indicators need attention"
    elif worst == "healthy":
        overall = "Healthy"
        headline = "All sampled operational indicators are healthy"
    else:
        overall = "Attention Required"
        headline = "Some operational data is unknown — verify Stripe and Runtime Contract sources"

    return {
        "overall": overall,
        "headline": headline,
        "derived_from": "authoritative_runtime_contract_billing_mirror_events",
        "indicators": indicators,
    }


def build_authority_chain(
    *,
    contract: Dict[str, Any],
    billing: Dict[str, Any],
    drift_flags: List[str],
    failed_webhook_count: int,
    background_summary: Dict[str, Any],
    communications_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    lifecycle_state = contract.get("lifecycle_state")
    recon_needed = bool(billing.get("billing_reconciliation_needed"))
    stale_cancel = bool(billing.get("stale_scheduled_cancellation_mirror"))

    stripe_status = "healthy" if billing.get("stripe_customer_id") else "unknown"
    if not billing.get("stripe_subscription_id") and billing.get("stripe_customer_id"):
        stripe_status = "drift_detected"

    mirror_status = "drift_detected" if (recon_needed or stale_cancel or drift_flags) else "healthy"
    if not billing:
        mirror_status = "unknown"

    resolver_status = "waiting" if (contract.get("lifecycle_context") or {}).get("transition_pending") else "healthy"

    runtime_status = "healthy" if contract.get("runtime_version") else "unknown"
    if contract.get("warnings"):
        runtime_status = "drift_detected"

    caps = contract.get("capabilities") or {}
    cap_status = "healthy" if caps else "unknown"

    nav_status = "healthy" if contract.get("portal_mode") else "unknown"

    bg_status = "healthy"
    if background_summary.get("terminated_count", 0) > 0:
        bg_status = "failed"
    elif background_summary.get("paused_count", 0) > 0:
        bg_status = "waiting"

    comm_policy = contract.get("communication_policy") or {}
    comm_status = "healthy" if comm_policy else "unknown"
    if communications_summary.get("suppressed_channels"):
        comm_status = "waiting"

    cx = contract.get("customer_experience") or {}
    cx_status = "healthy" if cx.get("heading") else "unknown"

    webhook_chain = "failed" if failed_webhook_count else ("healthy" if billing.get("stripe_webhook_last_received_at") else "unknown")

    return [
        _chain_stage("Stripe", "Stripe API", stripe_status, "Authoritative subscription and payment facts"),
        _chain_stage(
            "Billing mirror",
            "client_billing sync",
            mirror_status,
            "Local mirror fed by webhooks and governed reconciliation",
            mirror=True,
        ),
        _chain_stage(
            "Lifecycle resolver",
            "account_lifecycle_state_resolver",
            resolver_status,
            f"Resolved lifecycle state: {lifecycle_state}",
        ),
        _chain_stage(
            "Runtime Contract",
            "account_lifecycle_runtime_contract",
            runtime_status,
            f"Runtime version {contract.get('runtime_version')}",
        ),
        _chain_stage("Capabilities", "account_capability_enforcement", cap_status, "Capability matrix from Runtime Contract"),
        _chain_stage("Navigation", "portal_mode authority", nav_status, f"Portal mode: {contract.get('portal_mode')}"),
        _chain_stage("Background policies", "account_background_runtime_authority", bg_status, "Background job gating from contract"),
        _chain_stage("Communications", "account_customer_communication_authority", comm_status, "Channel eligibility from communication_policy"),
        _chain_stage("Customer experience", "lifecycle response authority", cx_status, cx.get("heading") or "Experience copy from contract"),
        _chain_stage(
            "Webhook processing",
            "stripe_webhook_service",
            webhook_chain,
            "Ingress events persisted to stripe_events",
        ),
    ]


async def build_operational_timeline(
    db,
    client_id: str,
    *,
    stripe_events: List[Dict[str, Any]],
    limit: int = 40,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    lifecycle_rows = await (
        db.account_lifecycle_events.find({"client_id": client_id}, {"_id": 0})
        .sort("published_at", -1)
        .limit(25)
        .to_list(25)
    )
    for row in lifecycle_rows:
        events.append(
            {
                "timestamp": _iso(row.get("published_at") or row.get("created_at")),
                "event_kind": "lifecycle",
                "title": row.get("event_type") or "Lifecycle event",
                "source": row.get("source_service") or "account_lifecycle_event_authority",
                "authority": "Lifecycle Event Authority",
                "result": row.get("lifecycle_state_after") or row.get("lifecycle_state"),
                "duration_ms": None,
                "metadata": {
                    k: row.get(k)
                    for k in ("event_category", "trigger", "portal_mode_after", "runtime_version")
                    if row.get(k) is not None
                },
            }
        )

    for row in stripe_events[:15]:
        created = _parse_dt(row.get("created"))
        processed = _parse_dt(row.get("processed_at"))
        duration_ms = None
        if created and processed:
            duration_ms = round((processed - created).total_seconds() * 1000, 1)
        status = row.get("status")
        events.append(
            {
                "timestamp": _iso(row.get("processed_at") or row.get("created")),
                "event_kind": "webhook",
                "title": f"Stripe webhook: {row.get('type')}",
                "source": "stripe",
                "authority": "stripe_webhook_service",
                "result": status,
                "duration_ms": duration_ms,
                "metadata": {"event_id": row.get("event_id"), "error_preview": row.get("error_preview")},
            }
        )

    audit_rows = await (
        db.audit_logs.find(
            {
                "client_id": client_id,
                "action": {"$in": ["ADMIN_ACTION", "BILLING", "SUBSCRIPTION"]},
            },
            {"_id": 0},
        )
        .sort("timestamp", -1)
        .limit(20)
        .to_list(20)
    )
    for row in audit_rows:
        meta = row.get("metadata") or {}
        action_type = meta.get("action_type") or row.get("action")
        events.append(
            {
                "timestamp": _iso(row.get("timestamp")),
                "event_kind": "audit",
                "title": action_type,
                "source": meta.get("event_source") or meta.get("resume_source") or "audit_log",
                "authority": "governed_admin_or_billing",
                "result": meta.get("result") or ("success" if meta else "recorded"),
                "duration_ms": None,
                "audit_ref": action_type,
                "metadata": {k: meta.get(k) for k in ("reason", "lifecycle_state", "subscription_status_after") if meta.get(k)},
            }
        )

    msg_rows = await (
        db.message_logs.find({"client_id": client_id}, {"_id": 0, "body": 0})
        .sort("created_at", -1)
        .limit(15)
        .to_list(15)
    )
    for row in msg_rows:
        events.append(
            {
                "timestamp": _iso(row.get("created_at") or row.get("sent_at")),
                "event_kind": "communication",
                "title": row.get("template_key") or row.get("subject") or "Customer communication",
                "source": row.get("channel") or "email",
                "authority": "notification_orchestrator",
                "result": row.get("status"),
                "duration_ms": None,
                "metadata": {
                    k: row.get(k)
                    for k in ("message_id", "category", "suppression_reason", "event_type")
                    if row.get(k) is not None
                },
            }
        )

    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return events[:limit]


def build_runtime_diagnostics(
    *,
    client_id: str,
    contract: Dict[str, Any],
    billing: Dict[str, Any],
    drift_report: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    cached = peek_cached_runtime_contract(client_id)
    cache_fresh = cached is not None and cached.get("runtime_version") == contract.get("runtime_version")

    mirror_age = _age_minutes(billing.get("billing_last_synced_at"), now)

    return {
        "runtime_version": contract.get("runtime_version"),
        "contract_version": contract.get("contract_version"),
        "resolved_at": contract.get("resolved_at"),
        "runtime_source": "account_lifecycle_runtime_contract.resolve_runtime_contract_for_client",
        "runtime_cache": {
            "ttl_seconds": CACHE_TTL_SECONDS,
            "cached": cache_fresh,
            "status": "warm" if cache_fresh else "cold_or_stale",
            "explanation": "In-process cache for session/runtime reads; admin snapshot bypasses cache",
        },
        "capability_evaluation": {
            "entries": len(contract.get("capabilities") or {}),
            "last_via": "Runtime Contract resolution",
        },
        "mirror_freshness": {
            "billing_last_synced_at": _iso(billing.get("billing_last_synced_at")),
            "age_minutes": mirror_age,
            "billing_sync_state": billing.get("billing_sync_state"),
            "stale_threshold_minutes": 360,
            "is_stale": mirror_age is not None and mirror_age > 360,
        },
        "legacy_drift": {
            "flags": drift_report.get("drift_flags") or [],
            "warnings": drift_report.get("warnings") or [],
        },
        "session_note": "Session freshness is per active portal session; use Activity tab for login audit",
    }


async def build_background_processing_summary(db, client_id: str, contract: Dict[str, Any]) -> Dict[str, Any]:
    samples: List[Dict[str, Any]] = []
    paused = 0
    terminated = 0
    for job_type in _BACKGROUND_JOB_SAMPLES:
        try:
            decision = await evaluate_background_runtime(db, client_id, job_type)
            row = decision.to_dict() if hasattr(decision, "to_dict") else {
                "decision": getattr(decision, "decision", None),
                "reason": getattr(decision, "reason", ""),
                "job_type": job_type,
            }
            if isinstance(row.get("decision"), str):
                dec = row["decision"]
            else:
                dec = str(getattr(decision.decision, "value", decision.decision))
            if dec in ("PAUSE", "SKIP", "RETENTION_ONLY"):
                paused += 1
            if dec == "TERMINATE":
                terminated += 1
            samples.append(
                {
                    "job_type": job_type,
                    "decision": dec,
                    "reason": row.get("reason"),
                    "background_policy_key": row.get("background_policy_key"),
                    "background_policy_action": row.get("background_policy_action"),
                }
            )
        except Exception as exc:
            samples.append({"job_type": job_type, "decision": "UNKNOWN", "reason": str(exc)[:200]})

    bg_policy = contract.get("background_policy") or {}
    return {
        "background_policy": bg_policy,
        "sampled_job_groups": samples,
        "paused_count": paused,
        "terminated_count": terminated,
        "automation_note": "Platform scheduler health: System Health dashboard (not duplicated here)",
        "resume_policy": "Background resumes when Runtime Contract policy allows CONTINUE",
    }


async def build_communications_summary(db, client_id: str, contract: Dict[str, Any]) -> Dict[str, Any]:
    comm_policy = dict(contract.get("communication_policy") or {})
    suppressed_channels = [k for k, v in comm_policy.items() if v in ("SUPPRESS", "DENY", "BLOCK", False)]

    template_samples: List[Dict[str, Any]] = []
    for template_key, label in _COMM_TEMPLATE_SAMPLES:
        try:
            decision = await evaluate_customer_communication(
                db,
                client_id,
                template_key=template_key,
                contract=contract,
            )
            template_samples.append(
                {
                    "label": label,
                    "template_key": template_key,
                    "allowed": decision.allowed,
                    "suppressed": decision.suppressed,
                    "suppression_reason": decision.suppression_reason,
                    "channel_policy_key": decision.channel_policy_key,
                }
            )
        except Exception as exc:
            template_samples.append(
                {"label": label, "template_key": template_key, "error": str(exc)[:120]},
            )

    msg_rows = await (
        db.message_logs.find({"client_id": client_id}, {"_id": 0, "body": 0, "html": 0})
        .sort("created_at", -1)
        .limit(10)
        .to_list(10)
    )
    recent = [
        {
            "timestamp": _iso(r.get("created_at") or r.get("sent_at")),
            "template_key": r.get("template_key"),
            "channel": r.get("channel"),
            "status": r.get("status"),
            "category": r.get("category"),
        }
        for r in msg_rows
    ]
    last_sent = recent[0]["timestamp"] if recent else None

    return {
        "communication_policy": comm_policy,
        "suppressed_channels": suppressed_channels,
        "template_eligibility_samples": template_samples,
        "recent_messages": recent,
        "last_sent_at": last_sent,
        "notification_eligibility_note": "Derived from Runtime Contract communication_policy via Communication Authority",
    }


def build_webhook_diagnostics(
    *,
    billing: Dict[str, Any],
    raw_events: List[Dict[str, Any]],
    failed_count: int,
    replay_blocked_reason: str,
) -> Dict[str, Any]:
    enriched: List[Dict[str, Any]] = []
    for ev in raw_events:
        created = _parse_dt(ev.get("created"))
        processed = _parse_dt(ev.get("processed_at"))
        duration_ms = None
        if created and processed:
            duration_ms = round((processed - created).total_seconds() * 1000, 1)
        status = ev.get("status")
        replay_eligible = False
        if status == "FAILED":
            replay_eligible = False
        enriched.append(
            {
                "event_id": ev.get("event_id"),
                "type": ev.get("type"),
                "status": status,
                "source": "stripe",
                "received_at": _iso(ev.get("created")),
                "processed_at": _iso(ev.get("processed_at")),
                "processing_duration_ms": duration_ms,
                "retry_count": ev.get("retry_count", 0),
                "replay_eligible": replay_eligible,
                "replay_note": replay_blocked_reason if status == "FAILED" else None,
                "error_preview": (ev.get("error") or "")[:200] or None,
            }
        )

    if failed_count > 0:
        health = "critical"
    elif billing.get("stripe_webhook_last_received_at"):
        health = "healthy"
    else:
        health = "unknown"

    return {
        "overall_health": health,
        "last_received_at": _iso(billing.get("stripe_webhook_last_received_at")),
        "last_event_type": billing.get("stripe_webhook_last_event_type"),
        "failed_event_count": failed_count,
        "events": enriched,
        "replay_policy": replay_blocked_reason,
        "platform_ingress_note": "Webhook endpoint platform health: System Health (not duplicated)",
    }


def build_phase2_extensions(
    *,
    contract: Dict[str, Any],
    billing: Dict[str, Any],
    client: Dict[str, Any],
    client_id: str,
    failed_webhook_count: int,
    raw_stripe_events: List[Dict[str, Any]],
    background_summary: Dict[str, Any],
    communications_summary: Dict[str, Any],
    operational_timeline: List[Dict[str, Any]],
    now: datetime,
) -> Dict[str, Any]:
    drift_report = compare_runtime_with_legacy(contract)
    drift_flags = list(drift_report.get("drift_flags") or [])

    indicators = build_health_indicators(
        contract=contract,
        billing=billing,
        client=client,
        failed_webhook_count=failed_webhook_count,
        background_summary=background_summary,
        communications_summary=communications_summary,
        drift_flags=drift_flags,
        now=now,
    )
    replay_reason = "Replay is intentionally unavailable. Use Stripe reconciliation instead."

    return {
        "customer_health": build_customer_health_summary(indicators),
        "authority_chain": build_authority_chain(
            contract=contract,
            billing=billing,
            drift_flags=drift_flags,
            failed_webhook_count=failed_webhook_count,
            background_summary=background_summary,
            communications_summary=communications_summary,
        ),
        "operational_timeline": operational_timeline,
        "runtime_diagnostics": build_runtime_diagnostics(
            client_id=client_id,
            contract=contract,
            billing=billing,
            drift_report=drift_report,
            now=now,
        ),
        "background_processing": background_summary,
        "communications": communications_summary,
        "webhook_diagnostics": build_webhook_diagnostics(
            billing=billing,
            raw_events=raw_stripe_events,
            failed_count=failed_webhook_count,
            replay_blocked_reason=replay_reason,
        ),
    }


def _redact_bundle_value(key: str, value: Any) -> Any:
    sensitive = ("password", "secret", "token", "raw_minimal", "api_key", "authorization")
    if any(s in key.lower() for s in sensitive):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _redact_bundle_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_bundle_value(key, v) for v in value]
    return value


def build_support_bundle_payload(snapshot: Dict[str, Any], client: Dict[str, Any]) -> Dict[str, str]:
    """Return filename → JSON string map for ZIP export."""
    cid = snapshot.get("client_id", "")
    customer_summary = {
        "client_id": cid,
        "email": client.get("email"),
        "name": client.get("name") or client.get("company_name"),
        "billing_plan": client.get("billing_plan"),
        "generated_at": snapshot.get("generated_at"),
        "programme": "ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01",
    }
    sections = {
        "README.txt": (
            f"Support bundle for client {cid}\n"
            f"Generated: {snapshot.get('generated_at')}\n"
            "No secrets included. Use governed admin actions for recovery.\n"
        ),
        "customer_summary.json": json.dumps(_redact_bundle_value("", customer_summary), indent=2, default=str),
        "customer_health.json": json.dumps(_redact_bundle_value("", snapshot.get("customer_health")), indent=2, default=str),
        "lifecycle.json": json.dumps(_redact_bundle_value("", snapshot.get("lifecycle")), indent=2, default=str),
        "billing.json": json.dumps(_redact_bundle_value("", snapshot.get("billing")), indent=2, default=str),
        "authority_chain.json": json.dumps(_redact_bundle_value("", snapshot.get("authority_chain")), indent=2, default=str),
        "runtime_diagnostics.json": json.dumps(_redact_bundle_value("", snapshot.get("runtime_diagnostics")), indent=2, default=str),
        "capabilities.json": json.dumps(_redact_bundle_value("", snapshot.get("capabilities")), indent=2, default=str),
        "webhook_diagnostics.json": json.dumps(_redact_bundle_value("", snapshot.get("webhook_diagnostics")), indent=2, default=str),
        "operational_timeline.json": json.dumps(_redact_bundle_value("", snapshot.get("operational_timeline")), indent=2, default=str),
        "background_processing.json": json.dumps(_redact_bundle_value("", snapshot.get("background_processing")), indent=2, default=str),
        "communications.json": json.dumps(_redact_bundle_value("", snapshot.get("communications")), indent=2, default=str),
        "recovery.json": json.dumps(_redact_bundle_value("", snapshot.get("recovery")), indent=2, default=str),
        "actions_eligibility.json": json.dumps(_redact_bundle_value("", snapshot.get("actions")), indent=2, default=str),
        "audit_timeline.json": json.dumps(
            _redact_bundle_value("", snapshot.get("lifecycle_audit_timeline")),
            indent=2,
            default=str,
        ),
    }
    return sections


def support_bundle_zip_bytes(snapshot: Dict[str, Any], client: Dict[str, Any]) -> bytes:
    files = build_support_bundle_payload(snapshot, client)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()
