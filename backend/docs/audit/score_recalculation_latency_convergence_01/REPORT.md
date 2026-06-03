# SCORE-RECALCULATION-LATENCY-FINAL-VERIFICATION-01

Verified at: 2026-06-03T21:54:21Z  
Fix commit: **d5252f99**  
Classification: **VERIFIED_OPERATIONALLY**

## Summary

Staging operational proof confirms the DONE-duplicate requeue fix (`d5252f99`) restores end-to-end score propagation after `requirements/sync` on a property with an existing DONE queue row.

## Part 1 — Deploy

| Check | Result |
|-------|--------|
| Frontend bundle `main.6bd8fcfe.js` | OK |
| `Updating…` / `score_cognition_line` / `compliance_score_pending` | Present |
| API health | 200, readiness `ready` |
| Worker | Healthy |

## Part 2 — Trigger

- **Method:** `POST /properties/{id}/requirements/sync`
- **Property:** `d35a58ae-3c81-491c-9694-1d021dd3b8ad` (Kensington Garden Flat)
- **Correlation:** `REQUIREMENTS_SYNC:d35a58ae-3c81-491c-9694-1d021dd3b8ad`
- **Status:** 200
- **DONE duplicate regeneration:** inferred true (pending observed immediately after sync on previously DONE row)

## Part 3 — Pending cognition

At **23.13s** after trigger:

- `compliance_score_pending=true`
- `score_status=calculating`
- Risk suppressed (`risk_level=null`)
- Cognition: *Score updating — recent compliance changes are being processed*
- No stale Elevated risk while pending
- Screenshots: `screenshots/final_verification/dashboard_pending.png`, `property_pending.png`

## Part 4 — Worker convergence

At **72.78s**:

- Score persisted **42 → 52**
- `compliance_score_pending=false`, `score_status=ok`
- Dashboard / property / portfolio headline agree (0 properties pending recalc)
- No contradictory cognition
- Screenshots: `dashboard_converged.png`, `property_converged.png`

## Part 5 — Safety

- Duplicate sync pair: both 200, bounded pending observations (no storm)
- Tenant isolation preserved (client-scoped token only)

## Part 6 — Regression

All suites passed (26 tests):

- `test_compliance_recalc_queue_stabilization_phase1.py` (17)
- `test_score_cognition_service.py` (4)
- `test_compliance_scoring_v2_model.py` (5)

Includes `test_enqueue_compliance_recalc_duplicate_done_regenerates`.

## Latency

| Metric | Value |
|--------|-------|
| Enqueue (sync API) | 6.09s |
| Pending first visible | 23.13s |
| Convergence complete | 72.78s |
| Class | acceptable |

## Residual watchlist

See `watchlist.md`.
