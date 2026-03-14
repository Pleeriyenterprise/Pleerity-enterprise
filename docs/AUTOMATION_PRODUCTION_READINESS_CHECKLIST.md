# Automation production-readiness checklist

This checklist supports **final operational hardening** of Pleerity automation: incident auto-recovery, "Run job now" from incidents, incident–job linking, and observability. Use it before treating automation as production-ready.

**Reference:** `docs/AUTOMATION_HARDENING_INCIDENT_RECOVERY_AUDIT.md`  
**Recovery verification script:** `backend/scripts/verify_automation_recovery.py` (dry-run: lists open incidents and which would auto-resolve; does not perform resolution)

---

## 1. Scheduled execution

| Check | How to verify | Pass criteria |
|-------|----------------|----------------|
| Critical jobs run on schedule | Inspect `job_runs` (or run `python -m scripts.verify_automation_runtime`) | daily_reminders, sla_watchdog, pending_verification_digest, etc. show runs at expected cadence |
| Scheduler heartbeat is updated | Observability health or DB `scheduler_heartbeat` | `last_heartbeat_at` is within HEARTBEAT_STALE threshold (e.g. last 10 minutes) |
| Next run times are set | Scheduler logs or `scheduled_jobs` (if used) | Jobs have `next_run_time` consistent with cron/config |

---

## 2. Manual recovery ("Run job now")

| Check | How to verify | Pass criteria |
|-------|----------------|----------------|
| Run job from incident | `POST /api/admin/observability/incidents/{incident_id}/run-job` for an incident with `source=job_monitor` and `related_job_name` in runnable jobs | 200; job runs; response includes run result |
| Run job from admin jobs API | `POST /api/admin/jobs/run` with body `{ "job": "<job_id>" }` | 200; job runs |
| Incident auto-resolves after successful run | Create or use an open job_monitor incident, trigger run for that job, job completes success/degraded per recovery rules | Incident moves to resolved with `metadata.recovery_source` and resolution note (when condition is cleared) |

**Note for UI:** The observability API supports "Run job now" via `POST /api/admin/observability/incidents/{incident_id}/run-job`. GET incident with `enrich=true` (default) returns `recovery_detected`, `recovery_hint`, `last_success`, `last_failure`, `expected_interval` for status line and recovery hint.

---

## 3. Output proof

| Check | How to verify | Pass criteria |
|-------|----------------|----------------|
| Job runs record outcome | `job_runs` collection: status, finished_at, outcome_metrics, message_logs | Success/degraded/failed and timestamps present; delivery-related jobs have delivery metrics |
| Delivery reconciliation | Reconciliation jobs and delivery state API | Runs with delivery_unknown / success counts as expected; no stale delivery_unknown beyond threshold without incident |
| Evidence of sent work | message_logs, reminders/digest records, or downstream systems | Reminders/digests sent and logged where applicable |

---

## 4. Incident honesty

| Check | How to verify | Pass criteria |
|-------|----------------|----------------|
| Incidents created only when condition exists | Review incidents created by sla_watchdog; check `metadata.triggering_reason` | triggering_reason set (heartbeat_stale, delivery_unknown_stale, job_never_succeeded, missed_sla, degraded_run); incident created only when corresponding condition is true |
| No inappropriate auto-resolution | Run recovery logic (sla_watchdog pass, or after job success); check resolved incidents | Only incidents whose underlying condition is cleared are resolved; degraded_run incidents only resolve when latest run is success |
| Linking and metadata | GET incident; inspect related_job_name, source, metadata | related_job_name and triggering_reason populated for job_monitor; source and metadata consistent |

---

## 5. Recovery

| Check | How to verify | Pass criteria |
|-------|----------------|----------------|
| Recovery state computation | Run `python -m scripts.verify_automation_recovery` or GET incident with `enrich=true` | Open incidents show `recovery_detected` true only when condition is cleared; hints and last_success/expected_interval sensible |
| Heartbeat recovery | After heartbeat is fresh, run sla_watchdog (or recovery pass) | Open heartbeat incidents resolve; resolved have resolution_notes/recovery_source |
| Delivery-unknown recovery | After no stale delivery_unknown runs, run sla_watchdog | Open delivery_unknown incidents resolve |
| Job-monitor recovery | After a successful (or degraded, per rules) run for the job | Open job_monitor incidents for that job resolve when rules allow; resolved incidents have metadata.recovery_source and resolution_notes |

---

## Quick commands

```bash
# From backend root
python -m scripts.verify_automation_runtime    # job_runs, scheduled_jobs, incidents, recommendations
python -m scripts.verify_automation_recovery   # open incidents, recovery state (dry-run), recent job runs
```

---

## Incidents that remain manual by design

- **api_error, webhook, email** (source): no automatic "condition cleared" in this system; resolve manually.
- **job_monitor (degraded_run):** auto-resolves only when the **next** run is **success**.
- **heartbeat / delivery_unknown:** auto-resolve only when heartbeat is fresh or there are no stale delivery_unknown runs (checked on sla_watchdog run).
