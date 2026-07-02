# Account Runtime Versioning

**Programme:** ACCOUNT-LIFECYCLE-RUNTIME-CONTRACT-01  
**Parent:** `ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT.md`

---

## Version dimensions

| Version | Scope | Example | Bumped when |
|---------|-------|---------|-------------|
| `contract_version` | JSON schema semver | `1.0.0` | Schema field add/remove/rename |
| `runtime_version` | Per-client monotonic integer | `42` | Any material contract change for client |
| `policy_pins.*` | Governance doc versions | `account_lifecycle_policy_v1` | ALPA/ACA/APMA release |
| `entitlements_version` | Existing platform field | (existing) | Plan/lifecycle sync (align with runtime) |
| `session_version` | Existing JWT invalidation | (existing) | Terminal transitions (ILP-7) |

---

## Semver rules (`contract_version`)

| Change type | Version bump | Example |
|-------------|--------------|---------|
| New optional field | MINOR | `1.0.0` → `1.1.0` |
| New required field | MAJOR | `1.x` → `2.0.0` |
| Grant enum value add | MINOR | Add `RESTRICTED` grant |
| Grant enum rename/remove | MAJOR | Breaking clients |
| Capability ID add | MINOR | New `CAP_*` in map |
| Capability ID remove | MAJOR | Clients may break |

---

## `runtime_version` increment rules

Increment when **any** of these change for the client:

- `lifecycle_state`
- `portal_mode`
- Any `capabilities[*]` value
- `plan.plan_code` or material `plan_features` change
- `background_policy` any value
- `communication_policy` any value
- `session_policy.force_reauth` false → true
- `reactivation_policy.eligible` or `restoration_scope`
- `navigation_policy` locked/read_only sets

**Do not increment** for:

- `resolved_at` refresh with identical content
- `customer_experience` copy tweak without behavioural change (use content version subfield in v1.1)

---

## Client compatibility

### Request headers

| Header | Purpose |
|--------|---------|
| `X-Lifecycle-Contract-Version` | Client schema support, e.g. `1.0.0` |
| `X-Lifecycle-Runtime-Version` | Client cached version |

### Response headers

| Header | Purpose |
|--------|---------|
| `X-Lifecycle-Contract-Version` | Server schema version |
| `X-Lifecycle-Runtime-Version` | Current client runtime version |

### Negotiation

- Server always returns latest `contract_version` it supports.
- If client sends older `X-Lifecycle-Contract-Version` than server minimum, return `426 Upgrade Required` with upgrade URL (mobile).
- Web app: deploy lockstep with API (no long cross-version support).

---

## Backward compatibility strategy

### Phase 1 (ILP-2 launch)

- New endpoint: `GET /api/client/lifecycle-runtime`
- Deprecated parallel: `GET /api/client/entitlements` (features only, no lifecycle)
- `GET /api/client/lifecycle-contract` alias → same handler

### Phase 2 (ILP-5)

- Frontend reads runtime first; falls back to entitlements if `runtime_version` absent (feature flag)

### Phase 3 (ILP-10)

- Remove entitlements lifecycle inference
- `entitlements` endpoint returns plan features only OR merged into runtime
- Remove `canonical_entitlement_state` from customer API errors

---

## Deprecation policy

| Artifact | Deprecation | Removal |
|----------|-------------|---------|
| `hasFeature` for lifecycle | ILP-5 launch | ILP-10 |
| `canonical_entitlement_state` in 403 JSON | ILP-6 | ILP-10 |
| `clients.subscription_status` job filter | ILP-8 | ILP-10 |
| `/client/entitlements` as primary shell contract | ILP-5 | ILP-10 |
| Legacy feature key aliases | ILP-10 | v2 policy |

Minimum **2 release** overlap for deprecated fields where external integrators exist (read API).

---

## Policy pin upgrades

When `account_lifecycle_policy_v1` → `v2`:

1. Publish governance docs.
2. Deploy resolver with dual-pin support (read v1 or v2 via feature flag).
3. Rebuild all client runtime snapshots.
4. Bump minimum `policy_pins` in contract.
5. Audit diff report for grant changes.

---

## Cache invalidation on version change

```
runtime_version N → N+1
  → invalidate API memory cache
  → invalidate Redis alrc:{client_id}:*
  → frontend refetch on header mismatch
  → workers scheduled after event use N+1 snapshot
```

---

## Idempotency and rebuild

| Operation | Idempotency key |
|-----------|-----------------|
| Webhook → rebuild | `stripe_event_id` |
| Admin reinstatement | `admin_action_id` |
| Reactivation | `client_id` + `path` + `subscription_id` |
| Scheduled reconciliation | `client_id` + `date` |

Rebuild with same facts → same `runtime_version` content (no spurious bump).

---

## Failure versioning

On resolver failure:

- Do **not** increment `runtime_version`
- Return last known good contract with `stale: true` (max 30s) — v1.1 field
- After 30s or no prior good → `UNKNOWN` / `BILLING_RECOVERY` safe contract

---

## Audit trail versioning

Lifecycle event store records:

```json
{
  "event_id": "evt_...",
  "runtime_version_before": 41,
  "runtime_version_after": 42,
  "contract_version": "1.0.0",
  "trigger": "SUBSCRIPTION_CANCELLED"
}
```

---

## Governance checklist for schema change

1. Update `ACCOUNT_RUNTIME_SCHEMA.md`
2. Bump `contract_version` semver
3. Update consumer docs
4. Add migration entry to evidence JSON
5. Stakeholder approval before deploy
6. No schema change in hotfix without approval

---

**Outcome:** `ACCOUNT_RUNTIME_VERSIONING_COMPLETE`
