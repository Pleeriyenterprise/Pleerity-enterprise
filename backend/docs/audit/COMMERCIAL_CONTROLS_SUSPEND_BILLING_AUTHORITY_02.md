# Suspend Billing — Authority Model 02

**Audit ID:** `COMMERCIAL-CONTROLS-AUTHORITY-CORRECTION-AND-E2E-CERTIFICATION-02`  
**Date:** 2026-08-15

## Original plan authority (precedence)

Never infer from arbitrary frontend state. Never default unknown values to `PLAN_1_SOLO`.

| Order | Source | Why |
| --- | --- | --- |
| 1 | `client_billing.current_plan_code` | Stripe-synced plan on the billing record |
| 2 | `clients.billing_plan` | Canonical client plan mirror |
| 3 | `client_billing.plan_code` | Legacy billing plan field |
| 4 | `clients.plan_code` | Legacy client plan field |
| 5 | `clients.selected_plan` | Intake/selected plan aliases (`Solo`/`Portfolio`/`Professional`) |

`plan_registry.resolve_plan_code` is **not** used for this path because it maps unknown codes to Solo.

If no candidate resolves to `PLAN_1_SOLO` / `PLAN_2_PORTFOLIO` / `PLAN_3_PRO`:

- reject with `PLAN_UNRESOLVED`
- do not grant arbitrary full access
- surface the reason to the operator
- record `commercial_rejected`

## Stripe mechanism (verified against current architecture)

The platform previously recorded a platform pause flag and **did not** call Stripe. That is insufficient for a control named Suspend billing.

Current subscription model: Stripe Subscription objects with automatic collection. There was no existing `pause_collection` helper.

**Least disruptive truthful operation for a billable subscription:**

```text
stripe.Subscription.modify(sub_id, pause_collection={"behavior": "void"})
```

- Does not cancel the subscription.
- Does not recreate a subscription.
- Voids invoices generated while paused (customer is not charged).
- Webhook `customer.subscription.updated` persists `stripe_collection_paused` from the Stripe object; status remains `active`/`past_due`/`trialing`.

**Cancelled / incomplete_expired / unpaid / missing subscription id:**

```text
mutation = already_non_collecting
```

No Stripe recreate. Access restoration is platform-governed only.

If pause is required and Stripe fails: execute aborts **before** governance persist (`STRIPE_PAUSE_FAILED`). If persist fails after a successful pause, a compensating `pause_collection=""` resume is attempted.

**Expiry / revoke:** resume collection only when the underlying subscription remains billable. Cancelled accounts stay non-collecting.

Dunning / grace-mid reminders / renewal reminders / post-grace transitions skip rows with `commercial_billing_collection_paused`.

## State-specific behaviour

### ACTIVE

| Field | During exception | After expiry |
| --- | --- | --- |
| Underlying subscription | Unchanged (still valid) | Unchanged |
| Canonical | `ENABLED` | Recalculated from subscription |
| Effective access | Restored/current plan | Underlying |
| Stripe | `pause_collection` void | Resume collection |
| Billing | Not collected | Resumes if still billable |

### PAYMENT_DUE / DUNNING (`PAST_DUE` / grace)

| Field | During exception | After expiry |
| --- | --- | --- |
| Collection / dunning | Suspended (Stripe pause + job skip) | Returns to billing lifecycle |
| Access | Plan-equivalent via overlay | Underlying GRACE/SUSPENDED |

### CANCELLATION_PENDING (`cancel_at_period_end`)

| Field | During exception | After expiry |
| --- | --- | --- |
| Cancellation schedule | Preserved | Underlying path continues |
| Collection | Paused if still billable | Resume only if still billable |
| Access | Plan-equivalent | Underlying |

### CANCELLED

| Field | During exception | After expiry |
| --- | --- | --- |
| Canonical / Stripe sub | Remains cancelled | Remains cancelled |
| Effective access | Previous plan | Cancelled access again |
| Stripe mutation | None (`already_non_collecting`) | None (do not recreate) |

### TERMINATION_PENDING

Same overlay as cancelled when canonical is `CANCELLED`. Termination authority remains visible on lifecycle/governance classification. Exception does not erase records.

## Operator UX (cancelled)

`Suspend billing` stays executable. Warning copy states:

- the account is currently cancelled
- this creates a temporary commercial exception
- access is restored to the previous plan
- underlying cancellation remains
- expiry returns to cancelled unless another lifecycle event changes the account

Still required: step-up, support reason, duration, impact confirmation.

## Customer email

Generated from committed preview after Stripe result:

- Cancelled: temporary plan access restored; billing will not be collected; arrangement has an end date; underlying cancelled status applies after expiry. Subject: `Temporary access restored on your account`.
- Active: billing collection paused; plan access kept; underlying subscription status unchanged. Subject: `Billing temporarily paused on your account`.

Do not say the subscription was reactivated.
