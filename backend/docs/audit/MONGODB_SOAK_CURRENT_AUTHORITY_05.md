# MongoDB soak — current authority 05

**Programme:** `COMMERCIAL-CONTROLS-CERTIFICATION-CLOSURE-AND-PROMOTION-GATE-05`  
**Do not reuse** the 6 August 2026 soak window (`INCIDENT_CLOSURE_24H_SOAK_01.md`, start 2026-08-06T17:59:07Z). That window was interrupted by later deploys.

## Pre-preservation-push baseline (authoritative until this push)

| Field | Value |
| --- | --- |
| Last staging backend deploy | `7c77391a` Render `dep-da0bd1m7bikc73bsgteg` |
| Trigger | `new_commit` (docs commit after `02533d50`) |
| `finishedAt` | 2026-08-15T18:59:45.440677Z |
| Instance count | 0 at 19:00–19:01Z (restart), 1 from 19:02Z |
| `/api/health` at 21:09Z | `healthy` / `ready`; scheduler `heartbeat_fresh`; age ~102s |
| Last heartbeat | 2026-08-15T21:09:31.582726Z |
| Elapsed uninterrupted | **~2.2 hours** (from 18:59:45Z) |
| Required | ~24 hours |
| Result | **INCOMPLETE** |

## Live storage (this window)

`GET /api/admin/observability/health-summary` 2026-08-15T21:13:38Z:

| Field | Value |
| --- | --- |
| Cluster used | 2854065854 / 5368709120 bytes |
| Usage | **53.16%** |
| Monitor level | `ok` |
| Writes at risk | false |
| Incident recommended | false |
| `open_p0_p1_count` | 0 |
| `open_incidents_count` | 4 |
| `overall_health` | `degraded` (non-P0/P1 incidents) |

Prevention line remains in tree: `a5bfccfd`, `9b76213e`, `703fbd67`, `7d8e3648`.

## Deployment automation (Phase 4)

| Question | Answer |
| --- | --- |
| Does every `develop` push trigger Render? | **Yes.** Staging web `srv-d68995vpm1nc738v1s70`: `autoDeploy=yes`, `autoDeployTrigger=commit`, branch `develop`. Last deploys are all `trigger=new_commit`. |
| Does Render rebuild if only frontend/docs changed? | **Yes.** `rootDir=backend` still clones and builds on every branch commit. Docs-only `7c77391a` rebuilt and restarted the API. |
| Does Vercel deploy automatically? | Staging FE is project `pleerity-enterprise-9jjg`. Certified bundle was a **manual** preview + alias, not this Render path. A `develop` push may or may not create a new Vercel preview; production project must not receive `--prod`. |
| Can evidence be committed without restarting backend? | **Commit locally: yes. Push to `origin/develop`: no.** |
| Path filters to skip backend rebuild? | Not configured. Adding them would be an infrastructure change not justified here. |
| Modify deploy architecture now? | **No.** |

## Push consequence (recorded before execution)

```text
SOAK_WILL_RESET = TRUE
```

Pushing the certified frontend commit plus evidence/docs will auto-deploy staging backend and restart web + scheduler + heartbeat. The ~2.2h window must not be carried forward.

New soak start after push = Render `finishedAt` of that deploy. Do not pretend the interrupted window continued.
