# Account Lifecycle Event Consumers (ILP-9)

**Programme:** ILP-9-LIFECYCLE-EVENTS-DISCOVERY-AND-IMPLEMENTATION-01  
**Registration API:** `register_lifecycle_event_consumer(category, handler)`

---

## Built-in consumers

| Consumer | Categories | Action |
|----------|------------|--------|
| `_consumer_runtime_cache_invalidation` | runtime, lifecycle, session | `invalidate_runtime_cache_for_client(client_id)` |

---

## Indirect consumers (via contract refresh)

| Module | Event interest |
|--------|----------------|
| `account_session_runtime_service` | SessionRuntimeChanged |
| `account_background_runtime_authority` | BackgroundPolicyChanged |
| `account_capability_enforcement` | CapabilitiesChanged |
| `account_lifecycle_response_authority` | All lifecycle/runtime |
| `account_customer_communication_authority` | Lifecycle + CommunicationSuppressed |
| `account_lifecycle_reactivation_authority` | Reactivation events (ILP-10) |

---

## Frontend

| Location | Mechanism |
|----------|-----------|
| `sessionRuntimeSync.js` | broadcastRuntimeInvalidation |
| `LifecycleRuntimeContext.js` | runtime_version polling |
| `communicationRuntime.js` | communication_policy from runtime |

---

## Audit

`_audit_lifecycle_event` → `LIFECYCLE_EVENT_PUBLISHED` audit metadata on every publish.

---

## Migration guidance

1. Register handlers via `register_lifecycle_event_consumer`.
2. Handlers must be idempotent.
3. Do not mutate lifecycle state in consumers.
