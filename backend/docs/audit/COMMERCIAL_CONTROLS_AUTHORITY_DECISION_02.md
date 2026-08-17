# Commercial Controls — Authority Decision 02

**Audit ID:** `COMMERCIAL-CONTROLS-AUTHORITY-CORRECTION-AND-E2E-CERTIFICATION-02`  
**Date:** 2026-08-15  
**Branch:** `develop`  
**Decision:** Suspend billing remains available in all lifecycle states, including cancelled / termination-pending.

## Product decision

`Suspend billing` is an exceptional governed intervention. It is **not** hidden or disabled because the underlying subscription is `CANCELLED`.

The control must behave truthfully:

```text
Underlying lifecycle state
+
Active commercial exception
=
Effective access
```

Do **not** solve cancelled access by mutating `CANCELLED → ACTIVE` on the subscription or lifecycle state machine.

## What Suspend billing must do

1. Create a governed temporary commercial exception (`billing_suspension`).
2. Preserve the underlying subscription and lifecycle state.
3. Resolve the customer's last valid subscribed plan from platform authority (never invent Solo).
4. Grant **plan-equivalent** access for the exception duration (feature gates remain; no RBAC/superuser bypass).
5. Prevent actual billing collection where the subscription is still billable (`pause_collection` behavior `void`).
6. For already-cancelled Stripe subscriptions: **no recreation**; collection is already stopped; access is platform-governed.
7. Preserve customer records, evidence, compliance history, and entitlements belonging to that plan.
8. Record reason, duration, operator, previous state, restored plan, Stripe mutation, and resulting effective state.
9. Send a continuity email only when selected, generated from the committed result.
10. Expire automatically and recalculate effective state from the underlying lifecycle.

## What it must not do

- Falsify historical / canonical cancelled state.
- Tell the customer their subscription was reactivated if it remains cancelled.
- Claim Stripe collection is paused unless collection is actually prevented or already non-collecting.
- Grant unrestricted access when the previous plan cannot be resolved (`PLAN_UNRESOLVED` — reject and audit).
- Waive recurring charges via onboarding-fee waiver (separate control).

## Other six controls

The Suspend billing decision does **not** make every other control valid for every lifecycle. See `COMMERCIAL_CONTROLS_SUSPEND_BILLING_AUTHORITY_02.md` for Suspend billing and the lifecycle legality section in `COMMERCIAL_CONTROLS_E2E_CERTIFICATION_02.md`.

## Implementation mapping

| Concept | Storage / authority |
| --- | --- |
| Underlying canonical band | `canonical_entitlement_state` from Stripe/lifecycle (`ENABLED`/`GRACE`/`SUSPENDED`/`CANCELLED`) |
| Effective access | `commercial_effective_entitlement_state` |
| Restored plan | `commercial_restored_plan_code` + governance `restored_plan_code` |
| Collection pause (platform) | `commercial_billing_collection_paused` |
| Collection pause (Stripe) | `stripe_collection_paused` / `pause_collection.behavior=void` |
| Runtime | Runtime Contract keeps `lifecycle_state`; overlay sets `portal_mode=FULL_ACCESS` and plan-gated capabilities when effective=`ENABLED` |

## Verdict on this document

Authority is explicit. Runtime certification of the implemented authority is recorded separately.
