# Account Lifecycle Event Authority

**Programme (implementation):** ILP-9-LIFECYCLE-EVENTS-DISCOVERY-AND-IMPLEMENTATION-01  
**Module:** `services/account_lifecycle_event_authority.py`  
**Schema version:** `account_lifecycle_event_v1`  
**Branch:** `develop`

**Programme (governance policy):** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01  
**Authority version:** `account_lifecycle_policy_v1`  
**Parent:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`

---

## ILP-9 implementation summary

ILP-9 introduces the **authoritative lifecycle event architecture** — not a generic message bus.

| Responsibility | Location |
|----------------|----------|
| Canonical event names | `LifecycleEventType` enum |
| Canonical payload schema | `LifecycleEventPayload` |
| Single publication authority | `LifecycleEventAuthority.publish()` |
| Runtime transition detection | `detect_runtime_contract_events()` |
| Consumer registry | `register_lifecycle_event_consumer()` |
| Persistence | `account_lifecycle_events` collection |
| Audit | `_audit_lifecycle_event()` |

**Related docs:** `ACCOUNT_LIFECYCLE_EVENT_CATALOG.md`, `ACCOUNT_LIFECYCLE_EVENT_SCHEMA.md`, `ACCOUNT_LIFECYCLE_EVENT_CONSUMERS.md`, `ACCOUNT_LIFECYCLE_EVENT_SEQUENCE.md`

**Discovery audit:** `docs/audit/account_lifecycle_ilp_09/LIFECYCLE_EVENT_DISCOVERY_INVENTORY.json`

No service may invent ad-hoc lifecycle event payloads outside this authority.

---

## Governance — Purpose

Canonical lifecycle events are the **audit and integration contract**. No subsystem may infer or emit lifecycle state changes independently.

---

## Event emission rules

1. **Single writer** per event type (see owner column).
2. Events are **idempotent** — duplicate webhook delivery must not double-apply.
3. Events carry `account_lifecycle_state_before`, `account_lifecycle_state_after`, `portal_mode_after`.
4. All events persist to **audit log** and **customer timeline** (where customer-visible).
5. Consumers subscribe to events; they do not poll Stripe for lifecycle truth.

---

## Canonical event catalogue

### ACCOUNT_CREATED

| Field | Policy |
|-------|--------|
| Authoritative owner | Onboarding / admin provision service |
| Trigger | Org record created |
| Payload | `{ client_id, plan_id, source, created_by }` |
| Ordering | First event for client |
| Consumers | Audit, analytics, welcome email |
| Idempotency | `client_id` unique |
| Replay | Skip if client exists |
| Audit persistence | Required |
| Timeline presentation | “Account created” |
| Notifications | Welcome |
| Automation | None until ACTIVE |
| Reports | None |
| Analytics | Funnel start |

---

### TRIAL_STARTED

| Field | Policy |
|-------|--------|
| Authoritative owner | `stripe_webhook_service` → lifecycle sync |
| Trigger | Stripe subscription `TRIALING` |
| Payload | `{ client_id, subscription_id, trial_end }` |
| Consumers | Billing, entitlements, email, timeline |
| Idempotency | `stripe_event_id` |
| Timeline | “Trial started” |
| Emails | Trial welcome |

---

### TRIAL_EXPIRED

| Field | Policy |
|-------|--------|
| Authoritative owner | Lifecycle sync (Stripe period end) |
| Trigger | Trial end without conversion |
| Payload | `{ client_id, trial_end, previous_state: TRIAL }` |
| Consumers | Portal mode resolver, jobs (pause), email |
| Timeline | “Trial ended” |
| Emails | Trial expired notice |

---

### PAYMENT_PENDING

| Field | Policy |
|-------|--------|
| Authoritative owner | Onboarding / checkout |
| Trigger | Checkout session created / incomplete |
| Payload | `{ client_id, checkout_session_id }` |
| Consumers | Portal mode, onboarding UI |

---

### PAYMENT_FAILED

| Field | Policy |
|-------|--------|
| Authoritative owner | `stripe_webhook_service` |
| Trigger | `invoice.payment_failed` |
| Payload | `{ client_id, invoice_id, attempt_count }` |
| Consumers | Notifications, email, grace resolver |
| Timeline | “Payment failed” |
| Emails | Payment failed |

---

### GRACE_STARTED

| Field | Policy |
|-------|--------|
| Authoritative owner | `subscription_lifecycle_service` |
| Trigger | `billing_lifecycle_state` → `grace_period` |
| Payload | `{ client_id, grace_end, canonical: GRACE }` |
| Consumers | Portal mode, banner, email |
| Timeline | “Grace period started” |

---

### PAYMENT_RECOVERED

| Field | Policy |
|-------|--------|
| Authoritative owner | `stripe_webhook_service` |
| Trigger | `invoice.paid` after past_due |
| Payload | `{ client_id, invoice_id }` |
| Consumers | Entitlements, jobs (resume), timeline |
| Idempotency | `stripe_event_id` |
| Timeline | “Payment received” |

---

### SUBSCRIPTION_STARTED

| Field | Policy |
|-------|--------|
| Authoritative owner | `stripe_webhook_service` |
| Trigger | First successful paid period / resubscribe |
| Payload | `{ client_id, subscription_id, plan_id }` |
| Consumers | Entitlements, jobs, analytics |
| Timeline | “Subscription active” |

---

### CANCELLATION_REQUESTED

| Field | Policy |
|-------|--------|
| Authoritative owner | Billing API (`POST /billing/cancel`) |
| Trigger | Customer initiates cancel |
| Payload | `{ client_id, mode: immediate \| period_end, requested_by }` |
| Consumers | Audit, timeline |
| Timeline | “Cancellation requested” |

---

### CANCELLATION_SCHEDULED

| Field | Policy |
|-------|--------|
| Authoritative owner | Billing API + Stripe sync |
| Trigger | `cancel_at_period_end: true` |
| Payload | `{ client_id, period_end }` |
| Consumers | Portal banner, email |
| Timeline | “Cancellation scheduled for {date}” |

---

### CANCELLATION_REMOVED

| Field | Policy |
|-------|--------|
| Authoritative owner | Billing API |
| Trigger | Customer resumes before period end |
| Payload | `{ client_id }` |
| Timeline | “Cancellation withdrawn” |

---

### SUBSCRIPTION_CANCELLED

| Field | Policy |
|-------|--------|
| Authoritative owner | `stripe_webhook_service` / billing API |
| Trigger | Immediate cancel or `customer.subscription.deleted` |
| Payload | `{ client_id, cancel_mode, subscription_id }` |
| Consumers | Portal mode, jobs (pause), middleware, email |
| Idempotency | `stripe_event_id` + subscription id |
| Timeline | “Subscription cancelled” |
| Emails | Cancellation confirmation |

---

### SUBSCRIPTION_EXPIRED

| Field | Policy |
|-------|--------|
| Authoritative owner | Lifecycle sync |
| Trigger | Period end without renewal / UNPAID terminal |
| Payload | `{ client_id, expired_at, reason }` |
| Consumers | Portal mode, jobs, email |
| Timeline | “Subscription expired” |

---

### ACCOUNT_READ_ONLY

| Field | Policy |
|-------|--------|
| Authoritative owner | Future retention scheduler |
| Trigger | Retention tier policy |
| Payload | `{ client_id, tier, effective_at }` |
| Consumers | Portal mode, API read-only enforcement |
| **Gap:** Event not implemented — **EVENT_GAP** |

---

### ACCOUNT_SUSPENDED

| Field | Policy |
|-------|--------|
| Authoritative owner | `subscription_lifecycle_service` OR `client_lifecycle_service` |
| Trigger | Post-grace / admin suspension |
| Payload | `{ client_id, reason, suspension_class }` |
| Consumers | Portal mode, jobs, session policy |
| **Gap:** Dual emitters — **AUTHORITY_DUPLICATION** |

---

### ACCOUNT_ARCHIVED

| Field | Policy |
|-------|--------|
| Authoritative owner | `client_lifecycle_service` |
| Trigger | Admin archive |
| Payload | `{ client_id, archived_by, reason }` |
| Consumers | Auth deny, jobs terminate, email |

---

### ACCOUNT_DELETED

| Field | Policy |
|-------|--------|
| Authoritative owner | Admin purge service |
| Trigger | Permanent delete |
| Payload | `{ client_id, deleted_by, purge_scope }` |
| Consumers | Audit only (customer gone) |
| Replay | Forbidden |

---

### ACCOUNT_REACTIVATED

| Field | Policy |
|-------|--------|
| Authoritative owner | Reactivation orchestrator (future) |
| Trigger | Any successful reactivation path |
| Payload | `{ client_id, path, previous_state, restoration_scope }` |
| Consumers | Entitlements, jobs, portal, timeline, email |
| Idempotency | `{ client_id, path, subscription_id }` dedup |
| Timeline | “Account reactivated” |
| See | `ACCOUNT_REACTIVATION_AUTHORITY.md` |

---

### LEGACY_MIGRATED

| Field | Policy |
|-------|--------|
| Authoritative owner | Migration job |
| Trigger | Legacy record normalised |
| Payload | `{ client_id, from: LEGACY, to }` |

---

### ENTITLEMENTS_VERSION_CHANGED

| Field | Policy |
|-------|--------|
| Authoritative owner | Lifecycle sync |
| Trigger | Any state change affecting features |
| Payload | `{ client_id, version, portal_mode }` |
| Consumers | Frontend refetch, session validation |

---

## Event ordering guarantees

| Rule | Policy |
|------|--------|
| Stripe webhooks | Process in `stripe_event_id` idempotency store |
| State transitions | `before` state must match or event rejected (optimistic) |
| Reactivation | `ACCOUNT_REACTIVATED` after billing validation, before job resume |
| Delete | Terminal — no subsequent customer events |

---

## Consumer registry (policy)

| Consumer | Events subscribed |
|----------|-------------------|
| Portal mode resolver | All state-changing |
| `client_route_guard` | SUBSCRIPTION_CANCELLED, ACCOUNT_SUSPENDED, ACCOUNT_ARCHIVED |
| Notification orchestrator | PAYMENT_FAILED, GRACE_STARTED, SUBSCRIPTION_* , ACCOUNT_* |
| Reminder scheduler | SUBSCRIPTION_STARTED, ACCOUNT_REACTIVATED, SUBSCRIPTION_CANCELLED |
| Report scheduler | Same as reminders |
| Compliance monitoring | SUBSCRIPTION_STARTED, pause events |
| Score/risk engines | SUBSCRIPTION_STARTED, ACCOUNT_REACTIVATED |
| Frontend lifecycle provider | ENTITLEMENTS_VERSION_CHANGED, all terminal events |
| Timeline service | Customer-visible subset |
| Analytics | All |

---

## Current drift (audit)

| Issue | Classification |
|-------|----------------|
| No unified event bus; sync is field writes | EVENT_GAP |
| Frontend infers state from 403 payloads | EVENT_GAP |
| Jobs poll `clients` fields, not events | BACKGROUND_POLICY_GAP |
| `canonical_entitlement_state` in error JSON leaked to UI | CUSTOMER_EXPERIENCE_GAP |

---

**Outcome:** `ACCOUNT_LIFECYCLE_EVENT_AUTHORITY_COMPLETE`
