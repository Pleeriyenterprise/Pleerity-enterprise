# Automation Observability — Fully vs Partially Observable

**Date:** 2026-02-20  
**Scope:** Automation Centre UI, outcome_metrics on all critical notification jobs, degraded-run alerting, delivery reconciliation.  
**Last-mile:** Delivery reconciliation extended to pending_verification_digest, compliance_check_*, scheduled_reports; delivery state definitions API; job-run message_logs drill-down/export; observability report (fully / partially / execution-only).

---

## 1. Automation Centre table/UI

**Done:**

- **Status column** with visible state per job:
  - **Healthy** (green) — last run `status === 'success'`
  - **Degraded** (amber) — last run `status === 'degraded'`
  - **Failed** (red) — last run `status === 'failed'` or scheduler_heartbeat when heartbeat is stale
  - **No runs** (gray) — no run recorded
- **Last run**, **Last success**, **Last degraded**, **Failures (24h)**, **Next schedule**, **Actions**.
- **Degraded (24h)** count shown when > 0 (e.g. “(2 degraded 24h)” next to status).
- **Stale heartbeat banner** (red) when health summary reports `heartbeat_stale`; table also fetches health summary for heartbeat and status.
- Job state is derived from latest run in `job_runs`; degraded runs are counted and shown.

**Files:** `frontend/src/pages/AdminAutomationCentrePage.js` (status column, degraded column, heartbeat banner, health summary fetch).

---

## 2. outcome_status and outcome_metrics (consistent)

**Done for:**

| Job | outcome_status | outcome_metrics |
|-----|----------------|-----------------|
| **daily_reminders** | success / degraded / failed | expected_count, attempted_count, success_count, failed_count, skipped_count |
| **monthly_digest** | success / degraded / failed | same |
| **pending_verification_digest** | success / degraded / failed | same (attempted = admin recipients, success/failed from send loop) |
| **compliance_check_morning / evening** | success / degraded / failed | same (attempted_alerts, success = alert_count, failed_alerts) |
| **scheduled_reports** | success / degraded / failed | same (attempted_reports, success = reports_sent, failed_reports) |

**Runner:** All of the above return a dict with `outcome_status` and `outcome_metrics`; `run_instrumented` records them in `job_runs` and calls `finish_job_run_degraded` or `finish_job_run_failure` when appropriate.

**Partially observable:**  
Jobs that do not send per-recipient notifications (e.g. expiry_rollover_recalc, compliance_recalc_worker) still only expose a single `count` or message; they do not need attempted/success/failed breakdown unless we add it later.

---

## 3. Repeated degraded runs → admin-visible alerts

**Done:**

- **SLA watchdog** (every 10 min):
  - If the latest run for a monitored job is within the SLA window but has **status = degraded**, it creates a **P2 incident**: “Job &lt;name&gt; last run was degraded”.
  - Dedupe: one open incident per job with `metadata.degraded_run: true`; no duplicate until that incident is resolved.
  - Admin alert email is sent when `ADMIN_ALERT_EMAILS` / `OPS_ALERT_EMAIL` is set.
- Monitored jobs: daily_reminders, monthly_digest, compliance_score_snapshots, expiry_rollover_recalc, compliance_recalc_worker.

**File:** `backend/services/sla_watchdog.py`.

---

## 4. Delivery reconciliation (attempted / provider accepted / delivered / bounced / unknown)

**Done:**

- **delivery_reconciliation** job runs every 15 minutes.
- For **all notification/report job runs** in the last **48 hours** (daily_reminders, monthly_digest, pending_verification_digest, compliance_check_morning/evening, scheduled_reports):
  - Finds `message_logs` in the run’s time window (started_at → finished_at + 2h) with `template_key` in `COMPLIANCE_EXPIRY_REMINDER`, `COMPLIANCE_EXPIRY_REMINDER_SMS`, `MONTHLY_DIGEST`.
  - Aggregates by `status` (SENT, DELIVERED, BOUNCED, FAILED).
  - Writes back into the run’s **outcome_metrics**:
    - **delivery_provider_accepted** — SENT + DELIVERED + BOUNCED (accepted by provider).
    - **delivery_delivered** — DELIVERED (Postmark delivery webhook).
    - **delivery_bounced** — BOUNCED (Postmark bounce webhook).
    - **delivery_unknown** — SENT (accepted but no delivery webhook yet).
    - **delivery_failed** — FAILED (send failed).
- Existing Postmark webhook behaviour is unchanged (message_logs updated to DELIVERED/BOUNCED); reconciliation only reads and aggregates.

**Files:**  
`backend/services/delivery_reconciliation.py`, `backend/job_runner.py` (run_delivery_reconciliation), `backend/server.py` (scheduler every 15 min).

---

## 5. Delivery state definitions (admin-facing)

**Done:**

- **GET /api/admin/observability/delivery-state-definitions** returns human-readable explanations for each delivery state used in `outcome_metrics`:
  - **provider_accepted** — Message accepted by provider for delivery; final delivery/bounce may not yet be confirmed.
  - **delivered** — Provider confirmed delivery (e.g. webhook); message reached recipient.
  - **bounced** — Provider reported bounce; message was not delivered.
  - **unknown** — Accepted but no delivery/bounce event yet (webhooks may arrive later).
  - **failed** — Send failed before provider acceptance (validation, rate limit, or API error).

**File:** `backend/routes/observability.py` (`DELIVERY_STATE_DEFINITIONS`, `get_delivery_state_definitions`).

---

## 6. Drill-down / export: message_logs per job run

**Done:**

- **GET /api/admin/observability/job-runs/{run_id}/message-logs** returns message_logs that belong to the given job run (same time window and template_keys as delivery reconciliation). Useful for inspecting degraded or failed runs.
- **Query params:** `format=json` (default) or `format=csv`; `limit` (default 500, max 2000).
- CSV response is downloadable (`Content-Disposition: attachment`).

**File:** `backend/routes/observability.py`; `backend/services/delivery_reconciliation.py` (`get_message_logs_for_run`).

---

## 7. Observability report: fully vs partially vs execution-only

### Fully observable (run + business outcome + delivery)

| Job | What is observed |
|-----|------------------|
| **daily_reminders** | Run status, attempted/success/failed/skipped counts, delivery_provider_accepted, delivery_delivered, delivery_bounced, delivery_unknown, delivery_failed (reconciled); drill-down message_logs. |
| **monthly_digest** | Same as above. |
| **pending_verification_digest** | Run status, outcome_metrics (attempted/success/failed), delivery_* after reconciliation; drill-down message_logs. |
| **compliance_check_morning** / **compliance_check_evening** | Run status, outcome_metrics (attempted_alerts, success, failed), delivery_* after reconciliation; drill-down message_logs. |
| **scheduled_reports** | Run status, outcome_metrics (attempted_reports, success, failed), delivery_* after reconciliation; drill-down message_logs. |

All of the above: status badge in Automation Centre, last success/failure/degraded in System Health, SLA/degraded incidents, optional message_logs export per run.

### Partially observable (run + business outcome, no delivery reconciliation)

| Job | What is observed | Gap |
|-----|------------------|-----|
| **renewal_reminders** | Run status, counts; exceptions re-raised so failures are recorded. | Not in RECONCILIATION_JOBS; no delivery_* in outcome_metrics (can be added later with RENEWAL_REMINDER template). |
| **notification_retry_worker** | Run status, counts. | No per-run delivery breakdown; retries are internal. |
| **notification_failure_spike_monitor** | Run status. | Alerting only; no delivery reconciliation. |

### Execution-level only (run success/failure + optional count)

| Job | What is observed |
|-----|------------------|
| **compliance_score_snapshots** | Run status, completion; no per-client outcome breakdown. |
| **expiry_rollover_recalc** | Run status; no delivery. |
| **compliance_recalc_worker** | Run status; no delivery. |
| **sla_watchdog** | Run status; creates incidents. |
| **scheduler_heartbeat** | Run status; last_heartbeat_at in health summary. |
| **delivery_reconciliation** | Run status; count of runs updated. |

These jobs do not produce per-recipient message_logs tied to a single run in the same way; they are observable at “did the job run and finish (or fail)” level.

---

## 8. Files changed (last-mile task)

| Area | File |
|------|------|
| Delivery reconciliation extended | `backend/services/delivery_reconciliation.py` (RECONCILIATION_JOBS + pending_verification_digest, compliance_check_*, scheduled_reports; get_message_logs_for_run) |
| Delivery state definitions | `backend/routes/observability.py` (DELIVERY_STATE_DEFINITIONS, GET /delivery-state-definitions) |
| Drill-down / export message_logs | `backend/routes/observability.py` (GET job-runs/:id/message-logs, format=json or csv); `frontend/src/api/client.js` (getJobRunMessageLogs, getJobRunMessageLogsCsv); `frontend/src/pages/AdminAutomationCentrePage.js` (Message logs button for degraded/failed runs, modal with table and Export CSV) |
| Doc | `docs/AUTOMATION_OBSERVABILITY_SUMMARY.md` |

---

## Summary

- **Fully observable:** daily_reminders, monthly_digest, pending_verification_digest, compliance_check_morning/evening, scheduled_reports — run status, outcome_metrics (attempted/success/failed), delivery_* after reconciliation, and optional message_logs drill-down/export. Automation Centre and System Health show status, heartbeat, and alerting; delivery state definitions endpoint explains each delivery state.
- **Partially observable:** renewal_reminders, notification_retry_worker, notification_failure_spike_monitor — run and outcome visible; no delivery reconciliation (or no per-run delivery breakdown).
- **Execution-level only:** compliance_score_snapshots, expiry_rollover_recalc, compliance_recalc_worker, sla_watchdog, scheduler_heartbeat, delivery_reconciliation — run success/failure (and optional count) only; no business-outcome or delivery breakdown.
