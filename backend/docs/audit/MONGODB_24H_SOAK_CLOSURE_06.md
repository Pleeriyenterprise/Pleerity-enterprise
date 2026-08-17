# MongoDB 24h soak closure 06

**Programme:** `MONGODB-24H-SOAK-CLOSURE-AND-PROMOTION-GATE-06`  
**Captured:** 2026-08-17T06:05Z–06:11Z  
**Previous platform verdict:** `HOLD_FOR_MONGO_SOAK` (05)  
**Commercial Controls:** `COMMERCIAL_CONTROLS_VERIFIED` (not re-opened)

This exercise is observation-only. It does not implement features, merge `main`, deploy production, or purge MongoDB.

## Verdict (soak window)

```text
SOAK_WINDOW = PASS
PLATFORM_PROMOTION_GATE = GO_FOR_PRODUCTION_PROMOTION_WITH_ACCEPTED_CONDITIONS
```

The required uninterrupted 24-hour staging soak on SHA `fb138ae5` / Render `dep-da0dekm1egvs739e9dog` completed. Mongo growth stayed controlled. Scheduler remained healthy after the documented post-deploy recovery. No P0/P1 remained open. The previous idle-poll telemetry explosion did not return.

This authorises a **separate** production-promotion exercise. It does **not** merge to `main` and does **not** deploy production.

## Phase 1 — Uninterrupted runtime

| Check | Result |
| --- | --- |
| Staging `/api/version` | `fb138ae5b8234d9e354f6f5175c2fd02b1f944c7`, `environment=staging` |
| Local / `origin/develop` | same SHA |
| Live Render deploy | `dep-da0dekm1egvs739e9dog` still `status=live`; no later backend deploy |
| Previous deploy | `dep-da0bd1m7bikc73bsgteg` `7c77391a` deactivated when this deploy went live |
| Soak baseline | `2026-08-15T21:19:51.151684Z` (`finishedAt`) |
| Scheduler recovered | `2026-08-15T21:26:36.127493Z` `healthy` / `heartbeat_fresh` |
| Observation | `2026-08-17T06:05:37Z` storage; `2026-08-17T06:10:36Z` collections |
| Elapsed from baseline | **32.76 hours** |
| Elapsed from scheduler recovery | **~32.65 hours** |
| Required | ~24 hours |
| Instance count 21:19Z–05:19Z hourly | **1 every hour** (no 0-gap) |
| App startup logs after 21:20Z | none (`hasMore: false`) |
| `/api/health` at close | `healthy` / `ready`; scheduler `heartbeat_fresh`; age ~10–50s |

No backend restart invalidated the window. Do **not** issue `HOLD_FOR_MONGO_SOAK`.

## Phase summary

| Phase | Result | Notes |
| --- | --- | --- |
| 2 Mongo capacity | PASS_WITH_CONDITION | 53.16% → 54.13%; level `ok`; writes available; shared Atlas remains roadmap |
| 3 Idle-skip | PASS_WITH_CONDITION | 15s / 1m / heartbeat skip proven; `risk_signal` persists some `BLOCKED` ticks (bounded) |
| 4 Scheduler | PASS | Heartbeat fresh; 54 registered jobs; instance_count=1; no stale leases |
| 5 Incidents | PASS_WITH_CONDITION | Deploy-window P0/P1 all RESOLVED; 0 open P0/P1; 2 historic P2s remain |
| 6 Observability | PASS_WITH_CONDITION | API healthy vs summary `degraded` is consistent dual-signal, not authority drift |
| 7 Commercial Controls | PASS | Bundle `main.7fd31560.js`; fingerprint still present; assessment 200 |
| 8 Production non-touch | PASS | `origin/main` `89217062`; production API/FE unchanged; no prod Mongo/Stripe/Postmark/deploy |

Detail: `MONGODB_STORAGE_GROWTH_24H_06.md`, `MONGODB_SCHEDULER_STABILITY_06.md`, `MONGODB_INCIDENT_STABILITY_06.md`, `PRODUCTION_PROMOTION_FINAL_GATE_06.md`.

## Why not unqualified GO

Remaining conditions are **non-blocking** and already classified as roadmap or residual ops debt in 05. They are documented rather than waived:

1. Staging and production still share one Atlas Flex cluster.
2. Live retention is not enabled; `operational_evidence_events` is now the largest staging collection.
3. Two open P2 incidents (`daily_reminders` RECOVERED-but-open; delivery-unknown DEGRADED).
4. `risk_signal_regen_worker` still persists feature-flag `BLOCKED` ticks (622 `job_runs` in-window vs ~3,931 theoretical idle ticks).
5. Inherited scorecard / pentest / staging Stripe recon were not re-executed here.

None of these reopened the pre-remediation write-block or 1.94M `job_runs` failure mode.

## Production non-touch (this exercise)

- No merge to `main`.
- No production deploy.
- Staging Mongo reads only (`pleerity_staging`); `production_db_touched=false`.
- No Stripe or Postmark calls.
- Docs are written locally. **Do not push `develop` as part of collecting this verdict** — Render auto-deploys every `develop` commit and would restart staging.

## Supporting evidence (local)

- `mongodb_24h_soak_live_06.json`
- `mongodb_24h_soak_collections_06.json`
- `production_promotion_final_gate_06.json`
