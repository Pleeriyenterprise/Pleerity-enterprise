# Automation Reliability Audit

**Standard:** A worker is only considered healthy if it has **trigger proof**, **execution proof**, **output proof**, **failure recording**, and **admin visibility**. “Success” counts only when the automation completed end-to-end and the **expected business outcome** actually happened.

**Audit date:** 2026-02-20.

---

## 1. Automation Inventory

All jobs are registered in `backend/server.py` (lifespan) and implemented in `backend/job_runner.py` via `JOB_RUNNERS`. Each runs through `run_instrumented()` which writes to `job_runs`.

| Job ID | Trigger | Implementation |
|--------|---------|----------------|
| daily_reminders | Cron 09:00 UTC | run_daily_reminders → JobScheduler.send_daily_reminders |
| pending_verification_digest | Cron 09:30 UTC | run_pending_verification_digest → JobScheduler.send_pending_verification_digest |
| monthly_digest | Cron 1st 10:00 UTC | run_monthly_digests → JobScheduler.send_monthly_digests |
| compliance_check_morning | Cron 08:00 UTC | run_compliance_status_check → JobScheduler.check_compliance_status_changes |
| compliance_check_evening | Cron 18:00 UTC | run_compliance_status_check (same) |
| scheduled_reports | Cron every hour | run_scheduled_reports → ScheduledReportJob.process_scheduled_reports |
| compliance_score_snapshots | Cron 02:00 UTC | run_compliance_score_snapshots → capture_all_client_snapshots |
| expiry_rollover_recalc | Cron 00:10 UTC | run_expiry_rollover_recalc (enqueues recalc) |
| compliance_recalc_worker | Interval 15s | run_compliance_recalc_worker (processes queue) |
| compliance_recalc_sla_monitor | Cron */5 min | run_compliance_recalc_sla_monitor |
| notification_failure_spike_monitor | Cron */5 min | run_notification_failure_spike_monitor |
| sla_watchdog | Cron */10 min | run_sla_watchdog (creates incidents from job_runs) |
| notification_retry_worker | Cron every minute | run_notification_retry_worker |
| order_delivery_processing | Cron */5 min | run_order_delivery_processing |
| sla_monitoring | Cron */15 min | run_sla_monitoring |
| stuck_order_detection | Cron */30 min | run_stuck_order_detection |
| queued_order_processing | Cron */10 min | run_queued_order_processing |
| abandoned_intake_detection | Cron */15 min | run_abandoned_intake_detection |
| lead_followup_processing | Cron */15 min | run_lead_followup_processing |
| lead_sla_check | Cron hourly | run_lead_sla_check |
| checklist_nurture_processing | Cron 09:00 UTC | run_checklist_nurture_processing |
| risk_lead_nurture_processing | Cron 09:15 UTC | run_risk_lead_nurture_processing |
| pending_payment_lifecycle | Cron 03:00 UTC | run_pending_payment_lifecycle |
| predictive_insights_job | Cron 04:00 UTC | run_predictive_insights_job |
| risk_signals_job | Cron 04:30 UTC | run_risk_signals_job |
| work_order_sla_breach_job | Cron hourly | run_work_order_sla_breach_job |

---

## 2. End-to-End Status for Each Automation

### Working end-to-end (trigger + execution + business output + proof + failure recording)

| Job | Evidence |
|-----|----------|
| **compliance_recalc_worker** | Runs every 15s; processes `compliance_recalc_queue`; writes DONE/FAILED/DEAD; audit COMPLIANCE_RECALC_FAILED; score_events; job_runs. |
| **notification_retry_worker** | Processes `notification_retry_queue`; calls notification_orchestrator.process_retry; message_logs updated. |
| **order_delivery_processing** | order_delivery_service.process_finalising_orders; DB updates; job_runs. |
| **compliance_recalc_sla_monitor** | Reads queue; creates audit/incidents; optional email; job_runs. |
| **notification_failure_spike_monitor** | Counts FAILED message_logs; sends OPS alert; job_runs. |
| **sla_watchdog** | Reads job_runs last success; creates incidents; sends admin email if ADMIN_ALERT_EMAILS set; job_runs. |
| **expiry_rollover_recalc** | Enqueues recalc; queue records; job_runs. |
| **compliance_score_snapshots** | capture_all_client_snapshots → compliance_score_history; job_runs; **re-raises** on exception (no false success). |
| **run_* (most order/lead/queue jobs)** | job_runner re-raises on exception → finish_job_run_failure; job_runs. |

### Partially working (execution recorded, business outcome not fully verified)

| Job | Issue |
|-----|--------|
| **daily_reminders** | **False success:** `JobScheduler.send_daily_reminders()` catches all exceptions and **returns 0** (`services/jobs.py` ~225–228). job_runner then calls `finish_job_run_success(job_run_id, affected_clients_count=0)`. So any exception (DB, orchestrator, config) is reported as **success**. No proof that reminders were delivered; count is “clients we attempted,” not “emails delivered.” |
| **monthly_digest** | Same pattern: exception → return 0 → success recorded (`jobs.py` ~345–347). |
| **pending_verification_digest** | Same: exception → return 0 → success (`jobs.py` ~623–625). |
| **compliance_check_morning / evening** | `check_compliance_status_changes()` on exception returns 0 → success (`jobs.py` ~780–782). |
| **scheduled_reports** | `ScheduledReportJob.process_scheduled_reports()` on exception returns 0 → success (`jobs.py` ~1222–1224). |
| **send_renewal_reminders** (if ever used via job) | Same return 0 on exception. |

### Triggering only but not completing (business output / proof gaps)

| Job | Issue |
|-----|--------|
| **daily_reminders / monthly_digest** | `_send_reminder_email` / `_send_digest_email` catch exceptions and **do not re-raise** (`jobs.py` _send_reminder_email ~412–413, _send_digest_email ~413–415). So if 5 of 10 reminder emails fail, the job still returns count 10 (or 7) and is marked **success**. Per-recipient failure is only in message_logs (if orchestrator wrote before failing); job_runs shows success. **Partial failure is invisible at job level.** |

### Not working / cannot verify

- **System Health** shows only **compliance_recalc_worker** with a last success time when the rest have no runs in `job_runs` (e.g. scheduler not running in API process, or jobs never executed). That is a **deployment/process** issue, not per-job logic.
- **Notification Health** empty: if no messages have been sent or logged, there is nothing to show. Emptiness does not by itself mean “not working”; it can mean no traffic. If reminders/digests are supposed to run and message_logs stay empty, that indicates reminders/digests are not running or not going through the orchestrator.

---

## 3. Proof (where evidence lives)

| Evidence | Location |
|----------|----------|
| Job run (start/finish, status, duration, error) | `job_runs` collection; `services/job_run_service.py` |
| Last success for System Health | `GET /api/admin/observability/health-summary` → `job_runs` for key_jobs |
| Failures (24h) | Aggregated from `job_runs` (status=failed, finished_at in window) in Automation Control Centre |
| Email/SMS send attempt and result | `message_logs` (PENDING → sent/FAILED/DEFERRED_THROTTLED); Postmark webhook updates delivery/bounce |
| Reminder sent (audit) | `audit_logs` REMINDER_SENT (jobs.py _send_reminder_email); digest: digest_logs + DIGEST_SENT audit |
| Compliance recalc | compliance_recalc_queue (PENDING/RUNNING/DONE/FAILED/DEAD); score_events; audit COMPLIANCE_RECALC_FAILED |
| Incidents | `incidents`; created by sla_watchdog; list/ack/resolve via observability API |
| Admin alert email | sla_watchdog _send_incident_alert_email; requires ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL |

---

## 4. Silent Failure Risks

1. **Reminder/digest/verification digest/status check/scheduled reports**  
   Any exception inside the `JobScheduler` / `ScheduledReportJob` methods is caught and **return 0**. The job is then recorded as **success** in `job_runs`. Admins see “Last success” and no failure. **Risk:** DB errors, missing env, orchestrator down, or partial outage are reported as success.
2. **Per-recipient send failure in reminders/digests**  
   If `notification_orchestrator.send()` fails for one recipient, `_send_reminder_email` catches and logs; the loop continues. The job still returns a count and is marked success. **Risk:** Some users never receive reminders; job_runs and System Health still show success.
3. **SLA watchdog not running**  
   If the scheduler is not running in the API process (or sla_watchdog is not registered), no incidents are created for missed job SLAs. **Risk:** No incidents and no admin alerts even when jobs never run.
4. **Admin alert emails not configured**  
   If `ADMIN_ALERT_EMAILS` and `OPS_ALERT_EMAIL` are unset, sla_watchdog creates incidents but does not send email. **Risk:** Incidents exist in DB but admins are not notified.
5. **Notification Health / message_logs**  
   If notification jobs never run or never call the orchestrator, message_logs stay empty. **Risk:** “Empty” looks like “no data” rather than “automations not running.”

---

## 5. Monitoring Gaps

| Gap | Detail |
|-----|--------|
| **No “business outcome” check for reminders/digests** | job_runs records “job finished without exception.” It does not verify that message_logs show a sent reminder for each intended recipient or that Postmark reported delivery. |
| **No delivery verification in job success** | Success is “orchestrator.send() returned” (or job returned 0 after exception). No check of message_log status or webhook delivery. |
| **Swallowed exceptions in jobs.py** | send_daily_reminders, send_monthly_digests, send_pending_verification_digest, check_compliance_status_changes, send_renewal_reminders, process_scheduled_reports all `return 0` on exception. So “no run” or “error” can appear as “success, count 0.” |
| **System Health key_jobs** | Only five jobs shown: daily_reminders, monthly_digest, compliance_score_snapshots, compliance_recalc_worker, expiry_rollover_recalc. Others (e.g. scheduled_reports, notification_retry_worker) are not in the health summary. |
| **Notification Health** | Depends on message_logs. If no notifications are sent (e.g. no clients, or jobs not running), the UI is empty. No distinct “notification jobs ran but sent 0” vs “notification jobs did not run.” |
| **Failed-job panel** | Automation Control Centre shows “Failures (24h)” from job_runs. Jobs that “succeed” (including false success) never appear as failures. |

---

## 6. False Success Conditions

| Condition | Where | Effect |
|----------|--------|--------|
| Exception in send_daily_reminders | jobs.py ~225–228 | return 0 → finish_job_run_success(0) → job_runs status=success. |
| Exception in send_monthly_digests | jobs.py ~345–347 | Same. |
| Exception in send_pending_verification_digest | jobs.py ~623–625 | Same. |
| Exception in check_compliance_status_changes | jobs.py ~780–782 | Same. |
| Exception in process_scheduled_reports | jobs.py ~1222–1224 | Same. |
| Exception in send_renewal_reminders | jobs.py ~973–975 | Same. |
| _send_reminder_email fails for one of N recipients | jobs.py ~412–413 | Exception caught and logged; job continues and returns count; job_runs success. |
| _send_digest_email returns False (e.g. send failed) | jobs.py ~413–415 | Skipped recipient; digest_count not incremented; no re-raise. Job can still succeed with lower count. |

---

## 7. Critical Fixes Required Before Launch

1. **Stop reporting success on exception (jobs.py)**  
   In `send_daily_reminders`, `send_monthly_digests`, `send_pending_verification_digest`, `check_compliance_status_changes`, `send_renewal_reminders`, and `ScheduledReportJob.process_scheduled_reports`: **re-raise** after logging instead of `return 0`. That way `run_instrumented` will call `finish_job_run_failure` and the job will appear in job_runs as failed and in Failures (24h).
2. **Optional but recommended: _send_reminder_email / _send_digest_email**  
   Consider re-raising on first send failure so the whole job fails and is recorded as failed (or aggregate failures and fail the job if any failed). Today, partial send failure is invisible at job level.
3. **Ensure scheduler runs in API process**  
   Confirm one process runs both API and scheduler (see `docs/AUTOMATION_CONTROL_CENTRE_AND_JOB_RUNS.md`). Check logs for “Background job scheduler started with N job(s).”
4. **Set ADMIN_ALERT_EMAILS (or OPS_ALERT_EMAIL)**  
   So that sla_watchdog incident creation results in admin email alerts.
5. **Duplicate run_predictive_insights_job**  
   Resolved in this audit: duplicate definition in job_runner.py was removed so there is a single implementation with correct return value.

---

## 8. Recommended Reliable Architecture

- **Keep current model** (APScheduler in-process, job_runs, sla_watchdog, incidents) but **fix false success** as above so that any exception in a job leads to `finish_job_run_failure` and visible failures and incidents.
- **Optional hardening:**
  - **Per-job “output proof”:** For reminder/digest jobs, after the run query message_logs for the relevant template_key/time window and fail the job (or set a “degraded” outcome) if expected count of sent messages is below intended.
  - **Heartbeat:** A small job that writes a timestamp to a “heartbeat” collection every 1–5 minutes; health dashboard shows “last heartbeat.” If scheduler or process dies, heartbeat stops.
  - **Delivery verification:** Use Postmark webhooks (already present) to update message_logs; consider a separate “delivery reconciliation” job that flags reminders with no “delivered”/“opened” within N hours for follow-up.
- **Queue-based workers:** For scale, moving reminder/digest/send logic to a queue (e.g. Redis/BullMQ or DB queue) with retries and dead-letter would give per-message failure and retry. Current design is “one job run, many sends”; a queue would make each send a unit of work with its own success/failure. That is a larger change; the immediate fix is to stop swallowing exceptions and re-raise so job_runs and SLA watchdog reflect reality.
- **Dead-letter / admin alert on repeated failure:** sla_watchdog already creates incidents when a job has not succeeded within max_delay. With false success removed, jobs that repeatedly fail will show in job_runs and trigger incidents and (if configured) admin emails.

---

## Summary

- **Trigger and execution:** All listed jobs are registered and run via `run_instrumented()` when the scheduler runs in the API process; execution is recorded in `job_runs`.
- **Business outcome and proof:** Reminder/digest/verification/status-check/scheduled-report jobs **do not** guarantee that “success” means “business outcome achieved.” They swallow exceptions and return 0, so the system records **success** and **no failure**. Per-recipient send failures in reminders/digests are not reflected as job failure.
- **Failure recording and admin visibility:** When a job **raises**, failure is recorded and visible (job_runs, Failures (24h), sla_watchdog, incidents, optional admin email). When a job **returns 0 after catch**, failure is not recorded and admin is not alerted.
- **Critical fix:** Re-raise in all `jobs.py` job methods that currently `return 0` on exception so that automation success in production reflects actual end-to-end completion, and so admins are alerted when automations fail.
