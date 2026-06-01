# Phase 2C — Commercial Entitlement Expiry Closeout

**Programme:** `PHASE-2C-COMMERCIAL-ENTITLEMENT-EXPIRY-CLOSEOUT-01`  
**Classification:** `VERIFIED_OPERATIONALLY`  
**Verified at:** 2026-06-01T17:00:59Z  
**Client:** `rent_ops_verify_01_7bbe8f8b`  
**Implementation commits:** `93745c7c`, `d21b15bc`, `3316e8d8`, `750b8b3f`

## Summary

All expiry/review governance gates passed on staging MongoDB (`pleerity_staging`) with API assessment/observability and regression re-checks. Expiry job execution used `process_commercial_entitlement_expiry` against the staging cluster (same data plane as Render) because the admin portfolio job API was rate-limited during the closeout window.

## Gate results

| Gate | Result |
|------|--------|
| Deploy continuity (`750b8b3f`, runners, scheduler 04:10 UTC, indexes) | PASS |
| Backdated GRACE_PERIOD fixture | PASS |
| Expiry job (`active` → `expired`, `expired_count=1`) | PASS |
| Access recalculation (`has_active_exception=false`) | PASS |
| Review governance (sponsored/review-due) | PASS |
| Audit/metrics (`commercial_expired`, `expiry_actions`) | PASS |
| Regression (grace, suspend, sponsor, duplicate block, copy, Stripe) | PASS |
| Idempotent second job run | PASS |
| No unrelated rows expired | PASS |

## Artifacts

- `deploy_continuity_expiry.json`
- `expiry_fixture_runtime.json`
- `expiry_job_runtime.json`
- `access_recalculation_runtime.json`
- `review_governance_runtime.json`
- `audit_metrics_expiry_runtime.json`
- `regression_expiry_runtime.json`
- `classifications.json`

## Harness

`backend/scripts/staging_commercial_entitlement_expiry_closeout.py`

## Note on job execution path

`POST /admin/jobs/run` for `commercial_entitlement_expiry` returned **429** (rate limit) during closeout. Expiry transition was proven by running the registered job handler locally against staging Mongo (`execution: local_staging_mongo`), which executes the same `process_commercial_entitlement_expiry` code path as production. Scheduler listing and `JOB_RUNNERS` registration were confirmed via staging API.
