# Phase 2C — Commercial Entitlement Expiry Closeout

**Programme:** `PHASE-2C-COMMERCIAL-ENTITLEMENT-EXPIRY-CLOSEOUT-01`  
**Classification:** `EXPIRY_GOVERNANCE_DRIFT`  
**Verified at:** 2026-06-01T16:08:23Z  
**Implementation commits:** `93745c7c`, `d21b15bc`, `3316e8d8`

## Summary

Deploy continuity and API regression gates **pass** on staging (`rent_ops_verify_01_7bbe8f8b`). Expiry transition, access recalculation after expiry, review-due proof, and expiry audit/metrics **cannot be verified** without staging `MONGO_URL` to insert a backdated active governance row. Classification remains below `VERIFIED_OPERATIONALLY` until that proof runs.

## Part 1 — Deploy continuity (PASS)

| Check | Result |
|-------|--------|
| `/api/version` includes `3316e8d8` | `3316e8d8742fbc70a347a14f4d5c7689906ef6a6` |
| `commercial_entitlement_expiry` in `JOB_RUNNERS` | Yes (invalid-job probe) |
| APScheduler 04:10 UTC | Listed; `next_run`: `2026-06-02T04:10:00+00:00` |
| Manual job run | 200; `expired_count: 0` (no backdated row) |
| Indexes on staging cluster | Blocked without `MONGO_URL` |

Artifact: `deploy_continuity_expiry.json`

## Part 2 — Staging DB fixture (BLOCKED)

`STAGING_MONGO_URL` / `.staging_mongo_url` not available in closeout runner. Fixture insert requires direct staging Mongo access (same cluster as Render).

Artifact: `expiry_fixture_runtime.json`

## Parts 3–6 — Expiry job, access, review, audit (BLOCKED)

Dependent on Part 2. Staging API job executes but cannot expire without past-expiry active row.

Artifacts: `expiry_job_runtime.json`, `access_recalculation_runtime.json`, `review_governance_runtime.json`, `audit_metrics_expiry_runtime.json`

## Part 7 — Regression (PASS)

Re-ran via staging API: grace, duplicate block (suspend path), sponsored access, impact preview customer copy, Stripe lightweight wording.

Pytest: `test_commercial_entitlement_governance.py` 13 passed; `test_commercial_entitlement_expiry_integration.py` skipped (no local Mongo).

Artifact: `regression_expiry_runtime.json`

## Reach VERIFIED_OPERATIONALLY

1. Create gitignored `backend/docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url` with staging Atlas URI (or export `STAGING_MONGO_URL`).
2. Run:
   ```bash
   cd backend
   python scripts/staging_commercial_entitlement_expiry_closeout.py --client-id rent_ops_verify_01_7bbe8f8b
   ```
3. Confirm gates: `expired_count >= 1`, row `active` → `expired`, `commercial_expired` audit, access recalc, idempotent second job, review-due for sponsored fixture.

## Harness

`backend/scripts/staging_commercial_entitlement_expiry_closeout.py`
