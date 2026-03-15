# Focused runtime diagnosis: scheduled_reports

**Job:** scheduled_reports  
**Purpose:** Process due report schedules (daily/weekly/monthly) and send compliance (or other) reports via email to schedule recipients.  
**Diagnosis scope:** Single job only; evidence from code path and required runtime checks.

---

## 1. Scheduler registration

| Item | Value |
|------|--------|
| **Registered** | Yes |
| **Trigger** | `CronTrigger(minute=0, timezone=SCHEDULER_TIMEZONE)` |
| **Cron/interval** | Every hour at minute 0 (00:00, 01:00, … UTC) |
| **Timezone** | `SCHEDULER_TIMEZONE = timezone.utc` (server.py) |
| **next_run_time** | Next :00 UTC |
| **Callable used at runtime** | `job_runner:run_scheduled_job` with `args=["scheduled_reports"]`, `kwargs={"run_type": "schedule"}` |

**Exact registration path:**  
`server.py` lifespan:

```python
scheduler.add_job(
    "job_runner:run_scheduled_job",
    CronTrigger(minute=0, timezone=SCHEDULER_TIMEZONE),
    id="scheduled_reports",
    name="Process Scheduled Reports",
    replace_existing=True,
    args=["scheduled_reports"],
    kwargs={"run_type": "schedule"},
    misfire_grace_time=300,
    coalesce=True,
    max_instances=1,
)
```

---

## 2. Execution path trace

| Step | Component | Confirmed |
|------|-----------|-----------|
| APScheduler trigger | Fires every hour at :00 UTC, invokes callable | Yes |
| `run_scheduled_job("scheduled_reports", "schedule")` | `job_runner.run_scheduled_job` | Yes |
| `run_instrumented` → `start_job_run` | Same as other scheduled jobs | Yes |
| Actual job function | `JOB_RUNNERS["scheduled_reports"]` = `run_scheduled_reports` | Yes |
| `run_scheduled_reports()` | Calls `ScheduledReportJob(db).process_scheduled_reports()` | Yes |
| `finish_job_run_*` | Called from `run_instrumented` based on outcome | Yes |

**Instrumented path:** Yes. No bypass; same pattern as daily_reminders.

**Break point:** None in code. If no job_runs row, failure is at runtime (process/DB or exception before `start_job_run`).

---

## 3. Why “today’s daily report” might not have sent

The job only sends for schedules that are **due**. A schedule is due when:

- `report_schedules.is_active` is true, and  
- `report_schedules.next_scheduled` is `<= now` (ISO string) or `null`.

After a successful send, `next_scheduled` is advanced (e.g. daily → next day). So if “daily report” did not send, check:

| Cause | What to check |
|-------|----------------|
| **Job never ran** | `job_runs` for `job_name: "scheduled_reports"` today; scheduler process up and same DB. |
| **No schedule due** | `db.report_schedules.find({ "is_active": true, "$or": [{ "next_scheduled": { "$lte": "<now-iso>" } }, { "next_scheduled": null }] })` — empty ⇒ none due. |
| **Schedule skipped** | Client missing; `subscription_status != "ACTIVE"`; `entitlement_status` not in `["ENABLED", None]`; `plan_registry.enforce_feature(client_id, "scheduled_reports")` denies (log: “Skipping scheduled report for client …”). |
| **Send failed** | `message_logs` for `template_key: "SCHEDULED_REPORT"` with status FAILED or BLOCKED_*; Postmark/orchestrator errors in logs. |

**Runtime verification:**

- **MongoDB:**  
  `db.job_runs.find({"job_name": "scheduled_reports"}).sort({started_at: -1}).limit(5)`  
  Confirm at least one run today and its `status` / `outcome_metrics`.
- **Due schedules:**  
  `db.report_schedules.find({ "is_active": true, "$or": [{ "next_scheduled": { "$lte": new Date().toISOString() } }, { "next_scheduled": null }] })`  
  Confirm the intended “daily” schedule appears and its `next_scheduled` / `last_sent`.

---

## 4. Business output verification

| Item | Detail |
|------|--------|
| **Expected output** | **message_logs:** entries with `template_key: "SCHEDULED_REPORT"`; report_schedules updated (`last_sent`, `last_attempted_at`, `next_scheduled`). |
| **Zero-output valid?** | Yes. “Scheduled reports: none due” is success with count 0 when no active schedules are due. |

---

## 5. Root cause summary

- **Design:** Job is registered and executed correctly; due logic and gating are in code.
- **If “daily report” did not send:** Confirm (1) job ran today (`job_runs`), (2) at least one schedule was due (`report_schedules` + `next_scheduled`), (3) client/plan/entitlement allowed, (4) send did not fail (message_logs / logs).

**Fix recommendation:** No code fix required for registration. Use the checks above in your environment to find whether the failure was: scheduler/process/DB, no due schedule, gating skip, or send failure.
