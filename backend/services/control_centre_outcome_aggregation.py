"""
Control Centre: group job_runs outcome_metrics sums by operational family.

Per-job attempted/success/failed semantics differ; families keep admin totals interpretable
without a second observability authority (read-only reshape of existing job_runs).

Governance: every job id in ``job_schedule_registry`` and ``job_runner.JOB_RUNNERS`` must appear
in ``REGISTRY_JOB_OUTCOME_FAMILY``. Unknown ``job_name`` values at runtime still bucket to
``platform_other`` (safety); CI tests fail when the canonical job sets drift without an update.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Tuple

# --- Operational family definitions (display order + UI disclaimer) ---

# Ordered display: key, human label, disclaimer for operators (Control Centre UI)
OUTCOME_FAMILY_ORDER: Tuple[Tuple[str, str, str], ...] = (
    (
        "queue_processing",
        "Queue & retry processing",
        "Counts reflect compliance recalc queue work and notification retries — not tenant score changes alone.",
    ),
    (
        "notification_and_delivery",
        "Notifications, reports & delivery reconciliation",
        "Mix of message sends, digests, and delivery reconciliation units — not comparable to queue rows.",
    ),
    (
        "compliance_snapshots",
        "Compliance score snapshots",
        "Client/portfolio snapshot successes and failures — not the same as property-level recalculations.",
    ),
    (
        "risk_regeneration",
        "Risk signal regeneration",
        "Property refresh / regen queue semantics — see Automation Centre for that job.",
    ),
    (
        "monitoring_and_watchdog",
        "Monitoring, SLA watchdog & heartbeat",
        "Often one successful unit per run (check completed) — high frequency inflates sums vs daily jobs.",
    ),
    (
        "compliance_scheduled_batch",
        "Scheduled compliance batch jobs",
        "Expiry rollover, performance recalc, etc. — units are job-specific.",
    ),
    (
        "billing_and_subscription_jobs",
        "Billing & subscription maintenance jobs",
        "Lifecycle / Stripe reconcile counters as recorded on each job run.",
    ),
    (
        "platform_other",
        "Other automation jobs",
        "Intentionally ungrouped pipeline or client-lifecycle jobs (see governance notes); "
        "legacy or ad-hoc job_name strings may also land here.",
    ),
)

# Internal governance: what belongs in each family, what it represents, what must NOT be parked there.
# Not shipped as a second doc system — constants for engineers and code review only.
OUTCOME_FAMILY_GOVERNANCE: Dict[str, Dict[str, str]] = {
    "queue_processing": {
        "belongs": "Compliance recalc worker, notification retry worker, per-property enqueue helpers.",
        "represents": "Internal queue throughput and retry work units.",
        "excludes": "Customer-facing campaigns, portfolio snapshots, liveness-only monitors, billing lifecycle.",
    },
    "notification_and_delivery": {
        "belongs": "Reminders, digests, scheduled reports, delivery/order pipeline sends, nurture sequences, "
        "admin broadcast comms, work-order reminder schedules.",
        "represents": "Outbound comms and delivery-side processing tied to user-facing artifacts.",
        "excludes": "Pure SLA monitors with no send semantics; compliance recalc queue; billing Stripe jobs.",
    },
    "compliance_snapshots": {
        "belongs": "Compliance score snapshot batch for client portfolios.",
        "represents": "Snapshot generation outcomes, not live property recalculation.",
        "excludes": "Property-level recalc worker outcomes; risk signal regen.",
    },
    "risk_regeneration": {
        "belongs": "Risk signal regen worker, queue alert monitor, batch risk_signals job.",
        "represents": "Risk pipeline refresh / detection volume.",
        "excludes": "Compliance score snapshots; generic notification retries.",
    },
    "monitoring_and_watchdog": {
        "belongs": "Scheduler heartbeat, SLA watchdog, spike monitors, SLA monitors, lead SLA checks, "
        "work-order SLA breach / timeout monitors.",
        "represents": "Operational checks and guardrails — often one unit per run, not customer outcomes.",
        "excludes": "Jobs whose primary outcome is sending customer content or mutating billing state.",
    },
    "compliance_scheduled_batch": {
        "belongs": "Expiry rollover, contractor performance recalc, predictive insights, lead compliance gap scan.",
        "represents": "Time-batched compliance or analytics maintenance.",
        "excludes": "Continuous queue workers; payment lifecycle; client purge/archive (parked elsewhere).",
    },
    "billing_and_subscription_jobs": {
        "belongs": "Subscription lifecycle, Stripe reconcile, pending payment lifecycle.",
        "represents": "Billing/subscription maintenance as recorded on job runs.",
        "excludes": "LIMITED entitlement display (not a job); revenue aggregates outside job_runs.",
    },
    "platform_other": {
        "belongs": "Order stuck/queue/generation auto-retry pipeline; client lifecycle archive/purge/test-flag jobs — "
        "see ``INTENTIONAL_PLATFORM_OTHER_JOB_IDS``.",
        "represents": "Mixed or cross-cutting automation not yet given a dedicated family (explicit allowlist).",
        "excludes": "Any newly added production job id: those must get a concrete family or an updated allowlist "
        "with rationale (tests enforce).",
    },
}

# Jobs deliberately classified as platform_other (ambiguous cross-cutting or fulfillment pipeline).
INTENTIONAL_PLATFORM_OTHER_JOB_IDS: FrozenSet[str] = frozenset(
    {
        "stuck_order_detection",
        "queued_order_processing",
        "generation_auto_retry_processing",
        "client_lifecycle_stale_archive",
        "client_purge_eligibility_scan",
        "client_test_like_flag_job",
    }
)

# Single source of truth: must match exactly:
#   set(get_registry_by_id()) | set(job_runner.JOB_RUNNERS.keys())
# Tests fail on mismatch or when a new id is added without updating this map.
REGISTRY_JOB_OUTCOME_FAMILY: Dict[str, str] = {
    "abandoned_intake_detection": "notification_and_delivery",
    "activation_reminder_processing": "notification_and_delivery",
    "checklist_nurture_processing": "notification_and_delivery",
    "client_lifecycle_stale_archive": "platform_other",
    "client_purge_eligibility_scan": "platform_other",
    "client_test_like_flag_job": "platform_other",
    "compliance_check_evening": "notification_and_delivery",
    "compliance_check_morning": "notification_and_delivery",
    "compliance_recalc_enqueue_property": "queue_processing",
    "compliance_recalc_sla_monitor": "monitoring_and_watchdog",
    "compliance_recalc_worker": "queue_processing",
    "compliance_score_snapshots": "compliance_snapshots",
    "contractor_performance_recalc": "compliance_scheduled_batch",
    "daily_reminders": "notification_and_delivery",
    "delivery_reconciliation": "notification_and_delivery",
    "expiry_rollover_recalc": "compliance_scheduled_batch",
    "generation_auto_retry_processing": "platform_other",
    "lead_compliance_gap_detection": "compliance_scheduled_batch",
    "lead_followup_processing": "notification_and_delivery",
    "lead_inactive_reactivation_detection": "notification_and_delivery",
    "lead_sla_check": "monitoring_and_watchdog",
    "monthly_digest": "notification_and_delivery",
    "notification_failure_spike_monitor": "monitoring_and_watchdog",
    "notification_retry_worker": "queue_processing",
    "onboarding_sequence_processing": "notification_and_delivery",
    "order_delivery_processing": "notification_and_delivery",
    "pending_payment_lifecycle": "billing_and_subscription_jobs",
    "pending_verification_digest": "notification_and_delivery",
    "pilot_lifecycle_reconcile": "billing_and_subscription_jobs",
    "predictive_insights_job": "compliance_scheduled_batch",
    "queued_order_processing": "platform_other",
    "risk_lead_nurture_processing": "notification_and_delivery",
    "risk_signal_regen_alert_monitor": "risk_regeneration",
    "risk_signal_regen_worker": "risk_regeneration",
    "risk_signals_job": "risk_regeneration",
    "scheduled_admin_communications": "notification_and_delivery",
    "scheduled_reports": "notification_and_delivery",
    "scheduler_heartbeat": "monitoring_and_watchdog",
    "sla_monitoring": "monitoring_and_watchdog",
    "sla_watchdog": "monitoring_and_watchdog",
    "stripe_subscription_reconcile": "billing_and_subscription_jobs",
    "stuck_order_detection": "platform_other",
    "subscription_lifecycle": "billing_and_subscription_jobs",
    "subscription_ops_digest": "notification_and_delivery",
    "work_order_contractor_confirmation_timeout_job": "monitoring_and_watchdog",
    "work_order_schedule_reminders": "notification_and_delivery",
    "work_order_sla_breach_job": "monitoring_and_watchdog",
}


def outcome_family_for_job_name(job_name: str) -> str:
    """
    Map a job_name string to an operational outcome family.

    Registry and JOB_RUNNERS ids must be present in ``REGISTRY_JOB_OUTCOME_FAMILY`` (enforced by tests).
    Any other string (legacy rows, typos) maps to ``platform_other`` without failing aggregation.
    """
    if not job_name or not isinstance(job_name, str):
        return "platform_other"
    return REGISTRY_JOB_OUTCOME_FAMILY.get(job_name.strip(), "platform_other")


async def summarize_outcome_metrics_24h_by_family(db, since_iso: str) -> List[Dict[str, Any]]:
    """
    Aggregate finished job_runs in [since_iso, ∞) by operational family.
    Returns rows only for families with finished_runs > 0, stable display order.
    """
    pipeline = [
        {"$match": {"finished_at": {"$gte": since_iso}}},
        {
            "$group": {
                "_id": "$job_name",
                "finished_runs": {"$sum": 1},
                "outcome_success_sum": {"$sum": {"$ifNull": ["$outcome_metrics.success_count", 0]}},
                "outcome_failed_sum": {"$sum": {"$ifNull": ["$outcome_metrics.failed_count", 0]}},
                "outcome_attempted_sum": {"$sum": {"$ifNull": ["$outcome_metrics.attempted_count", 0]}},
            }
        },
    ]
    per_job = await db.job_runs.aggregate(pipeline).to_list(500)

    buckets: Dict[str, Dict[str, int]] = {}
    for row in per_job:
        jid = row.get("_id")
        if not isinstance(jid, str) or not jid:
            continue
        fam = outcome_family_for_job_name(jid)
        b = buckets.setdefault(
            fam,
            {"finished_runs": 0, "outcome_success_sum": 0, "outcome_failed_sum": 0, "outcome_attempted_sum": 0},
        )
        b["finished_runs"] += int(row.get("finished_runs") or 0)
        b["outcome_success_sum"] += int(row.get("outcome_success_sum") or 0)
        b["outcome_failed_sum"] += int(row.get("outcome_failed_sum") or 0)
        b["outcome_attempted_sum"] += int(row.get("outcome_attempted_sum") or 0)

    out: List[Dict[str, Any]] = []
    for key, label, disc in OUTCOME_FAMILY_ORDER:
        agg = buckets.get(key)
        if not agg or agg.get("finished_runs", 0) <= 0:
            continue
        out.append(
            {
                "family_key": key,
                "family_label": label,
                "family_disclaimer": disc,
                **agg,
            }
        )
    return out
