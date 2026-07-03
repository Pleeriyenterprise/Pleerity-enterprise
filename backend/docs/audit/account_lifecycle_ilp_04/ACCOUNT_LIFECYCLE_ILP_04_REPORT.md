# ILP-4 Capability Enforcement — Progress Report

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01  
**Branch:** `develop`  
**Status:** ILP-4 in progress  
**Date:** 2026-07-03

---

## Latest milestone — evidence pack, analytics, activity-since

Migrated seven `client.py` routes to `client_require_capability()` / `assert_client_capability()`. Removed all `enforce_feature("audit_log_export")` checks from evidence-pack handlers.

| Area | Endpoints | Primary capabilities |
|------|-----------|---------------------|
| Analytics | 2 | `CAP_COMPLIANCE_ACTIVITY` (read/write) |
| Activity since | 2 | `CAP_COMPLIANCE_ACTIVITY` (read/write) |
| Evidence pack | 3 | `CAP_REPORT_AUDIT_PACK` (read/write) |

**Total this milestone:** 7 routes. **Cumulative migrated in `client.py`:** 37 endpoints on `CAP_*`.

**Not migrated:** tenant/branding, maintenance, rent ops, approvals, integrations, assistant, profile, billing, onboarding extras, entitlements, frontend.

---

## Test suites

| Suite | Path | Scope |
|-------|------|-------|
| Evidence pack + analytics | `test_account_capability_enforcement_evidence_pack_analytics.py` | 71 lifecycle matrix tests |
| Dashboard / today / ledger | `test_account_capability_enforcement_wave2c2.py` | regression |
| Properties / portfolio / score | `test_account_capability_enforcement_wave2c1.py` | regression |
| Evidence / reports / documents | `test_account_capability_enforcement_wave1.py` | regression |
| Pilot | `test_account_capability_enforcement_pilot.py` | regression |

Lifecycle states: `ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `READ_ONLY`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `UNKNOWN`.

---

## ILP-4 completion criteria (remaining)

- Backend customer APIs — ~35 unmigrated `client.py` handlers + standalone route modules
- Frontend Runtime Contract consumption — not started
- Full regression + staging validation — pending
- Final ILP-4 implementation report — pending programme completion

See `ACCOUNT_LIFECYCLE_ILP_04_EVIDENCE.json` for machine-readable route inventory.
