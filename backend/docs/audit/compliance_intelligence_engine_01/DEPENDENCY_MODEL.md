# Dependency Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Purpose

Model deterministic dependencies between compliance and operational entities to identify blocked actions, prerequisites, dependency chains, critical paths, and root causes.

---

## Entity types in dependency graph

| Node type | Source authority |
|-----------|------------------|
| `requirement` | `requirements` + assessment decisions |
| `document` | `documents` |
| `evidence` | CERs, reviews |
| `inspection` | Scheduled inspection records |
| `licence` | Licence evidence documents |
| `contractor` | Contractor assignment (ops) |
| `report` | Report generation jobs |
| `recommendation` | CIE recommendations |
| `work_order` | Maintenance work orders |
| `operational_event` | OE timeline events |
| `rule` | Governed rule version |

---

## Edge types

| Edge | Meaning | Example |
|------|---------|---------|
| `requires` | A cannot complete until B satisfied | Rec: book inspection → requires: access arranged |
| `blocks` | A prevents B progress | Missing gas cert blocks HMO licence rec |
| `evidences` | Document satisfies requirement | EICR doc evidences EICR requirement |
| `supersedes` | Newer artefact replaces older | New cert supersedes expired |
| `triggers` | Completion triggers downstream | Assessment VALID triggers reminder clear |
| `correlates` | OE link (non-authoritative) | WO correlates with recommendation |

Edges carry **provenance** identical to CEG edge model: `created_by`, `source_decision_id`, `reason_code`.

---

## Dependency chain output

```json
{
  "chain_id": "dep_chain_<uuid>",
  "root_cause_node": {
    "node_type": "requirement",
    "node_id": "req_gas",
    "summary": "Gas Safety requirement INVALID — expired certificate"
  },
  "critical_path": [
    { "node_type": "document", "node_id": "doc_gas_expired", "status": "expired" },
    { "node_type": "recommendation", "node_id": "rec_book_gas", "status": "generated" },
    { "node_type": "work_order", "node_id": null, "status": "not_created" }
  ],
  "blocked_actions": [
    { "recommendation_id": "rec_hmo_licence", "blocked_by": "req_gas" }
  ],
  "prerequisites": [
    { "recommendation_id": "rec_book_gas", "requires": ["req_access"] }
  ],
  "depth": 3,
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…"
}
```

---

## Algorithms

### find_dependency_chain(anchor_type, anchor_id)

1. BFS from anchor following `requires` + `blocks` edges (Graph Service `find_decision_dependencies` + CIE materialised edges)
2. Cap depth at `MAX_CHAIN_DEPTH=20` — return `truncated: true` if exceeded
3. Identify **root cause** as highest-upstream node with no unsatisfied `requires` parent on compliance authority path
4. Identify **critical path** as longest weighted path (weight = regulatory_exposure of node)

### blocked_actions(scope)

```
FOR each open recommendation in scope:
  IF any prerequisite requirement state != VALID (from latest assessment decision):
    MARK blocked
  IF any blocking requirement has open gap:
    MARK blocked
RETURN blocked list with blocked_by refs
```

### prerequisites(recommendation_id)

Return direct `requires` edges only — transitive closure available via `find_dependency_chain`.

---

## Root cause analysis

Root cause is **deterministic**:

1. Collect all upstream nodes on critical path
2. Select node with highest `regulatory_exposure` factor score
3. Tie-break: earliest `expiry_at` on evidence
4. Tie-break: lexicographic `node_id`

Output includes `root_cause_explanation` template string + `decision_ids[]`.

---

## Integration with Graph Service

| Graph Service method | Dependency use |
|---------------------|----------------|
| `find_decision_dependencies(decision_id)` | Seed compliance-side edges |
| `trace_evidence(anchor)` | Evidence chain traversal |
| `trace_operational_impact(decision_id)` | Ops-side correlation |
| `find_missing_evidence(requirement_id)` | Gap detection for blocks |

CIE **composes** graph responses — does not duplicate storage.

---

## Materialisation strategy

| Approach | When |
|----------|------|
| **On-demand** | Phase 1 — compute per request, cache by `inputs_hash` |
| **Materialised** | Phase 2+ — emit `compliance_intelligence_dependency_chains` on recommendation generation |

Cache TTL optional; invalidation on new compliance assessment decision for scoped requirements.

---

## Insufficient evidence

Return `insufficient_evidence: true` when:

- Anchor node not found in authoritative stores
- Circular dependency detected without resolution decision
- Graph Service returns insufficient for dependency seed
