# Focused runtime diagnosis: sla_watchdog

**Job:** sla_watchdog  
**Purpose:** Detect missed job runs, stale scheduler heartbeat, delivery_unknown buildup; create incidents and optionally send admin alert emails.  
**Scope:** This job only; exact break point and runtime evidence.

---

## 1. Scheduler registration

| Item | Value |
|------|--------|
| **Registered** | Yes |
| **Trigger** | `CronTrigger(minute="*/10", timezone=SCHEDULER_TIMEZONE)` |
| **Cron expression** | Every 10 minutes (:00, :10, :20, :30, :40, :50) |
| **Timezone** | `SCHEDULER_TIMEZONE = timezone.utc` |
| **next_run_time** | Next :00/:10/:20/:30/:40/:50 UTC; valid if scheduler uses UTC. |
| **Callable used at runtime** | `job_runner:run_scheduled_job` with `args=["sla_watchdog"]`, `kwargs={"run_type": "schedule"}`. |

**Exact registration (server.py):**

```python
scheduler.add_job(
    "job_runner:run_scheduled_job",
    CronTrigger(minute="*/10", timezone=SCHEDULER_TIMEZONE),
    id="sla_watchdog",
    name="SLA Watchdog (job run monitoring)",
    replace_existing=True,
    args=["sla_watchdog"],
    kwargs={"run_type": "schedule"},
)
```

---

## 2. Execution path

| Step | Confirmed |
|------|-----------|
| APScheduler trigger | Fires at */10 min UTC. |
| `run_scheduled_job("sla_watchdog", "schedule")` | Only scheduler entry point. |
| `run_instrumented("sla_watchdog", "schedule")` | Called by run_scheduled_job. |
| `start_job_run("sla_watchdog", "schedule")` | Called before fn(); no bypass. |
| Actual job | `JOB_RUNNERS["sla_watchdog"]` = `run_sla_watchdog` → `services.sla_watchdog.run_sla_watchdog()`. |
| `finish_job_run_success` | Called by run_instrumented (return dict has no outcome_status → default success). |

**Instrumented path:** Yes. No bypass.

**Break point:** None in code. If run_count stays 0 after the next :00/:10/:20/:30/:40/:50 UTC has passed, the break is runtime: scheduler not firing, exception before start_job_run, or different DB.

---

## 3. Runtime record verification

**Observed state:** registered = yes, next_run_time in the future, run_count = 0.

Possible causes:

| Cause | How to confirm |
|-------|----------------|
| **Not yet due** | next_run_time is the next :00/:10/… UTC. If server started recently, first run may not have occurred yet. Wait until next_run_time has passed, then re-check job_runs. |
| **Scheduler not firing** | After next_run_time has passed, if run_count still 0: check process logs for `job_run started job_name=sla_watchdog`; if missing, scheduler may not be executing jobs (event loop, jobstore, or process). |
| **Fails before start_job_run** | Logs: `run_instrumented: unknown job_id=sla_watchdog` or exception before `job_run started`. |
| **Writes to different DB** | Same process ⇒ same database.get_db(). If scheduler runs in another process, that process must call database.connect() and use same MONGO_URL/DB_NAME. |

**Runtime check:** Run `backend/scripts/proof_sla_watchdog_runtime.py` (see below) or:

- `db.job_runs.find({"job_name": "sla_watchdog"}).sort("started_at", -1).limit(5)`
- Count: `db.job_runs.count_documents({"job_name": "sla_watchdog"})`

---

## 4. Business output

| Output | Where | When |
|--------|--------|------|
| **Incidents** | `incidents` collection via `create_incident()` | Heartbeat stale (P1); delivery_unknown stale (P2); job never completed and not in grace period (P2/P1/P0); job missed SLA; job last run degraded (P2). |
| **Admin alert emails** | `notification_orchestrator.send(template_key="ADMIN_MANUAL", context={recipient, subject, body})` | When an incident is created and ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL is set. |
| **Detection** | Uses job_runs, scheduler_heartbeat, next_runs from scheduler, RECONCILIATION_JOBS / DELIVERY_UNKNOWN_STALE_HOURS. | Heartbeat stale; delivery_unknown stale; per-job last success/degraded and max_delay; grace period for “not yet due since startup”. |

**No-output valid?** Yes. If no conditions are met (heartbeat OK, no delivery_unknown stale, all jobs within SLA or in grace period), the watchdog creates zero incidents and returns success. That is a valid successful run.

**If no incidents:** Either (1) no qualifying conditions, (2) watchdog never ran (run_count 0), (3) conditions existed but not detected (logic/query bug), or (4) create_incident failed (e.g. DB). Runtime: confirm job_runs has at least one success for sla_watchdog, then check incidents and conditions (heartbeat, job_runs for other jobs, delivery_unknown).

---

## 5. Admin alerting

| Item | Value |
|------|--------|
| **ADMIN_ALERT_EMAILS** | Used by `_get_admin_alert_emails()` in sla_watchdog (comma-separated list). |
| **OPS_ALERT_EMAIL** | Fallback if ADMIN_ALERT_EMAILS not set (single value or comma-separated). |
| **Usage** | On each incident created, `_send_incident_alert_email()` is called; if env is empty, logs “ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL not set; SLA incident alert not sent” and returns False. |
| **Email path** | notification_orchestrator.send(template_key="ADMIN_MANUAL", client_id=None, context={recipient, subject, body}). Orchestrator supports client_id=None with recipient in context. |

**If not configured:** No admin emails for incidents; watchdog still creates incidents. “No admin email alerts” is expected when env is unset.

---

## 6. Admin observability

| View | Truthfulness for sla_watchdog |
|------|-------------------------------|
| **Automation Control Centre** | Uses job_runs and health-summary. If job_runs has rows for sla_watchdog, last run and state are correct. If run_count = 0, ACC shows “Never ran” or “Not yet due” from health-summary (next_run_iso). |
| **System Health** | sla_watchdog is in HEALTH_SUMMARY_JOBS; state from _compute_job_state_and_reason (last_completed, last_success, next_run_iso, etc.). Correct if job_runs is populated. |
| **Incidents** | Incidents list reads from incidents collection (same DB). If watchdog creates incidents, they appear here. |

---

## 7. Failure / degrade

| Scenario | Behaviour |
|----------|-----------|
| **Success, no qualifying incidents** | Returns dict with incidents_created=0, alerts_sent=0 → finish_job_run_success. Valid success. |
| **Success, incidents created** | Returns incidents_created>0; still success; incidents in DB; alerts sent if configured. |
| **Exception in run_sla_watchdog** | run_instrumented catches → finish_job_run_failure; job_runs status = failed. |
| **Alert config missing** | _send_incident_alert_email returns False; incidents_created still incremented; incident still created. No separate “missing config” incident; health-summary exposes alerting_configured from env. |

---

## 8. Database / environment consistency

Scheduler job store, job_runs, incidents, and observability routes all use the same DB in the same process (database.get_db()). Alert config from os.getenv in the same process. No code path uses a different DB for this job.

---

## 9. Root cause decision

**Primary diagnosis: F. Scheduler timing / not yet due** (when registered = yes, next_run_time in future, run_count = 0).

**Evidence:** sla_watchdog runs every 10 minutes at :00, :10, :20, :30, :40, :50 UTC. If “next_run_time in the future” is the next such tick and the server has not yet reached it, run_count = 0 is expected. So “not yet due” is the default interpretation.

**If after next_run_time has passed run_count is still 0:** Then the diagnosis shifts to **C** (triggered but instrumentation missing) or **H** (runtime failure before instrumentation), e.g. scheduler not actually executing the job or exception before start_job_run. Confirm with logs and runtime script.

---

## 10. Required output format (summary)

**JOB:** sla_watchdog

**1. Scheduler registration**  
- registered: yes  
- trigger: CronTrigger(minute="*/10", timezone=UTC)  
- next_run_time: next :00/:10/:20/:30/:40/:50 UTC  
- callable used: job_runner:run_scheduled_job (args=["sla_watchdog"], kwargs={"run_type": "schedule"})

**2. Execution path**  
- instrumented path confirmed: yes  
- break point if any: none in code

**3. Runtime records**  
- job_runs exists: verify with proof script or db.job_runs.find({"job_name": "sla_watchdog"})  
- run_count / last_run / last_status: from that query. Observed “run_count = 0” with next_run_time in future ⇒ consistent with not yet due.

**4. Business output**  
- expected: incidents when conditions met; optional admin emails if env set  
- actual: verify incidents collection and (if configured) message_logs for ADMIN_MANUAL  
- no-output valid?: yes (no incidents when no conditions)

**5. Admin alerting**  
- configured: only if ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL is set  
- if not configured: no emails; watchdog still creates incidents; log warning  
- actual: proof script reports env and recent incident alerts

**6. Admin observability**  
- Automation Control Centre / System Health / Incidents: correct if job_runs and incidents use same DB and sla_watchdog has run

**7. Failure/degrade**  
- full failure → finish_job_run_failure  
- no-incident success → finish_job_run_success  
- alert config missing → warning log; incidents still created

**8. Root cause**  
- primary: F (scheduler timing / not yet due) when run_count=0 and next_run_time still in future  
- evidence: */10 cron; first run only after next tick

**9. Fix recommendation**  
No code fix for “not yet due.” To confirm the job runs: (1) Run the runtime proof script after the next :10 boundary has passed. (2) If run_count remains 0, check logs for `job_run started job_name=sla_watchdog` and scheduler/process. (3) Set ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL if admin email alerts are required.
