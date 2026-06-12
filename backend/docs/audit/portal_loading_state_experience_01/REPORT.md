# PORTAL-LOADING-STATE-EXPERIENCE-01

**Classification (code):** `PORTAL_LOADING_STATE_EXPERIENCE_CONVERGED`  
**Classification (ops):** `PARTIAL` — staging browser proof pending

## Summary

Improved perceived performance and trust on **Today**, **Command Center**, and **Dashboard** by replacing anonymous skeleton-only waits with staged, accessible loading communication. No API, caching, scoring, or business-logic changes.

## Files changed

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

## Regression

14/14 frontend tests passed (see `regression_runtime.json`).

## Performance impact

**Neutral** on actual latency; improved perceived wait (see `performance_impact.json`).

## Screenshots

Pending post-deploy capture:

- `screenshots/desktop_today_loading.png`
- `screenshots/desktop_command_center_loading.png`
- `screenshots/desktop_dashboard_loading.png`
- `screenshots/mobile_390px_dashboard_loading.png`

## Next step

Deploy and run staging browser verification to reach `VERIFIED_OPERATIONALLY`.
