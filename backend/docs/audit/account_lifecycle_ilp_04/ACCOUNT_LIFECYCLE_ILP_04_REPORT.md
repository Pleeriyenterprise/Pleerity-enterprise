# ILP-4 Capability Enforcement — Phase 2C-2 Report

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01 (Phase 2C-2)  
**Branch:** `develop`  
**Verdict:** `ILP_04_PHASE_2C_2_COMPLETE`  
**Date:** 2026-07-03

---

## Summary

Phase 2C-2 migrates the `client.py` dashboard, command centre, today/task, and ledger route subset to `client_require_capability()` / `assert_client_capability()`, extending the Runtime Contract with `CAP_LEDGER_VIEW` and `CAP_LEDGER_EXPORT`.

Prior phases (2A pilot, 2B Wave 1, 2C-1) remain in place. Phase 2C-3 (evidence-pack) and ops modules are **not** started.

---

## 2C-2 scope delivered

| Area | Endpoints | Primary capabilities |
|------|-----------|---------------------|
| Dashboard | 2 | `CAP_DASHBOARD_VIEW` (+ conditional `CAP_SCORE_VIEW`) |
| Command centre | 2 | `CAP_CMD_CTR_VIEW` |
| Today / tasks | 8 | `CAP_TODAY_VIEW`, `CAP_TODAY_ACT` |
| Ledger | 2 | `CAP_LEDGER_VIEW`, `CAP_LEDGER_EXPORT` |

**Total:** 14 routes migrated in `routes/client.py`.

**Explicitly not migrated:** evidence-pack, analytics, activity-since, tenant/branding, maintenance, rent ops, approvals, integrations, assistant, profile, billing, jobs, sessions, frontend.

---

## Runtime contract extensions (schema unchanged)

- `CAP_LEDGER_VIEW` — lifecycle matrix row (read in billing recovery / read-only)
- `CAP_LEDGER_EXPORT` → plan key `reports_csv`
- Plan keys wired for 2C-2 consumers: `CAP_DASHBOARD_VIEW`, `CAP_CMD_CTR_VIEW` → `compliance_dashboard`

Portal ceilings updated for `BILLING_RECOVERY`, `READ_ONLY`, `SUSPENDED`.

Runtime resolver count: **49** capabilities (47 after 2C-1 + 2 ledger caps).

---

## Test suites (regression)

| Suite | Path | Result |
|-------|------|--------|
| ILP-4 Phase 2C-2 | `test_account_capability_enforcement_wave2c2.py` | 61 lifecycle matrix tests |
| ILP-4 Phase 2C-1 | `test_account_capability_enforcement_wave2c1.py` | regression |
| ILP-4 Phase 2B Wave 1 | `test_account_capability_enforcement_wave1.py` | regression |
| ILP-4 Phase 2A pilot | `test_account_capability_enforcement_pilot.py` | regression |

Lifecycle states: `ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `READ_ONLY`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `UNKNOWN`.

---

## Deferred to 2C-3+

- `client.py` evidence-pack routes (`CAP_REPORT_AUDIT_PACK`)
- Analytics, tenant/branding, maintenance, rent ops, approvals, integrations, assistant, profile
- Frontend `useCapability()` consumption

---

## Prior phases

- Phase 2C-1: `ILP_04_PHASE_2C_1_COMPLETE` — properties, portfolio, score/requirement subset
- Phase 2B Wave 1: `ILP_04_PHASE_2B_WAVE_1_COMPLETE` — evidence, reports, documents
- Phase 2A: `ILP_04_PHASE_2A_PILOT_COMPLETE` — 4 pilot endpoints

See `ACCOUNT_LIFECYCLE_ILP_04_EVIDENCE.json` for machine-readable route inventory.
