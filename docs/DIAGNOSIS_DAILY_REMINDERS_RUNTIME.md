# Focused runtime diagnosis: daily_reminders

**Job:** daily_reminders  
**Purpose:** Send daily compliance expiry reminders (email + optional SMS) to active clients with expiring/overdue requirements.  
**Diagnosis scope:** Single job only; evidence from code path and required runtime checks.

---

## 1. Scheduler registration

| Item | Value |
|------|--------|
| **Registered** | Yes |
| **Trigger** | `CronTrigger(hour=9, minute=0, timezone=SCHEDULER_TIMEZONE)` |
| **Cron/interval** | Daily at 09:00 UTC |
| **Timezone** | `SCHEDULER_TIMEZONE = timezone.utc` (server.py) |
| **next_run_time** | Set by APScheduler from cron; next occurrence of 09:00 UTC. Valid if server and scheduler use UTC. |
| **Callable used at runtime** | `job_runner:run_scheduled_job` (string ref). APScheduler resolves this and invokes `run_scheduled_job(job_id, run_type="schedule")` with `job_id="daily_reminders"` from `args=["daily_reminders"]`. |

**Exact registration path:**  
`server.py` lifespan (after `database.connect()` and scheduler start):

```python
scheduler.add_job(
    "job_runner:run_scheduled_job",
    CronTrigger(hour=9, minute=0, timezone=SCHEDULER_TIMEZONE),
    id="daily_reminders",
    name="Daily Compliance Reminders",
    replace_existing=True,
    args=["daily_reminders"],
    kwargs={"run_type": "schedule"},
)
```

Job store: MongoDB `db_name.scheduled_jobs` (same `db_name` from env at import). No separate trigger type or expression; next_run_time is valid for the environment as long as the process uses UTC.

---

## 2. Execution path trace

| Step | Component | Confirmed |
|------|-----------|-----------|
| APScheduler trigger | Fires at 09:00 UTC, invokes callable with `args` | Yes |
| `run_scheduled_job("daily_reminders", "schedule")` | `job_runner.run_scheduled_job` | Yes – only entry point for scheduler |
| `run_instrumented("daily_reminders", "schedule")` | Called by `run_scheduled_job` | Yes |
| `start_job_run("daily_reminders", "schedule")` | Called by `run_instrumented` before `fn()` | Yes – no bypass; unknown job_id would raise before this |
| Actual job function | `JOB_RUNNERS["daily_reminders"]` = `run_daily_reminders` | Yes – in job_runner.py |
| `run_daily_reminders()` | Calls `JobScheduler().send_daily_reminders()` | Yes |
| `finish_job_run_success` / `finish_job_run_degraded` / `finish_job_run_failure` | Called from `run_instrumented` based on `result.outcome_status` | Yes – send_daily_reminders returns dict with `outcome_status` |

**Instrumented path:** Yes. There is no code path where the scheduler invokes daily_reminders without going through `run_scheduled_job` → `run_instrumented` → `start_job_run` → `run_daily_reminders` → `finish_job_run_*`.

**Break point:** None in code. If runs do not appear in job_runs, the failure is at runtime (e.g. process not connected to DB, or exception before `start_job_run` such as unknown job_id in a different deployment).

---

## 3. Runtime record verification

**job_runs:** Written by `start_job_run` (insert) and `finish_job_run_*` (update) in `services/job_run_service.py`, collection `job_runs`, `job_name="daily_reminders"`, `run_type="schedule"`.

**To verify in your environment:**

- **MongoDB:**  
  `db.job_runs.find({"job_name": "daily_reminders"}).sort({created_at: -1}).limit(5)`  
  Check: at least one document; `started_at`/`finished_at` near 09:00 UTC on run days; `status` in `success`|`degraded`|`failed`; `run_type: "schedule"`.

- **Script:**  
  `python backend/scripts/verify_automation_runtime.py`  
  Inspect the table row for `daily_reminders`: total_runs, last_started_at, last_finished_at, last_status.

- **API:**  
  `GET /api/admin/observability/job-runs?job_name=daily_reminders&limit=10`  
  Response should include recent runs with `job_name: "daily_reminders"`.

**If the job has been seen in logs but no job_runs rows exist:**

1. **Exception before `start_job_run`** – e.g. `ValueError: Unknown job_id` (job_id not in `JOB_RUNNERS`). Check logs for `run_instrumented: unknown job_id=daily_reminders` or `job_run started job_name=daily_reminders`.
2. **DB not connected in the process that runs the job** – `start_job_run` raises `RuntimeError` if `database.get_db()` is None. That process must have run `database.connect()` (e.g. FastAPI lifespan).
3. **Different DB** – Same process and env ⇒ same DB. If the scheduler runs in another process, that process must use the same `MONGO_URL`/`DB_NAME` and call `database.connect()` so job_runs are written where the API reads.

---

## 4. Business output verification

| Item | Detail |
|------|--------|
| **Expected output** | (1) **message_logs:** entries for sends via `notification_orchestrator.send()` with `template_key` in `COMPLIANCE_EXPIRY_REMINDER`, `COMPLIANCE_EXPIRY_REMINDER_SMS`. (2) **audit_logs:** `action: "REMINDER_SENT"` per successful email. (3) Optional: requirement status updates to EXPIRING_SOON/OVERDUE and enqueue to compliance_recalc_queue. |
| **Actual output (code path)** | `send_daily_reminders` uses `_send_reminder_email` and `_maybe_send_reminder_sms`, both calling `notification_orchestrator.send()`, which writes to `message_logs`. On success, `audit_logs.insert_one` with REMINDER_SENT. So if the job runs and sends, message_logs and audit_logs are written. |
| **Zero-output valid?** | Yes. Registry has `zero_output_ok=True` for daily_reminders. When no clients have expiring/overdue requirements (or all skipped by preferences/quiet hours), the job returns `outcome_status: "success"`, `count: 0`, `outcome_metrics: {expected_count: 0, attempted_count: 0, ...}` and is treated as success; observability can show `conditional_no_output`. |

**To verify business output at runtime:** After a run, check `message_logs` for `template_key` in `["COMPLIANCE_EXPIRY_REMINDER", "COMPLIANCE_EXPIRY_REMINDER_SMS"]` and `created_at` near that run’s `started_at`/`finished_at`; and `audit_logs` for `action: "REMINDER_SENT"` in the same time window. If the job runs but no reminders are due, zero message_logs for that run is expected (conditional no output).

---

## 5. Admin observability verification

| View | Source | Truthfulness for daily_reminders |
|------|--------|----------------------------------|
| **Automation Control Centre** | Union of job_runs (by job_name) and scheduler job list; last run from job_runs; state from health-summary job_states or client-side fallback using next_run. | Correct if job_runs has rows for `job_name: "daily_reminders"`. If no row, job shows as “Never ran” or “Not yet due” depending on next_run_time. |
| **System Health** | `GET /api/admin/observability/health-summary`; includes daily_reminders in HEALTH_SUMMARY_JOBS; reads job_runs by job_name, computes state via `_compute_job_state_and_reason`. | Correct: daily_reminders is in CRITICAL_JOB_REGISTRY and HEALTH_SUMMARY_JOBS; state is derived from last run and outcome_metrics (including conditional_no_output when zero_output_ok and attempted_count=0). |
| **Incidents** | SLA watchdog and incident service; daily_reminders is critical; missed/overdue can create incidents. | Correct if watchdog and observability use same job_runs and registry. |
| **Notification Health / Email Delivery** | message_logs and delivery reconciliation. daily_reminders is in RECONCILIATION_JOBS; delivery_reconciliation updates job run outcome_metrics with delivery_* from message_logs. | Correct: template keys COMPLIANCE_EXPIRY_REMINDER, COMPLIANCE_EXPIRY_REMINDER_SMS are linked to daily_reminders; reconciliation runs separately and enriches recent job_runs. |

**Possible mismatch:** If job_runs has no row (e.g. wrong process or DB), the UI will show “never ran” or “not yet due” even if the job ran in another process/DB. Ensuring the same process and DB for scheduler and API avoids this.

---

## 6. Failure / degrade verification

| Scenario | Code behaviour | Observability |
|----------|----------------|---------------|
| **Full failure** | Exception in `run_daily_reminders` or `send_daily_reminders` → `run_instrumented` catches, calls `finish_job_run_failure`. All sends fail → return `outcome_status: "failed"` → `finish_job_run_failure`. | job_runs row has `status: "failed"`; state = failed; overall health can degrade. |
| **Partial failure** | Some sends fail → return `outcome_status: "degraded"`, `outcome_metrics` with success_count/failed_count → `finish_job_run_degraded`. | job_runs row has `status: "degraded"`; state = degraded. |
| **Zero valid output** | No reminders due or all skipped → return `outcome_status: "success"`, `count: 0`, `outcome_metrics: {attempted_count: 0, ...}` → `finish_job_run_success`. Registry `zero_output_ok=True` ⇒ `_compute_job_state_and_reason` can return `conditional_no_output`. | Not marked failed; shown as healthy or conditional_no_output. |
| **No run** | No job_runs row (e.g. job never triggered or exception before start_job_run) ⇒ no last_completed. With next_run in future ⇒ not_yet_due_since_startup; else never_ran_and_overdue. | Appropriate state and no false “success”. |

**Partial-failure observability:** Partial failure is reported as degraded and written to job_runs with outcome_metrics; there is no code path where a partial failure is recorded as success. If the job is observed “running” in logs but no job_runs row exists, the break is before or at `start_job_run` (see §3).

---

## 7. Database / environment consistency

| Layer | DB/source | Same as app? |
|-------|------------|--------------|
| Scheduler job store | `db_name.scheduled_jobs` (PyMongo; `db_name` from env at server.py import) | Same env ⇒ same DB name. |
| job_runs | `database.get_db()` → `database.db` (Motor; set in `database.connect()` from env) | Same process ⇒ same DB. |
| message_logs | Written by notification_orchestrator using `database.get_db()`; JobScheduler uses its own Motor client with `os.environ['MONGO_URL']`, `os.environ['DB_NAME']` | Job runs in same process as API ⇒ same env; JobScheduler’s client points to same DB name. |
| Observability routes | `database.get_db()` for job_runs, incidents, etc. | Same singleton as job_run_service. |

**Conclusion:** In a single-process deployment (one FastAPI app that starts the scheduler and serves the API), scheduler, job_runs, message_logs, and observability all use the same database. No timezone or collection mismatch for this job in code. If runs are missing in the UI, the most likely cause is a multi-process or multi-environment setup where the process that runs the job does not write to the same DB the API reads, or does not call `database.connect()`.

---

## 8. Root cause decision

**Primary diagnosis: A. Registered and working correctly (by design).**

**Evidence:**

- Scheduler registration: daily_reminders is added with `job_runner:run_scheduled_job`, args `["daily_reminders"]`, cron 09:00 UTC; no other callable.
- Execution path: Single instrumented path; no bypass; `run_daily_reminders` is in JOB_RUNNERS and returns outcome dict; finish_job_run_* are called correctly.
- Business output: Sends go through notification_orchestrator → message_logs; REMINDER_SENT → audit_logs; delivery_reconciliation and registry align for this job.
- Observability: daily_reminders is in HEALTH_SUMMARY_JOBS and CRITICAL_JOB_REGISTRY; state logic and zero_output_ok/conditional_no_output are correct.
- Failure handling: Failed → failed, degraded → degraded, zero output → success/conditional_no_output; no silent misclassification in code.

**Caveat:** This is design-time and code-path verification. To confirm “truly works end to end in the running system” you must verify at runtime:

1. After 09:00 UTC (or after a manual run): `db.job_runs.find({"job_name": "daily_reminders"}).sort({created_at: -1}).limit(1)` returns a recent document with `run_type: "schedule"` and `status` in [success, degraded, failed].
2. When reminders are sent: message_logs and audit_logs contain the expected entries for that run’s time window.
3. Automation Control Centre and System Health show the same last run and state as the job_runs document.

If runtime shows “job ran in logs but no job_runs row,” then the diagnosis shifts to **C** (triggered but instrumentation missing/wrong process) or **G** (database/environment mismatch). The code does not support a bypass or a different DB for this job in a single process.

---

## 9. Required output format (summary)

**JOB:** daily_reminders

**1. Scheduler registration**  
- registered: yes  
- trigger: CronTrigger(hour=9, minute=0, timezone=UTC)  
- next_run_time: next 09:00 UTC (from APScheduler; verify via scheduler.get_jobs() or scheduled_jobs collection)  
- callable used: `job_runner:run_scheduled_job` (invoked with args=["daily_reminders"], kwargs={"run_type": "schedule"})

**2. Execution path**  
- instrumented path confirmed: yes  
- break point if any: none in code; if runs missing, check runtime (wrong process/DB or exception before start_job_run)

**3. Runtime records**  
- job_runs exists: verify with `db.job_runs.find({"job_name": "daily_reminders"}).sort({created_at: -1}).limit(5)` or verify_automation_runtime.py  
- run_count / last_run / last_status: from that query or script output

**4. Business output**  
- expected output: message_logs (COMPLIANCE_EXPIRY_REMINDER, COMPLIANCE_EXPIRY_REMINDER_SMS), audit_logs (REMINDER_SENT)  
- actual output found: see message_logs and audit_logs for run time window  
- zero-output valid?: yes (conditional_no_output when no reminders due)

**5. Admin observability**  
- Automation Control Centre truthfulness: correct if job_runs has rows for this job  
- System Health truthfulness: correct (job in HEALTH_SUMMARY_JOBS; state from job_runs and registry)  
- other relevant admin views: Notification Health / Email Delivery and delivery_reconciliation use correct template keys for daily_reminders

**6. Failure/degrade honesty**  
- full failure handling: → failed in job_runs and UI  
- partial failure handling: → degraded  
- zero-output handling: → success / conditional_no_output, not failed

**7. Root cause**  
- primary diagnosis: A. Registered and working correctly  
- exact evidence: Single scheduled callable, single instrumented path, correct outcome_status handling, same DB in one process, registry and observability include daily_reminders with correct options

**8. Fix recommendation**  
No code fix required for this job. To confirm end-to-end in your environment:

- Run `backend/scripts/verify_automation_runtime.py` and check the row for daily_reminders (run_count, last_finished_at, last_status).  
- If run_count is 0 and the job should have run (e.g. after 09:00 UTC), check: (1) logs for `job_run started job_name=daily_reminders` and any exception before it; (2) that the process running the scheduler has called `database.connect()` and uses the same MONGO_URL/DB_NAME as the API.  
- Optionally trigger a manual run from the Automation Control Centre and confirm a new job_runs row and expected message_logs/audit_logs.
