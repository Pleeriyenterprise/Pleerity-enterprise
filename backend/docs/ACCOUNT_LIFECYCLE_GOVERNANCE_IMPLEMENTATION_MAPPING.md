# Account Lifecycle Governance ↔ Implementation Mapping

**Programme:** ACCOUNT-LIFECYCLE-GOVERNANCE-RECONCILIATION-01  
**Status:** **AUTHORITATIVE** — supersedes conflicting ILP roadmap tables in individual authority documents  
**Branch:** `develop`  
**Reconciled:** 2026-07-06 UTC

---

## Governance note (traceability)

During implementation, several **governance ILPs** were delivered within **other implementation programmes** (different numbering and sequencing). This document preserves complete architectural traceability between governance planning and what was built on `develop`.

**Do not rewrite history.** Original governance programme names and objectives remain in `ACCOUNT_LIFECYCLE_GOVERNANCE_REVIEW.md`, `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md` (historical roadmap section), and individual ILP audit reports. Use **this mapping** as the single cross-reference for “what was planned” vs “what was delivered.”

---

## Implementation authority stack (as built)

This is the **actual runtime architecture** on `develop` today:

```
Lifecycle Resolver          (ILP-1)
        ↓
Runtime Contract            (ILP-2)
        ↓
Capability Authority        (ILP-4)
        ↓
Session Runtime Authority   (ILP-5)
        ↓
Background Runtime Authority (ILP-6)
        ↓
Lifecycle Response Authority (ILP-7)
        ↓
Customer Communications & Reactivation   (ILP-8 ✓)
        ↓
Lifecycle Events                       (ILP-9 ✓)
        ↓
Platform Convergence                   (ILP-10 ✓)
        ↓
Platform Release Readiness               (programme gate — next)
```

Portal Mode consumption (ILP-3) is a **presentation layer** that reads the Runtime Contract; it does not sit in the enforcement stack above.

---

## Authoritative mapping table

| Governance ILP | Original governance objective | Implementation programme(s) | Completion | Evidence |
|----------------|------------------------------|------------------------------|------------|----------|
| **ILP-1** | Lifecycle State Resolver — map billing/org facts → `account_lifecycle_state` | **ILP-1** | ✓ Complete | `audit/account_lifecycle_ilp_01/` |
| **ILP-2** | Runtime Contract API — `GET /api/client/lifecycle-runtime` | **ILP-2** | ✓ Complete | `audit/account_lifecycle_ilp_02/` |
| **ILP-3** | Portal Mode — shell consumes `portal_mode`, `customer_experience`, `navigation_policy` | **ILP-3** | ✓ Complete | `audit/account_lifecycle_ilp_03/` |
| **ILP-4** | Capability Enforcement — APIs/guards check `capabilities` map | **ILP-4** | ✓ Complete | `audit/account_lifecycle_ilp_04/` |
| **ILP-5** | Frontend Lifecycle Shell — route guards, polling, no 403 storms | **ILP-3** + **ILP-5** | ✓ Complete | ILP-3 portal shell; ILP-5 session refresh shell |
| **ILP-6** | API Responses — safe errors, `lifecycle_redirect`, `runtime_version` in 403 | **ILP-7** | ✓ Complete | `audit/account_lifecycle_ilp_07/` |
| **ILP-7** | Session Authority — `session_policy`, force_reauth, runtime version sync | **ILP-5** | ✓ Complete | `audit/account_lifecycle_ilp_05/` |
| **ILP-8** *(historical)* | Background Services — jobs consume `background_policy` | **ILP-6** | ✓ Complete | `audit/account_lifecycle_ilp_06/` |
| **ILP-8** *(reconciled)* | Customer Communications & Reactivation | **ILP-8** | ✓ Complete | `audit/account_lifecycle_ilp_08/` |
| **ILP-9** | Lifecycle Events — event bus, audit, runtime invalidation | **ILP-9** | ✓ Complete | `audit/account_lifecycle_ilp_09/` |
| **ILP-10** | Platform Convergence / Legacy Removal | **ILP-10** | ✓ Complete | `audit/account_lifecycle_ilp_10/` |

### Numbering reconciliation

| Topic | Governance (original) | Implementation (actual) |
|-------|----------------------|-------------------------|
| API lifecycle responses | Governance **ILP-6** | Implementation **ILP-7** |
| Session runtime | Governance **ILP-7** | Implementation **ILP-5** |
| Background runtime | Governance **ILP-8** | Implementation **ILP-6** |
| Frontend shell | Governance **ILP-5** | Split: **ILP-3** (portal) + **ILP-5** (session sync) |

**Future programmes ILP-8–10** use the **reconciled governance names** in `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS.md`, not the historical implementation sequence numbers.

---

## Implementation programme index (ILP-1 → ILP-7)

| Impl ILP | Programme ID | Module / deliverable | Governance source |
|----------|--------------|---------------------|-------------------|
| ILP-1 | ILP-1-LIFECYCLE-STATE-RESOLVER-01 | `account_lifecycle_state_resolver.py` | Gov ILP-1 |
| ILP-2 | ILP-2-RUNTIME-CONTRACT-API-01 | `account_lifecycle_runtime_contract.py`, `/lifecycle-runtime` | Gov ILP-2 |
| ILP-3 | ILP-3-PORTAL-MODE-CONSUMPTION-01 | `LifecycleRuntimeContext`, `LifecycleShell` | Gov ILP-3 (+ partial Gov ILP-5) |
| ILP-4 | ILP-4-CAPABILITY-ENFORCEMENT-* | `account_capability_enforcement.py`, `capability_gating.py` | Gov ILP-4 |
| ILP-5 | ILP-5-SESSION-RUNTIME-AUTHORITY-01 | `SessionRuntimeService`, session refresh API | Gov ILP-7 |
| ILP-6 | ILP-6-BACKGROUND-PROCESSING-RUNTIME-AUTHORITY-01 | `account_background_runtime_authority.py` | Gov ILP-8 (historical) |
| ILP-7 | ILP-7-LIFECYCLE-RESPONSE-AUTHORITY-01 | `account_lifecycle_response_authority.py` | Gov ILP-6 |

---

## Remaining programmes (reconciled roadmap)

### ILP-8 — Customer Communications & Reactivation

**Dependencies:** ILP-1, ILP-2, ILP-4, ILP-5, ILP-6, ILP-7 (all implemented)

Scope includes:

- Communication authority integration
- Lifecycle-aware templates
- Email, SMS, notification, push governance
- Communication suppression
- Recovery journeys and account reactivation
- Lifecycle recovery orchestration

**Not in scope:** Background runtime (delivered in implementation ILP-6).

---

### ILP-9 — Lifecycle Events ✓

**Status:** Complete — see `audit/account_lifecycle_ilp_09/`

Delivered: `account_lifecycle_event_authority.py`, runtime transition publication, CommunicationSuppressed, cache invalidation consumers, audit integration.

---

### ILP-10 — Platform Convergence ✓

**Status:** Complete — see `audit/account_lifecycle_ilp_10/`

Delivered: convergence audit, obsolete module removal, route guard migration, platform architecture documentation.

**Next:** Platform Release Readiness audit (full regression).

---

## Programme gate

**Platform Release Readiness** — full backend/frontend regression and production-critical validation. Not an ILP implementation programme; runs after ILP-10 closeout.

---

## Document precedence

| Question | Authoritative source |
|----------|---------------------|
| What was originally planned? | Historical sections in ALPA, Governance Review, this mapping § mapping table |
| What was actually built? | Implementation ILP audit reports + this mapping |
| What remains to build? | `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS.md` § Remaining roadmap |
| How do governance vs impl numbers relate? | **This document** |

When individual authority documents conflict with this mapping, **this mapping wins** for roadmap and completion status.

---

**Outcome:** `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING_COMPLETE`
