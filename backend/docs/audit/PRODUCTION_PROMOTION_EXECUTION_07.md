# Production promotion execution 07

**Programme:** `PRODUCTION-PROMOTION-EXECUTION-07`  
**Date:** 2026-08-17  
**Commercial Controls:** `COMMERCIAL_CONTROLS_VERIFIED`  
**Final verdict:** `PRODUCTION_DEPLOYMENT_SUCCESSFUL_WITH_CONDITIONS`

This is production execution, not a repeat of staging certification. Validated `fb138ae5` behaviour was merged to `main` as `b6b7ddf5` and is live.

## Verdict meaning

Backend and frontend of the soaked candidate reached production. Health recovered to `ready` / `heartbeat_fresh`. Mongo growth stayed bounded. No rollback. Remaining items are accepted roadmap conditions plus production-admin execute not run.

This does **not** close Atlas split, live retention, pentest, or historic P2s.

## Matrix

| Domain | Pre-promotion | Post-promotion | Verdict |
| --- | --- | --- | --- |
| Backend deployment | `89217062` | `b6b7ddf5` `dep-da1ashu1egvs73a2chb0` | PASS |
| Frontend deployment | `main.eac95fab.js` | `main.c9306ba7.js` | PASS |
| Authentication | production healthy; staging creds must not work | staging admin 401; login pages 200; live prod admin not exercised | PASS_WITH_CONDITION |
| RBAC | inherited | not re-executed with a production session | NOT_EXERCISED |
| Commercial Controls | VERIFIED | fingerprints + unit tests on prod bundle | PASS_WITH_CONDITION |
| Subscription lifecycle | inherited CC-04 | no production subscription mutated | NOT_EXERCISED |
| Stripe/webhooks | inherited | no live test event; unit tests passed | NOT_EXERCISED |
| Postmark | inherited CC-04 | no customer email sent; 5 pre-existing orchestrator unit fails | PASS_WITH_CONDITION |
| Mongo capacity | 54.13% soak end | 54.19% `ok` (07:24Z) | PASS_WITH_CONDITION |
| Scheduler | old SHA had no heartbeat field | `heartbeat_fresh` from 06:56:56Z | PASS |
| Incidents | unknown on prod admin API | deploy-window SLA misses logged; none after resume; admin list not queried | PASS_WITH_CONDITION |
| Observability | public health only | `/api/health` matches scheduler logs after ready | PASS |
| Production customer data | untouched | no cleanup; no CC execute | PASS |

## Tests (candidate `fb138ae5`)

```text
tests_run = 230 backend + 16 frontend
tests_passed = 203 backend + 16 frontend
tests_failed = 5 backend (test_notification_orchestrator.py)
tests_skipped = 22 backend
known_pre_existing_failures = resolve_greeting NameError in finalize_db_email_html (also on origin/main)
```

## Observation (Phase 15)

Window: backend live **2026-08-17T06:49:14Z** through health recheck **2026-08-17T07:20:06Z** (**~31 minutes**). Scheduler first heartbeat 06:56:56Z through 07:20:06Z (**~23 minutes** of fresh heartbeats).

| Check | Result |
| --- | --- |
| `/api/version` | still `b6b7ddf5`, `environment=production` |
| `/api/health` | `healthy` / `ready` / `heartbeat_fresh` (age ~51s) |
| Instance count | 1 throughout 06:45–07:21Z |
| 5xx after cutover | none after 06:53Z (2×502 @ 06:50, 1×503 @ 06:53 only) |
| `Incident created` after resume | none in sampled logs |
| `DATABASE_CAPACITY_EXCEEDED` | none in production logs 07:00–07:22Z |
| Frontend | still `main.c9306ba7.js`; public pages 200 |
| Mongo cluster | 54.18% @ 06:58Z → **54.19%** @ 07:24Z; `ok`; writes not at risk |

This is **not** a 24-hour production soak. Extended post-launch monitoring can follow separately.

## Phase 17 — 06 evidence preservation

The 06 soak pack is committed on `develop` after production promotion. The soak itself remains:

```text
Staging SHA: fb138ae5
Render deployment: dep-da0dekm1egvs739e9dog
Soak baseline: 2026-08-15T21:19:51Z
Observed: 32.76 hours
```

This evidence commit does not rewrite that runtime fact. A later `develop` push may restart staging because `rootDir=backend`; treat that restart as post-promotion operational history, not soak invalidation.

## Evidence index

- `PRODUCTION_PROMOTION_REPOSITORY_RECONCILIATION_07.md`
- `PRODUCTION_PROMOTION_BACKEND_DEPLOYMENT_07.md`
- `PRODUCTION_PROMOTION_FRONTEND_DEPLOYMENT_07.md`
- `PRODUCTION_PROMOTION_SMOKE_07.md`
- `PRODUCTION_PROMOTION_MONGODB_OBSERVATION_07.md`
- `PRODUCTION_PROMOTION_COMMERCIAL_CONTROLS_SMOKE_07.md`
- `PRODUCTION_PROMOTION_ROLLBACK_READINESS_07.md`
- `POST_LAUNCH_ACCEPTED_CONDITIONS_07.md`
- `production_promotion_results_07.json`
- 06 soak pack (committed to `develop` after production promotion; soak SHA remains `fb138ae5`)
