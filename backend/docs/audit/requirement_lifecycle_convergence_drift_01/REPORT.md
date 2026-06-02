# REQUIREMENT-LIFECYCLE-CONVERGENCE-DRIFT-01

**Classification:** `VERIFIED_OPERATIONALLY`

## Root cause

Lifecycle derivation and attention eligibility treated legacy `status=OVERDUE` and system-estimated `due_date` as authoritative **before** non-document assessment-on-file truth. The Requirements portal rendered a red “days overdue” chip from raw `due_date` without checking `requirement_attention_eligible`.

Escalated HMO licensing rows are indexed on the **platform escalation queue** (`/admin/compliance-evidence/escalation-queue`), not the org compliance review queue or document pending-verification list.

## Fixes (this commit)

- `_is_expired` respects `legacy_due_date_blocks_renewal_attention` and authoritative `effective_expiry_date`
- `derive_attention_reason` prioritises escalation/verification before calendar expired
- `derive_client_lifecycle_fields` defers stale calendar OVERDUE; satisfied paths ordered before legacy `evidence_state=MISSING`
- `portal_renewal_countdown_eligible` + Requirements page gating

## Overdue governance

“17 days overdue” on estimated renewal with assessment on file = **stale lifecycle drift**, not valid legal overdue, unless `effective_expiry_date` or document-primary policy demands renewal attention.

## Queue convergence

`matches_escalation_queue` requires `queue_backed_review` + `review_owner=platform_admin_escalation`. Org queue excludes escalations by design.

## Regression

22 targeted unit tests passing locally.

## Remaining watchlist

See `watchlist.md`.
