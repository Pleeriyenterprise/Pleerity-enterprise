# Watchlist — onboarding recovery orchestration

## Before production sign-off

- [ ] Staging browser proof: admin execute + customer email + continuation landing
- [ ] Stripe webhook completes after continuation checkout
- [ ] No duplicate subscription created on recovery retry
- [ ] Fleet metrics endpoint returns sensible counters after test runs

## Known limits

- Fleet metrics mix global counters with recent-event sampling (30-day window).
- `VERIFIED_OPERATIONALLY` requires staging evidence — unit tests alone are insufficient.

## Do not regress

- Recover onboarding override alone does **not** constitute recovery complete.
- Recovery execute requires step-up, reason, and confirmation token.
