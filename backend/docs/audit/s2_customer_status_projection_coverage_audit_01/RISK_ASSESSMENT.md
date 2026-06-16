# Risk assessment — projection coverage

**Programme:** S2-CUSTOMER-STATUS-PROJECTION-COVERAGE-AUDIT-01  
**Date:** 2026-06-02

---

## Coverage risks

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R-COV-01 | supporting_upload_only projected incorrectly as recorded | Medium | High | UNS-RES-01 explicit rule; fixture in family matrices |
| R-COV-02 | Class A PENDING_REVIEW leaks under_review | Medium | Critical | AMB-06 gate; G2 metric; legionella/landlord fixtures |
| R-COV-03 | Class B pending admin without queue shows under_review | Medium | High | AMB-07 gate; gas phantom fixture |
| R-COV-04 | followup + satisfied both displayed | Low | High | Overlay precedence AMB-05; legionella fixture |
| R-COV-05 | HMO fire followup vs additional_action tie | Low | Medium | Precedence order 5 before 6; explicit test |
| R-COV-06 | Modal headline treated as badge | Low | Medium | I7 tests; separate headline table S3 |
| R-COV-07 | Legacy label used when active flag on | Medium | Critical | REM-02; shadow comparator |
| R-COV-08 | Subline table incomplete in vocabulary mirror | Low | Medium | Add sublines to vocabulary module in S2 |

---

## Vocabulary adequacy

| Question | Assessment |
|----------|------------|
| Can all 12 families be represented? | **Yes** |
| Are forbidden states enforceable? | **Yes** via I2 + gates |
| Is overlay set sufficient? | **Yes** |
| Need new primary status? | **No** |
| Need new overlay? | **No** |

---

## Implementation risks (projection logic)

| Area | Risk | Severity |
|------|------|----------|
| Gate implementation errors | Wrong label for edge states | High |
| Precedence bugs | Wrong overlay wins | Medium |
| Subline generation | Retired phrase leak in subline | High |
| Class resolution | Wrong path A vs B | Critical |

---

## Residual gaps (not blocking S2)

| Gap | Phase | Risk |
|-----|-------|------|
| D8 export buckets | S4 | Low until reports migrate |
| D11 FE dual map | S3 | Medium — backend emits key |
| D7 doc row copy | S3 | Low — scoped constraint documented |
| reviewer_feedback subline | S2 | Low — maps to under_review |

---

## Overall posture

| Dimension | Assessment |
|-----------|------------|
| Vocabulary completeness | **Adequate** |
| Determinism | **Adequate with gate discipline** |
| S2 implementation risk | **Medium** — logic complexity, not vocabulary gap |

---

## Conditions

1. Implement all gate rules from CUSTOMER_STATUS_VOCABULARY.json `gates` section verbatim.
2. Implement overlay_precedence order exactly.
3. Include 71 family-state rows as fixture/assertion coverage over time (12-family minimum for G1).
4. Do not introduce fallback labels outside vocabulary — use `action_required` fail-closed on projector error.
