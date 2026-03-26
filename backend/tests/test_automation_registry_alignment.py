import re
from pathlib import Path

from services.job_schedule_registry import ALL_JOB_IDS_FOR_HEALTH
from job_runner import JOB_RUNNERS


def _scheduled_job_ids_from_server() -> set[str]:
    server_path = Path(__file__).resolve().parent.parent / "server.py"
    text = server_path.read_text(encoding="utf-8")
    return set(re.findall(r'id="([a-z_]+)"', text))


def test_all_scheduled_jobs_are_in_health_registry():
    scheduled = _scheduled_job_ids_from_server()
    registry_ids = set(ALL_JOB_IDS_FOR_HEALTH)
    assert scheduled == registry_ids


def test_all_scheduled_jobs_are_runnable():
    scheduled = _scheduled_job_ids_from_server()
    runnable = set(JOB_RUNNERS.keys())
    assert scheduled.issubset(runnable)
