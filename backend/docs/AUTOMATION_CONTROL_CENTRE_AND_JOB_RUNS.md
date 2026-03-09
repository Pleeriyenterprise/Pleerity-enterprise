# Automation Control Centre and Job Runs

## How the Automation Control Centre gets its data

- **Last run, Last success, Failures (24h)** come from the `job_runs` MongoDB collection. Every execution that goes through `run_instrumented()` (scheduler or manual "Run now") calls `job_run_service.start_job_run` and then `finish_job_run_success` or `finish_job_run_failure`, so those fields are filled when the run is recorded.
- **Next schedule** comes from the in-process APScheduler: `scheduler.get_jobs()` and each job's `next_run_time`. So "Next schedule" is only correct in the process that actually runs the scheduler.

## Why you might see "Next run: Not scheduled" for most jobs

If the **API process** (that serves `GET /api/admin/jobs/status`) is not the same process that **starts the scheduler** (in `server.py` lifespan), then:

- That API process either has no scheduler or an empty scheduler, so `scheduler.get_jobs()` returns nothing or only some jobs.
- With **MongoDB job store**, multiple instances load jobs from the same DB; often only the instance that "owns" the scheduler computes and persists `next_run_time` for all jobs. Other instances may see job list but with `next_run_time` missing for most jobs (so only one job, e.g. daily_reminders, shows a next schedule).

**Requirement:** The same process that serves the API must start and own the scheduler (default in `server.py`). Do not run the scheduler in a separate worker/process unless you also expose or replicate next-run data for that worker.

## Why Last run / Last success / Failures might be empty after a run

If the **scheduler runs in a different process** (e.g. a separate "worker" or another instance):

- When a job runs there, it uses that process's `run_instrumented` and writes to `job_runs` in MongoDB. If that process uses a **different** MongoDB or doesn't use `run_instrumented` at all, the API's `job_runs` collection never gets the run.
- So the Automation Control Centre (which reads `job_runs` from the same DB the API uses) shows no Last run / Last success / Failures even though the job ran.

**Requirement:** All job executions (scheduled or manual) must go through `run_instrumented()` in a process that writes to the **same** `job_runs` collection the API reads. In the standard setup, that means the scheduler runs in the **same process** as the API.

## Manual "Run now" and Abandoned intake

- When you click "Run now", the API runs `run_instrumented(job_id, "manual", ...)` in the **API process**. So:
  - **Last run** and **Last success** are written to `job_runs` and show up.
  - **Failures (24h)** stays 0 (or —) unless a run failed in the last 24h.
  - **Next schedule** is still from the scheduler in this process. If this process has the scheduler and that job has a trigger, Next schedule will appear; otherwise it stays "—".

So for a manual run, **"Last run and Last success recorded, Failures and Next schedule not recorded"** is expected when there are no failures (so Failures shows —) and the scheduler in this process does not have a next run for that job (e.g. different instance or MongoDB job store only updated one job).

## Daily reminders: ran automatically but no Last run / Last success

If daily_reminders **did** run (e.g. you see "Next schedule" for it) but **Last run / Last success / Failures** are still empty:

- The run almost certainly happened in **another process** (e.g. a separate scheduler worker or external cron).
- That process either didn't call `run_instrumented` or didn't write to the same `job_runs` DB the API reads.
- So the API never sees the run, and the SLA watchdog (which also reads `job_runs`) doesn't see it either. Reminder emails may or may not have been sent by that other process.

**Fix:** Run the scheduler in the **same process** as the API (single process with `server.py` lifespan). Restart that process and wait for the next scheduled run (or trigger manually); then Last run / Last success should appear.

## Incidents page empty

Incidents are created by the **SLA watchdog** job (`sla_watchdog`), which runs every 10 minutes. It:

- Reads `job_runs` for last success per monitored job.
- If a job has never succeeded, or last success is older than the configured delay, it creates an incident (and can send admin alert emails if `ADMIN_ALERT_EMAILS` is set).

If the **Incidents** page is always empty:

1. **SLA watchdog may not be running** – e.g. scheduler not started or running in another process that doesn't own the API's DB.
2. **No job runs are in `job_runs`** – so the watchdog sees "never succeeded" and can create incidents; but if the watchdog itself isn't running, no incidents are created.
3. **Incidents are created but filtered out** – e.g. filter set to "Open" and they were already acknowledged/resolved.

Ensure the **same process** runs the scheduler (including `sla_watchdog`) and writes to the same `job_runs`/`incidents` DB. Set `ADMIN_ALERT_EMAILS` (or `OPS_ALERT_EMAIL`) if you want email alerts for new incidents.

## Deployment checklist (single process)

For predictable Automation Control Centre and incidents:

1. **One process** runs both the API and the scheduler (default: single `uvicorn` / `server:app` with lifespan starting the scheduler).
2. Do **not** run the scheduler in a separate worker unless you:
   - Have that worker write job runs to the **same** MongoDB `job_runs` collection the API uses, and
   - Either serve `GET /api/admin/jobs/status` from that same worker or replicate next-run data (e.g. store next_run in DB and have API read it).
3. Set **ADMIN_ALERT_EMAILS** (or OPS_ALERT_EMAIL) so SLA incidents send admin alerts.
4. After deploy, check server logs for: `Background job scheduler started with N job(s). Next runs: [...]`. If N is 0 or the list is empty, the scheduler did not start in that process.

## Summary

- **Last run / Last success / Failures (24h):** from `job_runs`, populated only when jobs run via `run_instrumented()` in a process that writes to the same DB the API uses.
- **Next schedule:** from the in-process scheduler; only correct in the process that actually runs the scheduler.
- **Incidents:** created by the `sla_watchdog` job from `job_runs`; only works if the watchdog runs and sees the same `job_runs` data.

For predictable behaviour, run **one** API process that starts the scheduler in its lifespan and runs all jobs in-process (default deployment). Avoid splitting scheduler and API across processes unless you replicate job state and next-run data accordingly.
