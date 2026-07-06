# Account Lifecycle Implementation Readiness

**Programme:** ACCOUNT-LIFECYCLE-GOVERNANCE-CONSISTENCY-REVIEW-01  
**Reconciliation:** ACCOUNT-LIFECYCLE-GOVERNANCE-RECONCILIATION-01  
**Status:** **ILP-1–8 IMPLEMENTED — ILP-9–10 PENDING**  
**Parent:** `ACCOUNT_LIFECYCLE_GOVERNANCE_REVIEW.md`  
**Mapping:** `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING.md` (authoritative cross-reference)

---

## Governance note

During implementation, several governance ILPs were delivered within other implementation programmes. The **original governance roadmap** is preserved in the historical section below and in `ACCOUNT_LIFECYCLE_GOVERNANCE_REVIEW.md`. **Future work (ILP-8–10)** follows the **reconciled governance names** in this document, not the historical implementation sequencing.

---

## Current implementation status (develop)

| ILP | Programme | Status |
|-----|-----------|--------|
| **ILP-1** | Lifecycle State Resolver | ✓ **Complete** |
| **ILP-2** | Runtime Contract API | ✓ **Complete** |
| **ILP-3** | Portal Mode Consumption | ✓ **Complete** |
| **ILP-4** | Capability Enforcement | ✓ **Complete** |
| **ILP-5** | Session Runtime Authority | ✓ **Complete** |
| **ILP-6** | Background Runtime Authority | ✓ **Complete** |
| **ILP-7** | Lifecycle Response Authority | ✓ **Complete** |
| **ILP-8** | Customer Communications & Reactivation | ✓ **Complete** |
| **ILP-9** | Lifecycle Events | ⬜ **Pending** |
| **ILP-10** | Platform Convergence | ⬜ **Pending** |

**Programme gate:** Platform Release Readiness (full regression) — pending after ILP-10.

---

## Implemented authority stack

```
Lifecycle Resolver
        ↓
Runtime Contract
        ↓
Capability Authority
        ↓
Session Runtime Authority
        ↓
Background Runtime Authority
        ↓
Lifecycle Response Authority
        ↓
Customer Communications & Reactivation    ← ILP-8 ✓
        ↓
Lifecycle Events                          ← ILP-9
        ↓
Platform Convergence                      ← ILP-10
        ↓
Platform Release Readiness
```

Portal Mode (ILP-3) consumes the Runtime Contract for presentation; it is not an enforcement authority in this stack.

---

## Implementation evidence (ILP-1 → ILP-7)

| ILP | Verdict | Evidence |
|-----|---------|----------|
| ILP-1 | `ILP_01_COMPLETE` | `audit/account_lifecycle_ilp_01/` |
| ILP-2 | `ILP_02_COMPLETE` | `audit/account_lifecycle_ilp_02/` |
| ILP-3 | `ILP_03_COMPLETE` | `audit/account_lifecycle_ilp_03/` |
| ILP-4 | Complete (Wave 1–4) | `audit/account_lifecycle_ilp_04/` |
| ILP-5 | Production ready (session) | `audit/account_lifecycle_ilp_05/` |
| ILP-6 | `ILP_06_IMPLEMENTED_TARGETED_VALIDATION_PASS_REGRESSION_DEFERRED` | `audit/account_lifecycle_ilp_06/` |
| ILP-7 | `ILP_07_IMPLEMENTED_TARGETED_VALIDATION_PASS_REGRESSION_DEFERRED` | `audit/account_lifecycle_ilp_07/` |

Governance ↔ implementation numbering: see `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING.md`.

---

## Remaining programmes

### ILP-8 — Customer Communications & Reactivation

| Field | Value |
|-------|-------|
| Purpose | Lifecycle-aware communication governance, suppression, recovery journeys, reactivation orchestration |
| Dependencies | ILP-1, ILP-2, ILP-4, ILP-5, ILP-6, ILP-7 |
| Governance inputs | Communication Authority, LCA, reactivation policy, `communication_policy` |
| Deliverables | Central communication eligibility; template governance; recovery orchestration |
| Risk | HIGH |
| **Readiness** | **READY** (dependencies implemented) |

Scope includes: communication authority, lifecycle-aware templates, email/SMS/notification/push governance, communication suppression, recovery journeys, account reactivation, lifecycle recovery orchestration.

**Note:** Background job runtime (historical governance “Background Services”) is **already delivered** in implementation ILP-6 — not part of ILP-8.

---

### ILP-9 — Lifecycle Events

| Field | Value |
|-------|-------|
| Purpose | Canonical lifecycle events, emission, runtime invalidation, audit/integration/analytics |
| Dependencies | ILP-1 through ILP-8 |
| Governance inputs | Event authority, versioning doc |
| Deliverables | Event model, idempotency store, invalidation hooks |
| Risk | MEDIUM |
| **Readiness** | **BLOCKED on ILP-8** |

---

### ILP-10 — Platform Convergence

| Field | Value |
|-------|-------|
| Purpose | Remove parallel lifecycle consumers; retire compatibility wrappers |
| Dependencies | ILP-1 through ILP-9 |
| Governance inputs | Runtime consumers doc, deprecation policy |
| Deliverables | No `hasFeature` lifecycle; no `canonical_entitlement_state` in customer paths; no job mirror reads |
| Risk | HIGH |
| **Readiness** | **BLOCKED on ILP-1–9** |

Scope includes: legacy removal, compatibility wrapper retirement, duplicate lifecycle/capability removal, obsolete authority removal, final convergence verification.

---

## Dependency graph (remaining)

```
ILP-8  → depends on ILP-1, ILP-2, ILP-4, ILP-5, ILP-6, ILP-7  (all ✓)
ILP-9  → depends on ILP-1 … ILP-8
ILP-10 → depends on ILP-1 … ILP-9
Gate   → full regression after ILP-10
```

Do not reference obsolete implementation phase names (e.g. “governance ILP-6 API Responses” as pending — delivered as implementation ILP-7).

---

## Governance approval gate (historical)

| Gate | Requirement | Status |
|------|-------------|--------|
| G-1 | Audit complete | ✓ |
| G-2 | Policy authority complete | ✓ |
| G-3 | Capability authority complete | ✓ |
| G-4 | Runtime contract complete | ✓ |
| G-5 | Consistency review | ✓ |
| G-6 | Stakeholder approval | Recorded via implementation on develop |

---

## Historical governance roadmap (preserved)

The table below is the **original governance sequence** from Governance Consistency Review 01. It is **not** the current implementation order. See mapping document for delivery traceability.

```
ILP-1  Lifecycle State Resolver          → delivered as ILP-1
  ↓
ILP-2  Runtime Contract API              → delivered as ILP-2
  ↓
ILP-3  Portal Mode                       → delivered as ILP-3
  ↓
ILP-4  Capability Enforcement            → delivered as ILP-4
  ↓
ILP-5  Frontend Lifecycle Shell          → delivered as ILP-3 + ILP-5
  ↓
ILP-6  API Responses                     → delivered as ILP-7
  ↓
ILP-7  Session Authority                 → delivered as ILP-5
  ↓
ILP-8  Background Services               → delivered as ILP-6
  ↓
ILP-9  Lifecycle Events                  → pending (reconciled ILP-9)
  ↓
ILP-10 Legacy Removal                    → pending (reconciled ILP-10)
```

Reconciled **future** ILP-8 is **Customer Communications & Reactivation** (not Background Services).

---

## Freeze rules (still active)

1. Do not add lifecycle states, portal modes, or CAP_* IDs without governance amendment.
2. Schema changes require semver + review.
3. ILP programmes must not introduce lifecycle decisions outside runtime contract.
4. Billing/Stripe remain fact sources only.
5. Do not begin ILP-8 until governance reconciliation is reviewed (`ACCOUNT-LIFECYCLE-GOVERNANCE-RECONCILIATION-01`).

---

## Deferred from completed ILPs (programme gate)

| Item | Owner ILP | Resolved in |
|------|-----------|-------------|
| Full backend/frontend regression | Programme gate | Platform Release Readiness |
| Non-customer background schedulers | ILP-6 | ILP-10 or ops programme |
| Plan-gate plain-string 403s | ILP-7 | ILP-10 |
| Legacy consumer fields | Multiple | ILP-10 |

---

**Outcome:** `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS_RECONCILED`  
**Decision:** **ILP-8 READY TO PLAN** upon reconciliation review; **do not implement ILP-8 until reconciliation is approved**
