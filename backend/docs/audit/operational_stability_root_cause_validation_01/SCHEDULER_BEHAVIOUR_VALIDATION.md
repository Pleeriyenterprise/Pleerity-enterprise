# Scheduler Behaviour Validation Report

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01  
**Environment:** Staging

---

## Architecture (confirmed)

- **51 jobs** registered in-process via APScheduler on Render web service
- **No external cron** — scheduler lifecycle tied to container process
- **Heartbeat job** every 2 min → writes `scheduler_heartbeat.last_heartbeat_at`
- **SLA watchdog** every 10 min → reads heartbeat + job_runs

---

## Validation window statistics

| Job | Runs | Success | Failed | Notes |
|---|---|---|---|---|
| scheduler_heartbeat | 249 | 249 | 0 | Continuous except deploy gaps |
| risk_signal_regen_worker | (high freq) | — | 0 | 30s interval |
| notification_retry_worker | 503 | 503 | 0 | Every ~60s |
| scheduled_admin_communications | — | — | 0 | Every 2 min |
| sla_watchdog | — | — | 0 | Normal ~601s inter-run gap |

---

## Scheduler interruption events

Two deploy-correlated interruptions identified:

1. **~15:10–15:45 UTC** — ops remediation deploys (`12ea3502`, `02e71254`)
2. **~21:40–22:10 UTC** — Control Centre fix deploy (`f2c10442`)

During each:
- APScheduler **did not run** (process down)
- Heartbeat collection **not updated** for 414–435 seconds
- High-frequency jobs **missed SLA windows**
- **Not** thread blocking, lock contention, or event-loop starvation — full process restart

---

## Post-recovery behaviour

| Check | Result |
|---|---|
| All 51 jobs re-register | Yes (after warmup) |
| Heartbeat resumes | Yes — last at 22:31:43 |
| Job runs resume | Yes — continuous success after each deploy |
| Misfire handling | Jobs use `misfire_grace_time` (120–300s); deploy gaps exceed grace → expected miss |

---

## Answers to investigation checklist

| Question | Answer |
|---|---|
| Scheduler actually stopped? | **Yes — during Render restarts only** |
| Thread blocked? | **No evidence** |
| APScheduler continued during restart? | **No — process terminated** |
| Heartbeat generation delayed vs persistence delayed? | **Generation stopped** (no process) |
| Mongo unavailable? | **No** |
| DB latency excessive? | **No** |
| Blocked by another task? | **No — full downtime** |
| CPU/memory/GC? | **Not measured; consistent with cold restart not saturation** |
| Heartbeat delayed while jobs ran? | **No — gaps correlated 1:1** |
| Jobs genuinely stopped? | **Yes during deploy windows only** |

---

## Verdict

Scheduler behaviour is **correct and predictable**. Deploy-induced downtime is the **only** shared scheduler interruption in the validation window. No scheduler defect identified.
