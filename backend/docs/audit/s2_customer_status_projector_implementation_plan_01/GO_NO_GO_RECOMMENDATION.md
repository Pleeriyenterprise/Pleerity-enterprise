# GO / NO-GO — S2 implementation

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Date:** 2026-06-02

**Inputs approved:**
- PR-1A vocabulary authority
- PR-1B vocabulary hardening
- S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01
- S2-PROJECTION-SOURCE-DISPOSITION-AUDIT-01

---

## Decision summary

| Scope | Verdict |
|-------|---------|
| **Implementation plan** | **GO** — complete |
| **S2 code implementation start** | **GO WITH CONDITIONS** |
| **S2 staging shadow** | **GO** after merge + disabled soak |
| **S2 production shadow** | **GO** after staging G1–G6 |
| **S2 production active** | **NO-GO** until production shadow G1–G6 + REM verification |
| **S3 start** | **NO-GO** until S2 active stable on staging |

---

## Rationale

This plan converts approved architecture and disposition audit into a concrete, bounded S2 scope:

- Single module `customer_status_projector_v2.py` at enrich time
- Feature-flagged `disabled` | `shadow` | `active`
- All **five mandatory backend remediations** included with tests and rollback
- 12-family fixture pack defined
- Frontend, reports, emails, and data explicitly unchanged
- Shadow-first rollout with G1–G6 gates

No undisclosed second authority path remains if REM-01 and REM-02 ship with active mode.

---

## Conditions before writing code

| # | Condition | Owner |
|---|-----------|-------|
| 1 | Approve this implementation plan package | Platform Architecture + Product |
| 2 | Approve MODULE_DESIGN + INTEGRATION_MAP | Platform Architecture |
| 3 | Confirm `CUSTOMER_STATUS_PROJECTOR_V2_MODE` env wiring with Ops | Ops |
| 4 | Assign S2 PR owner | Engineering |
| 5 | Fixture pack in same PR or immediately prior | Engineering |
| 6 | S2 PR checklist includes all REM-01..REM-05 | Engineering |

---

## Mandatory remediations — inclusion confirmed

| ID | Remediation | In plan | Risk if excluded |
|----|-------------|---------|------------------|
| REM-01 | requirement_truth overwrite | **Yes** | CRITICAL |
| REM-02 | derive_truth_presentation labels | **Yes** | CRITICAL |
| REM-03 | operational_cognition alignment | **Yes** | HIGH |
| REM-04 | actionability banners/stage | **Yes** | HIGH |
| REM-05 | take_action after projector | **Yes** | HIGH |

**None excluded.**

---

## NO-GO triggers

| Trigger | Action |
|---------|--------|
| Implement without disposition audit approval | Reject |
| Frontend changes in S2 PR | Reject — S3 |
| Mongo migration for status | Reject |
| Skip shadow mode | Reject |
| flag=active without G1–G6 | Reject |
| Merge without REM-01..05 | Reject for active promotion |
| PR-1B CI gate failing | Fix first |

---

## S2 boundary confirmation

| In scope | Out of scope |
|----------|--------------|
| Backend projector + enrich integration | Frontend consumers |
| Shadow comparison + logging | Reports/emails |
| 5 backend remediations | Feature flag admin UI |
| Additive API fields | Data mutations |
| 12-family test fixtures | S3/S4/S5 work |

---

## Final recommendation

**GO WITH CONDITIONS** to begin S2 **code implementation**.

The plan is sufficient to prevent legacy projection from surviving alongside `customer_status_projector_v2` on the backend enrich path, provided shadow soak completes before active promotion and all five remediations ship in the S2 PR.

**Do not recommend production `active`** until shadow acceptance passes and staging active pilot verifies REM-01..05.
