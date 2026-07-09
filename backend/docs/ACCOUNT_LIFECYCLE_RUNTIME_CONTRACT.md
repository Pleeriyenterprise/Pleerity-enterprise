# Account Lifecycle Runtime Contract

**Programme:** ACCOUNT-LIFECYCLE-RUNTIME-CONTRACT-01  
**Contract version:** `account_lifecycle_runtime_v1`  
**Follows:** ACCOUNT-LIFECYCLE-AUTHORITY-AUDIT-01, ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01, ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Precedes:** ILP-1 through ILP-10 (no implementation until approved)  
**Branch:** develop (governance only)

---

## Purpose

This document defines the **single authoritative runtime object** — the lifecycle kernel — that every subsystem must consume.

| Governance layer | Role |
|------------------|------|
| **Lifecycle Policy (ALPA)** | Business rules |
| **Capability Authority (ACA)** | Permission language |
| **Portal Mode (APMA)** | Customer experience |
| **Runtime Contract (this programme)** | **One object, computed once, consumed everywhere** |

**Lifecycle decisions are made exactly once** — inside the Runtime Contract Resolver (implementation: ILP-1 + ILP-2). Nothing outside the contract may independently determine lifecycle behaviour.

---

## Kernel principle

```
┌─────────────────────────────────────────────────────────────┐
│  INPUTS (facts only — never consumed for behaviour)          │
│  Stripe · client_billing · client_lifecycle_service · org    │
└───────────────────────────┬─────────────────────────────────┘
                            │ write path only
                            ▼
              ┌─────────────────────────────┐
              │  Runtime Contract Resolver     │  ← single owner
              │  (ILP-1 + ILP-2)              │
              └──────────────┬───────────────┘
                             │ produces
                             ▼
              ┌─────────────────────────────┐
              │  AccountLifecycleRuntime       │
              │  Contract (ALRC)               │
              └──────────────┬───────────────┘
                             │ read only
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   Frontend            Customer APIs         Background workers
   Admin (read)         Authorisation         Notifications
```

### Forbidden consumer inputs (behavioural)

| Input | Status |
|-------|--------|
| Raw Stripe `subscription.status` | **Forbidden** for access/UI decisions |
| `canonical_entitlement_state` | **Forbidden** outside resolver |
| `billing_lifecycle_state` | **Forbidden** outside resolver |
| `entitlement_status` on `clients` mirror | **Forbidden** outside resolver |
| `plan_registry.FEATURE_MATRIX` alone | **Forbidden** as permission decision |
| `hasFeature(feature_key)` alone | **Forbidden** as lifecycle decision |
| `subscription_status` on `clients` | **Forbidden** for job eligibility |

Stripe and billing remain **fact sources for the resolver only**.

---

## Canonical object: `AccountLifecycleRuntimeContract`

Type name (implementation): `AccountLifecycleRuntimeContract`  
API field: `lifecycle_runtime` (wrapper) or root per `ACCOUNT_RUNTIME_SCHEMA.md`  
Version field: `contract_version` (semver of schema, e.g. `1.0.0`)

### Top-level fields

| Field | Description | Authority doc |
|-------|-------------|---------------|
| `contract_version` | Schema semver | `ACCOUNT_RUNTIME_VERSIONING.md` |
| `runtime_version` | Monotonic integer; bumps on any material change | Versioning doc |
| `client_id` | Subject org | — |
| `resolved_at` | ISO-8601 UTC resolution timestamp | — |
| `lifecycle_state` | `account_lifecycle_state` enum | ALPA |
| `portal_mode` | Customer experience mode | APMA |
| `capabilities` | Effective `CAP_*` grants map | ACA |
| `plan` | Plan context (read-only slice) | plan_registry overlay |
| `lifecycle_context` | State label, reason, transition hints | ALPA |
| `customer_experience` | UX copy, CTAs, feature lists | Customer Experience Authority |
| `background_policy` | Worker continue/pause/terminate matrix | ALPA + BG capability matrix |
| `communication_policy` | Send eligibility per channel | ALPA + LCA |
| `session_policy` | JWT/refresh/session_version rules | ALPA session authority |
| `retention_policy` | Data retention tier | ALPA Phase 10 |
| `reactivation_policy` | Eligible paths and scope | Reactivation Authority |
| `polling_policy` | Frontend/worker poll rules | Customer Experience Authority |
| `navigation_policy` | Locked/read-only route sets | Navigation + portal mode |
| `audit` | Resolution provenance (internal) | Event authority |

`lifecycle_events` are **not embedded** in the steady-state contract; they are emitted on transition and referenced by `lifecycle_context.last_event_id`.

---

## Authority ownership summary

See `ACCOUNT_RUNTIME_SCHEMA.md` for per-field owner, source, mutability, cache, TTL, invalidation.

| Field | Authoritative owner | Mutability |
|-------|---------------------|------------|
| `lifecycle_state` | Runtime Contract Resolver | Resolver only |
| `portal_mode` | Derived from lifecycle_state + policy | Resolver only |
| `capabilities` | Capability resolver (part of runtime) | Resolver only |
| `plan` | plan_registry (facts); embedded read-only | Billing sync |
| `customer_experience` | Derived from portal_mode + ALPA | Resolver only |
| `background_policy` | Derived from lifecycle_state | Resolver only |
| `communication_policy` | Derived from lifecycle_state | Resolver only |
| `session_policy` | Derived from transition class | Resolver + session service |
| `retention_policy` | ALPA retention rules | Resolver + scheduled job |
| `reactivation_policy` | Reactivation Authority | Resolver |
| `runtime_version` | Resolver | Increment on change |

---

## Runtime lifecycle

### Creation

1. Trigger: login, API request, webhook transition, admin action, scheduled reconciliation.
2. Resolver loads fact snapshot from `client_billing` + org lifecycle + policy version pins.
3. Computes full `AccountLifecycleRuntimeContract`.
4. Persists snapshot row (optional cache) with `runtime_version`.
5. Returns contract to consumer.

### Refresh

| Trigger | Action |
|---------|--------|
| API `GET /api/client/lifecycle-runtime` | Full resolve or cache hit |
| `runtime_version` mismatch (client header) | Force refetch |
| `ENTITLEMENTS_VERSION_CHANGED` event | Bump `runtime_version` |
| Stripe webhook processed | Invalidate + rebuild |
| Reactivation complete | Rebuild + resume workers |

### Invalidation

- Webhook writes to `client_billing`
- Admin lifecycle action
- `entitlements_version` increment (existing field)
- `session_version` bump (terminal states)
- Policy version pin change (`account_lifecycle_policy_v1` → `v2`)

### Cache

| Layer | TTL | Key |
|-------|-----|-----|
| In-process (API worker) | 30s max | `client_id` + `runtime_version` |
| Redis (optional) | 60s | `alrc:{client_id}:{runtime_version}` |
| Frontend | Session | `runtime_version` etag |

**Never cache across `runtime_version` changes.**

### Failure handling

| Failure | Behaviour |
|---------|-----------|
| Resolver error | `lifecycle_state: UNKNOWN`, `portal_mode: BILLING_RECOVERY`, capabilities safe-deny |
| Stale cache | Serve stale with `stale: true` max 30s; then safe-deny |
| Partial fact snapshot | Do not guess; UNKNOWN + audit alert |

### Idempotency

Same fact snapshot + same policy pins → identical contract (deterministic resolver).

---

## API contract

**Endpoint (future ILP-2):** `GET /api/client/lifecycle-runtime`  
**Alias (transitional):** `GET /api/client/lifecycle-contract`

See `ACCOUNT_RUNTIME_SCHEMA.md` for full JSON Schema.

### Client consumption

```
fetch lifecycle-runtime
  → portal_mode drives shell
  → capabilities drives features
  → customer_experience drives copy/CTAs
  → polling_policy drives refetch
```

### Error behaviour

| Condition | HTTP | Body |
|-----------|------|------|
| Unauthenticated | 401 | Standard auth |
| ARCHIVED / DELETED | 403 | `customer_experience` block only (safe strings) |
| Lifecycle deny on mutation API | 403 | `error_code`, `message` (string), `lifecycle_redirect`, `runtime_version` |
| Plan deny | 403 | `upgrade_required`, `capability_id`, `message` |

**Never return** raw `canonical_entitlement_state` in customer-facing errors.

---

## Consumer rules

Full inventory: `ACCOUNT_RUNTIME_CONSUMERS.md`.

1. **Read** the contract; never re-derive lifecycle.
2. **Check capability** by ID; never `enforce_feature` without contract context.
3. **Background jobs** load contract snapshot at job start; not `clients.subscription_status`.
4. **Frontend** single provider: `LifecycleRuntimeProvider`.
5. **Admin** may view contract for diagnostics; admin actions go through resolver write path.

---

## Migration to ILP series

| Phase | Programme | Delivers |
|-------|-----------|----------|
| ILP-1 | Lifecycle State Resolver | `lifecycle_state` computation |
| ILP-2 | Runtime Contract API | `GET /api/client/lifecycle-runtime` |
| ILP-3 | Portal Mode | Shell consumes `portal_mode` from contract |
| ILP-4 | Capability Enforcement | APIs check `capabilities` map |
| ILP-5 | Frontend Lifecycle Shell | Provider + route guards |
| ILP-6 | API Responses | Safe errors + lifecycle_redirect |
| ILP-7 | Session Authority | `session_policy` enforcement |
| ILP-8 | Background Services | `background_policy` enforcement |
| ILP-9 | Lifecycle Events | Invalidation + event bus |
| ILP-10 | Legacy Removal | Remove parallel fields consumers |

**No ILP work begins until this contract is approved.**

---

## Document map

| Document | Content |
|----------|---------|
| `ACCOUNT_RUNTIME_SCHEMA.md` | Field-level schema and ownership |
| `ACCOUNT_RUNTIME_CONSUMERS.md` | Subsystem migration inventory |
| `ACCOUNT_RUNTIME_VERSIONING.md` | Version, deprecation, compatibility |
| `audit/.../ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT_EVIDENCE.json` | Gaps and acceptance |

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Single runtime owner | ✓ Runtime Contract Resolver |
| All subsystems consume same contract | ✓ Consumer audit |
| No direct Stripe/subscription reads for behaviour | ✓ Forbidden list |
| Portal mode from contract | ✓ |
| Capabilities from contract | ✓ |
| Background from contract | ✓ |
| Frontend from contract | ✓ |
| API responses governed | ✓ Schema |
| Versioning defined | ✓ Versioning doc |
| ILP migration path complete | ✓ |

---

**Outcome:** `ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT_COMPLETE`
