# Stripe Live → Test clone (services intake, non-CVP)

## Script

`backend/scripts/clone_stripe_live_to_test.py`

**Environment (run locally or CI; never commit keys):**

| Variable | Purpose |
|----------|---------|
| `STRIPE_LIVE_SECRET_KEY` | `sk_live_...` — read-only listing of Live products/prices |
| `STRIPE_TEST_SECRET_KEY` | `sk_test_...` — creates products/prices in Test |

```bash
cd backend
python scripts/clone_stripe_live_to_test.py --dry-run
python scripts/clone_stripe_live_to_test.py
```

**What gets cloned:** Products whose metadata includes `service_code` in the intake catalogue (AI automation, market research, compliance audits, document packs) or `addon_code` (`FAST_TRACK`, `PRINTED_COPY`). Everything else on Live is skipped (including CVP subscription products without those codes).

**Output:** `backend/seed/stripe_live_to_test_map.json` — `product_id_map` and `price_id_map` from Live ID → Test ID.

Live data is **never** deleted or updated.

---

## Webhooks, API keys, and what to set where

| Concern | Test mode | Live mode |
|---------|-----------|-----------|
| **Backend `STRIPE_SECRET_KEY` / `STRIPE_API_KEY`** | Use **`sk_test_...`** when developing/staging intake & orders | Use **`sk_live_...`** in production |
| **Stripe webhook endpoint** | **Separate** Test endpoint in Dashboard → Developers → Webhooks (Test mode toggle) | **Separate** Live endpoint |
| **Webhook signing secret** | `STRIPE_WEBHOOK_SECRET_TEST` (or `STRIPE_WEBHOOK_SECRET` if only one env) | `STRIPE_WEBHOOK_SECRET_LIVE` |
| **CVP subscription checkout** | Uses same key variables; must match mode (test key → test prices/webhook) | Live key → live webhook |

Intake order checkout (`checkout.session.completed` for `type=order_intake`) uses **whatever key the backend uses**. After cloning Live→Test:

1. Point **staging** backend at **test** secret key.
2. In Stripe **Test** Dashboard, add webhook URL (e.g. `https://your-staging-api/api/webhooks/stripe`) and subscribe at least to `checkout.session.completed`.
3. Put the **Test** webhook signing secret in `STRIPE_WEBHOOK_SECRET_TEST` (see `stripe_webhook_service.py`).
4. Update **MongoDB `service_catalogue_v2`** (or env price overrides) so **`stripe_price_id` values are Test price IDs** in staging — the clone script’s map file is the reference; catalogue must align with the key mode.

**Do not** reuse Live price IDs with a Test secret key (Stripe returns 400). **Do not** point Test webhooks at production-only secrets without matching mode.

---

## Manual steps after clone

1. Copy Test `price_...` IDs from `stripe_live_to_test_map.json` into the correct `pricing_variants[].stripe_price_id` for each service in the DB (or use env-based test price vars if your deployment uses them).
2. Re-run staging checkout end-to-end and confirm webhook delivery in Stripe Dashboard → Webhooks → Test.
