# Commercial Controls — Suspend billing authority (runtime 03)

**Runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`

This note records **runtime** against the 02 authority. Implementation was not redesigned.

## Authority (unchanged)

- Canonical lifecycle is not rewritten (`CANCELLED` stays `CANCELLED`).
- Active exception restores plan-equivalent **effective** access.
- Billable Stripe: `pause_collection.behavior = void` before persist.
- Cancelled / missing / non-collecting Stripe: `already_non_collecting`; no subscription recreate.
- Unknown plan: `PLAN_UNRESOLVED` reject; never invent Solo.
- Stripe failure: abort before persist (`STRIPE_PAUSE_FAILED`).

## Runtime vs authority

| Claim | Runtime 03 |
| --- | --- |
| Cancelled remains cancelled | **PASS** (allison@yopmail.com) |
| Effective ENABLED + previous plan | **PASS** `PLAN_3_PRO` |
| No Stripe recreate | **PASS** `already_non_collecting` |
| Email describes temporary access | **PASS** |
| Expiry returns cancelled behaviour | **PASS** |
| ACTIVE pause_collection void | **NOT APPLIED** — Stripe `No such subscription` on all probed ACTIVE ids |
| Fail closed on Stripe error | **PASS** — 502, no exception |
| PLAN_UNRESOLVED | **UNVERIFIED** — no fixture |

**Conclusion:** Do not change Suspend Billing authority. Staging lacks live Stripe subscription objects for ACTIVE accounts. `behavior=void` was not shown to mismatch the intended commercial outcome because it was never successfully applied.
