# Stranded onboarding — Stripe checkout 01

- Recovery sessions are created with the existing `StripeService.create_checkout_session`.
- Previous session is expired via `expire_checkout_session` before the new session is created.
- Old/new session IDs are stored on `recovery_checkout_context`.
- Discounts are server-applied invite discounts only.
- `allow_promotion_codes` is not used.
- Paid/active clients cannot regenerate payment (`CLIENT_ALREADY_ACTIVE`).
- Webhook idempotency is unchanged; superseded sessions should not complete after expire.

Staging Stripe payment-through-provisioning was **not** re-run in this exercise.
