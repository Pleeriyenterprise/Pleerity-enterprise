# Guided Flow Operational Closure — Root Cause Matrix (England AST pilot)

**Programme:** `GUIDED-FLOW-CLOSURE-01`  
**Pilot:** client `6bcc43c0-16f4-46a5-adf4-26693a0919d0` · property `3a69dcbd-74fd-4291-839b-3d52750598a1`  
**Scope:** tenancy_agreement · deposit_pi · right_to_rent · how_to_rent (consistency recheck)

## Summary

| Obligation | Prior classification | Primary failure class | Dominant layer |
|------------|---------------------|----------------------|----------------|
| tenancy_agreement | SYSTEM_OUTCOME_UNPROVEN | No CER delta + harness A-3/A-6/A-7 | Harness + submit capture |
| deposit_pi | IMPLEMENTED_NOT_VERIFIED | A-5/A-9 inspect + refresh | Harness timing + matrix copy |
| right_to_rent | ASYNC_CONVERGENCE_PARTIAL | A-5/A-9 inspect + refresh | Harness timing (trust remediated) |
| how_to_rent | VERIFIED_OPERATIONALLY | A-9 refresh only | Harness timing |

## Shared failure classes

| Class | Affected CPs | Evidence | Layer |
|-------|--------------|----------|-------|
| **S1 — Inspect panel not reached** | A-5, A-4 | deposit/RTR: `submission_inspect` false; panel requires CER fetch + optional “View submission” click | Harness limitation |
| **S2 — Refresh persistence not observed** | A-9 | All four: reload → panel/button not found within wait | Harness limitation |
| **S3 — Matrix row stale after submit** | (presentation) | deposit post row still “Evidence missing” while API has `primary_evidence_record_id` | UX timing / refetch lag |
| **S4 — Missing-evidence subline on file** | (presentation) | `workflowAwareMissingEvidenceLabel` returns “Declaration/Delivery not recorded” when submission exists but lifecycle still `ACTION_REQUIRED` | UX inconsistency |
| **S5 — Checkpoint A-3 authority read bug** | A-3 | Harness reads `authority.state` but capture nests `authority.evidence_authority.state` | Harness limitation |
| **S6 — Tenancy submit not captured** | A-2, A-3, A-7 | Browser JSON lacks real POST body; A-1 allowed `http_status: null` | Harness limitation |

## Per-obligation detail

### tenancy_agreement (`e47d1c2d-…`)

| Checkpoint | Result | Root cause | Type |
|------------|--------|------------|------|
| A-1 | Pass (weak) | Summary UI OK; POST not reliably captured; `http_status` null allowed | Harness |
| A-2/A-3/A-7 | Fail | `cer_count_delta_from_baseline: 0` (no new CER this run); A-3 false (S5); queue correlation missing | Operational unproven + harness |
| A-5/A-9 | Pass | Inspect panel found (prior CER on file) | — |

**Not trust-risk:** inspect wording references PENDING REVIEW.  
**Operational blocker:** new structured submit must produce observable CER + queue row for greenfield closure proof.

### deposit_pi (`f3b23246-…`)

| Checkpoint | Result | Root cause | Type |
|------------|--------|------------|------|
| A-1 | Pass | Real API 200; CER created | — |
| A-2/A-7 | Pass | CER delta +1; queue DONE | — |
| A-5/A-9 | Fail | Intel modal: CER list async; harness did not wait for `View submission` / panel (S1, S2) | Harness |
| Matrix | Stale | Row excerpt “Evidence missing” after submit (S3, S4) | UX inconsistency |

**Not operational contradiction:** backend authority `MISSING` + `PENDING_REVIEW` non-document is coherent pre-review.

### right_to_rent (`d72d87b0-…`)

| Checkpoint | Result | Root cause | Type |
|------------|--------|------------|------|
| A-1–A-7 | Pass | Structured submit + CER + queue (post-remediation trust) | — |
| A-5/A-9 | Fail | Same inspect/refresh harness gap as deposit (S1, S2) | Harness |
| Trust | OK | CTA “Record updated check”; no false verified CTA in browser artifact | — |

### how_to_rent (`cfb04b08-…`)

| Checkpoint | Result | Root cause | Type |
|------------|--------|------------|------|
| A-1–A-7 | Pass | Full backend closure | — |
| A-5 | Pass | Inspect panel reached | — |
| A-9 | Fail | Refresh path did not re-open inspect (S2) | Harness |

**Recheck goal:** confirm A-9 with improved harness; no regression on tenant-delivery semantics.

## Workflow-family notes

| Family | Obligations | Specific risk |
|--------|-------------|---------------|
| GUIDED_DECLARATION | tenancy, deposit, RTR | Matrix + missing-evidence copy vs `primary_evidence_record_id` |
| TENANT_DELIVERY | how_to_rent | Delivery-record copy vs pending review |
| Mixed evidence | RTR | Document on file + structured update (trust module already bounded) |

## Remediation plan (bounded)

1. **Presentation:** `workflowAwareMissingEvidenceLabel` — submission-on-file + awaiting-review copy for guided/tenant-delivery (no authority change).
2. **Harness:** Shared browser helpers — require POST 200, `expect_response` on compliance-evidence, wait for CER fetch, click View submission, wait for inspect panel, wait for compliance-detail refetch before matrix assert.
3. **Harness:** Fix A-3 to read `evidence_authority.state`.
4. **Intel modal:** `data-testid="requirement-intel-cer-ready"` when CER presence fetch completes (inspectability).
5. **Re-run:** Isolated bundles under `guided_closure_01_*`; reclassify only with full proof set.

## Out of scope

- Authority / queue / fanout redesign  
- New RCs or G1/E1/F1 widening  
- Global lifecycle semantic rewrites  
