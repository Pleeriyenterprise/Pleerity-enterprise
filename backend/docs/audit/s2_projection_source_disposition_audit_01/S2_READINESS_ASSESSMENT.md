# S2 readiness assessment

**Programme:** S2-PROJECTION-SOURCE-DISPOSITION-AUDIT-01  
**Date:** 2026-06-02

---

## Purpose

Assess whether disposition audit findings support beginning S2 **implementation** (not production active).

---

## Prerequisites

| Prerequisite | Status | Evidence |
|--------------|--------|----------|
| PR-1A vocabulary SoT | **DONE** | CUSTOMER_STATUS_VOCABULARY.json + mirror modules |
| PR-1B vocabulary CI gate | **DONE** | vocabulary_governance_ci_gate.py passing |
| S2 planning package | **DONE** | s2_customer_status_projector_planning_01/ |
| 21-source inventory | **DONE** | CUSTOMER_STATUS_PROJECTION_INVENTORY.json |
| Disposition classification | **DONE** | This audit package |
| Projector module | **NOT STARTED** | customer_status_projector_v2.py does not exist (expected) |

---

## Disposition audit findings relevant to S2

### Backend scope clarity

| Metric | Count |
|--------|-------|
| A — Projector inputs (survive S2) | 7 |
| B — Projector consumers (S2 migrate) | 5 |
| C — Shadow-only (PS-02 label path) | 1 |
| D — Deferred S3/S4 | 8 |
| PROJECTION_CONFLICT (backend S2 scope) | 7 of 17 total |

S2 implementation touch set confirmed: **~8–10 modules** (PS-02, PS-03, PS-05, PS-06, PS-08 partial, PS-12 partial, PS-21, new projector).

### Critical path understood

```
derive_client_lifecycle_fields (PS-01)
  → attach_cer_governance_presentation (PS-02) [shadow comparator]
  → satisfaction (PS-04)
  → [NEW] customer_status_projector_v2
  → audience (PS-08 partial)
  → actionability (PS-05)
  → cognition (PS-06)
```

Overwrite at `requirement_truth.py:804–806` identified as **CRITICAL** blocker for flag=active.

### Shadow strategy alignment

All 21 sources assessed for shadow utility. PS-02 is primary comparator; PS-16–20 enable staging FE divergence detection without blocking S2 backend work.

---

## S2 readiness checklist

| # | Criterion | Ready |
|---|-----------|-------|
| 1 | Every projection source classified A/B/C/D | Yes |
| 2 | Conflict inventory complete | Yes |
| 3 | Legacy override paths inventoried | Yes |
| 4 | Shadow comparators identified | Yes |
| 5 | Consumer migration sequence validated | Yes |
| 6 | Retirement phases assigned | Yes |
| 7 | No undisclosed second-generation authority | Yes — PS-02 is known legacy authority |
| 8 | S2/S3 boundary explicit for FE drift | Yes |
| 9 | Architecture doc exists | Yes |
| 10 | Mapping matrix exists | Yes — PROJECTOR_STATUS_MAPPING_MATRIX.json |

---

## Gaps before S2 code (from planning + this audit)

| Gap | Owner | Blocks start? |
|-----|-------|---------------|
| Architecture + mapping matrix sign-off | Product + Platform Architecture | **Yes** |
| 12-family shadow fixture pack | Engineering | **Yes** (same or prior PR) |
| Feature flag host confirmation | Ops | **Yes** |
| CTA_POLICY_MATRIX.json alignment with customer_status_key | Engineering | No — can be S2 PR task |
| Staging tenant for shadow | QA/Ops | No for code start; yes for shadow promotion |

---

## Risk summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| PS-02 continues as authority if active flag flipped early | CRITICAL | Shadow-first; G1–G6 gates |
| FE fallbacks mask API changes | HIGH | Accepted until S3; shadow populates API fields |
| Cognition not migrated before active | HIGH | PC-05 in S2 must-fix list |
| Report drift continues | MEDIUM | Deferred S4 — documented |

---

## S2 readiness verdict

| Dimension | Assessment |
|-----------|------------|
| **Audit completeness** | **READY** |
| **Disposition clarity** | **READY** |
| **Implementation start (code)** | **READY WITH CONDITIONS** — same conditions as planning GO/NO-GO |
| **Production active** | **NOT READY** — requires shadow acceptance G1–G6 |

**S2 readiness: GO WITH CONDITIONS** for implementation start.
