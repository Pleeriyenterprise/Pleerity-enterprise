# PRELAUNCH-PERFORMANCE-BACKEND-REMEDIATION-02

## Summary

Landlord portal pages were blocked by **actual API latency**, not shell rendering. Progressive UI was in place; operational endpoints still took 20–97s for primary content. This programme removes duplicate unified-task rebuilds, shrinks Today payloads, defers heavy dashboard/document work, adds safe caching with disclosure, and deduplicates frontend fetches.

**Classification:** `IMPLEMENTED_PENDING_DEPLOY_VERIFY` (see `classifications.json`).

## Root cause by page

| Page | Slowest API | Root cause |
|------|-------------|------------|
| Today | `GET /today/items` | Full unified tasks (120) + enrichment + 1.6MB flat `items[]` duplicating `tasks` |
| Command Centre | `GET /client/command-center` | **Double** `get_unified_tasks_for_client` via digest + full; then sequential compliance/gap/HIUA |
| Dashboard | `GET /client/dashboard` + satellites | `calculate_compliance_score` on dashboard; duplicate command-center + today unified calls |
| Properties | (was OK) | Regression when other pages called dashboard for property list |
| Property detail | `GET /client/properties` | Full portfolio fetch to resolve one property |
| Requirements | `GET /client/dashboard` + requirements + documents | Heavy dashboard only for properties |
| Documents | `GET /documents` | Linkage/visibility batch on 100 docs |

## Backend / API fixes

- **`command_center_service`:** One unified build; `digest_from_unified_tasks_full`; `asyncio.gather` for unified + compliance + risks; gap/HIUA parallel inside compliance.
- **`unified_tasks_service`:** `operational_surface_cache` (45s TTL, freshness metadata); `digest_from_unified_tasks_full`; digest uses `raw_limit=60` when standalone.
- **`/today/items`:** `raw_limit=60`; parallel rent + unified; `include_flat_items=false` default; slim task in flat list when enabled.
- **`/client/dashboard`:** `include_score_headline=false` default.
- **`/documents`:** `limit`, `projection=list` (skips linkage batch, flags deferred).
- **`today_projection_service`:** Missing `resolve_take_action_envelope` import fixed.
- **`database.py`:** Index `(client_id, uploaded_at desc)` on documents.

## Frontend fixes

- **Today:** Removed `getCommandCenter`; `fetchOperational` for today/requirements; jurisdiction from compliance-summary (deferred).
- **Command Centre / Documents / Requirements / Dashboard:** `fetchOperational` cache keys; Requirements uses `getProperties`; Documents uses `projection=list`.
- **Property detail:** Compliance-detail first for header + matrix.
- **Dashboard:** `include_score_headline=false`; deferred today fetch; cached command-center.

## Indexes

- `documents`: `{ client_id: 1, uploaded_at: -1 }`

## Before / after timings

### API (staging probe 2026-05-26, **pre-deploy**)

| Endpoint | Before (ms) | Probe (ms) | Notes |
|----------|-------------|------------|-------|
| Today | 29643 | 28168 | Fixes not live |
| Command Centre | 75197 | 74403 | Fixes not live |
| Dashboard | 24183 | 24067 | Query param accepted |
| Documents | 21753 | 22323 | list projection param accepted |

See `before_after_api_timings.json` for full matrix.

### Browser (baseline verify-01)

| Page | Shell | Primary |
|------|-------|---------|
| Today | 334ms | 3.1s |
| Command Centre | 580ms | **96.8s** |
| Dashboard | 218ms | 25s |

Post-deploy browser verification pending (`before_after_browser_timings.json`).

## Payload reductions (expected post-deploy)

- Today: **~1.6MB → <200KB** (no flat items; lower raw_limit).
- Command Centre: latency **~50%** from eliminating second unified rebuild + parallel compliance.
- Documents: modest bytes; larger win from skipping linkage batch CPU.

## Authority / coherence

All checks **PASS** — see `authority_regression_check.json`. No weakening of RBAC, score authority, or failure disclosure.

## Commit / push

Code changes committed in repo (see git log). Verification artifacts are **local** until `VERIFIED_OPERATIONALLY` after deploy.

## Watchlist

See `watchlist.md`.
