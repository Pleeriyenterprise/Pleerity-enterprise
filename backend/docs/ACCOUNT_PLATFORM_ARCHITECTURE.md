# Account Platform Architecture

**Programme:** ILP-10-PLATFORM-CONVERGENCE-AND-LEGACY-REMOVAL-01  
**Branch:** `develop`

---

## Overview

The account lifecycle platform is a **stack of single-purpose authorities** assembled from ILP-1 through ILP-10. Each layer reads from layers above; no layer invents lifecycle truth independently.

---

## Data flow

```
Billing / Org facts (Stripe, MongoDB)
    → Lifecycle State Resolver
    → Runtime Contract (versioned, cacheable)
    → Capability / Session / Background policies
    → HTTP responses, communications, events
    → Frontend runtime sync
```

---

## Core documents

| Document | Purpose |
|----------|---------|
| `ACCOUNT_PLATFORM_AUTHORITY_STACK.md` | Authority hierarchy and entry points |
| `ACCOUNT_PLATFORM_CONVERGENCE.md` | ILP-10 convergence summary |
| `ACCOUNT_PLATFORM_RELEASE_BASELINE.md` | Release readiness baseline |
| `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS.md` | Programme completion status |
| `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING.md` | Governance ↔ implementation mapping |

---

## Authority modules (backend)

| ILP | Module |
|-----|--------|
| 1 | `services/account_lifecycle_state_resolver.py` |
| 2 | `services/account_lifecycle_runtime_contract.py` |
| 4 | `services/account_capability_enforcement.py` |
| 5 | `services/account_session_runtime_service.py` |
| 6 | `services/account_background_runtime_authority.py` |
| 7 | `services/account_lifecycle_response_authority.py` |
| 8 | `services/account_customer_communication_authority.py` |
| 8 | `services/account_lifecycle_reactivation_authority.py` |
| 9 | `services/account_lifecycle_event_authority.py` |

---

## Frontend shell

| ILP | Component |
|-----|-----------|
| 3 | `contexts/LifecycleRuntimeContext.js` |
| 4 | `utils/capabilityRuntime.js`, `CapabilityProtectedRoute.js` |
| 5 | `utils/sessionRuntimeSync.js` |
| 8 | `utils/communicationRuntime.js` |

---

## API surfaces

| Endpoint | Authority |
|----------|-----------|
| `GET /api/client/lifecycle-runtime` | Runtime Contract (ILP-2) |
| Session runtime routes | Session Runtime (ILP-5) |
| All `/api/client/*` guarded routes | Capability + lifecycle guard |

---

## Terminology

| Term | Meaning |
|------|---------|
| **Lifecycle state** | Resolved account band (ACTIVE, TRIAL, GRACE_PERIOD, …) |
| **Runtime contract** | Versioned snapshot of lifecycle + capabilities + policies |
| **Portal mode** | Presentation overlay (FULL_ACCESS, BILLING_RECOVERY, …) |
| **Capability** | CAP_* grant (ALLOW, DENY, READ, …) |
| **Runtime version** | Material change fingerprint for cache/session sync |
| **Lifecycle event** | Authoritative platform event (ILP-9 catalogue) |

---

## Historical audits

Implementation history preserved under `backend/docs/audit/account_lifecycle_ilp_*/`. Do not rewrite historical reports.

---

**Status:** Converged architecture baseline — `account_lifecycle_platform_v1`
