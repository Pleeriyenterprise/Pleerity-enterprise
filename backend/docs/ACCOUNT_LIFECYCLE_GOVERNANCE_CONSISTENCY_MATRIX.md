# Account Lifecycle Governance Consistency Matrix

**Programme:** ACCOUNT-LIFECYCLE-GOVERNANCE-CONSISTENCY-REVIEW-01  
**Parent:** `ACCOUNT_LIFECYCLE_GOVERNANCE_REVIEW.md`

Cross-document presence matrix. **✓** = explicitly governed; **D** = derived; **G** = documented gap; **—** = not applicable.

---

## Lifecycle state × document

| State | ALPA | Policy Matrix | Portal Mode | Transitions | Events | Reactivation | CX | Capability Matrix | Runtime Schema | Diagram |
|-------|------|---------------|-------------|-------------|--------|--------------|-----|-------------------|----------------|---------|
| ACTIVE | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| TRIAL | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| TRIAL_EXPIRED | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| PAYMENT_PENDING | ✓ | ✓ | D | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| PAYMENT_FAILED | ✓ | ✓ | D | ✓ | ✓ | ✓ | D | ✓ | ✓ | ✓ |
| GRACE_PERIOD | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| CANCELLATION_SCHEDULED | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| CANCELLED_IMMEDIATE | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SUBSCRIPTION_EXPIRED | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| READ_ONLY | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SUSPENDED | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ARCHIVED | ✓ | ✓ | D | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ACCOUNT_DELETED | ✓ | ✓ | D | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| UNKNOWN | ✓ | ✓ | D | — | — | — | D | ✓ | ✓ | ✓ |
| LEGACY | ✓ | ✓ | D | ✓ | ✓ | ✓ | D | ✓ | ✓ | ✓ |

**D (derived):** Portal mode and PAYMENT_FAILED/UNKNOWN/LEGACY CX derived from mapping tables — consistent, not missing.

---

## Portal mode × document

| Portal Mode | APMA | PM Capability | CX | Runtime | Navigation Policy | Consistent |
|-------------|------|---------------|-----|---------|-------------------|------------|
| FULL_ACCESS | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| GRACE | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| BILLING_RECOVERY | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| PAYMENT_REQUIRED | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| READ_ONLY | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SUSPENDED | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ARCHIVED | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ACCOUNT_DELETED | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## Lifecycle state → portal mode (canonical)

| lifecycle_state | portal_mode | All docs agree |
|-----------------|-------------|----------------|
| ACTIVE | FULL_ACCESS | ✓ |
| TRIAL | FULL_ACCESS | ✓ |
| TRIAL_EXPIRED | PAYMENT_REQUIRED | ✓ |
| PAYMENT_PENDING | PAYMENT_REQUIRED | ✓ |
| PAYMENT_FAILED | FULL_ACCESS | ✓ |
| GRACE_PERIOD | GRACE | ✓ |
| CANCELLATION_SCHEDULED | FULL_ACCESS | ✓ |
| CANCELLED_IMMEDIATE | BILLING_RECOVERY | ✓ |
| SUBSCRIPTION_EXPIRED | BILLING_RECOVERY* | ✓ |
| READ_ONLY | READ_ONLY | ✓ |
| SUSPENDED | SUSPENDED | ✓ |
| ARCHIVED | ARCHIVED | ✓ |
| ACCOUNT_DELETED | ACCOUNT_DELETED | ✓ |
| UNKNOWN | BILLING_RECOVERY | ✓ |
| LEGACY | READ_ONLY | ✓ |

\*Default BILLING_RECOVERY; tier may be READ_ONLY — documented in ALPA Phase 10.

---

## Runtime contract field × source

| Field | Single owner | ALPA | ACA | APMA | CX | Schema | Consumers doc |
|-------|--------------|------|-----|------|-----|--------|---------------|
| lifecycle_state | Resolver | ✓ | D | D | D | ✓ | ✓ |
| portal_mode | Resolver | ✓ | D | ✓ | D | ✓ | ✓ |
| capabilities | Resolver | D | ✓ | D | D | ✓ | ✓ |
| plan | plan_registry | D | D | — | — | ✓ | ✓ |
| customer_experience | Resolver | D | — | D | ✓ | ✓ | ✓ |
| background_policy | Resolver | ✓ | ✓ | — | — | ✓ | ✓ |
| communication_policy | Resolver | ✓ | — | — | D | ✓ | ✓ |
| session_policy | Resolver | ✓ | — | — | — | ✓ | ✓ |
| retention_policy | Resolver | ✓ | — | — | — | ✓ | — |
| reactivation_policy | Resolver | D | — | — | D | ✓ | ✓ |
| polling_policy | Resolver | D | — | D | ✓ | ✓ | ✓ |
| navigation_policy | Resolver | D | D | ✓ | D | ✓ | ✓ |

**D = derived from upstream authority — no duplicate ownership.**

---

## Transition × event consistency

| Transition | Event(s) | Portal post | Verified |
|------------|----------|-------------|----------|
| T-001 Account creation | ACCOUNT_CREATED | PAYMENT_REQUIRED or FULL_ACCESS | ✓ |
| T-004 Trial expired | TRIAL_EXPIRED | PAYMENT_REQUIRED | ✓ |
| T-006 → Grace | GRACE_STARTED | GRACE | ✓ |
| T-007 Payment recovered | PAYMENT_RECOVERED | FULL_ACCESS | ✓ |
| T-008 Grace → Suspended | ACCOUNT_SUSPENDED | SUSPENDED | ✓ |
| T-011 Period end cancel | SUBSCRIPTION_EXPIRED | BILLING_RECOVERY | ✓ |
| T-012 Immediate cancel | SUBSCRIPTION_CANCELLED | BILLING_RECOVERY | ✓ |
| T-014 → Read-only | ACCOUNT_READ_ONLY | READ_ONLY | ✓ (future job) |
| T-020 Resubscribe | ACCOUNT_REACTIVATED, SUBSCRIPTION_STARTED | FULL_ACCESS | ✓ |

---

## Reactivation path × runtime support

| Path | Source | Dest | portal_mode | restoration_scope | Supported |
|------|--------|------|-------------|-------------------|-----------|
| R-002 | GRACE_PERIOD | ACTIVE | FULL_ACCESS | EVERYTHING | ✓ |
| R-004 | SUBSCRIPTION_EXPIRED | ACTIVE | FULL_ACCESS | EVERYTHING | ✓ |
| R-005 | CANCELLED_IMMEDIATE | ACTIVE | FULL_ACCESS | EVERYTHING | ✓ |
| R-008 | ARCHIVED | ACTIVE | FULL_ACCESS | MANUAL_REVIEW | ✓ |
| R-012 | READ_ONLY | ACTIVE | FULL_ACCESS | EVERYTHING | ✓ |

---

## Background policy consistency (post GCR-001 fix)

| State | ALPA master | Policy matrix | BG capability matrix | Runtime background_policy |
|-------|-------------|---------------|----------------------|---------------------------|
| GRACE_PERIOD | Continue | Continue | Run | CONTINUE |
| CANCELLED_IMMEDIATE | Pause | Pause | Stop | PAUSE |
| CANCELLATION_SCHEDULED | Continue until expiry | Continue | Run | CONTINUE |
| ARCHIVED | Terminate | Terminate | Terminate | TERMINATE |

---

## Authority boundary matrix

| Question | Owner | Conflicts with |
|----------|-------|----------------|
| What is customer relationship state? | ALPA → Resolver | None |
| What can customer do? | ACA → Resolver capabilities | None |
| What does customer see? | APMA + CX → Resolver | None |
| What object do subsystems read? | Runtime Contract | None |
| How are requirements computed? | Requirement Authority | Access only via CAP_* |
| How are scores computed? | Score Authority | Visibility via CAP_SCORE_* |
| How are reports formatted? | Report Presentation Authority | Generation via CAP_REPORT_* |

---

**Outcome:** `ACCOUNT_LIFECYCLE_GOVERNANCE_CONSISTENCY_MATRIX_COMPLETE`
