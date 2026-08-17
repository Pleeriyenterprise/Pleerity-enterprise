# MongoDB Storage Monitoring

**Audit ID:** `MONGODB-STORAGE-REMEDIATION-AND-LIFECYCLE-GOVERNANCE-01`  
**Date:** 2026-08-06

---

## Implementation

| Piece | Detail |
|-------|--------|
| Service | `services/mongo_storage_monitor.py` |
| Scheduler | `mongo_storage_capacity_monitor` every 15 minutes |
| Metric | Sum of `dbStats.dataSize + indexSize` across scan DBs |
| Default limit | 5 GiB (`MONGO_STORAGE_LIMIT_BYTES`) |
| Scan DBs | Primary + sibling `pleerity_staging` / `pleerity_production` (override `MONGO_STORAGE_SCAN_DBS`) |

## Thresholds

| % of limit | Level | Action |
|------------|-------|--------|
| 60 | warning | Surface in Health / Control Centre |
| 75 | attention | Elevated alert |
| 85 | critical | Create/update operational incident |
| 90 | platform_alert | P1 incident; `writes_at_risk` |
| 95 | emergency | P0 incident |

## Surfaces

- System Health / observability: `mongo_storage` on `/api/admin/observability/health-summary`  
- Control Centre: `system.mongo_storage` + platform alert card  
- Incidents: source `mongo_storage_capacity`, fingerprint via `atlas_flex_storage_pressure`  
- HTTP: capacity errors → **503** `DATABASE_CAPACITY_EXCEEDED`

## Tests

`tests/test_mongo_storage_governance_01.py` — threshold classification, idle-skip helpers, capacity detector.
