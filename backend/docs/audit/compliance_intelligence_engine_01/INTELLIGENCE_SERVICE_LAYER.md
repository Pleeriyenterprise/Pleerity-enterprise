# Intelligence Service Layer

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01

---

## Principle

> **Intelligence storage is internal. The Intelligence Service Layer (ISL) is the only supported access interface for Compliance Intelligence Artefacts.**

Parallel to the Compliance Evidence Graph pattern:

| Layer | Storage (internal) | Public interface |
|-------|-------------------|------------------|
| CEG | `compliance_evidence_nodes`, decisions, snapshots | Graph Service |
| CIE | `compliance_intelligence_artefacts`, transitions | **Intelligence Service Layer** |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONSUMERS                                 │
├────────────┬────────────┬────────────┬────────────┬────────────┤
│ Decision   │ Reports    │ Digest     │ Dashboards │ AI Layer   │
│ Explorer   │ Inspector  │ Portfolio  │ Auditor    │ (Phase 5+) │
│ OE Timeline│ Knowledge  │ Customer   │ Public API │ Advisors   │
│            │ Centre     │ Portal (*) │ (future)   │ (future)   │
└─────┬──────┴─────┬──────┴─────┬──────┴─────┬──────┴──────┬─────┘
      │            │            │            │             │
      └────────────┴────────────┴────────────┴─────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  INTELLIGENCE SERVICE LAYER      │
              │  services/compliance_intelligence_service/ │
              ├───────────────────────────────┤
              │ generate_intelligence()        │
              │ generate_recommendations()     │
              │ generate_portfolio_insights()  │
              │ generate_decision_impact()     │
              │ generate_regulatory_impact()   │
              │ generate_forecast()            │
              │ generate_readiness()           │
              │ generate_dependency_chain()    │
              │ generate_remediation_strategy()│
              │ list_intelligence()            │
              │ compare_intelligence()         │
              │ explain_intelligence()         │
              │ transition_intelligence()      │
              └───────────────┬───────────────┘
                              │ internal only
                              ▼
              ┌───────────────────────────────┐
              │  COMPLIANCE INTELLIGENCE ENGINE │
              │  services/compliance_intelligence_engine/ │
              ├───────────────────────────────┤
              │ Domain engines · orchestrator  │
              │ graph_emit · read_adapter      │
              └───────────────┬───────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   compliance_intelligence_artefacts    Graph Service (read)
```

(*) Future customer portal — not Phase 1.

---

## Package boundary

| Package | Role | May import |
|---------|------|------------|
| `compliance_intelligence_service` | ISL — consumer API | `compliance_intelligence_engine` (orchestrator), `compliance_graph_service` |
| `compliance_intelligence_engine` | Calculation + storage write | `compliance_graph_service`, `compliance_evidence_graph.emit_service` |
| `compliance_intelligence` (AI Phase 5) | Narration | **ISL only** — not CIE storage |
| Routes / UI / Reports | HTTP | **ISL only** |

**Forbidden:** `from services.compliance_intelligence_engine.storage import …` from any consumer.

---

## Core methods

### Generation (dispatch to CIE)

| Method | `artefact_type` | Notes |
|--------|-----------------|-------|
| `generate_intelligence(artefact_type, scope, …)` | Any registered | Generic dispatcher |
| `generate_recommendations(scope)` | `recommendation` | Pipeline A shortcut |
| `generate_portfolio_insights(client_id)` | `portfolio_insight` | |
| `generate_decision_impact(artefact_id \| scope)` | `decision_impact_assessment` | |
| `generate_regulatory_impact(event)` | `regulatory_impact_assessment` | |
| `generate_forecast(client_id, window)` | `forecast` \| `workload_forecast` | Deterministic only |
| `generate_readiness(scope, kind)` | `audit_readiness_assessment` \| `insurance_readiness_assessment` | |
| `generate_dependency_chain(anchor)` | `dependency_chain` | |
| `generate_remediation_strategy(scope)` | `remediation_strategy` | Composite bundle |

All return **Intelligence Service Envelope** (extends CIE-0 `IntelligenceEnvelope`).

### Query

| Method | Purpose |
|--------|---------|
| `list_intelligence(scope, artefact_type?, lifecycle_state?, active_only?)` | Filtered artefact list |
| `get_intelligence(artefact_id)` | Single artefact + lineage summary |
| `compare_intelligence(left_id, right_id)` | Structural diff |
| `explain_intelligence(artefact_id)` | Deterministic explanation |
| `get_intelligence_lifecycle(artefact_id)` | Transition history |

### Lifecycle

| Method | Purpose |
|--------|---------|
| `transition_intelligence(artefact_id, to_state, actor, reason)` | Immutable transition |

---

## Response envelope

```json
{
  "service": "explain_intelligence",
  "insufficient_evidence": false,
  "artefact_id": "cia_…",
  "artefact_type": "recommendation",
  "response_hash": "sha256:…",
  "artefact": { },
  "authoritative_references": {
    "artefact_ids": ["cia_…"],
    "decision_ids": ["dec_…"],
    "snapshot_ids": ["snap_…"]
  },
  "graph_service_response_hash": "sha256:… | null",
  "tier1": { },
  "tier2": null
}
```

`tier1` / `tier2` alignment with Phase 5 AI envelope allows drop-in narration.

---

## HTTP surface (future)

**Prefix:** `/api/admin/compliance/intelligence/`  
**Note:** Distinct from Phase 5 `/api/admin/compliance/intelligence/investigate` (Graph dispatch). ISL routes use `/artefacts/*` or `/engine/*` to avoid collision — exact path TBD at CIE-5.

---

## Caching

Deterministic cache keyed by `inputs_hash` + `artefact_type`. Invalidation on new assessment decisions in scope.

---

## Tenant access

Same `ActorContext` model as Graph Service. Portal users scoped to `client_id`. Admin may cross-tenant for ops views.

---

## Relationship to Graph Service

ISL **may** call Graph Service during `explain_intelligence()` to enrich with `explain_decision()`. ISL **does not** replace Graph Service for compliance decision history — complementary layers.
