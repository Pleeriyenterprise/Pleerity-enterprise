# Architecture Refinement Summary

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement ID:** COMPLIANCE-EVIDENCE-GRAPH-ARCHITECTURE-REFINEMENT-01  
**Status:** Approved — supersedes Phase 0 architecture for implementation  
**Date:** 2026-06-28

---

## What changed

The original Phase 0 architecture treated the graph as an indexed lifecycle layer with `compliance_assessment` as a node attribute. Refinement-01 elevates the platform to a **permanent business intelligence backbone** with three structural upgrades:

| # | Requirement | Architectural response |
|---|-------------|------------------------|
| 1 | Compliance Decisions as first-class entities | Dedicated `compliance_decisions` collection; immutable; independently queryable |
| 2 | Decision Snapshots | `compliance_decision_snapshots` — frozen knowledge state at decision time |
| 3 | Graph Service Layer | `compliance_graph_service/` — sole public API; storage is internal |
| 4 | Multi-consumer platform | Consumer registry; no AI-only framing |
| 5 | Historical explainability | `as_of` + snapshot-based resolution; never current mutable state |
| 6 | Decision comparison | `compare_decision()` / `compare_decision_snapshots()` structured diff |
| 7 | Relationship provenance | Full provenance on every edge |
| 8 | AI readiness without AI in Phase 1 | Standard response envelope on all service methods |
| 9 | Future capabilities | Capability → service method mapping (no redesign) |
| 10 | Acceptance criteria | See below |

---

## Updated collection model

| Collection | Role | Mutable |
|------------|------|---------|
| `compliance_decisions` | First-class immutable decisions | Append-only |
| `compliance_decision_snapshots` | Frozen knowledge at decision time | Immutable after create |
| `compliance_evidence_nodes` | Graph fact vertices | Append-only |
| `compliance_evidence_edges` | Graph relationships with provenance | Append-only |
| `compliance_graph_service_cache` | Optional deterministic response cache | Replaceable |

---

## Updated authority flow

```
Runtime Events
        ↓
Compliance Engine ──emit──→ Compliance Decision + Snapshot
        ↓                           ↓
Rules Engine                  Graph nodes + edges
        ↓                           ↓
Jurisdiction Engine           Graph Service Layer  ←── all consumers
        ↓                           ↓
Operational Evidence          (Explain · Replay · Compare · Trace · …)
        ↓
Authoritative Facts
        ↓
AI Intelligence Layer (Phase 5+ — consumes Graph Service responses only)
```

---

## Document index (refined)

| Document | Content |
|----------|---------|
| `COMPLIANCE_EVIDENCE_GRAPH_ARCHITECTURE.md` | Master architecture (updated) |
| `COMPLIANCE_DECISION_MODEL.md` | Decision + snapshot schemas, historical explainability |
| `GRAPH_SERVICE_LAYER.md` | Service methods, consumers, API, enforcement |
| `GRAPH_DATA_MODEL.md` | Node/edge schemas with provenance |
| `AI_INTELLIGENCE_LAYER_ARCHITECTURE.md` | AI consumes Graph Service only |
| `PHASED_IMPLEMENTATION_PLAN.md` | Revised phases |

---

## Refined acceptance criteria

Implementation architecture is **complete** when demonstrable:

- [ ] **Compliance Decisions** are first-class immutable entities in `compliance_decisions`
- [ ] **Decision Snapshots** preserve complete historical state in `compliance_decision_snapshots`
- [ ] **Historical decisions** reproducible via `find_historical_decision` + snapshot (not current state)
- [ ] **Graph edges** carry full provenance (creator, authority, decision ref, active status)
- [ ] **Graph Service Layer** is the only supported access interface for all consumers
- [ ] **Multiple consumers** (Compliance Engine, OE, Reporting, Portal, Inspector) use Graph Service without duplication
- [ ] **Future AI** can be added without graph redesign — consumes service envelopes only
- [ ] **Every AI explanation** generatable from Graph Service responses, not direct DB queries

---

## Phase 1 scope (revised, ready for implementation)

1. `compliance_decisions` + `compliance_decision_snapshots` schemas + indexes
2. `compliance_evidence_nodes` + `compliance_evidence_edges` with provenance
3. `compliance_graph_service/` — all method signatures + `explain_decision`, `find_historical_decision`, `compare_decision` (deterministic)
4. Internal `compliance_evidence_graph/emit_service` — decision + snapshot atomic emit
5. HTTP routes: Graph Service only (`/api/compliance/graph/*`)
6. Access boundary tests
7. **No AI. No raw storage API. No producers at mutation sites yet (Phase 2).**

---

## Approval status

| Item | Status |
|------|--------|
| Original architecture (Phase 0) | Approved in principle |
| Refinement-01 | **Approved** — implementation may proceed on Phase 1 revised scope |
| Feature flag | `COMPLIANCE_EVIDENCE_GRAPH_MODE=disabled` until Phase 2 producers validated |
