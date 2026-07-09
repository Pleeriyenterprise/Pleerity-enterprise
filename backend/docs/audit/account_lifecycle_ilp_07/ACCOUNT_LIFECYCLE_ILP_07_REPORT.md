# ILP-7 — Lifecycle Response Authority Report

**Programme:** ILP-7-LIFECYCLE-RESPONSE-AUTHORITY-01  
**Branch:** `develop`  
**Executed:** 2026-07-06 UTC  

## Verdict

**`ILP_07_IMPLEMENTED_TARGETED_VALIDATION_PASS_REGRESSION_DEFERRED`**

Lifecycle Response Authority is implemented. All governed customer lifecycle denial paths delegate to the central service. Targeted validation passed (18 tests). Full regression deferred under approved testing policy.

**Production ready:** No — full regression remains a programme closeout gate.

---

## Summary

ILP-7 completes the **customer interaction layer** of the Account Lifecycle Architecture. Every customer-facing lifecycle restriction, capability denial, recovery journey, and safe redirect is generated from `account_lifecycle_response_authority.py`.

| ILP | Layer |
|-----|-------|
| ILP-1 | Lifecycle determination |
| ILP-2 | Runtime contract exposure |
| ILP-3 | Portal mode presentation |
| ILP-4 | Capability enforcement |
| ILP-5 | Session runtime authority |
| ILP-6 | Background runtime authority |
| **ILP-7** | **Lifecycle response authority** |

---

## Deliverables

| Item | Status |
|------|--------|
| Customer response path audit | ✓ `RESPONSE_PATH_INVENTORY.json` |
| `account_lifecycle_response_authority.py` | ✓ |
| Canonical response schema | ✓ `ACCOUNT_LIFECYCLE_RESPONSE_SCHEMA.md` |
| Recovery guidance | ✓ `ACCOUNT_LIFECYCLE_RECOVERY_GUIDANCE.md` |
| Capability denial centralization | ✓ middleware + routes |
| Subscription guard migration | ✓ `_client_context_guard` |
| `lifecycle_redirect` authority | ✓ |
| Recovery metadata centralization | ✓ |
| Frontend consumer updates (minimal) | ✓ `capabilityRuntime.js`, `client.js` |
| Targeted tests | ✓ 18 passed |
| Evidence | ✓ `ACCOUNT_LIFECYCLE_ILP_07_EVIDENCE.json` |

---

## Key changes

### Central authority

`LifecycleResponseAuthority` generates governed payloads from CapabilityDecision or Runtime Contract material, including:

- `customer_experience` (safe subset from contract)
- `recovery` (action, eligibility, paths)
- `lifecycle_redirect` (route, label, surface)
- Runtime metadata (`runtime_version`, `contract_version`, `policy_version`)
- `support_reference` for observability

### Migrations

1. **Capability gating** — removed local builder; all 403 payloads via `capability_denied_http_detail()`
2. **Subscription guard** — replaced legacy `SUBSCRIPTION_ACCESS_BLOCKED` payload with `lifecycle_denial_for_client()`
3. **ILP-4 compatibility** — `reason_code` alias preserved alongside `error_code`

### Frontend

- `parseLifecycleResponseDetail()` for all governed lifecycle payloads
- `lifecycleRedirectRouteFromDetail()` prefers `lifecycle_redirect` over legacy `recovery.route`
- `parseApiError` respects `safe_to_retry`

---

## Lifecycle matrix validation

All 11 lifecycle states validated for schema, message, redirect, recovery, portal mode, and runtime metadata:

ACTIVE, TRIAL, GRACE_PERIOD, CANCELLATION_SCHEDULED, READ_ONLY, CANCELLED_IMMEDIATE, SUBSCRIPTION_EXPIRED, SUSPENDED, ARCHIVED, ACCOUNT_DELETED, UNKNOWN

---

## Targeted tests (passed)

```
pytest tests/test_account_lifecycle_response_authority.py -q                    → 14 passed
pytest tests/test_account_capability_enforcement.py::TestCapabilityDeniedError -q → 1 passed
pytest tests/test_account_capability_enforcement_pilot.py::TestCapabilityDeniedPayload -q → 3 passed
```

**Total:** 18 passed, 0 failed.

---

## Deferred

| Item | Reason |
|------|--------|
| `require_feature` plain-string 403 | Plan gate, not lifecycle response |
| RBAC/context 403 strings | Authorization, not lifecycle CX |
| Auth middleware wiring to `authentication_expired()` | Generators ready; existing 401 semantics preserved |
| `test_iteration26_billing_webhooks` assertion update | Requires seed DB; update at full regression |
| Full backend/frontend regression | Programme closeout gate |

---

## ILP-8 readiness

Customer HTTP lifecycle responses and background lifecycle authority (ILP-6) are complete. Platform is ready for ILP-8 planning and final production-critical programme validation.

---

## Out of scope (unchanged)

Lifecycle resolver, runtime contract schema, capability decisions, session runtime, background runtime, portal mode logic, billing/Stripe, customer workflows, frontend layouts.
