# Weight Registry Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02

---

## Purpose

Define the **Weight Registry** — versioned, immutable weight sets used in deterministic CIE calculations.

**Weighting must not be embedded inside algorithms.** Changing a weight produces a new registry version, a new provenance record, and a new intelligence artefact. Historical artefacts remain unchanged.

---

## Design principles

| Principle | Rule |
|-----------|------|
| Externalisation | All numeric weights live in registry documents |
| Versioning | Semantic version per weight set (`weights_v1.2.0`) |
| Immutability | Published weight sets are never modified |
| Provenance pin | `weight_set_version` on every provenance using weights |
| Traceability | Weight calculation stage records applied weight keys |

---

## Collection

**Name:** `compliance_intelligence_weight_registry`  
**ID pattern:** `weights_v{major}.{minor}.{patch}` or scoped variants e.g. `weights_v1.2.0-england`

---

## Weight set schema

```json
{
  "weight_set_id": "weights_v1.2.0",
  "semantic_version": "1.2.0",
  "published_at": "2026-06-01T00:00:00+00:00",
  "status": "active",
  "supersedes_weight_set_id": "weights_v1.1.0",
  "description": "Default operational weighting v1.2",
  "scope": {
    "global": true,
    "client_id": null,
    "jurisdiction_id": null
  },
  "weights": {
    "risk_weight": 0.35,
    "urgency_weight": 0.25,
    "portfolio_weight": 0.10,
    "dependency_weight": 0.10,
    "cost_weight": 0.05,
    "insurance_weight": 0.05,
    "audit_weight": 0.05,
    "tenant_impact_weight": 0.03,
    "operational_capacity_weight": 0.01,
    "commercial_impact_weight": 0.01
  },
  "normalization_rule": "sum_to_1.0",
  "content_hash": "sha256:…"
}
```

---

## Standard weight keys (v1 catalogue)

| Key | Used in |
|-----|---------|
| `risk_weight` | Priority, portfolio risk |
| `urgency_weight` | Priority, recommendation ranking |
| `portfolio_weight` | Portfolio aggregation |
| `dependency_weight` | Dependency chain severity |
| `cost_weight` | Commercial intelligence |
| `insurance_weight` | Insurance readiness |
| `audit_weight` | Audit readiness |
| `tenant_impact_weight` | Customer impact projection |
| `operational_capacity_weight` | Workload forecast |
| `commercial_impact_weight` | Commercial optimisation |

New keys append to catalogue with registry minor version bump — no provenance schema change.

---

## Weight application trace

The `weight_calculation` stage in provenance records:

```json
{
  "stage": "weight_calculation",
  "registry_refs": {
    "weight_set_version": "weights_v1.2.0"
  },
  "metadata": {
    "applied_weights": {
      "risk_weight": 0.35,
      "urgency_weight": 0.25
    },
    "weighted_scores": {
      "cia_candidate_1": 87.5
    }
  },
  "output_hash": "sha256:…"
}
```

Enables comparison: "which weight changed?" without re-running engines.

---

## Resolution rules

```
1. Resolve weight_set_id for (scope, jurisdiction, client, as_of)
2. Default: latest active global weight set where published_at ≤ as_of
3. Override: most specific scope wins (client > jurisdiction > global)
4. Pin weight_set_id in provenance before weight_calculation stage
```

---

## Change management

| Event | System behaviour |
|-------|------------------|
| Weight value changed | Publish `weights_v1.3.0`; old artefacts unchanged |
| New weight key added | Minor version bump; strategies declare required keys |
| Weight set deprecated | Status only; historical provenance still references old ID |
| Regeneration requested | New artefact + new provenance under new weight set |

---

## Relationship to scoring model

| Concept | Role |
|---------|------|
| `weight_set_version` | Numeric multipliers |
| `scoring_model_version` | Formula / aggregation logic (registered in Strategy Registry or separate scoring registry) |

Provenance records both. Changing formula without weights → new `scoring_model_version`. Changing weights without formula → new `weight_set_version`.

---

## Anti-patterns (forbidden)

| Forbidden | Correct approach |
|-----------|------------------|
| `PRIORITY_RISK_WEIGHT = 0.35` in engine code | Entry in weight registry |
| Runtime admin UI edits weights in place | Publish new weight set version |
| Silent weight change on redeploy | Explicit registry publication + provenance pin |

---

## CIE-2 implication

The Priority Engine in CIE-2 **cannot ship** without Weight Registry v1 published and pinned in provenance. Priority ordering stability tests (V2) must assert `weight_set_version` in addition to `response_hash`.
