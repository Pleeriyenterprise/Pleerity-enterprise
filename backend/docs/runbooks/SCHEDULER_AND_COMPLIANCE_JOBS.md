# Scheduler, compliance recalc worker, and Render deployment

This runbook explains how background jobs are expected to run in production and what to check when alerts fire.

## Where the scheduler runs

- The API process (`server.py`) starts an **APScheduler** `AsyncIOScheduler` when the app boots.
- Scheduled jobs invoke `job_runner.run_scheduled_job` → `run_instrumented`, which writes **`job_runs`** in Mongo for observability and the SLA watchdog.
- **Recommendation:** run **exactly one** long-lived web/worker process (or dedicated worker service) that owns the scheduler for a given environment. Multiple Python processes each starting the scheduler can **duplicate** job execution unless the Mongo job store correctly coordinates leadership.

## Mongo job store

- When `MONGO_URL` / job store configuration succeeds, the scheduler uses a **Mongo-backed job store** (`server.py` — `mongo_client` jobstores). That store is the coordination surface for “which instance should fire next”.
- If the job store **fails to configure**, the code falls back to an **in-memory** store: **each process has its own schedule**, which is unsafe for multi-instance deployments (duplicate ticks).
- **Check:** application logs at startup for `MongoDB job store configured` vs `using memory store`.

## Compliance recalc worker cadence and SLA

- Scheduler fires **`compliance_recalc_worker`** every **15 seconds** (`IntervalTrigger`), with `max_instances=1` and `coalesce=True` (`JOB_DEFAULTS` in `server.py`).
- Each tick may process up to **10** pending queue rows and can run **long** `recalculate_and_persist` work plus score-event side effects.
- **`job_schedule_registry`**: `max_delay_minutes` for `compliance_recalc_worker` is **10 minutes** (raised from 2) so the SLA watchdog does not false-positive when a single instrumented run legitimately exceeds a short wall-clock window. This does **not** relax per-property queue SLA alerts (`compliance_recalc_sla_monitor`).

## Stale `RUNNING` reclaim

- **`COMPLIANCE_RECALC_RUNNING_STALE_SECONDS`** (default **1800**): queue rows stuck in `RUNNING` beyond liveness (`max(heartbeat_at, updated_at)`) are reclaimed to **`PENDING`** (retry) or **`DEAD`** if attempts are exhausted — see `services/compliance_recalc_running_reclaim.py`.
- **Lease heartbeat:** while a job runs, **`heartbeat_at`** is refreshed periodically (`COMPLIANCE_RECALC_HEARTBEAT_SECONDS`, default **45**) so long-running but healthy work is not mistaken for stuck `RUNNING` rows in the SLA monitor.

## Scheduler heartbeat

- Job **`scheduler_heartbeat`** writes `scheduler_heartbeat.last_heartbeat_at` every **2 minutes**.
- **`sla_watchdog`** opens a **heartbeat stale** incident when that document is older than **`HEARTBEAT_STALE_SECONDS` (300s)**.
- **If heartbeat goes stale:** confirm the **process that runs APScheduler** is up (not only a stateless HTTP replica), Mongo is reachable, and no deploy left the fleet without a scheduler owner.

## Separate Render web vs worker services

- If **web** and **worker** are split: only the service that **starts FastAPI + lifespan/scheduler** will run scheduled jobs. A standalone web tier with **no** scheduler will show **stale heartbeat** and missed `job_runs` unless a separate worker dyno runs the same app entrypoint with scheduling enabled.
- Align **one** service as the scheduler owner and document it in deployment config.

## Operational snapshots

- `build_recalc_queue_operational_snapshot` exposes **`stale_running_reclaimed_last_24h`** and stuck-running counts based on the same **liveness** model as reclaim/SLA.

## Incident lifecycle and alert quality (operational)

Incidents use **`lifecycle_state`** in addition to workflow **`status`** (`open` / `acknowledged` / `resolved`):

| Lifecycle | Meaning |
|-----------|---------|
| **OPEN** | First detection; one email per incident (idempotent) unless severity escalates |
| **DEGRADED** | Condition persisted beyond `INCIDENT_DEGRADED_AFTER_SECONDS` (default 10 min); dashboard shows repeat count |
| **RECOVERED** | Underlying health cleared for `INCIDENT_RECOVERY_STABLE_SECONDS` (default 5 min); **one recovery email** per incident |
| **RESOLVED** | Auto-closed after stable recovery (`INCIDENT_AUTO_RESOLVE_AFTER_RECOVERY_SECONDS`, default 15 min) or manual resolve |

**Dedupe:** `incident_fingerprint` (source + job + triggering reason) — repeated watchdog ticks update the same row (`repeat_count`, `last_detected_at`) instead of creating new incidents or emails.

**Suppression (email only):** P0 ~15 min, P1 ~30 min, P2 ~60 min between repeat emails for the same incident. **Never suppressed:** severity escalation, recovery emails, materially different fingerprints.

**Deployment windows:** set `PLATFORM_DEPLOY_SUPPRESSION_UNTIL` (ISO UTC) during deploys to mark `deployment_related_possible` and suppress **P2 transient missed-SLA** emails only. P0/P1 and queue blockages still alert.

**Flapping:** repeated unhealthy/healthy transitions in `INCIDENT_FLAP_WINDOW_SECONDS` mark `flapping=true` — investigate in Admin → Incidents.

**Queue visibility:** System Health `GET /health-summary` includes `recalc_queue_health` (depth, dead letter, stuck markers). Incident recovery emails attach queue snapshot when available.

**When to investigate vs monitor:** OPEN/DEGRADED with low repeat count — monitor if deploy window active. DEGRADED + high `repeat_count` or flapping — investigate. RECOVERED — confirm no customer impact; keep watching 24h.

## Related code

- `backend/job_runner.py` — worker + heartbeat loop  
- `backend/services/compliance_recalc_running_reclaim.py` — reclaim  
- `backend/services/compliance_sla_monitor.py` — per-property SLA emails  
- `backend/services/sla_watchdog.py` — `job_runs` + heartbeat incidents  
- `backend/services/incident_lifecycle_service.py` — lifecycle, dedupe, recovery emails  
- `backend/services/job_schedule_registry.py` — `max_delay_minutes` source of truth  
