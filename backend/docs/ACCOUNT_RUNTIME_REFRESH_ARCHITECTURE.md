# Account Runtime Refresh Architecture (ILP-5)

## Refresh triggers

### Backend

- Login, password-set auto-login, session extend → new session record + version hints in JWT
- `POST /client/session-runtime/refresh` → full contract + session update
- Every `/api/client/*` request → validation via `client_route_guard` (cached contract)

### Frontend

| Trigger | Handler |
|---------|---------|
| Login / user change | `fetchRuntime({ force: true })` |
| Polling (`polling_policy.enabled`) | 120s interval |
| Tab visible | `visibilitychange` (15s throttle) |
| Window focus | `focus` (10s throttle) |
| API response header | `X-Session-Refresh-Required` → `refreshSession` |
| Session extend | `SessionIdleGuard` → `refreshSession('session_extend')` |
| Manual | `useLifecycleRuntime().refreshSession()` |
| Multi-tab | `BroadcastChannel` / `storage` invalidation |
| Offline recovery | `online` event + 30s retry while offline |

## Refresh flow

```mermaid
sequenceDiagram
    participant Tab as Customer Tab
    participant API as Backend API
    participant Contract as Runtime Contract
    participant DB as portal_session_runtime

    Tab->>API: Request + X-Client-Runtime-Version
    API->>Contract: resolve_runtime_contract_for_client
    API->>API: validate_session_against_contract
    API-->>Tab: 200 + X-Session-Refresh-Required (if stale)
    Tab->>API: POST /session-runtime/refresh
    API->>Contract: rebuild contract
    API->>DB: update session record
    API-->>Tab: lifecycle_runtime + optional access_token
    Tab->>Tab: update LifecycleRuntimeContext + broadcast to tabs
```

## Storm prevention

- `refreshLockRef` — single in-flight refresh
- `REFRESH_THROTTLE_MS` — 5s minimum between attempts
- Skip refresh on `/session-runtime/refresh` response interceptor loop
- Tab sync ignores events older than `lastFetchRef`

## Failure handling

| Condition | Behaviour |
|-----------|-------------|
| Runtime fetch fails | Governed fallback UI; capabilities deny (safe) |
| Refresh fails | Fallback to `fetchRuntime` |
| `SESSION_FORCE_REAUTH` | Logout + login redirect |
| Offline | Degraded message; retry when online |

## Capability cache invalidation

On successful refresh:

- `runtime` state replaced → all `useCapability` / domain hooks recompute
- Protected routes re-evaluate grants
- Navigation capabilities refresh via `usePortalNavigationCapabilities`
- Portal mode presentation updates via `usePortalMode`
