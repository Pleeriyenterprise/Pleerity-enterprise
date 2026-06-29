# Graph Integration Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Purpose

Define how CIE intelligence artefacts integrate with the Compliance Evidence Graph as first-class indexed entities — extending CEG without breaking access boundaries.

---

## Intelligence backbone relationship

```
Compliance Decision (assessment)
        │
        ▼ generates
Recommendation (CIE)
        │
        ├──► Expected Outcome (impact projection)
        ├──► Dependencies (edges)
        ├──► Affected Evidence (refs)
        ├──► Affected Rules / Legislation (refs)
        ├──► Affected Portfolio (snapshot link)
        ├──► Operational Tasks (WO / reminder refs)
        └──► Completion Outcome (lifecycle transition → assessment decision)
```

The graph becomes the **intelligence backbone** — traversal from any compliance decision to recommended actions and outcomes.

---

## New node types (CEG taxonomy extension)

| Node type | Collection | Emitted by |
|-----------|------------|------------|
| `intelligence_recommendation` | `compliance_intelligence_recommendations` | CIE Recommendation Engine |
| `intelligence_impact_projection` | `compliance_intelligence_impact_projections` | Decision Impact Engine |
| `intelligence_priority_snapshot` | `compliance_intelligence_portfolio_snapshots` / priority snapshots | Priority / Portfolio Engine |
| `intelligence_dependency_chain` | computed / materialised | Dependency Engine |
| `intelligence_regulatory_impact` | `compliance_intelligence_regulatory_impact_reports` | Regulatory Impact Engine |
| `recommendation_lifecycle_transition` | `compliance_intelligence_recommendation_transitions` | Lifecycle Engine |

Registered in `compliance_evidence_graph/constants.py` at implementation time.

---

## New edge types

| Edge type | From | To | Provenance |
|-----------|------|-----|------------|
| `generated_recommendation` | `compliance_decision` | `intelligence_recommendation` | assessment gap decision |
| `recommends_action_for` | `intelligence_recommendation` | `requirement` | template rule |
| `depends_on` | `intelligence_recommendation` | `requirement \| document \| recommendation` | Dependency Engine |
| `projects_impact` | `intelligence_recommendation` | `intelligence_impact_projection` | Impact Engine |
| `prioritised_in` | `intelligence_recommendation` | `intelligence_priority_snapshot` | Priority Engine |
| `affects_portfolio` | `intelligence_recommendation` | `organisation` | scope |
| `operational_task` | `intelligence_recommendation` | `work_order \| reminder` | lifecycle transition |
| `completed_by` | `intelligence_recommendation` | `compliance_decision` | verification assessment |
| `supersedes` | `intelligence_recommendation` | `intelligence_recommendation` | regeneration |
| `regulatory_impact_on` | `intelligence_regulatory_impact` | `property \| decision \| report` | rule change |

All edges require `provenance` block per `GRAPH_DATA_MODEL.md`.

---

## Decision types (CEG extension)

| decision_type | When |
|---------------|------|
| `recommendation` | CIE generates new recommendation |
| `recommendation_lifecycle` | Status transition |
| `priority_snapshot` | Portfolio prioritisation run |
| `regulatory_impact` | Regulatory impact report generated |
| `impact_projection` | Standalone impact calculation |

Aligns with existing `DECISION_RECOMMENDATION` constant in `constants.py`.

---

## Producer architecture

CIE registers as **CEG producer** (Phase 2 pattern):

```text
services/compliance_intelligence_engine/graph_emit.py
  → compliance_evidence_graph.emit_service.emit_intelligence_decision(...)
```

Producer rules:

- Gated by `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=shadow|enabled`
- Gated by `COMPLIANCE_EVIDENCE_GRAPH_MODE=shadow|enabled`
- Atomic: decision + snapshot + nodes + edges in one emit
- Dedupe via `dedupe_key` on recommendations
- Never emit on `insufficient_evidence`

---

## Graph Service extensions (future)

New Graph Service methods (consumer-facing):

| Method | Purpose |
|--------|---------|
| `explain_recommendation(recommendation_id)` | Compose recommendation + generation decision |
| `trace_recommendation_dependencies(recommendation_id)` | Dependency chain |
| `find_open_recommendations(scope)` | Query indexed recommendations |
| `find_regulatory_impact(report_id)` | Regulatory blast radius |

CIE **implements** calculation; Graph Service **implements** traversal/explain — same split as today.

---

## Access boundary (unchanged)

| Allowed | Forbidden |
|---------|-----------|
| CIE → Graph Service (read) | CIE → `compliance_evidence_graph.storage` direct |
| CIE → graph_emit adapter (write via emit_service) | CIE → mutate `requirements` / scores |
| Consumers → Graph Service | Consumers → `compliance_intelligence_recommendations` direct |

---

## AI layer consumption path

```
Graph Service.explain_recommendation()
        OR
CIE envelope passed to AI with graph_service_response_hash
```

AI never reads `compliance_intelligence_recommendations` collection directly.

---

## Integrity validation

Graph Integrity Validator extended with:

- Every `intelligence_recommendation` node has `generation_decision_id`
- Every recommendation edge has provenance
- No orphan impact projections
- Lifecycle transitions form valid DAG (no cycles except supersession)

---

## Migration from legacy recommendation fields

| Legacy | Migration |
|--------|-----------|
| `maintenance_service.recommendation_id` | Populate from CIE `recommendation_id` when WO created from rec |
| Digest `top_next_actions` | Source from `prioritise_actions()` snapshot |
| Report executive recommendations | Cite `recommendation_id` + `generation_decision_id` |

No big-bang — shadow mode dual-write comparison during migration slice.
