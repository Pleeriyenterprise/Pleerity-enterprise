# S3 readiness assessment

**Programme:** S2-PROJECTION-SOURCE-DISPOSITION-AUDIT-01  
**Date:** 2026-06-02

---

## Purpose

Assess whether S3 frontend migration can proceed after S2 completes, based on disposition of PS-16–20 and related override paths.

---

## S3 scope (from disposition audit)

| PS-ID | Module | Classification | S3 action |
|-------|--------|----------------|-----------|
| PS-16 | resolvedRequirementViewModel.js | D | Remove badge fallbacks; consume customer_status_* |
| PS-17 | requirementSubmissionModalContext.js | D | Hero from customer_status_label |
| PS-18 | requirementLifecyclePresentation.js | D | CTA from take_action + customer_status_class |
| PS-19 | evidenceStatus.js | D | Chips from customer_status_label |
| PS-20 | presentationLanguage.js | D | Filters keyed on customer_status_key |
| PS-02 FE | cerGovernancePresentation.js | D (mirror) | Stop client-side label fallback |
| PS-02 FE | clientPersistedSubmissionPresentation.js | D | Remove verification pending default |
| PS-12 FE | assurancePresentation.js | D | Assurance from customer_status_class |
| — | PropertyDetailPage.js | Consumer | truthLabel → customer_status_label |
| — | RequirementModalAssuranceSection.jsx | Consumer | Display customer_status_label |

---

## S3 dependencies on S2

| S2 deliverable | S3 dependency | Required |
|----------------|---------------|----------|
| customer_status_label on all enrich endpoints | FE badge display | **Mandatory** |
| customer_status_subline | Modal sublines | **Mandatory** |
| customer_status_key | Filter mapping | **Mandatory** |
| customer_status_class | CTA policy + assurance | **Mandatory** |
| customer_status_reason | Debug/tooltip (optional) | Nice-to-have |
| vocabulary_version | FE parity check | Recommended |
| take_action aligned to projector | Modal CTA | **Mandatory** |
| operational_cognition from projector | Today/CC UI | **Mandatory** |

---

## S3 readiness preconditions

| # | Precondition | Status today |
|---|--------------|--------------|
| 1 | S2 flag=active on staging | Not started |
| 2 | API fields populated for 12 governance families | Not started |
| 3 | 0 class_a_review_leaks in projector | Not started |
| 4 | Shadow divergence < 2% (G3) | Not started |
| 5 | customerStatusVocabulary.js parity tests green | **DONE** (PR-1A) |
| 6 | FE override inventory complete | **DONE** (this audit) |
| 7 | CONSISTENCY_AUDIT D1–D12 = 0 on staging | Not started |

---

## S3 consumer matrix alignment

| Consumer ID | Surface | S3 ready when |
|-------------|---------|---------------|
| C-01 | Requirements page | S2 active + API fields stable |
| C-02 | Property matrix | Same |
| C-03 | Requirement modal | Same + take_action alignment |
| C-06 | Documents page | Same (requirement cross-links only) |
| C-07 | Dashboard | Low risk — KPI unchanged |
| C-13 | Property operating hub | Same |

---

## S3 risks if started early

| Risk | Impact |
|------|--------|
| S3 before S2 active | FE would consume empty/missing customer_status_* → worse drift |
| Partial S3 (some pages only) | Cross-surface inconsistency (D2/D3/D5/D6) |
| Retiring presentationLanguage before filters migrated | Broken filter labels |

---

## S3 migration order (recommended)

1. **Enrich consumers first:** RequirementsPage, PropertyDetailPage (C-01, C-02)
2. **Modal stack:** requirementSubmissionModalContext → lifecyclePresentation → assurancePresentation (C-03)
3. **Operating hub:** PropertyOperatingHub.jsx (C-13)
4. **Filters:** presentationLanguage.js token retirement (C-07 misc)
5. **Cleanup:** cerGovernancePresentation.js, clientPersistedSubmissionPresentation.js fallbacks
6. **Remove** truth_presentation_label reads from client FE

---

## S3 readiness verdict

| Dimension | Assessment |
|-----------|------------|
| **Planning readiness** | **READY** — override inventory and consumer matrix complete |
| **API readiness** | **NOT READY** — S2 not implemented |
| **Vocabulary readiness** | **READY** — PR-1A FE module exists |
| **Execution readiness** | **BLOCKED ON S2** |

**S3 readiness: NOT READY FOR EXECUTION** — correctly sequenced after S2 active.  
**S3 planning readiness: GO** — sufficient disposition detail to scope S3 PRs once S2 shadow completes.
