# Capacity Frontend UX Validation

**Audit ID:** `MONGODB-PREVENTION-DEPLOYMENT-AND-RUNTIME-RECOVERY-01`

## Backend (deployed)

Payload: HTTP **503** + `code=DATABASE_CAPACITY_EXCEEDED` (unit + payload shape). Does not classify auth failures as capacity.

## Frontend (committed on `develop`)

| Change | Location |
|--------|----------|
| `DATABASE_CAPACITY_USER_MESSAGE` | `capabilityRuntime.js` |
| `isDatabaseCapacityError` | `capabilityRuntime.js` |
| Login mapping | `AuthContext.js` — capacity ≠ wrong password |
| Jest | `p0StagingRuntimeStabilization.test.js` — **7 passed** |

User-facing copy:

> The service is temporarily unavailable because of a system capacity issue. Please try again shortly.

## Live FE deploy

Staging alias `pleerity-enterprise-9jjg.vercel.app` bundle probe recorded in results JSON (`live_vercel_bundle_confirmed`). Treat as a condition if the probe does not find the capacity string on the currently aliased deployment.
