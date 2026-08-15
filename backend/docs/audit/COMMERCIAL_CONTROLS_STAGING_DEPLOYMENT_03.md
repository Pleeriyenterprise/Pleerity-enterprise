# Commercial Controls — Staging deployment authority 03

**Audit ID:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-COMPLETION-03`  
**Date:** 2026-08-15  
**Runtime SHA recorded on every live assertion:** `7c77391a5ee65f0a85372d9c462448c270b6b066`

## Git

| Item | Value |
| --- | --- |
| Implementation SHA | `02533d50faafc114292ab1cba56c2a283df01664` |
| Current develop / staging docs SHA | `7c77391a5ee65f0a85372d9c462448c270b6b066` |
| Diff `02533d50..7c77391a` | documentation only; application behaviour identical |
| Branch | `develop` |
| Merged to main | **No** |
| Production SHA | `89217062481b4eb858a8b530ec90c83de067a4be` (unchanged) |

## Backend

| Item | Live value |
| --- | --- |
| Staging `/api/version` | `{"commit_sha":"7c77391a5ee65f0a85372d9c462448c270b6b066","environment":"staging"}` |
| Production `/api/version` | `{"commit_sha":"89217062481b4eb858a8b530ec90c83de067a4be","environment":"production"}` |
| Staging service | `Pleerity-enterprise` (`srv-d68995vpm1nc738v1s70`), branch `develop` |
| Production | not deployed |

## Frontend

| Item | Live value |
| --- | --- |
| Alias | `https://pleerity-enterprise-9jjg.vercel.app` |
| Bundle | `main.c8b6a433.js` |
| `commercial-step-up-modal-host` | present |
| `commercial-entitlement-controls` | present |
| `commercial-effective-access` | present |
| `commercial-restored-plan` | present |
| API host in bundle | `https://pleerity-enterprise.onrender.com` (staging) |
| Production API host in bundle | absent |

## Mongo soak

Staging deploys/restarts on **15 August 2026** (implementation deploy live `2026-08-15T18:50:05Z`, plus docs auto-deploy of `7c77391a`) interrupted the previous MongoDB observation window. The prior soak duration is **not** carried forward. Commercial Controls certification is independent of the separately governed production Mongo soak condition.

## Production / main

Untouched. This exercise did not merge to main or deploy production.
