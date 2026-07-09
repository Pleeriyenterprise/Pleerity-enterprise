# Staging Validation Report

**Generated:** 2026-07-07T20:43:15Z  
**Status:** PENDING DEPLOY — backend fix must be deployed to Render staging before live re-validation.

## Pre-fix evidence

`PHASE_2_STAGING_SMOKE_75787532.json` recorded `GET /client/maintenance/issues` → 403 `CAP_OPS_MAINTENANCE` DENY for Professional pilot account while lifecycle ACTIVE.

## Post-fix expectation

After deploy from `develop`:

| Plan tier | Account probe | Expected |
|-----------|---------------|----------|
| Solo | ACTIVE | Maintenance/contractors DENY; core compliance ALLOW |
| Portfolio | ACTIVE | Maintenance/predictive ALLOW; contractors DENY |
| Professional | ACTIVE | Maintenance, issues, contractors, predictive ALLOW |

Re-run `tmp_p0_convergence_staging_smoke_75787532.py` or maintenance API probe after deploy.
