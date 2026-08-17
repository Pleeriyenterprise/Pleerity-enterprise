# MongoDB Storage Root Cause Report

**Audit ID:** `MONGODB-STORAGE-ROOT-CAUSE-AND-CONTROLLED-CLEANUP-01`  
**Date:** 2026-08-06  
**Mode:** Read-only investigation (no deletions, no Atlas/config/env changes, no production data touch)  
**Repo SHA (workspace):** `072b78f38f0a0e3f0bfc3b78fd9c955043d3fa68` (`develop`)

---

## Executive summary

The Atlas **Flex 5 GB data+index** limit was exhausted by the **combined** footprint of `pleerity_production` (~1.42 GB data, 916 indexes) and `pleerity_staging` (~2.60 GB data, 975 indexes) on a **shared cluster**. Staging is larger than production.

Primary growth drivers (production numbers from Atlas incident evidence):

| Collection | Docs (prod) | Data | Indexes | Nature |
|------------|-------------|------|---------|--------|
| `operational_evidence_events` | ~496k | ~886 MB | ~336 MB | Derived telemetry index (append-only; **never deleted**) |
| `job_runs` | ~612k | ~383 MB | ~111 MB | Operational run log (append-only; **no TTL**) |
| `operational_evidence_executions` | ~245k | ~123 MB | ~27 MB | Derived execution registry |

**Root cause (compound):**

1. Shared Flex cluster hosting both environments.  
2. High-frequency scheduler (~50+ instrumented jobs) writing `job_runs` forever.  
3. Each job run emits ≥2 Operational Evidence Platform (OEP) events (`JOB_RUN_STARTED` + finished), plus queue/notification/incident/score emitters and daily backfill.  
4. OEP “retention” only **tiers** events to `warm` after 90 days — **does not delete**.  
5. Very large index surface (`database.py` defines ~520 `create_index` calls; Atlas shows ~900+ indexes **per database**).  
6. Staging inflated by validation/certification workloads against the same cluster.

**Admin HTTP 500** is consistent with Mongo write failures when the cluster is at capacity (login paths that persist sessions/audit/security events cannot write).

---

## Final verdict

### SAFE_TO_PURGE_STAGING_SELECTIVELY

**With conditions:**

- Do **not** drop `pleerity_staging` wholesale until an inventory/export of any staging-only formal certification artefacts still living **only** in Mongo is completed (see `MONGODB_STAGING_CLEANUP_PLAN_01.md`).  
- Prefer first reclaim: aged `operational_evidence_*` + aged `job_runs` on **staging only**.  
- **Do not touch** `pleerity_production` in this incident response.  
- Separately plan production **retention going forward** (not emergency delete).

If product insists on full staging DB drop → escalate to **STAGING_REQUIRES_ARCHIVE_BEFORE_CLEANUP**.

Not chosen: `BLOCKED_BY_ENVIRONMENT_AUTHORITY_DRIFT` — `DB_NAME` correctly separates DBs when set; risk is shared **cluster**, not same-DB drift.

---

## 1. Environment authority

| Service (blueprint) | Branch | `DB_NAME` | `MONGO_URL` |
|---------------------|--------|-----------|-------------|
| `pleerity-api-staging` (`render.staging.yaml`) | `develop` | `pleerity_staging` | Dashboard secret → Atlas |
| `pleerity-api-production` (`render.production.yaml`) | `main` | `pleerity_production` | Dashboard secret → Atlas |

### Code paths

| Path | Behaviour |
|------|-----------|
| `database.py` `connect()` | **Requires** `MONGO_URL` and `DB_NAME` (KeyError if missing) |
| `server.py` module-level | Fallback `DB_NAME` default `compliance_vault_pro` if unset (pytest/legacy paths) — **not** `pleerity_*` |
| Many `tmp_*.py` / probes | Default `DB_NAME` → `pleerity_staging` when unset |
| CI/conftest | Uses test Mongo / safe defaults (not verified live here) |

### Can staging and production write the same database?

**Only if misconfigured** (same `DB_NAME` on both services, or script using production URI + wrong/missing `DB_NAME`). Correct Render blueprints use different `DB_NAME` values.

### Shared cluster risk (confirmed by incident)

Atlas Flex limit applies to **cluster** data+indexes. Two databases on one Flex instance **sum** toward 5 GB. Production alone (~1.42 GB) would not fill 5 GB; **staging + production + indexes** does.

### Local / CI / certification write risk

- Scripts with production `MONGO_URL` + default `pleerity_staging` inflate **staging**.  
- Scripts that hardcode `DB_NAME=pleerity_staging` while pointing at the shared Atlas URI write real hosted data.  
- Large certification/validation suites (Zoho CRM, CIE, OEP, lifecycle) on staging are a plausible major contributor to staging > production.

---

## 2. Growth root cause — detail

### 2.1 `job_runs`

| Factor | Evidence |
|--------|----------|
| Writer | `services/job_run_service.py` `start_job_run` → `insert_one` |
| Caller | `job_runner.run_instrumented` (scheduler + admin manual) |
| Frequency | Every scheduled/manual instrumented job; `JOB_RUNNERS` has **40+** entries; `server.py` registers many `scheduler.add_job` crons (some multi-daily) |
| Retention / TTL | **None** (`expireAfterSeconds` not found for `job_runs`) |
| Indexes | `job_name+created_at`, `job_name+started_at`, `status+created_at`, `created_at`, `correlation_id+created_at` |
| Idempotency | New ObjectId per run — **by design** one row per execution |
| Duplicate risk | Retries create **new** runs (correct for observability), increasing volume |

**Estimate:** If ~30–50 jobs fire daily × 2 environments × months of history → hundreds of thousands of rows matches ~612k production docs.

### 2.2 `operational_evidence_events`

| Factor | Evidence |
|--------|----------|
| Writer | `services/operational_evidence/emit_service.py` `emit_operational_evidence` → `insert_one` |
| Amplification | Each job: `emit_job_run_started` + `emit_job_run_finished` (`job_runner.py`); plus queue/notification/incident/score producers |
| Backfill | Daily `operational_evidence_maintenance_job` backfills from `job_runs`, `incidents`, `message_logs`, `score_ledger_events` |
| Idempotency (live emit) | New `uuid4()` `event_id` every emit — **no dedupe** on live path |
| Idempotency (backfill) | `_already_indexed(source_collection, source_id, event_type)` only in backfill |
| Retention | `retention_service.apply_warm_retention_tier` sets `retention.tier=warm` after **90 days** — **does not delete** |
| Indexes | **~20 indexes** on this collection alone (`database.py` 450–471) — index size ~336 MB vs data ~886 MB is consistent |

**Architecture claim (docs):** OEP is a **derived, non-authoritative** correlation index over `job_runs`, incidents, queues, etc. (`OPERATIONAL_EVIDENCE_PLATFORM_ARCHITECTURE.md`).

### 2.3 `operational_evidence_executions`

| Factor | Evidence |
|--------|----------|
| Writer | `_upsert_execution_summary` on every successful emit |
| Authority | Explicitly **non-authoritative** registry for story roots |
| Growth | One doc per `root_execution_id`; grows with job/API execution trees |

### 2.4 Index tax

`database.py` contains on the order of **~520** `create_index` invocations. Atlas reports **916 / 975 indexes** per DB. Flex counts indexes toward the 5 GB limit. OEP’s many compound indexes are a large share of reclaimable **index** bytes if events are purged.

### 2.5 What is *not* the primary cause

- Compliance evidence documents / requirements (authoritative) are not the top Atlas offenders listed.  
- Missing `DB_NAME` causing prod/staging merge is **not** evidenced when Render blueprints are correct.  
- OEP is working as designed (append-only index) — the defect is **unbounded retention on a shared Flex tier**.

---

## 3. Immediate incident response (approved order — plan only)

1. **Unblock writes** by reclaiming space on the shared cluster via **staging selective purge** of derived OEP + aged `job_runs` (after dry-run report).  
2. **Do not delete** production.  
3. Implement retention/TTL + storage alerts (prevention).  
4. Plan **separate Atlas projects/clusters** for staging vs production (or M10+ with headroom).  
5. Review index set for OEP (drop unused compounds after query audit).

---

## 4. Confirmation

No production data was modified. No deletions executed. No Atlas configuration changed. No environment variables changed. Cleanup remains **approval-gated**.
