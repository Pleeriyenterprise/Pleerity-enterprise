# Watchlist — PHASE-2A-OPERATIONAL-RECOVERY-AUTOMATION-01

- Deploy pending: `fast_mode` recovery scan optimisation (local commit after closeout) to improve CC primary-stream latency on large portfolios.
- Staging pilot did not surface live examples of all 13 recovery types (negotiation/reschedule/evidence loops, activation stalls, dead-end); unit tests cover those rules deterministically.
- CC primary stream may still degrade to maintenance fallback on very large portfolios; recovery is merged into degraded fallback as of `bb79d425`.
- Consider branded recovery email template (currently uses `ADMIN_MANUAL` like Phase 1 nudges).
