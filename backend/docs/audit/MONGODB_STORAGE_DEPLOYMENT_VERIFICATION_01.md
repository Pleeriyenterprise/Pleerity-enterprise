# MongoDB Storage — Deployment Verification

**Audit ID:** `MONGODB-STORAGE-PREVENTION-VALIDATION-01` / Phase 1  
**Date:** 2026-08-06

---

## Running staging

| Field | Value |
|-------|-------|
| Backend URL | `https://pleerity-enterprise.onrender.com` |
| `/api/version` | `{"commit_sha":"072b78f38f0a0e3f0bfc3b78fd9c955043d3fa68","environment":"staging"}` |
| `/api/health` | `healthy` / readiness `ready` |
| Local `git HEAD` | `072b78f38f0a0e3f0bfc3b78fd9c955043d3fa68` |
| HEAD subject | `feat(zoho): CRM concurrency hardening for Phase C certification` |

Staging SHA **matches** local HEAD, but remediation files are **not in that commit**.

---

## Remediation file tracking

| Path | In git? |
|------|---------|
| `backend/services/job_run_idle_persist.py` | **No (untracked)** |
| `backend/services/mongo_storage_monitor.py` | **No** |
| `backend/services/operational_retention_purge.py` | **No** |
| `backend/utils/mongo_capacity_errors.py` | **No** |
| `backend/scripts/mongodb_controlled_cleanup_01.py` | **No** |
| `backend/tests/test_mongo_storage_governance_01.py` | **No** |

Related modified-but-uncommitted wiring also expected in working tree: `job_runner.py`, `server.py`, `routes/observability.py`, `services/control_centre_service.py`, OEP `maintenance_service.py`.

---

## Feature flags / env (expected vs live)

| Flag / env | Expected after deploy | Live staging proven? |
|------------|----------------------|----------------------|
| `JOB_RUN_SKIP_IDLE_HIGH_FREQUENCY` | default on (`1`) | **No** — code absent |
| `MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED` | off until soak | **No** |
| `MONGO_STORAGE_LIMIT_BYTES` | optional override | **No** |
| `DB_NAME` | `pleerity_staging` | Blueprint + health env staging |
| Monitor job `mongo_storage_capacity_monitor` | every 15m | **Not registered on deployed SHA** |

Frontend build SHA / Vercel deploy timestamp: not required to disprove backend remediation deploy; backend version endpoint is authoritative for API safeguards.

---

## Verdict

**`FAIL_NOT_DEPLOYED`**

The running application is **not** executing remediated prevention code. Re-validation must wait until remediation is committed and Render staging shows a new `commit_sha`.
