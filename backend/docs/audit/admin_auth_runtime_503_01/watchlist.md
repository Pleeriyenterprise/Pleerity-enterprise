# Watchlist

## Status
- Classification: **VERIFIED_OPERATIONALLY**
- Billing Recovery guided-flow: auth path unblocked; see `phase4_billing_recovery_operations_01/` for flow-level gates.

## Completed
- Valid admin login (200, token issued; not persisted in artifacts)
- Protected recovery dashboard (200 authenticated)
- Invalid admin login → 401 (not 503)
- Invalid bearer → 401
- Startup readiness + billing recovery regression tests pass

## Security
- Rotate staging admin password if it was shared outside a secret store.
- Continue using `STAGING_ADMIN_EMAIL` / `STAGING_ADMIN_PASSWORD` via environment only (never commit).

## Phase 4 follow-up
- Regenerate checkout runtime returned 500 for probe client (see `regenerate_checkout_browser_runtime.json`)
- Browser screenshot proof not captured by closeout script
- Re-run guided closeout after regenerate runtime fix or alternate MODE_UNVERIFIED candidate
