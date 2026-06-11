# DASHBOARD-TODAY-COMMANDCENTER-PERFORMANCE-PHASE1

**Run:** `20260611T182100Z`  
**Staging account:** nancy@yopmail.com  
**API:** https://pleerity-enterprise.onrender.com/api  
**Before baseline:** `dashboard_today_commandcenter_load_performance_audit_01/`

## Executive summary

Phase 1 removes over-fetching and aligns initial mounts with the existing **`projection=primary`** command-center contract. **Command Center first paint drops from ~34s to ~1.6s** on staging (primary bundle). **Today** and **Dashboard** critical paths remain dominated by **`GET /today/items`** and **`GET /client/value-insights`** respectively — expected until a portal snapshot (Phase 2 proposal only; not implemented here).

Total dashboard mount **request count: 25 → 17**; **aggregate request time: ~266s → ~215s** (−51s network work on Nancy cold pass).

---

## Code changes (frontend only)

| Area | Change |
|------|--------|
| **Today** (`ClientTasksPage.js`) | `getCommandCenterPrimary` in gate; single `fetchOperational(complianceSummary)` for property dropdown + jurisdiction (removed duplicate direct fetch) |
| **Command Center** (`ClientCommandCenterPage.js`) | Initial mount uses `commandCenterPrimary` + deferred `commandCenterSecondary` (matches refresh path) |
| **Dashboard** (`ClientDashboard.js`) | Primary CC; single requirements/full via operational cache; portfolio summary via compliance-summary cache; removed dead `compliance-score/trend` + `score/timeline`; risk KPI from `protection-snapshot` only; work-orders limit **200** (was 500/422) |
| **Layout** (`ClientPortalLayout.jsx`) | CRN reads `peekOperationalCache(dashboard)` before fetching |

Business logic, authorities, scoring, entitlements, and projection semantics preserved. **No portal snapshot endpoint.**

---

## Before vs after (staging API simulation)

### Request counts

| Page | Before | After | Δ |
|------|--------|-------|---|
| Today | 5 | 4 | −1 (duplicate compliance-summary) |
| Command Center | 4 | 5 | +1 (explicit secondary projection; non-blocking) |
| Dashboard | 25 | 17 | −8 |

### Payload size (cold pass totals)

| Page | Before | After | Δ |
|------|--------|-------|---|
| Today | 848 KB | 797 KB | −51 KB |
| Command Center | 1.62 MB | 1.61 MB | −14 KB |
| Dashboard | 1.51 MB | 1.90 MB | +391 KB* |

\*Dashboard payload rose because **work-orders limit=200 succeeds** (923 KB) vs **limit=500 returned 422** in the audit baseline. Risk-signals list (~362 KB) removed.

### Critical path (longest gate / parallel max)

| Page | Before | After | Δ |
|------|--------|-------|---|
| Today | 40.2s (`/today/items`) | 39.9s (`/today/items`) | ~0s |
| Command Center | 33.9s (legacy CC bundle) | **1.6s** (`projection=primary`) | **−32.3s** |
| Dashboard (KPI row complete) | 55.8s (`value-insights`) | 56.0s (`value-insights`) | ~0s |

### Perceived first contentful data

| Page | Before | After | Notes |
|------|--------|-------|-------|
| Today | ~40s (Promise.all gate) | ~40s | Still gated on unified tasks |
| Command Center | ~34s | **~1.6s** | Urgent slice + headline compliance |
| Dashboard skeleton | ~5.2s (`/client/dashboard`) | ~5.1s | Unchanged |
| Dashboard KPI row | ~56s | ~56s | Still waits on slow parallel burst |

---

## Removed / deduped requests (Dashboard)

| Endpoint | Reason |
|----------|--------|
| `GET /client/compliance-score/trend?days=30` | Never rendered |
| `GET /client/score/timeline?days=90` | Never rendered (`netChange30` unused) |
| `GET /client/requirements` (list projection) | Superseded by single `requirements/full` |
| Duplicate `GET /client/dashboard` (layout) | Operational cache peek |
| `GET /client/maintenance/risk-signals?limit=500` | Scalar count from `protection-snapshot` |
| `GET /client/predictive-insights?limit=100` | Same (KPI only) |

Legacy **`GET /client/command-center?include_secondary=false`** replaced by **`?projection=primary`** on all three pages (~10s faster per call on Nancy; smaller payload ~47 KB → ~15 KB).

---

## Snapshot architecture — deferred

Phase 1 timings confirm that **eliminating duplicate projections and list hydration** yields large Command Center gains and meaningful dashboard network reduction, but **does not** fix Today or Dashboard dominant paths (`today/items`, `value-insights`, compliance-score family).

**Proposal (Phase 2, not implemented):** portal home snapshot (C1 from audit) after these numbers are accepted in production deploy.

---

## Artifacts

| File | Purpose |
|------|---------|
| `api_timing_runtime.json` | After-pass timings + comparison embed |
| `comparison.json` | Before/after summary table |
| `../tmp_dashboard_today_cc_performance_phase1_01.py` | Re-run script |

---

## Regression watchlist

- Deploy frontend to staging and confirm browser waterfall matches simulated after-pass.
- Investigate `/client/value-insights` ~56s (962 B body — server-side blocking).
- Consider moving command-center off Today `Promise.all` gate (audit P2) in a follow-up if false-empty disclosure can be server-side.
- Warm-cache repeat navigation (45s operational_surface_cache TTL) — re-measure after deploy.
