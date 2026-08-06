# Operational Telemetry Reduction

**Audit ID:** `MONGODB-STORAGE-REMEDIATION-AND-LIFECYCLE-GOVERNANCE-01`  
**Date:** 2026-08-06

---

## Root cause of ~1.9M staging `job_runs`

Almost entirely **schedule** runs (not manual/cert one-offs):

| Job | Approx docs | Interval | Cause |
|-----|-------------|----------|-------|
| `compliance_recalc_worker` | 814k | 15s | Idle poll still persisted full `job_runs` + OEP |
| `risk_signal_regen_worker` | 384k | 30s | Same |
| `notification_retry_worker` | 211k | 1m | Same |
| `scheduler_heartbeat` | 105k | 2m | Redundant with `scheduler_heartbeat` collection |
| `scheduled_admin_communications` | 93k | 2m | Idle ticks persisted |

≈ **83%** of staging `job_runs` from these five jobs. Not duplicate schedulers or runaway loops — **unbounded instrumentation of empty polls** + missing pruning.

---

## Fix implemented

`services/job_run_idle_persist.py` + `run_instrumented` high-frequency path:

1. For listed schedule jobs: execute first.  
2. On idle success: upsert `job_poll_heartbeats` only — **no** `job_runs`, **no** OEP emit.  
3. On work / failure / degraded: full persist as before.  
4. `scheduler_heartbeat`: always skip `job_runs` (heartbeat collection remains authoritative).  
5. Flag: `JOB_RUN_SKIP_IDLE_HIGH_FREQUENCY` (default **on**).

Health summary merges `job_poll_heartbeats` into `last_completed` so idle-skip does not false-alarm “never ran”.

---

## Further reduction (optional next)

| Idea | Benefit |
|------|---------|
| Daily roll-up collection for job outcomes | Keep trends without raw rows |
| Cap OEP emit for empty queue workers | Fewer derived events |
| Bound OEP backfill lookback | Stop re-amplification |
| Review 20 indexes on `operational_evidence_events` | Index byte savings |

Preserve audit value: failures, degraded runs, and non-empty work still create full `job_runs` + OEP.
