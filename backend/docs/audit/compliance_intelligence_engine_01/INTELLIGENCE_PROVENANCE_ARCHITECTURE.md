# Intelligence Provenance Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02  
**Status:** Architecture refined — **no implementation**  
**Date:** 2026-06-02  
**Prerequisite:** CIE-1 foundation validated; Refinement-01 committed

---

## Executive summary

**Intelligence Provenance** is the immutable calculation lineage for every Compliance Intelligence Artefact (CIA). It permanently preserves *how* intelligence was generated — not only *what* was generated.

Every CIA references exactly one provenance record. Provenance records are append-only and never modified. Recalculation with different inputs, weights, legislation, rules, or engine versions creates a **new** provenance record and a **new** artefact (with supersession linkage).

This refinement makes mathematical and operational reproducibility a **first-class platform capability** — independent of AI narration, UI, or consumer presentation.

---

## Problem statement

Refinement-01 established:

- Immutable artefacts with `inputs_hash` and `response_hash`
- Version pins (`engine_version`, `template_version`, `deterministic_version`)
- Source decision and snapshot references

These fields answer **what** was produced and **which upstream objects were cited**, but they do not fully answer:

- Which algorithm stages ran, in what order, with what intermediate outputs?
- Which strategy, weight, and constraint registry versions were active?
- Which rule, jurisdiction, and legislation versions governed the calculation?
- Why did a regenerated artefact differ from its predecessor?

Without provenance, replay, comparison, and audit require reconstructing calculation context from scattered fields — fragile and non-authoritative.

---

## Design principles

| Principle | Rule |
|-----------|------|
| Immutability | Provenance records are append-only; no updates or deletes |
| One-to-one | Each CIA references exactly one `provenance_id`; each provenance references exactly one `artefact_id` |
| Authority separation | Provenance explains CIE calculation; it does not determine compliance |
| Determinism | Same frozen inputs + same registry versions + same engine versions → same trace + same hashes |
| No AI dependency | Explanation, replay, and comparison are deterministic operations on provenance |
| Registry indirection | Strategies, weights, and constraints are versioned registry objects — never embedded opaquely in algorithms |
| Historical fidelity | Replay uses historical snapshots and registry versions — no current-state substitution |
| Extensibility | New engines register strategies without redesigning provenance schema |

---

## Entity model

```
┌─────────────────────────────────────────────────────────────────────┐
│ REGISTRIES (immutable versioned documents)                            │
│ Strategy Registry · Weight Registry · Constraint Registry           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ version references
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ COMPLIANCE INTELLIGENCE PROVENANCE (cip_*)                            │
│ Append-only calculation lineage + deterministic trace               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ provenance_id (1:1)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ COMPLIANCE INTELLIGENCE ARTEFACT (cia_*)                            │
│ Immutable intelligence output                                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ generation_decision_id
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ COMPLIANCE EVIDENCE GRAPH                                           │
│ Decision · snapshot · nodes · edges                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Position in authority stack

Provenance sits **inside CIE** as internal authoritative explanation of calculation. It is:

| Role | Description |
|------|-------------|
| **Not** a compliance authority | Does not alter scores, rules, evidence, or assessment decisions |
| **Not** a consumer API surface | Accessed via ISL `explain_intelligence`, `compare_intelligence`, `replay_intelligence` |
| **Is** the audit substrate | Auditors answer "why" without AI |
| **Is** the replay substrate | Historical reconstruction without guessing |

```
Authoritative Engines
        ↓
CEG / Graph Service (read-only for CIE)
        ↓
CIE Domain Engines + Registries
        ↓
Provenance (immutable lineage) ──► Artefact (immutable output)
        ↓
Intelligence Service Layer
        ↓
Consumers (dashboards, reports, AI narration)
```

---

## Deterministic calculation trace

Every provenance record preserves a ordered **calculation trace** — one entry per pipeline stage. Stages are reproducible: each records inputs hash, outputs hash, registry versions used, and stage-specific metadata.

### Standard pipeline (artefact-type variants may omit unused stages)

```
Inputs
  ↓  inputs_normalization
Normalization
  ↓  dependency_resolution
Dependency Resolution
  ↓  constraint_resolution
Constraint Resolution
  ↓  weight_calculation
Weight Calculation
  ↓  priority_calculation
Priority Calculation
  ↓  impact_calculation
Impact Calculation
  ↓  artefact_generation
Artefact Generation
  ↓  output_envelope
Output Envelope
  ↓  hashes
Hashes (inputs_hash, response_hash, graph_response_hash)
```

Each stage entry:

```json
{
  "stage": "weight_calculation",
  "stage_version": "weight_calculation_v1",
  "input_hash": "sha256:…",
  "output_hash": "sha256:…",
  "registry_refs": {
    "weight_set_version": "weights_v1.2.0",
    "constraint_set_version": "constraints_v1.0.0"
  },
  "duration_ms": 12,
  "insufficient_evidence": false
}
```

The full trace hash (`trace_hash`) is stored on the provenance record for integrity verification.

---

## Storage boundary

| Collection | Mutability | Access |
|------------|------------|--------|
| `compliance_intelligence_provenance` | Append-only | CIE engine write; ISL read via facade |
| `compliance_intelligence_artefacts` | Append-only | CIE engine write; ISL read via facade |
| Registry collections (see registry docs) | Append-only versions | CIE read; admin publish |

**Forbidden:** Consumers import `compliance_intelligence_engine.storage.provenance` directly — same boundary as artefact storage.

---

## Relationship to existing hash contract

Refinement-01 hashing remains authoritative for artefact identity. Provenance **extends** — does not replace — the hash contract:

| Field | Location | Purpose |
|-------|----------|---------|
| `inputs_hash` | Artefact + Provenance | Canonical upstream input fingerprint |
| `response_hash` | Artefact + Provenance | Canonical output fingerprint |
| `graph_response_hash` | Provenance | Hash of Graph Service envelope(s) consumed |
| `trace_hash` | Provenance only | Hash of ordered calculation trace |

Artefact `provenance_id` is included in `response_hash` exclusion set only if provenance is written after artefact finalisation — implementation orders: compute trace → write provenance → finalise artefact with `provenance_id` → compute `response_hash`.

---

## Registries (summary)

Three immutable registry families feed provenance:

| Registry | Document | Role |
|----------|----------|------|
| Strategy Registry | `STRATEGY_REGISTRY_ARCHITECTURE.md` | Versioned algorithm implementations |
| Weight Registry | `WEIGHT_REGISTRY_ARCHITECTURE.md` | Versioned weight sets — never embedded in code |
| Constraint Registry | `CONSTRAINT_REGISTRY_ARCHITECTURE.md` | Versioned deterministic constraint sets |

Each registry version change forces new provenance on regeneration — historical artefacts remain unchanged.

---

## Replay and comparison (summary)

| Capability | Document |
|------------|----------|
| Historical replay | `REPLAY_ARCHITECTURE.md` |
| Deterministic diff | `COMPARISON_ARCHITECTURE.md` |

Both operate on provenance + registries — never on AI-generated narrative.

---

## Audit questions answered without AI

| Auditor question | Provenance source |
|------------------|-------------------|
| Why did this recommendation exist? | `calculation_trace` + `constraint_set_version` + `source_decision_ids` |
| Why was it highest priority? | `priority_strategy_version` + `weight_set_version` + priority stage trace |
| Why did it change? | `compare_intelligence` against superseded artefact provenance |
| Why was it regenerated? | New `provenance_id`; `supersedes` edge + provenance diff |
| Which calculation version produced it? | `algorithm_version`, `calculation_version`, `engine_version` |
| Which rules applied? | `rule_versions_used[]` |
| Which legislation applied? | `legislation_versions_used[]` |
| Which evidence existed? | `evidence_ids_used[]` + `snapshot_ids_used[]` |
| Which assumptions existed? | Trace `constraint_resolution` stage + `runtime_context_version` |
| Which operational events influenced it? | `operational_event_references[]` |

---

## Future engine evolution

The provenance model supports without redesign:

- Multiple recommendation / prioritisation algorithms (strategy version pins)
- Customer-, portfolio-, jurisdiction-specific optimisation (scoped registry versions in provenance)
- Commercial optimisation engines
- ML-assisted **deterministic** scoring (new strategy versions with explicit model version pins)
- Experimental strategies and A/B validation (parallel provenance records per strategy version)
- Historical engine migration (replay under old `engine_version`)

New engines **register** strategies; they do not extend the provenance schema arbitrarily — they populate existing version reference slots and trace stages.

---

## Acceptance criteria mapping

| Criterion | Architectural response |
|-----------|-------------------------|
| Every CIA references immutable provenance | 1:1 `provenance_id` on artefact; append-only collection |
| Provenance explains calculation lineage | Full schema + calculation trace |
| Strategies independently versioned | Strategy Registry |
| Weights independently versioned | Weight Registry |
| Constraints independently versioned | Constraint Registry |
| Historical replay supported | Replay Architecture |
| Historical comparison supported | Comparison Architecture |
| CEG integration | Graph Integration Updates (Refinement-02) |
| No AI required for deterministic explanation | ISL `explain_intelligence` reads provenance |
| Future engines without redesign | Registry + trace stage extension protocol |

---

## Related documents

| Document | Role |
|----------|------|
| `PROVENANCE_DATA_MODEL.md` | Field-level schema |
| `STRATEGY_REGISTRY_ARCHITECTURE.md` | Algorithm versioning |
| `WEIGHT_REGISTRY_ARCHITECTURE.md` | Weight versioning |
| `CONSTRAINT_REGISTRY_ARCHITECTURE.md` | Constraint versioning |
| `REPLAY_ARCHITECTURE.md` | Historical reconstruction |
| `COMPARISON_ARCHITECTURE.md` | Deterministic diff |
| `GRAPH_INTEGRATION_MODEL.md` | CEG provenance edges (updated) |
| `API_DESIGN.md` | ISL provenance methods (updated) |
| `ARCHITECTURE_REFINEMENT_02.md` | Refinement summary + CIE-2 readiness |
