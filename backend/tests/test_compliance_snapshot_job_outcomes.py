"""compliance_snapshot_job_outcomes: job_runs / run_instrumented contract for compliance_score_snapshots."""

from services.compliance_snapshot_job_outcomes import (
    build_compliance_score_snapshots_run_result,
    should_skip_control_centre_no_outcome_flag,
)
from services.job_run_service import (
    OUTCOME_CONDITIONAL_NO_OUTPUT,
    OUTCOME_DEGRADED,
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
)


def test_no_active_clients_conditional_no_output():
    cap = {
        "total_clients": 0,
        "success_count": 0,
        "error_count": 0,
        "errors": [],
    }
    out = build_compliance_score_snapshots_run_result(cap)
    assert out["outcome_status"] == OUTCOME_CONDITIONAL_NO_OUTPUT
    assert out["outcome_metrics"]["no_clients"] is True
    assert out["outcome_metrics"]["outcome_kind"] == "NO_WORK_ELIGIBLE"
    assert out["outcome_metrics"]["queue_empty"] is True


def test_all_clients_succeed_no_property_issues():
    cap = {
        "total_clients": 2,
        "success_count": 2,
        "error_count": 0,
        "errors": [],
        "property_snapshots_created": 5,
        "property_snapshot_failures": 0,
        "property_snapshots_skipped_no_score": 1,
        "property_enumeration_failures": 0,
    }
    out = build_compliance_score_snapshots_run_result(cap)
    assert out["outcome_status"] == OUTCOME_SUCCESS
    assert out["outcome_metrics"]["outcome_kind"] == "WORK_PERFORMED"
    assert out["outcome_metrics"]["clients_succeeded"] == 2
    assert out["outcome_metrics"]["failed_count"] == 0


def test_partial_client_failure_degraded():
    cap = {
        "total_clients": 3,
        "success_count": 2,
        "error_count": 1,
        "errors": [{"client_id": "c1", "error": "boom"}],
        "property_snapshots_created": 4,
        "property_snapshot_failures": 0,
    }
    out = build_compliance_score_snapshots_run_result(cap)
    assert out["outcome_status"] == OUTCOME_DEGRADED
    assert out["outcome_metrics"]["outcome_kind"] == "DEGRADED"
    assert out["outcome_metrics"]["failed_count"] == 1


def test_property_snapshot_failures_degraded():
    cap = {
        "total_clients": 1,
        "success_count": 1,
        "error_count": 0,
        "property_snapshots_created": 0,
        "property_snapshot_failures": 2,
        "property_snapshots_skipped_no_score": 0,
    }
    out = build_compliance_score_snapshots_run_result(cap)
    assert out["outcome_status"] == OUTCOME_DEGRADED
    assert out["outcome_metrics"]["property_snapshot_failures"] == 2
    assert out["outcome_metrics"]["failed_count"] == 2


def test_property_enumeration_failure_degraded():
    cap = {
        "total_clients": 1,
        "success_count": 1,
        "error_count": 0,
        "property_snapshots_created": 0,
        "property_snapshot_failures": 0,
        "property_enumeration_failures": 1,
    }
    out = build_compliance_score_snapshots_run_result(cap)
    assert out["outcome_status"] == OUTCOME_DEGRADED
    assert out["outcome_metrics"]["failed_count"] == 1


def test_all_clients_portfolio_failed():
    cap = {
        "total_clients": 2,
        "success_count": 0,
        "error_count": 2,
        "errors": [{"client_id": "a", "error": "e1"}, {"client_id": "b", "error": "e2"}],
        "property_snapshots_created": 0,
        "property_snapshot_failures": 0,
    }
    out = build_compliance_score_snapshots_run_result(cap)
    assert out["outcome_status"] == OUTCOME_FAILED
    assert out["outcome_metrics"]["outcome_kind"] == "FAILED"
    assert out["error_code"] == "COMPLIANCE_SCORE_SNAPSHOTS_ALL_CLIENTS_FAILED"


def test_control_centre_skip_flag_no_clients():
    detail = {
        "last_outcome_status": "conditional_no_output",
        "last_run_status": "success",
        "outcome_metrics": {"no_clients": True, "attempted_count": 0, "success_count": 0},
    }
    assert should_skip_control_centre_no_outcome_flag("compliance_score_snapshots", detail) is True
    assert should_skip_control_centre_no_outcome_flag("daily_reminders", detail) is False


def test_metrics_keys_present():
    cap = {
        "total_clients": 1,
        "success_count": 1,
        "error_count": 0,
        "property_snapshots_created": 1,
        "property_snapshot_failures": 0,
        "property_snapshots_skipped_no_score": 0,
        "property_enumeration_failures": 0,
    }
    om = build_compliance_score_snapshots_run_result(cap)["outcome_metrics"]
    for k in (
        "clients_considered",
        "clients_succeeded",
        "clients_failed",
        "property_snapshots_created",
        "property_snapshot_failures",
        "attempted_count",
        "success_count",
        "failed_count",
    ):
        assert k in om
