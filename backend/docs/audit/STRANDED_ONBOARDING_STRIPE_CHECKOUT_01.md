# Stranded onboarding — Stripe checkout 01

- Recovery sessions are created with the existing `StripeService.create_checkout_session`.
- Previous session is expired via `expire_checkout_session` before the new session is created.
- Old/new session IDs are stored on `recovery_checkout_context`.
- Discounts are server-applied invite discounts only.
- `allow_promotion_codes` is not used.
- Paid/active clients cannot regenerate payment (`CLIENT_ALREADY_ACTIVE`).
- Webhook idempotency is unchanged; superseded sessions should not complete after expire.

Staging Stripe payment-through-provisioning was **not** completed. A **paid** (no promo) recovery session **was** created on staging test mode (`cs_test_b1jZQrXm…` / later `cs_test_b1jZQrXm06D8eyPipCpyIQe4VEqeIKqNmnKQmXzcu30UqIhrwjn25gSBCH`). Hosted Checkout showed £68.00 and no customer-entered promotion-code control.

Applying `PILOTACCESS` on staging test keys fails because coupon `85x6smtg` exists only in live mode. After `ccd87cc3` this is `409 STRIPE_PROMO_MODE_MISMATCH`, not HTTP 500.
