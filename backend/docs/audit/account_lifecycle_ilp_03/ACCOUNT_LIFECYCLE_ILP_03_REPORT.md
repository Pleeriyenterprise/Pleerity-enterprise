# ILP-3 Portal Mode Consumption — Implementation Report

**Programme:** ILP-3-PORTAL-MODE-CONSUMPTION-01  
**Branch:** `develop`  
**Verdict:** `ILP_03_COMPLETE`  
**Date:** 2026-07-03

---

## Summary

ILP-3 implements governed Portal Mode consumption across the customer portal frontend. Presentation is driven exclusively by `GET /api/client/lifecycle-runtime`. Permissions, middleware, and API behaviour are unchanged.

---

## Deliverables

| Area | Path |
|------|------|
| Runtime provider | `frontend/src/contexts/LifecycleRuntimeContext.js` |
| Lifecycle shell | `frontend/src/components/lifecycle/LifecycleShell.jsx` |
| Diagnostics | `frontend/src/components/lifecycle/LifecycleRuntimeDiagnostics.jsx` |
| Nav policy utils | `frontend/src/utils/portalNavigationPolicy.js` |
| API client | `frontend/src/api/client.js` (`getLifecycleRuntime`) |
| Layout integration | `frontend/src/components/ClientPortalLayout.jsx` |
| App wiring | `frontend/src/App.js` |
| Backend doc | `backend/docs/PORTAL_MODE_CONSUMPTION.md` |
| Frontend doc | `frontend/docs/LIFECYCLE_RUNTIME_CONSUMPTION.md` |

---

## Provider architecture

- Single fetch on client session load
- Refetch on visibility when `polling_policy.enabled`
- Exposes `portalMode`, `customerExperience`, `navigationPolicy`, version metadata
- Governed fallback when API unavailable (no crash)

---

## Page migration

All listed customer-facing pages consume Portal Mode presentation via shell, banner, or `PortalPageShell`. No migrated page infers lifecycle from `subscription_status` for presentation (Billing uses runtime `customer_experience` first).

---

## Regression proof

- No changes to `middleware/__init__.py`
- No changes to `ProtectedRoute.js` auth logic
- No changes to `hasFeature()` / `FEATURE_MATRIX`
- No backend API permission changes
- No session invalidation

---

## Deferred enforcement

Capability enforcement, API guards, and `hasFeature()` replacement remain ILP-4.

---

## ILP-4 readiness

Portal Mode and capability grants are available in runtime contract. ILP-4 can enforce `capabilities` map without frontend presentation redesign.
