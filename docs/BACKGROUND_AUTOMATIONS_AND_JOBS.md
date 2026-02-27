# Background automations and scheduled jobs

All times are **UTC**. The job scheduler (APScheduler) runs **in-process** with the FastAPI application. Jobs execute only while the API server is running.

## Why automations might not run or not deliver

1. **Server not running** – If the API process is stopped (e.g. dev machine off, deployment down), no jobs run.
2. **Scheduler not started** – Scheduler starts in `server.py` lifespan after DB connect. If `PYTEST_RUNNING=1`, scheduler is skipped.
3. **Delivery dependencies** – Reminders, digests, and scheduled reports use the notification orchestrator (Postmark for email, Twilio for SMS). If email/SMS is not configured or is rate-limited, sends can fail; job logic may still run but no email/SMS is delivered.
4. **Plan/entitlement gating** – Some jobs skip clients by plan or entitlement (e.g. scheduled reports require Portfolio+ and ENABLED entitlement; monthly digest respects `monthly_digest_enabled`).
5. **Stuck “Next” date (scheduled reports)** – If every send attempt fails, `next_scheduled` used to stay in the past. The job now advances `next_scheduled` to the next period when it’s already in the past so the UI shows a future date and the next run tries again.

---

## Registered jobs (from `server.py`)

| Job ID | Schedule (UTC) | Purpose |
|--------|----------------|---------|
| **daily_reminders** | 09:00 daily | Compliance expiry reminders (email/SMS per preferences). |
| **pending_verification_digest** | 09:30 daily | Pending verification digest (counts, no PII). |
| **monthly_digest** | 1st of month, 10:00 | Monthly compliance digest; respects `monthly_digest_enabled`. |
| **compliance_check_morning** | 08:00 daily | Compliance status change detection; sends alerts when status degrades. |
| **compliance_check_evening** | 18:00 daily | Same as morning. |
| **scheduled_reports** | Every hour (minute=0) | Processes due report schedules; sends report emails; advances `next_scheduled` (or on send failure when past). |
| **compliance_score_snapshots** | 02:00 daily | Writes compliance score history for trend analysis. |
| **expiry_rollover_recalc** | 00:10 daily | Recalculates scores for properties with due_date in rollover window. |
| **compliance_recalc_worker** | Every 15 s | Processes compliance_recalc_queue (event-driven score updates). |
| **compliance_recalc_sla_monitor** | Every 5 min | Handles stuck recalc jobs and alerts. |
| **notification_failure_spike_monitor** | Every 5 min | Monitors notification failure spikes. |
| **notification_retry_worker** | Every minute | Retries failed notifications from retry queue (outbox). |
| **order_delivery_processing** | Every 5 min | Delivers orders in FINALISING status. |
| **sla_monitoring** | Every 15 min | SLA warnings (75%) and breach notifications (100%). |
| **stuck_order_detection** | Every 30 min | Detects orders stuck in FINALISING. |
| **queued_order_processing** | Every 10 min | Processes queued orders (document generation). |
| **abandoned_intake_detection** | Every 15 min | Abandoned intake detection. |
| **lead_followup_processing** | Every 15 min | Lead follow-up processing. |
| **pending_payment_lifecycle** | 03:00 daily | Pending payment lifecycle (abandoned/archived). |
| **lead_sla_check** | Every hour (minute=0) | Lead SLA breach check. |
| **checklist_nurture_processing** | 09:00 daily | Checklist nurture (Day 2, 4, 6, 9). |
| **risk_lead_nurture_processing** | 09:15 daily | Risk-check lead nurture (steps 2–5 at day 2, 4, 6, 10). |

---

## Scheduled reports (client portal)

- **Trigger:** Job `scheduled_reports` runs every hour on the hour (UTC).
- **Logic:** `services/jobs.py` → `ScheduledReportJob.process_scheduled_reports()`.
- **Eligibility:** Active schedule, client ACTIVE, entitlement ENABLED, plan allows `scheduled_reports` (Portfolio+).
- **After send:** On success, `next_scheduled` and `last_sent` are set; `last_attempted_at` is always set when the job processes the schedule. If no email was sent and `next_scheduled` is already in the past (e.g. >30 min ago), it is still advanced to the next period so the UI “Next” date stays correct and the next run tries again.
- **UI:** Reports → Scheduled Reports shows `next_scheduled`, and when available "Last sent" or "Last attempted" so you can see the job is running even when delivery fails.

---

## Manual run (admin)

Admin can trigger job runs via the job runner (see `job_runner.py` and admin API for “run now” style endpoints) for testing or one-off execution.
