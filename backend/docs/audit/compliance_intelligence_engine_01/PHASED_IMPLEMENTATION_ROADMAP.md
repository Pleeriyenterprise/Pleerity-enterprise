# Phased Implementation Roadmap

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Delivery model

**Architecture first (this slice) → Foundation → Domain engines → Graph integration → Staging validation → Operational integration → AI consumer wiring (separate authorisation)**

Estimated implementation phases: **CIE-0 through CIE-6**.

**Prerequisite:** CEG Phases 1–5 Tier 1 accepted (`PHASE_5_TIER1_STAGING_ACCEPTED`).

---

## CIE-0 — Architecture ✓

**Deliverables:**

- `COMPLIANCE_INTELLIGENCE_ENGINE_ARCHITECTURE.md`
- `INTELLIGENCE_DOMAIN_MODEL.md`
- `RECOMMENDATION_MODEL.md`
- `RECOMMENDATION_LIFECYCLE.md`
- `DEPENDENCY_MODEL.md`
- `PRIORITY_MODEL.md`
- `DECISION_IMPACT_MODEL.md`
- `PORTFOLIO_INTELLIGENCE_MODEL.md`
- `REGULATORY_IMPACT_MODEL.md`
- `GRAPH_INTEGRATION_MODEL.md`
- `API_DESIGN.md`
- `RUNTIME_VALIDATION_PLAN.md`
- `PHASED_IMPLEMENTATION_ROADMAP.md` (this document)

**Exit criteria:** Architecture approved. **No code.**

---

## CIE-1 — Foundation

**Scope:**

- `services/compliance_intelligence_engine/` package skeleton
- `config.py` — `COMPLIANCE_INTELLIGENCE_ENGINE_MODE`
- `hashing.py` — `inputs_hash`, `response_hash`
- `read_adapter.py` — Graph Service client wrapper
- `orchestrator.py` — scope resolution, flag gating
- `database.py` indexes for new collections (stubs)
- Unit tests: hashing, config, access boundary (no graph storage imports)
- Feature flag default: `disabled`

**Not in CIE-1:** Recommendation logic, HTTP routes, producers.

**Exit criteria:** Package imports cleanly; access boundary tests pass; flag gating verified.

---

## CIE-2 — Recommendation + Priority engines

**Scope:**

- `recommendation/` — template registry v1, `generate_recommendations()`
- `priority/` — weights v1, `prioritise_actions()`
- Collections: `compliance_intelligence_recommendations`
- `explain_recommendation()` — static field composition
- `compare_recommendations()` — structural diff
- Unit tests: template matching, dedupe, priority ordering stability
- Integration tests with mocked Graph Service fixtures

**Flag:** `shadow` on staging.

**Exit criteria:** V1 + V2 + V7 (partial) from runtime validation plan on fixtures.

---

## CIE-3 — Impact + Dependency engines

**Scope:**

- `decision_impact/` — impact templates v1, projections collection
- `dependency/` — chain builder, `find_dependency_chain()`, blocked detection
- Wire into `generate_recommendations` pipeline
- `calculate_decision_impact()`, `calculate_portfolio_impact()`

**Exit criteria:** V3 + V4 pass on fixtures; impact disclaimers present.

---

## CIE-4 — Portfolio + Regulatory engines

**Scope:**

- `portfolio/` — snapshot, velocity, `forecast_workload()`, `calculate_readiness()`
- `regulatory_impact/` — rule change handler, blast radius report
- `calculate_portfolio_intelligence()`, `calculate_regulatory_impact()`

**Exit criteria:** V5 + V6 pass on fixtures.

---

## CIE-5 — Graph integration + Lifecycle

**Scope:**

- `graph_emit.py` — CEG producer for intelligence artefacts
- CEG constants extension (node/edge types)
- `lifecycle/` — transitions, validation matrix
- Graph Service method stubs: `explain_recommendation`, `find_open_recommendations`
- `transition_recommendation()`, `get_recommendation_lifecycle()`
- Admin HTTP routes (read-heavy first)

**Flag:** `shadow` on staging — graph emit without operational effects.

**Exit criteria:** Graph Integrity Validator extended; V8 pass; CEG producer tests pass.

---

## CIE-6 — Staging validation + operational integration

**Scope:**

- `tmp_compliance_intelligence_engine_staging_validation.py`
- Staging smoke per `RUNTIME_VALIDATION_PLAN.md`
- Operational hooks: digest, reports, maintenance `recommendation_id` linkage
- Reminder eligibility feed (read-only)
- Work order linkage on lifecycle `scheduled` (enabled sub-flag)

**Flag progression:** `shadow` acceptance → explicit approval → `enabled` for controlled WO slice.

**Exit criteria:** `CIE_STAGING_VALIDATION_ACCEPTED` artefact committed.

---

## Post-CIE-6 (separate authorisations)

| Slice | Programme | Dependency |
|-------|-----------|------------|
| AI narration of CIE outputs | Phase 5 Tier 2 staging | CIE-6 accepted |
| Customer-facing intelligence UI | Phase 7 | CIE + AI |
| Predictive intelligence (ML) | New programme | Not CIE |
| Scenario intelligence (deterministic) | CIE extension | CIE-3 |
| Production promotion | Ops gate | Staging accepted + prod authorisation |

---

## Feature flag matrix

| Flag | CIE-1 | CIE-2 | CIE-5 | CIE-6 |
|------|-------|-------|-------|-------|
| `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` | disabled | shadow | shadow | shadow → enabled |
| `COMPLIANCE_EVIDENCE_GRAPH_MODE` | enabled (staging) | enabled | enabled | enabled |
| `AI_ENABLED` | false | false | false | false |

Production: all CIE flags `disabled` until promotion authorisation.

---

## Risk register

| Risk | Mitigation |
|------|------------|
| CIE confused with AI `compliance_intelligence` | Separate package name; docs; access boundaries |
| Recommendations perceived as compliance authority | Disclaimers; never write score_ledger; UI labelling |
| Duplicate recommendation sources (digest, reports) | Migration plan in `GRAPH_INTEGRATION_MODEL.md` |
| Non-determinism from datetime | Explicit `as_of`; versioned weights |
| Graph producer volume | Dedupe keys; batch prioritisation snapshots |

---

## Programme acceptance (architecture gate)

Architecture slice complete when:

- [x] All 13 deliverable documents produced
- [x] Determinism contract defined
- [x] Non-authority contract explicit
- [x] AI consumption path defined without redesign
- [x] CEG integration model extends existing graph
- [x] Runtime validation plan defined
- [x] Phased roadmap with explicit stop before production

**Implementation authorisation:** Await explicit `CIE-1` authorisation per slice.
