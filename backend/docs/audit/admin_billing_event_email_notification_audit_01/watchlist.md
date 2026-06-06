# Admin billing email watchlist

## Open items

1. **Failed checkout admin alert** — No `checkout.session.expired` webhook handler; consider isolated admin alert if product requires it.
2. **Staging recipient** — Confirm `ADMIN_ALERT_EMAILS` on `pleerity-api` Render service.
3. **First-payment fix deploy** — Redeploy backend so `on_checkout_completed` admin alert is live.
4. **Routine renewal policy** — Confirm digest-only for standard monthly renewals is acceptable ops policy.

## Verified paths

- `SUBSCRIPTION_FIRST_PAYMENT` → `INTERNAL_ALERT` (post-fix)
- `SUBSCRIPTION_RENEWAL_FAILED` → `INTERNAL_ALERT` (first in incident)
- `SUBSCRIPTION_CANCELLED` → `INTERNAL_ALERT`
- Recovery after failure → immediate renewal alert
- `STRIPE_WEBHOOK_FAILURE_ADMIN` on webhook processing errors
