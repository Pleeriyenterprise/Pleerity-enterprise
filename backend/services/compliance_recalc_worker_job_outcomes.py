"""
Maps compliance_recalc_worker batch counters to run_instrumented / job_runs outcome contract.

Does not implement queue scoring logic — classification only.
"""
from __future__ import annotations

from typing import Any, Dict

from services.job_run_service import (
    OUTCOME_CONDITIONAL_NO_OUTPUT,
    OUTCOME_DEGRADED,
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
)

COMPLIANCE_RECALC_WORKER_JOB_ID = "compliance_recalc_worker"


def should_skip_control_centre_no_outcome_flag_recalc(job_id: str, detail: Dict[str, Any]) -> bool:
    """No-work queue batch: intentional, not a misconfiguration."""
    if job_id != COMPLIANCE_RECALC_WORKER_JOB_ID:
        return False
    if (detail.get("last_outcome_status") or "").strip().lower() != OUTCOME_CONDITIONAL_NO_OUTPUT:
        return False
    om = detail.get("outcome_metrics") or {}
    if int(om.get("stale_running_reclaimed_to_pending") or 0) > 0 or int(om.get("stale_running_reclaimed_to_dead") or 0) > 0:
        return False
    return om.get("queue_empty") is True


def build_compliance_recalc_worker_run_result(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build return dict for run_compliance_recalc_worker.

    Expected metrics keys (all optional; default 0):
      batch_size: queue rows read this batch (cursor length)
      claim_skipped: claim lost (another worker / race)
      processed: rows completed to DONE
      failed_retry: rows set to FAILED for retry this batch
      dead: rows set to DEAD this batch
    """
    batch = int(metrics.get("batch_size") or 0)
    claim_skipped = int(metrics.get("claim_skipped") or 0)
    processed = int(metrics.get("processed") or 0)
    failed_retry = int(metrics.get("failed_retry") or 0)
    dead = int(metrics.get("dead") or 0)
    reclaim_p = int(metrics.get("stale_running_reclaimed_to_pending") or 0)
    reclaim_d = int(metrics.get("stale_running_reclaimed_to_dead") or 0)
    reclaim_total = reclaim_p + reclaim_d

    claimed = batch - claim_skipped
    operational_fail = failed_retry + dead

    outcome_metrics: Dict[str, Any] = {
        "queue_items_seen_batch": batch,
        "queue_items_claimed": claimed,
        "queue_items_claim_skipped": claim_skipped,
        "queue_items_processed": processed,
        "queue_items_failed": failed_retry,
        "queue_items_dead": dead,
        "stale_running_reclaimed_to_pending": reclaim_p,
        "stale_running_reclaimed_to_dead": reclaim_d,
        "attempted_count": batch,
        "success_count": processed,
        "failed_count": operational_fail,
        "queue_empty": batch == 0 and reclaim_total == 0,
    }

    if batch == 0 and reclaim_total == 0:
        outcome_metrics["outcome_kind"] = "NO_WORK_ELIGIBLE"
        return {
            "message": "Compliance recalc worker: no pending queue items due now.",
            "count": 0,
            "errors": 0,
            "outcome_status": OUTCOME_CONDITIONAL_NO_OUTPUT,
            "outcome_metrics": outcome_metrics,
        }

    if batch == 0 and reclaim_total > 0:
        outcome_metrics["outcome_kind"] = "STALE_RUNNING_RECLAIMED"
        outcome_metrics["queue_empty"] = False
        msg = (
            f"Compliance recalc worker: reclaimed {reclaim_total} stale RUNNING row(s) "
            f"({reclaim_p} to PENDING, {reclaim_d} to DEAD); no pending work due this tick."
        )
        return {
            "message": msg,
            "count": reclaim_total,
            "errors": 0,
            "outcome_status": OUTCOME_SUCCESS,
            "outcome_metrics": outcome_metrics,
        }

    # Saw rows but claimed none — normal contention; not a failure.
    if processed == 0 and operational_fail == 0 and claim_skipped == batch:
        outcome_metrics["outcome_kind"] = "CONTENTION_ONLY"
        return {
            "message": (
                f"Compliance recalc worker: {batch} queue row(s) due but none claimed "
                "(another worker may be processing)."
            ),
            "count": 0,
            "errors": 0,
            "outcome_status": OUTCOME_SUCCESS,
            "outcome_metrics": outcome_metrics,
        }

    if processed > 0 and operational_fail == 0:
        outcome_metrics["outcome_kind"] = "WORK_PERFORMED"
        tail = ""
        if claim_skipped > 0:
            tail = f" {claim_skipped} row(s) skipped (claim not acquired)."
        if reclaim_total > 0:
            tail += f" Reclaimed {reclaim_total} stale RUNNING row(s) ({reclaim_p}→PENDING, {reclaim_d}→DEAD)."
        return {
            "message": (
                f"Compliance recalc worker: {processed} queue item(s) recalculated successfully.{tail}"
            ),
            "count": processed,
            "errors": 0,
            "outcome_status": OUTCOME_SUCCESS,
            "outcome_metrics": outcome_metrics,
        }

    if processed > 0 and operational_fail > 0:
        outcome_metrics["outcome_kind"] = "DEGRADED"
        return {
            "message": (
                f"Compliance recalc worker: {processed} succeeded; "
                f"{failed_retry} queued for retry, {dead} marked DEAD."
            ),
            "count": processed,
            "errors": operational_fail,
            "outcome_status": OUTCOME_DEGRADED,
            "outcome_metrics": outcome_metrics,
            "error_message": (
                f"{operational_fail} queue item(s) failed in this batch "
                f"({dead} DEAD, {failed_retry} retry)."
            ),
        }

    # processed == 0 and operational_fail > 0 (claimed work all failed)
    outcome_metrics["outcome_kind"] = "FAILED"
    return {
        "message": (
            f"Compliance recalc worker: no successful recalcs; "
            f"{failed_retry} retry, {dead} DEAD."
        ),
        "count": 0,
        "errors": operational_fail,
        "outcome_status": OUTCOME_FAILED,
        "outcome_metrics": outcome_metrics,
        "error_code": "COMPLIANCE_RECALC_WORKER_BATCH_ALL_FAILED",
        "error_message": f"All {operational_fail} claimed queue item(s) failed ({dead} DEAD).",
        "stack_trace": None,
    }
