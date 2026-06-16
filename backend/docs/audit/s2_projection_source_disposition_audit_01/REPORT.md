# S2 projection source disposition audit — report

**Programme:** S2-PROJECTION-SOURCE-DISPOSITION-AUDIT-01  
**Date:** 2026-06-02  
**Type:** Audit only — no implementation, no production/staging changes

---

## Objective

Determine the final disposition of every projection source in `CUSTOMER_STATUS_PROJECTION_INVENTORY.json` before S2 implementation, to prevent legacy projection logic surviving alongside `customer_status_projector_v2`.

---

## Deliverables

| # | Deliverable | File |
|---|-------------|------|
| 1 | Projection source disposition matrix | `PROJECTION_SOURCE_DISPOSITION_MATRIX.json`, `.md` |
| 2 | Projection conflict inventory | `PROJECTION_CONFLICT_INVENTORY.json` |
| 3 | Legacy override inventory | `LEGACY_OVERRIDE_INVENTORY.json` |
| 4 | Shadow-mode inventory | `SHADOW_MODE_INVENTORY.json` |
| 5 | Consumer migration validation | `CONSUMER_MIGRATION_VALIDATION.md` |
| 6 | Retirement roadmap | `RETIREMENT_ROADMAP.md` |
| 7 | S2 readiness assessment | `S2_READINESS_ASSESSMENT.md` |
| 8 | S3 readiness assessment | `S3_READINESS_ASSESSMENT.md` |
| 9 | Dependency validation | `DEPENDENCY_VALIDATION.md` |
| 10 | GO / NO-GO recommendation | `GO_NO_GO_RECOMMENDATION.md` |

---

## Executive summary

### All 21 sources classified

| Classification | Count | IDs |
|----------------|-------|-----|
| **A** — Projector Input | 7 | PS-01, 04, 07, 09, 10, 11, 21 |
| **B** — Projector Consumer | 5 | PS-03, 05, 06, 08, 12 |
| **C** — Shadow-only | 1 path | PS-02 `derive_truth_presentation` customer labels |
| **D** — Retirement Candidate | 8 | PS-13–20 |

### Survivors

**Long-term:** PS-01, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 21, plus PS-02 governance metadata (`assurance_tier`, `governance_family`, `review_owner`, `queue_backed_review`).

### Shadow-only

PS-02 customer label emission path — primary divergence comparator during S2 shadow; disabled when flag=active.

### Must retire

- **S3:** PS-16–20 (frontend fallback/modal/CTA/chip/filter projection)
- **S4:** PS-13–15 (reports, PDF sections, digest buckets)
- **S3/S4:** PS-02 `derive_truth_presentation` label emission
- **S5:** Admin parallel maps (`progress_contract_service.py`)

### Would override projector

**23 paths** in legacy override inventory. **5 backend paths** must be fixed in S2 before flag=active:

1. `requirement_truth.py:804–806` — client_lifecycle_label overwrite
2. `cer_governance_presentation.py` — derive_truth_presentation labels
3. `operational_cognition_service.py` — independent review copy
4. `cer_actionability_presentation.py` — stage mutation + review banners
5. `requirement_action_resolver.py` — CTA before projector

Remaining overrides accepted until S3 (frontend) or S4 (reports/email).

### Projection conflicts

**17 conflicts** flagged (PC-01 through PC-17): 2 CRITICAL, 9 HIGH, 6 MEDIUM. Primary authority conflict is PS-02 today; PS-03 orchestration propagates it.

### Consumer migration

Sequence **S2 → S3 → S4 → S5 validated**. No source forces out-of-order migration. Partial FE drift during S2 active is documented and accepted.

### GO / NO-GO

| Decision | Verdict |
|----------|---------|
| Disposition audit | **GO** |
| S2 implementation start | **GO WITH CONDITIONS** |
| S2 production active | **NO-GO** until shadow G1–G6 |
| S3 execution | **BLOCKED** on S2 active |

---

## Critical enrich path (today)

```795:830:Pleerity-enterprise/backend/services/requirement_truth.py
        out.update(derive_client_lifecycle_fields(out, linked_primary_document=linked_primary_document))
        ...
        out.update(attach_cer_governance_presentation(out))
        truth_label = str(out.get("truth_presentation_label") or "").strip()
        if truth_label:
            out["client_lifecycle_label"] = truth_label
        ...
        out.update(reconcile_client_lifecycle_with_satisfaction(out))
        ...
        apply_actionability_cta_override(out)
```

S2 must insert projector after satisfaction, remove overwrite on active, and migrate downstream consumers to `customer_status_*`.

---

## Authority references

- `docs/governance/REVIEW_POLICY_VOCABULARY.md`
- `docs/governance/CUSTOMER_STATUS_VOCABULARY.json`
- `docs/governance/RETIRED_OBLIGATION_PHRASE_REGISTRY.json`
- `s2_customer_status_projector_planning_01/CUSTOMER_STATUS_PROJECTION_INVENTORY.json`
- `s2_customer_status_projector_planning_01/SHADOW_MODE_STRATEGY.md`

---

## Constraints honoured

- No projector implementation
- No API/frontend/report/email changes
- No feature flags created
- No production or staging modifications
- Audit documentation only
