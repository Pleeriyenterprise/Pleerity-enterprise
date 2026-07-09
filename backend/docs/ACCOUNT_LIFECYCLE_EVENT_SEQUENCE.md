# Account Lifecycle Event Sequence (ILP-9)

**Programme:** ILP-9-LIFECYCLE-EVENTS-DISCOVERY-AND-IMPLEMENTATION-01

---

## Primary publication flow

1. Source calls `resolve_runtime_contract_for_client`.
2. Authority compares cached contract vs rebuilt contract.
3. On material change: `publish_runtime_contract_transition` → `detect_runtime_contract_events`.
4. Each payload: idempotency check → persist → dispatch consumers → audit.
5. Builtin consumer invalidates runtime cache; cache updated with new contract.

---

## Ordering guarantees

| Aspect | Guarantee |
|--------|-----------|
| Single transition | Payloads published sequentially |
| Cross-request | Best-effort; idempotency prevents duplicate apply |
| Consumers | Registration order within category |
| Replay | Same idempotency key → no-op |
| Out-of-order | Contract rebuild is source of truth |

---

## Runtime invalidation chain

Lifecycle change → events → cache invalidation → rebuild → new runtime_version → session/frontend refresh.

---

## Deferred (ILP-10)

Reactivation events, CommunicationSent, event replay API, dead-letter retry.
