# Shared Root Cause Correlation Matrix

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01  
**Window:** 2026-06-27T14:00Z – 22:33Z (staging)

---

## Cluster A — Render deploy / container restart (primary shared cause)

| Event | ~15:20–15:45 UTC (`12ea3502` / `02e71254`) | ~21:45–22:10 UTC (`f2c10442`) |
|---|---|---|
| Render instance restart | Yes (connection drops observed during polling) | Yes |
| Scheduler heartbeat gap | **435.6s** (last HB 15:37 → 15:44) | **414.0s** (21:48 → 21:55) |
| Heartbeat stale incident (P1) | Created 15:23, resolved 16:10 | Created 21:54, resolved 22:30 |
| risk_signal_regen_worker gap | **268.8s** | **283.9s** |
| risk_signal_regen P0 incident | Created 15:24, resolved 15:44 | Created 21:54, resolved 22:15 |
| scheduled_admin_communications P0 | Created 15:24, resolved 15:46 | — |
| sla_watchdog gap | **777.8s** | **838.8s** |
| Jobs stopped permanently? | **No** — 249 heartbeat successes in window | **No** |
| Mongo unavailable? | **No** — API/DB healthy post-warmup | **No** |
| Queue backlog? | **No** — pending=0 at recovery | **No** |

**Causal chain:**

```
Render deploy / container recycle
    ↓
APScheduler process down ~7–14 min
    ↓
scheduler_heartbeat not persisted (>300s) → P1 heartbeat stale
    ↓
High-frequency jobs miss 3–6 min SLA windows → P0 missed SLA
    (risk_signal_regen_worker, scheduled_admin_communications)
    ↓
sla_watchdog itself offline → extended gap ~778–839s
    ↓
Automatic recovery when scheduler resumes
    ↓
Incidents auto-resolved (recovery_source: automatic_job_recovery)
```

**Classification:** Expected deployment behaviour + correctly functioning operational protection.

---

## Cluster B — Application defect (compliance timeline null canonical)

| Alert | Root cause | Related to Cluster A? |
|---|---|---|
| compliance_check_evening missed SLA (P2, **open**) | Job **ran and FAILED** at 2026-06-27T18:00:22 with `'NoneType' object has no attribute 'upper'` — same bug as Control Centre HTTP 500 | **No** — independent timing |
| Control Centre HTTP 500 (prior validation) | `normalize_requirement_code(slug)` returned None in `_family_rules_for_requirement` | Same code path |

**Fix:** `f2c10442` deployed 21:45 UTC. Evening job runs once daily at 18:00 UTC — **next success opportunity: 2026-06-28T18:00Z**. Incident correctly remains open until success or manual resolve.

**Classification:** Application defect — **remediated in code**, awaiting next scheduled run for incident closure.

---

## Cluster C — Deploy-adjacent schedule miss (hourly job)

| Alert | Root cause |
|---|---|
| work_order_schedule_reminders missed SLA (P2, resolved) | Hourly job at :20; 15:20 deploy window missed 15:20 slot; last success 14:20; delay 100 min at 16:00 incident; resolved when 17:20 run succeeded |

**Classification:** Expected deployment behaviour (downstream of Cluster A).

---

## Non-alert: notification_retry_worker

User cited "Notification retry worker delayed" as example alert type. **No incident created** in validation window. Runtime: **503/503 success** runs (every ~60s). **No defect found.**

If email was received, it was likely presentation text for a different job or a deploy-cluster alert that resolved before persistence in our filter.

---

## Evidence

`INCIDENT_RECONSTRUCTION.json` — incidents, job timelines, gap_analysis, deploy_correlation
