# Production promotion frontend deployment 07

**Programme:** `PRODUCTION-PROMOTION-EXECUTION-07`  
**Result:** PASS

## Project separation

| Project | Role | This promotion |
| --- | --- | --- |
| `pleerity-enterprise` | Production (`pleerityenterprise.co.uk`) | GitHub Production deploy `5940350296` on `b6b7ddf5` — **success** |
| `pleerity-enterprise-9jjg` | Staging alias | Also received a GitHub “Production” deploy on the same SHA. Bundle still embeds **staging** API `pleerity-enterprise.onrender.com`. Not the customer domain. |

Do not treat `9jjg` as production. Production domain was not pointed at `9jjg`.

## Production site

| Field | Pre | Post |
| --- | --- | --- |
| URL | `https://pleerityenterprise.co.uk` | same |
| Bundle | `main.eac95fab.js` | **`main.c9306ba7.js`** |
| Homepage | 200 | 200 |
| Production API in bundle | `api.pleerityenterprise.co.uk` | **present** |
| Staging Render URL in bundle | absent | **absent** |
| `cc-step-up-circuit-fix-04` | n/a (old bundle) | **present** |
| `commercial-step-up-modal-host` | | **present** |
| `DATABASE_CAPACITY_EXCEEDED` | | **present** |

Vercel deployment URL: `https://pleerity-enterprise-ktjpvb37f-victory-aigbochies-projects.vercel.app`  
GitHub: environment `Production – pleerity-enterprise`, state `success`, SHA `b6b7ddf5`.

No `vercel --prod` was issued against `9jjg`. Production frontend arrived via the existing Git integration on `main`.
