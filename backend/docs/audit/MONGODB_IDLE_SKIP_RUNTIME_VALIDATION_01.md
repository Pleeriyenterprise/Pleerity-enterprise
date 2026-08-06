# Idle-Skip Runtime Validation

**Audit ID:** `MONGODB-PREVENTION-DEPLOYMENT-AND-RUNTIME-RECOVERY-01`

## Window A — after `a5bfccfd` (pre-contention fix)

210s observation. `job_runs` +11 / OEP +23. Idle workers wrote `job_poll_heartbeats` with `skipped_persist`. Defect: `CONTENTION_ONLY` recalc ticks still persisted.

## Window B — after `9b76213e` (contention fix)

240s observation (`mongodb_idle_observation_post_9b76213e.json`):

| Metric | Before | After | Δ |
|--------|-------:|------:|--:|
| job_runs | 58 | 64 | +6 |
| OEP events | 261 | 273 | +12 |
| OEP executions | 2 | 2 | 0 |
| poll heartbeats | 5 | 5 | 0 (upserts) |
| scheduler heartbeat | advancing | advancing | — |

### Proven idle-skip (live)

| Worker | skipped_persist | idle | ticks (later recheck) |
|--------|-----------------|------|------------------------:|
| notification_retry_worker | true | true | 111 |
| risk_signal_regen_worker | true | true | 215 |
| scheduled_admin_communications | true | true | — |
| compliance_recalc_worker | true | true | 422 |
| scheduler_heartbeat | true | false (work) | — |

Heartbeat probe window: `job_runs` stayed **45→45** while heartbeat advanced.

### Genuine work still persists

Latest 30 `job_runs` include monitors/SLA/order jobs — **zero** `compliance_recalc_worker` rows. Idle/contention ticks no longer dominate.

### Idle-skip does not

- suppress heartbeat updates (advancing)
- suppress poll tick bookkeeping (`job_poll_heartbeats`)
- hide genuine monitor/SLA outcomes
