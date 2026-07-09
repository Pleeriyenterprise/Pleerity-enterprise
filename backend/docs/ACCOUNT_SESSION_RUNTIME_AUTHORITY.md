# Account Session Runtime Authority (ILP-5)

**Governance mapping:** Original governance **ILP-7 Session Authority** — see `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING.md`

## Summary

ILP-5 makes the **Runtime Contract** the live permission authority for authenticated customer sessions. JWT proves identity only; capability decisions always come from the Runtime Contract at request time (backend) and from `LifecycleRuntimeContext` (frontend).

## Authority split

| Layer | Responsibility |
|-------|----------------|
| JWT | Identity (`portal_user_id`, `client_id`, `role`), `session_version` invalidation, **version hints** (`runtime_version`, `entitlements_version`, `session_id`) |
| Runtime Contract | Capabilities, portal mode, navigation policy, session policy, customer experience |
| CapabilityEnforcementService | Backend route enforcement from contract |
| LifecycleRuntimeContext | Frontend capability consumption and refresh |

JWT must **never** carry `CAP_*` grants or `hasFeature` keys.

## Components

| Component | Path |
|-----------|------|
| SessionRuntimeService | `backend/services/account_session_runtime_service.py` |
| Session middleware | `backend/middleware/session_runtime.py` |
| Session API | `backend/routes/client_session_runtime.py` |
| Frontend sync | `frontend/src/utils/sessionRuntimeSync.js` |
| Version store | `frontend/src/utils/sessionRuntimeStore.js` |
| Runtime provider | `frontend/src/contexts/LifecycleRuntimeContext.js` |

## Session record fields

Each client portal login creates a `portal_session_runtime` document:

- `session_id`, `client_id`, `portal_user_id`
- `runtime_version`, `contract_version`, `entitlements_version`
- `issued_at`, `last_runtime_validation`, `last_runtime_refresh`, `last_capability_refresh`
- `refresh_reason`, `session_state`, `lifecycle_state`, `portal_mode`

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/client/session-runtime/status` | Lightweight validation |
| POST | `/api/client/session-runtime/validate` | Compare client-held versions |
| POST | `/api/client/session-runtime/refresh` | Refresh contract + session metadata; may re-issue JWT |

## Security

- Version drift → refresh, not silent permission replay
- Terminal lifecycle (`session_policy.jwt_valid=false`, `force_reauth`) → 401
- Refresh throttled client-side (5s) and single-flight locked
- Multi-tab invalidation via `BroadcastChannel` + `storage` events
- Response headers: `X-Session-Refresh-Required`, `X-Session-Refresh-Reason`

## Related documents

- [ACCOUNT_RUNTIME_SESSION_MODEL.md](./ACCOUNT_RUNTIME_SESSION_MODEL.md)
- [ACCOUNT_RUNTIME_REFRESH_ARCHITECTURE.md](./ACCOUNT_RUNTIME_REFRESH_ARCHITECTURE.md)
- [ACCOUNT_RUNTIME_VERSIONING_SESSION.md](./ACCOUNT_RUNTIME_VERSIONING_SESSION.md)
