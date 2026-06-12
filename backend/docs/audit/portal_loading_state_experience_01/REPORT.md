# PORTAL-LOADING-STATE-EXPERIENCE-01

**Classification (code):** `PORTAL_LOADING_STATE_EXPERIENCE_CONVERGED`  
**Classification (ops):** `VERIFIED_OPERATIONALLY`  
**Post-deploy run:** `20260612T083925Z`  
**Commit:** `3e974609`

## Summary

Improved perceived performance and trust on **Today**, **Command Center**, and **Dashboard** by replacing anonymous skeleton-only waits with staged, accessible loading communication. No API, caching, scoring, or business-logic changes.

## Deploy proof

- API deploy match: **true** (`3e974609442cbbdcdc2b2658861137f2680ff240`)
- Frontend bundle markers: **true** (`main.f195af99.js` — `portal_loading_started`, `today-page-loading`, `command-center-primary-loading`)
- Deploy ready: **true**

## Browser verification (staging)

| Page | Desktop | Mobile 390px | Notes |
|------|---------|--------------|-------|
| Today | pass | pass | Staged copy, `role=status`, `aria-live=polite` |
| Command Center | pass | pass | Primary staged loader; ready state after delay |
| Dashboard | pass | pass | KPI preview cards + 3 card loaders; no horizontal overflow |

Screenshots: `screenshots/` (6 captures).

## Analytics

- `portal_loading_started`: 6 events captured
- `portal_loading_completed`: 4 events captured (CC + Dashboard desktop/mobile)
- `portal_loading_duration_ms`: recorded (e.g. 13770ms CC, 28666ms Dashboard)

## Regression

14/14 frontend tests passed (see `regression_runtime.json`).

## Performance impact

**Neutral** on actual latency; improved perceived wait (see `performance_impact.json`).

## Files changed (implementation)

### New

| File | Purpose |
|------|---------|
| `frontend/src/components/loading/PortalLoadingState.jsx` | Shared staged loading panel |
| `frontend/src/components/loading/PortalCardLoading.jsx` | In-card loading message |
| `frontend/src/components/loading/PortalEmptyNotice.jsx` | Distinct empty-state helper |
| `frontend/src/components/loading/portalLoadingStageModels.js` | Reusable stage definitions |
| `frontend/src/components/loading/usePortalLoadingStages.js` | Timer-based stage progression |
| `frontend/src/components/loading/usePortalLoadingTelemetry.js` | Analytics hook |
| `frontend/src/components/loading/*.test.js` | Unit tests |

### Updated

| File | Change |
|------|--------|
| `frontend/src/pages/ClientTasksPage.js` | Staged Today loader; ErrorBanner + Retry |
| `frontend/src/pages/ClientCommandCenterPage.js` | Staged primary loader; PortalCardLoading for secondary |
| `frontend/src/pages/ClientDashboard.js` | Staged initial load + KPI card loaders; valueInsights tri-state |
| `frontend/src/pages/ClientCommandCenterPage.test.js` | Analytics mock |
| `backend/services/product_analytics_service.py` | Allowlist `portal_loading_*` events |
