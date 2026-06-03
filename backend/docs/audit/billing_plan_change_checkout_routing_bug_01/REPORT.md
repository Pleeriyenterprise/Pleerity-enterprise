# BILLING-STRIPE-PRICE-CONFIG-VERIFY-01

**Classification:** **STRIPE_PRICE_CONFIG_DRIFT**

## Summary

Routing fix `0f06cb8c` is **deployed** and **regression tests pass**. Live deployment **blocks plan-change checkout** because all three `STRIPE_LIVE_PRICE_*_MONTHLY` env values resolve to the **same** Stripe price ID. That explains Portfolio £39 appearing for every plan selection — it is **configuration drift**, not application routing logic.

## Deploy

| Component | Result |
|-----------|--------|
| Backend `/api/version` | `0f06cb8c009a65c25ba40cbe7d70ab07835defcd` |
| Frontend | `https://pleerityenterprise.co.uk` reachable (200) |

## Stripe price config (live)

**API proof:** `POST /api/billing/checkout` returns **400** `STRIPE_MODE_MISMATCH`:

> Duplicate Stripe subscription price IDs detected for live mode. Each plan must map to a distinct STRIPE_{mode}_PRICE_*_MONTHLY value.

**Remediation (Render env):** assign **three distinct** live monthly price IDs:

- `STRIPE_LIVE_PRICE_PLAN_1_SOLO_MONTHLY` → Solo **£19**/mo
- `STRIPE_LIVE_PRICE_PLAN_2_PORTFOLIO_MONTHLY` → Portfolio **£39**/mo
- `STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY` → Professional **£79**/mo

Also verify test-mode vars if `STRIPE_MODE=test` on any environment.

## Checkout session / UX proof

Blocked by config guard until env is fixed. No Stripe screenshots captured (checkout sessions not created).

## Live subscriber guardrail

- No `stored_stripe_mode=live` rows on staging sample
- Unit test `test_create_upgrade_session_verified_live_uses_portal_not_deployment_checkout` **passes**

## Code status

**No further billing code changes required** for this finding — `0f06cb8c` duplicate-ID guard is working as designed.
