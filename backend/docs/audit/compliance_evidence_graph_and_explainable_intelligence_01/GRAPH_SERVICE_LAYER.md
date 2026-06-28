# Graph Service Layer

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-ARCHITECTURE-REFINEMENT-01

---

## Principle

> **The graph storage is internal. The Graph Service Layer is the only supported access interface.**

No consumer — including AI, Compliance Engine adapters, Reporting, or future external APIs — may query `compliance_evidence_nodes`, `compliance_evidence_edges`, `compliance_decisions`, or `compliance_decision_snapshots` directly.

**Package:** `services/compliance_graph_service/`  
**Internal storage package:** `services/compliance_evidence_graph/` (private to graph service)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PLATFORM CONSUMERS                        │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│ Compliance   │ Operational  │ Reporting    │ Customer Portal    │
│ Engine       │ Evidence TL  │ Inspector    │ Knowledge Centre   │
│ Regulatory   │ Portfolio    │ Scenario Sim │ AI Assistants      │
│ Framework    │ Analytics    │ External API │ (Phase 5+)         │
└──────┬───────┴──────┬───────┴──────┬───────┴─────────┬──────────┘
       │              │              │                 │
       └──────────────┴──────────────┴─────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   COMPLIANCE GRAPH SERVICE      │
              │   (authoritative public API)    │
              ├───────────────────────────────┤
              │ explain_decision()            │
              │ replay_decision()             │
              │ compare_decision()            │
              │ trace_evidence()              │
              │ trace_requirement()           │
              │ find_decision_dependencies()  │
              │ find_affected_properties()    │
              │ find_affected_requirements()  │
              │ find_missing_evidence()       │
              │ find_superseded_evidence()    │
              │ find_historical_decision()    │
              │ compare_decision_snapshots()  │
              │ trace_operational_impact()    │
              └───────────────┬───────────────┘
                              │ internal only
                              ▼
              ┌───────────────────────────────┐
              │ compliance_evidence_graph/      │
              │  emit_service, storage queries  │
              ├───────────────────────────────┤
              │ compliance_decisions            │
              │ compliance_decision_snapshots   │
              │ compliance_evidence_nodes       │
              │ compliance_evidence_edges       │
              └───────────────────────────────┘
```

---

## Service methods

All methods return a **structured, AI-ready response envelope** (see § AI-readiness) with tenant scoping enforced server-side.

### Core decision services

#### `explain_decision(decision_id, *, actor_context) → ExplainDecisionResponse`

Answers: **Why was this exact decision made?**

- Loads `compliance_decisions` + linked `compliance_decision_snapshots`.
- Returns decision fields, reasoning inputs, evidence set, legislation/rules versions, confidence, operational correlation.
- Does **not** infer from current mutable state.

#### `replay_decision(decision_id | scope, *, as_of=None) → ReplayDecisionResponse`

Chronological replay of events leading to the decision.

- Uses snapshot `timeline_references` + graph traversal bounded by snapshot timestamp.
- Phases: requirements → evidence → extraction → review → authority → score → risk → outcome.

#### `compare_decision(left_decision_id, right_decision_id) → CompareDecisionResponse`

Structured diff between two decisions (outcome, score, risk, evidence, rules, legislation).

Delegates to snapshot comparison when snapshots differ.

#### `compare_decision_snapshots(left_snapshot_id, right_snapshot_id) → CompareSnapshotsResponse`

Deep diff of frozen knowledge states — for historical vs current analysis.

#### `find_historical_decision(scope, *, as_of, decision_type=None) → HistoricalDecisionResponse`

Resolves the effective decision at a point in time.

- Example: "Why was this property compliant six months ago?"
- Returns `decision_id` + `snapshot_id` valid at `as_of`.

---

### Trace services

#### `trace_evidence(evidence_anchor, *, depth=5) → TraceEvidenceResponse`

Traverses evidence lineage: document → extraction → review → CER → requirement → decision.

#### `trace_requirement(requirement_id, *, include_decisions=True) → TraceRequirementResponse`

Full requirement graph: applicability decisions, evidence, assessments, reminders.

#### `trace_operational_impact(decision_id) → TraceOperationalImpactResponse`

Follows `operational_correlation_id` to OE bridge — jobs, queue items, incidents triggered by decision.

#### `find_decision_dependencies(decision_id) → DecisionDependenciesResponse`

Upstream: rules, evidence, prior decisions, jurisdiction, legislation versions required for this decision.

---

### Impact & gap services

#### `find_affected_properties(decision_id) → AffectedPropertiesResponse`

Properties impacted by this decision (portfolio-level decisions).

#### `find_affected_requirements(decision_id) → AffectedRequirementsResponse`

Requirements whose state changed due to this decision.

#### `find_missing_evidence(scope) → MissingEvidenceResponse`

Evidence gaps from latest assessment decision + snapshot reasoning inputs.

#### `find_superseded_evidence(scope) → SupersededEvidenceResponse`

Documents/CERs superseded per `supersedes` edges with provenance.

---

## Standard response envelope (AI-ready)

Every Graph Service response includes:

```json
{
  "service": "explain_decision",
  "service_version": "1.0",
  "generated_at": "2026-06-28T…",
  "request": { "decision_id": "dec_…" },
  "authoritative_references": {
    "decision_id": "dec_…",
    "snapshot_id": "snap_…",
    "decision_ids": [],
    "node_ids": [],
    "edge_ids": [],
    "source_pointers": [
      { "collection": "documents", "id": "doc_abc", "version": 3 }
    ]
  },
  "evidence_lineage": [ ],
  "decision_lineage": {
    "previous_decision_id": "…",
    "superseding_decision_id": null,
    "chain": []
  },
  "confidence_metadata": {
    "decision_confidence": 100,
    "label": "runtime_confirmed"
  },
  "applicable_legislation": [ ],
  "applicable_rules": [ ],
  "historical_references": {
    "snapshot_id": "snap_…",
    "snapshot_timestamp": "…",
    "as_of": null
  },
  "operational_references": {
    "correlation_id": "…",
    "operational_event_ids": []
  },
  "insufficient_evidence": false,
  "payload": { }
}
```

Future AI services consume **only** this envelope — never raw Mongo documents.

---

## HTTP API mapping

**Prefix:** `/api/compliance/graph/` (authenticated, tenant-scoped)

| HTTP | Graph Service method |
|------|---------------------|
| `GET /decisions/{decision_id}/explain` | `explain_decision` |
| `GET /decisions/{decision_id}/replay` | `replay_decision` |
| `GET /decisions/compare?left=&right=` | `compare_decision` |
| `GET /snapshots/compare?left=&right=` | `compare_decision_snapshots` |
| `GET /historical?scope_type=&scope_id=&as_of=` | `find_historical_decision` |
| `GET /evidence/trace?anchor_type=&anchor_id=` | `trace_evidence` |
| `GET /requirements/{id}/trace` | `trace_requirement` |
| `GET /decisions/{id}/dependencies` | `find_decision_dependencies` |
| `GET /decisions/{id}/affected-properties` | `find_affected_properties` |
| `GET /decisions/{id}/affected-requirements` | `find_affected_requirements` |
| `GET /scope/missing-evidence?property_id=` | `find_missing_evidence` |
| `GET /scope/superseded-evidence?property_id=` | `find_superseded_evidence` |
| `GET /decisions/{id}/operational-impact` | `trace_operational_impact` |

**Admin prefix:** `/api/admin/compliance/graph/` — same methods + cross-tenant admin guard.

**Removed from public API:** Direct `GET /nodes`, `GET /subgraph` — internal/debug only behind `COMPLIANCE_EVIDENCE_GRAPH_DEBUG=true`.

---

## Multi-consumer registry

| Consumer | Integration | Methods used |
|----------|-------------|--------------|
| **Compliance Engine** | Emit via internal `emit_service`; read via `explain_decision` | emit (internal), explain, trace |
| **Operational Evidence Timeline** | Bridge `operational_correlation_id`; OE UI links to `explain_decision` | trace_operational_impact |
| **Reporting** | Report jobs store `decision_id`; replay at generation time | replay_decision, find_historical |
| **Inspector View** | Property journey | replay_decision, trace_requirement, trace_evidence |
| **Auditor View** | Decision-centric audit | explain_decision, compare_decision_snapshots |
| **Customer Portal** | Filtered explain (role-scoped) | explain_decision, find_missing_evidence |
| **Knowledge Centre** | Regulation articles link to decisions | applicable_legislation from envelope |
| **Regulatory Framework** | Rule version lineage | find_decision_dependencies |
| **Portfolio Analytics** | Aggregate decision outcomes | find_affected_properties |
| **Scenario Simulation** | Read-only dry-run + compare | compare_decision (hypothetical branch) |
| **Compliance Intelligence** | Advisor recommendations cite decisions | explain_decision, find_missing_evidence |
| **AI Assistants (Phase 5+)** | NL → service dispatch | all methods; **no direct storage** |
| **Future external APIs** | Versioned Graph Service HTTP | public subset of methods |

---

## Future capability mapping

| Future capability | Graph Service foundation |
|-------------------|-------------------------|
| Explain This | `explain_decision` + `trace_*` by object scope |
| Compliance Replay | `replay_decision` |
| Decision Diff | `compare_decision` / `compare_decision_snapshots` |
| Portfolio Advisor | `find_affected_*` + `find_missing_evidence` |
| Compliance Advisor | `find_missing_evidence` + `explain_decision` |
| Predictive Risk | Historical decision chains via `find_historical_decision` |
| Scenario Simulation | `compare_decision` on dry-run branch (no writes) |
| Regulatory Change Impact | `compare_decision_snapshots` across rule versions |
| Audit Preparation | `replay_decision` + snapshot export |
| Insurance Evidence Packs | `trace_evidence` + snapshot bundle |
| Dispute Resolution | `compare_decision_snapshots` + provenance |
| Root Cause Analysis | `find_decision_dependencies` + `trace_operational_impact` |
| Natural Language Search | AI dispatches to Graph Service methods |

**No graph redesign required** — new capabilities add service methods or compose existing ones.

---

## Enforcement

1. **Lint rule / code review:** No imports of `compliance_evidence_graph.storage` outside `compliance_graph_service`.
2. **Route layer:** HTTP handlers call Graph Service only.
3. **AI layer:** `compliance_intelligence/*` imports Graph Service only.
4. **Tests:** `test_graph_service_access_boundary.py` — assert consumers cannot import storage module.

---

## Phase 1 deliverable

Phase 1 implements:

- `compliance_graph_service/` with method stubs + `explain_decision`, `find_historical_decision` (minimal)
- Internal storage in `compliance_evidence_graph/`
- HTTP routes for Graph Service only
- **No** public raw graph storage API
- **No** AI
