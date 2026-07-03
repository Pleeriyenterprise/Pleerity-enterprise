# ILP-4 Capability Enforcement — Phase 0–1 Report

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01 (Phase 0–1 only)  
**Branch:** `develop`  
**Verdict:** `ILP_04_PHASE_01_COMPLETE`  
**Date:** 2026-07-03

---

## Summary

Phase 0–1 introduces the governed capability enforcement service and compatibility layer. `CAP_*` grants from the Runtime Contract can be evaluated for read/write actions. **No production route, middleware, or frontend behaviour changed.**

---

## Deliverables

| Area | Path |
|------|------|
| Enforcement service | `backend/services/account_capability_enforcement.py` |
| Compatibility mapping | `backend/services/capability_compatibility.py` |
| `require_capability()` helper | `backend/middleware/capability_gating.py` (not wired) |
| Diagnostics API | `backend/routes/client_capability_enforcement.py` |
| Verification matrix scaffold | `backend/docs/ACCOUNT_CAPABILITY_ENFORCEMENT_MATRIX.md` |
| Drift diagnostic | `backend/scripts/account_capability_enforcement_drift_diagnostic.py` |
| Unit tests | `backend/tests/test_account_capability_enforcement.py` (20 tests) |

---

## Capability inventory

| Scope | Count |
|-------|------:|
| Catalog (`ACCOUNT_CAPABILITY_CATALOG.md`) | 104 |
| Runtime resolver (`_BASE_CAPABILITY_MATRIX`) | 33 |
| Missing from runtime (deferred) | 71 |
| Feature_key compatibility mappings | 31 |

`READ` contract grant is enforced as **READ_ONLY** semantics (view permitted, mutation blocked with governed reason).

---

## Regression proof

| Area | Changed? |
|------|----------|
| `middleware/__init__.py` `client_route_guard` | **No** |
| Route `enforce_feature` call sites | **No** |
| `plan_registry.enforce_feature` implementation | **No** |
| Frontend | **No** |
| Runtime Contract schema | **No** |
| Lifecycle resolver | **No** |
| Portal Mode (ILP-3) | **No** |
| Billing / Stripe / jobs | **No** |

**Tests:** 82 passing (ILP-1 + ILP-2 + ILP-4 Phase 0–1).

---

## Deferred to Phase 2+

- Middleware `client_route_guard` capability migration
- Per-endpoint `require_capability()` wiring
- Frontend `useCapability()` / guards
- `hasFeature()` internal delegation
- Resolver matrix extension for 71 catalog-gap capabilities

---

## ILP-5 / Phase 2 readiness

`CapabilityEnforcementService`, `CapabilityDecision`, compatibility mappings, and diagnostics are ready. API route migration can proceed without redesigning the enforcement model.
