"""
Runtime verification of the automation system.
Queries the database and (if available) scheduler state — no code analysis.

Run from backend root:
  python -m scripts.verify_automation_runtime
  or: python scripts/verify_automation_runtime.py (with PYTHONPATH=.)
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load env before importing app modules
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
# Allow running without .env (e.g. local MongoDB)
if "MONGO_URL" not in os.environ:
    os.environ["MONGO_URL"] = "mongodb://localhost:27017"
if "DB_NAME" not in os.environ:
    os.environ["DB_NAME"] = "compliance_vault_pro"


async def main():
    from database import database
    from services.job_schedule_registry import ALL_JOB_IDS_FOR_HEALTH
    from services.incident_service import (
        SOURCE_JOB_MONITOR,
        SOURCE_HEARTBEAT,
        SOURCE_DELIVERY_UNKNOWN,
    )

    await database.connect()
    db = database.get_db()

    # 1) job_runs: per job_name -> total_runs, last_started_at, last_finished_at, last_status
    pipeline = [
        {"$sort": {"finished_at": -1, "started_at": -1}},
        {"$group": {
            "_id": "$job_name",
            "total_runs": {"$sum": 1},
            "last_started_at": {"$first": "$started_at"},
            "last_finished_at": {"$first": "$finished_at"},
            "last_status": {"$first": "$status"},
        }},
    ]
    cursor = db.job_runs.aggregate(pipeline)
    job_runs_by_name = {}
    async for doc in cursor:
        job_runs_by_name[doc["_id"]] = {
            "total_runs": doc["total_runs"],
            "last_started_at": doc.get("last_started_at"),
            "last_finished_at": doc.get("last_finished_at"),
            "last_status": doc.get("last_status"),
        }

    # 2) scheduled_jobs (APScheduler MongoDB store): job_id, next_run_time, trigger
    # APScheduler stores: _id (job_id), next_run_time (UTC timestamp number), job_state (pickled)
    scheduled_jobs_list = []
    try:
        cursor = db.scheduled_jobs.find({}, {"_id": 1, "next_run_time": 1})
        async for doc in cursor:
            job_id = doc.get("_id")
            if not isinstance(job_id, str):
                job_id = str(job_id) if job_id is not None else None
            next_run = doc.get("next_run_time")
            if next_run is not None:
                # APScheduler stores UTC timestamp (seconds from epoch)
                if isinstance(next_run, (int, float)):
                    next_run_dt = datetime.fromtimestamp(next_run, tz=timezone.utc)
                    next_run = next_run_dt.isoformat()
                elif hasattr(next_run, "isoformat"):
                    next_run = next_run.isoformat()
                else:
                    next_run = str(next_run)
            scheduled_jobs_list.append({
                "job_id": job_id,
                "next_run_time": next_run,
                "trigger": "see job_state (pickled)",
            })
    except Exception as e:
        scheduled_jobs_list = [{"error": str(e)}]

    scheduled_by_id = {s["job_id"]: s for s in scheduled_jobs_list if s.get("job_id") and "error" not in s}

    # 3) Registry vs job_runs: jobs with zero executions
    registry_job_ids = list(ALL_JOB_IDS_FOR_HEALTH)
    zero_run_jobs = [jid for jid in registry_job_ids if job_runs_by_name.get(jid, {}).get("total_runs", 0) == 0]

    # 4) Why zero-run jobs never ran (heuristic: next_run in future vs not in scheduler vs other)
    now = datetime.now(timezone.utc)
    reasons = {}
    for jid in zero_run_jobs:
        sch = scheduled_by_id.get(jid)
        if not sch:
            reasons[jid] = "not_in_scheduled_jobs_or_scheduler_never_started"
            continue
        nrt = sch.get("next_run_time")
        if not nrt:
            reasons[jid] = "next_run_time_null_or_missing"
            continue
        try:
            if isinstance(nrt, str):
                dt = datetime.fromisoformat(nrt.replace("Z", "+00:00"))
            else:
                dt = nrt
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt > now:
                reasons[jid] = "next_run_time_still_in_future"
            else:
                reasons[jid] = "scheduler_may_not_have_triggered_or_runtime_error_before_instrumentation"
        except Exception:
            reasons[jid] = "could_not_parse_next_run_time"

    # 5) Open incidents: missed job runs, stale heartbeat, delivery_unknown_stale
    open_incidents = []
    cursor = db.incidents.find({
        "status": "open",
        "source": {"$in": [SOURCE_JOB_MONITOR, SOURCE_HEARTBEAT, SOURCE_DELIVERY_UNKNOWN]},
    }, {"_id": 1, "title": 1, "source": 1, "related_job_name": 1, "created_at": 1})
    async for doc in cursor:
        open_incidents.append({
            "id": str(doc["_id"]),
            "title": doc.get("title"),
            "source": doc.get("source"),
            "related_job_name": doc.get("related_job_name"),
            "created_at": doc.get("created_at"),
        })

    # 6) ADMIN_ALERT_EMAILS
    admin_emails = os.environ.get("ADMIN_ALERT_EMAILS") or os.environ.get("OPS_ALERT_EMAIL") or ""
    admin_alert_configured = bool(admin_emails.strip())

    # Build output table: job_name, registered, next_run_time, run_count, last_run, status, issue
    rows = []
    for job_name in registry_job_ids:
        runs = job_runs_by_name.get(job_name, {})
        total = runs.get("total_runs", 0)
        last_finished = runs.get("last_finished_at") or runs.get("last_started_at")
        last_status = runs.get("last_status") or ""
        sch = scheduled_by_id.get(job_name)
        registered = "yes" if sch or job_name in [s.get("job_id") for s in scheduled_jobs_list if s.get("job_id")] else "no"
        next_run = (sch or {}).get("next_run_time") if sch else None
        if not next_run and scheduled_jobs_list and "error" in scheduled_jobs_list[0]:
            next_run = "N/A (store error)"
        elif not next_run:
            next_run = "N/A"

        issue = ""
        if total == 0:
            issue = reasons.get(job_name, "no_run_recorded")
        elif last_status == "failed":
            issue = "last_run_failed"

        rows.append({
            "job_name": job_name,
            "registered": registered,
            "next_run_time": next_run,
            "run_count": total,
            "last_run": last_finished,
            "status": last_status or "—",
            "issue": issue or "—",
        })

    # Print report
    print("=" * 100)
    print("1. JOB_RUNS (per job_name)")
    print("=" * 100)
    for jid in registry_job_ids:
        r = job_runs_by_name.get(jid, {})
        print(f"  {jid}: total_runs={r.get('total_runs', 0)}, last_started_at={r.get('last_started_at')}, last_finished_at={r.get('last_finished_at')}, last_status={r.get('last_status')}")

    print("\n" + "=" * 100)
    print("2. SCHEDULED_JOBS (APScheduler store)")
    print("=" * 100)
    for s in scheduled_jobs_list:
        if "error" in s:
            print(f"  Error: {s['error']}")
        else:
            print(f"  job_id={s.get('job_id')}, next_run_time={s.get('next_run_time')}, trigger={s.get('trigger')}")

    print("\n" + "=" * 100)
    print("3. ZERO-EXECUTION JOBS (registry vs job_runs)")
    print("=" * 100)
    print(f"  Jobs with zero runs: {zero_run_jobs}")

    print("\n" + "=" * 100)
    print("4. WHY ZERO-RUN JOBS NEVER RAN")
    print("=" * 100)
    for jid in zero_run_jobs:
        print(f"  {jid}: {reasons.get(jid, 'unknown')}")

    print("\n" + "=" * 100)
    print("5. OPEN INCIDENTS (missed / heartbeat / delivery_unknown)")
    print("=" * 100)
    for inc in open_incidents:
        print(f"  {inc.get('id')}: source={inc.get('source')}, title={inc.get('title')}, related_job={inc.get('related_job_name')}")

    print("\n" + "=" * 100)
    print("6. ADMIN_ALERT_EMAILS")
    print("=" * 100)
    print(f"  Configured: {admin_alert_configured}  (ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL)")

    print("\n" + "=" * 100)
    print("TABLE: job_name | registered | next_run_time | run_count | last_run | status | issue")
    print("=" * 100)
    for r in rows:
        print(f"  {r['job_name']}\t{r['registered']}\t{r['next_run_time']}\t{r['run_count']}\t{r['last_run']}\t{r['status']}\t{r['issue']}")
    # Markdown table for report
    print("\n--- Markdown table ---")
    print("| job_name | registered | next_run_time | run_count | last_run | status | issue |")
    print("|----------|------------|---------------|-----------|----------|--------|-------|")
    for r in rows:
        nr = str(r["next_run_time"])[:19] if r["next_run_time"] else "—"
        lr = str(r["last_run"])[:19] if r["last_run"] else "—"
        print(f"| {r['job_name']} | {r['registered']} | {nr} | {r['run_count']} | {lr} | {r['status']} | {r['issue']} |")

    await database.close()
    return {
        "job_runs_by_name": job_runs_by_name,
        "scheduled_jobs": scheduled_jobs_list,
        "zero_run_jobs": zero_run_jobs,
        "reasons": reasons,
        "open_incidents": open_incidents,
        "admin_alert_configured": admin_alert_configured,
        "table": rows,
    }


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
    except Exception as e:
        if "MongoDB" in str(e) or "MONGO" in str(e) or "connection" in str(e).lower() or "refused" in str(e).lower():
            print("MongoDB not available. Set MONGO_URL and DB_NAME (or use defaults) and ensure MongoDB is running.")
            print("Table format: job_name | registered | next_run_time | run_count | last_run | status | issue")
            print("Example: daily_reminders | yes | 2026-02-21T09:00:00 | 5 | 2026-02-20T09:00:00 | success | —")
        raise
