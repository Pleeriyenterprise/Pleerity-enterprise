# ANALYTICS_STAGING_SCHEDULE_VALIDATION

**Phase:** `PHASE_B_ANALYTICS_SCHEDULED_OPERATION_01`  
**Date:** 2026-07-14  
**Status:** **PENDING DEPLOY** — code and unit regression complete; live staging checklist below must be executed after deploy.

Do not fabricate a successful Zoho export. Scheduler-equivalent execution via `POST /api/admin/jobs/run` with job id `zoho_analytics_export` is allowed (same runner, `force_reexport=false`).

---

## Preconditions

1. Deploy backend build containing scheduler registration + dual-bound export filters to **staging only**.
2. Confirm `ENVIRONMENT=staging` (or `ENV=staging`) on the staging service.
3. Confirm production service still has `ENVIRONMENT=production` / `prod` and does **not** register `zoho_analytics_export`.

---

## Checklist

| # | Validation | Expected | Result |
|---|---|---|---|
| 1 | Staging health | System Health / Zoho overall not unexpectedly failed; kill switch off unless testing | ☐ PENDING |
| 2 | Scheduler registration once | Logs contain single `registered zoho_analytics_export at Daily 02:15 UTC`; one job id in `scheduler.get_jobs()` | ☐ PENDING |
| 3 | No duplicate after restart/redeploy | `replace_existing=True`; after redeploy still **one** `zoho_analytics_export` | ☐ PENDING |
| 4 | Scheduler-equivalent test run | Admin job run **without** force override; period = last completed UTC day | ☐ PENDING |
| 5 | Duplicate protection | Second run for same period → SKIPPED `period_already_exported` (not failure) | ☐ PENDING |
| 6 | Run-lock | Concurrent second execution → `run_lock_held` skip while first holds lock | ☐ PENDING |
| 7 | Kill-switch skip | `ZOHO_KILL_SWITCH=true` → skip `kill_switch_active`, success outcome, not incident | ☐ PENDING |
| 8 | Controlled soft failure → DL | Induce recoverable Analytics failure → dead letter created | ☐ PENDING |
| 9 | Replay resolves DL | Replay via existing dead-letter path resolves or increments replay correctly | ☐ PENDING |
| 10 | Production unchanged | Prod has no Analytics schedule job; Zoho admin/prod posture unchanged | ☐ PENDING |

---

## Observability spot-checks (after step 4+)

Confirm `analytics_ops` shows:

- `schedule_registration_allowed: true` (staging)
- `configured_cadence: Daily 02:15 UTC`
- `next_scheduled_run` populated
- `last_scheduled_*` updated after test run
- `run_lock_status`
- `duplicate_skips` / `dead_letter_count` as applicable
- `incident_policy.level` appropriate for outcomes (kill switch → `disabled_expected`)

---

## Sign-off

| Field | Value |
|---|---|
| Deployed commit | _pending_ |
| Validated by | _pending_ |
| Staging cycles completed (toward prod gate) | **0 / 3** consecutive daily scheduled successes |

When all ten rows are PASS, update this document and reconsider the production gate.
