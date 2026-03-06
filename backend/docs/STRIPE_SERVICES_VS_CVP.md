# Stripe setup for services (order intake) vs CVP

## Do services use the same Stripe secrets and env as CVP?

**Yes.** Services (MR_BASIC, DOC_PACK_*, etc.) and CVP (Compliance Vault Pro / subscription) share:

| Env variable | Used by | Purpose |
|-------------|--------|---------|
| `STRIPE_SECRET_KEY` or `STRIPE_API_KEY` | Both | Stripe API secret key (one key per Stripe account). |
| `STRIPE_WEBHOOK_SECRET` (or `STRIPE_WEBHOOK_SECRET_TEST` / `STRIPE_WEBHOOK_SECRET_LIVE`) | Both | Verify webhook signatures. **One webhook endpoint** receives both CVP subscription events and order-intake payment events; the handler routes by `checkout.session.mode` and `metadata.type` (`order_intake` vs subscription). |

**CVP-only env (services do not need these):**

- `STRIPE_TEST_PRICE_PLAN_*_MONTHLY`, `STRIPE_LIVE_PRICE_PLAN_*_*` — CVP subscription plan Price IDs.  
  Services checkout uses **dynamic** `price_data`, not pre-created Price IDs.

So: same Stripe account, same secret key, same webhook secret. No separate Stripe app or env set for services.

---

## What to add or create in Stripe for services

### Minimum (what you need for checkout to work)

- **Stripe Dashboard:** Nothing. No Products or Prices need to be created for services.
- **Env:** Set `STRIPE_SECRET_KEY` or `STRIPE_API_KEY` to a valid Stripe **secret key** (Developers → API keys; use test key for non-live).
- **Webhook:** Configure one endpoint (e.g. `https://your-api/api/webhooks/stripe`) with the same webhook signing secret you use for CVP. No separate webhook for services.

The current flow builds the Checkout Session with **dynamic** `price_data` (product name + amount in pence from the draft’s `pricing_snapshot`). Stripe creates the product on the fly; no pre-created Products or Prices are required.

### Optional (Stripe Products/Prices for reporting or future use)

If you want each service to exist in Stripe as a Product with fixed Prices (e.g. for Stripe reporting or a future switch to Price IDs):

1. **Stripe Dashboard:** Either create Products/Prices by hand, or use the script below.
2. **Script:** From the backend directory, with `STRIPE_SECRET_KEY` or `STRIPE_API_KEY` and `MONGO_URL` set:
   - `python scripts/setup_stripe_products.py` — creates one Product per service and Prices per variant (standard, fast_track, printed where applicable).
   - `python scripts/setup_stripe_products.py --sync-db` — same, then writes Stripe Price IDs into `service_catalogue_v2.pricing_variants[].stripe_price_id`.

The script’s service list is in `SERVICE_STRIPE_CONFIG` (e.g. MR_BASIC, DOC_PACK_ESSENTIAL, DOC_PACK_PLUS, DOC_PACK_PRO). **Running this script is optional;** today’s checkout does not use these Price IDs; it still uses dynamic `price_data` from the draft.

---

## Summary

| Question | Answer |
|----------|--------|
| Same Stripe secrets/env as CVP? | Yes. Same `STRIPE_SECRET_KEY`/`STRIPE_API_KEY` and same `STRIPE_WEBHOOK_SECRET` (or test/live pair). |
| What to create in Stripe for services? | **Required:** Nothing in the Dashboard; only a valid secret key in env. **Optional:** Run `setup_stripe_products.py` to create Products/Prices and optionally sync to DB. |
| Separate webhook for services? | No. One webhook; handler distinguishes order intake (`metadata.type === "order_intake"`) from CVP subscription. |
