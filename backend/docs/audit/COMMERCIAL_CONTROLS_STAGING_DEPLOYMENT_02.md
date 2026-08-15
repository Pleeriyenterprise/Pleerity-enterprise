# Commercial Controls — Staging Deployment 02

**Audit ID:** `COMMERCIAL-CONTROLS-AUTHORITY-CORRECTION-AND-E2E-CERTIFICATION-02`  
**Date:** 2026-08-15

## Git

| Item | Value |
| --- | --- |
| Previous SHA | `dfe9e19edf88d88559b6003c2215fd84419956f7` |
| New SHA | `02533d50faafc114292ab1cba56c2a283df01664` |
| Rollback SHA | `dfe9e19edf88d88559b6003c2215fd84419956f7` |
| Branch | `develop` (pushed) |
| Merged to main | **No** |

## Backend (staging only)

| Item | Value |
| --- | --- |
| Service | `Pleerity-enterprise` (`srv-d68995vpm1nc738v1s70`) |
| URL | `https://pleerity-enterprise.onrender.com` |
| Branch | `develop` (auto-deploy on commit) |
| Deploy | `dep-da0b8be1egvs739cft9g` live 2026-08-15T18:50:05Z |
| Trigger | `new_commit` (push of `02533d50`) |
| `/api/version` | `{"commit_sha":"02533d50faafc114292ab1cba56c2a283df01664","environment":"staging"}` |

Production Render `pleerity-api-production` (`srv-d8m59gmgvqtc73cmbu6g`, branch `main`) was **not** deployed. Production `/api/version` remained `89217062481b4eb858a8b530ec90c83de067a4be` / `production`.

## Frontend (staging only)

| Item | Value |
| --- | --- |
| Project | `pleerity-enterprise-9jjg` |
| Preview | `https://pleerity-enterprise-9jjg-lz1ca2id0-victory-aigbochies-projects.vercel.app` |
| SHA | `02533d50faafc114292ab1cba56c2a283df01664` |
| Alias | `https://pleerity-enterprise-9jjg.vercel.app` → preview above |
| Bundle | `main.c8b6a433.js` |
| `commercial-step-up-modal-host` | present in bundle |
| `commercial-effective-access` | present in bundle |
| `commercial-restored-plan` | present in bundle |

Production Vercel project `pleerity-enterprise` was **not** deployed.

## Mongo soak / scheduler

This staging backend deploy restarted the web service (and therefore the in-process scheduler).

| Item | Value |
| --- | --- |
| Prior soak baseline | 2026-08-06T17:59:07Z (`incident_closure_soak_snapshot_01.json`) |
| Interrupt | Staging deploy live 2026-08-15T18:50:05Z |
| Action | Observation window must be **restarted/extended**; this deploy is not hidden |

## Tests before push

- Backend targeted: 72 passed (`test_commercial_entitlement_governance`, `test_entitlement_access_and_billing_payload`, `test_account_lifecycle_runtime_contract`, `test_admin_action_governance_policy`)
- Frontend: 6 passed (`CommercialEntitlementControls.test.js`)
