# Account Lifecycle Response Authority (ILP-7)

**Programme:** ILP-7-LIFECYCLE-RESPONSE-AUTHORITY-01  
**Module:** `services/account_lifecycle_response_authority.py`  
**Policy version:** `account_lifecycle_response_v1`  
**Branch:** `develop`

---

## Purpose

ILP-7 centralizes **customer-facing lifecycle-aware API responses**. Every capability denial, lifecycle restriction, recovery journey, safe redirect, and lifecycle message is generated from one authority.

Routes and middleware must **not** assemble lifecycle payloads locally.

---

## Authority hierarchy (customer interaction layer)

```
Authentication Authority     → JWT
Permission Authority         → Runtime Contract + Capability Enforcement (ILP-4)
Session Authority            → Session Runtime (ILP-5)
Background Authority         → Background Runtime (ILP-6)
Lifecycle Response Authority → HTTP payload shape (ILP-7)  ← this programme
```

ILP-7 does **not** change lifecycle resolution, capability decisions, portal mode, billing, or session invalidation policy. It governs **how responses are produced**.

---

## Responsibilities

| Generator | Use when |
|-----------|----------|
| `from_capability_decision()` | CAP_* enforcement blocks an action (403) |
| `from_contract_lifecycle_denial()` | Route/middleware blocks by lifecycle state (403) |
| `authentication_expired()` | Session/token expired (401) |
| `session_refresh_required()` | Runtime version drift requires refresh |
| `capability_denied_http_detail()` | Compatibility wrapper for ILP-4 callers |
| `lifecycle_denial_for_client()` | Async helper — loads live Runtime Contract |

---

## Response categories

| `response_type` | Typical HTTP | Trigger |
|-----------------|--------------|---------|
| `capability_denied` | 403 | Plan or portal overlay denies capability |
| `lifecycle_denied` | 403 | Lifecycle blocks route access |
| `read_only` | 403 | READ_ONLY lifecycle / read-only blocked mutation |
| `billing_recovery` | 403 | Cancelled/expired subscription recovery |
| `suspended` | 403 | Account suspended |
| `archived` | 403 | Archived account |
| `deleted` | 403 | Purged account |
| `unknown_lifecycle` | 403 | Unresolved lifecycle |
| `authentication_expired` | 401 | Auth token invalid/expired |
| `session_refresh_required` | 409/403* | Runtime version mismatch |
| `retry_later` | 503 | Transient failure (reserved) |
| `temporary_unavailable` | 503 | Runtime contract unavailable |
| `support_required` | 403 | Support-only recovery (reserved) |
| `background_paused` | — | Background-only; not customer HTTP |

\* HTTP status preserved per existing route semantics; payload shape is standardized.

---

## Migration surface

### Centralized (ILP-7)

| Location | Before | After |
|----------|--------|-------|
| `middleware/capability_gating.py` | Local payload builder | `capability_denied_http_detail()` |
| `services/account_capability_enforcement.py` | `CapabilityDeniedError.to_detail()` local | Authority wrapper |
| `middleware/__init__.py` `_client_context_guard` | `SUBSCRIPTION_ACCESS_BLOCKED` + `canonical_entitlement_state` | `lifecycle_denial_for_client()` |
| All `capability_denied_http_detail()` route callers | Mixed `recovery.route` only | Full canonical schema |

### Out of scope (not lifecycle responses)

- RBAC denials (`Client context required`, role checks)
- Contractor/tenant portal guards
- Plan feature gating (`require_feature` plain strings)
- Step-up authentication payloads
- Admin/ops routes

---

## Observability

`log_lifecycle_response_generated()` emits structured INFO logs:

- `client_id`, `route`, `capability`, `grant`
- `lifecycle_state`, `response_type`, `runtime_version`
- `policy_version` (`account_lifecycle_response_v1`)

No sensitive customer content is logged.

---

## Related documents

| Document | Content |
|----------|---------|
| `ACCOUNT_LIFECYCLE_RESPONSE_SCHEMA.md` | Canonical JSON schema |
| `ACCOUNT_LIFECYCLE_RECOVERY_GUIDANCE.md` | Recovery actions and redirects |
| `ACCOUNT_RUNTIME_API.md` | Runtime contract API |
| `ACCOUNT_CAPABILITY_AUTHORITY.md` | Capability enforcement |
| `audit/account_lifecycle_ilp_07/` | ILP-7 audit, evidence, report |

---

## Tests

```bash
pytest tests/test_account_lifecycle_response_authority.py -q
pytest tests/test_account_capability_enforcement.py::TestCapabilityDeniedError -q
pytest tests/test_account_capability_enforcement_pilot.py::TestCapabilityDeniedPayload -q
```

Full platform regression deferred until final programme gate.
