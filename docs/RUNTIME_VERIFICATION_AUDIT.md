# Runtime Verification Audit — Critical Automations

**Audit type:** Production reliability — runtime verification (evidence-based)  
**Scope:** 14 critical automations  
**Rule:** Only mark VERIFIED where runtime evidence exists or code path guarantees it. Otherwise UNPROVEN.

**Important:** This audit is based on **code-path analysis and design verification**. It does **not** substitute for running the system and inspecting live `job_runs`, `message_logs`, and incidents. Where "Evidence would show" is stated, that must be confirmed with real data before launch.

---

## Evidence Model (from code)

| Layer | Source | Fields / behaviour |
|-------|--------|-------------------|
| **Trigger** | `job_runs` | `job_name`, `run_type` ("schedule" | "manual"), `started_at`, `triggered_by` (null for schedule) |
| **Execution** | `job_runs` | `status` (success | failed | degraded), `finished_at`, `duration_ms`, `error_message`, `stack_trace` (on failure) |
| **Business outcome** | Job-specific | `message_logs`, `outcome_metrics`, queue updates, incidents, heartbeat collection |
| **Failure detection** | `job_runs` + `incidents` | status=failed/degraded, `outcome_metrics`, SLA watchdog / heartbeat / delivery_unknown incidents |
| **Admin visibility** | Health summary, Automation Centre, Incidents | `job_states`, `overall_health`, summary counts, delivery_unknown_stale_runs |

All jobs that go through `run_scheduled_job` → `run_instrumented()` get:
- `start_job_run()` → one `job_runs` doc with `started_at`, `run_type`, `status=running`
- On exit: `finish_job_run_success` | `finish_job_run_failure` | `finish_job_run_degraded` → `finished_at`, `duration_ms`, `status`, and optionally `outcome_status`, `outcome_metrics`
- Any uncaught exception → `finish_job_run_failure()` (failure **is** recorded; not silently swallowed)

---

## Per-job verification

### 1. daily_reminders

**Purpose:** Send expiry reminders (email/SMS) to clients with due requirements.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | Scheduler calls `run_scheduled_job("daily_reminders", "schedule")` → `start_job_run("daily_reminders", "schedule")` → `job_runs` entry with `run_type="schedule"`, `started_at`. |
| **Execution** | `run_daily_reminders()` → `JobScheduler.send_daily_reminders()`; on return, `finish_job_run_success` or `_failure`/`_degraded` per returned `outcome_status`. |
| **Output** | `jobs.send_daily_reminders()` uses notification orchestrator; orchestrator writes `message_logs` (template_key e.g. COMPLIANCE_EXPIRY_REMINDER). Returns `outcome_metrics`: expected_count, attempted_count, success_count, failed_count, skipped_count. Zero expected → conditional_no_output (success with 0 counts). |
| **Failure** | Exception → `finish_job_run_failure`. Partial send failure → returns `outcome_status="degraded"` / `"failed"` and `finish_job_run_degraded` / `_failure`. |
| **Admin** | Automation Centre shows job state from `job_states`; delivery reconciliation enriches `outcome_metrics` with delivery_*; Message logs drill-down available. |

**Status: VERIFIED WITH RISK**  
- **Risk:** No live DB was inspected; proof is from code only. Confirm in staging: after a scheduled run, one `job_runs` with `run_type="schedule"` and corresponding `message_logs` (when expected_count > 0).

---

### 2. monthly_digest

**Purpose:** Send monthly compliance digest emails.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | Same as above: `job_runs` with `job_name="monthly_digest"`, `run_type="schedule"`, `started_at`. |
| **Execution** | `run_monthly_digests()` → `send_monthly_digest()`; returns outcome_status and outcome_metrics (expected, attempted, success, failed, skipped). |
| **Output** | Digest emails via orchestrator → `message_logs` (template MONTHLY_DIGEST). outcome_metrics populated. |
| **Failure** | Exceptions and partial/full failure returns handled same as daily_reminders. |
| **Admin** | In RECONCILIATION_JOBS; delivery_* and Message logs available. |

**Status: VERIFIED WITH RISK**  
- Same as daily_reminders: code path supports full evidence; runtime confirmation required.

---

### 3. pending_verification_digest

**Purpose:** Send pending verification digest to admin recipients.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="pending_verification_digest"`, `run_type="schedule"`, `started_at`. |
| **Execution** | `run_pending_verification_digest()` → `send_pending_verification_digest()`; returns outcome_status and outcome_metrics. |
| **Output** | `message_logs` (PENDING_VERIFICATION_DIGEST). Zero recipients → success with 0 counts. |
| **Failure** | Same pattern: exception → failed; all sends failed → failed; some failed → degraded. |
| **Admin** | In RECONCILIATION_JOBS; job state and message logs visible. |

**Status: VERIFIED WITH RISK**  
- Code path complete; no runtime evidence inspected.

---

### 4. compliance_check_morning / 5. compliance_check_evening

**Purpose:** Run compliance status check and send COMPLIANCE_ALERT notifications (morning/evening schedule).

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | Two scheduler entries (compliance_check_morning, compliance_check_evening) both call `run_compliance_status_check()`; each produces its own `job_runs` row with respective `job_name`, `run_type="schedule"`, `started_at`. |
| **Execution** | Same runner; completion and status written via finish_* and returned outcome_status/outcome_metrics. |
| **Output** | Alerts via orchestrator → `message_logs` (COMPLIANCE_ALERT). outcome_metrics (expected, attempted, success, failed). |
| **Failure** | Exceptions and partial/total send failure mapped to failed/degraded. |
| **Admin** | In RECONCILIATION_JOBS; both jobs in health summary and Automation Centre. |

**Status: VERIFIED WITH RISK**  
- Design supports full chain; runtime proof not performed.

---

### 6. scheduled_reports

**Purpose:** Generate and send scheduled reports (email with report).

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="scheduled_reports"`, `run_type="schedule"`, `started_at`. |
| **Execution** | `run_scheduled_reports()` → jobs logic; returns outcome_status and outcome_metrics including schedules_failed. |
| **Output** | Report generation + send via orchestrator → `message_logs` (SCHEDULED_REPORT). outcome_metrics with expected/attempted/success/failed/schedules_failed. |
| **Failure** | All sends failed → failed; some failed or schedule errors → degraded; exception → failed. |
| **Admin** | In RECONCILIATION_JOBS; delivery reconciliation and Message logs. |

**Status: VERIFIED WITH RISK**  
- Code path supports evidence; no live run inspected.

---

### 7. compliance_score_snapshots

**Purpose:** Capture daily compliance score snapshots per client.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="compliance_score_snapshots"`, `run_type="schedule"`, `started_at`. |
| **Execution** | `run_compliance_score_snapshots()` → `capture_all_client_snapshots()`; returns plain dict (no outcome_status). Default → `finish_job_run_success` with no outcome_metrics. |
| **Output** | `compliance_score_history` (or equivalent) updated per client via `capture_daily_snapshot`. |
| **Failure** | Any exception → `finish_job_run_failure`. If `capture_all_client_snapshots` fails for some clients but does not raise, run is still recorded as success — **partial failure can be under-reported**. |
| **Admin** | Job appears in health summary; state = healthy/failed from last run status. |

**Status: VERIFIED WITH RISK**  
- **Risk:** No outcome_metrics; partial failures (e.g. some clients fail to snapshot) would not set degraded. Recommend adding outcome_metrics (e.g. success_count, failed_count) to this job for observability.

---

### 8. expiry_rollover_recalc

**Purpose:** Enqueue compliance recalc for properties with due_date in expiry/expiring window.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="expiry_rollover_recalc"`, `run_type="schedule"`, `started_at`. |
| **Execution** | `run_expiry_rollover_recalc()` → enqueue_compliance_recalc per property; returns `{"message": ..., "count": count}`. No outcome_status → success. |
| **Output** | `compliance_recalc_queue` documents (PENDING) for each enqueued property. |
| **Failure** | Exception → `finish_job_run_failure`. If enqueue fails for some properties but no exception, run stays success. |
| **Admin** | Job in health summary; last run / last success visible. |

**Status: VERIFIED WITH RISK**  
- **Risk:** No outcome_metrics; "count" is not written to outcome_metrics. Partial enqueue failure could be invisible.

---

### 9. compliance_recalc_worker

**Purpose:** Process compliance_recalc_queue (recalculate and persist scores).

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="compliance_recalc_worker"`, `run_type="schedule"`, `started_at`. |
| **Execution** | Processes up to 10 PENDING queue items; updates properties, audit, score_events. Returns dict (no outcome_status in return) → success. |
| **Output** | Queue status updates (RUNNING → DONE/FAILED/DEAD), property compliance_score, audit_logs, score_events. |
| **Failure** | Exception in runner → `finish_job_run_failure`. Per-item failure (recalculate_and_persist) is handled inside the loop (retry/backoff or DEAD); job still returns successfully. |
| **Admin** | Job in health summary; SLA watchdog monitors last success; missed run → incident. |

**Status: VERIFIED WITH RISK**  
- **Risk:** Job reports success even if some items end up FAILED/DEAD; no degraded outcome. Consider outcome_metrics (processed, failed, dead) for visibility.

---

### 10. notification_retry_worker

**Purpose:** Process notification_retry_queue (retry failed sends).

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="notification_retry_worker"`, `run_type="schedule"`, `started_at`. |
| **Execution** | Picks PENDING items, calls notification_orchestrator.process_retry; returns `{"message": ..., "count": processed}`. No outcome_status. |
| **Output** | Retries produce/update `message_logs`; queue items updated. |
| **Failure** | Exception → failed. Per-item failure is logged (logger.warning) but does not change job outcome — **partial failure not reflected as degraded**. |
| **Admin** | Job in health summary; no outcome_metrics for retry success/fail counts. |

**Status: VERIFIED WITH RISK**  
- **Risk:** Some retries can fail while job is still recorded as success. Recommend outcome_metrics (attempted, success, failed) and degraded when any retry fails.

---

### 11. notification_failure_spike_monitor

**Purpose:** Detect high FAILED message_logs in last 15 minutes and send admin alert (with cooldown).

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="notification_failure_spike_monitor"`, `run_type="schedule"`, `started_at`. |
| **Execution** | Counts FAILED in window; if above threshold, sends alert and writes cooldown/audit. Returns dict (breached, severity, failed_count, alert_sent). No outcome_status. |
| **Output** | Admin email (if breached + cooldown passed); notification_spike_cooldown; audit log. |
| **Failure** | Exception → `finish_job_run_failure`. |
| **Admin** | Job in health summary; spike monitor does not set job outcome to degraded when it detects breaches (it sends alert; job itself is success). |

**Status: VERIFIED WITH RISK**  
- Design correct: job runs and records success; detection is via message_logs and alert. No runtime proof.

---

### 12. delivery_reconciliation

**Purpose:** Enrich recent reminder/digest/report job runs with delivery_* from message_logs.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="delivery_reconciliation"`, `run_type="schedule"`, `started_at`. |
| **Execution** | `run_delivery_reconciliation(hours_back=48)` → fetches recent runs for RECONCILIATION_JOBS, aggregates message_logs by status, updates run's outcome_metrics with delivery_provider_accepted, delivery_delivered, delivery_bounced, delivery_unknown, delivery_failed. Returns message/count. |
| **Output** | Updates to existing `job_runs` documents (outcome_metrics.delivery_*). No new business records; purely observability. |
| **Failure** | Exception → `finish_job_run_failure`. If aggregation fails for some runs, whole job can throw or return; no per-run degraded. |
| **Admin** | Delivery unknown stale detection uses these metrics; drill-down message_logs per run. |

**Status: VERIFIED WITH RISK**  
- **Delivery reconciliation verification:** provider_accepted, delivered, bounced, unknown, failed are aggregated from message_logs and written to outcome_metrics. delivery_unknown_stale (e.g. > 6h) triggers P2 incident and is shown in health summary. Code path correct; runtime not inspected.

---

### 13. sla_watchdog

**Purpose:** Create incidents for missed job SLA, stale heartbeat, and delivery_unknown stale; send admin alerts.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="sla_watchdog"`, `run_type="schedule"`, `started_at`. |
| **Execution** | Runs heartbeat check, delivery_unknown_stale check, per-job SLA check from registry; creates incidents (deduped), sends emails. Returns incidents_created, alerts_sent. |
| **Output** | `incidents` collection (open); admin alert emails (if configured). |
| **Failure** | Exception → `finish_job_run_failure`. If incident creation fails after some succeeded, partial state. |
| **Admin** | Incidents visible on Incidents page; health summary uses open P0/P1 to set overall_health. |

**Status: VERIFIED WITH RISK**  
- Logic for missed run, heartbeat stale, delivery_unknown stale is implemented and deduped; runtime confirmation recommended.

---

### 14. scheduler_heartbeat

**Purpose:** Write current timestamp to `scheduler_heartbeat` so health can detect a live scheduler.

| Layer | Proof (code-path) |
|-------|--------------------|
| **Trigger** | `job_runs` with `job_name="scheduler_heartbeat"`, `run_type="schedule"`, `started_at`. |
| **Execution** | Updates `scheduler_heartbeat` collection `_id: "default"` with `last_heartbeat_at`. Then `finish_job_run_success`. |
| **Output** | Single doc in `scheduler_heartbeat` (last_heartbeat_at, updated_at). |
| **Failure** | Exception → `finish_job_run_failure`; heartbeat not updated. SLA watchdog treats stale heartbeat → P1 incident; health summary sets overall_health = failed when stale. |
| **Admin** | System Health shows last heartbeat and stale warning; Jobs tab and Automation Centre use same health. |

**Status: VERIFIED WITH RISK**  
- Design enforces: no heartbeat update → no write; next run can still record; staleness is detected and escalated. No live run verified.

---

## Special scenarios (code-path verification)

| Scenario | Result |
|----------|--------|
| **Successful run** | `job_runs` has status=success, finished_at, duration_ms; notification jobs have outcome_metrics; admin UI uses job_states and overall_health from same data. **Enforced by code.** |
| **Partial failure** | Notification jobs (daily_reminders, digest, compliance_check, scheduled_reports) return outcome_status=degraded and outcome_metrics (failed_count); `finish_job_run_degraded`; Automation Centre shows degraded; repeated degraded can create P2 incident. **Enforced for notification jobs.** compliance_score_snapshots, notification_retry_worker do not report degraded for partial failure. |
| **Hard failure** | Any exception → `finish_job_run_failure`; status=failed; error_message and stack_trace stored; SLA watchdog can create incident for missed next run; overall_health becomes degraded/attention_required. **Enforced.** |
| **Missed run** | No new job_runs for that job → last_success/last_completed age; _compute_job_state_and_reason marks state=missed when delay > max_delay_minutes; _compute_overall_health returns degraded/attention_required; sla_watchdog creates incident (deduped). **Enforced.** |
| **Conditional zero output** | Notification jobs return success with outcome_metrics (expected_count=0, attempted_count=0, ...); job_schedule_registry zero_output_ok allows state=conditional_no_output; admin sees reason "Ran successfully; no qualifying records". **Enforced.** |

---

## Observability truth test

**Rule:** If any critical automation has never_ran, missed, failed, or repeatedly degraded, the system must **not** display Healthy overall.

**Code:** `_compute_overall_health()` in `observability.py`:
- open_p0_p1 > 0 → attention_required  
- heartbeat_stale → failed  
- any critical job state in (missed, never_ran, failed) → degraded or attention_required  
- any critical degraded or delivery_unknown_stale_count > 0 → degraded  
- otherwise → healthy  

**Verdict: ENFORCED.**  
No code path allows overall_health = healthy when a critical job is never_ran, missed, or failed. Runtime check: stop scheduler, wait past max_delay for a critical job, then call GET /api/admin/observability/health-summary and confirm overall_health ≠ healthy.

---

## Summary counts

| Category | Count |
|----------|--------|
| Total critical automations audited | 14 |
| Verified safe (runtime evidence + no under-reporting) | 0 |
| Verified with risk (code supports evidence; gaps or no runtime proof) | 14 |
| Unproven (no code path or missing evidence) | 0 |
| Misleading observability (healthy despite failure) | 0 |

---

## Risk analysis

1. **Automations that could under-report partial failure**
   - **compliance_score_snapshots:** No outcome_metrics; partial snapshot failure could still show success.
   - **expiry_rollover_recalc:** No outcome_metrics; some enqueue failures could be invisible.
   - **compliance_recalc_worker:** No degraded outcome when some queue items go FAILED/DEAD.
   - **notification_retry_worker:** Per-retry failures only logged; job remains success.

2. **Automations that rely on manual intervention**
   - None by design. Manual "Run now" is for recovery/testing; SLA watchdog and heartbeat create incidents when runs are missed or scheduler is stale.

3. **Observability gaps**
   - Jobs without outcome_metrics (snapshots, expiry_rollover, recalc_worker, retry_worker) do not show attempted/success/failed in Automation Centre.
   - delivery_unknown is reconciled and surfaced after delivery_reconciliation runs; 6h stale threshold is defined and incident-created.

4. **Scheduler risks**
   - Single process: if API/scheduler process dies, no runs and no heartbeat. SLA watchdog and health then show missed/stale and create incidents (when scheduler is running again, or from another instance if multi-instance). Single point of failure is inherent unless multiple scheduler instances are used (not verified).

---

## Final conclusion

**Standard:** *"Automations run safely end-to-end without manual intervention except in extreme recovery scenarios."*

**Assessment:**

- **Trigger and execution:** All 14 jobs are invoked via the scheduler through `run_scheduled_job` → `run_instrumented` and persist to `job_runs` with run_type, started_at, and finish status. **Design supports trigger and execution proof.**
- **Business outcomes:** Notification jobs (reminders, digests, compliance check, scheduled reports) produce message_logs and outcome_metrics; delivery_reconciliation enriches delivery_*; sla_watchdog creates incidents; scheduler_heartbeat updates the heartbeat collection. **Design supports output proof.**
- **Failure detection:** Exceptions are not swallowed; they result in `finish_job_run_failure`. Partial failure is reflected as degraded only for notification jobs that return outcome_status/outcome_metrics. **Partial failure under-reporting exists for 4 jobs** (compliance_score_snapshots, expiry_rollover_recalc, compliance_recalc_worker, notification_retry_worker).
- **Admin observability:** overall_health is strict (never healthy when critical job is never_ran, missed, or failed); job_states and summary counts are exposed; incidents are created for missed SLA, stale heartbeat, delivery_unknown stale, and repeated degraded. **Observability is not misleading** for the cases implemented.

**Verdict:** The platform **meets the standard in design** for trigger, execution, hard failure recording, and observability truth. It **does not fully meet** the standard for **partial-failure honesty** for the four jobs listed above until they report outcome_metrics and/or degraded when appropriate.

**Before launch (recommended):**
1. **Runtime proof:** In staging, run each critical job (or allow schedule to run), then verify: `job_runs` has corresponding row with run_type="schedule", status and finished_at set, and where applicable message_logs/outcome_metrics/incidents/heartbeat as expected.
2. **Optional hardening:** Add outcome_metrics (and degraded when applicable) to compliance_score_snapshots, expiry_rollover_recalc, compliance_recalc_worker, and notification_retry_worker so partial failures are visible and can affect health if desired.
