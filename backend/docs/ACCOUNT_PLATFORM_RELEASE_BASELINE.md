# Account Platform Release Baseline

**Programme:** ILP-10-PLATFORM-CONVERGENCE-AND-LEGACY-REMOVAL-01  
**Baseline version:** `account_lifecycle_platform_v1`  
**Branch:** `develop`

---

## Baseline scope

This document defines the **converged platform architecture** after ILP-1 through ILP-10. It is the reference for the subsequent **Platform Release Readiness** programme.

---

## Implemented programmes

| ILP | Programme | Status |
|-----|-----------|--------|
| ILP-1 | Lifecycle State Resolver | ✓ |
| ILP-2 | Runtime Contract | ✓ |
| ILP-3 | Portal Mode Consumption | ✓ |
| ILP-4 | Capability Enforcement | ✓ |
| ILP-5 | Session Runtime Authority | ✓ |
| ILP-6 | Background Runtime Authority | ✓ |
| ILP-7 | Lifecycle Response Authority | ✓ |
| ILP-8 | Customer Communications & Reactivation | ✓ |
| ILP-9 | Lifecycle Events | ✓ |
| ILP-10 | Platform Convergence | ✓ |

---

## Architecture invariants

1. Customer permissions derive from Runtime Contract `capabilities` map only.
2. Customer lifecycle HTTP responses derive from Lifecycle Response Authority only.
3. Customer communication gating derives from Communication Authority only.
4. Lifecycle platform events derive from Lifecycle Event Authority only.
5. Route-level lifecycle blocks use Runtime Contract `lifecycle_state`.
6. Session refresh uses `runtime_version` / `session_version` from Session Runtime Authority.

---

## Removed from baseline

- `plan_gating.py`
- `feature_entitlement.py`
- Customer `canonical_entitlement_state` gate in `_client_context_guard`

---

## Known deferred items (not baseline blockers)

See `PLATFORM_CONVERGENCE_INVENTORY.json` § `deferred_roadmap`.

---

## Release Readiness prerequisites

Before production promotion:

| Prerequisite | Owner programme |
|--------------|-----------------|
| Full backend regression | Platform Release Readiness |
| Full frontend regression | Platform Release Readiness |
| E2E lifecycle journey validation | Platform Release Readiness |
| Staging verification | Platform Release Readiness |
| Operational / observability validation | Platform Release Readiness |
| Production readiness assessment | Platform Release Readiness |

---

## Evidence

- Convergence inventory: `audit/account_lifecycle_ilp_10/PLATFORM_CONVERGENCE_INVENTORY.json`
- ILP-10 report: `audit/account_lifecycle_ilp_10/ACCOUNT_LIFECYCLE_ILP_10_REPORT.md`
- Authority stack: `ACCOUNT_PLATFORM_AUTHORITY_STACK.md`

---

**Production ready:** No — pending Platform Release Readiness audit.
