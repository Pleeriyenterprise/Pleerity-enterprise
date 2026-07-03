# ILP-4 Capability Enforcement — Phase 2C-1 Report

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01 (Phase 2C-1)  
**Branch:** `develop`  
**Verdict:** `ILP_04_PHASE_2C_1_COMPLETE`  
**Date:** 2026-07-03

---

## Summary

Phase 2C-1 migrates `properties.py`, `portfolio.py`, and the `client.py` property/requirement/score subset to `client_require_capability()` / `assert_client_capability()`, extending the Runtime Contract with nine new capability rows including **`CAP_REQ_MARK_N_A`** (Option A — distinct from `CAP_REQ_RESOLVE`).

Phase 2B Wave 1 and Phase 2A pilot routes remain in place. Phase 2C-2 (ledger, Today, Command Centre, maintenance, etc.) is **not** started.

---

## 2C-1 scope delivered

| Module | Status | Notes |
|--------|--------|-------|
| `routes/properties.py` | **Full** | 9 endpoints; archive via `CAP_PROP_ARCHIVE` assert on patch |
| `routes/portfolio.py` | **Full** | 6 endpoints; router-level `client_route_guard` removed |
| `routes/client.py` | **Subset** | Score, activity, requirements, mark-not-applicable; duplicate score-trend handlers removed |

**Governance decision:** All mark-not-applicable routes use `CAP_REQ_MARK_N_A` (not aliased to `CAP_REQ_RESOLVE`).

**Explicitly not migrated (2C-2+):** ledger, dashboard, command-centre, priority-actions, evidence-pack, tenant/branding, analytics, billing, jobs, sessions, frontend, admin routes.

---

## Runtime contract extensions (schema unchanged)

New `_BASE_CAPABILITY_MATRIX` rows:

- `CAP_PROP_ARCHIVE`, `CAP_PROP_DELETE` (matrix row; no delete route)
- `CAP_PROP_IMPORT` → plan key `document_upload_bulk_zip`
- `CAP_REQ_MARK_N_A` — **Option A; not aliased to `CAP_REQ_RESOLVE`**
- `CAP_REQ_COMPLETE` (matrix row; no route in 2C-1)
- `CAP_SCORE_EXPLAIN`, `CAP_SCORE_SNAPSHOT` → plan key `compliance_score`
- `CAP_SCORE_TREND` → plan key `score_trending`
- `CAP_COMPLIANCE_ACTIVITY` → plan key `compliance_dashboard`

Portal ceilings updated for `BILLING_RECOVERY`, `READ_ONLY`, `SUSPENDED`.

---

## Enforcement patterns

| Pattern | Usage |
|---------|--------|
| `client_require_capability(CAP, action)` | Route dependency — returns `user` when allowed |
| `assert_client_capability(user, CAP, action)` | Conditional gates (archive, NOT_REQUIRED applicability) |
| Denied | HTTP 403 `capability_denied` governed payload |
| Plan limits | `plan_registry.enforce_property_limit()` retained (plan cap, not `enforce_feature`) |

---

## Objectives proved

| Objective | Evidence |
|-----------|----------|
| Module-complete migration (properties, portfolio) | No `enforce_feature` / `client_route_guard` in those modules |
| Client subset only | Non-2C-1 `client.py` routes unchanged |
| `CAP_REQ_MARK_N_A` distinct | Mark-not-applicable on properties + client; pilot tests updated |
| Lifecycle matrix regression | `test_account_capability_enforcement_wave2c1.py` |
| Prior phases regression | pilot + wave1 suites |

---

## Test suites (regression)

| Suite | Path |
|-------|------|
| ILP-1 resolver | `test_account_lifecycle_state_resolver.py` |
| ILP-2 runtime contract | `test_account_lifecycle_runtime_contract.py` |
| ILP-4 Phase 0–1 | `test_account_capability_enforcement.py` |
| ILP-4 Phase 2A pilot | `test_account_capability_enforcement_pilot.py` |
| ILP-4 Phase 2B Wave 1 | `test_account_capability_enforcement_wave1.py` |
| ILP-4 Phase 2C-1 | `test_account_capability_enforcement_wave2c1.py` |

Lifecycle states parametrized in 2C-1 tests: `ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `READ_ONLY`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `UNKNOWN`.

---

## Deferred to 2C-2+

- `client.py` evidence-pack routes (`CAP_REPORT_AUDIT_PACK`)
- Ledger, Today, Command Centre, maintenance, rent ops, approvals, integrations, assistant, profile, billing, jobs, sessions
- Frontend `useCapability()` consumption
- `client_route_guard` capability integration for remaining routes
- Remaining catalog-gap capability resolver rows

---

## Prior phases

- Phase 0–1: `ILP_04_PHASE_01_COMPLETE` — enforcement service, compatibility layer, diagnostics
- Phase 2A: `ILP_04_PHASE_2A_PILOT_COMPLETE` — 4 pilot endpoints
- Phase 2B Wave 1: `ILP_04_PHASE_2B_WAVE_1_COMPLETE` — evidence, reports, documents

See `ACCOUNT_LIFECYCLE_ILP_04_EVIDENCE.json` for machine-readable route inventory.
