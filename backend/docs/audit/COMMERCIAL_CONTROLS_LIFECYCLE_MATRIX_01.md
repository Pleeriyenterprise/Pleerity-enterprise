# Commercial Controls — Lifecycle Matrix

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_LIFECYCLE_MATRIX_01.md`  
**Date:** 2026-08-15

## Governance vs canonical access

Commercial **governance_state** (exception truth) is distinct from **canonical_entitlement_state** (`ENABLED` / `GRACE` / `SUSPENDED` / `CANCELLED`).

Classification without an active exception (from billing signals):

| Billing / Stripe signal | Governance classification | Canonical baseline |
| --- | --- | --- |
| ACTIVE + active/renewing | `ACTIVE` | `ENABLED` |
| PAST_DUE / grace_period | `GRACE_PERIOD` | `GRACE` |
| UNPAID / expired / limited | `RESTRICTED` | `SUSPENDED` |
| CANCELED / cancelled | `TERMINATION_PENDING` | `CANCELLED` |
| INCOMPLETE / PAUSED | `PAYMENT_HOLD` | `GRACE` |
| Active exception present | exception `entitlement_state` | see bridge below |
| Exception past expiry (still active row) | `ENTITLEMENT_DRIFT` | baseline |

Bridge (`derive_customer_access_state`) when an exception is active:

| Exception state | Access policy | Canonical result |
| --- | --- | --- |
| GRACE / BILLING_SUSPENDED / SPONSORED / RETENTION / RECOVERY / WAIVED / ACTIVE | `full_access` | `ENABLED` **unless** baseline is `CANCELLED` (then stays `CANCELLED`) |
| RESTRICTED or policy `suspended` | `suspended` | `SUSPENDED` |
| PAYMENT_HOLD | — | `GRACE` |
| TERMINATION_PENDING | — | `CANCELLED` |

## Executable actions (current authority)

| Condition | Executable |
| --- | --- |
| Active governance row | `resume_billing`, `revoke_commercial_exception` only |
| No active row | All seven create-actions, **including from CANCELLED** |

Backend still rejects a second create with `ACTIVE_EXCEPTION_EXISTS`.

## Observed account (screenshot)

`TERMINATION_PENDING` + canonical `CANCELLED` + `full_access` + all seven buttons.

Suspend billing is **currently legal** in code. It will **not** restore `ENABLED`. Operator warning added; action not removed (policy decision).

## Recommended decision (not implemented)

| From state | Suspend billing | Grace / retention / sponsored | Restrict | Waive onboarding |
| --- | --- | --- | --- | --- |
| ENABLED / GRACE | Meaningful platform record; Stripe still collects in v1 | Meaningful if duration valid | Meaningful | Meaningful if fee unpaid |
| CANCELLED / TERMINATION_PENDING | Low meaning; billing already stopped | Does not restore access in v1 | Redundant | May still set waiver flags |

Until product decides, backend remains: any non-exception account may receive any create-action; cancelled access is not upgraded.

## Expiry

Job `commercial_entitlement_expiry` marks `active` → `expired` when `entitlement_expiry_at` ≤ now, clears client commercial fields, recomputes canonical from billing. Prior staging proof: 2026-06-01 (`VERIFIED_OPERATIONALLY` for expiry closeout). Not re-run this exercise.
