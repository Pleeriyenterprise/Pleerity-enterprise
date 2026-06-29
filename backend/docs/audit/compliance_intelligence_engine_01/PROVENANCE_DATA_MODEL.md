# Provenance Data Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02

---

## Purpose

Define the **Compliance Intelligence Provenance** entity — the immutable, append-only record that authoritatively explains how a Compliance Intelligence Artefact was calculated.

---

## Collection

| Property | Value |
|----------|-------|
| **Name** | `compliance_intelligence_provenance` |
| **ID prefix** | `cip_` |
| **Mutability** | Append-only — never updated or deleted |
| **Cardinality** | Exactly one provenance record per artefact |

---

## Base schema

```json
{
  "provenance_id": "cip_<uuid>",
  "generated_at": "2026-06-17T14:30:00+00:00",
  "artefact_id": "cia_<uuid>",
  "artefact_type": "recommendation",
  "client_id": "uuid",

  "engine_version": "cie-2.0.0",
  "algorithm_version": "recommendation_algorithm_v1",
  "template_version": "recommendation_templates_v1",
  "calculation_version": "cie-calculation-2.0.0",
  "deterministic_seed_version": "cie-seed-1.0.0",

  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…",
  "graph_response_hash": "sha256:…",
  "trace_hash": "sha256:…",

  "decision_ids_used": ["dec_…"],
  "snapshot_ids_used": ["snap_…"],
  "rule_versions_used": [
    { "rule_id": "rule_eicr_renewal", "version": "2026-03-01" }
  ],
  "jurisdiction_versions_used": [
    { "jurisdiction_id": "england", "version": "2026-01-15" }
  ],
  "legislation_versions_used": [
    { "legislation_id": "housing_act_2004", "version": "2026-01-01" }
  ],
  "evidence_ids_used": ["doc_…", "cer_…"],

  "operational_event_references": ["corr_…", "inc_…"],
  "graph_node_references": ["ceg_…"],
  "graph_edge_references": ["cee_…"],

  "recommendation_strategy_version": "rec_strategy_v1.0.0",
  "priority_strategy_version": "priority_strategy_v1.0.0",
  "portfolio_strategy_version": null,
  "regulatory_strategy_version": null,
  "commercial_strategy_version": null,
  "dependency_strategy_version": null,
  "impact_strategy_version": "impact_strategy_v1.0.0",
  "forecast_strategy_version": null,

  "weight_set_version": "weights_v1.2.0",
  "scoring_model_version": "scoring_model_v1.0.0",
  "constraint_set_version": "constraints_v1.0.0",
  "runtime_context_version": "runtime_ctx_v1.0.0",

  "calculation_trace": [
    {
      "stage": "inputs_normalization",
      "stage_version": "normalization_v1",
      "sequence": 1,
      "input_hash": "sha256:…",
      "output_hash": "sha256:…",
      "registry_refs": {},
      "insufficient_evidence": false,
      "metadata": {}
    }
  ],

  "as_of": "2026-06-17T00:00:00+00:00",
  "scope": {
    "client_id": "uuid",
    "property_id": null,
    "requirement_id": null,
    "portfolio_root": true
  },

  "environment": "staging",
  "build_sha": "abc123…",
  "generation_decision_id": "dec_<uuid>"
}
```

---

## Required fields

| Field | Rule |
|-------|------|
| `provenance_id` | Server-generated; immutable |
| `artefact_id` | Unique — one provenance per artefact |
| `artefact_type` | Registered enum (matches CIA) |
| `engine_version` | CIE package version at generation |
| `algorithm_version` | Domain algorithm identifier + version |
| `calculation_version` | Cross-pipeline calculation contract version |
| `deterministic_seed_version` | Seed contract for tie-breaking / ordering stability |
| `inputs_hash` | Must match artefact `inputs_hash` |
| `response_hash` | Must match artefact `response_hash` |
| `trace_hash` | SHA256 of canonical `calculation_trace` |
| `calculation_trace` | Ordered non-empty array (may be single stage for insufficient-evidence artefacts) |
| `constraint_set_version` | Always present — even if no constraints applied |
| `weight_set_version` | Required when weight stages present; null otherwise |
| `generation_decision_id` | CEG decision for artefact creation |

---

## Version reference fields

Strategy version fields are **nullable** — only populated when the corresponding engine participated in the pipeline.

| Field | When required |
|-------|---------------|
| `recommendation_strategy_version` | `artefact_type=recommendation` or recommendation stage in trace |
| `priority_strategy_version` | Priority stage in trace or `artefact_type=priority_assessment` |
| `dependency_strategy_version` | Dependency resolution stage |
| `impact_strategy_version` | Impact calculation stage |
| `portfolio_strategy_version` | Portfolio artefact types |
| `regulatory_strategy_version` | Regulatory impact artefacts |
| `commercial_strategy_version` | Commercial fields calculated |
| `forecast_strategy_version` | Forecast artefacts |

Unpopulated strategy slots are `null` — not omitted — for schema stability.

---

## Upstream reference arrays

### `rule_versions_used`

Pin of every rule version consulted during calculation. Not the live rule store — the **version at `as_of`**.

### `jurisdiction_versions_used` / `legislation_versions_used`

Same principle — historical version pins, not current state.

### `evidence_ids_used`

Document, CER, and evidence node identifiers read during calculation. Must be ⊆ snapshots cited in `snapshot_ids_used` or graph traversal at `as_of`.

### `operational_event_references`

OE correlation IDs, incident fingerprints, or work-order refs that influenced weighting or eligibility — **read-only citations**, not mutations.

---

## Calculation trace stage catalogue

| `stage` | Typical producer engine |
|---------|-------------------------|
| `inputs_normalization` | Orchestrator |
| `dependency_resolution` | Dependency Engine |
| `constraint_resolution` | Constraint evaluator |
| `weight_calculation` | Weight applier |
| `priority_calculation` | Priority Engine |
| `impact_calculation` | Decision Impact Engine |
| `portfolio_aggregation` | Portfolio Engine |
| `regulatory_projection` | Regulatory Impact Engine |
| `commercial_projection` | Commercial Engine |
| `artefact_generation` | Domain engine emit |
| `output_envelope` | Orchestrator |
| `hashes` | Hashing module |

Stages are ordered by `sequence`. Skipped stages are absent — not null placeholders.

---

## Insufficient-evidence provenance

When `insufficient_evidence: true` on the artefact:

- Provenance is **still written**
- `calculation_trace` records the stage where insufficiency was detected
- Final stage includes `insufficient_evidence: true` and `insufficient_reason`
- `response_hash` covers the insufficient artefact body
- Audit trail remains complete — "why nothing was recommended" is explainable

---

## Artefact linkage

CIA base schema gains one required field (Refinement-02):

```json
{
  "artefact_id": "cia_…",
  "provenance_id": "cip_…",
  "…": "existing fields unchanged"
}
```

**Invariant:** `artefact.provenance_id` → `provenance.artefact_id` is bijective.

---

## Indexes (implementation guidance)

| Index | Purpose |
|-------|---------|
| `provenance_id` unique | Primary lookup |
| `(artefact_id, 1)` unique | 1:1 enforcement |
| `(client_id, generated_at DESC)` | Tenant audit queries |
| `inputs_hash` | Dedupe / replay lookup |
| `(artefact_type, engine_version)` | Migration analysis |
| `generation_decision_id` | CEG join |

---

## Integrity rules

1. `provenance.inputs_hash` == `artefact.inputs_hash`
2. `provenance.response_hash` == `artefact.response_hash`
3. `trace_hash` == SHA256(canonical_json(calculation_trace))
4. All registry versions referenced in trace exist in registry collections
5. All `decision_ids_used` resolvable via Graph Service at generation time
6. Provenance immutability — no update operations in storage API

---

## Hashing extensions

```
trace_hash = SHA256(canonical_json(calculation_trace))

provenance_record_hash = SHA256(canonical_json(provenance excluding provenance_id, generated_at))
```

`provenance_record_hash` optional for cross-system export; not required on artefact.

---

## Extension protocol

New artefact types or engines:

1. Add strategy version slot if new engine family (or reuse existing slot)
2. Register trace stages in stage catalogue
3. Bump `calculation_version` minor if trace contract changes
4. Do **not** add arbitrary top-level provenance fields — use `calculation_trace[].metadata` for stage-specific detail
