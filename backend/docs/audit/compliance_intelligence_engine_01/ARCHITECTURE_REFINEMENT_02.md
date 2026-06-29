# Architecture Refinement 02 — Intelligence Provenance

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02  
**Status:** Approved for planning — **no implementation**  
**Date:** 2026-06-02  
**Prerequisite:** CIE-1 foundation validated (`CIE_1_FOUNDATION_VALIDATED`); Refinement-01 committed

---

## Executive summary

Refinement-01 established **Compliance Intelligence Artefacts (CIA)** as the immutable parent entity for all deterministic CIE outputs. Refinement-02 introduces **Intelligence Provenance** — the immutable calculation lineage that permanently preserves *how* each artefact was generated.

Every CIA references exactly one provenance record (`cip_*`). Provenance is append-only and never modified. Recalculation with different inputs, weights, legislation, rules, or engine versions creates new provenance and a new artefact.

Three **versioned registries** externalise calculation configuration:

- **Strategy Registry** — algorithm versions
- **Weight Registry** — numeric weight sets (never embedded in code)
- **Constraint Registry** — deterministic constraint catalogues

**Replay** and **comparison** operate on provenance without AI — supporting audit, migration, and supersession analysis.

---

## What changed (Refinement-01 → Refinement-02)

| # | Requirement | Architectural response |
|---|-------------|------------------------|
| 1 | Immutable Intelligence Provenance entity | `INTELLIGENCE_PROVENANCE_ARCHITECTURE.md`, `PROVENANCE_DATA_MODEL.md` |
| 2 | Full provenance schema with version pins | `PROVENANCE_DATA_MODEL.md` — 30+ authoritative fields |
| 3 | Deterministic calculation trace | Ordered pipeline stages in `calculation_trace[]` |
| 4 | Strategy Registry | `STRATEGY_REGISTRY_ARCHITECTURE.md` |
| 5 | Weight Registry | `WEIGHT_REGISTRY_ARCHITECTURE.md` |
| 6 | Constraint Registry | `CONSTRAINT_REGISTRY_ARCHITECTURE.md` |
| 7 | Intelligence Replay | `REPLAY_ARCHITECTURE.md` |
| 8 | Intelligence Comparison | `COMPARISON_ARCHITECTURE.md` |
| 9 | CEG provenance integration | `GRAPH_INTEGRATION_MODEL.md` (updated) |
| 10 | ISL provenance APIs | `API_DESIGN.md` (updated) |
| 11 | Runtime validation | `RUNTIME_VALIDATION_PLAN.md` — V10–V12 |
| 12 | Phased roadmap | `PHASED_IMPLEMENTATION_ROADMAP.md` — CIE-1.5 gate |

---

## Authority stack (refined)

```
Authoritative Engines
        ↓
CEG / Graph Service (read-only)
        ↓
Strategy · Weight · Constraint Registries (immutable versions)
        ↓
CIE Domain Engines (calculation)
        ↓
Intelligence Provenance (cip_*) — how
        ↓
Compliance Intelligence Artefact (cia_*) — what
        ↓
Intelligence Service Layer
        ↓
Consumers · AI narration (explain only)
```

**Key invariant:** Provenance explains calculation; it does not determine compliance. AI narrates envelopes — it never creates provenance.

---

## Refinement acceptance criteria

| Criterion | Status |
|-----------|--------|
| Every intelligence artefact references immutable provenance | ✓ 1:1 `provenance_id` on CIA |
| Provenance completely explains deterministic calculation lineage | ✓ Schema + `calculation_trace` |
| Strategies are independently versioned | ✓ Strategy Registry |
| Weights are independently versioned | ✓ Weight Registry |
| Constraints are independently versioned | ✓ Constraint Registry |
| Historical replay is architecturally supported | ✓ Replay Architecture |
| Historical comparison is architecturally supported | ✓ Comparison Architecture |
| Provenance integrates cleanly with CEG | ✓ Graph nodes/edges updated |
| AI is never required to explain deterministic calculations | ✓ ISL `explain` / `compare` / `replay` |
| Future optimisation engines addable without redesign | ✓ Registry + trace extension protocol |

---

## Document index (post-refinement-02)

| Document | Role |
|----------|------|
| `ARCHITECTURE_REFINEMENT_02.md` | This summary |
| `INTELLIGENCE_PROVENANCE_ARCHITECTURE.md` | **New** — provenance master architecture |
| `PROVENANCE_DATA_MODEL.md` | **New** — field-level schema |
| `STRATEGY_REGISTRY_ARCHITECTURE.md` | **New** — algorithm versioning |
| `WEIGHT_REGISTRY_ARCHITECTURE.md` | **New** — weight versioning |
| `CONSTRAINT_REGISTRY_ARCHITECTURE.md` | **New** — constraint versioning |
| `REPLAY_ARCHITECTURE.md` | **New** — historical reconstruction |
| `COMPARISON_ARCHITECTURE.md` | **New** — deterministic diff |
| `COMPLIANCE_INTELLIGENCE_ENGINE_ARCHITECTURE.md` | Updated — provenance in stack |
| `INTELLIGENCE_ARTEFACT_MODEL.md` | Updated — `provenance_id` required |
| `GRAPH_INTEGRATION_MODEL.md` | Updated — provenance graph chain |
| `API_DESIGN.md` | Updated — provenance/replay/compare methods |
| `RUNTIME_VALIDATION_PLAN.md` | Updated — V10–V12 |
| `PHASED_IMPLEMENTATION_ROADMAP.md` | Updated — CIE-1.5 gate |
| `ARCHITECTURE_REFINEMENT_01.md` | Prior refinement (artefact generalisation) |
| `CIE_1_IMPLEMENTATION.md` | CIE-1 implementation evidence |

---

## CIE-2 readiness recommendation

### Should provenance become part of CIE core before CIE-2?

**Recommendation: YES — mandatory via CIE-1.5 provenance foundation slice before any CIE-2 domain engine emits real artefacts.**

### Rationale

1. **Irreversible audit gap** — If CIE-2 emits recommendations without provenance, the first production artefacts lack calculation lineage. Retrofitting provenance onto artefacts generated without trace data is architecturally lossy and compliance-risky.

2. **Weight Registry dependency** — CIE-2 includes the Priority Engine. Refinement-02 forbids embedded weights. Priority ordering without `weight_set_version` pins cannot satisfy reproducibility or comparison requirements.

3. **Comparison on supersession** — Recommendation regeneration is a core CIE-2 behaviour. Without provenance, `compare_intelligence` cannot answer "which weight/rule/evidence changed?" deterministically.

4. **CIE-1 is compatible** — CIE-1 implemented artefact schema without `provenance_id`. CIE-1.5 adds provenance schema, registry stubs, and `provenance_id` on the artefact model — a small, reviewable extension. No domain logic required.

5. **Deferral cost** — Adding provenance at CIE-5 (graph integration) is too late: artefacts would exist for multiple phases without lineage. Graph emit should index provenance nodes that already exist — not introduce provenance retroactively.

### Recommended sequencing

| Phase | Scope | Blocker for next |
|-------|-------|------------------|
| **CIE-1** ✓ | Artefact schema, ISL stub, hashing | — |
| **CIE-1.5** | Provenance schema, registry v1 seeds, storage stubs, `provenance_id` on CIA | **Blocks CIE-2** |
| **CIE-2** | Recommendation + Priority engines with full provenance write | CIE-3 |
| **CIE-5** | Graph emit for provenance nodes (index existing records) | — |
| **CIE-6** | Replay + comparison engines fully validated (V11–V12) | Staging acceptance |

### CIE-1.5 minimum viable scope

- `compliance_intelligence_provenance` collection + indexes
- Registry collections with v1 seed documents (strategy, weight, constraint)
- Pydantic provenance schema + validation
- `provenance_id` added to `IntelligenceArtefactBase`
- Orchestrator provenance trace builder (skeleton)
- ISL stubs: `get_intelligence_provenance`, `replay_intelligence`
- Tests: schema, 1:1 linkage, storage access boundary

### What CIE-2 must not do without CIE-1.5

- Emit artefacts with real payloads that lack `provenance_id`
- Hard-code priority weights in engine code
- Ship recommendation generation without `calculation_trace`

### Gate before CIE-2 authorisation

- [ ] CIE-1.5 provenance foundation implemented and validated
- [ ] Weight Registry v1 published (`weights_v1.0.0` minimum)
- [ ] Constraint Registry v1 published (`constraints_v1.0.0`)
- [ ] Strategy Registry v1 seeds for recommendation + priority
- [ ] `provenance_id` on artefact schema with validation tests
- [ ] Access boundary: provenance storage same rules as artefact storage

---

## Explicit non-goals (unchanged)

- No code in this refinement slice
- No production flags
- No replay/comparison engine implementation (deferred to CIE-2+ / CIE-6)
- No AI, frontend, or customer portal
- ML predictive planning remains a separate programme

---

## Summary verdict

Refinement-02 is **complete as architecture documentation**. Intelligence Provenance is a **core CIE capability** — not an optional audit add-on. It should be implemented as **CIE-1.5** immediately after CIE-1 and **before** CIE-2 domain engines begin.

**Do not authorise CIE-2 implementation until CIE-1.5 provenance foundation is explicitly approved and completed.**
