"""compliance_recalc_worker job_runs outcome classification."""

from services.compliance_recalc_worker_job_outcomes import (
    build_compliance_recalc_worker_run_result,
    should_skip_control_centre_no_outcome_flag_recalc,
)
from services.job_run_service import OUTCOME_CONDITIONAL_NO_OUTPUT, OUTCOME_DEGRADED, OUTCOME_FAILED, OUTCOME_SUCCESS


def test_empty_queue_conditional_no_output():
    out = build_compliance_recalc_worker_run_result(
        {"batch_size": 0, "claim_skipped": 0, "processed": 0, "failed_retry": 0, "dead": 0}
    )
    assert out["outcome_status"] == OUTCOME_CONDITIONAL_NO_OUTPUT
    assert out["outcome_metrics"]["queue_empty"] is True
    assert out["outcome_metrics"]["outcome_kind"] == "NO_WORK_ELIGIBLE"


def test_contention_only_success():
    out = build_compliance_recalc_worker_run_result(
        {"batch_size": 3, "claim_skipped": 3, "processed": 0, "failed_retry": 0, "dead": 0}
    )
    assert out["outcome_status"] == OUTCOME_SUCCESS
    assert out["outcome_metrics"]["outcome_kind"] == "CONTENTION_ONLY"
    assert out["outcome_metrics"]["queue_items_claim_skipped"] == 3


def test_all_processed_success():
    out = build_compliance_recalc_worker_run_result(
        {"batch_size": 2, "claim_skipped": 0, "processed": 2, "failed_retry": 0, "dead": 0}
    )
    assert out["outcome_status"] == OUTCOME_SUCCESS
    assert out["outcome_metrics"]["outcome_kind"] == "WORK_PERFORMED"
    assert out["count"] == 2


def test_partial_failure_degraded():
    out = build_compliance_recalc_worker_run_result(
        {"batch_size": 3, "claim_skipped": 0, "processed": 2, "failed_retry": 1, "dead": 0}
    )
    assert out["outcome_status"] == OUTCOME_DEGRADED
    assert out["outcome_metrics"]["outcome_kind"] == "DEGRADED"
    assert out["outcome_metrics"]["failed_count"] == 1


def test_all_claimed_failed_batch_failed():
    out = build_compliance_recalc_worker_run_result(
        {"batch_size": 2, "claim_skipped": 0, "processed": 0, "failed_retry": 1, "dead": 1}
    )
    assert out["outcome_status"] == OUTCOME_FAILED
    assert out["outcome_metrics"]["outcome_kind"] == "FAILED"


def test_metrics_claim_skipped_not_processed():
    out = build_compliance_recalc_worker_run_result(
        {"batch_size": 4, "claim_skipped": 2, "processed": 2, "failed_retry": 0, "dead": 0}
    )
    assert out["outcome_status"] == OUTCOME_SUCCESS
    om = out["outcome_metrics"]
    assert om["queue_items_claimed"] == 2
    assert om["queue_items_claim_skipped"] == 2
    assert om["queue_items_processed"] == 2


def test_control_centre_skip_empty_queue():
    detail = {
        "last_outcome_status": OUTCOME_CONDITIONAL_NO_OUTPUT,
        "last_run_status": "success",
        "outcome_metrics": {"queue_empty": True},
    }
    assert should_skip_control_centre_no_outcome_flag_recalc("compliance_recalc_worker", detail) is True
    assert should_skip_control_centre_no_outcome_flag_recalc("daily_reminders", detail) is False


def test_no_misleading_success_when_partial_failures():
    out = build_compliance_recalc_worker_run_result(
        {"batch_size": 1, "claim_skipped": 0, "processed": 0, "failed_retry": 1, "dead": 0}
    )
    assert out["outcome_status"] != OUTCOME_SUCCESS
