# ILP-2 Account Lifecycle Runtime Contract API — Implementation Report

**Programme:** ILP-2-RUNTIME-CONTRACT-API-01  
**Branch:** `develop`  
**Verdict:** `ILP_02_COMPLETE`  
**Date:** 2026-07-03

---

## Summary

ILP-2 implements the governed `AccountLifecycleRuntimeContract` service and exposes it via new read-only API endpoints. The runtime contract consumes the ILP-1 lifecycle resolver and derives portal mode, capabilities, and policy blocks from approved governance.

No middleware, frontend, enforcement, billing, Stripe, jobs, or session behaviour was changed.

---

## Deliverables

| Artifact | Path |
|----------|------|
| Runtime contract service | `services/account_lifecycle_runtime_contract.py` |
| API routes | `routes/client_lifecycle_runtime.py` |
| Server registration | `server.py` (router include only) |
| Unit tests | `tests/test_account_lifecycle_runtime_contract.py` |
| Drift diagnostic | `scripts/account_lifecycle_runtime_drift_diagnostic.py` |
| API documentation | `docs/ACCOUNT_RUNTIME_API.md` |
| Audit evidence | `docs/audit/account_lifecycle_ilp_02/` |

---

## API endpoints (new)

- `GET /api/client/lifecycle-runtime`
- `GET /api/client/lifecycle-contract` (alias)
- `GET /api/client/lifecycle-runtime/diagnostic`

Existing `/api/client/entitlements` and all other APIs unchanged.

---

## Runtime schema

Contract version `1.0.0` with required fields per `ACCOUNT_RUNTIME_SCHEMA.md`:

`lifecycle_state`, `portal_mode`, `capabilities`, `plan`, `customer_experience`, `background_policy`, `communication_policy`, `session_policy`, `polling_policy`, `retention_policy`, `reactivation_policy`, `navigation_policy`, `warnings`, `source_facts`, `resolver_metadata`, `policy_pins`.

---

## Portal Mode mapping

Implemented per `ACCOUNT_PORTAL_MODE_AUTHORITY.md` with read-only retention override for `SUBSCRIPTION_EXPIRED`.

---

## Capability mapping

Implemented per `ACCOUNT_CAPABILITY_MATRIX.md` with portal overlays per `ACCOUNT_PORTAL_MODE_CAPABILITY_MATRIX.md`. `PLAN_GATED` pre-resolved to `ALLOW`/`DENY` for API simplicity (v1.0 schema rule).

---

## Tests

```
pytest tests/test_account_lifecycle_runtime_contract.py -q
30 passed
```

ILP-1 resolver tests remain green (62 total with ILP-2).

---

## Regression proof

- No changes to `middleware/__init__.py`
- No changes to `routes/auth.py` enforcement
- No changes to `plan_registry` enforcement paths
- No changes to frontend
- Service module does not import middleware or FEATURE_MATRIX

---

## Known limitations

1. `runtime_version` is deterministic hash-based (no Mongo snapshot persistence in ILP-2).
2. `plan_name` falls back to plan code when Stripe price mappings unavailable (diagnostic/local).
3. Capabilities are descriptive only — `hasFeature()` remains authoritative until ILP-4.
4. `audit` block included only on diagnostic endpoint / `include_audit=True`.

---

## ILP-3 readiness

| Criterion | Status |
|-----------|--------|
| Stable runtime contract shape | Ready |
| Single `portal_mode` per contract | Ready |
| Customer experience block populated | Ready |
| Navigation policy populated | Ready |
| Version headers on API | Ready |
| No enforcement side effects | Confirmed |

ILP-3 (Portal Mode frontend shell) can consume `GET /api/client/lifecycle-runtime` without backend redesign.

---

## Consumer inventory

See `ACCOUNT_RUNTIME_CONSUMERS.md`. ILP-2 activates only tests, diagnostics, and the new API. All other consumers remain blocked until their ILP programmes.
