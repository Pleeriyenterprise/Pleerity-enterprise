# MongoDB Storage Remediation — Execution Report

**Audit ID:** `MONGODB-STORAGE-REMEDIATION-AND-LIFECYCLE-GOVERNANCE-01`  
**Date:** 2026-08-06  
**Mode:** Controlled implementation

---

## Phase 1 — Environment authority

| Check | Result |
|-------|--------|
| Render production `DB_NAME` | `pleerity_production` (`render.production.yaml`) |
| Render staging `DB_NAME` | `pleerity_staging` (`render.staging.yaml`) |
| Runtime connect (`database.py`) | Requires `MONGO_URL` + `DB_NAME` (no silent swap) |
| Deployment guard | Staging refuses production DB; production refuses staging DB (`deployment_environment_guard.py`) |
| Prod ↔ staging DB crossover on live services | **Not found** |

**CLI risk (non-blocking):** many `tmp_*` / certification scripts default `DB_NAME` to `pleerity_staging` when unset. That inflates **staging** on the shared cluster; it does not write production when blueprints are correct.

**Verdict:** `PASS_WITH_CLI_HARDENING` — cleanup **allowed**. Blocking drift (prod service → staging DB or staging → production DB) **not** present.

---

## Phase 2 — Staging Tier-1 cleanup

**Utility:** `backend/scripts/mongodb_controlled_cleanup_01.py`

| Control | Implemented |
|---------|-------------|
| Default dry-run | Yes |
| Refuse `pleerity_production` | Yes |
| Allowlist `pleerity_staging` only | Yes |
| Execute token | `YES_I_APPROVED_STAGING_PURGE` |
| Batch + checkpoint | Yes (`docs/audit/mongodb_cleanup_checkpoints/`) |
| Protected blocklist | `audit_logs`, compliance graph, clients, requirements, consent, score ledger, GridFS, etc. |

### Dry-run (Tier 1)

| Collection | Match docs | Reclaim est. (data) | Index est. |
|------------|------------|---------------------|------------|
| `job_runs` | ~1.94M | ~1.08 GB | ~322 MB |
| `operational_evidence_events` | ~544k | ~999 MB | ~360 MB |
| `operational_evidence_executions` | ~150k | ~75 MB | ~18 MB |
| **Total estimate** | | **~2.16 GB** | **~700 MB** |

Evidence: `mongodb_cleanup_execution_01.json` (updated after execute).

### Execute

Tier-1 execute completed against **staging only** with explicit confirmation flag.

| Metric | Value |
|--------|-------|
| Documents deleted | **2,631,804** |
| Collections | `job_runs`, `operational_evidence_events`, `operational_evidence_executions` |
| Empty collection drop (index reclaim) | Same three collections after count==0 |
| Cluster usage after | **~46.8%** of 5 GB (~2.51 GB) |
| Production touched | **false** |

Evidence: `mongodb_cleanup_execution_01.json`, checkpoints under `mongodb_cleanup_checkpoints/`.

---

## Phase 3–6 — Governance shipped in code

| Capability | Location |
|------------|----------|
| Idle high-frequency job_run skip | `services/job_run_idle_persist.py` + `job_runner.run_instrumented` |
| Retention purge (flagged) | `services/operational_retention_purge.py` via OEP maintenance |
| Storage monitor + incidents | `services/mongo_storage_monitor.py` job every 15m |
| Health / Control Centre surface | `routes/observability.py` `mongo_storage`; Control Centre alerts |
| Capacity → HTTP 503 | `utils/mongo_capacity_errors.py` + global exception handler |

**Staging job_runs root cause (fixed at source):** 83% from high-frequency idle polls — `compliance_recalc_worker` (15s), `risk_signal_regen_worker` (30s), `notification_retry_worker` (1m), `scheduler_heartbeat`, `scheduled_admin_communications`. Idle schedule ticks no longer insert `job_runs`/OEP; poll heartbeats keep System Health fresh.

**Retention flag (off by default until ops enable):** `MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED=1`

---

## Production guarantees

- No production authoritative collections modified  
- No production Tier-1 delete  
- No index drops  
- No API contract changes  
- No lifecycle authority changes  

---

## Follow-ups

1. Confirm Atlas Flex usage &lt; ~70% after execute completes + WiredTiger compaction lag.  
2. Enable retention purge on staging first, then production.  
3. Separate Atlas clusters (roadmap in `MONGODB_ENVIRONMENT_ISOLATION_01.md`).  
4. Harden CLI scripts to refuse unset `DB_NAME` (optional follow-on).
