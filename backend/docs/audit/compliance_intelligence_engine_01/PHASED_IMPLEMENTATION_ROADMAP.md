# Phased Implementation Roadmap

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Delivery model

**Architecture first (this slice) → Foundation → Domain engines → Graph integration → Staging validation → Operational integration → AI consumer wiring (separate authorisation)**

Estimated implementation phases: **CIE-0 through CIE-6**.

**Prerequisite:** CEG Phases 1–5 Tier 1 accepted (`PHASE_5_TIER1_STAGING_ACCEPTED`).

---

## CIE-0 — Architecture ✓

**Deliverables:** CIE-0 docs (committed `f8da4fe5`)

**Exit criteria:** Architecture approved. **No code.**

---

## CIE-0-R1 — Architecture refinement ✓

**Deliverables:**

- `ARCHITECTURE_REFINEMENT_01.md`
- `INTELLIGENCE_ARTEFACT_MODEL.md`
- `INTELLIGENCE_SERVICE_LAYER.md`
- `INTELLIGENCE_LIFECYCLE_MODEL.md`
- `INTELLIGENCE_CONSUMERS.md`
- `COMMERCIAL_INTELLIGENCE_MODEL.md`
- Updates to CIE-0 documents

**Exit criteria:** Refinement-01 approved. **No code.**

---

## CIE-0-R1 — Architecture refinement ✓

**Deliverables:**

- `ARCHITECTURE_REFINEMENT_01.md`
- `INTELLIGENCE_ARTEFACT_MODEL.md`
- … (Refinement-01 docs)

**Exit criteria:** Refinement-01 approved. **No code.**

---

## CIE-0-R2 — Provenance refinement ✓

**Deliverables:**

- `ARCHITECTURE_REFINEMENT_02.md`
- `INTELLIGENCE_PROVENANCE_ARCHITECTURE.md`
- `PROVENANCE_DATA_MODEL.md`
- `STRATEGY_REGISTRY_ARCHITECTURE.md`
- `WEIGHT_REGISTRY_ARCHITECTURE.md`
- `CONSTRAINT_REGISTRY_ARCHITECTURE.md`
- `REPLAY_ARCHITECTURE.md`
- `COMPARISON_ARCHITECTURE.md`
- Updates to `GRAPH_INTEGRATION_MODEL.md`, `API_DESIGN.md`, `RUNTIME_VALIDATION_PLAN.md`, `INTELLIGENCE_ARTEFACT_MODEL.md`, `COMPLIANCE_INTELLIGENCE_ENGINE_ARCHITECTURE.md`

**Exit criteria:** Refinement-02 approved. **No code.**

---

## CIE-1 — Foundation ✓

**Scope (refined):**

- `services/compliance_intelligence_engine/` — config, hashing, orchestrator stub, artefact schema
- `services/compliance_intelligence_service/` — ISL skeleton, access boundary, envelope types
- `artefact_type` registry (constants)
- `compliance_intelligence_artefacts` + `compliance_intelligence_transitions` index stubs in `database.py`
- Unit tests: hashing, config, dual access boundary (ISL + CIE vs graph storage)
- Feature flag: `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=disabled`

**Not in CIE-1:** Domain engines, graph producers, HTTP routes, provenance (deferred to CIE-1.5 per Refinement-02).

**Exit criteria:** `CIE_1_FOUNDATION_VALIDATED` — see `CIE_1_IMPLEMENTATION.md`.

---

## CIE-1.5 — Provenance foundation (Refinement-02 implementation gate)

**Scope (required before first real artefact emission in CIE-2):**

- `compliance_intelligence_provenance` collection + index stubs
- Registry collection stubs: strategy, weight, constraint (v1 seed documents)
- Provenance Pydantic schema + validation helpers
- `provenance_id` on `IntelligenceArtefactBase`
- CIE storage stub: `insert_provenance` (raises until CIE-2 write path)
- ISL: `get_intelligence_provenance`, `replay_intelligence` stubs
- Orchestrator: provenance trace builder skeleton (empty stages OK for stubs)
- Unit tests: provenance schema, 1:1 artefact linkage, registry immutability contract
- Access boundary: provenance storage same rules as artefact storage

**Not in CIE-1.5:** Domain calculation, replay execution, comparison diff engine.

**Exit criteria:** Provenance schema validates; registries publish v1 seeds; access boundary tests pass.

**Flag:** `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=disabled`

---

## CIE-2 — Recommendation + Priority engines

**Scope:**

- `recommendation/` — template registry v1, `generate_recommendations()`
- `priority/` — weights v1 from **Weight Registry**, `prioritise_actions()`
- **Provenance write on every artefact** — full calculation trace
- **Strategy Registry** pins for recommendation + priority
- Collections: `compliance_intelligence_artefacts` + `compliance_intelligence_provenance`
- ISL: `generate_recommendations()`, `explain_intelligence()`, `get_intelligence_provenance()`
- Unit tests: template matching, dedupe, priority ordering stability, provenance 1:1 linkage
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

- `graph_emit.py` — CEG producer for intelligence artefacts **and provenance nodes**
- CEG constants extension (node/edge types)
- `lifecycle/` — transitions, validation matrix
- Graph Service + ISL method stubs: `explain_intelligence`, `list_intelligence`
- `transition_intelligence()` for recommendations
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

| Flag | CIE-1 | CIE-1.5 | CIE-2 | CIE-5 | CIE-6 |
|------|-------|---------|-------|-------|-------|
| `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` | disabled | disabled | shadow | shadow | shadow → enabled |
| `COMPLIANCE_EVIDENCE_GRAPH_MODE` | enabled (staging) | enabled | enabled | enabled |
| `AI_ENABLED` | false | false | false | false |

Production: all CIE flags `disabled` until promotion authorisation.

---

## Risk register

| Risk | Mitigation |
|------|------------|
| CIE confused with AI `compliance_intelligence` | Separate packages: `compliance_intelligence_engine` + `compliance_intelligence_service` vs `compliance_intelligence` |
| Recommendations perceived as compliance authority | Disclaimers; never write score_ledger; UI labelling |
| Recommendation-centric storage refactor later | Refinement-01 unified CIA — CIE-1 implements base first |
| Non-determinism from datetime | Explicit `as_of`; versioned weights in Weight Registry |
| Provenance absent on first artefact | CIE-1.5 gate before CIE-2 domain engines |
| Weight changes without audit trail | Weight Registry + provenance pin |
| Graph producer volume | Dedupe keys; batch prioritisation snapshots |

---

## Programme acceptance (architecture gate)

Architecture slice complete when:

- [x] CIE-0 deliverables committed
- [x] Refinement-01 artefact generalisation documented
- [x] Intelligence Service Layer boundary defined
- [x] Determinism + non-authority contracts explicit
- [x] AI consumption path via ISL
- [x] CEG integration artefact-centric
- [x] Runtime validation plan defined
- [x] Refinement-02 provenance + registries documented
- [x] CIE-1 foundation implemented and validated
- [x] Runtime validation plan includes provenance (V10–V12)
- [x] CIE-1.5 / CIE-2 readiness recommendation documented (Refinement-02)

**Implementation authorisation:** CIE-1.5 provenance foundation required before CIE-2 domain engines.
