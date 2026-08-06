# Observability Consistency Validation

**Audit ID:** `PRODUCTION-READINESS-CLOSURE-01`  
**Date:** 2026-08-06

## Authority model

| Signal | Authority |
|--------|-----------|
| Scheduler liveness | `scheduler_heartbeat` + `scheduler_health_authority` |
| High-freq idle ticks | `job_poll_heartbeats` (merged into health-summary `last_completed`) |
| Platform process health | `/api/health` (HTTP 200 + truthful `status`) |
| System Health / Control Centre | `build_health_summary_payload` + Control Centre snapshot |
| Storage | `mongo_storage_monitor` / `mongo_storage` on health-summary |
| Incidents | lifecycle + SLA watchdog recovery |

## Cross-surface audit (pre-fix)

| Surface | Observed | Agreement? |
|---------|----------|------------|
| Mongo heartbeat | Fresh / advancing | — |
| `/api/health` | `healthy`, scheduler `heartbeat_fresh` | Aligns with heartbeat |
| health-summary `scheduler_health` | healthy | Aligns |
| health-summary `mongo_storage` | `ok` ~46.85% | Aligns with capacity reality |
| Job states for idle workers | Some `missed` / `never_ran` despite fresh poll ticks | **Drift** |
| Open incidents | P0 “has not succeeded” for idle-skip workers; P1 heartbeat stale in recovery window | **Drift vs runtime** |
| Control Centre | Surfaces open incidents → `attention_required` | Reflects incident table, not poll truth |

## Correction shipped

Commit `7d8e3648`:

- health-summary treats poll ticks / non-stale heartbeat as healthy for idle-skip / heartbeat jobs  
- SLA watchdog treats fresh poll heartbeats as success  
- Incident recovery resolves idle-skip job_monitor incidents when poll ticks are fresh  

## Post-deploy expectation

After staging runs `7d8e3648` and SLA recovery windows elapse (stable 300s + auto-resolve 900s for recovered lifecycle):

- no new P0s for actively ticking idle-skip workers  
- heartbeat P1 progresses RECOVERED → RESOLVED when fresh  
- System Health / Control Centre converge with `/api/health` and Mongo runtime  

## Residual

Until soak confirms post-fix convergence for a full day, observability consistency is **conditionally** accepted.
