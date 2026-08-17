# ANALYTICS_SCHEDULER_IMPLEMENTATION_REPORT

**Phase:** `PHASE_B_ANALYTICS_SCHEDULED_OPERATION_01`  
**Date:** 2026-07-14  
**Scope:** Staging-only daily schedule for validated Zoho Analytics export

---

## Objective

Move Zoho Analytics from manual-only staging operation to a controlled daily staging schedule without enabling production or any other Zoho integration.

## Precondition — MongoDB timestamp storage

### Investigation (writer code, not assumed)

| Collection / field | Writer evidence | Representation |
|---|---|---|
| `leads.created_at` | `lead_service.py` assigns `datetime.now(timezone.utc).isoformat()` | ISO-8601 strings (primary) |
| `leads.converted_at` | Same pattern; convert path parses with `fromisoformat` | ISO-8601 strings (primary) |
| `support_tickets.created_at` / `updated_at` | `support_service.py` uses `.isoformat()` | ISO-8601 strings (primary) |

BSON UTC datetimes remain possible for historical rows. String-only `$gte`/`$lt` bounds would **undercount** any BSON-stored timestamps.

### Fix

`period_timestamp_filter()` in `metrics/analytics_export.py` emits an `$or` of:

1. ISO string bounds  
2. BSON `datetime` bounds  

Used by `build_analytics_export()` for period-scoped lead and closed-ticket counts.

Constant: `TIMESTAMP_STORAGE_NOTE = primary_iso_strings_with_dual_bound_query_for_bson_compat` (surfaced on `analytics_ops`).

---

## Scheduling implementation

| Item | Implementation |
|---|---|
| Framework | Existing APScheduler (`server.py`) → `job_runner:run_scheduled_job` → `zoho_analytics_export` |
| Cadence | Daily **02:15 UTC** (`CronTrigger(hour=2, minute=15)`) |
| Environment gate | `zoho_analytics_schedule_registration_allowed()` — `ENVIRONMENT`/`ENV` **must be `staging`**; **never** production |
| Overlap | APScheduler `max_instances=1`, `coalesce=True`, plus DB lock `zoho_analytics_export_locks` |
| Period | Last completed UTC calendar day (unchanged `resolve_daily_reporting_period`) |
| `force_reexport` | Always `False` from scheduled/manual job runner path |
| Duplicate guard | Existing `find_successful_analytics_period_export` remains authoritative (skip, not failure) |

### Flag / kill-switch behaviour

When `ZOHO_KILL_SWITCH`, master flag, or Analytics flag disables the path, `run_zoho_analytics_export` returns **SKIPPED** with `outcome_status=success` and records skip reason in `outcome_metrics` (not a job failure).

### Soft failure / DL

Unchanged: Analytics soft failures → existing dead-letter path; no new infinite retries; HTTP timeout unchanged (30s client preserved).

---

## Observability (`analytics_ops`)

Exposed via existing System Health / Platform Status / Control Centre surfaces:

- `schedule_enabled` / `schedule_registration_allowed`
- `configured_cadence` (`Daily 02:15 UTC`)
- `next_scheduled_run`
- `last_scheduled_attempt` / `last_scheduled_success` / `last_scheduled_failure`
- `last_exported_period` (+ start/end)
- `consecutive_failures`
- `duplicate_skips`
- `dead_letter_count`
- `run_lock_status`
- `incident_policy`

### Incident policy

| Condition | Level |
|---|---|
| Kill switch / disabled flags / non-staging | `disabled_expected` (not an incident) |
| 1 consecutive failure | `warning` (Control Centre MEDIUM) |
| 2 consecutive failures | `degraded` (Control Centre HIGH; overall health can degrade) |
| 3 consecutive **or** no success within 48h while armed (with prior success timestamp) | `incident` (actionable Control Centre HIGH) |

---

## Files touched

| File | Change |
|---|---|
| `metrics/analytics_export.py` | Dual-bound period filters |
| `analytics_schedule.py` | **New** — lock, next-run helper, schedule state |
| `config.py` | Staging registration gate |
| `types.py` | Lock collection + `RUN_LOCK_HELD` |
| `job_runner.py` | Lock, skip outcomes, no force, fail→`OUTCOME_FAILED` |
| `server.py` | Staging-only `add_job` at 02:15 UTC |
| `operational_health.py` | Extended `analytics_ops` + policy |
| `control_centre_service.py` | Warning / degraded / incident rows |

---

## Production

**Not registered. Not enabled.** See `ANALYTICS_PRODUCTION_SCHEDULE_GATE.md`.
