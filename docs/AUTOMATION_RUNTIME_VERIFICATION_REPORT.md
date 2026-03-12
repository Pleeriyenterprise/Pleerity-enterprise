# Automation System — Runtime Verification Report

**Purpose:** Inspect the **database and scheduler state** (not code). Run the verification script against your MongoDB and API environment to fill the sections below.

---

## How to run the verification

From the **backend** directory, with MongoDB available and env loaded:

```bash
# Optional: set if not in .env
# export MONGO_URL="mongodb://localhost:27017"
# export DB_NAME="compliance_vault_pro"

python -m scripts.verify_automation_runtime
```

Or:

```bash
cd backend
python scripts/verify_automation_runtime.py
```

The script uses `backend/.env` (and defaults `MONGO_URL=mongodb://localhost:27017`, `DB_NAME=compliance_vault_pro` if unset). It will:

1. Query **job_runs** and report per-job run counts and last run timestamps/status.
2. Query **scheduled_jobs** (APScheduler MongoDB store) for job_id and next_run_time.
3. Cross-check the job registry with job_runs and list jobs with **zero executions**.
4. Infer **why** zero-run jobs never ran (next_run in future, not in scheduler, etc.).
5. List **open incidents** (missed job, stale heartbeat, delivery_unknown_stale).
6. Report whether **ADMIN_ALERT_EMAILS** (or OPS_ALERT_EMAIL) is configured.

At the end it prints a **table** and a **Markdown table** you can paste below.

---

## 1. job_runs (per job_name)

For each `job_name` the script returns:

| Field             | Meaning |
|------------------|--------|
| **total_runs**   | Number of documents in `job_runs` with that `job_name`. |
| **last_started_at** | `started_at` of the most recent run (by `finished_at` then `started_at`). |
| **last_finished_at** | `finished_at` of the most recent run. |
| **last_status**  | `status` of that run (`success`, `failed`, `degraded`, `running`). |

*Paste script output for section 1 here after running against your DB.*

---

## 2. scheduled_jobs (APScheduler store)

For each document in the `scheduled_jobs` collection:

| Field           | Meaning |
|----------------|--------|
| **job_id**     | Job identifier (often `_id`). |
| **next_run_time** | When the job is next scheduled (if stored by the jobstore). |
| **trigger**    | Trigger type if readable (e.g. cron/interval). |

Note: APScheduler may store job state in a serialized form; `next_run_time` is shown if present at top level. Otherwise, “Scheduler state” may need to be read from the running API (e.g. admin jobs status endpoint).

*Paste script output for section 2 here.*

---

## 3. Cross-check: jobs with zero executions

The script compares **job registry** (`ALL_JOB_IDS_FOR_HEALTH` from `job_schedule_registry`) with **job_runs**. Any job that appears in the registry but has **no** `job_runs` documents is listed as “zero executions”.

*Paste the list of zero-execution job names here.*

---

## 4. Why those jobs never ran

For each zero-execution job, the script infers a reason:

| Reason | Meaning |
|--------|--------|
| **next_run_time_still_in_future** | Job is scheduled but its next run has not yet passed (e.g. after a restart). |
| **not_in_scheduled_jobs_or_scheduler_never_started** | No document in `scheduled_jobs` for this job (scheduler may not have started or job not registered). |
| **next_run_time_null_or_missing** | Job is in `scheduled_jobs` but has no next run time (e.g. paused or misconfigured). |
| **scheduler_may_not_have_triggered_or_runtime_error_before_instrumentation** | Next run was in the past but no run was recorded (scheduler didn’t fire or error before `start_job_run`). |
| **could_not_parse_next_run_time** | `next_run_time` could not be parsed. |

*Paste the per-job reason list here.*

---

## 5. Open incidents (missed / heartbeat / delivery_unknown)

Open incidents with `source` in:

- `job_monitor` (missed job runs),
- `heartbeat` (stale scheduler heartbeat),
- `delivery_unknown` (delivery_unknown_stale)

are listed with: id, title, source, related_job_name, created_at.

*Paste script output for section 5 here.*

---

## 6. ADMIN_ALERT_EMAILS

The script reports whether **ADMIN_ALERT_EMAILS** or **OPS_ALERT_EMAIL** is set (non-empty). If not configured, incident alert emails will not be sent.

*Paste: Configured: yes/no*

---

## Output table (paste after running script)

After running the script, paste the **Markdown table** it prints (or the text table) here.

| job_name | registered | next_run_time | run_count | last_run | status | issue |
|----------|------------|---------------|-----------|----------|--------|-------|
| *(run script to fill)* | | | | | | |

---

## Summary

- **job_runs** and **scheduled_jobs** are queried directly from MongoDB.
- **Zero-execution** jobs are derived by comparing the registry to `job_runs`.
- **Reasons** for zero runs are inferred from `scheduled_jobs.next_run_time` and current time.
- **Open incidents** are filtered by source (job_monitor, heartbeat, delivery_unknown).
- **ADMIN_ALERT_EMAILS** is read from the environment.

For a **code-level** verification (registration, triggers, instrumentation), see `docs/SCHEDULER_RUNTIME_VERIFICATION_AUDIT.md`.
