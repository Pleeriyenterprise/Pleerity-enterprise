# Phase 1 — Stripe Mode Containment

**Programme:** `PHASE-1-STRIPE-MODE-CONTAINMENT-01`  
**Classification:** `PARTIAL`  
**Prior:** `STRIPE_ENVIRONMENT_GOVERNANCE_GAP` / `MIXED_MODE_DATA_DRIFT`

## Summary

Guardrails-only phase: preflight billing mode before Stripe mutations, customer-safe 409 responses, ops read-only inventory, persist `stripe_mode` on new writes. **No automatic migration or Stripe object mutation.**

## Implemented

| Part | Deliverable |
|------|-------------|
| 1 | `validate_stripe_subscription_mode` (+ customer/checkout/portal/event validators) |
| 2 | Drift codes + `record_stripe_mode_drift` audit/metrics |
| 3 | `GET /api/admin/billing/stripe-mode-inventory` |
| 4 | `stripe_mode` on `client_billing`, `checkout_sessions`; `livemode` on `stripe_events` |
| 5 | `resolve_stripe_context()` + legacy caller instrumentation |
| 6 | Customer-safe copy; BillingPage structured error handling |
| 7 | `billing_mode_drift` on commercial entitlement assessment |
| 8 | `tests/test_stripe_mode_containment.py` (11 tests) |

## Wired paths

- `POST /api/billing/checkout` (upgrade/downgrade)
- `POST /api/billing/portal`
- `POST /api/admin/billing/clients/{id}/sync`
- `POST /api/admin/billing/clients/{id}/portal-link`
- `retrieve_stripe_subscription_dict` (webhook trusted_mode + stored preflight)
- Checkout + webhook billing persistence

## Remaining (Phase 2)

- Backfill `stripe_mode` on legacy billing rows (read-only inventory will show volume)
- Converge `intake_draft_service`, `jobs.py`, Clearform routes
- Live staging inventory artifact run
- Re-classify to `VERIFIED_OPERATIONALLY` after ops proof

## Watchlist

See `watchlist.md`.
