# Enterprise Observability Task — Codebase Audit

This document checks the codebase against the **Enterprise Observability** task (job monitoring, incident management, system health dashboards, score ledger, structured logging, optional Sentry/OTel). It identifies what is implemented, what is missing, and **conflicts or overlap** with existing behaviour. No code is changed here; recommendations are given for the safest, non-duplicative approach.

---

## 1. Summary: Implemented vs Missing

| Goal | Status | Notes |
|------|--------|--------|
| 1) Every automation/job execution persisted in DB (job_runs) | **Missing** | No `job_runs` collection; jobs run via `job_runner` + scheduler but no per-run record (started_at, finished_at, status, duration_ms, error_code, etc.). |
| 2) Watchdog detects missed SLAs → create Incident | **Partial** | `compliance_sla_monitor` + `notification_failure_spike_monitor` exist but monitor **queue/email health**, not “last successful run” of expiry_scan / reminder_send / monthly_digest. No generic **job_runs**-based SLA checker. No **incidents** collection. |
| 3) Incidents in admin UI with ack/resolve workflow | **Missing** | No `incidents` collection, no incident CRUD or ack/resolve endpoints, no Incidents admin page. |
| 4) Admin alerts: dashboard banner + Notifications list + Email | **Partial** | Email: `ADMIN_ALERT_EMAILS` / `OPS_ALERT_EMAIL` used for provisioning failed, Stripe webhook failure, notification spike, compliance SLA. In-app: `in_app_notifications` + admin notifications API (order-related + preferences). **No** incident-driven notifications or P0/P1 banner. |
| 5) System Health admin page + Automation Control Centre | **Partial** | `GET /admin/jobs/status` exists (heuristic from audit_logs/digest_logs + scheduler next_run). **No** “System Health” overview page (OK/Degraded/Incident tiles). **No** “Automation Control Centre” (job table with last run, last success, fail count 24h, Run Now, View Logs). Notification Health page exists at `/admin/notification-health`. |
| 6) Score Change Ledger with timestamps and export | **Done** | **score_ledger_events** + **score_ledger_service** (log_score_change from recalculate_and_persist), GET /api/client/ledger, GET /api/client/ledger/export.csv, GET /api/admin/ledger, GET /api/admin/ledger/export.csv. Client: “Audit & Change History” page with **Score History** tab (filters, table, row expand, Export CSV) and **Activity Log** tab (audit timeline). |
| 7) Structured logging with correlation IDs across API + jobs | **Partial** | **Correlation IDs** used in: score_ledger, compliance_recalc_queue, job_runner (recalc worker), documents, properties, OTP, assistant. **No** global middleware that sets `X-Correlation-Id` on every API response or injects correlation_id into every request. **No** structured (JSON) logger with timestamp, level, message, correlation_id, route, user_id, client_id. |
| 8) Optional Sentry/OpenTelemetry behind env flags | **Missing** | No Sentry or OpenTelemetry integration in codebase. |

---

## 2. Existing Pieces (Do Not Duplicate)

### 2.1 Score / Ledger (Goal 6 — Done)

- **score_events** (collection): client-level “What Changed” + trend; written from routes (document/requirement/property events) and from job_runner (SCORE_RECALCULATED). Fields: client_id, event_type, score_before/after, delta, property_id, requirement_id, document_id, actor_*, created_at.
- **score_ledger_events** (collection): enterprise “statement of account”; one row per recalc with before/after, delta, drivers_before/after/delta, trigger_type/label, rule_version, correlation_id. Written **only** from `recalculate_and_persist` via `log_score_change`.
- **APIs**: GET /api/client/ledger (paginated), GET /api/client/ledger/export.csv, GET /api/admin/ledger?client_id=..., GET /api/admin/ledger/export.csv?client_id=...
- **Frontend**: Client “Audit & Change History” (/audit-log): tabs **Score History** (ledger table + Export CSV) and **Activity Log** (portfolio audit timeline).

**Task “score_events” export under observability:** The task’s “GET /admin/observability/score-events” and “score-events/export” can map to the **existing ledger** (score_ledger_events) to avoid a second “score events” API. Recommend: add **GET /admin/observability/score-events** (and export) as **aliases** that call the same list_ledger/list_ledger_export with client_id required, or document that admin ledger endpoints are the observability score-events API.

### 2.2 Job Execution (Current Behaviour)

- **job_runner.py**: One async function per job (e.g. run_daily_reminders, run_monthly_digests, run_compliance_recalc_worker). **JOB_RUNNERS** dict maps job_id → function. Scheduler (server.py) runs them on cron/interval; admin can trigger via POST /admin/jobs/run (body: `{ "job": "<id>" }`) or legacy POST /admin/jobs/trigger/{job_type}. **No** persistence of each run (no job_runs table).
- **GET /admin/jobs/status**: Returns heuristic “last run” from audit_logs (REMINDER_SENT) and digest_logs (monthly digest), plus scheduler.get_jobs() (next_run_time). **No** job_runs-based last success time or failure count.

### 2.3 SLA / Alerts (Existing, Domain-Specific)

- **compliance_sla_monitor**: Detects stuck PENDING/RUNNING recalc jobs, repeated failures, DEAD jobs, property pending too long. Writes to **compliance_sla_alerts**; can send email via OPS_ALERT_EMAIL (COMPLIANCE_SLA_ALERT template). **Not** a generic “last successful run of job X” checker.
- **notification_failure_spike_monitor**: Checks message_logs for send failure spike; sends admin email (OPS_ALERT_NOTIFICATION_SPIKE). **Not** job_runs-based.
- **compliance_sla_alerts** (collection): per-property alert type, severity, last_detected_at, etc. **Not** the same as task’s **incidents** (which are system-wide, ack/resolve workflow, severity P0/P1/P2).

### 2.4 Admin Notifications and Email

- **in_app_notifications**: Used by order_service and order_notification_service; admin_notifications routes (list, unread-count, mark read). Tied to **user_id** (admin). Task’s “notifications” for incidents could extend this (add type/severity/title/body and incident_id) or add a separate **incident_notifications** or **admin_alerts** collection.
- **ADMIN_ALERT_EMAILS** / **OPS_ALERT_EMAIL**: Already used for provisioning failed, Stripe webhook failure, notification spike, compliance SLA. Reuse for incident alerts (e.g. “P0: expiry_scan has not succeeded in 26h”).

### 2.5 Correlation ID Usage

- **Present** in: compliance_recalc_queue (correlation_id in payload), job_runner (passes to recalculate_and_persist context), score_ledger (idempotency), documents/routes (DOC_UPLOADED, etc.), properties, OTP routes (`_correlation_id(request)`), assistant (per-request correlation_id). **Not** present as global middleware: no single place that (1) reads X-Correlation-Id from request or generates one, (2) sets X-Correlation-Id on response, (3) makes it available to all routes and to structured logs.

---

## 3. Conflicts and Overlap

### 3.1 score_events vs score_ledger_events (Task B vs Goal 6)

- **Task** describes a **score_events** collection with: client_id, property_id (optional), old_score, new_score, delta, driver_type, driver_ref, actor, occurred_at, explanation, metadata.
- **Current**: **score_events** exists with a **different** shape (event_type, score_before/after, delta, actor_role, document_id, requirement_id, etc.) and is used for “What Changed” and 90-day trend. **score_ledger_events** is the richer “statement of account” with drivers, trigger_type, rule_version, etc.
- **Conflict**: Naming overlap. Task’s “score_events” export under observability should not create a second schema; it should point at the **ledger** (score_ledger_events) for admin “score change history” and export. Keep **score_events** as-is for client timeline/changes; use **score_ledger_events** for enterprise ledger and admin observability export.

**Recommendation:** Implement **GET /admin/observability/score-events** (and export) to query **score_ledger_events** (with client_id required), not a new collection. Document in API that “score-events” in observability context means the score ledger.

### 3.2 Incidents vs compliance_sla_alerts

- **compliance_sla_alerts**: Property-scoped, alert_type (PENDING_STUCK, RUNNING_STUCK, etc.), cooldown, email. No ack/resolve workflow, no “incident” concept.
- **Task incidents**: System-wide, severity P0/P1/P2, status open/ack/resolved, acknowledged_by/resolved_by, related_job_run_id, dashboard banner, notifications list.
- **No conflict**: Add **incidents** as a **new** collection and workflow. When the **job SLA watchdog** (new) detects “last success of expiry_scan > 26h”, create an **incident** (and optionally still use compliance_sla_alerts for recalc-specific details if desired). Do not replace compliance_sla_alerts; they serve different scope (recalc queue vs global job health).

### 3.3 job_runs vs audit_logs / digest_logs

- **Today**: Manual job runs are logged to **audit_logs** (action REMINDER_SENT, ADMIN_ACTION with metadata job_id). Digest runs may write **digest_logs**. No unified “job_runs” record with started_at, finished_at, duration_ms, error_code, status.
- **Task**: **job_runs** as the single source of truth for “when did job X last succeed/fail”.
- **Recommendation:** Add **job_runs** and instrument each job (start_job_run / finish_job_run_success | finish_job_run_failure). Keep existing audit_log entries for manual triggers for audit trail; **job_runs** is for SLA and “last run” dashboards. Do not try to infer job_runs from audit_logs.

---

## 4. What to Implement (Recommended Order)

### Phase 1: Foundation (no breaking changes)

1. **job_runs collection**  
   - Schema: job_name, run_type (schedule/manual/webhook), status (running/success/failed/timeout/skipped), started_at, finished_at, duration_ms, error_code, error_message, stack_trace (optional), correlation_id, triggered_by, affected_clients_count, metadata, created_at.  
   - Indexes: job_name + created_at desc; status + created_at desc.

2. **Job instrumentation helper**  
   - `start_job_run(job_name, run_type, metadata) -> job_run_id`  
   - `finish_job_run_success(job_run_id, affected_counts, metadata)`  
   - `finish_job_run_failure(job_run_id, error_code, error_message, stack_trace)`  
   - Wrap each entry in `job_runner.py` (and scheduler-invoked paths) with this helper so every run is recorded.

3. **Correlation ID middleware**  
   - Middleware: read X-Correlation-Id from request or generate UUID; set X-Correlation-Id on response; store in request.state (and optionally in contextvar for async use).  
   - No change to existing correlation_id usage in recalc/OTP/assistant; add global middleware so **all** API requests get a correlation_id.

4. **Structured logger (JSON)**  
   - Optional: add a structured logging handler (e.g. JSON with timestamp, level, message, correlation_id, route, user_id, client_id). Can be behind env (e.g. LOG_FORMAT=json). Default remains current format for local dev.

### Phase 2: Incidents and Watchdog

5. **incidents collection**  
   - Schema: severity (P0/P1/P2), title, description, source, status (open/acknowledged/resolved), created_at, updated_at, acknowledged_by, acknowledged_at, resolved_by, resolved_at, related_job_run_id, metadata.  
   - Indexes: status + created_at; severity + status.

6. **SLA watchdog job**  
   - New scheduled job (e.g. every 10 minutes). Config: list of { job_name, expected_frequency_minutes, max_delay_minutes, severity, description }.  
   - For each: query job_runs for last successful run (status=success); if now - last_success > max_delay_minutes, create **incident** (if no open incident for same job_name/source) and create admin notification + send email (ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL).  
   - Do not remove or replace compliance_recalc_sla_monitor or notification_failure_spike_monitor; run in parallel.

7. **Admin notifications for incidents**  
   - When creating an incident, insert into **in_app_notifications** (or a dedicated admin_alerts collection) with type=incident, severity, title, body, incident_id, so admins see it in existing Notifications list.  
   - Optional: dedicated “incident_notifications” collection and endpoint if you want to keep order vs incident notifications separate.

8. **Observability API**  
   - GET /admin/observability/job-runs (filters: job_name, status, from/to, limit).  
   - GET /admin/observability/incidents (filters: status, severity).  
   - POST /admin/observability/incidents/{id}/ack (body: optional note).  
   - POST /admin/observability/incidents/{id}/resolve (body: optional note).  
   - GET /admin/observability/score-events?client_id=... (and export): delegate to existing ledger (score_ledger_events) so no duplication.  
   - All behind admin RBAC; rate-limit export endpoints; do not expose stack_trace to non-admin.

### Phase 3: Admin UI

9. **System Health page**  
   - Status badge: OK / Degraded / Incident (e.g. from open P0/P1 incidents).  
   - Tiles: last success time for key jobs (from job_runs): expiry_scan, reminder_send, monthly_digest (map to existing job_ids e.g. daily_reminders, monthly_digest, compliance_score_snapshots or as configured in watchdog).  
   - Open incidents list; latest failures (job_runs with status=failed, limit 10).

10. **Automation Control Centre page**  
    - Table: job name, last run, last success, fail count (24h), next schedule (from scheduler), actions: Run Now, View Logs (link to job_runs filtered by job_name).

11. **Incidents page**  
    - Table with status filters, severity chips, Acknowledge / Resolve buttons, link to related job_run.

12. **Admin banner and nav**  
    - Red dot (or badge) in admin nav when any P0/P1 incident is open.  
    - Global banner when P0 open: “System degraded: [title]. View incident.”

### Phase 4: Optional Integrations

13. **Sentry**  
    - Behind env (e.g. SENTRY_DSN). Init in server startup; capture exceptions and optionally set correlation_id as tag. Core system must work with SENTRY_DSN unset.

14. **OpenTelemetry**  
    - Behind env (e.g. OTEL_EXPORTER_OTLP_ENDPOINT). Trace FastAPI requests and job runs. Core system must work without OTLP.

---

## 5. Files to Touch (Implementation Checklist)

### Backend

- **database.py**: Add indexes for job_runs, incidents. (in_app_notifications already used; add index if incident notifications stored there.)
- **New**: `services/job_run_service.py` (or `utils/job_run.py`): start_job_run, finish_job_run_success, finish_job_run_failure.
- **job_runner.py**: Wrap each run_* with job_run start/finish (and pass correlation_id where available).
- **New**: `services/incident_service.py`: create_incident, list_incidents, ack_incident, resolve_incident.
- **New**: `services/sla_watchdog.py` (or job in job_runner): config-driven “last success” check, create incident + notification + email.
- **server.py**: Register SLA watchdog job (interval 10 min); add correlation middleware if not in middleware.py.
- **middleware.py**: Add correlation_id middleware (request + response).
- **New**: `routes/observability.py` (or under admin): job-runs, incidents, score-events (proxy to ledger), export CSV for score-events (proxy to ledger export).
- **admin_notifications** or order_service: When incident created, insert admin notification (or use new collection).
- **Structured logging**: Optional JSON formatter and env flag (e.g. in server.py or a logging config module).
- **Sentry/OTel**: Optional init in server.py behind env.

### Frontend

- **New**: Admin “System Health” page (e.g. /admin/system-health) with status, job tiles, open incidents, recent failures.
- **New**: Admin “Automation Control Centre” (e.g. /admin/automation) with job table, Run Now, View Logs.
- **New**: Admin “Incidents” page (e.g. /admin/incidents) with filters, ack/resolve.
- **UnifiedAdminLayout**: Add nav items; red dot when P0/P1 open; global banner when P0 open.
- **API**: Add client methods for GET observability/job-runs, incidents, score-events, ack, resolve, and for system health summary if a single endpoint is added.

---

## 6. Env Vars (New / Documented)

- **ADMIN_ALERT_EMAIL** / **ADMIN_ALERT_EMAILS**: Already used; reuse for incident alerts.
- **Optional**: SENTRY_DSN, OTEL_EXPORTER_OTLP_ENDPOINT, LOG_FORMAT=json.
- **Optional**: SLA watchdog config (e.g. JSON or env list) for job_name → expected_frequency_minutes, max_delay_minutes, severity.

---

## 7. Quality

- **Unit tests**: SLA watchdog logic (last success threshold, dedup by open incident per job). Incident ack/resolve.
- **Integration test**: Simulate “no successful run of job X in last 27h” (mock job_runs), run watchdog, assert incident created and (if possible) notification/email attempted.

---

## 8. Safe Options Summary

| Area | Recommendation |
|------|----------------|
| **Score ledger / score-events** | Keep score_ledger_events and client/admin ledger APIs as-is. Expose them as “observability score-events” for admin (same data, no second collection). |
| **score_events (existing)** | Keep for client “What Changed” and timeline; do not replace with task’s score_events schema. |
| **job_runs** | Add new collection and instrumentation; do not try to derive from audit_logs. |
| **Incidents** | New collection and workflow; keep compliance_sla_alerts for recalc-specific alerts. |
| **Admin notifications** | Extend in_app_notifications (or add incident_notifications) for incident alerts so existing Notification Bell and list show them. |
| **Correlation ID** | Add global middleware; keep existing per-route/correlation_id usage where it exists. |
| **GET /admin/jobs/status** | Can be updated to use job_runs once available (last success per job from job_runs instead of audit_logs/digest_logs); keep same response shape for compatibility or version the API. |

This audit is the single reference for implementing Enterprise Observability without duplicating or conflicting with the existing score ledger, score_events, compliance SLA alerts, and admin notifications. Implement in phases; do not implement blindly.
