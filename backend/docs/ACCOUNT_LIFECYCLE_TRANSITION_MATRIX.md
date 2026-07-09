# Account Lifecycle Transition Matrix

**Programme:** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01  
**Authority version:** `account_lifecycle_policy_v1`  
**Parent:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`

---

## Purpose

Every supported lifecycle transition has a governed contract. **No transition may be undefined.**

Each transition specifies: trigger, authority, validation, preconditions, postconditions, portal mode, and downstream effects.

---

## Transition authority model

| Role | Owner |
|------|-------|
| **State resolver** | Future `AccountLifecycleResolver` (consumes Stripe facts + billing + org) |
| **Payment transitions** | Stripe webhooks → `billing_stripe_sync_service` → `subscription_lifecycle_service` |
| **Org transitions** | `client_lifecycle_service` |
| **Admin transitions** | Admin API with audit |
| **Portal mode** | Derived from resolved `account_lifecycle_state` |

**Policy:** Only the resolver may write `account_lifecycle_state`. Subsystems react to events.

---

## Core transition catalogue

### T-001: Account creation

| Field | Policy |
|-------|--------|
| From | — |
| To | `PAYMENT_PENDING` or `TRIAL` |
| Trigger | Registration / admin provision / checkout start |
| Authority | Onboarding + billing |
| Validation | Unique org, plan selected |
| Preconditions | None |
| Postconditions | `ACCOUNT_CREATED` event; portal `PAYMENT_REQUIRED` or `FULL_ACCESS` |
| Portal mode | `PAYMENT_REQUIRED` or `FULL_ACCESS` |
| Authentication | Issue JWT |
| Entitlements | Plan matrix initialised |
| Sessions | New session |
| Background jobs | Pause until ACTIVE |
| Reports | None |
| Notifications | Welcome |
| Emails | Welcome / verify |
| SMS | If opted in |
| Timeline | Account created |
| Audit events | `ACCOUNT_CREATED` |
| Recovery | N/A |
| Rollback | Admin delete draft |

---

### T-002: Trial started

| Field | Policy |
|-------|--------|
| From | `PAYMENT_PENDING` |
| To | `TRIAL` |
| Trigger | Stripe `TRIALING` webhook |
| Authority | Stripe → lifecycle sync |
| Postconditions | `TRIAL_STARTED`; portal `FULL_ACCESS` |
| Portal mode | `FULL_ACCESS` |
| Background jobs | Resume on ACTIVE path |

---

### T-003: Trial → Active (conversion)

| Field | Policy |
|-------|--------|
| From | `TRIAL` |
| To | `ACTIVE` |
| Trigger | Successful first payment |
| Authority | Stripe `invoice.paid` |
| Postconditions | `SUBSCRIPTION_STARTED`; full entitlements |
| Portal mode | `FULL_ACCESS` |
| Notifications | Subscription confirmed |

---

### T-004: Trial expired

| Field | Policy |
|-------|--------|
| From | `TRIAL` |
| To | `TRIAL_EXPIRED` |
| Trigger | Trial end without payment |
| Authority | Stripe `customer.subscription.updated` / period end |
| Postconditions | `TRIAL_EXPIRED`; pause jobs |
| Portal mode | `PAYMENT_REQUIRED` |
| Sessions | Valid; refetch contract |
| Emails | Trial ended |

---

### T-005: Active → Payment failed

| Field | Policy |
|-------|--------|
| From | `ACTIVE` |
| To | `PAYMENT_FAILED` |
| Trigger | Stripe `invoice.payment_failed` |
| Authority | Stripe webhook |
| Postconditions | `PAYMENT_FAILED` event |
| Portal mode | `FULL_ACCESS` + warning banner |
| Notifications | Payment failed |
| Emails | Payment failed |

---

### T-006: Payment failed → Grace

| Field | Policy |
|-------|--------|
| From | `PAYMENT_FAILED` |
| To | `GRACE_PERIOD` |
| Trigger | Grace window entered (`billing_lifecycle_state: grace_period`) |
| Authority | `subscription_lifecycle_service` |
| Validation | Within configured grace days |
| Postconditions | `GRACE_STARTED`; canonical `GRACE` |
| Portal mode | `GRACE` |
| Sessions | Valid |
| Background jobs | Continue (limited side-effects) |
| Emails | Grace notice |

---

### T-007: Grace → Active (payment recovered)

| Field | Policy |
|-------|--------|
| From | `GRACE_PERIOD` |
| To | `ACTIVE` |
| Trigger | Successful payment |
| Authority | Stripe `invoice.paid` |
| Postconditions | `PAYMENT_RECOVERED`; canonical `ENABLED` |
| Portal mode | `FULL_ACCESS` |
| Sessions | Valid; entitlements_version++ |
| Background jobs | Resume full |
| Notifications | Payment success |
| Timeline | Payment recovered |

---

### T-008: Grace → Suspended

| Field | Policy |
|-------|--------|
| From | `GRACE_PERIOD` |
| To | `SUSPENDED` |
| Trigger | Grace window elapsed |
| Authority | `subscription_lifecycle_service` |
| Postconditions | `ACCOUNT_SUSPENDED`; canonical `SUSPENDED` |
| Portal mode | `SUSPENDED` |
| Sessions | Optional bump |
| Background jobs | Pause |
| Emails | Suspension notice |

---

### T-009: Active → Cancellation scheduled

| Field | Policy |
|-------|--------|
| From | `ACTIVE` |
| To | `CANCELLATION_SCHEDULED` |
| Trigger | Customer `cancel_at_period_end` |
| Authority | Billing API → Stripe |
| Validation | Active subscription |
| Postconditions | `CANCELLATION_SCHEDULED`; canonical stays `ENABLED` |
| Portal mode | `FULL_ACCESS` |
| Sessions | Valid |
| Background jobs | Continue until expiry |
| Emails | Cancellation scheduled |
| **Current:** Backend NO_CHANGE_REQUIRED (ALC-010) |

---

### T-010: Cancellation scheduled → Active (resume)

| Field | Policy |
|-------|--------|
| From | `CANCELLATION_SCHEDULED` |
| To | `ACTIVE` |
| Trigger | Customer resumes subscription |
| Authority | Billing API → Stripe |
| Postconditions | `CANCELLATION_REMOVED` |
| Portal mode | `FULL_ACCESS` |

---

### T-011: Cancellation scheduled → Subscription expired

| Field | Policy |
|-------|--------|
| From | `CANCELLATION_SCHEDULED` |
| To | `SUBSCRIPTION_EXPIRED` |
| Trigger | Stripe period end + `customer.subscription.deleted` |
| Authority | Stripe webhook |
| Postconditions | `SUBSCRIPTION_EXPIRED`; canonical `CANCELLED` or `SUSPENDED` |
| Portal mode | `BILLING_RECOVERY` |
| Sessions | Valid; refetch |
| Background jobs | Pause |
| Emails | Subscription ended |

---

### T-012: Active → Cancelled immediate

| Field | Policy |
|-------|--------|
| From | `ACTIVE` (or TRIAL, GRACE) |
| To | `CANCELLED_IMMEDIATE` |
| Trigger | Customer/admin immediate cancel |
| Authority | Billing API → Stripe delete |
| Postconditions | `SUBSCRIPTION_CANCELLED`; canonical `CANCELLED` |
| Portal mode | `BILLING_RECOVERY` |
| Sessions | Valid (policy); entitlements_version++ |
| Background jobs | Pause |
| API | Non-billing client routes blocked |
| Emails | Cancellation confirmation |
| **Current gap:** Frontend still mounts shell — **TRANSITION_GAP** |

---

### T-013: Active → Subscription expired (non-payment)

| Field | Policy |
|-------|--------|
| From | `ACTIVE` / `GRACE_PERIOD` |
| To | `SUBSCRIPTION_EXPIRED` |
| Trigger | `UNPAID` / expired lifecycle |
| Authority | Stripe + lifecycle sync |
| Postconditions | `SUBSCRIPTION_EXPIRED` |
| Portal mode | `BILLING_RECOVERY` or `READ_ONLY` |
| Background jobs | Pause |

---

### T-014: Subscription expired → Read-only

| Field | Policy |
|-------|--------|
| From | `SUBSCRIPTION_EXPIRED` |
| To | `READ_ONLY` |
| Trigger | Retention tier elapsed (policy timer) |
| Authority | Scheduled lifecycle job (future) |
| Postconditions | `ACCOUNT_READ_ONLY` |
| Portal mode | `READ_ONLY` |
| Background jobs | Remain paused |

---

### T-015: Active → Suspended (ops)

| Field | Policy |
|-------|--------|
| From | `ACTIVE` |
| To | `SUSPENDED` |
| Trigger | Admin suspension / abuse |
| Authority | Admin API + `client_lifecycle_service` |
| Postconditions | `ACCOUNT_SUSPENDED` |
| Portal mode | `SUSPENDED` |
| Sessions | Bump recommended |
| Background jobs | Pause |

---

### T-016: Suspended → Active (reinstatement)

| Field | Policy |
|-------|--------|
| From | `SUSPENDED` |
| To | `ACTIVE` |
| Trigger | Admin reinstatement or payment recovery |
| Authority | Admin or Stripe |
| Postconditions | `ACCOUNT_REACTIVATED` |
| Portal mode | `FULL_ACCESS` |
| See | `ACCOUNT_REACTIVATION_AUTHORITY.md` |

---

### T-017: Active → Archived

| Field | Policy |
|-------|--------|
| From | `ACTIVE` (or terminal billing states) |
| To | `ARCHIVED` |
| Trigger | Admin archive |
| Authority | `client_lifecycle_service` |
| Postconditions | `ACCOUNT_ARCHIVED` |
| Portal mode | `ARCHIVED` |
| Sessions | Invalidate all |
| Background jobs | Terminate |

---

### T-018: Archived → Active (reactivation)

| Field | Policy |
|-------|--------|
| From | `ARCHIVED` |
| To | `ACTIVE` |
| Trigger | Admin reactivation + valid billing |
| Authority | Admin |
| Postconditions | `ACCOUNT_REACTIVATED` |
| Portal mode | `FULL_ACCESS` after billing validation |

---

### T-019: Any → Account deleted

| Field | Policy |
|-------|--------|
| From | Any |
| To | `ACCOUNT_DELETED` |
| Trigger | Admin permanent delete / GDPR purge |
| Authority | Admin purge workflow |
| Validation | Retention policy satisfied |
| Postconditions | `ACCOUNT_DELETED` |
| Portal mode | `ACCOUNT_DELETED` |
| Sessions | Invalidate all |
| Background jobs | Terminate |
| Data | Purged per retention policy |
| Rollback | None |

---

### T-020: Cancelled → Active (resubscribe)

| Field | Policy |
|-------|--------|
| From | `CANCELLED_IMMEDIATE` / `SUBSCRIPTION_EXPIRED` |
| To | `ACTIVE` |
| Trigger | New subscription checkout success |
| Authority | Stripe + billing |
| Postconditions | `ACCOUNT_REACTIVATED` + `SUBSCRIPTION_STARTED` |
| Portal mode | `FULL_ACCESS` |
| Background jobs | Resume deterministically |
| Idempotency | Required |

---

### T-021: Legacy → Resolved

| Field | Policy |
|-------|--------|
| From | `LEGACY` |
| To | Mapped state |
| Trigger | Migration job |
| Authority | Admin migration |
| Postconditions | `LEGACY_MIGRATED` event |

---

## Transition effects matrix (summary)

| Transition class | Portal mode change | Session | Jobs | Emails |
|------------------|-------------------|---------|------|--------|
| Payment recovery | → FULL_ACCESS | Refresh entitlements | Resume | Yes |
| Grace entry | → GRACE | None | Continue limited | Yes |
| Immediate cancel | → BILLING_RECOVERY | Optional bump | Pause | Yes |
| Period end cancel | → BILLING_RECOVERY | Refresh | Pause | Yes |
| Suspension | → SUSPENDED | Bump | Pause | Yes |
| Archive | → ARCHIVED | Invalidate | Terminate | Yes |
| Delete | → ACCOUNT_DELETED | Invalidate | Terminate | Final |
| Reactivation | → FULL_ACCESS | Refresh | Resume | Yes |

---

## Undefined transitions (policy gaps)

| Gap ID | Transition | Classification |
|--------|------------|----------------|
| TG-001 | `SUBSCRIPTION_EXPIRED` → `READ_ONLY` (timer) | TRANSITION_GAP — no job |
| TG-002 | `TRIAL_EXPIRED` → `READ_ONLY` | TRANSITION_GAP |
| TG-003 | Dual `SUSPENDED` (billing vs org) convergence | AUTHORITY_DUPLICATION |
| TG-004 | Frontend does not enforce post-transition portal mode | PORTAL_MODE_GAP |

---

**Outcome:** `ACCOUNT_LIFECYCLE_TRANSITION_MATRIX_COMPLETE`
