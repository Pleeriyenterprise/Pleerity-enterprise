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

INTERNAL_ALERTS: Dict[str, Dict[str, Any]] = {
    SCHEDULER_HEARTBEAT_STALE: {
        "severity": "P1",
        "component": "Scheduler",
        "description": "The background scheduler has not updated the heartbeat within the expected window. Jobs may not be running.",
        "default_title": "Scheduler heartbeat stale",
        "suggested_action": "Check server process and logs; restart scheduler if needed.",
    },
    JOB_MISSED_SLA: {
        "severity": "P2",  # Overridden per-job by sla_watchdog (P0/P1/P2 from max_delay)
        "component": "Job Monitor",
        "description": "A critical job has not completed successfully within its SLA window.",
        "default_title": "Job missed SLA",
        "suggested_action": "Check Automation Centre job runs and logs; verify dependencies and retry.",
    },
    JOB_DEGRADED: {
        "severity": "P2",
        "component": "Job Monitor",
        "description": "Job completed but with degraded outcome (some outputs failed or were skipped).",
        "default_title": "Job last run was degraded",
        "suggested_action": "Check Automation Centre outcome_metrics and job logs.",
    },
    DELIVERY_UNKNOWN_STALE: {
        "severity": "P2",
        "component": "Delivery reconciliation",
        "description": "Runs still have delivery_unknown beyond the stale threshold. Provider webhooks or message status may be delayed.",
        "default_title": "Delivery unknown unresolved",
        "suggested_action": "Check provider webhooks and Message logs.",
    },
    EMAIL_DELIVERY_FAILURE_SPIKE: {
        "severity": "P1",
        "component": "Email delivery",
        "description": "Unusual spike in email delivery failures detected.",
        "default_title": "Email delivery failure spike",
        "suggested_action": "Check Postmark dashboard and bounce/complaint logs; review NOTIFICATION_SPIKE_* config.",
    },
    PROVISIONING_FAILED: {
        "severity": "P1",
        "component": "Provisioning",
        "description": "Tenant or channel provisioning (e.g. Postmark, Twilio) failed.",
        "default_title": "Provisioning failed",
        "suggested_action": "Check provisioning logs and provider API status; retry or fix configuration.",
    },
    STRIPE_WEBHOOK_FAILURE: {
        "severity": "P1",
        "component": "Billing webhooks",
        "description": "Stripe webhook processing failed; billing events may be missed.",
        "default_title": "Stripe webhook failure",
        "suggested_action": "Check webhook endpoint logs and Stripe dashboard; retry failed events if needed.",
    },
}


def get_alert_config(alert_type: str) -> Optional[Dict[str, Any]]:
    """Return the config dict for an alert type, or None if unknown."""
    return INTERNAL_ALERTS.get(alert_type)
