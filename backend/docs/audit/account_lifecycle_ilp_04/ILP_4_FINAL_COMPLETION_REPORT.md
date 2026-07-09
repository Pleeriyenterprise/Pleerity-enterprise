# ILP-4 Final Completion Report

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-COMPLETION-02 + ILP-4-CLOSEOUT-VALIDATION-01  
**Branch:** `develop`  
**Executed:** 2026-07-05 – 2026-07-06 UTC  
**Verdict:** **PRODUCTION READY** (ILP-4 customer capability authority)

---

## Executive summary

Runtime Contract capabilities are the sole customer permission authority in the portal application. The customer React tree no longer mounts `EntitlementsProvider`. Route gates, navigation visibility, page actions, and upgrade discoverability consume `LifecycleRuntimeContext` capability evaluation.

Legacy entitlement hooks (`useEntitlements`, `hasFeature`, plan-gated route wrappers) are removed from all customer-facing pages and shared presentation components.

Closeout validation (ILP-4-CLOSEOUT-VALIDATION-01) resolved five frontend regression failures (test drift only), re-ran full backend and frontend regressions, and validated lifecycle journeys for all six customer portal modes.

---

## Migration summary

### New capability modules

| Module | Capabilities |
|--------|-------------|
| `integrationCapabilityAccess.js` | `CAP_INTEGRATION_WEBHOOKS`, `CAP_INTEGRATION_READ_API`, `CAP_EXPORT_API` |
| `tenantCapabilityAccess.js` | `CAP_TENANT_PORTAL`, `CAP_TENANT_MANAGE`, `CAP_TENANT_MESSAGES` |
| `calendarCapabilityAccess.js` | `CAP_CALENDAR_VIEW` |
| `assistantCapabilityAccess.js` | `CAP_AI_ASSISTANT` |
| `usePortfolioUsageContext.js` | Display-only portfolio counts via `/client/entitlements/context` (backend gated by `CAP_DASHBOARD_VIEW`) |

### Pages migrated (this milestone)

| Page | Authority change |
|------|------------------|
| `ComplianceScorePage` | Export gated on `CAP_REPORT_GENERATE_PDF` / `CAP_REPORT_GENERATE_CSV` |
| `IntegrationsPage` | Webhooks/read-API gated on integration capabilities |
| `ClientRentOperationsPage` | Route gate via `CAP_OPS_RENT` |
| `ClientTenantComplianceDeliveryPage` | `CAP_TENANT_MANAGE` + `CAP_REPORT_GENERATE_PDF` |
| `CalendarPage` | View/export on `CAP_CALENDAR_VIEW` |
| `AssistantPage` | Read/write on `CAP_AI_ASSISTANT` |
| `IntakePage` | Portfolio hint via `usePortfolioUsageContext` (not entitlements) |

### Shared infrastructure

| Component | Disposition |
|-----------|-------------|
| `EntitlementsContext.js` | **INTENTIONALLY_RETAINED** — deprecated; not mounted in customer App |
| `EntitlementProtectedRoute.js` | **COMPATIBILITY_WRAPPER** — re-exports `AccountCapabilityProtectedRoute` |
| `UpgradePrompt.js` | **MIGRATED** — `CapabilityGate`; portfolio hints via `usePortfolioUsageContext` |
| `PlanRestrictedActionModal.jsx` | **MIGRATED** — static presentation metadata only |
| `PlanGatingDiscoverability.jsx` | **MIGRATED** — presentation-only (no entitlement checks) |
| `CapabilityProtectedRoute.js` | **MIGRATED** — unified `ROUTE_CAPABILITY` + `AccountCapabilityProtectedRoute` |
| `App.js` | **MIGRATED** — `EntitlementsProvider` removed; routes use capability gates |

### Navigation

- Calendar secondary nav: `calendarGate` + `showCalendar` from `CAP_CALENDAR_VIEW`
- Assistant header button: `showAssistant` from `CAP_AI_ASSISTANT` read
- Existing ops/report/billing/tenant gates unchanged (capability-backed)

---

## Legacy authority inventory

| Symbol / pattern | Classification | Notes |
|------------------|----------------|-------|
| `useEntitlements()` | REMOVED (customer) | Only in deprecated `EntitlementsContext.js` + test mocks |
| `hasFeature()` | REMOVED (customer) | Test utility mappers only |
| `EntitlementProtectedRoute` | COMPATIBILITY_WRAPPER | Delegates to Runtime Contract |
| `EntitlementsProvider` | REMOVED (customer App) | Not mounted |
| `FEATURE_MATRIX` (BillingPage) | INTENTIONALLY_RETAINED | Plan comparison copy only; billing actions use `CAP_BILLING_*` |
| `UpgradePrompt` / `PlanGatingDiscoverability` | MIGRATED | Presentation-only discoverability |
| `subscription_status` (admin pages) | ADMIN_ONLY | AdminDashboard, AdminBilling, etc. |
| `client_orders` routes | PUBLIC_PAGE / no CAP | Backend matrix notes no catalog CAP yet |

---

## Closeout validation (ILP-4-CLOSEOUT-VALIDATION-01)

### Frontend regression failures — resolved

Five failures from the completion milestone were classified and fixed (no product defects):

| Suite | Failures | Classification | Resolution |
|-------|----------|----------------|------------|
| `scoreFreshnessUi.test.js` | 3 | **TEST_DRIFT** | Assertions aligned to current `scoreFreshnessUi.js` copy |
| `PropertyDetailPage.missingRequirementsActions.test.js` | 1 | **TEST_DRIFT** | Upload CTA URL now includes `&focus=upload` |
| `PropertyCreatePage.test.js` | 1 | **TEST_DRIFT** | Added `usePropertyCapabilities` mock with `canCreateProperty: true` |

### Full frontend regression (closeout)

| Metric | Result |
|--------|--------|
| Suites | 210 passed |
| Tests | **964 passed / 0 failed** |
| Duration | ~52 s |
| Log | `frontend/tmp_ilp4_closeout_frontend_regression.log` |

### Full backend regression (closeout)

| Metric | Result |
|--------|--------|
| Tests | **916 passed / 0 failed** (903 prior checkpoint + 13 closeout lifecycle tests) |
| Duration | 4:04:30 |
| Exit code | 0 |
| Log | `backend/tmp_ilp4_closeout_regression_full.log` |

Suites include all ILP-4 capability enforcement modules, billing client, backend completion, billing recovery operations, and closeout lifecycle journey validation.

### Lifecycle E2E journey validation

Six portal lifecycle states validated on backend (Runtime Contract) and frontend (grant fixtures):

| Lifecycle | Portal mode | Backend | Frontend | Billing recovery | Ops write denied |
|-----------|-------------|---------|----------|------------------|------------------|
| ACTIVE | FULL_ACCESS | ✓ | ✓ | n/a | n/a |
| READ_ONLY | READ_ONLY | ✓ | ✓ | ✓ | ✓ (create denied) |
| CANCELLED_IMMEDIATE | BILLING_RECOVERY | ✓ | ✓ | ✓ | ✓ |
| SUBSCRIPTION_EXPIRED | BILLING_RECOVERY | ✓ | ✓ | ✓ | n/a |
| SUSPENDED | SUSPENDED | ✓ | ✓ | n/a | ✓ |
| ARCHIVED | ARCHIVED | ✓ | ✓ | ✓ (billing denied) | ✓ |

**Test artefacts:**

- `backend/tests/test_ilp4_closeout_lifecycle_journey_validation.py` — 13 passed
- `frontend/src/pages/ilp4Closeout.lifecycleJourney.test.js` — 12 passed (included in full regression)

**Verified behaviours:**

- Billing recovery (`CAP_BILLING_VIEW` read, `CAP_BILLING_CHECKOUT` write) remains available on CANCELLED_IMMEDIATE, SUBSCRIPTION_EXPIRED, and READ_ONLY
- Cancelled accounts deny ops write (`CAP_OPS_MAINTENANCE`) while retaining billing read — no 403 storm pattern (billing endpoints allowed, ops endpoints denied by contract)
- SUSPENDED and ARCHIVED deny customer surfaces as expected

### Authority alignment verification

| Check | Result |
|-------|--------|
| Customer pages use `useEntitlements` / `hasFeature` for permissions | **None** (grep + `ilp4Completion.capability.test.js`) |
| Runtime Contract sole customer permission authority | **Confirmed** |
| `EntitlementsProvider` mounted in customer App | **Removed** |
| Backend / frontend capability matrix drift | **None introduced** |
| Billing recovery after cancellation | **Confirmed** (closeout lifecycle tests) |
| ErrorBoundary / 403 storm after cancellation | **Not observed** — contract grants billing read/write; denies ops only |

---

## Regression summary (prior milestones)

### Targeted capability suites (ILP-4)

- **165+ tests passed** across capability, runtime, navigation, and migrated page suites
- `CI=true npm run build` — **PASS**

---

## Final readiness verdict

| Criterion | Status |
|-----------|--------|
| Runtime Contract single customer authority | ✓ |
| No customer permission via legacy entitlements | ✓ |
| Navigation capability-driven | ✓ |
| Portal Mode presentation-only | ✓ |
| Backend/frontend matrix alignment | ✓ |
| Unexplained legacy permission code | ✓ (documented inventory) |
| Full frontend regression | ✓ **964/964** |
| Full backend regression | ✓ **916/916** |
| Lifecycle journey validation (6 states) | ✓ |
| Billing recovery after cancellation | ✓ |
| Closeout evidence recorded | ✓ |

**ILP-4 customer-facing capability enforcement: PRODUCTION READY on `develop`.**
