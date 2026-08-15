# Production promotion gate assessment 05

**Programme:** `COMMERCIAL-CONTROLS-CERTIFICATION-CLOSURE-AND-PROMOTION-GATE-05`  
**Assessed:** 2026-08-15T21:13Z  
**This is a gate assessment, not a new implementation programme.**

`COMMERCIAL_CONTROLS_VERIFIED` is not `PLATFORM_PRODUCTION_READY`.

## Domain notes

### Commercial Controls — PASS (not blocking)

CC-04. All seven controls; ACTIVE and CANCELLED Suspend Billing distinct; circuit fix certified; `PLAN_UNRESOLVED` proven.

### MongoDB capacity — PASS_WITH_CONDITION (not blocking)

Prevention deployed (`a5bfccfd` line). Live 2026-08-15T21:13Z: **53.16%**, level `ok`, `writes_at_risk=false`. Condition: Atlas still shared staging+production on one cluster (roadmap, not a new defect).

### MongoDB soak — BLOCKED (launch)

Current uninterrupted window **~2.2h** from 2026-08-15T18:59:45Z. Required ~24h. 6 Aug soak is obsolete. Preservation push resets this window.

### Scheduler — PASS_WITH_CONDITION (not blocking)

`/api/health` scheduler `healthy` / `heartbeat_fresh`. Condition: every Render restart creates a stale window; needs soak outside deploy flaps (`7d8e3648`).

### Subscription lifecycle — PASS (not blocking)

No known blocking lifecycle defect after CC-04 and P0 lifecycle work. ACTIVE pause/resume and CANCELLED non-recreation proven. Inherited P0 matrices exist (July 2026); not re-run here.

### Payments/Stripe — PASS_WITH_CONDITION (not blocking)

Certified pause/void semantics on a current test subscription. Historic staging `sub_*` decay is isolated (27 stale rows). Follow-up: periodic staging Stripe reconciliation (post-launch).

### Authentication — PASS (not blocking)

Staging admin login and step-up proven in CC-03/04. Circuit no longer treats `STEP_UP_REQUIRED` as instability.

### Email/Postmark — PASS (not blocking)

ACTIVE Suspend Billing ADMIN_MANUAL **DELIVERED** + inbox body. CANCELLED path DELIVERED in 03.

### Customer journeys — PASS_WITH_CONDITION (not blocking)

Last platform journey scorecard `PRODUCTION_PILOT_READY` dated **2026-07-09**. Not re-executed in 05. No new blocking journey defect recorded since. Not marked PASS as a fresh 05 run.

### Observability — PASS_WITH_CONDITION (not blocking)

Health truthful. Live `overall_health=degraded` with **4 open incidents** and **0 P0/P1**. Incident lifecycle completion from 6 Aug remains an open soak-time condition, not a new code defect.

### Security — PASS_WITH_CONDITION (not blocking)

`platform_release_readiness_01/SECURITY_VALIDATION.md`: no critical automated findings; pentest/CSRF/secrets rotation not this gate. Step-up remains required for commercial execute.

## Governance drift follow-up

`lifecycle_ops_*` five keys: **VALID_INTENTIONAL_EXTENSION** (`COMMERCIAL_CONTROLS_GOVERNANCE_DRIFT_02.md`). Test allow-list already aligned with comment. Unrelated to Commercial Controls. Keep exact-match registry test as an ongoing contract. Backlog: do not silently add further keys.
