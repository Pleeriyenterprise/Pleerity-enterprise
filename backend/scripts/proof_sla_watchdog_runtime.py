"""
Runtime proof for sla_watchdog only.
Queries: job_runs (sla_watchdog), incidents (open/recent), ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL.
Run from backend: python -m scripts.proof_sla_watchdog_runtime
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
if "MONGO_URL" not in os.environ:
    os.environ["MONGO_URL"] = "mongodb://localhost:27017"
if "DB_NAME" not in os.environ:
    os.environ["DB_NAME"] = "compliance_vault_pro"


async def main():
    from database import database
    try:
        await database.connect()
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return
    db = database.get_db()
    db_name = getattr(db, "name", "?")
    print(f"DB: {db_name}\n")

    # 1) job_runs for sla_watchdog
    print("=" * 60)
    print("1. JOB_RUNS (job_name = 'sla_watchdog')")
    print("=" * 60)
    total_runs = await db.job_runs.count_documents({"job_name": "sla_watchdog"})
    last_run = await db.job_runs.find_one(
        {"job_name": "sla_watchdog"},
        {"_id": 0, "started_at": 1, "finished_at": 1, "status": 1, "run_type": 1, "error_message": 1},
        sort=[("started_at", -1)],
    )
    print(f"  total_runs: {total_runs}")
    if last_run:
        print(f"  last_started_at: {last_run.get('started_at')}")
        print(f"  last_finished_at: {last_run.get('finished_at')}")
        print(f"  last_status: {last_run.get('status')}")
        print(f"  run_type: {last_run.get('run_type')}")
        if last_run.get("error_message"):
            print(f"  error_message: {last_run.get('error_message')}")
    else:
        print("  last_started_at: (none)")
        print("  last_finished_at: (none)")
        print("  last_status: (none)")
        print("  run_type: (none)")

    # 2) Incidents (open + recent from job_monitor / heartbeat / delivery_unknown)
    print("\n" + "=" * 60)
    print("2. INCIDENTS (open, source in job_monitor / heartbeat / delivery_unknown)")
    print("=" * 60)
    cursor = db.incidents.find(
        {"status": "open", "source": {"$in": ["job_monitor", "heartbeat", "delivery_unknown"]}},
        {"_id": 1, "title": 1, "source": 1, "related_job_name": 1, "severity": 1, "created_at": 1},
    ).sort("created_at", -1).limit(20)
    incidents = await cursor.to_list(20)
    if not incidents:
        print("  (none)")
    else:
        for i in incidents:
            print(f"  id={i.get('_id')} title={i.get('title')} source={i.get('source')} related_job_name={i.get('related_job_name')} severity={i.get('severity')} created_at={i.get('created_at')}")

    # 3) Admin alert config
    print("\n" + "=" * 60)
    print("3. ADMIN ALERT CONFIG")
    print("=" * 60)
    admin_emails = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    print(f"  ADMIN_ALERT_EMAILS: {'(set)' if os.getenv('ADMIN_ALERT_EMAILS') else '(not set)'}")
    print(f"  OPS_ALERT_EMAIL: {'(set)' if os.getenv('OPS_ALERT_EMAIL') else '(not set)'}")
    print(f"  Effective recipients: {admin_emails[:80] + '...' if len(admin_emails) > 80 else admin_emails or '(none)'}")

    # 4) Scheduler next_run for sla_watchdog (if available)
    print("\n" + "=" * 60)
    print("4. SCHEDULER next_run_time (sla_watchdog)")
    print("=" * 60)
    try:
        from server import scheduler
        for j in scheduler.get_jobs():
            if getattr(j, "id", None) == "sla_watchdog":
                nrt = getattr(j, "next_run_time", None)
                print(f"  next_run_time: {nrt.isoformat() if nrt else None}")
                break
        else:
            print("  (sla_watchdog not in scheduler.get_jobs())")
    except Exception as e:
        print(f"  (scheduler not available: {e})")

    # 5) Interpretation
    print("\n" + "=" * 60)
    print("5. INTERPRETATION")
    print("=" * 60)
    if total_runs == 0:
        print("  run_count=0: sla_watchdog has not yet written a job_runs row.")
        print("  If next_run_time is in the future => likely 'not yet due' (first run not reached).")
        print("  If next_run_time is in the past => scheduler may not be firing or job fails before start_job_run.")
    else:
        print("  sla_watchdog has run at least once. Last run status and incidents above.")
    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
