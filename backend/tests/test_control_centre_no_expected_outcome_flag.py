"""Control Centre no-expected-outcome flag: legacy telemetry vs structured outcomes."""
from services.control_centre_no_expected_outcome_flag import (
    detail_has_structured_outcome_telemetry,
    should_flag_no_expected_outcome_control_centre,
)
from services.job_schedule_registry import (
    JOB_STATE_DEGRADED,
    JOB_STATE_FAILED,
    JOB_STATE_HEALTHY,
)


def _flag(jid, *, z=False, st=JOB_STATE_HEALTHY, detail=None):
    return should_flag_no_expected_outcome_control_centre(
        jid,
        zero_output_ok=z,
        job_state=st,
        detail=detail or {},
    )


def test_legacy_success_missing_outcome_not_flagged():
    detail = {
        "last_run_status": "success",
        "last_outcome_status": None,
        "outcome_metrics": {},
        "last_completed": "2024-01-01T00:00:00+00:00",
    }
    assert detail_has_structured_outcome_telemetry(detail) is False
    assert _flag("compliance_recalc_worker", detail=detail) is False


def test_legacy_success_no_metrics_key_not_flagged():
    detail = {
        "last_run_status": "success",
        "outcome_metrics": None,
    }
    assert _flag("expiry_rollover_recalc", detail=detail) is False


def test_structured_no_work_recalc_skipped():
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "conditional_no_output",
        "outcome_metrics": {"queue_empty": True, "attempted_count": 0, "success_count": 0},
    }
    assert _flag("compliance_recalc_worker", detail=detail) is False


def test_structured_snapshots_no_clients_skipped():
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "conditional_no_output",
        "outcome_metrics": {
            "no_clients": True,
            "queue_empty": True,
            "attempted_count": 0,
            "success_count": 0,
            "clients_considered": 0,
        },
    }
    assert _flag("compliance_score_snapshots", detail=detail) is False


def test_structured_suspicious_success_still_flagged():
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "success",
        "outcome_metrics": {
            "attempted_count": 0,
            "success_count": 0,
            "queue_empty": False,
            "failed_count": 0,
        },
    }
    assert detail_has_structured_outcome_telemetry(detail) is True
    assert _flag("expiry_rollover_recalc", detail=detail) is True


def test_risk_regen_empty_queue_skipped():
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "conditional_no_output",
        "outcome_metrics": {"queue_empty": True, "attempted_count": 0, "regenerated_count": 0},
    }
    assert _flag("risk_signal_regen_worker", detail=detail) is False


def test_degraded_not_flagged():
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "success",
        "outcome_metrics": {"attempted_count": 0, "success_count": 0},
    }
    assert _flag("daily_reminders", st=JOB_STATE_DEGRADED, detail=detail) is False


def test_failed_state_not_flagged():
    detail = {
        "last_run_status": "failed",
        "outcome_metrics": {"attempted_count": 0, "success_count": 0},
    }
    assert _flag("daily_reminders", st=JOB_STATE_FAILED, detail=detail) is False


def test_zero_output_ok_registry_not_flagged():
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "success",
        "outcome_metrics": {"attempted_count": 0, "success_count": 0},
    }
    assert _flag("daily_reminders", z=True, detail=detail) is False


def test_outcome_status_only_triggers_telemetry_then_zero_counts_flags():
    """Non-empty last_outcome_status counts as structured; suspicious zero work still flags if no skip."""
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "success",
        "outcome_metrics": {},
    }
    assert detail_has_structured_outcome_telemetry(detail) is True
    assert _flag("expiry_rollover_recalc", detail=detail) is True


def test_detail_has_structured_true_when_metric_key_present():
    assert detail_has_structured_outcome_telemetry({"outcome_metrics": {"attempted_count": 0}}) is True
