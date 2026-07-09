# Phase 4 Implementation Summary

**Programme:** OPERATIONAL-EVIDENCE-TIMELINE-IMPLEMENTATION-02 — Phase 4  
**Date:** 2026-06-02

## Scheduled maintenance job

| Component | Detail |
|---|---|
| Job ID | `operational_evidence_maintenance_job` |
| Schedule | Daily 03:30 UTC |
| Runner | `run_operational_evidence_maintenance_job` → `maintenance_service.run_operational_evidence_maintenance` |
| Work | Bounded 1-day backfill (200/source) + warm retention batch (2000 events) |

## Retention tiers (append-only)

- **Service:** `services/operational_evidence/retention_service.py`
- Events older than **90 days** marked `retention.tier: warm` with `retention.archived_at`
- Default reads exclude warm/cold tiers (`include_archived=true` to include)
- **API:** `GET /retention/stats`, `POST /retention/apply`
- Index: `(retention.tier, occurred_at)`

## Portfolio view

- **Service:** `services/operational_evidence/portfolio_service.py`
- **API:** `GET /views/portfolio/{client_id}` — category breakdown, high-impact events, properties touched, timeline + story
- **UI:** Client ID filter on timeline page activates portfolio summary card

## Annotation UI

- **Component:** `OperationalEvidenceAnnotations.js`
- Embedded on timeline event detail sidebar and `OperationalEvidencePanel`
- Uses existing `POST/GET /annotations` API (separate from runtime evidence)

## Intelligence & maintenance UI

- Timeline sidebar: 24h intelligence shortcuts (failures, retry loops)
- Retention stats + manual **Run 7-day backfill** button
- **Include archived** filter checkbox

## Tests

- `test_retention_filter_excludes_warm_by_default`
- `test_apply_warm_retention_tier`
- `test_maintenance_job_orchestrates_backfill_and_retention`

## Next (Phase 5 — if planned)

- Cold archive collection migration
- Performance acceptance script (50-event / 200-chain latency)
- Production promotion gate after staging validation
