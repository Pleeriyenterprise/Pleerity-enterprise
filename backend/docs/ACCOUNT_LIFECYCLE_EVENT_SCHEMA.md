# Account Lifecycle Event Schema (ILP-9)

**Programme:** ILP-9-LIFECYCLE-EVENTS-DISCOVERY-AND-IMPLEMENTATION-01  
**Schema version:** `account_lifecycle_event_v1`  
**Policy version:** `account_lifecycle_event_v1`

---

## Document shape

Every persisted lifecycle event conforms to `LifecycleEventPayload.to_document()`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | string | ✓ | `lev_{uuid}` — unique event identifier |
| `event_type` | string | ✓ | Canonical name from catalog |
| `event_category` | string | ✓ | lifecycle, runtime, session, background, communication, reactivation, recovery, audit |
| `client_id` | string | ✓ | Tenant identifier |
| `lifecycle_state` | string | | Current lifecycle after event |
| `lifecycle_state_before` | string | | Previous lifecycle (transitions) |
| `lifecycle_state_after` | string | | New lifecycle (transitions) |
| `portal_mode` | string | | Current portal mode |
| `portal_mode_before` | string | | Previous portal mode |
| `portal_mode_after` | string | | New portal mode |
| `runtime_version` | int | | Current runtime version |
| `runtime_version_before` | int | | Previous runtime version |
| `contract_version` | string | ✓ | Runtime contract version (default from ILP-2) |
| `session_version` | any | | Session version when relevant |
| `capability_version` | string | | Capability fingerprint when CapabilitiesChanged |
| `source_service` | string | ✓ | Publishing module name |
| `correlation_id` | string | ✓ | Defaults to `corr_{client_id}` |
| `causation_id` | string | | Upstream event or request ID |
| `idempotency_key` | string | ✓ | Dedup key — unique index |
| `severity` | string | ✓ | Default `info` |
| `schema_version` | string | ✓ | `account_lifecycle_event_v1` |
| `policy_version` | string | ✓ | `account_lifecycle_event_v1` |
| `trigger` | string | | Human/machine trigger reason |
| `metadata` | object | ✓ | Non-sensitive operational extensions |
| `occurred_at` | ISO8601 | ✓ | Event time (UTC) |
| `created_at` | ISO8601 | ✓ | Persist time (UTC) |

---

## Idempotency

- Publisher supplies `idempotency_key`.
- Authority checks collection before insert.
- Duplicate publish returns `{status: "duplicate", duplicate: true}` without re-dispatching consumers.

---

## Sensitive data

Do not include payment instruments, tokens, passwords, or raw Stripe objects in event payloads.

---

## Observability metadata

Fields suitable for future metrics: `event_type`, `event_category`, `source_service`, `severity`, `schema_version`. Consumer failures log as `lifecycle_event_consumer_failed`.
