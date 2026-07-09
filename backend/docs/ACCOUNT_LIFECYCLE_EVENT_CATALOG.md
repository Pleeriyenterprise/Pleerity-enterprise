# Account Lifecycle Event Catalog (ILP-9)

**Programme:** ILP-9-LIFECYCLE-EVENTS-DISCOVERY-AND-IMPLEMENTATION-01  
**Authority:** `services/account_lifecycle_event_authority.py`  
**Schema version:** `account_lifecycle_event_v1`  
**Branch:** `develop`

---

## Purpose

Authoritative catalogue of platform lifecycle events. No service may invent ad-hoc event names or payloads outside this catalog.

Governance policy definitions remain in the policy section of `ACCOUNT_LIFECYCLE_EVENT_AUTHORITY.md`. This catalog reflects **implemented** ILP-9 types (`LifecycleEventType`).

---

## Lifecycle events

| Event | Category | Typical trigger | Idempotency key pattern |
|-------|----------|-----------------|-------------------------|
| `AccountActivated` | lifecycle | UNKNOWN/PAYMENT_PENDING → ACTIVE | `{client}:{event}:{before}:{after}:{rv}` |
| `TrialStarted` | lifecycle | Onboarding / Stripe TRIALING | Deferred — transition map |
| `TrialExpired` | lifecycle | TRIAL_EXPIRED → PAYMENT_REQUIRED | `{client}:{event}:{before}:{after}:{rv}` |
| `GracePeriodStarted` | lifecycle | ACTIVE → GRACE_PERIOD | `{client}:{event}:{before}:{after}:{rv}` |
| `PaymentRecovered` | lifecycle | GRACE_PERIOD → ACTIVE | `{client}:{event}:{before}:{after}:{rv}` |
| `CancellationScheduled` | lifecycle | ACTIVE → CANCELLATION_SCHEDULED | `{client}:{event}:{before}:{after}:{rv}` |
| `CancellationCancelled` | lifecycle | CANCELLATION_SCHEDULED → ACTIVE | `{client}:{event}:{before}:{after}:{rv}` |
| `SubscriptionExpired` | lifecycle | → CANCELLED_IMMEDIATE / SUBSCRIPTION_EXPIRED | `{client}:{event}:{before}:{after}:{rv}` |
| `SubscriptionReactivated` | reactivation | Cancelled/expired/read-only → ACTIVE | `{client}:{event}:{before}:{after}:{rv}` |
| `AccountSuspended` | lifecycle | → SUSPENDED | `{client}:{event}:{before}:{after}:{rv}` |
| `AccountArchived` | lifecycle | ACTIVE → ARCHIVED | `{client}:{event}:{before}:{after}:{rv}` |
| `AccountDeleted` | lifecycle | ACTIVE → ACCOUNT_DELETED | `{client}:{event}:{before}:{after}:{rv}` |
| `LifecycleStateChanged` | lifecycle | Any lifecycle_state change | `{client}:LifecycleStateChanged:{before}:{after}:{rv}` |

---

## Runtime events

| Event | Category | Typical trigger |
|-------|----------|-----------------|
| `PortalModeChanged` | runtime | portal_mode material change |
| `RuntimeContractChanged` | runtime | runtime_version bump |
| `CapabilitiesChanged` | runtime | capability fingerprint change |
| `BackgroundPolicyChanged` | background | background_policy dict change |
| `SessionRuntimeChanged` | session | runtime_version bump (session refresh recommended) |

---

## Communication events

| Event | Category | Publisher | Status |
|-------|----------|-----------|--------|
| `CommunicationSuppressed` | communication | `account_customer_communication_authority` | ✓ ILP-9 |
| `CommunicationSent` | communication | `notification_orchestrator` | Deferred ILP-10 |

---

## Reactivation & recovery events

| Event | Category | Publisher | Status |
|-------|----------|-----------|--------|
| `ReactivationStarted` | reactivation | reactivation authority | Deferred ILP-10 |
| `ReactivationCompleted` | reactivation | reactivation authority | Deferred ILP-10 |
| `ReactivationFailed` | reactivation | reactivation authority | Deferred ILP-10 |
| `RecoveryJourneyStarted` | recovery | reactivation authority | Deferred ILP-10 |
| `RecoveryJourneyCompleted` | recovery | reactivation authority | Deferred ILP-10 |
| `RecoveryJourneyAbandoned` | recovery | reactivation authority | Deferred ILP-10 |

---

## Publication rules

1. All events pass through `LifecycleEventAuthority.publish()` or `publish_lifecycle_event()`.
2. Runtime-derived events use `detect_runtime_contract_events()` — no duplicate manual emission.
3. Transition-specific events emit **in addition to** `LifecycleStateChanged` when mapped.
4. Unmapped transitions emit `LifecycleStateChanged` only.

---

## Storage

Collection: `account_lifecycle_events`  
Indexes: `idempotency_key` (unique sparse), `(client_id, occurred_at)`, `(event_type, occurred_at)`
