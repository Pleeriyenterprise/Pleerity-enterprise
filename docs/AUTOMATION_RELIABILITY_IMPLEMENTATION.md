# Automation Reliability Implementation Summary

**Date:** 2026-02-20  
**Objective:** Fix the automation layer so system health reflects real end-to-end outcomes; eliminate false success; add outcome metrics, heartbeat, and clear notification/alerting visibility.

---

## 1. Files Changed

| File | Changes |
|------|---------|
| `backend/services/jobs.py` | Re-raise on exception in send_daily_reminders, send_monthly_digests, send_pending_verification_digest, check_compliance_status_changes, send_renewal_reminders, ScheduledReportJob.process_scheduled_reports. _send_reminder_email returns bool; send_daily_reminders/send_monthly_digests return dict with outcome_status and outcome_metrics (attempted/success/failed). |
| `backend/services/job_run_service.py` | Added STATUS_DEGRADED, OUTCOME_* constants; finish_job_run_success accepts outcome_status and outcome_metrics; finish_job_run_failure sets outcome_status=OUTCOME_FAILED; new finish_job_run_degraded. |
| `backend/job_runner.py` | run_instrumented handles outcome_status (success/degraded/failed) and outcome_metrics; calls finish_job_run_degraded when outcome_status=degraded, finish_job_run_failure when outcome_status=failed; run_daily_reminders/run_monthly_digests return full result dict; added run_scheduler_heartbeat and JOB_RUNNERS["scheduler_heartbeat"]. |
| `backend/server.py` | Registered scheduler_heartbeat job (IntervalTrigger every 2 min). |
| `backend/routes/observability.py` | HEALTH_SUMMARY_JOBS expanded; get_health_summary returns per-job last_triggered/last_success/last_failure/last_degraded/outcome_status/outcome_metrics, last_heartbeat_at, heartbeat_stale, alerting_configured. |
| `backend/services/sla_watchdog.py` | Treats status in (success, degraded) as “job ran” for SLA so incidents are not created when the only run was degraded. |
| `backend/routes/admin.py` | get_notification_health_summary returns notification_health_status (sent_ok, partial_failure, failed, notifications_queued, no_notifications_due, job_did_not_run, cannot_verify) and uses reminder job outcome_metrics to detect job_did_not_run when logs empty. |
| `frontend/src/pages/AdminSystemHealthPage.js` | Displays last_heartbeat_at and heartbeat_stale; shows alert when alerting_configured is false. |

---

## 2. Jobs Patched (No Longer Swallow Exceptions)

| Job | Method | Change |
|-----|--------|--------|
| daily_reminders | JobScheduler.send_daily_reminders | except: logger.exception; raise (was return 0) |
| monthly_digest | JobScheduler.send_monthly_digests | except: logger.exception; raise (was return 0) |
| pending_verification_digest | JobScheduler.send_pending_verification_digest | except: logger.exception; raise (was return 0) |
| compliance_check_morning / evening | JobScheduler.check_compliance_status_changes | except: logger.exception; raise (was return 0) |
| renewal_reminders | JobScheduler.send_renewal_reminders | except: logger.exception; raise (was return 0) |
| scheduled_reports | ScheduledReportJob.process_scheduled_reports | except: logger.exception; raise (was return 0) |

Any exception in these methods now propagates; `run_instrumented` calls `finish_job_run_failure`, so the run is recorded as **failed** and appears in Failures (24h) and recent_failures.

---

## 3. Schema Updates

**job_runs (additive):**

- `status`: may now be `"degraded"` in addition to `"running"` | `"success"` | `"failed"` | `"timeout"` | `"skipped"`.
- `outcome_status`: optional string, one of `"success"` | `"degraded"` | `"failed"`.
- `outcome_metrics`: optional object, e.g. `{ "expected_count", "attempted_count", "success_count", "failed_count", "skipped_count" }`.

**scheduler_heartbeat (new collection):**

- Single document `_id: "default"` with `last_heartbeat_at` (ISO string), `updated_at` (ISO string). Updated by the scheduler_heartbeat job every 2 minutes.

No breaking changes: existing job_runs documents remain valid; new fields are optional.

---

## 4. System Health Changes

- **Expanded jobs:** Health summary now includes: daily_reminders, pending_verification_digest, monthly_digest, compliance_check_morning, compliance_check_evening, scheduled_reports, compliance_score_snapshots, expiry_rollover_recalc, compliance_recalc_worker, notification_retry_worker, notification_failure_spike_monitor, sla_watchdog, scheduler_heartbeat.
- **Per-job detail:** For each job: last_triggered, last_completed, last_success, last_failure, last_failure_message, last_degraded, last_outcome_status, outcome_metrics.
- **Backward compat:** `last_success` map still returned for existing UI.
- **Heartbeat:** `last_heartbeat_at` and `heartbeat_stale` (true if older than 5 minutes).
- **Alerting:** `alerting_configured` (true if ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL is set).
- **Status badge:** `degraded` when no job runs recorded, heartbeat stale, or any job’s last outcome is degraded; `incident` when open P0/P1 incidents.

---

## 5. Notification Health Changes

- **notification_health_status** returned in summary with one of: `sent_ok`, `partial_failure`, `failed`, `notifications_queued`, `no_notifications_due`, `job_did_not_run`, `cannot_verify`.
- **job_did_not_run:** When the daily_reminders job ran in the window with attempted_count > 0 but message_logs in the window are empty, status is `job_did_not_run` (reliability concern).
- **Empty state:** No longer ambiguous; status explains whether there were no notifications due, or jobs ran but produced no logs.

---

## 6. Alerting Changes

- **Config surface:** Health summary returns `alerting_configured`. System Health UI shows a notice when false, telling admin to set ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL.
- **SLA watchdog:** Unchanged behaviour for creating incidents and sending email when ADMIN_ALERT_EMAILS/OPS_ALERT_EMAIL is set. Now treats runs with status `success` or `degraded` as “job ran” so we do not create incidents solely because the last run was degraded.
- **Failed runs:** Job failures are recorded in job_runs; SLA watchdog creates incidents when a job has not completed (success or degraded) within max_delay. No new separate “alert on every failure” email; incidents remain the mechanism and are emailed when config is set.

---

## 7. Remaining Risks

- **Per-recipient failure in digest/verification digest:** We do not yet aggregate send outcome per recipient for pending_verification_digest or compliance_check; they still return a single count. Only daily_reminders and monthly_digest return full outcome_metrics and can report degraded/failed.
- **Scheduled reports:** process_scheduled_reports now re-raises on exception (no false success) but does not yet return outcome_metrics (attempted/success/failed) or outcome_status degraded; it returns a plain count.
- **UI for degraded runs:** Automation Control Centre table may still show “Last success” only for status=success; runs with status=degraded are visible in health-summary `jobs[job].last_degraded` and `last_outcome_status`. Frontend could be extended to show degraded in the table.
- **message_logs status casing:** Summary supports both "SENT"/"FAILED" and "sent"/"failed"; orchestrator uses "SENT"/"FAILED". If other code writes different casing, counts could be wrong.

---

## 8. Recommended Next-Step Hardening

- **Queue-based notifications:** Move reminder/digest sends to a per-message job (e.g. Redis/BullMQ or DB queue) so each send is a unit of work with its own success/failure and retry.
- **Dead-letter queue:** For messages that exceed max retries, persist to a dead-letter collection and surface in admin with alert.
- **Delivery reconciliation:** Job that compares reminder/digest job outcome_metrics to message_logs (and optionally Postmark delivery webhooks) and flags mismatches.
- **Scheduled reports outcome_metrics:** Have process_scheduled_reports return outcome_status and outcome_metrics (attempted/success/failed) so partial report failure is visible as degraded.

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Swallowed exception in a critical automation job results in a recorded failure | Met: all six jobs re-raise; run_instrumented calls finish_job_run_failure. |
| Reminder/digest jobs cannot report clean success when real outputs failed | Met: daily_reminders and monthly_digest return outcome_status failed/degraded and outcome_metrics; run_instrumented calls finish_job_run_degraded or finish_job_run_failure. |
| System health reflects real outcomes, not just execution | Met: status badge considers degraded and heartbeat; per-job last_success/last_failure/last_degraded and outcome_status returned. |
| Notification health is not empty/ambiguous when jobs were expected | Met: notification_health_status returned; job_did_not_run when reminder ran with attempts but no logs. |
| Admin can be alerted when automations fail, degrade, or are missed | Met: SLA watchdog creates incidents for missed runs; email sent when ADMIN_ALERT_EMAILS/OPS_ALERT_EMAIL set; alerting_configured surfaced so missing config is visible. |
| No existing working jobs broken by the patch | Met: backward-compatible last_success; jobs that return int still work; SLA watchdog treats degraded as “ran”. |
