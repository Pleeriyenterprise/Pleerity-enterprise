# Production promotion final gate 06

**Programme:** `MONGODB-24H-SOAK-CLOSURE-AND-PROMOTION-GATE-06`  
**Assessed:** 2026-08-17T06:11Z  
**This is a gate assessment. It does not merge `main` and does not deploy production.**

## Separate authorities

```text
COMMERCIAL_CONTROLS_VERIFIED
PLATFORM_PROMOTION_GATE = GO_FOR_PRODUCTION_PROMOTION_WITH_ACCEPTED_CONDITIONS
```

Not `HOLD_FOR_MONGO_SOAK` — the uninterrupted 24h window is proven.  
Not `NO_GO` — no new launch-blocking operational defect appeared.  
Not unqualified `GO_FOR_PRODUCTION_PROMOTION` — residual conditions remain and are listed below. They are non-blocking.

This authorises the **next separate production-promotion exercise** only.

## Why this verdict

| GO criterion | Evidence |
| --- | --- |
| Full uninterrupted soak | 32.76h on `fb138ae5` / `dep-da0dekm1egvs739e9dog`; instance_count=1 hourly; no later deploy; no startup logs after 21:20Z |
| Mongo growth controlled | 53.16% → 54.13%; +49.76 MiB; ~38 MB/day; level `ok`; writes available |
| Scheduler healthy | `heartbeat_fresh` at close; 54 jobs; no duplicate; no stale leases |
| No P0/P1 remaining / none after recovery | Deploy-window P0/P1 at 21:24–21:25Z all RESOLVED; none after 21:26:36Z; open_p0_p1=0 |
| No telemetry explosion | Idle poll heartbeats still 5 upserts; high-freq workers 650 `job_runs` vs ~13.8k theoretical ticks; `job_runs` 15 MB vs pre-remediation ~1.4 GB |
| Observability truthful | API `healthy` + summary `degraded` agree: process up, 2 P2s open |
| No known launch-blocking defect | Remaining items are 05 roadmap / residual P2s |

## Promotion matrix

| Domain | Status | Blocking? | Evidence |
| --- | --- | --- | --- |
| MongoDB capacity | PASS_WITH_CONDITION | No | 54.13% `ok`; writes_at_risk=false; shared Flex is roadmap |
| MongoDB 24h soak | PASS | No | 32.76h uninterrupted on current staging SHA |
| Scheduler | PASS | No | Heartbeat fresh; instance_count=1; 54 registered jobs |
| Incidents | PASS_WITH_CONDITION | No | 0 open P0/P1; 2 historic P2s; deploy-window P0/P1 resolved |
| Observability | PASS_WITH_CONDITION | No | `/api/health`, health-summary, heartbeat, mongo monitor, incident engine agree |
| Commercial Controls | PASS | No | `COMMERCIAL_CONTROLS_VERIFIED`; bundle `main.7fd31560.js`; fingerprint `cc-step-up-circuit-fix-04` |
| Subscription lifecycle | PASS | No | Inherited CC-04; not re-run; no soak regression signal |
| Authentication | PASS | No | Staging admin JWT + CC assessment 200; circuit fingerprint present |
| Payments/Stripe | PASS_WITH_CONDITION | No | Inherited CC-04 void-pause; no Stripe call in this exercise; periodic recon is roadmap |
| Postmark/email | PASS | No | Inherited CC-04 DELIVERED; no Postmark test in this exercise |
| Production non-touch | PASS | No | `origin/main` `89217062`; prod API production; FE `main.eac95fab.js`; no prod Mongo/Stripe/Postmark/deploy |

## Accepted non-blocking conditions

Do not convert these to blockers without new runtime evidence:

1. **Atlas staging/production separation** — still one Flex cluster; monitor scans both DBs.
2. **Live retention enablement** — flagged off; OEP events are now the largest staging collection; soak-window growth ~9.2k events/day, not a 15s flood.
3. **Storage budgeting** — monitor + thresholds exist; budgeting UX is improvement.
4. **Periodic staging Stripe reconciliation** — 27 stale fixture rows remain a known staging hygiene item from CC-04.
5. **Pentest / pre-GA security review** — last automated readiness 2026-07-09.
6. **Two open P2 incidents** — `daily_reminders` RECOVERED-but-open (9 Aug); delivery-unknown DEGRADED (6 Aug).
7. **`risk_signal_regen_worker` `BLOCKED` persist** — 622 `job_runs` in-window; idle ticks still skip via poll heartbeats.
8. **Customer journeys scorecard** — last platform card 2026-07-09; optional re-smoke in the production-promotion exercise, not a soak fail.

## Observability consistency (Phase 6)

| Surface | Runtime truth |
| --- | --- |
| `/api/health` | `healthy` / `ready`; scheduler `heartbeat_fresh` |
| System Health (`health-summary`) | `overall_health=degraded`; `open_p0_p1_count=0`; `open_incidents_count=2` |
| Platform Status / Automation Control Centre | same health-summary payload (54 jobs, heartbeat, mongo 54.13%) |
| Scheduler heartbeat | advancing; poll + `/api/health` agree |
| Mongo storage monitor | `ok`, 54.13%, writes not at risk |
| Incident engine | 2 open P2s; 0 P0/P1; no storage incident |

API healthy **and** summary degraded is **intentional dual-signal** (liveness vs incident posture). That is not material authority drift. `NO_GO` is not issued on this point.

## Commercial Controls non-regression (Phase 7)

CC-04 was **not** repeated.

| Check | Result |
| --- | --- |
| Staging FE alias bundle | `main.7fd31560.js` (unchanged since 05) |
| `cc-step-up-circuit-fix-04` | present in bundle |
| `commercial-step-up-modal-host` | present |
| `DATABASE_CAPACITY_EXCEEDED` | present |
| Controls available | `GET .../commercial-entitlement/assessment` HTTP 200, `found=true` (nancy smoke) |
| Subsequent FE deploy | **none** that would revert the circuit |

Authority remains `COMMERCIAL_CONTROLS_VERIFIED`.

## Production non-touch (Phase 8)

| Check | Result |
| --- | --- |
| `origin/main` | `89217062481b4eb858a8b530ec90c83de067a4be` unchanged |
| Production `/api/version` | same SHA, `environment=production` |
| Production `/api/health` | `healthy` |
| Production FE | `main.eac95fab.js` |
| Production Mongo mutation | none (`pleerity_staging` reads only) |
| Production Stripe | none |
| Production Postmark | none |
| Production deploy | none |

## Next exercise (not this one)

A later production-promotion programme may merge and deploy only under its own controls. Pushing this 06 documentation to `origin/develop` will auto-deploy staging and **restart** a new soak clock. Capture is complete locally; push is optional and is **not** required to issue this gate.
