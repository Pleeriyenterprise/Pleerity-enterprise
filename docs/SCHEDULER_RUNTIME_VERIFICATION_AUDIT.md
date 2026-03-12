# Runtime Verification Audit: Automation Scheduler

**Date:** 2026-02-20  
**Goal:** Confirm that all critical scheduled jobs are properly registered, scheduled, and instrumented.

---

## 1. APScheduler registration

All scheduled jobs are registered in `backend/server.py` inside the lifespan context manager, after `database.connect()` and after the scheduler is bound to the running event loop. Each job uses the single callable reference `"job_runner:run_scheduled_job"` with `args=[job_id]` so that the MongoDB job store can persist jobs (picklable string reference).

### 1.1 Jobs requested for verification (14 critical)

| job_id | Trigger type | Cron / interval | next_run_time | registered |
|--------|--------------|-----------------|---------------|------------|
| daily_reminders | CronTrigger | hour=9, minute=0 (daily 09:00 UTC) | Set at runtime | ✓ |
| pending_verification_digest | CronTrigger | hour=9, minute=30 (daily 09:30 UTC) | Set at runtime | ✓ |
| monthly_digest | CronTrigger | day=1, hour=10, minute=0 (1st of month 10:00 UTC) | Set at runtime | ✓ |
| compliance_check_morning | CronTrigger | hour=8, minute=0 (daily 08:00 UTC) | Set at runtime | ✓ |
| compliance_check_evening | CronTrigger | hour=18, minute=0 (daily 18:00 UTC) | Set at runtime | ✓ |
| scheduled_reports | CronTrigger | minute=0 (every hour on the hour) | Set at runtime | ✓ |
| compliance_score_snapshots | CronTrigger | hour=2, minute=0 (daily 02:00 UTC) | Set at runtime | ✓ |
| expiry_rollover_recalc | CronTrigger | hour=0, minute=10 (daily 00:10 UTC) | Set at runtime | ✓ |
| compliance_recalc_worker | IntervalTrigger | seconds=15 | Set at runtime | ✓ |
| notification_retry_worker | CronTrigger | minute="*" (every minute) | Set at runtime | ✓ |
| notification_failure_spike_monitor | CronTrigger | minute="*/5" (every 5 min) | Set at runtime | ✓ |
| delivery_reconciliation | CronTrigger | minute="*/15" (every 15 min) | Set at runtime | ✓ |
| sla_watchdog | CronTrigger | minute="*/10" (every 10 min) | Set at runtime | ✓ |
| scheduler_heartbeat | IntervalTrigger | minutes=2 | Set at runtime | ✓ |

**Cron expressions (APScheduler style):**

- `CronTrigger(hour=9, minute=0)` → 09:00 UTC daily  
- `CronTrigger(hour=9, minute=30)` → 09:30 UTC daily  
- `CronTrigger(day=1, hour=10, minute=0)` → 1st of month, 10:00 UTC  
- `CronTrigger(hour=8, minute=0)` / `(hour=18, minute=0)` → 08:00 and 18:00 UTC daily  
- `CronTrigger(minute=0)` → every hour at :00  
- `CronTrigger(hour=2, minute=0)` → 02:00 UTC daily  
- `CronTrigger(hour=0, minute=10)` → 00:10 UTC daily  
- `CronTrigger(minute="*/5")` → every 5 minutes  
- `CronTrigger(minute="*")` → every minute  
- `CronTrigger(minute="*/15")` → every 15 minutes  
- `CronTrigger(minute="*/10")` → every 10 minutes  
- `IntervalTrigger(seconds=15)` → every 15 seconds  
- `IntervalTrigger(minutes=2)` → every 2 minutes  

All of these are valid; APScheduler computes `next_run_time` at runtime when the scheduler starts and after each run.

### 1.2 Other registered jobs (same pattern)

Additional jobs registered in the same way (same instrumentation path) include:  
`compliance_recalc_sla_monitor`, `order_delivery_processing`, `sla_monitoring`, `stuck_order_detection`, `queued_order_processing`, `abandoned_intake_detection`, `lead_followup_processing`, `pending_payment_lifecycle`, `lead_sla_check`, `checklist_nurture_processing`, `risk_lead_nurture_processing`, `predictive_insights_job`, `risk_signals_job`, `work_order_sla_breach_job`.

---

## 2. Scheduler startup sequence

Order of operations in `server.py` lifespan:

1. **Database:** `await database.connect()`
2. **Optional:** Production JWT check, ClearForm indexes, etc.
3. **Scheduler binding:** `scheduler._eventloop = asyncio.get_running_loop()` so async jobs run on the app loop
4. **Job registration:** All `scheduler.add_job("job_runner:run_scheduled_job", trigger, id=job_id, args=[job_id], kwargs={"run_type": "schedule"}, replace_existing=True)` in sequence
5. **Scheduler start:** `scheduler.start()`  
   - Jobs are loaded from MongoDB job store (if configured) or in-memory; `next_run_time` is set by APScheduler
6. **Log:** `scheduler.get_jobs()` and next runs for first 5 jobs are logged

Shutdown: `scheduler.shutdown(wait=False)` then `await database.close()`.

---

## 3. Job instrumentation

Every scheduled run goes through:

1. **APScheduler** invokes `job_runner.run_scheduled_job(job_id, run_type="schedule")` (module path `job_runner:run_scheduled_job`, `args=["<job_id>"]`).
2. **`run_scheduled_job`** calls `run_instrumented(job_id, "schedule", triggered_by=None)`.
3. **`run_instrumented`** (in `job_runner.py`):
   - Resolves `fn = JOB_RUNNERS[job_id]` (raises if `job_id` not in `JOB_RUNNERS`)
   - Calls `start_job_run(job_id, run_type, triggered_by=...)` → inserts one document into `job_runs`
   - Awaits `fn()` (the actual job logic)
   - On success/degraded/failure: calls `finish_job_run_success`, `finish_job_run_degraded`, or `finish_job_run_failure` with the same `job_run_id`

So every job that is both **registered** in the scheduler and present in **`JOB_RUNNERS`** uses `start_job_run` and one of the `finish_job_run_*` paths. Manual "Run now" uses the same path: `run_instrumented(job_id, "manual", triggered_by=user_id)`.

**Verification:** All 14 requested job_ids exist in `JOB_RUNNERS` in `job_runner.py`:

- daily_reminders, pending_verification_digest, monthly_digest → run_daily_reminders, run_pending_verification_digest, run_monthly_digests  
- compliance_check_morning, compliance_check_evening → run_compliance_status_check (same function, different schedule by job_id)  
- scheduled_reports, compliance_score_snapshots, expiry_rollover_recalc, compliance_recalc_worker, notification_retry_worker, notification_failure_spike_monitor, delivery_reconciliation, sla_watchdog, scheduler_heartbeat → corresponding `run_*` in `JOB_RUNNERS`

**Instrumentation status:** **Full** for all 14: each calls `start_job_run()` and exactly one of `finish_job_run_success()`, `finish_job_run_failure()`, or `finish_job_run_degraded()`.

---

## 4. job_runs persistence

- **Collection:** `job_runs` (see `services/job_run_service.py`, `COLLECTION = "job_runs"`).
- **Start:** `start_job_run(job_name, run_type, ...)` inserts a document with `job_name`, `run_type`, `status: "running"`, `started_at`, `finished_at: None`, etc., and returns `job_run_id` (ObjectId string).
- **Finish:** `finish_job_run_success`, `finish_job_run_failure`, or `finish_job_run_degraded` updates that document with `status`, `finished_at`, `duration_ms`, `outcome_status`, `outcome_metrics`, and error fields when applicable.

Every execution that goes through `run_instrumented` therefore produces one `job_runs` entry per run. No code path bypasses this for the 14 critical jobs.

---

## 5. Cron / trigger validation and next_run_time

- **CronTrigger** and **IntervalTrigger** are used with valid parameters; APScheduler computes the next run time when the job is added and after each execution.
- **next_run_time** is not stored in code; it is computed at runtime and (when using MongoDB job store) persisted in the `scheduled_jobs` collection. To see actual values, run the API and call `scheduler.get_jobs()` or use the admin/observability endpoints that read from the scheduler and `job_runs`.
- No invalid cron expressions were found; all triggers use standard APScheduler semantics.

---

## 6. SLA watchdog scheduling

- **job_id:** `sla_watchdog`
- **Registered:** Yes, in `server.py`: `scheduler.add_job("job_runner:run_scheduled_job", CronTrigger(minute="*/10"), id="sla_watchdog", ...)`.
- **Schedule:** Every 10 minutes (`minute="*/10"`).
- **Runner:** `run_sla_watchdog` in `job_runner.py` (wraps `services.sla_watchdog.run_sla_watchdog`).
- **Instrumentation:** Same as all others: `run_scheduled_job` → `run_instrumented` → `start_job_run` + `run_sla_watchdog()` + `finish_job_run_*`.

---

## 7. Summary table (requested 14 jobs)

| job_id | registered | next_run_time | last_run | instrumentation_status | issue |
|--------|------------|---------------|----------|-------------------------|-------|
| daily_reminders | ✓ | Set at runtime (APScheduler) | Persisted in job_runs when job runs | Full (start + finish_*) | None |
| pending_verification_digest | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| monthly_digest | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| compliance_check_morning | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| compliance_check_evening | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| scheduled_reports | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| compliance_score_snapshots | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| expiry_rollover_recalc | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| compliance_recalc_worker | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| notification_retry_worker | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| notification_failure_spike_monitor | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| delivery_reconciliation | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| sla_watchdog | ✓ | Set at runtime | Persisted in job_runs | Full | None |
| scheduler_heartbeat | ✓ | Set at runtime | Persisted in job_runs | Full | None |

**Inconsistencies:** None. No job in the list is missing from the scheduler, and no job uses a null or missing `next_run_time` by design (APScheduler sets it). All 14 are in `JOB_RUNNERS` and go through `run_instrumented`, so all write to `job_runs`.

---

## 8. Files referenced

| Purpose | File |
|--------|------|
| Scheduler init and job registration | `backend/server.py` (lifespan, add_job calls) |
| Single entry point for scheduler | `backend/job_runner.py` (`run_scheduled_job`, `run_instrumented`, `JOB_RUNNERS`) |
| job_runs persistence | `backend/services/job_run_service.py` (`start_job_run`, `finish_job_run_success`, `finish_job_run_failure`, `finish_job_run_degraded`) |
| Admin manual run | `backend/routes/admin.py` (`run_job_now` → `run_instrumented`) |

---

## 9. Conclusion

- All 14 critical jobs are **registered** with APScheduler with the expected triggers and schedules.
- **next_run_time** is determined at runtime by APScheduler; no job is registered with a null trigger.
- **Instrumentation** is uniform: every run uses `start_job_run` and one of the `finish_job_run_*` methods.
- **job_runs** entries are written for every execution that goes through `run_instrumented`.
- **sla_watchdog** is registered and runs every 10 minutes with the same instrumentation as the rest.

No missing registration, null next run, missing instrumentation, or missing job_runs persistence was found for the 14 critical jobs.

---

## 10. Why only some jobs appear in a short log window

**Observation:** In a 2–3 minute console log you may see only **Compliance Recalc Worker** (every 15s), **Notification Retry Worker** (every minute), and **Scheduler Heartbeat** (every 2 min). Other jobs do not appear in that window because they are less frequent.

**Expected behavior:**

- **Every 15s:** compliance_recalc_worker → appears many times in a few minutes.
- **Every 1 min:** notification_retry_worker → appears every minute.
- **Every 2 min:** scheduler_heartbeat → appears every 2 minutes.
- **Every 5 min:** notification_failure_spike_monitor, compliance_recalc_sla_monitor, order_delivery_processing → appear at :00, :05, :10, :15, … of each hour.
- **Every 10 min:** sla_watchdog, queued_order_processing → at :00, :10, :20, …
- **Every 15 min:** delivery_reconciliation, sla_monitoring, … → at :00, :15, :30, :45.
- **Every hour:** scheduled_reports, lead_sla_check, … → at :00 of each hour.
- **Daily (e.g. 09:00 UTC):** daily_reminders, pending_verification_digest, … → once per day at the configured time.

So “only the same set of jobs running” in a **short** window is expected. To confirm that other jobs run:

1. **Startup log:** After scheduler start, the server logs: `Background job scheduler started with N job(s). Job ids: [...]`. Check that all expected job ids are present. Set log level to DEBUG to see each job’s `next_run_time`.
2. **Runtime verification:** Run `python -m scripts.verify_automation_runtime` (with MongoDB available) and check `job_runs` and `scheduled_jobs` so that less frequent jobs show runs and next run times.
3. **Wait for the next tick:** For example, wait until :00, :05, :10, :15 of the hour and look for “Notification Failure Spike Monitor”, “Delivery Reconciliation”, “SLA Watchdog”, etc., in the logs.

**Fixes applied (UTC and diagnostics):**

- Scheduler and all cron/interval triggers now use **UTC** explicitly (`timezone=datetime.timezone.utc`) so server locale cannot change when jobs run.
- Startup logs the full list of job ids and (at DEBUG) each job’s `next_run_time` for verification.
