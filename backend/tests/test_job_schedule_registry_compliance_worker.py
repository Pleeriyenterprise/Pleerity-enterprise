"""Registry SLA metadata for compliance_recalc_worker (watchdog input)."""


def test_compliance_recalc_worker_max_delay_covers_long_batches():
    from services.job_schedule_registry import get_job_entry

    e = get_job_entry("compliance_recalc_worker")
    assert e is not None
    assert e.max_delay_minutes == 10
