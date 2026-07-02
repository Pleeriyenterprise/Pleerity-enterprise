# Account Lifecycle Governance Review

**Programme:** ACCOUNT-LIFECYCLE-GOVERNANCE-CONSISTENCY-REVIEW-01  
**Review date:** 2026-06-30  
**Branch:** develop  
**Reviewer:** Architecture review (automated cross-document validation)

---

## Executive decision

### Verdict: **GOVERNANCE APPROVED FOR IMPLEMENTATION**

The complete account lifecycle governance architecture is **internally consistent**, **free from material contradictions** after harmonization, and **ready for ILP-1 (Lifecycle State Resolver)**.

| Decision | Status |
|----------|--------|
| Governance frozen for implementation | **Yes** — subject to version pins below |
| ILP-1 may begin | **Yes** |
| New governance required before ILP-1 | **No** |
| Material blockers remaining | **None** |

**Version pins (frozen):**

- `account_lifecycle_policy_v1`
- `account_capability_v1`
- `account_lifecycle_runtime_v1` (schema `1.0.0`)

---

## Scope reviewed

19 governance documents cross-validated:

| Layer | Documents |
|-------|-----------|
| Policy | ALPA, Policy Matrix, Portal Mode, Transitions, Events, Reactivation, Customer Experience |
| Capability | ACA, Catalog, Matrices (lifecycle, feature, API, portal mode, background), State Diagram |
| Runtime | Runtime Contract, Schema, Consumers, Versioning |

Prior audit and evidence JSON programmes inform context but were not re-opened for new governance.

---

## Review summary by phase

### Phase 1 — Lifecycle states: **PASS**

15 states uniquely defined across all documents:

`ACTIVE`, `TRIAL`, `TRIAL_EXPIRED`, `PAYMENT_PENDING`, `PAYMENT_FAILED`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `READ_ONLY`, `SUSPENDED`, `ARCHIVED`, `ACCOUNT_DELETED`, `UNKNOWN`, `LEGACY`

| Check | Result |
|-------|--------|
| Duplicate names | None |
| Undefined states | None |
| Orphan states | None |
| Runtime schema enum match | Exact match |
| Diagram coverage | All states present |

**Note:** Capability matrix uses column abbreviations (`TRIAL_EXP`, `CANCEL_SCHED`) — same states, not duplicates (**TERMINOLOGY_DRIFT**, non-blocking).

---

### Phase 2 — Portal modes: **PASS**

8 portal modes uniquely defined:

`FULL_ACCESS`, `READ_ONLY`, `BILLING_RECOVERY`, `PAYMENT_REQUIRED`, `GRACE`, `SUSPENDED`, `ARCHIVED`, `ACCOUNT_DELETED`

| Check | Result |
|-------|--------|
| Lifecycle mapping | Consistent APMA ↔ ALPA ↔ Runtime |
| Customer experience | All modes covered (see Phase 8 note) |
| Capability mapping | Portal mode capability matrix complete |
| Runtime representation | `portal_mode` field + `navigation_policy` |
| Duplicates | None |

**Clarification (non-blocking):** `PAYMENT_FAILED` lifecycle state maps to `FULL_ACCESS` portal mode with warning banner; `GRACE_PERIOD` maps to `GRACE` portal mode. APMA conditional wording for PAYMENT_FAILED is resolved by state transition T-006, not dual portal assignment.

---

### Phase 3 — Capabilities: **PASS**

| Check | Result |
|-------|--------|
| Catalog entries | 89 `CAP_*` identifiers |
| Unique IDs | No duplicates |
| Owner per capability | All catalogued |
| Lifecycle matrix | Core + background caps covered |
| Feature mapping | Plan + ops flags mapped |
| API mapping | Customer API surfaces covered |
| Portal mode mapping | All 8 modes |
| Runtime contract | Pre-resolved in `capabilities` map |

**Known platform gap (documented, not contradiction):** `READ_ONLY` lifecycle state has no current platform band — consistently marked POLICY_GAP across ALPA, ACA, audit. Implementation is ILP-1 scope.

**Orphan capabilities:** None material. Summary matrix abbreviates rows; full catalog is authoritative.

---

### Phase 4 — Runtime contract: **PASS**

| Check | Result |
|-------|--------|
| Single resolver owner | ILP-1 + ILP-2 |
| Schema version | `1.0.0` |
| Field ownership matrix | Complete in ACCOUNT_RUNTIME_SCHEMA.md |
| No duplicate semantics | `lifecycle_state` vs `portal_mode` vs `capabilities` distinct |
| Consumer bypass inventory | Documented; all must migrate (ILP-2–10) |
| Forbidden inputs list | Consistent across runtime contract + evidence |

---

### Phase 5 — Transitions: **PASS**

21 transitions (T-001–T-021) validated:

| Check | Result |
|-------|--------|
| Valid source/destination states | All reference governed enums |
| Events referenced | All map to event authority |
| Portal mode postconditions | Consistent |
| Session/communication/background | Cross-referenced |
| Impossible transitions | None defined |

**Documented future transitions (not contradictions):** T-014 (SUBSCRIPTION_EXPIRED → READ_ONLY) marked TRANSITION_GAP — timer job not yet specified in code; policy is consistent.

---

### Phase 6 — Lifecycle events: **PASS**

| Check | Result |
|-------|--------|
| Unique event IDs | 20 canonical events |
| Transition coverage | Each material transition emits events |
| Duplicate meanings | None |
| Owner + consumers | Event authority registry complete |
| Unused events | `PAYMENT_PENDING`, `LEGACY_MIGRATED` have defined triggers |

---

### Phase 7 — Reactivation: **PASS**

12 paths (R-001–R-012) validated:

| Check | Result |
|-------|--------|
| Source/destination states | Valid |
| Portal mode transitions | Defined |
| Capability restoration | Scoped per path |
| Session/background/communication | Cross-referenced |
| Runtime contract support | `reactivation_policy` field |
| Unsupported paths | None |

---

### Phase 8 — Customer experience: **PASS WITH NOTES**

All 8 portal modes have full experience templates.

| Portal mode | CX document section |
|-------------|---------------------|
| FULL_ACCESS | ✓ (covers ACTIVE, TRIAL, CANCELLATION_SCHEDULED, PAYMENT_FAILED via banner) |
| GRACE | ✓ |
| BILLING_RECOVERY | ✓ |
| PAYMENT_REQUIRED | ✓ |
| READ_ONLY | ✓ |
| SUSPENDED | ✓ |
| ARCHIVED | ✓ |
| ACCOUNT_DELETED | ✓ |

**Minor notes (non-blocking):**

- `UNKNOWN` state inherits `BILLING_RECOVERY` CX — not a separate section (**TERMINOLOGY_DRIFT**).
- `LEGACY` inherits `READ_ONLY` CX subset — documented in portal mode mapping.
- `ACCOUNT_DELETED` section omits explicit available/unavailable feature lists — acceptable for terminal deny state.

No contradictory messaging found across portal modes.

---

### Phase 9 — Terminology: **PASS WITH NOTES**

| Concept | Canonical term | Drift found |
|---------|----------------|-------------|
| Subscription ended (period) | `SUBSCRIPTION_EXPIRED` | None |
| Subscription cancelled now | `CANCELLED_IMMEDIATE` | None |
| Cancel at period end | `CANCELLATION_SCHEDULED` | Audit used `CANCEL_SCHEDULED` historically — mapped |
| Read-only access | `READ_ONLY` state / portal mode | Consistent |
| Suspension | `SUSPENDED` | Distinct from expiry/cancel |
| Archiving | `ARCHIVED` | Distinct |
| Deletion | `ACCOUNT_DELETED` | Distinct |
| Reactivation | `ACCOUNT_REACTIVATED` event | Consistent |
| Grace | `GRACE_PERIOD` state / `GRACE` portal mode | Consistent pairing |
| Payment recovery | `BILLING_RECOVERY` portal mode | Consistent |
| Capability vs entitlement | `CAP_*` vs plan `feature_key` | ACA defines overlay — consistent |
| API endpoint | `lifecycle-runtime` primary; `lifecycle-contract` alias | Harmonized in runtime versioning |

---

### Phase 10 — Implementation readiness: **PASS**

Canonical ILP sequence harmonized in `ACCOUNT_LIFECYCLE_IMPLEMENTATION_READINESS.md`.

All ILP dependencies documented. No programme depends on undocumented behaviour.

---

### Phase 11 — Authority boundaries: **PASS**

| Authority | Responsibility | Overlap |
|-----------|----------------|---------|
| Requirement Authority | Obligation logic | None — access via CAP_REQ_* |
| Lifecycle Authority (req) | Requirement lifecycle | None — distinct from account lifecycle |
| Navigation Authority | Nav structure | Visibility via navigation_policy |
| Score Authority | Score calculation | Visibility via CAP_SCORE_* |
| Communication Authority | Channel rules | Send via communication_policy |
| Email Presentation Authority | Email layout | Copy via template_family |
| Report Presentation Authority | Report layout | Eligibility via CAP_REPORT_* |
| Lifecycle Policy Authority | Business rules | Source for resolver |
| Capability Authority | Permission language | Resolved into contract |
| Runtime Contract | Single runtime object | Consumer-only for behaviour |

No circular dependencies. Resolver consumes facts; consumers read contract only.

---

## Findings resolved during review

| ID | Classification | Issue | Resolution |
|----|----------------|-------|------------|
| GCR-001 | DOCUMENT_INCONSISTENCY | ALPA background table: GRACE scheduled reports "Pause new schedules" vs policy matrix "Continue" | **Fixed** in ALPA — aligned to Continue |
| GCR-002 | DOCUMENT_INCONSISTENCY | ILP roadmap differed between ALPA and Runtime Contract | **Fixed** in ALPA — harmonized to runtime sequence |
| GCR-003 | TERMINOLOGY_DRIFT | Older ILP labels in committed ACA doc | Superseded by Implementation Readiness canonical table |
| GCR-004 | TERMINOLOGY_DRIFT | Capability matrix column abbreviations | Documented; catalog authoritative |
| GCR-005 | NO_CHANGE_REQUIRED | READ_ONLY platform gap | Known; ILP-1 implementation scope |
| GCR-006 | NO_CHANGE_REQUIRED | Current codebase drift | Expected; ILP-2–10 address |

---

## Governance freeze declaration

Effective upon approval of this review:

1. **No new lifecycle states, portal modes, or capability IDs** without governance amendment programme.
2. **Schema changes** require semver bump per `ACCOUNT_RUNTIME_VERSIONING.md`.
3. **ILP-1** is the first permitted implementation programme.
4. Policy pins locked at v1 until post-ILP-10 review.

---

## Approval

| Criterion | Met |
|-----------|-----|
| Internally consistent | ✓ |
| Lifecycle states unique | ✓ |
| Portal modes governed | ✓ |
| Capabilities governed | ✓ |
| Runtime fields owned | ✓ |
| Transitions valid | ✓ |
| Events consumed | ✓ |
| Reactivation supported | ✓ |
| Terminology consistent | ✓ |
| No authority overlap | ✓ |
| ILP dependencies complete | ✓ |
| Ready for implementation | ✓ |

---

**Outcome:** `ACCOUNT_LIFECYCLE_GOVERNANCE_REVIEW_COMPLETE`  
**Decision:** `GOVERNANCE_APPROVED_FOR_IMPLEMENTATION`
