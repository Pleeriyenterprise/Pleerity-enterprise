# Commercial Controls — Stripe Reconciliation

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_STRIPE_RECONCILIATION_01.md`  
**Date:** 2026-08-15

## v1 posture (existing, not redesigned)

`reconcile_entitlement_billing_state`:

> Does not mutate Stripe subscriptions or pause_collection.

`reconcile_stripe_vs_platform_state` writes `stripe_reconciliation_status=reconciled_lightweight` and a plan (`no_action` / `sync_canonical_entitlement_to_client` / `expire_governance`).

Platform governance is authoritative for exceptions. Stripe remains the subscription/collection processor unless a later governed Stripe action exists.

## Classification per control

| Control | Classification | Actual Stripe object change |
| --- | --- | --- |
| Grant grace period | `NO_STRIPE_ACTION` | None |
| Suspend billing | `NO_STRIPE_ACTION` (not `STRIPE_BILLING_PAUSE`) | None. Live subscriptions can still invoice. |
| Sponsored access | `NO_STRIPE_ACTION` | None |
| Retention extension | `NO_STRIPE_ACTION` | None |
| Waive onboarding fee | `NO_STRIPE_ACTION` on the subscription; checkout **omits** onboarding price when `onboarding_fee_waived` (this fix) | No invoice rewrite of past charges |
| Recovery compensation | `NO_STRIPE_ACTION` — not `STRIPE_CREDIT` | None. Not a balance credit. |
| Restrict entitlement | `NO_STRIPE_ACTION` | None |

Observed cancelled account (`customer.subscription.deleted`): Stripe is already not collecting. Suspend billing on that account does not change Stripe and does not restore access.

## Operator / customer claims

Before this fix, the modal preview said “Billing collection paused.” while `stripe_impact` said Stripe is not mutated. That combination is unsafe.

After this fix, operator `billing_impact` states Stripe is not mutated in v1.

**Do not tell operators or customers that Stripe collection has stopped unless `pause_collection` (or equivalent) is implemented and verified on the Stripe object.** That implementation is a commercial authority decision, not part of this diff.

## Reconciliation observability

Governance fields: `stripe_reconciliation_status`, `stripe_action_plan`. Assessment `drift` when stored canonical ≠ derived canonical, or governance past expiry.

This run did not retrieve a live Stripe subscription after execute (staging login locked).
