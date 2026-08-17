# Production promotion backend deployment 07

**Programme:** `PRODUCTION-PROMOTION-EXECUTION-07`  
**Result:** PASS

## Identity

| Field | Value |
| --- | --- |
| Service | `pleerity-api-production` (`srv-d8m59gmgvqtc73cmbu6g`) |
| Branch | `main` (`autoDeploy=yes`, trigger `commit`) |
| Merge SHA | `b6b7ddf553482fa2797f317ce69296b21a494230` |
| Deploy | `dep-da1ashu1egvs73a2chb0` |
| Started | 2026-08-17T06:46:31Z |
| Finished / live | 2026-08-17T06:49:14Z |
| Manual `trigger_deploy` | **not used** (auto-deploy) |

## Runtime

| Check | Result |
| --- | --- |
| `https://pleerity-api-production.onrender.com/api/version` | `b6b7ddf5…`, `environment=production` |
| `https://api.pleerityenterprise.co.uk/api/version` | same |
| Staging env leak | none — reports `production` |
| Mongo connect | startup reached `post_db_initialization` then `ready` |
| Jobs registered | 53 (log at 06:54:20Z) |
| Scheduler resumed | 06:56:54Z |
| First heartbeat | 06:56:56Z |
| Health at 07:02Z | `healthy` / `ready` / `heartbeat_fresh` (age ~40s) |
| Health at 07:20Z | still `healthy` / `ready` / `heartbeat_fresh` (age ~51s; heartbeat `2026-08-17T07:20:06Z`) |

## Expected startup window

| Time (UTC) | Event |
| --- | --- |
| 06:49 | version already `b6b7ddf5`; `/api/health` 503 |
| 06:50 | two 502s (deploy cutover) |
| 06:53 | one 503; health `unhealthy`, stage `post_db_initialization`, heartbeat stale (legacy 2026-07-27 timestamp) |
| 06:54:20 | scheduler started paused; 53 jobs |
| 06:54–06:56 | SLA-miss incidents for jobs that had not yet ticked (expected) |
| 06:56:54 | scheduler resumed |
| 06:56:56 | heartbeat job success |
| 06:57+ | `/api/health` `healthy` / `heartbeat_fresh` |

Instance count remained **1**. No crash loop.

Staging env vars were **not** copied into production.
