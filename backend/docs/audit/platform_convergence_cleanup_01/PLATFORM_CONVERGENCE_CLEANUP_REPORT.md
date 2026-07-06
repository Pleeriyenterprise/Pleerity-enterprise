# Platform Convergence Cleanup 01 — BillingPage Legacy Entitlement Removal

**Programme:** PLATFORM-CONVERGENCE-CLEANUP-01  
**Branch:** `develop`  
**Executed:** 2026-07-06 UTC  

## Verdict

**`BILLING_LEGACY_DEPENDENCY_REMOVED`**

---

## Objective

Remove the remaining deprecated `BillingPage` dependency on `GET /api/client/entitlements` and align customer-facing billing with the ILP-10 platform convergence model: Runtime Contract capabilities for actions, billing APIs for subscription state, and static plan metadata for comparison display.

---

## Problem (pre-fix)

`BillingPage.js` called `/client/entitlements` on mount, after checkout return, on usage refresh, and after subscription cancel. This:

- Conflicted with ILP-10 (customer pages must not depend on legacy entitlement endpoints)
- Contributed to P0 staging failures (“Failed to load plan information”) when entitlements returned 403
- Mixed authoritative entitlement feature overrides into plan comparison UI

Permissions were already migrated to `useBillingCapabilities()`; entitlements were only used for plan code, property cap, and feature comparison display.

---

## Changes

| Area | Change |
|------|--------|
| `BillingPage.js` | Removed `fetchEntitlements`, `entitlements` state, all `/client/entitlements` calls |
| `BillingPage.js` | `currentPlan` derived from `GET /billing/status` → `current_plan_code` |
| `BillingPage.js` | Loading lifecycle consolidated into `fetchBillingStatus` (no separate entitlements fetch) |
| `billingPlanPresentation.js` | New module: static `BILLING_PLAN_FEATURE_MATRIX` + display helpers (matches `plan_registry.py`) |
| Plan banner copy | “features enabled (your account)” → “plan features included” (presentation-only matrix) |
| Property cap display | `planPropertyLimitForDisplay()` from billing status or plan catalog |

**Unchanged (per scope):**

- Stripe / billing backend logic
- Runtime Contract schema
- `billingCapabilityAccess.js` permission authority (`CAP_BILLING_*`, `CAP_SUB_*`)
- Billing recovery journeys (lifecycle grants unchanged)
- Billing UI layout and recovery banners

---

## Authority model (post-fix)

| Concern | Source |
|---------|--------|
| View billing / invoices / payment methods | Runtime Contract `CAP_BILLING_*` |
| Checkout / manage / cancel subscription | Runtime Contract `CAP_BILLING_CHECKOUT`, `CAP_SUB_*` |
| Current plan, renewal, usage | `GET /billing/status` |
| Plan catalog pricing | `GET /billing/plans` |
| Feature comparison matrix | Static `billingPlanPresentation.js` (non-authoritative) |
| Recovery UX | `LifecycleRuntimeContext` → `customerExperience` |

**Not used:** `EntitlementsContext`, `hasFeature`, feature keys, `subscription_status`, `entitlement_status`, `/client/entitlements`.

---

## Error handling

- Removed entitlements fetch that surfaced “Failed to load plan information” toast on 403
- Billing status errors continue to use `isCapabilityDeniedApiError` / `getCapabilityDeniedMessage`
- No new retry loops introduced; refresh paths call single billing status fetch

---

## Targeted tests

```
npm test -- --testPathPattern="BillingPage.capability|billingCapabilityAccess|billingPlanPresentation" --watchAll=false
→ BillingPage.capability.test.js PASS
→ billingCapabilityAccess.test.js PASS
→ billingPlanPresentation.test.js PASS
```

---

## Acceptance checklist

| Criterion | Status |
|-----------|--------|
| BillingPage no longer calls `/api/client/entitlements` | ✓ |
| No billing permission decision uses legacy entitlement data | ✓ |
| Billing recovery journeys preserved (capability fixtures unchanged) | ✓ |
| No React object-rendering changes introduced | ✓ |
| No retry storm from entitlements removal | ✓ |
| Targeted tests pass | ✓ |

---

## Related programmes

- ILP-10 Platform Convergence (deferred BillingPage entitlements call noted in P0 audit)
- P0 Staging Runtime Stabilization (entitlements 403 loop root cause partially addressed here)
