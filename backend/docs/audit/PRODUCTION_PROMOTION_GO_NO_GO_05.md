# Production promotion GO/NO-GO 05

**Programme:** `COMMERCIAL-CONTROLS-CERTIFICATION-CLOSURE-AND-PROMOTION-GATE-05`  
**Date:** 2026-08-15

## Separate authorities

```text
COMMERCIAL_CONTROLS_VERIFIED
PLATFORM_PROMOTION_GATE = HOLD_FOR_MONGO_SOAK
```

Not `GO_FOR_PRODUCTION_PROMOTION`.  
Not `NO_GO` (no new launch-blocking product defect identified).  
Not `GO_FOR_PRODUCTION_PROMOTION_WITH_ACCEPTED_CONDITIONS` — the soak gap is a stated launch condition, not an accepted residual.

This does **not** deploy production and does **not** merge `main`.

## Reason

Commercial Controls are closed. The platform still lacks a completed **uninterrupted 24-hour Mongo soak** after the 15 August 2026 backend restarts. Current elapsed ~2.2h. Pushing certified source to `origin/develop` will restart staging again (`SOAK_WILL_RESET = TRUE`). Production promotion remains a later controlled exercise after a clean 24h window on the then-current staging SHA.

## Gate matrix

See `PRODUCTION_PROMOTION_GATE_ASSESSMENT_05.md` and the 05 canvas. Summary:

| Domain | Latest authority | Status | Blocking? | Required action |
| --- | --- | --- | --- | --- |
| Commercial Controls | CC-04 | PASS | No | Preserve source on `develop`; do not reopen |
| MongoDB capacity | health-summary 2026-08-15 53.16% ok | PASS_WITH_CONDITION | No | Keep monitor; Atlas split is roadmap |
| MongoDB soak | Render `7c77391a` 18:59Z + ~2.2h | BLOCKED | **Yes** | Complete 24h after the preservation-push restart |
| Scheduler | `/api/health` heartbeat_fresh | PASS_WITH_CONDITION | No | Confirm across soak |
| Subscription lifecycle | CC-04 + P0 matrices | PASS | No | None |
| Payments/Stripe | CC-04 void pause | PASS_WITH_CONDITION | No | Periodic staging Stripe recon (roadmap) |
| Authentication | CC-03/04 step-up | PASS | No | None |
| Email/Postmark | CC-04 DELIVERED | PASS | No | None |
| Customer journeys | scorecard 2026-07-09 | PASS_WITH_CONDITION | No | Optional inherited re-smoke before prod cutover |
| Observability | health-summary degraded, 0 P0/P1 | PASS_WITH_CONDITION | No | Soak; close remaining non-P0 incidents |
| Security | readiness 2026-07-09 | PASS_WITH_CONDITION | No | Standard pre-GA review remains roadmap |

## After soak completes

A separate production-promotion exercise may move the gate to GO only if:

* 24h soak on the post-push staging SHA is complete;
* scheduler remains healthy outside deploy windows;
* production still untouched until that exercise explicitly deploys.
