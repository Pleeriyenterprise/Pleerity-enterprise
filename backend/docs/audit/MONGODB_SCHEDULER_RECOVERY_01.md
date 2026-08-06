# MongoDB Scheduler Recovery

**Audit ID:** `MONGODB-PREVENTION-DEPLOYMENT-AND-RUNTIME-RECOVERY-01`  
**Date:** 2026-08-06

## Root cause of stale heartbeat (2026-07-16 → deploy)

| Finding | Evidence |
|---------|----------|
| Heartbeat writer | `run_scheduler_heartbeat` → `scheduler_heartbeat` `_id=default` |
| Ownership | In-process `AsyncIOScheduler` in web service (`server.py` lifespan) |
| Why stale | After Atlas write block, process likely degraded; heartbeat frozen at `2026-07-16T17:39:33Z` |
| Post-deploy lag | Startup stage stayed `post_db_initialization` for several minutes while seeds/indexes ran **before** `scheduler.resume()` |
| Recovery | After heavy startup finished → stage `ready`, heartbeat advanced to `2026-08-06T15:09:59Z` |

## Not the cause

- Idle-skip does **not** suppress heartbeat collection writes (ALWAYS_SKIP only skips `job_runs`)
- Wrong DB: writing `pleerity_staging` correctly
- Probe syntax error was in validation aggregate only (fixed separately)

## Proof of operation

| Check | Result |
|-------|--------|
| Heartbeat advances | Yes (15:09 → 15:13 in observation) |
| `/api/health` scheduler.fresh | `heartbeat_fresh` |
| Poll ticks | `job_poll_heartbeats` for high-freq workers |

## Residual risk

Long post-DB seed path delays scheduler start after each deploy. Future hardening (out of critical path): start scheduler immediately after `db_ready`.
