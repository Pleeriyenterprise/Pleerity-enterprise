# Automation Framework Audit

Last updated: 2026-02-20  
Scope: scheduler registration, execution instrumentation, observability truthfulness, manual recovery, and incident behavior.

## Audit Method

This audit is evidence-based from code paths and read-only diagnostics.

Primary sources:

- `backend/server.py` (scheduler init and `scheduler.add_job` registrations)
- `backend/job_runner.py` (`run_scheduled_job` -> `run_instrumented` -> `job_runs`)
- `backend/services/job_schedule_registry.py` (health registry)
- `backend/services/startup_reconciliation.py` (startup catch-up / overdue incident handling)
- `backend/routes/admin.py` (legacy and current job status / manual run endpoints)
- `backend/routes/observability.py` (health summary, incidents, job runs)
- `backend/routes/admin_billing.py` (billing-specific manual job path)

New read-only diagnostics endpoint:

- `GET /api/admin/observability/framework-audit`

This endpoint returns per-job inventory with:

- `job_name`
- `purpose`
- `registered`
- `trigger_type`
- `trigger_expression`
- `next_run_time`
- `included_in_health_summary`
- `included_in_automation_centre`
- `can_be_run_manually`
- `total_runs`
- `last_started_at`
- `last_finished_at`
- `last_status`
- `current_incident_state`
- `startup_reconciliation_included`
- `diagnostic_category`

## Full Job Inventory (Code-Level)

### Registered in scheduler (`server.py`)

- `daily_reminders`
- `pending_verification_digest`
- `monthly_digest`
- `compliance_check_morning`
- `compliance_check_evening`
- `scheduled_reports`
- `compliance_score_snapshots`
- `expiry_rollover_recalc`
- `contractor_performance_recalc`
- `compliance_recalc_worker`
- `compliance_recalc_sla_monitor`
- `notification_failure_spike_monitor`
- `scheduler_heartbeat`
- `delivery_reconciliation`
- `sla_watchdog`
- `notification_retry_worker`
- `order_delivery_processing`
- `sla_monitoring`
- `stuck_order_detection`
- `queued_order_processing`
- `generation_auto_retry_processing`
- `abandoned_intake_detection`
- `lead_followup_processing`
- `pending_payment_lifecycle`
- `lead_sla_check`
- `checklist_nurture_processing`
- `risk_lead_nurture_processing`
- `onboarding_sequence_processing`
- `activation_reminder_processing`
- `predictive_insights_job`
- `risk_signals_job`
- `work_order_sla_breach_job`

### In health registry (`job_schedule_registry.py`)

- `daily_reminders`
- `pending_verification_digest`
- `monthly_digest`
- `compliance_check_morning`
- `compliance_check_evening`
- `scheduled_reports`
- `compliance_score_snapshots`
- `expiry_rollover_recalc`
- `compliance_recalc_worker`
- `notification_retry_worker`
- `notification_failure_spike_monitor`
- `sla_watchdog`
- `scheduler_heartbeat`
- `delivery_reconciliation`
- `contractor_performance_recalc` (non-critical)

### Manually runnable via canonical runner (`job_runner.JOB_RUNNERS`)

Includes all scheduler jobs listed above.

### Manual-only outlier

- `renewal_reminders` (billing route calls service directly; not scheduler-registered and not in `JOB_RUNNERS`)

## Healthy Architecture (Reference Path)

Expected standard path:

1. APScheduler entrypoint: `job_runner:run_scheduled_job`
2. Wrapper: `run_instrumented(job_id, run_type, triggered_by)`
3. Persistence:
   - `start_job_run(...)`
   - `finish_job_run_success(...)` / `finish_job_run_degraded(...)` / `finish_job_run_failure(...)`
4. Incident auto-recovery hook after success/degraded.

This is already implemented and should remain the baseline.

## Exact Differences and Gaps

1. **Registry vs scheduler mismatch**
   - Some scheduler jobs are not in health registry (e.g., `pending_payment_lifecycle`, `predictive_insights_job`, `risk_signals_job`, `work_order_sla_breach_job`, etc.).
   - Result: not all scheduled jobs receive first-class health-state semantics.

2. **Multiple status surfaces**
   - `/api/admin/jobs/status` (legacy mixed status)
   - `/api/admin/observability/health-summary` (newer strict health semantics)
   - `/api/admin/billing/jobs/status` (billing-specific semantics)
   - Result: admin truth can diverge by endpoint.

3. **Multiple manual trigger paths**
   - `/api/admin/jobs/run`
   - `/api/admin/jobs/trigger/{job_type}` (legacy)
   - `/api/admin/observability/incidents/{incident_id}/run-job`
   - Billing-specific run path outside canonical runner for renewal reminders.

4. **Startup reconciliation coverage is partial by design**
   - Covers selected infrequent critical jobs.
   - High-frequency jobs rely on their next scheduled run and watchdog.
   - Without explicit reasoning in UI, this can look like “never ran” ambiguity after restart.

5. **In-process scheduler visibility limitation**
   - `next_run_time` depends on process-local scheduler access.
   - In multi-instance or mismatch scenarios, API may see no scheduler jobs while runs exist in DB.

## Never-Ran / Missing next_run / Missing last_run Categories

Use `diagnostic_category` from `GET /api/admin/observability/framework-audit`:

- `registered_not_yet_due`
- `registered_overdue_never_ran`
- `startup_reconciliation_issue`
- `triggered_but_uninstrumented`
- `conditionally_no_output`
- `UI_state_bug`
- `database/environment_mismatch`
- `none`

These categories are computed from scheduler runtime presence, job_runs history, outcome metrics, and startup reconciliation membership.

## Framework Standardizations Applied (Phase A)

Implemented in this pass:

1. Added a single read-only reconciliation endpoint:
   - `GET /api/admin/observability/framework-audit`
2. Standardized inventory fields required for enterprise audit reporting.
3. Added explicit reconciliation sections:
   - `registry_only`
   - `scheduler_only`
   - `runner_only`
4. Added per-job diagnostic category for root-cause triage.

## Framework Standardizations Applied (Phase B)

Implemented in this pass:

1. Automation Centre switched to observability-first truth source:
   - uses `GET /api/admin/observability/framework-audit` for scheduler registration, next run, and diagnostic category.
2. Legacy endpoints retained but explicitly marked deprecated:
   - `GET /api/admin/jobs/status` now returns `deprecated` + replacement endpoints.
   - `POST /api/admin/jobs/trigger/{job_type}` now returns `deprecated` + canonical replacement.
3. `framework-audit` inventory now includes `last_run_id` to support deterministic drill-down from UI.

Still intentionally deferred:

- Expanding health registry coverage to every scheduled job (behavioral policy change).
- Removing legacy endpoints (compatibility risk; requires coordinated frontend/backoffice cutover).
- Converging billing-specific manual jobs into canonical scheduler runner contract.

## Framework Standardizations Applied (Phase C)

Implemented in this pass:

1. Added explicit visibility reason codes for missing/ambiguous next-run and last-run states in observability payloads:
   - `next_run_reason_code`
   - `last_run_reason_code`
   - `scheduler_registered`
2. Added scheduler runtime availability metadata in health summary:
   - `scheduler_runtime.available`
   - `scheduler_runtime.registered_jobs_count`
3. Extended framework-audit inventory with explicit reason fields:
   - `registration_reason`
   - `next_run_reason`
   - `last_run_reason`
4. Updated admin UIs to surface explicit reasons instead of ambiguous blanks:
   - Automation Centre reason fallback now uses visibility reason fields.
   - System Health shows scheduler-runtime warning and per-job no-run reason text.

## Framework Standardizations Applied (Phase D)

Implemented in this pass:

1. Removed the remaining first-party frontend dependency on legacy status endpoint:
   - Admin Dashboard job monitor now reads `GET /api/admin/observability/framework-audit` + `GET /api/admin/observability/health-summary`.
2. Froze legacy endpoints behind an explicit compatibility window contract:
   - `GET /api/admin/jobs/status` and `POST /api/admin/jobs/trigger/{job_type}` now return:
     - `deprecated: true`
     - `compatibility_window_ends_at: "2026-06-30T00:00:00Z"`
3. Added server-side warning logs on legacy endpoint usage for cutover tracking.

## Acceptance Checklist (Per Job)

Checklist fields:

- registered
- visible in automation centre
- visible in system health
- next run recorded
- last run recorded after execution
- truthful outcome classification
- manual run supported or intentionally excluded
- incident behavior correct
- recovery behavior correct

Execution:

- Use `GET /api/admin/observability/framework-audit` for inventory and registration/manual/incident/run-history coverage.
- Use `GET /api/admin/observability/health-summary` for state classification and summary counters.
- Use `GET /api/admin/observability/job-runs` and incidents endpoints for runtime evidence.

## Jobs Intentionally Conditional or Future-Due

Expected conditional-no-output jobs:

- `daily_reminders`
- `pending_verification_digest`
- `monthly_digest`
- `scheduled_reports`
- `notification_retry_worker`
- `delivery_reconciliation`
- `contractor_performance_recalc`

Expected future-due states may appear after restart:

- Any registered job with no historical run where `next_run_time` is still in the future (`registered_not_yet_due`).

## Remaining Risks

1. Endpoint-level truth split between legacy status APIs and observability APIs.
2. Health registry does not include all scheduler-registered jobs.
3. Billing reminder manual path is outside canonical scheduler/runner registration model.
4. Multi-instance scheduler visibility can create apparent mismatch unless deployment role ownership is explicit.

## Recommended Next Safe Step

1. Unify metadata authority across:
   - `job_schedule_registry`
   - `server.py` registrations
   - `job_runner.JOB_RUNNERS`
2. After compatibility-window expiry, remove legacy trigger/status endpoint variants and keep observability-first payloads only.
3. Move manual-only outlier jobs into canonical runner contract or explicitly mark as excluded with reason code.

