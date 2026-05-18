# Stripe mode governance

Canonical authority for **live** vs **test** Stripe billing. The platform must never mix live and test API keys, webhooks, prices, or coupons in a single runtime.

## Authoritative configuration

| Variable | Values | Role |
|----------|--------|------|
| `STRIPE_MODE` | `live` \| `test` | **Required for production.** Selects which Stripe account mode the deployment uses. |

Implementation: `services/stripe_mode_authority.py`

### Backend secrets (never expose to frontend)

| Mode | Secret API key | Webhook signing secret |
|------|----------------|------------------------|
| Live | `STRIPE_SECRET_KEY_LIVE` | `STRIPE_WEBHOOK_SECRET_LIVE` |
| Test | `STRIPE_SECRET_KEY_TEST` | `STRIPE_WEBHOOK_SECRET_TEST` |

Legacy (deprecated): `STRIPE_SECRET_KEY` / `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` — accepted **only** when the key prefix matches `STRIPE_MODE`. No cross-mode fallback.

### Frontend (build-time)

| Mode | Publishable key |
|------|-----------------|
| Live | `REACT_APP_STRIPE_PUBLISHABLE_KEY_LIVE` |
| Test | `REACT_APP_STRIPE_PUBLISHABLE_KEY_TEST` |

Legacy: `REACT_APP_STRIPE_PUBLISHABLE_KEY` (must match `STRIPE_MODE` prefix).

CVP checkout is **hosted** (redirect to Stripe Checkout); publishable keys are still checked for operational alignment and future Elements use.

### Plan price IDs

Mode-prefixed env vars (unchanged):

- Test: `STRIPE_TEST_PRICE_PLAN_*_MONTHLY`, `STRIPE_TEST_PRICE_PLAN_*_ONBOARDING`
- Live: `STRIPE_LIVE_PRICE_PLAN_*_MONTHLY`, `STRIPE_LIVE_PRICE_PLAN_*_ONBOARDING`

Loaded only for the active `STRIPE_MODE`.

## Environment strategy

| Environment | Recommended `STRIPE_MODE` | Notes |
|-------------|---------------------------|--------|
| Production | `live` | Live keys, live webhooks, live prices, live pilot coupons |
| Staging / dev | `test` | Test Dashboard objects only |
| Live E2E with real cards | `live` | Use **100% pilot coupons** — never test coupons in live mode |

Do **not** infer mode from “whichever key is set”. Set `STRIPE_MODE` explicitly on every deployment.

## Webhook endpoints

Configure Stripe Dashboard webhooks to point at:

- `POST /api/webhook/stripe` (primary)
- `POST /api/webhooks/stripe` (alias)

Use the signing secret that matches the endpoint’s Stripe mode:

- Test endpoint → `STRIPE_WEBHOOK_SECRET_TEST` when `STRIPE_MODE=test`
- Live endpoint → `STRIPE_WEBHOOK_SECRET_LIVE` when `STRIPE_MODE=live`

The handler rejects events whose `livemode` flag does not match `STRIPE_MODE`.

Non-production may skip verification if no secret is set (fail-closed in production).

## Mixed-mode protection

Blocked at runtime:

- `STRIPE_MODE=live` with `sk_test_*` secret
- Coupon/promotion validated in opposite mode (`livemode` on Stripe object)
- Webhook `livemode` mismatch
- Checkout price env vars for wrong mode (`STRIPE_MODE_MISMATCH`)

Admin operational config (`GET /api/admin/pilot-invites/operational-config`) reports:

- `mode_badge`: `LIVE MODE` / `TEST MODE`
- `warnings` / `errors` (no secret values)
- `frontend_alignment` status

## Deployment checklist

1. Set `STRIPE_MODE=live` or `test`
2. Set mode-specific secret + webhook secret
3. Set all `STRIPE_{MODE}_PRICE_*` vars for that mode
4. Build frontend with matching `REACT_APP_STRIPE_PUBLISHABLE_KEY_{MODE}`
5. Confirm admin **Founding Pilot Invites** ops card shows green checks and no errors
6. Register Stripe webhook with matching signing secret

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `STRIPE_MODE_MISMATCH` on checkout | Price env vars missing for active mode |
| Coupon not found on validate | Coupon created in opposite Stripe mode |
| Webhook signature failed | Webhook secret does not match `STRIPE_MODE` or endpoint mode |
| `Webhook mode mismatch` | Test event sent to live deployment (or reverse) |
| Admin shows legacy inferred mode | `STRIPE_MODE` unset — set explicitly |

## Live testing with pilot coupons

1. `STRIPE_MODE=live`
2. Create **live** coupons/promotion codes in Stripe Dashboard
3. Validate via admin **Validate Stripe** before distributing invites
4. Use 100% repeating coupons for safe conversion testing without charging

See also: `PILOT_INVITE_STRIPE_CHECKOUT.md`, `STRIPE_SERVICES_VS_CVP.md`.
