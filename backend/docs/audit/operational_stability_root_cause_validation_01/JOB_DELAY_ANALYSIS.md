# Job Delay Analysis

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01

For each alert type, first responsible component:

---

## Deploy-cluster delays (shared)

| Job | First failure point | Not caused by |
|---|---|---|
| scheduler_heartbeat | **Scheduler process down** (Render restart) | Mongo, provider, locks |
| risk_signal_regen_worker | **Scheduler process down** | Queue backlog, DB slow, worker logic |
| scheduled_admin_communications | **Scheduler process down** | External provider |
| notification_retry_worker | **N/A — no delay observed** | — |
| sla_watchdog | **Scheduler process down** | Self-blocked |

**First component:** Render container recycle → APScheduler unavailable

---

## compliance_check_evening (independent)

| Stage | Finding |
|---|---|
| Scheduled? | **Yes** — CronTrigger 18:00 UTC fired |
| Started? | **Yes** — 2026-06-27T18:00:02 |
| Executed? | **Yes** — ran ~20s |
| Completed? | **Failed** — not delayed |
| First failure point | **Application code** — `normalize_requirement_code()` returned None in compliance timeline |

**Not:** scheduled late, queued late, DB wait, provider wait, lock contention.

---

## work_order_schedule_reminders

| Stage | Finding |
|---|---|
| Scheduled late? | **Yes** — 15:20 slot missed due to deploy |
| First failure point | **Scheduler unavailable** during deploy window |

---

## Steady-state performance (non-deploy)

| Job | Typical interval | Observed |
|---|---|---|
| notification_retry_worker | ~60s | 503 runs / 8.5h ≈ 59s ✓ |
| scheduler_heartbeat | ~120s | 249 runs / 8.5h ≈ 123s ✓ |
| risk_signal_regen_worker | ~30s | Continuous success outside deploy gaps |

**No chronic slow execution identified.**

---

## Verdict

All investigated delays trace to **(A) deploy scheduler downtime** or **(B) application exception in compliance_check_evening**. No worker defect, queue defect, or chronic DB latency.
