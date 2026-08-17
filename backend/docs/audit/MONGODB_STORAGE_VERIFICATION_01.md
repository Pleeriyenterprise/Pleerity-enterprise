# MongoDB Storage Verification

**Audit ID:** `MONGODB-STORAGE-REMEDIATION-AND-LIFECYCLE-GOVERNANCE-01`  
**Date:** 2026-08-06  
**Post-execute verification**

---

## Results

| Criterion | Status | Evidence |
|-----------|--------|----------|
| MongoDB writes restored | **PASS** | Staging insert/delete probe `_storage_remediation_probes` succeeded |
| Flex below limit with margin | **PASS** | Cluster data+index **~2.51 GB / 5 GB (46.8%)** after purge + empty-collection drop |
| Only approved telemetry removed | **PASS** | Tier-1: `job_runs`, `operational_evidence_events`, `operational_evidence_executions` on staging |
| Production authoritative intact | **PASS** | clients=6, requirements=110, audit_logs=5375, score_ledger=1033 unchanged pattern; prod job_runs/OEP **not** deleted |
| Staging usable | **PASS** | Writes OK; protected staging `audit_logs` retained (191429); clients retained (43) |
| Storage reduced | **PASS** | Staging data+idx **3.45 GB → ~0.60 GB**; cluster **~5.37 GB effective → ~2.51 GB** |
| No authority drift | **PASS** | Cleanup refused production; DB allowlist enforced |
| No lifecycle / audit regression (staging protecteds) | **PASS** | `audit_logs` / compliance graph / consent / score ledger not in delete set |
| Idle growth fix deployed in code | **PASS** | `job_run_idle_persist` + instrumented path |
| Monitoring deployed in code | **PASS** | `mongo_storage_capacity_monitor` + Health/Control Centre surfaces |
| Retention purge available | **PASS** | Flagged off by default (`MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED`) |
| Separate clusters migrated | **N/A** | Roadmap only (by design) |

---

## Counts after remediation

| DB / collection | After |
|-----------------|-------|
| staging `job_runs` | 0 (collection recreated empty with minimal indexes) |
| staging OEP events/executions | 0 (recreated empty) |
| staging `audit_logs` | 191,429 (preserved) |
| production `job_runs` | 611,973 (untouched) |
| production OEP events | 495,814 (untouched) |
| cluster usage | **46.8%** of 5 GB |

---

## Notes

1. Document delete alone left large empty-collection **index** footprints; dropping empty staging Tier-1 collections reclaimed ~1.3 GB index bytes.  
2. Production still holds ~1.92 GB — enable retention + idle-skip deploy to stop re-growth.  
3. Deploy code changes (idle-skip, monitor, 503 handler, retention) to Render staging/production for prevention to take effect at runtime.  
4. Full index set for OEP returns on next `database.connect()` `_create_indexes`.

---

## Success criteria assessment

**Met for incident unblock + governance scaffolding.** Remaining soak: deploy runtime fixes; enable retention purge on staging after approval; plan Atlas cluster split.
