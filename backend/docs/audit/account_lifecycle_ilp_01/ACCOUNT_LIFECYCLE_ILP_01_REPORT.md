# ILP-1 Account Lifecycle State Resolver — Implementation Report

**Programme:** ILP-1-LIFECYCLE-STATE-RESOLVER-01  
**Branch:** `develop`  
**Verdict:** `ILP_01_COMPLETE`  
**Date:** 2026-06-30

---

## Summary

ILP-1 implements a pure backend Account Lifecycle State Resolver that reads existing billing, subscription, entitlement, organisation, and client facts and resolves them into the governed `account_lifecycle_state` without mutating data or altering runtime behaviour.

---

## Deliverables

| Artifact | Path |
|----------|------|
| Resolver module | `services/account_lifecycle_state_resolver.py` |
| Unit tests | `tests/test_account_lifecycle_state_resolver.py` |
| Drift diagnostic script | `scripts/account_lifecycle_state_drift_diagnostic.py` |
| Implementation doc | `docs/ACCOUNT_LIFECYCLE_RESOLVER.md` |
| Audit evidence | `docs/audit/account_lifecycle_ilp_01/ACCOUNT_LIFECYCLE_ILP_01_EVIDENCE.json` |

---

## State coverage

All 15 approved lifecycle states are implemented:

`ACTIVE`, `TRIAL`, `TRIAL_EXPIRED`, `PAYMENT_PENDING`, `PAYMENT_FAILED`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `READ_ONLY`, `SUSPENDED`, `ARCHIVED`, `ACCOUNT_DELETED`, `UNKNOWN`, `LEGACY`

---

## Precedence

Documented in code (`resolve_account_lifecycle_state` docstring) and `ACCOUNT_LIFECYCLE_RESOLVER.md`:

1. Permanent deletion (`purged_at`)
2. Archive / soft delete
3. Org suspension
4. Legacy funnel
5. Onboarding without billing
6. Read-only retention markers
7. Billing-derived states (prefer `client_billing`)
8. Hard contradictions → `UNKNOWN`
9. Unmapped → `UNKNOWN`

---

## Tests

```
pytest tests/test_account_lifecycle_state_resolver.py -q
32 passed
```

Coverage includes all 26 requested scenarios plus boundary and idempotency cases.

---

## Diagnostics

Fixture-mode drift diagnostic executed (read-only, no Mongo mutation):

```
python scripts/account_lifecycle_state_drift_diagnostic.py --fixture
```

Output captured in `drift_diagnostic_fixture_output.json`.

---

## Non-invasive scope confirmation

ILP-1 does **not** modify:

- Middleware / route guards
- Frontend routing
- Stripe webhook write paths
- Background jobs
- `canonical_entitlement_state` persistence
- Subscription cancellation behaviour
- Pricing or charging

Resolver is available for tests and diagnostics only.

---

## Known limitations

1. **READ_ONLY** requires explicit retention markers (`read_only_retention`, `account_lifecycle_read_only`, `retention_tier`); automated retention timer transition is deferred to ILP-8/9.
2. **ACCOUNT_DELETED** resolves when `purged_at` is present on a client document; permanent delete currently removes the document (audit metadata only) — resolver handles tombstone field when present.
3. Pilot overlay emits warnings only; does not override billing-derived lifecycle state in ILP-1.
4. Hard billing contradictions (e.g. Stripe `ACTIVE` + stored `cancelled` billing lifecycle) resolve to `UNKNOWN` with warnings rather than picking a side.

---

## ILP-2 readiness

| Criterion | Status |
|-----------|--------|
| Deterministic `account_lifecycle_state` output | Ready |
| Version metadata (`policy_version`, `resolver_version`) | Ready |
| `source_facts` + `warnings` for audit | Ready |
| Read-only Mongo loader (`resolve_for_client_id`) | Ready |
| Drift comparison helper | Ready |
| No runtime side effects | Confirmed |

ILP-2 may wrap `resolve_for_client_id()` in the Runtime Contract API without changing resolver logic.

---

## Governance documents consumed

- `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`
- `ACCOUNT_LIFECYCLE_POLICY_MATRIX.md`
- `ACCOUNT_PORTAL_MODE_AUTHORITY.md`
- `ACCOUNT_LIFECYCLE_TRANSITION_MATRIX.md`
- `ACCOUNT_LIFECYCLE_EVENT_AUTHORITY.md`
- `ACCOUNT_REACTIVATION_AUTHORITY.md`
- `ACCOUNT_CUSTOMER_EXPERIENCE_AUTHORITY.md`
- `ACCOUNT_CAPABILITY_AUTHORITY.md`
- `ACCOUNT_CAPABILITY_CATALOG.md`
- `ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT.md`
- `ACCOUNT_RUNTIME_SCHEMA.md`
- `ACCOUNT_RUNTIME_VERSIONING.md`
- `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS.md`
