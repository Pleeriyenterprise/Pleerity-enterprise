# Account Lifecycle Policy Authority

**Programme:** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01  
**Authority version:** `account_lifecycle_policy_v1`  
**Precedes:** All lifecycle implementation programmes  
**Follows:** ACCOUNT-LIFECYCLE-AUTHORITY-AUDIT-01  
**Branch:** develop (policy only — no implementation)

---

## Purpose

This document is the **governance contract** for the entire customer account lifecycle on Pleerity Enterprise / Compliance Vault Pro.

The audit proved lifecycle enforcement is fragmented across authentication, billing, entitlements, sessions, frontend routing, background services, and communications. **No subsystem may infer lifecycle behaviour independently after this policy is approved.**

This programme does **not** implement fixes. It defines the business, operational, and technical policy every subsystem must consume.

---

## Authority hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│  Account Lifecycle Policy Authority (this programme)          │
│  — business policy matrix, portal modes, transitions, events │
└───────────────────────────┬─────────────────────────────────┘
                            │ consumes (does not replace)
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  Stripe (payment      subscription_      client_lifecycle_
  facts only)          lifecycle_service   service (org funnel)
        │                   │                   │
        └──────────► Lifecycle State Resolver (implementation future)
                            │
                            ▼
              account_lifecycle_state (policy enum)
                            │
                            ▼
              portal_mode (customer-facing contract)
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   API authorisation   Frontend shell      Background jobs
   Session policy      Communications      Reports / Today /
   Entitlements        Navigation          Command Centre / etc.
```

### Preserved authorities (must not be replaced)

| Authority | Relationship to ALPA |
|-----------|----------------------|
| Requirement Authority | Obligation logic unchanged; **access** governed by ALPA |
| Lifecycle Authority (requirements) | Requirement lifecycle semantics unchanged |
| Evidence Authority | Evidence truth unchanged; **upload/download** governed by ALPA |
| Navigation Authority | Nav structure unchanged; **visibility** governed by portal mode |
| Score Authority | Score calculation unchanged; **visibility** governed by ALPA |
| Today Authority | Task ranking unchanged; **surface access** governed by ALPA |
| Command Centre Authority | Aggregation unchanged; **access** governed by ALPA |
| Communication Authority | Channel rules unchanged; **send eligibility** governed by ALPA |
| Email Presentation Authority | Email layout unchanged; **lifecycle copy** via LCA + ALPA |
| Report Presentation Authority | Report layout unchanged; **generation eligibility** governed by ALPA |

**Stripe** remains payment fact source. **ALPA** defines what those facts mean for customer experience.

---

## Canonical policy enums

### Account lifecycle state (`account_lifecycle_state`)

Single policy enum consumed by all subsystems:

| State | Business meaning |
|-------|------------------|
| `ACTIVE` | Paying or trialing; full entitled access |
| `TRIAL` | Trial period; full entitled access with trial messaging |
| `TRIAL_EXPIRED` | Trial ended without conversion |
| `PAYMENT_PENDING` | Onboarding / checkout incomplete |
| `PAYMENT_FAILED` | Payment attempt failed; not yet in grace |
| `GRACE_PERIOD` | Past due within grace window |
| `CANCELLATION_SCHEDULED` | Cancel at period end; access until period end |
| `CANCELLED_IMMEDIATE` | Subscription ended immediately by customer or admin |
| `SUBSCRIPTION_EXPIRED` | Billing period ended without renewal |
| `READ_ONLY` | Data retained; view/export limited; no mutations |
| `SUSPENDED` | Access restricted for non-payment, abuse, or ops suspension |
| `ARCHIVED` | Organisation archived; portal closed |
| `ACCOUNT_DELETED` | Account purged or marked deleted |
| `UNKNOWN` | Resolver could not determine; safe deny |
| `LEGACY` | Unmapped legacy record; read-only + billing recovery until migrated |

### Portal mode (`portal_mode`)

**Frontend must consume portal mode only** — never raw Stripe fields or `canonical_entitlement_state` directly.

See `ACCOUNT_PORTAL_MODE_AUTHORITY.md`.

### Lifecycle events

Canonical event catalogue in `ACCOUNT_LIFECYCLE_EVENT_AUTHORITY.md`.  
**Only** the Lifecycle State Resolver (future) and Stripe webhook adapters may emit state-changing events.

---

## Policy principles

1. **One customer-facing truth** — portal mode + lifecycle state label + recovery CTA.
2. **No silent partial function** — if access is denied, show intentional lifecycle screen; never 403 storms or Error Boundaries.
3. **Authentication ≠ entitlement** — valid JWT does not imply operational access.
4. **Cancellation ≠ expiry ≠ suspension ≠ read-only ≠ archive ≠ delete** — distinct concepts (Phase 10).
5. **Billing recovery always reachable** when subscription can be restored.
6. **Data retention** — cancel/expiry/suspend retain data unless `ACCOUNT_DELETED` policy applies.
7. **Background services** follow explicit continue/pause/read-only rules — no inference.
8. **Communications** consume Lifecycle Communication Authority + ALPA send matrix.
9. **Reactivation** is first-class with idempotent events and deterministic restoration scope.
10. **Audit everything** — every transition emits authoritative lifecycle event + audit log.

---

## Document map

| Document | Content |
|----------|---------|
| `ACCOUNT_LIFECYCLE_POLICY_MATRIX.md` | Per-state business policy (Phase 1) |
| `ACCOUNT_PORTAL_MODE_AUTHORITY.md` | Portal modes and UI contract (Phase 2) |
| `ACCOUNT_LIFECYCLE_TRANSITION_MATRIX.md` | Transitions, triggers, postconditions (Phase 3) |
| `ACCOUNT_LIFECYCLE_EVENT_AUTHORITY.md` | Canonical events (Phase 4) |
| `ACCOUNT_CUSTOMER_EXPERIENCE_AUTHORITY.md` | Per-mode customer journey (Phase 5) |
| Session policy | §Session Authority in this document + matrix |
| Background policy | §Background Processing in this document + matrix |
| Communication policy | §Communication Policy + LCA cross-reference |
| `ACCOUNT_REACTIVATION_AUTHORITY.md` | Reactivation paths (Phase 9) |
| `audit/.../ACCOUNT_LIFECYCLE_POLICY_EVIDENCE.json` | Evidence, gaps, roadmap |

---

## Session authority (Phase 6)

| Transition | JWT | Refresh | session_version | Customer experience |
|------------|-----|---------|-----------------|---------------------|
| ACTIVE → GRACE_PERIOD | Valid | Valid | No bump | Stay logged in; payment banner |
| GRACE → SUSPENDED | Valid until policy expiry | Revoke optional | **Bump recommended** | Forced re-auth or billing recovery mode |
| → CANCELLED_IMMEDIATE | Valid until policy expiry | Revoke | **Bump recommended** | Billing recovery mode; no operational APIs |
| → READ_ONLY | Valid | Valid | No bump | Read-only portal mode |
| → ARCHIVED | Invalidate | Revoke | **Bump required** | Sign-in blocked with explanation |
| → ACCOUNT_DELETED | Invalidate | Revoke | N/A | Sign-in denied |
| Admin force logout | Invalidate | Revoke | Bump | Sign-in |
| Reactivation → ACTIVE | New token optional | Reissue | Bump on restoration | Full access after entitlements refresh |

**Policy:** Lifecycle-changing transitions must include `entitlements_version` increment (existing) and **optional `session_version` bump** for terminal states. Frontend must refetch lifecycle contract on every visibility resume.

---

## Background processing policy (Phase 7)

| Lifecycle state | Reminders | Digest | Scheduled reports | Compliance monitoring | Risk/score calc | Queues |
|-----------------|-----------|--------|-------------------|----------------------|-----------------|--------|
| ACTIVE / TRIAL | Continue | Continue | Continue | Continue | Continue | Continue |
| CANCELLATION_SCHEDULED | Continue until expiry event | Continue | Continue | Continue | Continue | Continue |
| GRACE_PERIOD | Continue (no new side-effect features) | Continue | Continue | Continue read | Continue | Continue |
| CANCELLED_IMMEDIATE | **Pause** | **Pause** | **Revoke** | **Pause** | **Pause** | Drain then pause |
| SUBSCRIPTION_EXPIRED | **Pause** | **Pause** | **Pause** | **Pause** | **Pause** | Pause |
| READ_ONLY | **Pause** | **Pause** | **Pause** | **Pause** | **Pause** | Pause |
| SUSPENDED | **Pause** | **Pause** | **Pause** | **Pause** | **Pause** | Pause |
| ARCHIVED / DELETED | **Terminate** | **Terminate** | **Terminate** | **Terminate** | **Terminate** | Terminate |

**Policy:** Jobs must read **policy snapshot** from `client_billing` (or future `account_lifecycle_state`), not `clients` mirror alone.

---

## Communication policy (Phase 8)

All customer communications must:

1. Resolve `account_lifecycle_state` → portal mode → **Lifecycle Communication Authority** template family.
2. Never send operational reminders when state is `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `ACCOUNT_DELETED`.
3. Send payment/grace/recovery/cancellation/expiry/reactivation messages per communication matrix in evidence JSON.
4. Portal banners must match email/SMS lifecycle state wording (single glossary).

---

## Distinct lifecycle concepts (Phase 10)

| Concept | Customer expectation | Portal mode | Data |
|---------|---------------------|-------------|------|
| **Cancellation (scheduled)** | “I cancelled but can use until date X” | FULL_ACCESS until expiry event | Retained |
| **Cancellation (immediate)** | “I ended now; fix billing to return” | BILLING_RECOVERY | Retained |
| **Subscription expiry** | “My period ended” | BILLING_RECOVERY or READ_ONLY | Retained |
| **Suspension** | “Account blocked (payment or ops)” | SUSPENDED | Retained |
| **Read-only** | “I can view/export but not change” | READ_ONLY | Retained |
| **Archiving** | “Account closed; contact support” | ARCHIVED | Retained, hidden |
| **Deletion** | “Account removed” | ACCOUNT_DELETED | Purged per policy |
| **Reactivation** | “I'm back; restore my access” | → FULL_ACCESS per path | Restored per path |

---

## Authority consumption (Phase 11)

Every subsystem must consume **portal mode** derived from ALPA. Current drift (audit):

| Subsystem | Today consumes | Must consume |
|-----------|----------------|--------------|
| `middleware.client_route_guard` | `canonical_entitlement_state` | portal mode policy mapping |
| `plan_registry` / jobs | `entitlement_status` on clients | ALPA background matrix |
| `EntitlementsContext` | `/client/entitlements` features | portal mode + feature matrix |
| `ProtectedRoute` | JWT only | portal mode guard |
| `BillingPage` | `/billing/status` | portal mode (billing is subset) |
| Notification orchestrator | `entitlement_status` | ALPA communication matrix |
| Report generation | per-feature 403 | ALPA report policy |

---

## Implementation roadmap

**Authoritative status:** `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS.md`  
**Governance ↔ implementation mapping:** `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING.md`

During implementation, several governance ILPs were delivered within other implementation programmes. This section preserves the **original governance plan**; completion status and cross-reference are in the mapping document.

### Original governance sequence (historical)

| Phase | Programme | Purpose | Delivered in |
|-------|-----------|---------|--------------|
| **ILP-1** | Lifecycle State Resolver | Map Stripe+billing+org → `account_lifecycle_state` | ILP-1 ✓ |
| **ILP-2** | Runtime Contract API | `GET /api/client/lifecycle-runtime` → full contract | ILP-2 ✓ |
| **ILP-3** | Portal Mode | Shell consumes `portal_mode` + `customer_experience` | ILP-3 ✓ |
| **ILP-4** | Capability Enforcement | APIs check `capabilities` map | ILP-4 ✓ |
| **ILP-5** | Frontend Lifecycle Shell | Route guards, polling policy, no 403 storms | ILP-3 + ILP-5 ✓ |
| **ILP-6** | API Responses | Safe errors, lifecycle_redirect | ILP-7 ✓ |
| **ILP-7** | Session Authority | `session_policy` enforcement | ILP-5 ✓ |
| **ILP-8** | Background Services | `background_policy` from contract | ILP-6 ✓ |
| **ILP-9** | Lifecycle Events | Invalidation + event bus | ⬜ Pending |
| **ILP-10** | Legacy Removal | Remove parallel consumer fields | ⬜ Pending |

### Reconciled remaining roadmap

| ILP | Programme | Depends on |
|-----|-----------|------------|
| **ILP-8** | Customer Communications & Reactivation | ILP-1–7 ✓ |
| **ILP-9** | Lifecycle Events | ILP-1–8 |
| **ILP-10** | Platform Convergence | ILP-1–9 |

**ILP-1–7 implemented on develop.** Do not begin ILP-8 until governance reconciliation is reviewed.

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Every lifecycle state has governed business policy | ✓ `ACCOUNT_LIFECYCLE_POLICY_MATRIX.md` |
| Every transition has governed contract | ✓ `ACCOUNT_LIFECYCLE_TRANSITION_MATRIX.md` |
| Every event has authoritative owner | ✓ `ACCOUNT_LIFECYCLE_EVENT_AUTHORITY.md` |
| Every portal mode defined | ✓ `ACCOUNT_PORTAL_MODE_AUTHORITY.md` |
| Subsystem consumption documented | ✓ Phase 11 + evidence JSON |
| Session / background / communication policy | ✓ This document + matrices |
| Distinct lifecycle concepts | ✓ Phase 10 |
| Reactivation governed | ✓ `ACCOUNT_REACTIVATION_AUTHORITY.md` |
| Customer experience per mode | ✓ `ACCOUNT_CUSTOMER_EXPERIENCE_AUTHORITY.md` |
| Ready for implementation | ✓ Pending stakeholder approval |

---

**Outcome:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY_COMPLETE`
