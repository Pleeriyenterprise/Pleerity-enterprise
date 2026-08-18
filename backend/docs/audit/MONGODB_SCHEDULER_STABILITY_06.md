# MongoDB scheduler stability 06

**Programme:** `MONGODB-24H-SOAK-CLOSURE-AND-PROMOTION-GATE-06`  
**Window:** 2026-08-15T21:19:51Z → 2026-08-17T06:11Z on SHA `fb138ae5` / `dep-da0dekm1egvs739e9dog`.

## Heartbeat

| Check | Close of soak |
| --- | --- |
| `/api/health` scheduler | `healthy`, `stale=false`, `reason=heartbeat_fresh` |
| Last heartbeat | `2026-08-17T06:04:36.113594Z` (health-summary); advancing at 06:10:36Z on poll heartbeat |
| Age | ~10–50 seconds vs 300s stale threshold |
| `heartbeat_stale` | false |
| `scheduler_heartbeat` job_runs in-window | **0** (always-skip; `scheduler_heartbeat` collection is authority) |
| `scheduler_heartbeat` collection | 2 docs |
| Poll heartbeat ticks (lifetime upsert) | 7,628; `skipped_persist=true`; last tick `2026-08-17T06:10:36Z` |

Heartbeat remained fresh for the observation period after the known recovery at `2026-08-15T21:26:36Z`.

## Process continuity

| Check | Result |
| --- | --- |
| Hourly `instance_count` | **1** at every sample 21:19Z 15 Aug → 05:19Z 17 Aug |
| Later Render deploys | **none**; live remains `dep-da0dekm1egvs739e9dog` |
| Startup / uvicorn logs after 21:20Z | **none** |
| Duplicate scheduler | **no** (single instance; no second deploy) |
| `scheduler_leases` | empty / none — **no stale leases** |
| Unexplained scheduler restarts | **none** after the soak-starting deploy recovery |

The 21:19–21:26Z stale window is the **documented** post-deploy recovery that started this soak, not a mid-window restart.

## Registered jobs and executions

| Check | Result |
| --- | --- |
| `scheduler_runtime.available` | true |
| Registered jobs | **54** |
| Job-state keys in health-summary | 51 |
| `job_runs` created in-window | **3,902** |
| Recent genuine work (not idle polls) | `order_delivery_processing`, `sla_watchdog`, `queued_order_processing`, `lead_followup_processing`, `mongo_storage_capacity_monitor`, SLA monitors — success at 5-minute cadence |
| Failed runs (last 24h) | 1 (`compliance_recalc_worker`) |
| Degraded runs (last 24h) | 3 (`compliance_recalc_worker` ×2, `daily_reminders` ×1) |
| Recalc queue posture | `NON_BLOCKING_OBSERVABILITY_ONLY`; pending 417 stale markers; dead_letter 0 |

Failed/degraded counts are non-zero but not a scheduler-down event. Heartbeat and instance count contradict a stuck or duplicated writer.

## Idle-skip (15s / 30s / 1m)

Theoretical ticks over **32.76h** vs persisted `job_runs` in the same window, versus lifetime poll-heartbeat upserts (document count stays at 5).

| Worker | Interval | Theoretical ticks | `job_runs` in soak | Lifetime poll ticks | Latest poll |
| --- | --- | ---: | ---: | ---: | --- |
| `compliance_recalc_worker` | 15s | ~7,862 | **28** | 59,657 | 06:11:24Z `skipped_persist=true` `idle=true` |
| `risk_signal_regen_worker` | 30s | ~3,931 | **622** | 25,452 | 06:11:06Z `skipped_persist=true` `idle=true` |
| `notification_retry_worker` | 1m | ~1,966 | **0** | 15,259 | 06:11:00Z `skipped_persist=true` `idle=true` |
| `scheduler_heartbeat` | ~2m | ~983 | **0** | 7,628 | 06:10:36Z `skipped_persist=true` |
| `scheduled_admin_communications` | ~2m | ~983 | **0** | 7,630 | 06:10:01Z `skipped_persist=true` `idle=true` |

Pre-remediation those three high-frequency workers created **~1.94M** `job_runs`. In this soak they created **650** combined (28+622+0), **4.7%** of theoretical idle ticks.

`compliance_recalc_worker` persisted rows are `outcome_kind=WORK_PERFORMED` (genuine work), last at 03:35Z — not a 15s flood.

`notification_retry_worker` and `scheduler_heartbeat` created **zero** `job_runs` while poll ticks advanced. That is the intended design.

### `risk_signal_regen_worker` condition

Recent persisted runs are `outcome_kind=BLOCKED` with `skipped_feature_flag_count`, `regenerated_count=0`, `attempted_count` 1–2. Idle-skip classifies `NO_WORK_ELIGIBLE` / `CONTENTION_ONLY` / zero-work as skippable; **`BLOCKED` still persists a `job_run`**.

622 documents in 32.76h is **not** a 30s persist-every-tick flood (that would be ~3,931). It is a bounded classifier gap, not a return of the 1.94M pattern. Do not treat as launch-blocking. Do not implement a skip-rule change in this closure exercise.

## Scheduler verdict

```text
SCHEDULER = PASS
IDLE_SKIP = PASS_WITH_CONDITION
```

Condition: `risk_signal_regen_worker` `BLOCKED` ticks still write `job_runs`. High-frequency idle ticks remain governed by poll heartbeats.
