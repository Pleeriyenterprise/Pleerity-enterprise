# Billing truth verification 02

Implementation SHA: `a9a2efd329f827f335ca2d759cfa2cf0fb883302`

## SUBSCRIPTION_CANCELED (Audit 01 P0)

**Root cause:** `access_end_date` derived from webhook processing time.

**Implementation:** `resolve_subscription_canceled_customer_copy` uses Stripe `ended_at` / `current_period_end` / `canceled_at` / `cancel_at_period_end`. Missing period → no invented date (“cannot confirm a precise access-end date”). Commercial overlay / `ENABLED` entitlement does not claim access has ended.

**Live staging:** no `invoice`/`customer.subscription.deleted` test webhook was injected. Local `.env` has no Stripe key. Staging `message_logs` had **0** `SUBSCRIPTION_CANCELED` rows at cert time. **Live send not proven.**

Unit: period-end copy uses 1 August 2026, not webhook “now”; missing period does not invent a date.

## PAYMENT_FAILED (Audit 01 P1)

**Root cause:** DB-first alias with no staging template row; generic “You have a new notification from Pleerity.”

**Implementation:** unconditional code-built HTML. States payment unsuccessful; names plan when present; does not claim suspension unless entitlement is `DISABLED`; Stripe retry labelled as Stripe retry **not** grace-period end; no invented retry date.

**Live staging:** 0 `PAYMENT_FAILED` message_logs. No production charge. No test-mode invoice.payment_failed fired. **Live send not proven.**

Webhook replay remains idempotent via `{event_id}_PAYMENT_FAILED` (existing orchestrator unique key).

## 7d / 3d renewal subjects (Audit 01 P1)

**Implementation:** `subscription_renewal_reminder_subject(days_until)` — “in 6 days” / “in 3 days” / “tomorrow”. Body uses the same `days_until`.

**Live analogue:** compliance EICR subject used calculated **4 days**, not a hardcoded “about 7 days”. Dedicated subscription 7d/3d job was not in a live window for a yopmail fixture.

## Stripe / entitlement table (code)

| Fixture | Stripe authority | Platform | Customer wording |
| --- | --- | --- | --- |
| Cancel at period end | `cancel_at_period_end` + period end | DISABLED | Access ended/ends on that date |
| Immediate cancel | `ended_at` / no remaining period | DISABLED | Access ended; no fabricated future date |
| Missing period | no trustworthy timestamp | DISABLED | Safe wording, no invented date |
| Payment failed + retry | `next_payment_attempt` if present | LIMITED | Retry is Stripe’s, not grace end |
| Payment failed, no retry | field absent | LIMITED | “no confirmed retry date”; access not suspended |
