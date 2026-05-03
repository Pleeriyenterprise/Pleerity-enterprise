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
        "default_title": "Scheduler heartbeat stale",
        "suggested_action": "Check server process and logs; restart scheduler if needed.",
    },
    JOB_MISSED_SLA: {
        "severity": "P2",  # Overridden per-job by sla_watchdog (P0/P1/P2 from max_delay)
        "component": "Job Monitor",
        "description": "A critical job has not completed successfully within its SLA window.",
        "business_impact": "Downstream compliance and automation outputs tied to this job may be stale until processing recovers.",
        "default_title": "Job missed SLA",
        "suggested_action": "Check Automation Centre job runs and logs; verify dependencies and retry.",
    },
    JOB_DEGRADED: {
        "severity": "P2",
        "component": "Job Monitor",
        "description": "Job completed but with degraded outcome (some outputs failed or were skipped).",
        "business_impact": "Some outputs from this job may be incomplete; dependent summaries or notifications may be partial.",
        "default_title": "Job last run was degraded",
        "suggested_action": "Check Automation Centre outcome_metrics and job logs.",
    },
    DELIVERY_UNKNOWN_STALE: {
        "severity": "P2",
        "component": "Delivery reconciliation",
        "description": "Runs still have delivery_unknown beyond the stale threshold. Provider webhooks or message status may be delayed.",
        "business_impact": "Delivery confirmation for outbound messages may be uncertain until reconciliation recovers.",
        "default_title": "Delivery unknown unresolved",
        "suggested_action": "Check provider webhooks and Message logs.",
    },
    EMAIL_DELIVERY_FAILURE_SPIKE: {
        "severity": "P1",
        "component": "Email delivery",
        "description": "Unusual spike in email delivery failures detected.",
        "business_impact": "Clients and staff may not receive expected emails until delivery stabilizes.",
        "default_title": "Email delivery failure spike",
        "suggested_action": "Check Postmark dashboard and bounce/complaint logs; review NOTIFICATION_SPIKE_* config.",
    },
    PROVISIONING_FAILED: {
        "severity": "P1",
        "component": "Provisioning",
        "description": "Tenant or channel provisioning (e.g. Postmark, Twilio) failed.",
        "business_impact": "Tenant messaging or telephony channels may be incomplete until provisioning succeeds.",
        "default_title": "Provisioning failed",
        "suggested_action": "Check provisioning logs and provider API status; retry or fix configuration.",
    },
    STRIPE_WEBHOOK_FAILURE: {
        "severity": "P1",
        "component": "Billing webhooks",
        "description": "Stripe webhook processing failed; billing events may be missed.",
        "business_impact": "Subscription and payment state in the platform may drift from Stripe until webhooks recover.",
        "default_title": "Stripe webhook failure",
        "suggested_action": "Check webhook endpoint logs and Stripe dashboard; retry failed events if needed.",
    },
    RISK_REGEN_QUEUE_ATTENTION: {
        "severity": "P2",
        "component": "Risk monitoring",
        "description": "Risk signal regeneration queue reports unhealthy backlog or stalled jobs.",
        "business_impact": "Property risk signals and related compliance summaries may not refresh until the queue recovers.",
        "default_title": "Risk signal regeneration queue needs attention",
        "suggested_action": "Review Automation Centre and risk regen queue diagnostics; clear dead jobs or fix failing workers as appropriate.",
    },
}


def get_alert_config(alert_type: str) -> Optional[Dict[str, Any]]:
    """Return the config dict for an alert type, or None if unknown."""
    return INTERNAL_ALERTS.get(alert_type)
