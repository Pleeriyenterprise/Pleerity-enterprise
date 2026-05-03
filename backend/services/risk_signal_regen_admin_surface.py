"""
Admin-only copy and guardrails for risk_signal_regen_worker job_runs / health summary.
Keeps observability and Control Centre aligned without touching regen execution logic.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.job_schedule_registry import (
    JOB_STATE_DEGRADED,
    JOB_STATE_FAILED,
    JOB_STATE_HEALTHY,
)

RISK_SIGNAL_REGEN_JOB_ID = "risk_signal_regen_worker"


def _n_properties(n: int) -> str:
    return f"{n} propert{'y' if n == 1 else 'ies'}"


def should_skip_no_expected_outcome_flag(job_id: str, detail: Dict[str, Any]) -> bool:
    """
    Control Centre jobs_flagged_no_expected_outcome: for risk_signal_regen_worker only,
    empty queue + conditional_no_output is intentional, not a configuration defect.

    Other jobs that reuse queue_empty / conditional_no_output must not be suppressed here
    without an explicit job_id guard (would hide real misconfigurations).
    """
    if job_id != RISK_SIGNAL_REGEN_JOB_ID:
        return False
    if (detail.get("last_outcome_status") or "").strip().lower() != "conditional_no_output":
        return False
    om = detail.get("outcome_metrics") or {}
    if om.get("queue_empty") is True:
        return True
    return False


def health_summary_reason_override(job_id: str, state: str, detail: Dict[str, Any]) -> Optional[str]:
    """
    When health state maps to generic labels, replace reason text for risk regen only.
    Returns None to keep the default reason from JOB_STATE_REASONS / _compute_job_state_and_reason.
    """
    if job_id != RISK_SIGNAL_REGEN_JOB_ID:
        return None
    om = detail.get("outcome_metrics") or {}
    loc = (detail.get("last_outcome_status") or "").strip().lower()
    reg = int(om.get("regenerated_count") or 0)
    skip = int(om.get("skipped_feature_flag_count") or 0)
    fail = int(om.get("failed_count") or 0)
    queue_empty = om.get("queue_empty") is True

    if state == JOB_STATE_FAILED:
        if fail > 0:
            return (
                f"{fail} risk signal refresh attempt(s) failed on the last run. "
                "Review error_message, audit_logs (RISK_SIGNAL_REGEN_FAILED), and queue rows."
            )
        return "Last run completed as failed; review error_message and logs."

    if state == JOB_STATE_DEGRADED:
        parts = []
        if fail > 0:
            parts.append(f"{fail} refresh attempt(s) failed")
        if reg > 0:
            parts.append(f"{_n_properties(reg)} had risk signals refreshed")
        if skip > 0:
            parts.append(
                f"{_n_properties(skip)} skipped because predictive maintenance is disabled"
            )
        if parts:
            return "; ".join(parts) + ". Review outcome_metrics and audits."
        return "Last run completed with a degraded outcome; review outcome_metrics and audits."

    if state != JOB_STATE_HEALTHY:
        return None

    if queue_empty and loc == "conditional_no_output":
        return "No risk signal refresh work was waiting on the last completed run."

    if skip > 0 and reg == 0 and fail == 0 and loc == "conditional_no_output":
        return (
            f"{_n_properties(skip)} skipped because predictive maintenance is disabled; "
            "no risk signals were refreshed on the last run."
        )

    if reg > 0:
        base = f"Risk signals refreshed for {_n_properties(reg)} on the last run."
        if skip > 0:
            base += f" {_n_properties(skip)} skipped because predictive maintenance is disabled."
        return base

    return None
