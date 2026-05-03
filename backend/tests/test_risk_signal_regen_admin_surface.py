"""risk_signal_regen_admin_surface: Control Centre guardrails and health-summary copy."""
from services.job_schedule_registry import JOB_STATE_DEGRADED, JOB_STATE_FAILED, JOB_STATE_HEALTHY
from services.risk_signal_regen_admin_surface import (
    health_summary_reason_override,
    should_skip_no_expected_outcome_flag,
)


def test_skip_no_outcome_flag_queue_empty_conditional():
    detail = {
        "last_outcome_status": "conditional_no_output",
        "last_run_status": "success",
        "outcome_metrics": {"queue_empty": True, "attempted_count": 0},
    }
    assert should_skip_no_expected_outcome_flag("risk_signal_regen_worker", detail) is True


def test_skip_no_outcome_flag_not_when_flag_skips_only():
    detail = {
        "last_outcome_status": "conditional_no_output",
        "last_run_status": "success",
        "outcome_metrics": {"queue_empty": False, "attempted_count": 1, "skipped_feature_flag_count": 1},
    }
    assert should_skip_no_expected_outcome_flag("risk_signal_regen_worker", detail) is False


def test_skip_no_outcome_flag_not_for_other_jobs_even_if_pattern_matches():
    """Future workers must opt in explicitly; same metrics shape must not suppress flags."""
    detail = {
        "last_outcome_status": "conditional_no_output",
        "last_run_status": "success",
        "outcome_metrics": {"queue_empty": True, "attempted_count": 0},
    }
    assert should_skip_no_expected_outcome_flag("hypothetical_queue_worker", detail) is False


def test_health_reason_queue_empty():
    detail = {
        "last_outcome_status": "conditional_no_output",
        "outcome_metrics": {"queue_empty": True, "regenerated_count": 0},
    }
    r = health_summary_reason_override("risk_signal_regen_worker", JOB_STATE_HEALTHY, detail)
    assert r and "waiting" in r.lower()


def test_health_reason_flag_skips_only():
    detail = {
        "last_outcome_status": "conditional_no_output",
        "outcome_metrics": {
            "queue_empty": False,
            "skipped_feature_flag_count": 2,
            "regenerated_count": 0,
            "failed_count": 0,
        },
    }
    r = health_summary_reason_override("risk_signal_regen_worker", JOB_STATE_HEALTHY, detail)
    assert r and "predictive maintenance" in r.lower()
    assert "2" in r


def test_health_reason_refreshed():
    detail = {
        "last_outcome_status": "success",
        "outcome_metrics": {"regenerated_count": 3, "skipped_feature_flag_count": 0},
    }
    r = health_summary_reason_override("risk_signal_regen_worker", JOB_STATE_HEALTHY, detail)
    assert r and "3" in r and "refreshed" in r.lower()


def test_health_reason_degraded():
    detail = {
        "last_outcome_status": "degraded",
        "outcome_metrics": {"regenerated_count": 1, "failed_count": 2, "skipped_feature_flag_count": 0},
    }
    r = health_summary_reason_override("risk_signal_regen_worker", JOB_STATE_DEGRADED, detail)
    assert r and "failed" in r.lower() and "1" in r


def test_health_reason_failed():
    detail = {"last_outcome_status": "failed", "outcome_metrics": {"failed_count": 3}}
    r = health_summary_reason_override("risk_signal_regen_worker", JOB_STATE_FAILED, detail)
    assert r and "3" in r and "failed" in r.lower()


def test_health_reason_override_only_regen_job():
    assert health_summary_reason_override("daily_reminders", JOB_STATE_HEALTHY, {}) is None
