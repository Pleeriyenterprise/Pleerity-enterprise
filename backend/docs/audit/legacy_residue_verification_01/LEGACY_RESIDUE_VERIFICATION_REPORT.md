# Legacy Residue Verification 01 — Final Legacy Authority Verification

**Programme:** LEGACY-RESIDUE-VERIFICATION-01  
**Branch:** `develop`  
**Executed:** 2026-07-06 UTC  

## Verdict

**`LEGACY_RESIDUE_REMOVED`**

Two production legacy authority consumers were found and remediated. All remaining legacy symbols are classified as compatibility, diagnostic, test-only, billing-sync facts, or admin display — none perform customer-facing permission decisions outside the governed authority stack.

---

## Objective

Prove that ILP-1 through ILP-10 migration is complete and that no unexplained customer-facing legacy authority remains.

---

## Authority chain (verified)

Customer permission flows through:

```
Lifecycle Resolver (account_lifecycle_state_resolver)
  ↓
Runtime Contract (account_lifecycle_runtime_contract)
  ↓
Capability Authority (account_capability_enforcement)
  ↓
Session Authority (account_session_runtime_service / middleware.session_runtime)
  ↓
Lifecycle Response Authority (account_lifecycle_response_authority)
  ↓
Customer Communication Authority (account_customer_communication_authority)
  ↓
Lifecycle Event Authority (account_lifecycle_event_authority)
  ↓
Frontend Runtime Contract (LifecycleRuntimeContext)
```

No customer HTTP route applies `require_feature`, `enforce_feature`, or `hasFeature` for permission.

---

## Repository scan summary

| Area | Result |
|------|--------|
| Customer frontend pages | No `useEntitlements`, `EntitlementsContext`, or `hasFeature()` permission usage |
| Customer routes | No `require_feature` / `enforce_feature` imports |
| Route guard | Uses `resolve_runtime_contract_for_client(emit_events=False)` |
| Portal mode | Presentation/navigation only via Runtime Contract |
| BillingPage | No `/client/entitlements` (PLATFORM-CONVERGENCE-CLEANUP-01) |
| Obsolete modules | `plan_gating.py`, `feature_entitlement.py` absent |

---

## Production legacy consumers found and fixed

### 1. Branding resolver white-label gate

**Before:** `branding_resolver_service.resolve_branding()` called `plan_registry.enforce_feature(client_id, "white_label_reports")` — legacy plan/subscription gating for PDFs, emails, and reports.

**After:** `CapabilityEnforcementService.evaluate(client_id, "CAP_BRANDING_WHITE_LABEL", "read")` — aligned with branding HTTP routes.

### 2. Renewal reminder background suppression

**Before:** `jobs.process_subscription_lifecycle_and_reminders()` skipped clients when `billing.entitlement_status` was not `ENABLED` — direct entitlement-based job suppression.

**After:** Uses `gate_client_background_job(client_id, "renewal_reminders")` and `"subscription_lifecycle"` — Background Authority canonical path.

---

## Remaining compatibility layers (intentional, non-blocking)

| Layer | Classification | Production use | Notes |
|-------|----------------|----------------|-------|
| `EntitlementsContext.js` | OBSOLETE | No (not in App) | Test mocks only |
| `GET /client/entitlements` | COMPATIBILITY_ONLY | API exists | CAP_PROFILE_VIEW gated; no frontend prod consumer |
| `GET /client/entitlements/context` | COMPATIBILITY_ONLY | Display hints | CAP_DASHBOARD_VIEW gated |
| `GET /client/plan-features` | COMPATIBILITY_ONLY | Presentation | `is_active` field uses plan registry; not route permission |
| `middleware/feature_gating.py` | OBSOLETE | No routes | Governance test retention |
| `plan_registry.enforce_feature` | COMPATIBILITY_ONLY | Definition only | No production callers after fix |
| `capability_compatibility.py` | COMPATIBILITY_ONLY | Template mapping | Delegates to CapabilityEnforcementService |
| `compare_runtime_with_legacy` | DIAGNOSTIC_ONLY | `/lifecycle-runtime/diagnostic` | Drift comparison |
| Admin pages `subscription_status` | Admin display | Yes | Outside customer platform |
| Stripe webhook `entitlement_status` writes | Billing sync | Yes | Resolver input facts, not permission |

Full itemised inventory: `LEGACY_RESIDUE_INVENTORY.json`.

---

## Frontend verification

- All customer pages gate actions via `useLifecycleRuntime().capabilityAllowed` or domain helpers (`useBillingCapabilities`, `accountCapabilityAccess`, etc.).
- Navigation visibility uses Runtime Contract `navigationPolicy` from portal mode (presentation).
- No component mixes Runtime Contract permissions with legacy entitlements for gating.
- `UpgradePrompt` uses capability route map + optional display-only usage context.

---

## Backend verification

- Customer routes use `client_require_capability` / `assert_client_capability`.
- Guard coarse lifecycle block uses Runtime Contract `lifecycle_state` + Response Authority denials.
- Background jobs use `account_background_runtime_authority` for per-client suppression.
- Notification sends use Communication Authority + capability compatibility for template feature keys.
- No hand-built unstructured lifecycle 403 payloads on guarded routes (Response Authority).

---

## Targeted tests

```
pytest tests/test_legacy_residue_verification.py tests/test_branding_resolver.py \
  tests/test_platform_convergence.py tests/test_account_background_runtime_authority.py -q
→ 39 passed
```

---

## Related programmes

- ILP-10 Platform Convergence
- PLATFORM-CONVERGENCE-CLEANUP-01 (BillingPage entitlements removal)
- P0 Staging Runtime Stabilization

---

## Conclusion

Customer-facing permission authority is fully converged on the Runtime Contract stack. Residual legacy symbols are documented, classified, and inactive for customer permission decisions.
