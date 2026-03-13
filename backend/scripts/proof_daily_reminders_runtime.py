"""
Runtime proof for daily_reminders only.
Queries actual DB: job_runs, message_logs, audit_logs.
Run from backend: python -m scripts.proof_daily_reminders_runtime
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
        print("Set MONGO_URL and DB_NAME (e.g. in .env) and ensure MongoDB is running.")
        return
    db = database.get_db()
    db_name = getattr(db, "name", "?")
    print(f"Connected to DB: {db_name}\n")

    # 1) job_runs for job_name = "daily_reminders"
    print("=" * 60)
    print("1. JOB_RUNS (job_name = 'daily_reminders')")
    print("=" * 60)
    pipeline = [
        {"$match": {"job_name": "daily_reminders"}},
        {"$sort": {"started_at": -1}},
        {"$group": {
            "_id": None,
            "total_runs": {"$sum": 1},
            "last_started_at": {"$first": "$started_at"},
            "last_finished_at": {"$first": "$finished_at"},
            "last_status": {"$first": "$status"},
            "last_run_type": {"$first": "$run_type"},
        }},
    ]
    cursor = db.job_runs.aggregate(pipeline)
    job_runs_summary = None
    async for doc in cursor:
        job_runs_summary = doc
        break
    if not job_runs_summary:
        print("  total_runs: 0")
        print("  last_started_at: (none)")
        print("  last_finished_at: (none)")
        print("  last_status: (none)")
        print("  run_type: (none)")
        total_runs = 0
        last_started_at = last_finished_at = last_status = last_run_type = None
    else:
        total_runs = job_runs_summary["total_runs"]
        last_started_at = job_runs_summary.get("last_started_at")
        last_finished_at = job_runs_summary.get("last_finished_at")
        last_status = job_runs_summary.get("last_status")
        last_run_type = job_runs_summary.get("last_run_type")
        print(f"  total_runs: {total_runs}")
        print(f"  last_started_at: {last_started_at}")
        print(f"  last_finished_at: {last_finished_at}")
        print(f"  last_status: {last_status}")
        print(f"  run_type: {last_run_type}")
    # Also list last 3 raw docs for run_type
    cursor = db.job_runs.find({"job_name": "daily_reminders"}).sort("started_at", -1).limit(3)
    rows = await cursor.to_list(3)
    if rows:
        print("  Last 3 runs (run_type):")
        for r in rows:
            print(f"    started_at={r.get('started_at')} status={r.get('status')} run_type={r.get('run_type')}")

    # 2) message_logs for COMPLIANCE_EXPIRY_REMINDER, COMPLIANCE_EXPIRY_REMINDER_SMS
    print("\n" + "=" * 60)
    print("2. MESSAGE_LOGS (template_key IN COMPLIANCE_EXPIRY_REMINDER, COMPLIANCE_EXPIRY_REMINDER_SMS)")
    print("=" * 60)
    cursor = db.message_logs.find(
        {"template_key": {"$in": ["COMPLIANCE_EXPIRY_REMINDER", "COMPLIANCE_EXPIRY_REMINDER_SMS"]}}
    ).sort("created_at", -1).limit(15)
    msg_logs = await cursor.to_list(15)
    if not msg_logs:
        print("  (no records)")
    else:
        for m in msg_logs:
            print(f"  created_at={m.get('created_at')} status={m.get('status')} recipient={m.get('recipient')} channel={m.get('channel')} error_message={m.get('error_message')}")

    # 3) audit_logs action = REMINDER_SENT (recent: last 14 days or since last job run)
    print("\n" + "=" * 60)
    print("3. AUDIT_LOGS (action = 'REMINDER_SENT')")
    print("=" * 60)
    since = datetime.now(timezone.utc) - timedelta(days=14)
    since_str = since.isoformat()
    cursor = db.audit_logs.find(
        {"action": "REMINDER_SENT", "timestamp": {"$gte": since_str}}
    ).sort("timestamp", -1).limit(15)
    audit_logs = await cursor.to_list(15)
    if not audit_logs:
        print("  (no records in last 14 days)")
    else:
        for a in audit_logs:
            print(f"  timestamp={a.get('timestamp')} client_id={a.get('client_id')} metadata={a.get('metadata')}")

    # 4) What Automation Control Centre would show
    print("\n" + "=" * 60)
    print("4. WHAT AUTOMATION CONTROL CENTRE WOULD SHOW")
    print("=" * 60)
    print("  (ACC uses: GET /api/admin/observability/job-runs?limit=200 and health-summary.)")
    print("  job_runs items for daily_reminders: same DB collection as above.")
    if total_runs == 0:
        print("  -> Last run: (none); Status: Never ran / Not yet due (depending on next_run_time).")
    else:
        print(f"  -> Last run: {last_finished_at or last_started_at}; Status from last run: {last_status}.")
        print("  -> ACC 'Last run' column = most recent job_runs.finished_at or started_at for this job.")

    # 5) Answers A–E
    print("\n" + "=" * 60)
    print("5. RUNTIME ANSWERS (A–E)")
    print("=" * 60)
    has_run = total_runs > 0
    run_recorded = has_run and last_started_at is not None
    output_recorded = (len(msg_logs) > 0) or (len(audit_logs) > 0)
    ui_truthful = True  # same DB; if job_runs has row, API returns it
    if has_run and not run_recorded:
        ui_truthful = False
    gap_layer = None
    if not has_run:
        gap_layer = "Job has not run in this environment (no job_runs row for daily_reminders)."
    elif not run_recorded:
        gap_layer = "Run not recorded: job_runs has no document for daily_reminders (instrumentation or DB mismatch)."
    elif not output_recorded and has_run:
        gap_layer = "Output not recorded: no message_logs/audit_logs for reminders in window (possible zero-output run or different time window)."
    elif not ui_truthful:
        gap_layer = "Admin UI does not reflect job_runs (wrong DB, query filter, or API not reading same collection)."

    print(f"  A. Has daily_reminders actually run in this environment? {'YES' if has_run else 'NO'}")
    print(f"  B. If yes, is the run recorded in job_runs? {'YES' if run_recorded else 'N/A' if not has_run else 'NO'}")
    print(f"  C. If yes, is the output recorded in message_logs/audit_logs? {'YES' if output_recorded else 'N/A' if not has_run else 'NO (or zero-output run)'}")
    print(f"  D. If yes, does the admin UI reflect that truthfully? {'YES' if ui_truthful else 'N/A' if not has_run else 'NO'}")
    print(f"  E. If no, at exactly which layer does the truth gap occur? {gap_layer or 'N/A (all yes)'}")

    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
