# Investigation: Jobs Not Running / Not Recorded

## Summary

Many scheduled jobs show **no last successful run** on System Health and **"Never ran"** (or "Not yet due") in the Automation Control Centre, while **no open incidents** are created. This document explains why this is expected in normal operation and when it indicates a real problem.

---

## Root cause: schedule timing

### How runs get recorded

1. **APScheduler** triggers a job at its scheduled time (cron or interval).
2. The scheduler calls `run_scheduled_job(job_id)` → `run_instrumented()`.
3. **Before** the job logic runs, `start_job_run()` inserts a row into the `job_runs` collection.
4. When the job finishes, `finish_job_run_success` / `finish_job_run_failure` / `finish_job_run_degraded` updates that row.

So a job has **no run recorded** only when the scheduler has **never fired** that job since the process started (or since the job was added). There is no code path where a job runs but leaves no record.

### Why some jobs have runs and others don’t

| Job | Schedule | Why it has / doesn’t have runs |
|-----|----------|--------------------------------|
| **scheduler_heartbeat** | Every **2 minutes** | Fires often → almost always has a recent run. |
| **compliance_recalc_worker** | Every **15 seconds** | Fires very often → has runs. |
| **notification_retry_worker** | Every **minute** | Fires often → has runs. |
| **notification_failure_spike_monitor** | Every **5 minutes** | Fires every 5 min → has runs. |
| **daily_reminders** | **9:00 UTC** once per day | No run until 9:00 UTC has occurred since server start. |
| **pending_verification_digest** | **9:30 UTC** once per day | No run until 9:30 UTC. |
| **monthly_digest** | **1st of month, 10:00 UTC** | No run until that time. |
| **compliance_check_morning** | **8:00 UTC** daily | No run until 8:00 UTC. |
| **compliance_check_evening** | **18:00 UTC** daily | No run until 18:00 UTC. |
| **scheduled_reports** | **Every hour at :00** | No run until the next top of the hour. |
| **compliance_score_snapshots** | **2:00 UTC** daily | No run until 2:00 UTC. |
| **expiry_rollover_recalc** | **00:10 UTC** daily | No run until 00:10 UTC. |
| **sla_watchdog** | Every **10 minutes** (*/10) | First run at next :00, :10, :20, … after start. |
| **delivery_reconciliation** | Every **15 minutes** (*/15) | First run at next :00, :15, :30, :45 after start. |

So:

- **High-frequency jobs** (every 15s, 1m, 2m, 5m) will show a last run soon after startup.
- **Daily / hourly jobs** will show **no run** until their first scheduled time (e.g. 9:00 UTC for daily_reminders). If the server started at 22:11 UTC, that time has already passed today, so the next run is **tomorrow** at 9:00.
- **Cron jobs like */10 and */15** run at the next matching minute; if the server started at 22:07, the first */10 run is at 22:10, first */15 at 22:15.

So “not running yet” and “not recorded” for daily/hourly jobs (and shortly after startup for */10, */15) is **expected**, not a bug.

---

## Why there are no open incidents

The SLA watchdog runs every 10 minutes and creates incidents when:

- A critical job has **no successful run** and is **past due** (past its `max_delay` or first expected run).

We added a **grace period** so we do **not** create an incident when:

- The job has never run but its **next scheduled run** (from the scheduler) is still **in the future**.

For daily jobs, `next_run_time` is typically **tomorrow** (e.g. 9:00 UTC). So the watchdog correctly does **not** open an incident: the job is “not yet due”, not “overdue”.

So **no open incidents** for these jobs is correct: they are waiting for their first run time, not missing it.

---

## When “no run” is a real problem

Investigate further if:

1. **High-frequency jobs** (e.g. scheduler_heartbeat every 2 min, compliance_recalc_worker every 15s) have **no run** after the process has been up for longer than their interval (e.g. > 2 min, > 15s). That suggests the scheduler is not firing them.
2. **After the first scheduled time has passed** (e.g. after 9:00 UTC for daily_reminders), the job still has no run. That could indicate:
   - Scheduler not running in this process (e.g. only in a worker).
   - Exception or misconfiguration preventing the job from being triggered.
3. **Runs exist in `job_runs`** but the UI doesn’t show them (e.g. wrong job name, or UI reading from a different source). That would be a bug in the API or frontend.

---

## Recommendations

1. **UI**  
   - For jobs with no last successful run, show **“No run yet”** and, where available, **“Next run: &lt;time&gt;”** so it’s clear they are waiting for their first run, not failed.
2. **System Health**  
   - Add a short note near “Last successful run” that daily/hourly jobs will show “No run yet” until their first scheduled time after server start.
3. **Operational**  
   - After a deploy or server restart, expect daily jobs to show no run until their next cron time (e.g. next 9:00 UTC).  
   - Use Automation Control Centre “Next schedule” and status “Not yet due” vs “Never ran (overdue)” to tell “waiting for first run” from “missed run”.

---

## Files involved

- **Scheduler registration:** `backend/server.py` (all jobs use `run_scheduled_job`).
- **Run recording:** `backend/job_runner.py` (`run_instrumented` → `start_job_run` before job logic).
- **Health summary / job state:** `backend/routes/observability.py` (`_compute_job_state_and_reason`, uses `next_run` for “not yet due” vs “never ran overdue”).
- **Incident creation:** `backend/services/sla_watchdog.py` (grace period when `next_run` is in the future).
- **UI:** `frontend/src/pages/AdminSystemHealthPage.js`, `frontend/src/pages/AdminAutomationCentrePage.js`.
