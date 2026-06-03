# Watchlist

- Classification: **STRIPE_PRICE_CONFIG_DRIFT**
- [ ] **P0:** On Render (production), set three **distinct** `STRIPE_LIVE_PRICE_PLAN_*_MONTHLY` values (Solo £19, Portfolio £39, Pro £79)
- [ ] Re-run `python backend/scripts/billing_stripe_price_config_verify_01.py` after env fix
- [ ] Capture Stripe checkout screenshots (Solo/Portfolio/Professional) and back-button → `/settings/billing`
- [ ] Confirm `STRIPE_TEST_PRICE_*` distinct on any test-mode deployment
- [ ] Optional: set `STRIPE_SECRET_KEY_LIVE` on verify runner for automated cancel_url metadata proof
