# Account Lifecycle Implementation Readiness

**Programme:** ACCOUNT-LIFECYCLE-GOVERNANCE-CONSISTENCY-REVIEW-01  
**Status:** **READY FOR ILP-1**  
**Parent:** `ACCOUNT_LIFECYCLE_GOVERNANCE_REVIEW.md`

---

## Governance approval gate

| Gate | Requirement | Status |
|------|-------------|--------|
| G-1 | Audit complete | ✓ ACCOUNT-LIFECYCLE-AUTHORITY-AUDIT-01 |
| G-2 | Policy authority complete | ✓ ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01 |
| G-3 | Capability authority complete | ✓ Committed `3ca32450` |
| G-4 | Runtime contract complete | ✓ Committed `0236a8d3` |
| G-5 | Consistency review | ✓ This programme |
| G-6 | Stakeholder approval | Pending sign-off on Governance Review |

**Implementation may begin with ILP-1 when G-6 is recorded.**

---

## Canonical ILP sequence

This table **supersedes** all other ILP roadmap tables in individual authority documents (harmonized Governance Review 01).

```
ILP-1  Lifecycle State Resolver
  ↓
ILP-2  Runtime Contract API
  ↓
ILP-3  Portal Mode ─────────────┐
  ↓                              │
ILP-4  Capability Enforcement    │
  ↓                              │
ILP-5  Frontend Lifecycle Shell ←┘ (depends ILP-2 + ILP-3)
  ↓
ILP-6  API Responses
  ↓
ILP-7  Session Authority
  ↓
ILP-8  Background Services
  ↓
ILP-9  Lifecycle Events
  ↓
ILP-10 Legacy Removal
```

---

## Programme detail

### ILP-1 — Lifecycle State Resolver

| Field | Value |
|-------|-------|
| Purpose | Compute `account_lifecycle_state` from Stripe/billing/org facts |
| Governance inputs | ALPA enums, transition rules, APMA mapping |
| Deliverables | Resolver service; writes state snapshot; invalidates runtime |
| Dependencies | G-6 approval only |
| Blocks | ILP-2, ILP-9 |
| Risk | HIGH |
| Regression | `test_iteration26_billing_webhooks`, billing lifecycle visibility tests |
| **Readiness** | **READY** |

---

### ILP-2 — Runtime Contract API

| Field | Value |
|-------|-------|
| Purpose | `GET /api/client/lifecycle-runtime` returns `AccountLifecycleRuntimeContract` |
| Governance inputs | ACCOUNT_RUNTIME_SCHEMA.md, all policy/capability matrices |
| Deliverables | API endpoint; resolver integration; `runtime_version` |
| Dependencies | ILP-1 |
| Blocks | ILP-3, ILP-4, ILP-5, ILP-7, ILP-8 |
| Risk | MEDIUM |
| Regression | Schema contract tests; example payload validation |
| **Readiness** | **BLOCKED on ILP-1** (governance ready) |

---

### ILP-3 — Portal Mode

| Field | Value |
|-------|-------|
| Purpose | Frontend/backend consume `portal_mode`, `customer_experience`, `navigation_policy` |
| Governance inputs | APMA, Customer Experience Authority |
| Deliverables | Portal mode shell components; landing route enforcement |
| Dependencies | ILP-2 |
| Blocks | ILP-5 |
| Risk | MEDIUM |
| **Readiness** | **BLOCKED on ILP-2** |

---

### ILP-4 — Capability Enforcement

| Field | Value |
|-------|-------|
| Purpose | APIs and guards check `capabilities` map before plan overlay |
| Governance inputs | ACA catalog, API capability matrix |
| Deliverables | Capability check middleware/helper; replace direct enforce_feature lifecycle |
| Dependencies | ILP-2 |
| Blocks | ILP-6 |
| Risk | HIGH |
| **Readiness** | **BLOCKED on ILP-2** |

---

### ILP-5 — Frontend Lifecycle Shell

| Field | Value |
|-------|-------|
| Purpose | LifecycleRuntimeProvider; route guards; polling circuit breaker |
| Governance inputs | FRONTEND_CAPABILITY_CONSUMPTION, CX authority |
| Deliverables | No 403 storms; no Error Boundary from lifecycle detail |
| Dependencies | ILP-2, ILP-3 |
| Blocks | None (parallel ILP-6) |
| Risk | HIGH |
| **Readiness** | **BLOCKED on ILP-2, ILP-3** |

---

### ILP-6 — API Responses

| Field | Value |
|-------|-------|
| Purpose | Safe string errors; `lifecycle_redirect`; `runtime_version` in 403 |
| Governance inputs | CX API error policy |
| Deliverables | Normalized error payloads; read-tier APIs for recovery |
| Dependencies | ILP-4 |
| Risk | MEDIUM |
| **Readiness** | **BLOCKED on ILP-4** |

---

### ILP-7 — Session Authority

| Field | Value |
|-------|-------|
| Purpose | Enforce `session_policy` on transitions |
| Governance inputs | ALPA session table |
| Deliverables | session_version rules; force_reauth flows |
| Dependencies | ILP-2 |
| Risk | MEDIUM |
| **Readiness** | **BLOCKED on ILP-2** |

---

### ILP-8 — Background Services

| Field | Value |
|-------|-------|
| Purpose | Jobs consume `background_policy` + `communication_policy` |
| Governance inputs | Background capability matrix |
| Deliverables | Replace clients.subscription_status filters |
| Dependencies | ILP-2 |
| Risk | HIGH |
| **Readiness** | **BLOCKED on ILP-2** |

---

### ILP-9 — Lifecycle Events

| Field | Value |
|-------|-------|
| Purpose | Event bus; audit; runtime invalidation |
| Governance inputs | Event authority, versioning doc |
| Deliverables | Canonical events; idempotency store |
| Dependencies | ILP-1, ILP-2 |
| Risk | MEDIUM |
| **Readiness** | **BLOCKED on ILP-1, ILP-2** |

---

### ILP-10 — Legacy Removal

| Field | Value |
|-------|-------|
| Purpose | Remove parallel lifecycle consumers |
| Governance inputs | Runtime consumers doc, deprecation policy |
| Deliverables | No hasFeature lifecycle; no canonical in 403; no job mirror reads |
| Dependencies | ILP-1 through ILP-9 |
| Risk | HIGH |
| **Readiness** | **BLOCKED on ILP-1–9** |

---

## Missing prerequisites

| Item | Status | Blocker? |
|------|--------|----------|
| Governance document set | Complete | No |
| Consistency review | Complete | No |
| Policy pins frozen | v1 | No |
| Runtime schema | 1.0.0 | No |
| Stakeholder sign-off | Pending | **Yes for production ILP; recommend proceed ILP-1 on develop** |
| READ_ONLY platform band | Documented gap | No — ILP-1 implements |
| Communication Authority glossary cross-link | Referenced | No — ILP-8 integrates LCA |
| Codebase implementation | None started | Expected |

**No undocumented behaviour dependencies identified.**

---

## Recommended first sprint (ILP-1)

1. Implement `AccountLifecycleStateResolver` reading `client_billing` + org lifecycle.
2. Map to 15-state enum per ALPA.
3. Unit tests for all audit-mapped Stripe → state paths.
4. Persist `account_lifecycle_state` snapshot (no consumer migration yet).
5. Do **not** change frontend, middleware, or jobs in ILP-1.

---

## Governance documents — commit status (develop)

| Document set | Committed to develop |
|--------------|---------------------|
| Capability authority | ✓ `3ca32450` |
| Runtime contract | ✓ `0236a8d3` |
| Policy authority | Uncommitted (working tree) |
| Governance review | Uncommitted (this programme) |

Recommend scoped commit for policy + governance review packs before ILP-1 merge requests.

---

## Freeze rules during implementation

1. Do not add lifecycle states, portal modes, or CAP_* IDs without governance amendment.
2. Schema changes require semver + review.
3. ILP programmes must not introduce lifecycle decisions outside runtime contract.
4. Billing/Stripe remain fact sources only.

---

**Outcome:** `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS_COMPLETE`  
**Decision:** **ILP-1 READY TO BEGIN** upon governance review approval
