# Platform Hygiene Cleanup 01

**Programme:** PLATFORM-HYGIENE-CLEANUP-01  
**Branch:** `develop`  
**Executed:** 2026-07-06 UTC  

## Verdict

**`PLATFORM_HYGIENE_COMPLETE_WITH_RETAINED_COMPATIBILITY`**

Genuinely dead frontend entitlement code removed. Intentional compatibility layers retained with documented justification. No customer behaviour changes.

---

## Objective

Final implementation hygiene pass after ILP convergence and Legacy Residue Verification — remove code with zero production purpose without touching intentional compatibility infrastructure.

---

## Removals (safe — zero production callers)

| Item | Location | Why safe |
|------|----------|----------|
| `EntitlementsContext.js` | `frontend/src/contexts/` | Not mounted in App; no production imports; only dead test mocks |
| `getEntitlements()` API wrapper | `frontend/src/api/client.js` | No frontend production callers after BillingPage cleanup |
| Dead `jest.mock('../contexts/EntitlementsContext')` blocks | 5 dashboard/command-centre test files | Components never imported EntitlementsContext |
| Obsolete `hasFeature` comment | `PlanGatingDiscoverability.jsx` | Updated to Runtime Contract wording |

---

## Intentionally retained (COMPATIBILITY_ONLY / DIAGNOSTIC_ONLY)

| Item | Reason |
|------|--------|
| `getEntitlementsContext()` + `usePortfolioUsageContext` | Active display-only portfolio usage; CAP_DASHBOARD_VIEW gated |
| `EntitlementProtectedRoute.js` | Thin alias to `AccountCapabilityProtectedRoute`; governance test contract |
| `GET /api/client/entitlements` (backend) | Compatibility API; CAP_PROFILE_VIEW gated; no frontend wrapper |
| `GET /api/client/plan-features` | Presentation metadata endpoint |
| `middleware/feature_gating.py` | OBSOLETE; governance regression tests |
| `plan_registry.enforce_feature` | Definition retained; tests and plan metadata |
| `compare_runtime_with_legacy` | Diagnostic endpoint only |
| Billing sync fields (`subscription_status`, etc.) | Lifecycle Resolver input facts |

---

## Validation

- No broken production imports
- No customer permission path changes
- No architectural changes
- Targeted tests pass
- Frontend production build succeeds

---

## Targeted tests

```
npm test -- --testPathPattern="platformHygieneCleanup|ilp10PlatformConvergence|ilp4Completion|BillingPage.capability" --watchAll=false
pytest tests/test_legacy_residue_verification.py -q
npm run build
```

---

## Readiness

Repository is **implementation-complete** for entry into the Platform-Wide Release Readiness Audit.
