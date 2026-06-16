# S2 — Customer status projector implementation plan

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01  
**Status:** PLANNING COMPLETE — no implementation  
**Date:** 2026-06-02

---

## Executive summary

S2 introduces **`customer_status_projector_v2`** — the first runtime phase that projects approved obligation status vocabulary at the enrich boundary. Shadow mode ensures zero customer impact until explicit flag activation. Frontend, reports, and emails remain **out of scope** (S3/S4).

---

## Exact S2 implementation scope

### Create

| Item | Description |
|------|-------------|
| `services/customer_status_projector_v2.py` | Pure projector + gate engine |
| `tests/test_customer_status_projector_v2.py` | Unit + shadow tests |
| `tests/fixtures/customer_status_projector/` | 12-family fixtures |
| Flag wiring | `customer_status_projector_v2` disabled/shadow/active (design: FEATURE_FLAG_STRATEGY.md) |
| Divergence logger | Structured `customer_status_projector_divergence` events |

### Modify (backend only)

| Module | Change |
|--------|--------|
| `requirement_truth.py` | Call projector; emit `customer_status_*`; shadow compare |
| `operational_cognition_service.py` | Consume `customer_status_*` not re-derive |
| `cer_actionability_presentation.py` | Banner/CTA copy from canonical pair |
| `requirement_attention_eligibility_service.py` | Suppress Class A customer review_pending |
| `requirement_satisfaction_service.py` | Decouple satisfied+review presentation |
| `client_requirement_lifecycle.py` | Input-only; no customer review labels |
| `cer_governance_presentation.py` | Legacy path for shadow/disabled; optional slimming |
| `audience_governance_v1.py` | Read `customer_status_*` for landlord interpretation |
| Admin explain route | Projector debug fields |

### Do not modify (S2)

- Frontend (`frontend/src/**`)
- Reports (`report_human_language_v1.py`, etc.)
- Emails
- Mongo schemas / queues
- Production or staging data

---

## Blast radius

| Dimension | Estimate |
|-----------|----------|
| Backend services touched | **8–10** (critical path 7) |
| API endpoints affected | All client enrich paths (`/api/client/requirements`, portfolio compliance, command-center enrich) |
| Frontend surfaces changed | **0** in S2 |
| Report/email surfaces | **0** in S2 |
| Data migration | **None** |
| Engineering effort | **5–8 days** + **2–3 days QA** (per impact audit) |

---

## Deployment sequence

```
1. Merge S2 PR to develop
2. Deploy staging → flag=shadow
3. Run shadow soak ≥5 business days; collect divergence report
4. Fix projector gaps; re-soak if needed
5. Merge to main / production deploy → flag=shadow
6. Production shadow ≥7 days; monitor metrics
7. Product sign-off on G1–G6
8. flag=active (pilot tenant optional → fleet)
9. Monitor 48h; keep rollback ready
10. Begin S3 frontend PR (separate release)
```

---

## Shadow-mode acceptance criteria

| ID | Criterion |
|----|-----------|
| G1 | CONSISTENCY_AUDIT D1–D12 = 0 on staging cohort |
| G2 | `class_a_review_leaks` = 0 for 7 days |
| G3 | Production shadow divergence_rate < 2% |
| G4 | Enrich p95 latency +≤15% |
| G5 | All S2 tests green in CI |
| G6 | Product written sign-off |

---

## Remaining blockers before S2 code

| ID | Blocker | Owner |
|----|---------|-------|
| BLK-01 | Plan approval | Product + Platform Architecture |
| BLK-02 | Shadow fixture pack | Engineering |
| BLK-03 | Flag registry sign-off | Platform Architecture |
| BLK-04 | Staging tenant for soak | Ops |

**Prerequisites satisfied:** PR-1A, PR-1B, Programme G S1 DONE.

---

## Deliverable index

| # | File |
|---|------|
| 1 | `CUSTOMER_STATUS_PROJECTION_INVENTORY.json` |
| 2 | `CUSTOMER_STATUS_PROJECTOR_ARCHITECTURE.md` |
| 3 | `PROJECTOR_STATUS_MAPPING_MATRIX.json` |
| 4 | `SHADOW_MODE_STRATEGY.md` |
| 5 | `FEATURE_FLAG_STRATEGY.md` |
| 6 | `CONSUMER_MIGRATION_MATRIX.json` |
| 7 | `S2_TEST_STRATEGY.md` |
| 8 | `ROLLBACK_STRATEGY.md` |
| 9 | `RISK_ASSESSMENT.md` |
| 10 | `DEPENDENCY_VALIDATION.json` |
| 11 | `GO_NO_GO_RECOMMENDATION.md` |

---

## Decision

**GO** for S2 implementation planning. **GO with conditions** to start S2 code after plan approval and fixture pack readiness.

**Do not implement S2 in this programme folder** — planning artefacts only.
