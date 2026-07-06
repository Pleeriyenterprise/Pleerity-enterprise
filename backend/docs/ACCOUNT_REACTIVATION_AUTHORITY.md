# Account Reactivation Authority

**Programme:** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01  
**ILP-8 implementation:** `services/account_lifecycle_reactivation_authority.py` (`account_lifecycle_reactivation_v1`)  
**Authority version:** `account_lifecycle_policy_v1`  
**Parent:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`

---

## ILP-8 runtime module

Governance path catalogue (R-001–R-008 below) is implemented for **orchestration metadata** in `LifecycleReactivationAuthority`:

- Consumes `reactivation_policy` from Runtime Contract
- Exposes recovery journeys (steps, CTA, eligibility)
- Does **not** execute Stripe/billing mutations (fact sources unchanged)

See `ACCOUNT_CUSTOMER_COMMUNICATION_AUTHORITY.md` for communication eligibility.

---

## Purpose

Reactivation is a **first-class lifecycle**. Every path from a restricted state back to operational access must be explicitly governed, idempotent, auditable, and deterministic in what it restores.

---

## Reactivation principles

1. **Billing validation first** — no operational restore without authoritative payment truth.
2. **Idempotent** — duplicate checkout/webhook must not double-restore or duplicate events.
3. **Scoped restoration** — each path defines exactly what is restored (full, read-only, selective).
4. **Single event** — every successful path emits `ACCOUNT_REACTIVATED` with `restoration_scope`.
5. **Deterministic job resume** — reminders, monitoring, reports resume per background policy matrix.
6. **Session refresh** — entitlements_version increment; optional session bump for terminal→active.
7. **Rollback** — failed reactivation leaves prior state unchanged.

---

## Reactivation path catalogue

### R-001: Trial resumed (before expiry)

| Field | Policy |
|-------|--------|
| From state | `TRIAL` |
| To state | `TRIAL` or `ACTIVE` |
| Authoritative trigger | Plan change / payment method added before trial end |
| Eligibility | Trial not expired |
| Billing validation | Stripe subscription active/trialing |
| Subscription validation | Same subscription id |
| Portal mode transition | `FULL_ACCESS` |
| Authentication | Existing JWT valid |
| Entitlements | Refresh plan matrix |
| Session restoration | entitlements_version++ |
| Background monitoring | Continue (never paused) |
| Reminder scheduling | Continue |
| Compliance recalculation | Continue |
| Risk/score recalculation | Continue |
| Timeline | Trial continued |
| Audit events | `SUBSCRIPTION_STARTED` or plan update |
| Emails | Optional confirmation |
| Restoration scope | **Everything** |

---

### R-002: Payment recovered during grace

| Field | Policy |
|-------|--------|
| From state | `GRACE_PERIOD` |
| To state | `ACTIVE` |
| Authoritative trigger | `invoice.paid` webhook |
| Eligibility | Subscription not cancelled |
| Billing validation | Stripe `ACTIVE` |
| Portal mode transition | `GRACE` → `FULL_ACCESS` |
| Session restoration | entitlements_version++; no forced logout |
| Background monitoring | Resume full |
| Reminder scheduling | Resume |
| Scheduled reports | Resume |
| Compliance recalculation | Recalculate if stale |
| Risk/score recalculation | Recalculate if stale |
| Timeline | Payment recovered |
| Audit events | `PAYMENT_RECOVERED`, `ACCOUNT_REACTIVATED` |
| Restoration scope | **Everything** |

---

### R-003: Cancelled subscription renewed before expiry (undo cancellation)

| Field | Policy |
|-------|--------|
| From state | `CANCELLATION_SCHEDULED` |
| To state | `ACTIVE` |
| Authoritative trigger | Resume subscription API |
| Eligibility | Before `period_end` |
| Billing validation | Stripe `cancel_at_period_end: false` |
| Portal mode transition | `FULL_ACCESS` |
| Background | Never paused |
| Audit events | `CANCELLATION_REMOVED` |
| Restoration scope | **Everything** (never lost) |

---

### R-004: Expired subscription renewed

| Field | Policy |
|-------|--------|
| From state | `SUBSCRIPTION_EXPIRED` |
| To state | `ACTIVE` |
| Authoritative trigger | New checkout / resubscribe |
| Eligibility | Account not ARCHIVED/DELETED |
| Billing validation | New or reactivated Stripe subscription `ACTIVE` |
| Portal mode transition | `BILLING_RECOVERY` → `FULL_ACCESS` |
| Session restoration | entitlements_version++; refetch lifecycle contract |
| Background monitoring | **Resume** from pause |
| Reminder scheduling | **Restart** schedules |
| Scheduled reports | **Re-register** schedules |
| Compliance recalculation | **Full recalc** |
| Risk/score recalculation | **Full recalc** |
| Queue recovery | Drain backlog policy: process or skip stale |
| Cache invalidation | Client entitlements + portal context |
| Idempotency | `stripe_subscription_id` dedup |
| Rollback | Revert to `SUBSCRIPTION_EXPIRED` on payment failure |
| Timeline | Subscription renewed |
| Audit events | `SUBSCRIPTION_STARTED`, `ACCOUNT_REACTIVATED` |
| Emails | Welcome back |
| Restoration scope | **Everything** |

---

### R-005: Immediately cancelled account restored

| Field | Policy |
|-------|--------|
| From state | `CANCELLED_IMMEDIATE` |
| To state | `ACTIVE` |
| Authoritative trigger | Resubscribe checkout |
| Eligibility | Within data retention window |
| Billing validation | New subscription `ACTIVE` |
| Portal mode transition | `BILLING_RECOVERY` → `FULL_ACCESS` |
| Session restoration | Same as R-004 |
| Background | Resume from pause |
| Properties restored | Yes |
| Evidence restored | Yes |
| Reports restored | Generation resumed; historical retained |
| Idempotency | Required |
| Restoration scope | **Everything** |

---

### R-006: Suspended account reinstated (payment)

| Field | Policy |
|-------|--------|
| From state | `SUSPENDED` (billing) |
| To state | `ACTIVE` |
| Authoritative trigger | Payment success post-suspension |
| Eligibility | Suspension class = payment |
| Billing validation | Stripe `ACTIVE` |
| Portal mode transition | `SUSPENDED` → `FULL_ACCESS` |
| Session restoration | May require re-login if session bumped |
| Background | Resume |
| Restoration scope | **Everything** |

---

### R-007: Suspended account reinstated (admin)

| Field | Policy |
|-------|--------|
| From state | `SUSPENDED` (ops) |
| To state | `ACTIVE` |
| Authoritative trigger | Admin reinstatement |
| Eligibility | Admin approval |
| Billing validation | Valid subscription or new subscription required |
| Portal mode transition | `SUSPENDED` → `FULL_ACCESS` or `BILLING_RECOVERY` |
| Session restoration | Force new login |
| Background | Manual review may be required |
| Restoration scope | **Selective** or **Everything** per admin choice |

---

### R-008: Admin reinstatement (archived)

| Field | Policy |
|-------|--------|
| From state | `ARCHIVED` |
| To state | `ACTIVE` |
| Authoritative trigger | Admin unarchive |
| Eligibility | Admin only; billing must be established |
| Billing validation | New or restored subscription |
| Portal mode transition | `ARCHIVED` → `PAYMENT_REQUIRED` or `FULL_ACCESS` |
| Authentication | New login required |
| Session restoration | All sessions invalidated; new issue |
| Background | **Restart** from terminate |
| Compliance recalculation | **Full recalc** |
| Restoration scope | **Manual review** default; **Everything** after validation |

---

### R-009: Manual billing recovery (admin)

| Field | Policy |
|-------|--------|
| From state | Any billing terminal state |
| To state | `ACTIVE` |
| Authoritative trigger | Admin billing adjustment |
| Eligibility | Admin + audit reason |
| Billing validation | Admin confirms Stripe/billing aligned |
| Portal mode transition | Per resolved state |
| Restoration scope | Per admin scope flag |

---

### R-010: Legacy account migration

| Field | Policy |
|-------|--------|
| From state | `LEGACY` |
| To state | Resolved policy state |
| Authoritative trigger | Migration job |
| Eligibility | Mapping table |
| Billing validation | Required before FULL_ACCESS |
| Portal mode transition | `READ_ONLY` → target mode |
| Restoration scope | **Selective** until migration complete |

---

### R-011: Trial expired → subscribe

| Field | Policy |
|-------|--------|
| From state | `TRIAL_EXPIRED` |
| To state | `ACTIVE` |
| Authoritative trigger | New subscription |
| Eligibility | Within retention |
| Portal mode transition | `PAYMENT_REQUIRED` → `FULL_ACCESS` |
| Background | Start from pause |
| Restoration scope | **Everything** |

---

### R-012: Read-only → active

| Field | Policy |
|-------|--------|
| From state | `READ_ONLY` |
| To state | `ACTIVE` |
| Authoritative trigger | Subscription renewal |
| Eligibility | Policy tier allows upgrade |
| Portal mode transition | `READ_ONLY` → `FULL_ACCESS` |
| Background | Resume |
| Restoration scope | **Everything** |

---

## Restoration scope definitions

| Scope | Meaning |
|-------|---------|
| **Everything** | Full portal mode, all mutations, all background services |
| **Read-only** | View/export only until further upgrade |
| **Selective** | Admin-defined subset (e.g. billing only) |
| **Manual review** | Ops queue before FULL_ACCESS |

---

## Idempotency and failure recovery

| Scenario | Policy |
|----------|--------|
| Duplicate Stripe webhook | No-op; single `ACCOUNT_REACTIVATED` |
| Checkout success but sync fails | Retry sync; portal stays `BILLING_RECOVERY` until confirmed |
| Partial job resume | Transactional event: jobs resume only after `ACTIVE` committed |
| Payment fails after restore | Transition back to `GRACE_PERIOD` or `SUSPENDED` per billing rules |

---

## Reactivation vs new account

| | Reactivation | New account |
|---|-------------|-------------|
| Client ID | Preserved | New |
| Historical data | Restored per scope | None |
| Timeline | Continuous | Fresh |
| Eligibility | Retention window | Always |

---

## Current gaps (audit)

| Gap | Classification |
|-----|----------------|
| No reactivation orchestrator | REACTIVATION_GAP |
| Resubscribe path exists in billing but portal stays broken | PORTAL_MODE_GAP |
| Job resume not tied to events | BACKGROUND_POLICY_GAP |
| No `ACCOUNT_REACTIVATED` canonical event today | EVENT_GAP |

---

**Outcome:** `ACCOUNT_REACTIVATION_AUTHORITY_COMPLETE`
