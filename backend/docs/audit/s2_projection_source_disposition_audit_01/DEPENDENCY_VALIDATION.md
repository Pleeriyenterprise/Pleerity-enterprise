# Dependency validation

**Programme:** S2-PROJECTION-SOURCE-DISPOSITION-AUDIT-01  
**Date:** 2026-06-02  
**Extends:** `s2_customer_status_projector_planning_01/DEPENDENCY_VALIDATION.json`

---

## Upstream prerequisites

| ID | Dependency | Status | Disposition audit impact |
|----|------------|--------|--------------------------|
| DEP-01 | PR-1A vocabulary SoT | **SATISFIED** | Projector must import customer_status_vocabulary.py |
| DEP-02 | PR-1B retired phrase registry + CI | **SATISFIED** | Shadow must detect retired_phrase_in_legacy |
| DEP-03 | Programme G S1 DONE | **SATISFIED** | — |
| DEP-04 | No S2 before S1 | **SATISFIED** | — |
| DEP-05 | P1 sign-off artefacts | **SATISFIED** | CONSISTENCY_AUDIT D1–D12 drives shadow fixtures |

---

## Projection source dependency graph

```
PS-11 (evidence authority)
    └── PS-01 (lifecycle enum)
            └── PS-09 (legacy convergence)
                    └── PS-10 (queue membership)
                            └── PS-02 governance meta + legacy label [C]
                                    └── PS-04 (satisfaction)
                                            └── [PROJECTOR v2] ← vocabulary SoT
                                                    └── PS-08 (audience partial)
                                                    └── PS-05 (actionability)
                                                    └── PS-21 (take_action)
                                                    └── PS-06 (cognition)
PS-07 (attention) ── input only, parallel
PS-12 (assurance) ── consumes projector class + PS-02 assurance_tier
```

**PS-03** orchestrates entire client enrich chain — integration dependency for all backend sources.

---

## Downstream phase dependencies

| Phase | Blocked until | Disposition validation |
|-------|---------------|------------------------|
| S2 code start | BLK-01..03 (plan approval, fixtures design, flag design) | All 21 sources classified — **unblocks planning sign-off** |
| S2 shadow promotion | G1–G6 + shadow soak | PS-02 comparator + 12 families |
| S2 active | S2 shadow G1–G6 | 5 backend override remediations (see LEGACY_OVERRIDE_INVENTORY) |
| S3 | S2 active on staging | PS-16–20 retirement scope defined |
| S4 | S2 active (recommended) | PS-13–15 retirement scope defined |
| S5 | S3 complete | Admin parallel maps |

---

## Module dependency matrix (S2 implementation)

| Module | Depends on | Depended on by |
|--------|------------|----------------|
| customer_status_projector_v2 (new) | PS-01,04,09,10,11 inputs; vocabulary SoT; queue gates | PS-03,05,06,08,12,21 |
| requirement_truth.py | All enrich chain | All API routes |
| cer_governance_presentation.py | PS-01,09,10 | PS-02 shadow; PS-05,06 until migrated |
| operational_cognition_service.py | customer_status_* (post-migration) | C-04, C-05 |
| cer_actionability_presentation.py | customer_status_* | C-14 banners |
| requirement_action_resolver.py | customer_status_key/class | take_action on enrich |

---

## Blockers (unchanged from planning)

| ID | Item | Status |
|----|------|--------|
| BLK-01 | S2 implementation plan approved | PENDING |
| BLK-02 | Shadow fixture pack (12 families) | PENDING |
| BLK-03 | Feature flag registry design signed off | PENDING |
| BLK-04 | Staging tenant for shadow soak | PENDING |

**New from disposition audit (informational, not additional blockers):**

| ID | Item | Status |
|----|------|--------|
| BLK-05 | Disposition audit complete | **SATISFIED** (this package) |
| BLK-06 | PROJECTION_CONFLICT remediation in S2 PR scope | PENDING — engineering task |

---

## Circular dependency check

| Potential cycle | Result |
|-----------------|--------|
| Projector → cognition → enrich → projector | **No cycle** — cognition is downstream enrich field |
| Satisfaction reconciles after projector | **Prevented** — PS-04 must run before projector |
| CTA resolver before projector | **Prevented** — PS-21 must run after projector |

**No circular dependencies identified.**

---

## Verdict

**Dependency validation: PASS** — graph is acyclic; phase sequencing valid; prerequisites satisfied; blockers are procedural (sign-off, fixtures, ops) not architectural.
