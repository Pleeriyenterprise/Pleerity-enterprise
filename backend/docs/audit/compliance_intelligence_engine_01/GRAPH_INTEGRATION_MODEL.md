# Graph Integration Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01

---

## Purpose

Define how **Compliance Intelligence Artefacts** integrate with the Compliance Evidence Graph — extending CEG without breaking access boundaries.

---

## Intelligence relationship chain

```
Compliance Decision (assessment)
        │
        ▼ generates
Compliance Intelligence Artefact (cia_*)
        │
        ├──► recommendation (subtype payload)
        │         │
        │         ├──► Expected Outcome (decision_impact_assessment artefact)
        │         ├──► Operational Tasks (work_order / reminder refs)
        │         └──► Completion → assessment decision (authority)
        │
        ├──► priority_assessment
        ├──► dependency_chain
        ├──► portfolio_insight / risk / readiness / trend
        ├──► regulatory_impact_assessment
        └──► forecast / workload_forecast / operational_insight
                │
                ├──► Evidence (refs)
                ├──► Reports (consumer refs)
                ├──► Portfolio (scope)
                ├──► Customer Impact (payload fields)
                ├──► Operational Impact (OE correlation)
                └──► Historical Outcomes (supersession chain)
```

Every edge is traceable with full provenance.

---

## Node types (CEG taxonomy extension)

| Node type | Maps to | `artefact_type` |
|-----------|---------|-----------------|
| `compliance_intelligence_artefact` | `compliance_intelligence_artefacts` | any |
| `intelligence_recommendation` | payload view | `recommendation` |
| `intelligence_impact` | payload view | `decision_impact_assessment` |
| `intelligence_priority` | payload view | `priority_assessment` |
| `intelligence_dependency` | payload view | `dependency_chain` |
| `intelligence_portfolio` | payload view | portfolio types |
| `intelligence_regulatory` | payload view | `regulatory_impact_assessment` |
| `intelligence_lifecycle_transition` | `compliance_intelligence_artefact_transitions` | — |

**Canonical graph node:** `compliance_intelligence_artefact` with `artefact_type` attribute. Subtype-specific node types optional for traversal ergonomics.

---

## Edge types

| Edge type | From | To |
|-----------|------|-----|
| `generated_intelligence` | `compliance_decision` | `compliance_intelligence_artefact` |
| `artefact_subtype` | `compliance_intelligence_artefact` | typed view / payload role |
| `recommends_action_for` | artefact (`recommendation`) | `requirement` |
| `depends_on` | artefact | `requirement \| document \| artefact` |
| `projects_impact` | artefact | `decision_impact_assessment` artefact |
| `prioritised_in` | artefact | `priority_assessment` artefact |
| `affects_portfolio` | artefact | `organisation` |
| `operational_task` | artefact | `work_order \| reminder` |
| `completed_by` | artefact | `compliance_decision` |
| `supersedes` | artefact | artefact |
| `regulatory_impact_on` | `regulatory_impact_assessment` | `property \| decision \| report` |
| `references_evidence` | artefact | `document \| cer \| node` |
| `consumed_by` | artefact | consumer registry id |
| `customer_impact` | artefact | `property` (tenant scope) |
| `operational_impact` | artefact | OE correlation node |
| `historical_outcome` | artefact | superseded / completed artefact chain |

All edges require provenance per `GRAPH_DATA_MODEL.md`.

---

## Decision types (CEG extension)

| decision_type | When |
|---------------|------|
| `intelligence_artefact` | CIE emits any CIA |
| `intelligence_lifecycle` | Any lifecycle transition |
| `recommendation` | Alias for intelligence_artefact where type=recommendation (backward compat) |
| `recommendation_lifecycle` | Alias for recommendation transitions |

---

## Producer architecture

CIE `graph_emit.py` emits atomic:

1. `compliance_decisions` (`intelligence_artefact`)
2. `compliance_decision_snapshots` (frozen artefact JSON)
3. Graph nodes + provenanced edges

Gated by `COMPLIANCE_INTELLIGENCE_ENGINE_MODE` + `COMPLIANCE_EVIDENCE_GRAPH_MODE`.

---

## Graph Service extensions (future)

| Method | Purpose |
|--------|---------|
| `explain_intelligence(artefact_id)` | Delegates to ISL / reads snapshot |
| `trace_intelligence_lineage(artefact_id)` | Supersession + source decisions |
| `find_open_intelligence(scope, artefact_type?)` | Indexed query |

Consumers use **ISL first**; Graph Service provides decision-lineage join.

---

## Access boundary (unchanged)

| Allowed | Forbidden |
|---------|-----------|
| CIE → Graph Service (read) | Consumers → `compliance_intelligence_artefacts` direct |
| CIE → emit_service (write) | CIE → mutate compliance authority |
| Consumers → ISL | Consumers → CIE storage |

---

## Integrity validation extensions

- Every CIA node has `generation_decision_id`
- Orphan impact / dependency artefacts linked to parent CIA
- Lifecycle transitions form valid DAG
- `response_hash` on snapshot matches artefact record

---

## Legacy migration

| Legacy | Target |
|--------|--------|
| `maintenance_service.recommendation_id` | `artefact_id` where type=recommendation |
| Per-type collections (CIE-0) | Unified `compliance_intelligence_artefacts` at implementation |

Shadow dual-write optional during CIE-2 migration slice.
