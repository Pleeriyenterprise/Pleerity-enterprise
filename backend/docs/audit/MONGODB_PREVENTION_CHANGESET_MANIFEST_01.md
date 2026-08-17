# MongoDB Prevention — Change-set Manifest

**Audit ID:** `MONGODB-PREVENTION-DEPLOYMENT-AND-RUNTIME-RECOVERY-01`  
**Date:** 2026-08-06  
**Verdict on isolation:** Changes can be isolated — **not** `BLOCKED_BY_CHANGESET_CONTAMINATION`

| File | Classification | Reason | Include |
|------|----------------|--------|---------|
| `backend/services/job_run_idle_persist.py` | implementation | Idle-skip for high-freq polls | yes |
| `backend/services/mongo_storage_monitor.py` | implementation | Storage capacity monitor | yes |
| `backend/services/operational_retention_purge.py` | implementation | Flagged retention purge | yes |
| `backend/services/scheduler_health_authority.py` | implementation | Heartbeat freshness authority | yes |
| `backend/utils/mongo_capacity_errors.py` | implementation | Capacity → 503 mapping | yes |
| `backend/job_runner.py` | implementation | Idle-skip + monitor job wiring | yes |
| `backend/server.py` | implementation | Scheduler job + health truth + 503 | yes |
| `backend/routes/observability.py` | implementation | mongo_storage + scheduler_health | yes |
| `backend/services/control_centre_service.py` | implementation | Storage alert surface | yes |
| `backend/services/operational_evidence/maintenance_service.py` | implementation | Retention purge hook | yes |
| `frontend/src/utils/capabilityRuntime.js` | implementation | Capacity UX mapping | yes |
| `frontend/src/contexts/AuthContext.js` | implementation | Login capacity message | yes |
| `backend/tests/test_mongo_storage_governance_01.py` | test | Unit coverage | yes |
| `frontend/src/utils/p0StagingRuntimeStabilization.test.js` | test | Capacity UX unit | yes |
| `backend/scripts/mongodb_controlled_cleanup_01.py` | operational script | Staging cleanup utility | yes |
| `backend/scripts/mongodb_storage_prevention_validation_01.py` | validation harness | Prevention validation | yes |
| `backend/scripts/mongodb_scheduler_heartbeat_probe_01.py` | validation harness | Fixed heartbeat probe | yes |
| `backend/docs/audit/MONGODB_*.md` (storage/prevention series) | audit evidence | Remediation docs | yes |
| `backend/docs/audit/mongodb_*.json` (inventory/validation/cleanup) | audit evidence | Machine evidence | yes |
| `backend/tmp_*` | temporary | Local probes | **no** |
| gallery PDFs / unrelated audits | unrelated | Not this programme | **no** |
| `backend/services/integrations/orchestration/` | unrelated | WP-001 | **no** |
| secrets / `.env` | unsafe | Never | **no** |
