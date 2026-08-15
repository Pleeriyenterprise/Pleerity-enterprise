# Commercial Controls — Lifecycle legality (other six) and E2E certification 02

**Audit ID:** `COMMERCIAL-CONTROLS-AUTHORITY-CORRECTION-AND-E2E-CERTIFICATION-02`  
**Date:** 2026-08-15  
**Source SHA at implementation:** pending commit on `develop`

## Other six controls — legality (code + product semantics)

Suspend billing being available in every lifecycle does **not** imply the same for every other control. All seven remain **executable** whenever there is no active exception (including cancelled). Warnings are operator-facing; backend does not currently hard-block by lifecycle except `PLAN_UNRESOLVED` / `ACTIVE_EXCEPTION_EXISTS` / validation.

### Grant grace period

| Axis | Authority |
| --- | --- |
| Valid states | No active exception. Intended for payment-risk / access continuity. |
| Invalid states | Second exception (`ACTIVE_EXCEPTION_EXISTS`). |
| Resulting access | Continuity overlay: effective `ENABLED`, plan-equivalent. Cancelled canonical stays `CANCELLED`. |
| Billing | Collection continues unless a separate suspend is in force (cannot combine while one exception is active). |
| Duration | Required, max 30 days. |
| Expiry | Overlay cleared; underlying lifecycle resumes. |
| Email | Access extended; not a reactivation claim. |
| Stripe | No pause/recreate. |
| Audit | `commercial_granted` / reject path `commercial_rejected`. |
| Policy note | Grace on a fully cancelled account is **executable** with a warning. Whether that is commercially desirable vs Suspend billing is a product choice; behaviour is the continuity overlay, not a Stripe uncancel. |

### Sponsored access

| Axis | Authority |
| --- | --- |
| Valid states | No active exception; sponsor reference + duration/expiry required. |
| Resulting access | Continuity overlay, plan-equivalent. |
| Billing | Continues (not a collection pause). |
| Duration | Max 90 days; review required. |
| Stripe | No mutation. |
| Policy note | Sponsorship on cancelled accounts is allowed by code; it is access continuity, not a paid reactivation. |

### Retention extension

| Axis | Authority |
| --- | --- |
| Valid states | No active exception. |
| Resulting access | Continuity overlay. |
| Billing | Continues. |
| Duration | Max 30 days. |
| Stripe | No mutation. |

### Waive onboarding fee

| Axis | Authority |
| --- | --- |
| Valid states | No active exception. |
| Resulting access | **Does not** overlay `ENABLED` on cancelled. Persists existing onboarding-fee-waiver flags only. |
| Billing | Does **not** waive recurring subscription charges. |
| Duration | Max 30 days (exception row); waiver flags persist per existing onboarding authority. |
| Stripe | No recurring-price mutation. |
| Email | Onboarding fee update copy. |

### Recovery compensation

| Axis | Authority |
| --- | --- |
| Valid states | No active exception. |
| Resulting access | Continuity overlay (time-bound access), **not** a Stripe credit/refund. |
| Billing | Continues unless separately suspended. |
| Duration | Max 30 days. |
| Stripe | No credit API. Documented product gap if finance expects a Stripe credit. |

### Restrict entitlement

| Axis | Authority |
| --- | --- |
| Valid states | No active exception. |
| Resulting access | Effective `SUSPENDED` (not ENABLED overlay). |
| Billing | Continues. |
| Duration | Max 30 days. |
| Stripe | No mutation. |
| Cancelled | Restriction is redundant for access (already cancelled); records are not deleted. |

## Certification matrix

| Control | UI | Step-up | API | DB | Authority | Access | Stripe | Email | Audit | Expiry | Refresh | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Grant grace period | code | code | code | code | documented | unit | code-path | code | code | code | code | unverified-runtime |
| Suspend billing | code | code | code | code | implemented | unit | implemented | implemented | code | implemented | code | unverified-runtime |
| Sponsored access | code | code | code | code | documented | unit | n/a-mutation | code | code | code | code | unverified-runtime |
| Retention extension | code | code | code | code | documented | unit | n/a-mutation | code | code | code | code | unverified-runtime |
| Waive onboarding fee | code | code | code | code | documented | unit | no recurring waive | code | code | code | code | unverified-runtime |
| Recovery compensation | code | code | code | code | documented | unit | no Stripe credit | code | code | code | code | unverified-runtime |
| Restrict entitlement | code | code | code | code | documented | unit | n/a-mutation | code | code | code | code | unverified-runtime |

No row is PASS while a required column is code-path-only. Staging runtime proof is still required.

## Unit tests run (implementation)

```text
tests/test_commercial_entitlement_governance.py
tests/test_entitlement_access_and_billing_payload.py
tests/test_account_lifecycle_runtime_contract.py
tests/test_admin_action_governance_policy.py
→ 72 passed
```
