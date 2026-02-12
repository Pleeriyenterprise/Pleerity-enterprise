"""
Retry a provisioning job (failed or resend invite only).

Usage (from backend/):
  python -m scripts.retry_provisioning_job --job-id <job_id>
  python -m scripts.retry_provisioning_job --client-id <client_id>   # finds latest job for client
  python -m scripts.retry_provisioning_job --resend-invite --job-id <job_id>  # email-only for PROVISIONING_COMPLETED
"""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
from models import ProvisioningJobStatus


async def run(job_id: str = None, client_id: str = None, resend_invite_only: bool = False) -> bool:
    from services.provisioning_runner import run_provisioning_job

    db = database.get_db()
    if not job_id and client_id:
        job = await db.provisioning_jobs.find_one(
            {"client_id": client_id},
            {"_id": 0, "job_id": 1, "status": 1},
            sort=[("created_at", -1)]
        )
        if not job:
            print(f"No provisioning job found for client_id={client_id}")
            return False
        job_id = job["job_id"]
        print(f"Using job_id={job_id} (status={job.get('status')})")
    if not job_id:
        print("Provide --job-id or --client-id")
        return False
    if resend_invite_only:
        job = await db.provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0, "status": 1})
        if not job or job.get("status") != ProvisioningJobStatus.PROVISIONING_COMPLETED.value:
            print(f"Job {job_id} must be PROVISIONING_COMPLETED for --resend-invite")
            return False
    ok = await run_provisioning_job(job_id)
    job_after = await db.provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0, "status": 1})
    print(f"Job {job_id} status after run: {job_after.get('status')}")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Retry provisioning job or resend invite")
    parser.add_argument("--job-id", help="Provisioning job ID")
    parser.add_argument("--client-id", help="Client ID (use latest job for this client)")
    parser.add_argument("--resend-invite", action="store_true", help="Only resend welcome email (job must be PROVISIONING_COMPLETED)")
    args = parser.parse_args()

    async def _():
        await database.connect()
        try:
            return await run(
                job_id=args.job_id,
                client_id=args.client_id,
                resend_invite_only=args.resend_invite,
            )
        finally:
            await database.close()

    ok = asyncio.run(_())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
