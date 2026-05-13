"""
Internal alert registry: single source of truth for operational alert types.
Used by sla_watchdog, notification_failure_spike_monitor, provisioning_runner, webhooks, etc.
Each entry defines severity, component, description, and optional suggested_action.
"""
from typing import Dict, Any, Optional

# Alert type identifiers (use these when creating incidents or sending alert emails)
SCHEDULER_HEARTBEAT_STALE = "SCHEDULER_HEARTBEAT_STALE"
JOB_MISSED_SLA = "JOB_MISSED_SLA"
JOB_DEGRADED = "JOB_DEGRADED"
DELIVERY_UNKNOWN_STALE = "DELIVERY_UNKNOWN_STALE"
EMAIL_DELIVERY_FAILURE_SPIKE = "EMAIL_DELIVERY_FAILURE_SPIKE"
PROVISIONING_FAILED = "PROVISIONING_FAILED"
STRIPE_WEBHOOK_FAILURE = "STRIPE_WEBHOOK_FAILURE"
RISK_REGEN_QUEUE_ATTENTION = "RISK_REGEN_QUEUE_ATTENTION"

INTERNAL_ALERTS: Dict[str, Dict[str, Any]] = {
    SCHEDULER_HEARTBEAT_STALE: {
        "severity": "P1",
        "component": "Scheduler",
        "description": "The background scheduler has not updated the heartbeat within the expected window. Jobs may not be running.",
        "business_impact": "Background automation may not be running reliably; scheduled operational tasks may be delayed.",
        "customer_impact": "Tenants may see stale reminders, scores, or operational updates until the scheduler recovers.",
        "urgency_guidance": "Immediate investigation recommended: confirm the application process is healthy and the scheduler loop is running.",
        "if_ignored": "Automation backlog can grow across multiple jobs; recovery may require coordinated restart and catch-up.",
        "default_title": "Scheduler heartbeat stale",
        "suggested_action": "Check server process and logs; restart scheduler if needed.",
        "recommended_actions_ordered": [
            "Open Admin → System health and confirm heartbeat age.",
            "Check host and application logs for crashes or deploy windows.",
            "If the process is down, restart per runbook; then verify Automation Centre shows fresh job runs.",
            "Escalate to platform engineering if heartbeat does not resume within 15 minutes after restart.",
        ],
    },
    JOB_MISSED_SLA: {
        "severity": "P2",  # Overridden per-job by sla_watchdog (P0/P1/P2 from max_delay)
        "component": "Job Monitor",
        "description": "A critical job has not completed successfully within its SLA window.",
        "business_impact": "Downstream compliance and automation outputs tied to this job may be stale until processing recovers.",
        "customer_impact": "Depending on the job, clients may see delayed scores, reminders, orders, or risk signals.",
        "urgency_guidance": "Immediate investigation recommended when severity is P0 or P1; for P2, begin triage within one business hour unless paired with user-reported issues.",
        "if_ignored": "Queues and dependent calculations can fall further behind; some user-visible surfaces may drift from authoritative data.",
        "default_title": "Job missed SLA",
        "suggested_action": "Check Automation Centre job runs and logs; verify dependencies and retry.",
        "recommended_actions_ordered": [
            "Open Automation Control Centre and locate the latest run for the affected job.",
            "Confirm whether the last run failed, was skipped, or never started (check outcome_metrics when present).",
            "Review Observability → Message logs if the job sends notifications.",
            "Check database and external provider health if failures cluster across jobs.",
            "Retry or re-queue the job only after understanding the failure mode; escalate if unresolved after 30–60 minutes.",
        ],
    },
    JOB_DEGRADED: {
        "severity": "P2",
        "component": "Job Monitor",
        "description": "Job completed but with degraded outcome (some outputs failed or were skipped).",
        "business_impact": "Some outputs from this job may be incomplete; dependent summaries or notifications may be partial.",
        "customer_impact": "Potential customer-facing impact: partial batches (for example reminders or digests) until the next successful run.",
        "urgency_guidance": "Safe to monitor briefly if this is an isolated degraded run; schedule follow-up verification on the next scheduled execution.",
        "if_ignored": "Repeated degraded runs can hide systemic issues; automation may silently skip subsets of work.",
        "default_title": "Job last run was degraded",
        "suggested_action": "Check Automation Centre outcome_metrics and job logs.",
        "recommended_actions_ordered": [
            "Open Automation Control Centre and review outcome_metrics for the degraded run.",
            "Compare against the prior successful run to see which outputs were partial.",
            "If degradation repeats, treat as operational warning and widen investigation (dependencies, rate limits).",
            "Escalate if customer-reported symptoms align with the degraded window.",
        ],
    },
    DELIVERY_UNKNOWN_STALE: {
        "severity": "P2",
        "component": "Delivery reconciliation",
        "description": "Runs still have delivery_unknown beyond the stale threshold. Provider webhooks or message status may be delayed.",
        "business_impact": "Delivery confirmation for outbound messages may be uncertain until reconciliation recovers.",
        "customer_impact": "Messages may have been delivered while the platform still shows unknown status; avoid duplicate resends until confirmed.",
        "urgency_guidance": "Operational degradation only: begin triage within a few hours unless volumes are high.",
        "if_ignored": "Message logs may retain unknown states; reporting and retries can become harder to reason about.",
        "default_title": "Delivery unknown unresolved",
        "suggested_action": "Check provider webhooks and Message logs.",
        "recommended_actions_ordered": [
            "Open Observability and filter recent provider callbacks.",
            "Confirm webhook signing secrets and endpoint availability.",
            "Reconcile stuck rows per provider guidance; document any bulk replay.",
        ],
    },
    EMAIL_DELIVERY_FAILURE_SPIKE: {
        "severity": "P1",
        "component": "Email delivery",
        "description": "Unusual spike in email delivery failures detected.",
        "business_impact": "Clients and staff may not receive expected emails until delivery stabilizes.",
        "customer_impact": "Clients and staff may miss time-sensitive operational or compliance emails.",
        "urgency_guidance": "Immediate investigation recommended when crossing critical thresholds; otherwise treat as priority review within the hour.",
        "if_ignored": "Backlog of unsent or bounced mail can grow; reputation and support load may suffer.",
        "default_title": "Email delivery failure spike",
        "suggested_action": "Check Postmark dashboard and bounce/complaint logs; review NOTIFICATION_SPIKE_* config.",
        "recommended_actions_ordered": [
            "Open Observability and identify dominant failing template_keys.",
            "Check Postmark (or provider) for bounces, blocks, and rate limits.",
            "Verify recent configuration or content changes; adjust throttles if appropriate.",
        ],
    },
    PROVISIONING_FAILED: {
        "severity": "P1",
        "component": "Provisioning",
        "description": "Tenant or channel provisioning (e.g. Postmark, Twilio) failed.",
        "business_impact": "Tenant messaging or telephony channels may be incomplete until provisioning succeeds.",
        "customer_impact": "Tenant onboarding or messaging channels may be incomplete until provisioning succeeds.",
        "urgency_guidance": "Immediate investigation recommended for new tenants; existing tenants may be partially impacted.",
        "if_ignored": "Channels remain incomplete; retries may compound without fixing root configuration.",
        "default_title": "Provisioning failed",
        "suggested_action": "Check provisioning logs and provider API status; retry or fix configuration.",
        "recommended_actions_ordered": [
            "Open Admin dashboard for the affected tenant context.",
            "Review provisioning logs and provider API responses.",
            "Retry only after correcting configuration; track audit trail.",
        ],
    },
    STRIPE_WEBHOOK_FAILURE: {
        "severity": "P1",
        "component": "Billing webhooks",
        "description": "Stripe webhook processing failed; billing events may be missed.",
        "business_impact": "Subscription and payment state in the platform may drift from Stripe until webhooks recover.",
        "customer_impact": "Billing and entitlement state may drift from Stripe until webhooks recover.",
        "urgency_guidance": "Immediate investigation recommended: billing divergence can affect access and invoices.",
        "if_ignored": "Renewals, cancellations, and payment events may not propagate; reconciliation work increases.",
        "default_title": "Stripe webhook failure",
        "suggested_action": "Check webhook endpoint logs and Stripe dashboard; retry failed events if needed.",
        "recommended_actions_ordered": [
            "Open Admin → Billing and Stripe dashboard for failed webhook deliveries.",
            "Inspect application logs for the reported exception.",
            "Retry failed events from Stripe after fixing the defect.",
        ],
    },
    RISK_REGEN_QUEUE_ATTENTION: {
        "severity": "P2",
        "component": "Risk monitoring",
        "description": "Risk signal regeneration queue reports unhealthy backlog or stalled jobs.",
        "business_impact": "Property risk signals and related compliance summaries may not refresh until the queue recovers.",
        "customer_impact": "Risk indicators and downstream summaries may be stale until the queue clears.",
        "urgency_guidance": "Safe to monitor briefly if counts are improving; otherwise schedule investigation within one business hour.",
        "if_ignored": "Risk views and automation that depend on fresh signals may stay stale.",
        "default_title": "Risk signal regeneration queue needs attention",
        "suggested_action": "Review Automation Centre and risk regen queue diagnostics; clear dead jobs or fix failing workers as appropriate.",
        "recommended_actions_ordered": [
            "Open Automation Control Centre and review risk signal regeneration queue depth.",
            "Identify FAILED or DEAD jobs and inspect last_error snippets.",
            "Clear or requeue only with runbook alignment; escalate if backlog grows over consecutive monitors.",
        ],
    },
}


def get_alert_config(alert_type: str) -> Optional[Dict[str, Any]]:
    """Return the config dict for an alert type, or None if unknown."""
    return INTERNAL_ALERTS.get(alert_type)
