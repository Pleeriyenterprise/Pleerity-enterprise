# Commercial Controls — Stripe runtime 03

**Runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`

Suspend Billing authority was **not** changed. Live evidence did not prove an implementation defect in `pause_collection.behavior = void`. It proved staging subscription IDs are missing from the connected Stripe account.

## ACTIVE billable path — not completed

Platform correctly called Stripe before persist. Stripe rejected missing objects. Execute returned **502** `STRIPE_PAUSE_FAILED`. No commercial exception was persisted (`commercial_rejected`). That is atomic failure, not a false success.

| Fixture | Stripe id prefix | Stripe result |
| --- | --- | --- |
| drjpane@gmail.com `ec0b091b-…` | `sub_1T53…` | `No such subscription` |
| nancy@yopmail.com `6fd5ac4c-…` | `sub_1TI7…` | `No such subscription` |
| olivia.chen@oxfordlets.co.uk | `sub_1T3H…` | `No such subscription` |
| anya.sharma@gmail.com | `sub_1T2T…` | `No such subscription` |

Probed ACTIVE rows all had `current_period_end` in the past (May–June 2026). UI billing for Alistair Campbell shows next billing **26/05/2026** and last webhook **26 Apr 2026**. There was no controlled staging subscription whose Stripe object still exists.

`pause_collection` was therefore **not** applied on a live billable subscription in this exercise.

## CANCELLED path — completed

Client `5db7bba1-ed9d-444e-9e0d-b7478d5b566b` (allison@yopmail.com), previous plan `PLAN_3_PRO`.

| Axis | After execute | SHA |
| --- | --- | --- |
| Canonical lifecycle | `CANCELLED` | `7c77391a` |
| Effective entitlement | `ENABLED` | `7c77391a` |
| Restored plan | `PLAN_3_PRO` | `7c77391a` |
| Stripe mutation | `already_non_collecting` | `7c77391a` |
| Subscription recreation | none | `7c77391a` |
| Collection attempt | none | `7c77391a` |

## `behavior = void` financial semantics (Stripe contract; not live-invoiced here)

Because implementation uses `pause_collection.behavior = void`:

| Question | Documented Stripe / implementation behaviour | Live in this window |
| --- | --- | --- |
| Invoices generated during suspension | Stripe immediately marks them **void** | **Not observed** (pause never applied) |
| Automatically voided? | Yes, for invoices created while void-paused | Not observed |
| Collectible later? | No — voided invoices stay void | Not observed |
| When pause is removed | Future invoices collect again; voided ones stay void | Not observed |
| Next billing date | `pause_collection` does not itself change `current_period_end` | Not observed |
| Immediate invoice on resume | Unsetting `pause_collection` is not the Subscription Pause (`status=paused`) Resume API; an unexpected immediate invoice is not expected from this path | Not observed |
| Unintended free service | Void pause offers service without collecting those invoices for the exception duration; expiry must restore collection on still-billable subs | Expiry resume not exercised (no successful pause) |
| Accounting truth | Platform must not claim collection paused unless Stripe accepted pause | **Honoured:** ACTIVE path refused rather than claiming pause |

**Do not certify ACTIVE Suspend Billing as PASS** from Stripe API acceptance: the API did **not** accept pause. Do not change `behavior=void` based on this window; the intended commercial outcome was never applied because the subscription objects are absent.

## Failure atomicity (Stripe)

`STRIPE_PAUSE_FAILED` → HTTP 502 → no active exception → `commercial_rejected`. `billing_reconciliation_needed` may be marked (`pause_collection_stripe_error`) so platform/Stripe drift is reconcilable. That is a governed reconciliation flag, not a commercial exception overlay.
