# MongoDB Health Authority Correction

**Audit ID:** `MONGODB-PREVENTION-DEPLOYMENT-AND-RUNTIME-RECOVERY-01`

## Authority

`services/scheduler_health_authority.py` is the single evaluator for heartbeat freshness.

| Status | Meaning |
|--------|---------|
| healthy | Heartbeat age ≤ 300s |
| unhealthy | Stale or missing |
| unknown | Unparseable / missing |
| disabled_by_design | Explicit disable |
| degraded | Startup degraded overlay |

## Surfaces

| Surface | Behaviour |
|---------|-----------|
| `/api/health` | `status` mirrors scheduler; includes `scheduler` object; HTTP 200 when process up (Render liveness) |
| health-summary | Uses same evaluator → `heartbeat_stale` / `scheduler_health` |
| Control Centre | Consumes health-summary |

## Runtime proof

| Time | `/api/health.status` | Heartbeat |
|------|----------------------|-----------|
| Pre-scheduler-ready | `unhealthy` | 2026-07-16 (stale) |
| Post-ready | `healthy` | 2026-08-06 advancing |

Stale critical heartbeat no longer coexists with `status: healthy`.
