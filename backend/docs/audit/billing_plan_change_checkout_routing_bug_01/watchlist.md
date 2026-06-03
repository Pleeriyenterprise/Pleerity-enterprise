# Watchlist

- Classification: **VERIFIED_OPERATIONALLY**
- [ ] Deploy backend + frontend to staging/production
- [ ] Post-deploy: verify Solo/Portfolio/Professional Stripe amounts on live keys (env price IDs must be distinct)
- [ ] Post-deploy: capture Stripe back-button → `/settings/billing` screenshots
- [ ] If Portfolio still shows for all plans after deploy, audit Render `STRIPE_LIVE_PRICE_*_MONTHLY` / `STRIPE_TEST_PRICE_*_MONTHLY` for duplicate values
