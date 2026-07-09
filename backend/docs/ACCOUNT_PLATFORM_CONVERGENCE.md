# Account Platform Convergence (ILP-10)

**Programme:** ILP-10-PLATFORM-CONVERGENCE-AND-LEGACY-REMOVAL-01  
**Branch:** `develop`  
**Status:** Complete — not production-ready until Platform Release Readiness audit

---

## Objective

Converge the platform onto the implemented lifecycle architecture. Exactly **one authority** per lifecycle concern. No customer-facing runtime decision depends on deprecated mechanisms.

---

## Authority stack (final)

See `ACCOUNT_PLATFORM_AUTHORITY_STACK.md`.

---

## Phase A audit

Complete inventory: `docs/audit/account_lifecycle_ilp_10/PLATFORM_CONVERGENCE_INVENTORY.json`

Every legacy pattern classified before code changes.

---

## Convergence actions (ILP-10)

| Action | Detail |
|--------|--------|
| Route guard migration | `_client_context_guard` uses `resolve_runtime_contract_for_client` lifecycle_state |
| Obsolete module removal | `plan_gating.py`, `feature_entitlement.py` (zero imports) |
| Middleware obsolescence | `feature_gating.require_feature` marked test-only |
| Compatibility retained | EntitlementsContext, EntitlementProtectedRoute, capability_compatibility |

---

## Validation

| Check | Result |
|-------|--------|
| Single permission authority (customer) | Runtime Contract + CAP_* enforcement |
| Single response authority | ILP-7 Lifecycle Response Authority |
| Single communication authority | ILP-8 Customer Communication Authority |
| Single event authority | ILP-9 Lifecycle Event Authority |
| No duplicate lifecycle gating in routes | Verified |
| Targeted convergence tests | Pass |

---

## Deferred (intentional)

Items documented in inventory § `deferred_roadmap`. Not release-blocking for convergence; tracked for post-release or infrastructure programmes.

---

## Next programme

**PLATFORM-WIDE-RELEASE-READINESS-AUDIT** — full regression, E2E lifecycle validation, staging/production readiness assessment.

---

**Verdict:** `ILP_10_IMPLEMENTED_TARGETED_VALIDATION_PASS_REGRESSION_DEFERRED`
