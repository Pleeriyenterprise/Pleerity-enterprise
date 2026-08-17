# Commercial Controls — Stripe `pause_collection.behavior=void` semantics 04

**Programme:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04`  
**Fixture:** lere `ce8d3b56-…` / `sub_1Tr2…` (test mode)  
**Pause applied:** 2026-08-15T20:43:11Z  
**Pause removed (expiry):** 2026-08-15T20:45:09–20:45:12Z  
**Authority unchanged:** still `pause_collection.behavior=void`. No silent switch.

03 documented the Stripe **contract** without a live pause (`COMMERCIAL_CONTROLS_STRIPE_RUNTIME_03.md`). This window applies that contract to a real test subscription.

## Intended product meaning

Temporary billing suspension on an ACTIVE subscription:

- collection paused for the exception duration;
- plan-equivalent access remains;
- underlying subscription status remains ACTIVE (not cancelled, not recreated);
- recurring invoices are not collected while paused;
- after expiry, collection resumes on the existing subscription.

## Live observations (this subscription)

| Question | Observation |
| --- | --- |
| Invoices existing before pause | Latest `in_1U2HX…` unchanged; not voided |
| Invoices generated during pause | **None** in the ~2 minute pause (next cycle 2026-09-08) |
| Would in-pause invoices become void? | Stripe contract: yes, immediately void; not live-invoiced this window |
| Collectible later? | Stripe contract: voided invoices stay void |
| After pause removal | Webhook `customer.subscription.updated` 20:45:12Z; subscription still ACTIVE; same `sub_*` |
| Next billing date | Unchanged 2026-09-08T21:11:39Z (`pause_collection` does not rewrite `current_period_end`) |
| Immediate invoice on resume | **No.** Same latest invoice; no open invoice |
| Unintended unpaid/free period | Pause sat inside an already-paid period ending 8 Sep. Resume did not skip or double the next cycle. Exception duration was minutes, not a gifted extra billing period. |
| Platform billing UI | Next billing date truthful. Classification BILLING_SUSPENDED / reason truthful while paused. GET billing `pause_collection` field lagged null during pause (projection gap; execute payload is authority). |
| Accounting / reconciliation | `billing_reconciliation_needed=false`; `stripe_reconciliation_status=reconciled_lightweight`; no duplicate sub/invoice |

## Stripe contract (unchanged)

`pause_collection.behavior=void` on an existing Subscription:

- invoices **created while paused** are marked void and are not later collectible;
- unsetting pause is not the Subscription Pause (`status=paused`) Resume API, so resume is not expected to invoice immediately;
- `current_period_end` is not itself moved by pause/unpause.

That matches the intended commercial outcome. Do **not** change `behavior=void` without a separate commercial decision.

## Not a blocker

Inability to mint a cycle invoice inside a two-minute test pause does not contradict the contract or the product meaning. A live void of an in-pause invoice remains a future optional observation (next invoice 8 Sep). It is not `BLOCKED_BY_SUSPEND_BILLING_FINANCIAL_SEMANTICS`.

## Verdict

```text
SEMANTICS_MATCH_INTENDED_OUTCOME
```
