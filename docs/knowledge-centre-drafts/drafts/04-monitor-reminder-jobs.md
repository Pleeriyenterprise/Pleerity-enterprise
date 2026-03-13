---
title: How to Monitor Reminder Jobs
slug: monitor-reminder-jobs
audience: ADMIN
category_id: job-monitoring
module: Job Monitoring
excerpt: Where to see whether the daily compliance reminder job has run, how to interpret status, and when to use Run Now or escalate.
tags: admin, automation, reminders, daily_reminders, jobs, monitoring
status: draft
---

# How to Monitor Reminder Jobs

**Audience:** ADMIN / STAFF  
**Category:** Job Monitoring  
**Module:** Job Monitoring  
**Summary:** Where to see whether the daily compliance reminder job has run, how to interpret status, and when to use “Run Now” or escalate.

---

## Purpose

The platform sends daily compliance reminders (e.g. for expiring requirements) via a scheduled job called **daily_reminders**. This guide tells staff where to check that the job is running, what healthy vs unhealthy looks like, and how to respond to failures without incorrectly using “Run Now” as a routine step.

---

## When to use this guide

- You need to confirm that reminder emails (or SMS) are being sent.
- A client reports they did not receive a reminder.
- You see an incident or alert about reminder or automation failure.
- You are doing a routine check of automation health.

---

## Steps

1. **Open Automation Control Centre** — In the admin sidebar go to **Settings & System → Automation Control Centre** (or **System Health**). The exact path may be under “Automation” or “System Health.”
2. **Find the daily_reminders job** — In the job list, locate **daily_reminders** (job ID; may be labelled “Daily Compliance Reminders”). Check **Last run** / **Last success** and **Next run**.
3. **Interpret status** — **Healthy** usually means the last run succeeded and the next run is scheduled. **Degraded** means the last run had partial failure (e.g. some sends failed). **Never ran** or **Overdue** means the job has not run by the expected time; an incident may have been created.
4. **Check Notification Health** — Go to **Notification Health** (or **Email delivery**) to see delivery stats or message logs for reminder-related templates (e.g. COMPLIANCE_EXPIRY_REMINDER). Use this to confirm sends or see bounces/failures.
5. **If a client did not get a reminder** — Verify: (1) Client has **Settings → Notifications** with **Daily Reminders** and **Expiry Reminders** turned **on**. (2) Client has at least one requirement expiring in the reminder window. (3) The job actually ran (**Automation Control Centre** last run). (4) No delivery failure in Notification Health. If all are OK, the client may be outside the reminder window or there is a product bug; escalate if needed.
6. **Use “Run Now” only for recovery** — If the job missed a run (e.g. server was down), you can trigger **Run Now** once to catch up. Do **not** use Run Now as a substitute for fixing the schedule or the job itself. Document in the playbook when Run Now is appropriate.

---

## What happens next

- After Run Now, the job runs once in that moment; the next scheduled run is unchanged. Check job_runs or **Automation Control Centre** again to confirm the run completed.
- If the job keeps failing, check System Health (e.g. scheduler heartbeat), app logs, and database connectivity. Escalate using the **Reminder Failure Response** playbook if you have one.

---

## Common mistakes / troubleshooting

- **Run Now as routine:** Do not run daily_reminders manually every day. It is for recovery only.
- **Assuming “no reminder” = job broken:** Often the client has reminders off or no items due; check client preferences and data first.
- **Ignoring “not yet due since startup”:** If the app just restarted, “next run” may be in the future; that is normal. Only treat as a problem when the next run time is in the past and the job still shows as not run.

---

## Related guides

- Admin Console Overview  
- How to Review Email Failures  
- Reminder Failure Response (playbook)  
- How Reminder Alerts Work (user-facing)  

---

**Verification status:** Draft. Needs product review (e.g. exact job name and labels in Automation Centre, and that Run Now is idempotent and safe for daily_reminders).
