# Admin – Reminder System (Training Manual)

## 1. Module name
**Reminder System (Admin / Automation)**

## 2. Audience
**Admin / internal staff.** Clients control *whether* they receive reminders (Notification preferences); admins monitor *that* reminders run and troubleshoot delivery.

## 3. Purpose
The platform sends **daily compliance reminders** (e.g. for expiring requirements) via the `daily_reminders` scheduled job. Admins need to: (1) understand that reminders are sent automatically, (2) know where to see if the job ran (Automation Centre, Notification Health), (3) know when to use “Run Now” (recovery/testing only), and (4) understand client-facing preference toggles (email/SMS, daily_reminder_enabled, expiry_reminders).

## 4. Where to find it in the UI
- **Automation Centre:** `/admin/automation` (or under Settings & System). Lists scheduled jobs including `daily_reminders`; shows last run, next run, status (healthy, degraded, never ran, etc.), and **Run Now** button.
- **System Health:** `/admin/system-health`. Overall health and per-job status; may show stale heartbeat or failed jobs.
- **Notification Health:** `/admin/notification-health`. Email/delivery health and possibly message logs; useful to see if reminder emails were sent or bounced.
- **Incidents:** `/admin/incidents`. Open incidents for missed jobs, stale heartbeat, or delivery issues (if created by SLA watchdog or other automation).

## 5. What the user sees
- **Automation Centre:** Table or cards of jobs. For `daily_reminders`: job name, schedule (e.g. daily 09:00 UTC), last run time, next run time, outcome (success/degraded/failed), and actions (Run Now). Reasons and recommended actions for “never ran” or “overdue” states.
- **Notification Health:** Delivery stats, top templates, searches with no results (for KB); may include message_logs or delivery reconciliation data for reminder templates (e.g. COMPLIANCE_EXPIRY_REMINDER).
- **Incidents:** List of open/acknowledged/resolved incidents; source may be job monitor, heartbeat, or delivery_unknown_stale.

## 6. Step-by-step actions
| Action | What to click | What happens |
|--------|----------------|--------------|
| Check if reminders ran today | Automation Centre → find `daily_reminders` → check Last run / Last success | If last success is today and outcome is success, job ran. |
| See why a job shows “never ran” or “overdue” | Automation Centre → click job or reason text | UI shows reason (e.g. “Not yet due since startup”, “Overdue – incident created”). |
| Run reminders manually (recovery only) | Automation Centre → `daily_reminders` → Run Now | Backend: triggers `run_instrumented("daily_reminders", ...)`. Job runs once. Use only for recovery or testing; do not use routinely. |
| Check delivery of reminder emails | Notification Health (or Email delivery tab) | View message logs or delivery stats for reminder template; see sent/bounced/unknown. |
| Respond to an incident | Incidents → open incident → Acknowledge or Resolve | Marks incident acknowledged/resolved; does not re-run the job (use Run Now separately if needed). |

## 7. What happens after each action
- **Run Now:** Job executes in the same process as the API; `daily_reminders` calls `send_daily_reminders()` which respects client notification preferences (daily_reminder_enabled, expiry_reminders). Emails/SMS sent to clients with expiring items and preferences ON. Outcome recorded in job_runs.
- **Acknowledge/Resolve incident:** Status updated; no automatic re-run.
- **View health:** Read-only; no change.

## 8. Status/outcome examples
- **daily_reminders – Healthy:** Last run succeeded; next run scheduled. No action.
- **daily_reminders – Never ran (overdue):** Job has not run by expected time; incident may be created. Consider Run Now once and check scheduler.
- **daily_reminders – Degraded:** Last run had partial failure (e.g. some sends failed); check Notification Health for errors.
- **Stale heartbeat:** Scheduler heartbeat not updated; overall health may show Failed. Check app/scheduler process and restart if needed.

## 9. Common errors or confusing points
- **Run Now is not for “send reminders now” as a normal operation.** It is for recovery after a missed run or for testing. Routine sends are on schedule (e.g. 09:00 UTC).
- **Client didn’t get a reminder:** Check (1) client has expiring requirements in the window, (2) client preferences have daily_reminder_enabled and expiry_reminders ON, (3) job ran (Automation Centre), (4) delivery (Notification Health / message_logs). No “resend” button for a single client in base implementation.
- **Job shows “not yet due since startup”:** Scheduler started recently; next run is in the future. Normal; no action unless next run is in the past.

## 10. Current limitations or known gaps
- **Needs runtime confirmation:** That `daily_reminders` actually sends email in your environment (template COMPLIANCE_EXPIRY_REMINDER and notification_orchestrator). Proof script: `backend/scripts/proof_daily_reminders_runtime.py`.
- No admin UI to “preview” or “send test reminder” to one client from the admin console in base implementation.
- SMS reminders depend on SMS config and client phone verification; if SMS is off, only email is sent.
- Deduplication: reminders are typically keyed by client + template + date so the same client doesn’t get duplicate emails the same day; Run Now may respect the same key (needs confirmation).

## 11. Notes for training staff
- “Reminders are automatic. We monitor that the job ran and that delivery is healthy. We only use Run Now when something went wrong and we’re recovering.”
- For “client didn’t get reminder” tickets: walk through preferences (client side), then job run (Automation Centre), then delivery (Notification Health).
- Point to client Reminder System manual for what clients can control (email/SMS toggles).

---

## Trainer walkthrough (5–10 minutes)

1. **Open Automation Centre** → find `daily_reminders` → explain “this job runs every day and sends compliance reminders to clients who have expiring items and have reminders enabled.”
2. **Show Last run / Next run / Status** → “If status is Healthy and last run is today, we’re good.”
3. **Show Run Now** → “Only use this for recovery or testing. Don’t run it every day manually.”
4. **Open Notification Health** → “Here we see if reminder emails were sent or if there were bounces.”
5. **Open Incidents** → “If the job misses a run or heartbeat is stale, we may get an incident here; acknowledge and resolve after fixing.”
6. **Briefly:** “Clients turn reminders on/off in Settings → Notifications; we don’t change that from here unless we have a client-specific override.”
