"""
Central registry for scheduled job metadata: criticality, expected frequency, max delay.
Used by observability (health summary, job states) and sla_watchdog for single source of truth.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Overall health states (strict; no optimistic "ok" when critical jobs are uncertain)
OVERALL_HEALTH_HEALTHY = "healthy"
OVERALL_HEALTH_DEGRADED = "degraded"
OVERALL_HEALTH_FAILED = "failed"
OVERALL_HEALTH_ATTENTION_REQUIRED = "attention_required"

# Per-job states
JOB_STATE_HEALTHY = "healthy"
JOB_STATE_DEGRADED = "degraded"
JOB_STATE_FAILED = "failed"
JOB_STATE_MISSED = "missed"
JOB_STATE_NEVER_RAN = "never_ran"  # legacy; prefer never_ran_and_overdue for no-run + overdue
JOB_STATE_NOT_YET_DUE_SINCE_STARTUP = "not_yet_due_since_startup"
JOB_STATE_NEVER_RAN_AND_OVERDUE = "never_ran_and_overdue"
JOB_STATE_NOT_DUE = "not_due"
JOB_STATE_DISABLED = "disabled"
JOB_STATE_CONDITIONAL_NO_OUTPUT = "conditional_no_output"

# Heartbeat staleness threshold (seconds) - align with observability
HEARTBEAT_STALE_SECONDS = 300  # 5 min


@dataclass
class JobScheduleEntry:
    """Metadata for a scheduled job."""
    job_id: str
    critical: bool  # If True, never_ran/missed/failed affect overall health
    max_delay_minutes: int  # Max acceptable delay since last success/degraded before "missed"
    frequency_label: str  # e.g. "Every 5 min", "Daily", "Monthly"
    zero_output_ok: bool  # True = zero outcome can be conditional_no_output (e.g. no reminders due)


# Critical jobs for health + SLA. Must match job_runner registered ids.
# max_delay_minutes: after this, job is "missed" if no successful/degraded run
CRITICAL_JOB_REGISTRY: List[JobScheduleEntry] = [
    JobScheduleEntry("daily_reminders", True, 26 * 60, "Daily", True),
    JobScheduleEntry("pending_verification_digest", True, 26 * 60, "Daily", True),
    JobScheduleEntry("monthly_digest", True, 36 * 60, "Monthly", True),
    JobScheduleEntry("compliance_check_morning", True, 26 * 60, "Twice daily", True),
    JobScheduleEntry("compliance_check_evening", True, 26 * 60, "Twice daily", True),
    JobScheduleEntry("scheduled_reports", True, 26 * 60, "Daily", True),
    JobScheduleEntry("compliance_score_snapshots", True, 26 * 60, "Daily", False),
    JobScheduleEntry("expiry_rollover_recalc", True, 26 * 60, "Daily", False),
    JobScheduleEntry("compliance_recalc_worker", True, 5, "Every 5 min", False),
    JobScheduleEntry("notification_retry_worker", True, 5, "Every minute", True),
    JobScheduleEntry("notification_failure_spike_monitor", True, 10, "Every 5 min", False),
    JobScheduleEntry("sla_watchdog", True, 15, "Every 10 min", False),
    JobScheduleEntry("scheduler_heartbeat", True, 5, "Every 2 min", False),
    JobScheduleEntry("delivery_reconciliation", True, 25, "Every 15 min", True),
    JobScheduleEntry("contractor_performance_recalc", False, 26 * 60, "Daily", True),
]

# All jobs that may appear in health summary / automation centre (including non-critical)
ALL_JOB_IDS_FOR_HEALTH: List[str] = [
    e.job_id for e in CRITICAL_JOB_REGISTRY
]


def get_registry_by_id() -> Dict[str, JobScheduleEntry]:
    return {e.job_id: e for e in CRITICAL_JOB_REGISTRY}


def get_critical_job_ids() -> List[str]:
    return [e.job_id for e in CRITICAL_JOB_REGISTRY if e.critical]


def get_job_entry(job_id: str) -> Optional[JobScheduleEntry]:
    return get_registry_by_id().get(job_id)
