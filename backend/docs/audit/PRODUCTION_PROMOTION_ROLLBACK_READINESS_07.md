# Production promotion rollback readiness 07

**Programme:** `PRODUCTION-PROMOTION-EXECUTION-07`

Recorded **before** merge/deploy and still the restore targets.

```text
PRE_PROMOTION_MAIN_SHA = 89217062481b4eb858a8b530ec90c83de067a4be
PRE_PROMOTION_PRODUCTION_BACKEND_SHA = 89217062481b4eb858a8b530ec90c83de067a4be
PRE_PROMOTION_FRONTEND_DEPLOYMENT = main.eac95fab.js
ROLLBACK_BACKEND_SHA = 89217062481b4eb858a8b530ec90c83de067a4be
ROLLBACK_FRONTEND_DEPLOYMENT = main.eac95fab.js
ROLLBACK_RENDER_DEPLOY = dep-d97pv767r5hc73cfefeg
```

## Verified

| Check | Result |
| --- | --- |
| Git `main` can be reverted | Yes — previous SHA remains on origin; no force-push used |
| Render can redeploy prior SHA | Yes — `pleerity-api-production` auto-deploys `main`; checkout/revert `89217062` and push, or dashboard rollback to `dep-d97pv767r5hc73cfefeg` |
| Vercel production alias | Previous bundle `main.eac95fab.js` was live on `pleerityenterprise.co.uk`; restore by promoting the prior Production deployment |
| Irreversible DB migration in this promotion | **None** (no alembic/migration files in develop delta) |
| Destructive schema operation | **None** |
| Production Mongo cleanup | **None** — cleanup script refuses `pleerity_production`; not executed |

Do not roll back database state unless a separate restoration is approved.

## Rollback trigger (not fired)

Production became `healthy` / `ready` / `heartbeat_fresh` after the expected startup window. No rollback executed.
