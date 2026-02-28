# Background automations and scheduled jobs

All times are **UTC**. The job scheduler (APScheduler) runs **in-process** with the FastAPI application. Jobs execute only while the API server is running.

## Why do I have to manually trigger jobs?

Automations run **only when the API process that started the scheduler is running**. If you have to run jobs manually for them to do anything, one of the following is usually true:

1. **The API server is not running 24/7**
   - **Local development:** If you stop the server (e.g. close the terminal), no jobs run until you start it again. Schedules (e.g. “9:00 UTC”) only fire when the process is up at that time.
   - **Hosting that spins down:** Some platforms (e.g. Render free tier, serverless, or “sleep after idle”) shut down the process when there’s no traffic. When the process is down, no cron runs. **Fix:** Use a plan or setup that keeps **one** API instance running all the time, or use an **external cron** (e.g. cron job or hosted scheduler) that calls your “run job now” endpoint on a schedule.

2. **Multiple API workers**
   - If you start the app with **multiple workers** (e.g. `uvicorn ... --workers 4`), each worker is a separate process. Each process runs its own scheduler, so jobs can run multiple times (once per worker), or in some deployments only one process is long-lived and the others are short-lived, so the scheduler may only run in one process. **Fix:** For scheduled jobs, run **one** worker (or one dedicated “worker” process) that stays up and owns the scheduler; use more workers only for HTTP if needed.

3. **Scheduler never started or not bound to the event loop**
   - If `PYTEST_RUNNING=1` is set, the scheduler is skipped. In production this should not be set.
   - If the app crashes or fails during startup before `scheduler.start()` runs, the scheduler never starts. Check startup logs for “Background job scheduler started” and any errors before it.
   - The scheduler must run on the same asyncio event loop as the FastAPI app. In `server.py` lifespan, the running loop is set on the scheduler before jobs are added and started (`scheduler._eventloop = asyncio.get_running_loop()`). If you see “No running event loop for scheduler” in logs, jobs will not run automatically until that is fixed.

4. **Jobs run but don’t do what you expect**
   - Delivery (email/SMS) can fail if Postmark/Twilio are not configured or are rate-limited; the job still “runs” but no email is sent.
   - Some jobs only act for clients in certain states (e.g. ENABLED entitlement, plan allows feature). See “Delivery dependencies” and “Plan/entitlement gating” below.

**Quick check:** Open **Admin → Dashboard → Jobs** (or call `GET /api/admin/jobs/status`). If you see “Next run” times for each job, the scheduler is running in that process. If you don’t, that process doesn’t have an active scheduler.

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
