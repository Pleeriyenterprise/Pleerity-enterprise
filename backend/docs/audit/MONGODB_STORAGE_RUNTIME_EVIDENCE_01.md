# MongoDB Storage — Runtime Evidence Pack

**Audit ID:** `MONGODB-STORAGE-PREVENTION-VALIDATION-01`  
**Date:** 2026-08-06  
**Source:** `mongodb_storage_validation_results_01.json` + live Mongo probes

---

## Cluster storage (now)

| Metric | Value |
|--------|-------|
| Combined data+index | **2,510,658,520 B (~2.51 GB)** |
| Flex limit | 5 GiB |
| Utilisation | **46.76%** |

| Database | dataSize | indexSize |
|----------|----------|-----------|
| `pleerity_production` | 1,415,545,165 | 499,683,328 |
| `pleerity_staging` | 445,524,619 | 149,905,408 |

---

## Collection snapshots

### Staging

| Collection | Count |
|------------|------:|
| `job_runs` | 0 |
| `operational_evidence_events` | 0 |
| `operational_evidence_executions` | 0 |
| `job_poll_heartbeats` | 0 |
| `audit_logs` | 191,429 |
| `clients` | 43 |
| `score_ledger_events` | 13,283 |

### Production (read-only sample)

| Collection | Count |
|------------|------:|
| `job_runs` | 611,973 |
| `operational_evidence_events` | 495,814 |
| `operational_evidence_executions` | 245,147 |
| `audit_logs` | 5,375 |
| `clients` | 6 |
| `score_ledger_events` | 1,033 |

Production recent `job_runs` sample timestamps end at **2026-07-27** (pre-dating this validation day) — consistent with prolonged write/scheduler disruption after the Flex incident.

---

## Scheduler liveness (staging)

| Probe | Result |
|-------|--------|
| `scheduler_heartbeat.last_heartbeat_at` | `2026-07-16T17:39:33.087764+00:00` |
| After 130s wait | **Unchanged** |
| `job_runs` during window | remained 0 |

**Conclusion:** Staging background scheduler is **not advancing**. Idle/active prevention cannot be runtime-proven until heartbeat resumes under remediated code.

---

## Growth window (90s)

| Metric | Δ |
|--------|--:|
| `job_runs` | 0 |
| OEP events | 0 |
| OEP executions | 0 |
| poll heartbeats | 0 |

Interpreted as **scheduler quiet**, not as proof of idle-skip (deploy absent + heartbeat stale).

---

## Unit / local runtime proofs

- Governance unit tests: **4 passed** (`test_mongo_storage_governance_01.py`)
- Idle-skip contract: idle schedule skips; heartbeat skips; manual/non-idle persist
- Capacity TestClient: **HTTP 503** + `DATABASE_CAPACITY_EXCEEDED`
- Cleanup against `pleerity_production`: **REFUSED** (exit 1)

---

## API responses captured

- `GET /api/version` → staging SHA `072b78f3…`
- `GET /api/health` → `healthy` (see observability validation for conflict with stale heartbeat)
