# Account Runtime Session Model (ILP-5)

## Session lifecycle

```
Login / password-set / session-extend (client portal)
    → resolve Runtime Contract
    → create or refresh portal_session_runtime record
    → issue JWT with identity + version hints
    → frontend loads LifecycleRuntimeContext

Authenticated API request (client portal)
    → JWT auth + session_version check
    → client_route_guard + session runtime validation
    → optional X-Client-Runtime-Version / X-Client-Entitlements-Version headers
    → capability enforcement from Runtime Contract (per route)

Version drift detected
    → X-Session-Refresh-Required response header
    → frontend refreshSession() without logout
    → optional new JWT when entitlements_version changed

Terminal lifecycle (ACCOUNT_DELETED, jwt_valid=false)
    → 401 SESSION_FORCE_REAUTH / SESSION_TERMINATED
```

## JWT claims (client portal)

**Authentication:**

- `portal_user_id`, `client_id`, `email`, `role`, `session_version`

**Staleness hints (not permissions):**

- `session_id`
- `runtime_version`
- `contract_version`
- `entitlements_version`
- `issued_at`

Staff, contractor, and admin tokens are unchanged (no session runtime record).

## Session states

| State | Meaning |
|-------|---------|
| `ACTIVE` | Versions match; normal operation |
| `REFRESH_REQUIRED` | Contract changed; refresh without logout |
| `FORCE_REAUTH` | Terminal lifecycle; sign in again |
| `TERMINATED` | `jwt_valid=false`; session ended |

## Persistence

Collection: `portal_session_runtime` (MongoDB)

Indexed by `session_id`; updated on login, extend, and explicit refresh.

## Frontend session store

`sessionRuntimeStore.js` holds client-held version hints attached to every client API request. Cleared on logout. Updated from:

- Login user payload
- `refreshSessionRuntime` response
- Lifecycle runtime fetch
