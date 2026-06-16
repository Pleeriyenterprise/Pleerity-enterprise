# Projection source disposition matrix

**Programme:** S2-PROJECTION-SOURCE-DISPOSITION-AUDIT-01  
**Date:** 2026-06-02  
**Machine-readable:** `PROJECTION_SOURCE_DISPOSITION_MATRIX.json`

---

## Classification legend

| Code | Name | Rule |
|------|------|------|
| **A** | Projector Input | Survives; feeds gates; must not emit customer status post-active |
| **B** | Projector Consumer | Survives; reads `customer_status_*`; stops independent derivation |
| **C** | Shadow-only | Comparison/divergence during rollout; disabled after cutover |
| **D** | Retirement Candidate | Removed once projector authoritative |

---

## Full matrix (21 sources)

| ID | Source | Class | Conflict | S2 | S3 | S4 | S5 | Retire |
|----|--------|-------|----------|----|----|----|----|--------|
| PS-01 | client_requirement_lifecycle.py | **A** | — | ✓ | ✓ | ✓ | ✓ | — |
| PS-02 | cer_governance_presentation.py | **C** + A meta | PC-01 | partial | partial | ✗ | ✗ | S3/S4 labels |
| PS-03 | requirement_truth.py | **B** | PC-02 | ✓ | ✓ | ✓ | ✓ | — |
| PS-04 | requirement_satisfaction_service.py | **A** | PC-03 | ✓ | ✓ | ✓ | ✓ | — |
| PS-05 | cer_actionability_presentation.py | **B** | PC-04 | ✓ | ✓ | ✓ | ✓ | — |
| PS-06 | operational_cognition_service.py | **B** | PC-05 | ✓ | ✓ | ✓ | ✓ | — |
| PS-07 | requirement_attention_eligibility_service.py | **A** | PC-06 | ✓ | ✓ | ✓ | ✓ | — |
| PS-08 | audience_governance_v1.py | **B** | PC-07 | partial | ✓ | partial | ✓ | S4 buckets |
| PS-09 | review_assurance_legacy_convergence.py | **A** | — | ✓ | ✓ | ✓ | ✓ | S5? |
| PS-10 | review_queue_service.py | **A** | — | ✓ | ✓ | ✓ | ✓ | — |
| PS-11 | requirement_evidence_authority.py | **A** | — | ✓ | ✓ | ✓ | ✓ | — |
| PS-12 | assurance_actionability_service.py | **B** | PC-08 | ✓ | ✓ | ✓ | ✓ | — |
| PS-13 | report_human_language_v1.py | **D** | PC-09 | ✗ | ✗ | replace | ✗ | **S4** |
| PS-14 | report_layout_governance.py | **D** | PC-10 | ✗ | ✗ | replace | ✗ | **S4** |
| PS-15 | monthly_digest_operational_intelligence.py | **D** | PC-11 | ✗ | ✗ | replace | ✗ | **S4** |
| PS-16 | resolvedRequirementViewModel.js | **D** | PC-12 | unchanged | ✗ | ✗ | ✗ | **S3** |
| PS-17 | requirementSubmissionModalContext.js | **D** | PC-13 | unchanged | ✗ | ✗ | ✗ | **S3** |
| PS-18 | requirementLifecyclePresentation.js | **D** | PC-14 | unchanged | ✗ | ✗ | ✗ | **S3** |
| PS-19 | evidenceStatus.js | **D** | PC-15 | unchanged | ✗ | ✗ | ✗ | **S3** |
| PS-20 | presentationLanguage.js | **D** | PC-16 | unchanged | ✗ | ✗ | ✗ | **S3** |
| PS-21 | requirement_action_resolver.py | **A** | PC-17 | ✓ | ✓ | ✓ | ✓ | — |

✓ = survives in role | ✗ = retired/replaced | partial = split responsibilities

---

## PS-02 split detail

| Function | Class | Survives |
|----------|-------|----------|
| derive_truth_presentation (labels) | **C → D** | Shadow S2; retire S3/S4 |
| derive_assurance_tier | **A** | Long-term |
| governance_family, review_owner | **A** | Long-term |
| cognition_next_step_for_requirement | **B** | Consumes projector in S2 |

---

## Summary counts

| Category | Sources |
|----------|---------|
| Long-term backend (A+B) | PS-01,03,04,05,06,07,08,09,10,11,12,21 + PS-02 meta |
| Shadow-only path | PS-02 labels |
| S3 retirement | PS-16,17,18,19,20 |
| S4 retirement | PS-13,14,15 |
| Projection conflicts | 17 (PC-01 through PC-17) |
