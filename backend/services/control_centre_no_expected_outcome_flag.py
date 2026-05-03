"""
Control Centre: "success but no attempted outcomes" false-positive guard.

Legacy job_runs rows may be success with missing outcome_status / empty outcome_metrics.
Those must not be treated as confirmed unexpected no-output (insufficient telemetry).

Real warnings require structured persisted outcome fields before applying attempted/success heuristics.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_recalc_worker_job_outcomes import (
    should_skip_control_centre_no_outcome_flag_recalc,
)
from services.compliance_snapshot_job_outcomes import should_skip_control_centre_no_outcome_flag
from services.job_schedule_registry import (
    JOB_STATE_CONDITIONAL_NO_OUTPUT,
    JOB_STATE_HEALTHY,
)
from services.risk_signal_regen_admin_surface import should_skip_no_expected_outcome_flag

# Keys persisted by instrumented jobs with outcome_metrics contracts (subset; extend only with evidence).
STRUCTURED_OUTCOME_METRIC_KEYS = frozenset(
    {
        "attempted_count",
        "expected_count",
        "success_count",
        "failed_count",
        "outcome_kind",
        "queue_empty",
        "no_clients",
        "regenerated_count",
        "skipped_feature_flag_count",
        "clients_considered",
        "clients_succeeded",
        "clients_failed",
        "queue_items_seen_batch",
        "queue_items_processed",
        "queue_items_claim_skipped",
        "queue_items_failed",
        "queue_items_dead",
    }
)


def detail_has_structured_outcome_telemetry(detail: Dict[str, Any]) -> bool:
    """
    True when the health-summary job detail row has enough persisted outcome contract
    to evaluate the no-expected-outcome heuristic (vs legacy incomplete rows).
    """
    last_outcome = (detail.get("last_outcome_status") or "").strip()
    if last_outcome:
        return True
    om = detail.get("outcome_metrics")
    if not isinstance(om, dict) or len(om) == 0:
        return False
    return any(k in om for k in STRUCTURED_OUTCOME_METRIC_KEYS)


def should_flag_no_expected_outcome_control_centre(
    job_id: str,
    *,
    zero_output_ok: bool,
    job_state: Optional[str],
    detail: Dict[str, Any],
) -> bool:
    """
    Whether Control Centre should list this job under unexpected no-outcome successes.

    Caller supplies registry zero_output_ok and job_states-derived state for the job.
    """
    if zero_output_ok:
        return False
    st = (job_state or "").strip()
    if st not in (JOB_STATE_HEALTHY, JOB_STATE_CONDITIONAL_NO_OUTPUT):
        return False
    if (
        should_skip_no_expected_outcome_flag(job_id, detail)
        or should_skip_control_centre_no_outcome_flag(job_id, detail)
        or should_skip_control_centre_no_outcome_flag_recalc(job_id, detail)
    ):
        return False
    if not detail_has_structured_outcome_telemetry(detail):
        return False
    om_last = detail.get("outcome_metrics") or {}
    if not isinstance(om_last, dict):
        om_last = {}
    attempted = int(om_last.get("attempted_count") or om_last.get("expected_count") or 0)
    success_c = int(om_last.get("success_count") or 0)
    last_run_status = (detail.get("last_run_status") or "").strip().lower()
    if attempted == 0 and success_c == 0 and last_run_status == "success":
        return True
    return False
