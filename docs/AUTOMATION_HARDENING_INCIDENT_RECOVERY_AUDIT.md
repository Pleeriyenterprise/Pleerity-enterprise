# Automation Hardening & Incident Recovery – Task vs Codebase Audit

## Goal

Audit the codebase against the task requirements for **final operational hardening**: incident auto-recovery, "Run job now" from incidents, incident–job linking, UI hints, production-readiness checklist, and backend recovery logic. Identify what is implemented, what is missing, and any conflicts. Propose the safest implementation path. **Do not implement blindly.**

---

## 1. Current Architecture Summary

| Component | Current implementation |
|-----------|------------------------|
| **Incident model** | `incidents` collection: status (open, acknowledged, resolved), severity, title, description, source, related_job_name, related_job_run_id, metadata, created_at, updated_at, acknowledged_by, acknowledged_at, resolved_by, resolved_at. Resolution note: `metadata.note_resolve`. No `resolution_notes` top-level; no `recovery_source`; no "recovered" status. |
| **Incident service** | `incident_service.py`: create_incident, list_incidents, get_incident, acknowledge_incident, resolve_incident. resolve_incident(incident_id, resolved_by, note) sets status=resolved, resolved_at, resolved_by, and optional metadata.note_resolve. |
| **SLA watchdog** | `sla_watchdog.py`: runs every 10 min. Creates incidents for: (1) heartbeat stale (source=heartbeat), (2) delivery_unknown stale (source=delivery_unknown), (3) per-job: "has not succeeded", "missed SLA", "last run degraded" (source=job_monitor, related_job_name, metadata with last_finished_at, degraded_run, max_delay_minutes). Does **not** close incidents when condition clears. |
| **Run job now** | **admin.py**: `POST /api/admin/jobs/run` with body `{ "job": "<job_id>" }`. Calls run_instrumented(job_id, "manual", triggered_by=user). Job ids from JOB_RUNNERS (e.g. daily_reminders, sla_watchdog). **Observability** routes do **not** expose "run job now"; incidents API is under `/api/admin/observability`. |
| **Job run completion** | `job_runner.run_instrumented`: after fn() returns, calls finish_job_run_success or finish_job_run_degraded/failure. **No** hook for incident recovery after success. |
| **Heartbeat** | `run_scheduler_heartbeat` job updates `scheduler_heartbeat` collection `last_heartbeat_at`. Staleness checked in sla_watchdog and observability. |
| **Delivery unknown** | RECONCILIATION_JOBS; stale = job_runs with finished_at older than DELIVERY_UNKNOWN_STALE_HOURS and outcome_metrics.delivery_unknown > 0. |
| **Observability API** | `/api/admin/observability`: GET job-runs, GET incidents, GET incident/{id}, POST incidents/{id}/ack, POST incidents/{id}/resolve. Health summary includes job_states, open_incidents_count, last_heartbeat_at, delivery_unknown_stale_runs. |
| **Frontend** | No incidents/observability UI found in this workspace (likely separate repo or different path). Task says "Do not redesign the existing admin UI" and "Add Run job now button" – backend must support the action; UI changes may be in another codebase. |
| **Scripts** | `scripts/verify_automation_runtime.py` exists (job_runs, scheduled_jobs, incidents, recommendations). No `verify_automation_recovery.py` or production-readiness checklist doc. |

---

## 2. Task Requirements vs Current State

### PART 1 — Incident lifecycle improvements

| Requirement | Status | Notes |
|-------------|--------|-------|
| Auto-resolve when related job later runs successfully | **Missing** | No recovery logic. Incidents stay open until manually resolved. |
| Update incident with resolved_at, resolution_notes, recovery_source | **Partial** | resolved_at, resolved_by exist. resolution_notes not a field (use metadata.note_resolve or add metadata.resolution_notes). recovery_source not present – add as metadata.recovery_source = "automatic_job_recovery". |
| Do not auto-resolve if condition still exists (heartbeat still stale, delivery_unknown still unresolved, degraded still has failed metrics) | **N/A** | Must be enforced in recovery logic. |
| Optional "recovered" status | **Recommendation** | Task: if it adds complexity, use resolved + recovery metadata. **Use resolved** with metadata.recovery_source and metadata.resolution_notes (or resolution_notes top-level for consistency). |

**Implementation approach:** Add `resolve_incident_auto_recovery(incident_id, resolution_note, recovery_source="automatic_job_recovery")` (or extend resolve_incident with an optional flag) that sets status=resolved, resolved_at, resolved_by=null or "system", and metadata.recovery_source + metadata.resolution_notes. Add a **recovery helper** that, given current system state, determines which open incidents can be auto-resolved (see Part 6).

---

### PART 2 — Run job now action

| Requirement | Status | Notes |
|-------------|--------|-------|
| "Run job now" button on Incidents page / Automation Control Centre | **Backend only** | No UI in this repo. Backend already has POST /api/admin/jobs/run with body `{ "job": "<job_id>" }`. |
| Only for incidents linked to a runnable background job | **N/A** | UI/API can check incident.source === job_monitor && incident.related_job_name && related_job_name in JOB_RUNNERS. |
| Confirmation and messaging (recovery/testing; routine runs automatic) | **N/A** | UI concern. |
| On success: refresh job state, incidents, health | **N/A** | UI concern. |
| If manual run succeeds and clears issue, incident should auto-resolve | **N/A** | Will be satisfied once Part 1 recovery runs after job success (e.g. from job_runner or next sla_watchdog pass). |

**Conflict:** Task says `POST /admin/jobs/run/{job_name}`. Current API is `POST /api/admin/jobs/run` with body `{ "job": "<job_id>" }`. Same semantics (job_id = job_name in this codebase). **Recommendation:** Keep existing endpoint. Optionally add `POST /api/admin/observability/incidents/{incident_id}/run-job` that (1) loads incident, (2) if source=job_monitor and related_job_name in JOB_RUNNERS, calls run_instrumented(related_job_name, "manual", …), (3) returns run result. This gives the UI a single "run job for this incident" endpoint without changing admin.py.

---

### PART 3 — Incident-to-job linking

| Requirement | Status | Notes |
|-------------|--------|-------|
| Metadata: related_job_name, source, severity, triggering_reason, created_from_run_id, degraded_run | **Partial** | related_job_name, source, severity already set. metadata has last_finished_at, degraded_run, max_delay_minutes. **Missing:** explicit triggering_reason (could derive from title/source or add at create), created_from_run_id (not set when creating incident). |

**Recommendation:** When creating incidents in sla_watchdog, add metadata.triggering_reason (e.g. "missed_sla", "degraded_run", "heartbeat_stale", "delivery_unknown_stale", "job_never_succeeded") and, when available, metadata.created_from_run_id (e.g. the run that was last checked and caused the incident – optional). Ensures consistent filtering and UI.

---

### PART 4 — Incident UI improvements

| Requirement | Status | Notes |
|-------------|--------|-------|
| Status line: last successful run, last failed/degraded, expected interval, issue still active or recovered | **Partial** | Observability health summary already has per-job last_success, last_failure, last_degraded, schedule. Incident detail API (GET incident/{id}) returns stored fields only – it does **not** currently enrich with "last run" or "recovery detected". |
| Hint "Recovery detected. This incident can be resolved automatically." | **Missing** | Requires backend to expose a computed flag or message. Add e.g. `recovery_detected: bool` or `recovery_hint: str` when GET incident shows an open incident whose condition is now cleared (same logic as auto-recovery check). |
| "Run job now" button beside Acknowledge/Resolve | **Missing** | Backend: expose runnable job for incident (related_job_name in JOB_RUNNERS). UI: add button (if frontend in another repo, document API). |
| Notes / Resolution notes support | **Done** | resolve_incident accepts note → metadata.note_resolve; acknowledge accepts note → metadata.note_ack. |

**Recommendation:** Add an optional **enrichment** in GET incident (or a small helper) that, for open/acknowledged incidents with source=job_monitor and related_job_name, computes "recovery_detected" (and optionally last_success, last_failure, expected_interval) from job_runs + registry. Same for heartbeat/delivery_unknown. This supports both the hint and the status line without redesigning the page.

---

### PART 5 — Production-readiness test support

| Requirement | Status | Notes |
|-------------|--------|-------|
| docs/AUTOMATION_PRODUCTION_READINESS_CHECKLIST.md with 5 verification tests | **Missing** | Create checklist: (1) scheduled execution, (2) manual recovery, (3) output proof, (4) incident honesty, (5) recovery. |
| backend/scripts/verify_automation_recovery.py | **Missing** | Create script: list open incidents, recent job_runs, detect incidents whose underlying condition is cleared, print which would auto-resolve. |

---

### PART 6 — Backend logic changes

| Requirement | Status | Notes |
|-------------|--------|-------|
| resolve_recovered_incidents_for_job(job_name, latest_run) | **Missing** | To add. Called when a job finishes successfully (and optionally from sla_watchdog for heartbeat/delivery_unknown). |
| When to run recovery | **Design** | (A) **After each job success** in job_runner: after finish_job_run_success, call resolve_recovered_incidents_for_job(job_id, run_info). Resolves job_monitor incidents for that job when the run proves the condition is cleared. (B) **In sla_watchdog** at start of run: before creating new incidents, run a "recovery pass" – for each open incident (or by source), check if condition is cleared; if so, resolve. (A) gives immediate recovery after "Run job now" or scheduled run. (B) catches heartbeat and delivery_unknown recovery (no "job finish" event for those) and reinforces job_monitor recovery. **Recommendation:** Do both: (A) in job_runner for job_monitor incidents tied to that job_name; (B) in sla_watchdog for heartbeat and delivery_unknown and optionally re-check job_monitor. |

**Recovery rules (conservative):**

- **job_monitor (missed SLA / has not succeeded):** Auto-resolve only if there exists a **success** or **degraded** run for that job_name with finished_at **after** the incident created_at (or after metadata.last_finished_at), and that run is within SLA (delay <= max_delay_minutes). So: latest run is success/degraded and within SLA ⇒ resolve.
- **job_monitor (degraded run):** Auto-resolve only when the **latest** run for that job is **success** (not degraded). So: if metadata.degraded_run and the most recent run for job_name has status=success ⇒ resolve.
- **heartbeat:** Auto-resolve only when heartbeat is **not** stale (last_heartbeat_at within HEARTBEAT_STALE_SECONDS). So: run same check as sla_watchdog; if not stale ⇒ resolve open heartbeat incident.
- **delivery_unknown:** Auto-resolve only when there are **no** reconciliation job runs older than DELIVERY_UNKNOWN_STALE_HOURS with delivery_unknown > 0. So: re-run the same count query; if 0 ⇒ resolve open delivery_unknown incident.

---

### PART 7 — Safety rules

| Requirement | Status | Notes |
|-------------|--------|-------|
| Do not auto-resolve incorrectly; be conservative | **N/A** | Enforce in recovery helper: only resolve when the **same** condition that created the incident is verified cleared. |
| Do not break scheduler, incident creation, job run instrumentation, observability endpoints | **N/A** | Additive changes only: new helper, call from job_runner after success and from sla_watchdog; optional new endpoint for "run job for incident". |

---

### PART 8 — Deliverables (to return)

Will be satisfied by implementation: files modified, where auto-recovery was added, where "Run job now" was added, how linking is handled, how auto-resolution decides issue is cleared, checklist file, incidents that still require manual resolution.

---

## 3. Conflicts and Recommended Resolution

| # | Conflict / choice | Recommendation |
|---|-------------------|----------------|
| 1 | Task "resolved = true" | Keep **status = "resolved"**; add metadata.recovery_source and metadata.resolution_notes (or top-level resolution_notes) for auto-resolutions. |
| 2 | "recovered" status | **Do not** add a new status. Use **resolved** with metadata.recovery_source = "automatic_job_recovery" and metadata.resolution_notes. |
| 3 | POST /admin/jobs/run/{job_name} | Keep **POST /api/admin/jobs/run** with body `{ "job": "<id>" }`. Optionally add **POST /api/admin/observability/incidents/{id}/run-job** that resolves related_job_name and calls run_instrumented (so UI has one incident-scoped action). |
| 4 | Where to run recovery | **Job runner:** after finish_job_run_success, call recovery for that job_name (resolves job_monitor incidents for that job when condition cleared). **SLA watchdog:** at start, run recovery pass for heartbeat and delivery_unknown (and optionally for all open job_monitor incidents to catch any cleared by other runs). |

---

## 4. Implementation Order (Safest)

1. **Incident metadata and resolve extension**  
   - Add optional metadata.recovery_source and metadata.resolution_notes (or resolution_notes) in resolve_incident; add resolve_incident_auto_recovery(incident_id, resolution_note) that sets resolved_by="system" (or null) and recovery_source + resolution_notes.  
   - In sla_watchdog create_incident calls, add metadata.triggering_reason (and created_from_run_id if easily available).

2. **Recovery helper**  
   - Add `incident_recovery.py` (or in incident_service): `resolve_recovered_incidents_for_job(job_name, latest_run_finished_at, latest_run_status)` – finds open job_monitor incidents for that job, applies rules above, resolves with auto note.  
   - Add `check_and_resolve_heartbeat_incidents()`, `check_and_resolve_delivery_unknown_incidents()` using same conditions as sla_watchdog (heartbeat not stale; no delivery_unknown stale runs).

3. **Hook recovery into job completion**  
   - In job_runner.run_instrumented, after finish_job_run_success (and after finish_job_run_degraded for "degraded" incident resolution when latest is success), call resolve_recovered_incidents_for_job(job_id, finished_at_iso, status). Pass job_run_id so resolution_notes can cite the run.

4. **Recovery pass in sla_watchdog**  
   - At start of run_sla_watchdog, before creating incidents: call check_and_resolve_heartbeat_incidents(); call check_and_resolve_delivery_unknown_incidents(); optionally call resolve_recovered_incidents_for_job for each critical job that has a recent success (or limit to jobs that have an open incident). Keep creation logic unchanged.

5. **Observability API**  
   - Add POST /api/admin/observability/incidents/{incident_id}/run-job: load incident, if source=job_monitor and related_job_name in JOB_RUNNERS, call run_instrumented(related_job_name, "manual", triggered_by=user), return result.  
   - Enrich GET /api/admin/observability/incidents/{id} (or add query param) with recovery_detected and, if useful, last_success/last_failure/expected_interval for job-related incidents.

6. **Checklist and script**  
   - Add docs/AUTOMATION_PRODUCTION_READINESS_CHECKLIST.md with the 5 tests.  
   - Add backend/scripts/verify_automation_recovery.py: open incidents, recent job_runs, heartbeat/delivery state; print which incidents would be auto-resolved and why.

7. **UI**  
   - If the incidents/observability UI lives in this repo, add "Run job now" button and recovery hint. Otherwise document the new/updated endpoints for the frontend.

---

## 5. Incidents That Still Require Manual Resolution by Design

- **API error / webhook / email** (source = api_error, webhook, email): no automatic "condition cleared" in this system; remain manual.  
- **Acknowledged** incidents: auto-recovery can either be allowed to resolve them (treat as "condition cleared") or leave them for manual resolve only; recommend **allowing** auto-resolve for acknowledged so recovery is consistent.  
- **Degraded-run** incident: only auto-resolve when the **next** run is **success**; if the next run is again degraded, do not resolve.  
- **Delivery unknown / heartbeat**: only when the underlying metric is actually cleared (no stale delivery_unknown runs; heartbeat fresh).

---

## 6. Summary

- **Implemented:** Incident create/ack/resolve, sla_watchdog creation rules, POST /api/admin/jobs/run, observability incidents list/detail/ack/resolve, job run instrumentation, verify_automation_runtime.py.  
- **Missing:** Auto-recovery logic, recovery_source/resolution_notes, triggering_reason (and optional created_from_run_id), recovery pass in sla_watchdog and after job success, incident-scoped "run job" endpoint, recovery_detected enrichment, production-readiness checklist, verify_automation_recovery.py.  
- **Conflicts resolved:** Use resolved + metadata for recovery; keep existing jobs/run endpoint; add optional incident-scoped run-job; run recovery both after job success and in sla_watchdog.

Implement in the order above; do not change existing scheduler or incident creation behaviour beyond adding metadata and the recovery pass.
