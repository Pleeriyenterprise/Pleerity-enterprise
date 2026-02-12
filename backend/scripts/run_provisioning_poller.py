"""
Lightweight poller for provisioning_jobs: processes PAYMENT_CONFIRMED (and runnable) jobs.

Webhook only persists state and returns 200; this script is the reliable dispatch.
Run via cron in production (e.g. every 1–2 minutes).

Usage (from backend/):
  python -m scripts.run_provisioning_poller
  python -m scripts.run_provisioning_poller --once   # process one batch and exit (default)
  python -m scripts.run_provisioning_poller --max-jobs 5

Production (cron example):
  */2 * * * * cd /app/backend && python -m scripts.run_provisioning_poller --max-jobs 10
"""
import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
from models import ProvisioningJobStatus


async def poll_once(max_jobs: int = 20) -> int:
    """
    Find jobs with needs_run=True and lock free; run each (runner acquires lock atomically).
    Returns number of jobs processed.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    cursor = db.provisioning_jobs.find(
        {
            "$and": [
                {"$or": [{"needs_run": True}, {"needs_run": {"$exists": False}}]},
                {
                    "$or": [
                        {"locked_until": None},
                        {"locked_until": {"$exists": False}},
                        {"locked_until": {"$lt": now}},
                    ]
                },
                {
                    "status": {
                        "$in": [
                            ProvisioningJobStatus.PAYMENT_CONFIRMED.value,
                            ProvisioningJobStatus.PROVISIONING_STARTED.value,
                            ProvisioningJobStatus.PROVISIONING_COMPLETED.value,
                            ProvisioningJobStatus.FAILED.value,
                        ]
                    }
                },
            ],
        },
        {"_id": 0, "job_id": 1},
    ).limit(max_jobs)
    jobs = await cursor.to_list(length=max_jobs)
    if not jobs:
        return 0
    from services.provisioning_runner import run_provisioning_job
    processed = 0
    for row in jobs:
        job_id = row["job_id"]
        try:
            await run_provisioning_job(job_id)
            processed += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Poller run_provisioning_job %s: %s", job_id, e)
    return processed


def main():
    parser = argparse.ArgumentParser(description="Run provisioning job poller (PAYMENT_CONFIRMED jobs)")
    parser.add_argument("--max-jobs", type=int, default=20, help="Max jobs per run (default 20)")
    args = parser.parse_args()

    async def _():
        await database.connect()
        try:
            n = await poll_once(max_jobs=args.max_jobs)
            print(f"Processed {n} job(s)")
            return 0
        finally:
            await database.close()

    return asyncio.run(_())


if __name__ == "__main__":
    sys.exit(main())
