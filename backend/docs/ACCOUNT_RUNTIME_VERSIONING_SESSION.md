# Account Runtime Versioning in Session (ILP-5)

## Version fields

| Field | Source | Purpose |
|-------|--------|---------|
| `contract_version` | `CONTRACT_VERSION` constant (`1.0.0`) | Schema compatibility |
| `runtime_version` | Hash of material contract fields | Detect lifecycle/capability changes |
| `entitlements_version` | `clients.entitlements_version` | Detect plan/billing entitlement bumps |
| `session_version` | `portal_users.session_version` | Force logout (security) |

## Validation rules

`validate_session_against_contract()` compares JWT/session record against authoritative contract:

1. `session_policy.force_reauth` → `FORCE_REAUTH`
2. `session_policy.jwt_valid=false` → `TERMINATED`
3. `runtime_version` mismatch → `REFRESH_RUNTIME`
4. `entitlements_version` mismatch → `REFRESH_TOKEN` (new JWT hints)
5. `contract_version` mismatch → `REFRESH_RUNTIME`
6. `lifecycle_state` / `portal_mode` change in session record → `REFRESH_RUNTIME`

## Request headers

**Client sends (staleness hints):**

- `X-Client-Runtime-Version`
- `X-Client-Entitlements-Version`
- `X-Client-Contract-Version`
- `X-Client-Session-Id`

**Server responds:**

- `X-Lifecycle-Runtime-Version`
- `X-Session-Entitlements-Version`
- `X-Session-Refresh-Required` (`true` | `false` | `force_reauth`)
- `X-Session-Refresh-Reason` (comma-separated)

## Performance

- Backend uses existing 30s runtime contract cache per `client_id`
- Session validation reuses cached contract from `resolve_runtime_contract_for_client`
- Frontend throttles visibility/focus/poll refreshes
- Full contract refresh only on drift or explicit refresh — not every API call

## No duplication

Session validation **does not** re-implement capability logic. It delegates to:

- `build_runtime_contract` / `resolve_runtime_contract_for_client`
- `resolve_session_policy`
- `CapabilityEnforcementService` for route-level grants
