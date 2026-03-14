"""
Verify incident auto-recovery logic: list open incidents and detect which would be auto-resolved.
Helps validate that recovery conditions (heartbeat fresh, no delivery_unknown stale, job ran successfully) are applied correctly.

Run from backend root:
  python -m scripts.verify_automation_recovery
  or: python scripts/verify_automation_recovery.py (with PYTHONPATH=.)
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
    from services.incident_service import SOURCE_JOB_MONITOR, SOURCE_HEARTBEAT, SOURCE_DELIVERY_UNKNOWN
    from services.incident_recovery import compute_recovery_state_for_incident
    from services.job_run_service import COLLECTION as JOB_RUNS_COLLECTION, STATUS_SUCCESS, STATUS_DEGRADED

    await database.connect()
    db = database.get_db()

    # 1) Open / acknowledged incidents
    cursor = db.incidents.find(
        {"status": {"$in": ["open", "acknowledged"]}},
        {"_id": 1, "title": 1, "source": 1, "related_job_name": 1, "created_at": 1, "metadata": 1},
    ).sort("created_at", -1)
    incidents = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        incidents.append(doc)

    # 2) For each incident, compute recovery state (would it be auto-resolved?)
    print("=" * 80)
    print("OPEN / ACKNOWLEDGED INCIDENTS AND RECOVERY STATE")
    print("=" * 80)
    if not incidents:
        print("No open or acknowledged incidents.")
    else:
        for inc in incidents:
            inc_id = inc.get("id", "")
            title = inc.get("title", "")
            source = inc.get("source", "")
            job_name = inc.get("related_job_name", "")
            created = inc.get("created_at", "")
            state = await compute_recovery_state_for_incident(inc)
            inc["_recovery_state"] = state
            recovery = state.get("recovery_detected", False)
            hint = state.get("recovery_hint", "")
            print(f"\n  Incident: {inc_id}")
            print(f"    Title: {title}")
            print(f"    Source: {source}  Related job: {job_name or '—'}")
            print(f"    Created: {created}")
            print(f"    Recovery detected: {recovery}")
            if hint:
                print(f"    Hint: {hint}")
            if state.get("last_success"):
                print(f"    Last success (job): {state['last_success']}")
            if state.get("expected_interval"):
                print(f"    Expected interval: {state['expected_interval']}")
            if recovery:
                print("    -> Would be auto-resolved by recovery logic (or next sla_watchdog / job completion).")

    # 3) Recent job runs (last 24h) summary
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat()
    recent = await db[JOB_RUNS_COLLECTION].find(
        {"finished_at": {"$gte": since}},
        {"_id": 0, "job_name": 1, "finished_at": 1, "status": 1},
    ).sort("finished_at", -1).limit(50).to_list(50)
    print("\n" + "=" * 80)
    print("RECENT JOB RUNS (last 24h, sample 50)")
    print("=" * 80)
    for r in recent[:20]:
        print(f"  {r.get('job_name')}: {r.get('finished_at')}  status={r.get('status')}")
    if len(recent) > 20:
        print(f"  ... and {len(recent) - 20} more")

    # 4) Summary: how many would be auto-resolved (dry-run; no actual resolve)
    print("\n" + "=" * 80)
    print("RECOVERY ELIGIBILITY (dry-run; incidents above with recovery_detected=True would auto-resolve)")
    print("=" * 80)
    would_resolve = [inc for inc in incidents if inc.get("_recovery_state", {}).get("recovery_detected")]
    n_job = sum(1 for inc in incidents if inc.get("source") == SOURCE_JOB_MONITOR and inc.get("_recovery_state", {}).get("recovery_detected"))
    n_hb = sum(1 for inc in incidents if inc.get("source") == SOURCE_HEARTBEAT and inc.get("_recovery_state", {}).get("recovery_detected"))
    n_del = sum(1 for inc in incidents if inc.get("source") == SOURCE_DELIVERY_UNKNOWN and inc.get("_recovery_state", {}).get("recovery_detected"))
    print(f"  Total open/acknowledged incidents: {len(incidents)}")
    print(f"  Would be auto-resolved (condition cleared): {len(would_resolve)} (job_monitor: {n_job}, heartbeat: {n_hb}, delivery_unknown: {n_del})")
    print("  Job-monitor incidents resolve when the related job next completes successfully (or on next sla_watchdog pass).")
    print("  Heartbeat/delivery_unknown resolve on next sla_watchdog run if condition is cleared.")

    await database.close()
    return {"incidents": incidents, "recent_runs_count": len(recent)}


if __name__ == "__main__":
    asyncio.run(main())
