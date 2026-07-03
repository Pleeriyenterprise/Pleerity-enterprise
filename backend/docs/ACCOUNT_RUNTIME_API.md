# Account Lifecycle Runtime API (ILP-2)

**Programme:** ILP-2-RUNTIME-CONTRACT-API-01  
**Contract version:** `1.0.0` (`account_lifecycle_runtime_v1`)  
**Runtime build:** `ilp2_lifecycle_runtime_contract_v1`  
**Module:** `services/account_lifecycle_runtime_contract.py`

---

## Purpose

ILP-2 wraps the approved Runtime Contract around the ILP-1 Lifecycle State Resolver. It produces a single immutable, versioned `AccountLifecycleRuntimeContract` object for future ILP consumers.

ILP-2 does **not** enforce lifecycle behaviour. Existing `canonical_entitlement_state`, `hasFeature()`, middleware guards, and jobs remain authoritative for runtime.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/client/lifecycle-runtime` | Full runtime contract |
| GET | `/api/client/lifecycle-contract` | Transitional alias (same handler) |
| GET | `/api/client/lifecycle-runtime/diagnostic` | Contract + legacy drift comparison |

### Response wrapper

```json
{
  "lifecycle_runtime": { "...": "..." }
}
```

### Response headers

| Header | Value |
|--------|-------|
| `X-Lifecycle-Contract-Version` | `1.0.0` |
| `X-Lifecycle-Runtime-Version` | Monotonic integer per material contract |

---

## Schema

Governed by `ACCOUNT_RUNTIME_SCHEMA.md`. Required top-level fields:

- `contract_version`, `runtime_version`, `client_id`, `resolved_at`
- `lifecycle_state`, `portal_mode`, `capabilities`, `plan`
- `customer_experience`, `background_policy`, `communication_policy`
- `session_policy`, `polling_policy`
- `retention_policy`, `reactivation_policy`, `navigation_policy` (optional in schema v1 but always emitted)
- `warnings`, `source_facts`, `resolver_metadata`, `policy_pins`

---

## Field ownership

| Field | Owner | Source |
|-------|-------|--------|
| `lifecycle_state` | ILP-1 resolver | billing + org facts |
| `portal_mode` | APMA derivation | lifecycle state + retention markers |
| `capabilities` | ACA matrix | lifecycle + portal overlay + plan pre-resolution |
| `plan` | plan_registry (read-only) | `clients.billing_plan` |
| Policy blocks | ALPA / CX authority | Derived from lifecycle + portal mode |
| `runtime_version` | ILP-2 | Hash of material contract fields |

---

## Versioning

Per `ACCOUNT_RUNTIME_VERSIONING.md`:

| Version | Example | Bumped when |
|---------|---------|-------------|
| `contract_version` | `1.0.0` | Schema change |
| `runtime_version` | `1847293012` | Material contract change |
| `policy_pins.*` | `account_lifecycle_policy_v1` | Governance release |
| `resolver_metadata.resolver_version` | `ilp1_lifecycle_state_resolver_v1` | ILP-1 change |

`runtime_version` is deterministic from material fields (not incremented on identical refetch).

In-process cache TTL: 30 seconds (`client_id` + `runtime_version`).

---

## Resolver relationship

```
client_billing + clients facts
        ↓
ILP-1 resolve_account_lifecycle_state()
        ↓
ILP-2 build_runtime_contract()
        ↓
AccountLifecycleRuntimeContract (immutable)
```

---

## Portal Mode relationship

Single portal mode per contract (APMA). Lifecycle → mode map in `resolve_portal_mode()`. `SUBSCRIPTION_EXPIRED` + read-only retention markers → `READ_ONLY` instead of `BILLING_RECOVERY`.

---

## Capability relationship

Capabilities are **descriptive only** in ILP-2:

1. Base grants from `ACCOUNT_CAPABILITY_MATRIX.md`
2. Portal mode overlay (restrict only, never expand)
3. `PLAN_GATED` pre-resolved to `ALLOW`/`DENY` via `plan.plan_features`

Does not replace `hasFeature()` or `FEATURE_MATRIX`. Enforcement is ILP-4.

### ILP-4 Phase 2C-1 runtime extensions (schema unchanged)

Nine new capability rows in `_BASE_CAPABILITY_MATRIX`:

| Capability | Plan key |
|------------|----------|
| `CAP_PROP_ARCHIVE` | — |
| `CAP_PROP_DELETE` | — (governance row; no customer route) |
| `CAP_PROP_IMPORT` | `document_upload_bulk_zip` |
| `CAP_REQ_MARK_N_A` | — (distinct from `CAP_REQ_RESOLVE`; Option A) |
| `CAP_REQ_COMPLETE` | — (governance row; no route in 2C-1) |
| `CAP_SCORE_EXPLAIN` | `compliance_score` |
| `CAP_SCORE_TREND` | `score_trending` |
| `CAP_SCORE_SNAPSHOT` | `compliance_score` |
| `CAP_COMPLIANCE_ACTIVITY` | `compliance_dashboard` |

Portal ceilings for `BILLING_RECOVERY`, `READ_ONLY`, and `SUSPENDED` restrict write grants and expose read grants for score explain/trend/activity where `CAP_SCORE_VIEW` is readable.

Runtime resolver count: **47** capabilities (38 after Wave 1 + 9 in 2C-1).

Enforcement wiring: `ACCOUNT_CAPABILITY_ENFORCEMENT_MATRIX.md` — `properties.py`, `portfolio.py`, `client.py` score/requirement subset.

---

## Consumer roadmap

| Consumer | Status | ILP |
|----------|--------|-----|
| Tests / diagnostics | Active | ILP-2 |
| `GET /lifecycle-runtime` API | Active (new) | ILP-2 |
| Middleware `client_route_guard` | Blocked | ILP-4 |
| Frontend `EntitlementsContext` | Blocked | ILP-5 |
| Portal shell / navigation | Blocked | ILP-3, ILP-5 |
| Background jobs | Blocked | ILP-8 |
| Session invalidation | Blocked | ILP-7 |

Full inventory: `ACCOUNT_RUNTIME_CONSUMERS.md`.

---

## Deferred enforcement

ILP-2 explicitly does **not**:

- Wire contract into middleware or API guards
- Replace `/api/client/entitlements`
- Modify Stripe, billing, jobs, notifications, reports, or sessions
- Enforce `capabilities` grants on mutations

---

## Diagnostics

```bash
python scripts/account_lifecycle_runtime_drift_diagnostic.py --fixture
python scripts/account_lifecycle_runtime_drift_diagnostic.py --client-id <id>
```

Compares runtime contract against legacy `canonical_entitlement_state`, `billing_lifecycle_state`, and `entitlement_status`.

---

## Tests

```bash
pytest tests/test_account_lifecycle_runtime_contract.py -v
pytest tests/test_account_capability_enforcement_wave2c1.py -v
```

30 unit tests cover generation, portal mode, capabilities, policies, versioning, immutability, idempotency, cache, JSON serialization, and regression guards. ILP-4 Phase 2C-1 adds lifecycle-matrix route tests in `test_account_capability_enforcement_wave2c1.py`.
