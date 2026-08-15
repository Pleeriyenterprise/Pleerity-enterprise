# Commercial Controls — Stripe runtime 02

**Runtime status:** **UNVERIFIED** (no live Stripe object refetch after execute)

## Implemented (code + unit)

Billable subscription: `stripe.Subscription.modify(..., pause_collection={"behavior": "void"})` before governance persist.

Cancelled / incomplete_expired / unpaid / missing sub: `mutation=already_non_collecting`; no recreate.

Webhook/billing sync persists `stripe_collection_paused` from the Stripe subscription object.

Expiry/revoke resume collection only if underlying subscription remains billable.

Dunning, renewal reminders, and post-grace transitions skip `commercial_billing_collection_paused`.

## Required live proof (not captured)

| Account | Required |
| --- | --- |
| ACTIVE | pause_collection applied; no unintended invoice collection |
| CANCELLED | no subscription recreation; platform overlay only |

Stripe IDs must be recorded without secrets.
