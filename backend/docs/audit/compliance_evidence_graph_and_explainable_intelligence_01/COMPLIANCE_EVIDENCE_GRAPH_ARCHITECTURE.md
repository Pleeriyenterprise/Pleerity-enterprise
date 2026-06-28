# Compliance Evidence Graph & Explainable Compliance Intelligence — Architecture

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-ARCHITECTURE-REFINEMENT-01  
**Status:** Architecture refined — Phase 1 implementation authorised  
**Date:** 2026-06-28  
**Prerequisite:** Operational Evidence Platform Phases 1–4 accepted on staging (`49eb7978`)

---

## Executive summary

Pleerity already has mature **compliance scoring**, **rules/jurisdiction engines**, **template explainability**, and an **Operational Evidence Platform** (ops causality index). What it lacks is a **unified Compliance Evidence Graph (CEG)** that connects every compliance decision, evidence artefact, rule evaluation, score change, and operational consequence into one **append-only, reproducible knowledge graph**.

This programme implements that graph as the **permanent business intelligence backbone** of Pleerity — not an AI feature or reporting adjunct. A **Graph Service Layer** is the sole supported access interface. An **AI Intelligence Layer** (Phase 5+) **consumes Graph Service responses** — never inventing facts, scores, regulations, or relationships.

---

## Authority stack (non-negotiable)

```
Runtime Events
        │
Compliance Engine  (scoring, authority sync, outcome engine)
        │
Rules Engine       (requirement_rules, governed rules, applicability)
        │
Jurisdiction Engine (compliance_rules_registry attribution)
        │
Compliance Decision + Snapshot  ← NEW first-class immutable decision records
        │
Compliance Evidence Graph  ← graph nodes + provenanced edges (internal storage)
        │
Graph Service Layer  ← NEW sole public interface (Explain · Replay · Compare · Trace)
        │
Operational Evidence Timeline  (existing ops investigation layer)
        │
──────────────────────────────────────
Authoritative Facts (requirements, documents, CERs, score_ledger, job_runs, …)
──────────────────────────────────────
        │
        ▼
AI Intelligence Layer  ← Phase 5+ read-only interpreter (Graph Service consumer)
        │
Explain · Summarise · Compare · Recommend · Predict · Answer · Report
```

| Layer | Role | Authority |
|-------|------|-----------|
| `requirements`, `documents`, `compliance_evidence_records` | Mutable / fact stores | **Yes** — compliance state |
| `score_ledger_events`, `compliance_activity_log` | Append-only ledgers | **Yes** — score/outcome facts |
| `operational_evidence_events` | Ops correlation index | **No** for compliance — ops only |
| `compliance_decisions` + `compliance_decision_snapshots` | Immutable decision + frozen knowledge | **Yes** — decision authority index |
| `compliance_evidence_nodes` + `compliance_evidence_edges` | Graph traversal storage | **Internal** — not directly queried |
| `compliance_graph_service` | Platform capability API | **Yes** — supported access interface |
| AI services | Narration / Q&A | **Never** — Graph Service consumer only |

**The AI never becomes the source of truth.**

---

## Problem statement (from domain audit)

`COMPLIANCE-EVENT-DOMAIN-MODEL-AUDIT-01` verdict: lifecycle meaning is inferred from mutable requirement snapshots across enrich, authority sync, scoring, and parallel logs. **`requirement_transition_trace` is ephemeral**. No first-class immutable compliance event ledger exists.

The CEG closes this gap without replacing existing engines or duplicating operational authority.

---

## Design principles

1. **Compliance Decisions are first-class** — every decision is an immutable `compliance_decisions` record with a frozen `compliance_decision_snapshots` companion.
2. **Downstream artefacts cite decisions** — scores, risks, reminders, recommendations, work orders, and reports reference `decision_id`.
3. **Graph storage is internal** — all consumers use `compliance_graph_service`; no direct collection queries.
4. **Authoritative pointers** — every graph node carries `source_collection` + `source_id` (+ optional `source_version`).
5. **Immutable append-only** — nodes, edges, decisions, and snapshots are never updated in place; supersession creates new records.
6. **Historical explainability** — past-tense questions resolve against snapshots at `as_of`, never current mutable state.
7. **Reproducible explanations** — Graph Service responses include `authoritative_references`, lineage, and confidence metadata.
8. **Relationship provenance** — every edge records why it exists, who created it, and which decision references it.
9. **Insufficient evidence is explicit** — `"insufficient_evidence": true` when traversal cannot support a claim.
10. **Tenant isolation** — all queries enforce `client_id` (and role scope) server-side.
11. **Bridge, don't duplicate** — link to OE via `operational_correlation_id`; do not re-emit ops facts as compliance authority.
12. **Rules stay in Rules Engine** — graph records *which rule evaluation occurred*; rules engine remains authoritative for logic.
13. **AI readiness without AI in Phase 1** — all Graph Service responses use the standard AI-ready envelope.

---

## Collections

| Collection | Role | Access |
|------------|------|--------|
| `compliance_decisions` | First-class immutable compliance decisions | Graph Service internal |
| `compliance_decision_snapshots` | Frozen knowledge state at decision time | Graph Service internal |
| `compliance_evidence_nodes` | Graph fact vertices | Graph Service internal |
| `compliance_evidence_edges` | Provenanced relationships | Graph Service internal |
| `compliance_graph_service_cache` | Optional deterministic response cache | Graph Service internal |

**Phase 5+ only:** `compliance_ai_narrations` — LLM audit trail (consumes Graph Service envelopes).

**Not replacing:** `requirements`, `documents`, `score_ledger_events`, `operational_evidence_events`.

See `COMPLIANCE_DECISION_MODEL.md` and `GRAPH_DATA_MODEL.md` for schemas.

---

## Node taxonomy

**Primary entity:** `compliance_decision` — see `COMPLIANCE_DECISION_MODEL.md`. Every significant compliance outcome emits a decision + snapshot before downstream artefacts.

Supporting graph node types (traversal index):

| Node type | Authoritative source | Notes |
|-----------|---------------------|-------|
| `compliance_decision` | `compliance_decisions` | Mirror node for graph traversal; links to snapshot |
| `decision_snapshot` | `compliance_decision_snapshots` | Reference node for snapshot edges |
| `organisation` | `clients` | portfolio root |
| `property` | `properties` | dwelling unit |
| `requirement` | `requirements` | obligation row snapshot ref |
| `rule` | `requirement_rules` / governed versions | applicability rule at version |
| `jurisdiction` | attribution projection | England, Wales, local authority |
| `document` | `documents` | uploaded certificate |
| `cer` | `compliance_evidence_records` | structured evidence |
| `ai_extraction` | `documents.extraction` | extraction blob ref |
| `human_review` | `evidence_review_events` | approve/reject |
| `authority_sync` | authority sync outcome | expiry/state transition (feeds decision) |
| `score_change` | `score_ledger_events` | **must reference `decision_id`** |
| `risk_assessment` | `risk_signals` | **must reference `decision_id`** |
| `reminder` | reminder evaluation | **must reference `decision_id`** |
| `recommendation` | gap/advisor output | **must reference `decision_id`** |
| `work_order` | `work_orders` | **must reference `decision_id`** when compliance-triggered |
| `notification` | `message_logs` | delivery fact |
| `incident` | `incidents` | ops incident (linked, not authoritative) |
| `operational_event` | `operational_evidence_events` | cross-link only |
| `user_action` | `audit_logs` / actor fields | admin/landlord action |
| `report` | report generation job | **must reference `decision_id`** |

**Removed as standalone authority:** `compliance_assessment` as a mere node attribute — assessments are `decision_type=compliance_assessment` decisions.

---

## Edge taxonomy

| Edge type | Semantics |
|-----------|-----------|
| `belongs_to` | property → portfolio, requirement → property |
| `governed_by` | requirement → rule, rule → jurisdiction |
| `supported_by` | requirement → document/CER |
| `extracted_from` | ai_extraction → document |
| `verified_by` | human_review → document/CER |
| `decided_under` | compliance_decision → rule/jurisdiction/legislation version |
| `based_on_evidence` | compliance_decision → evidence nodes |
| `produced` | compliance_decision → score_change / reminder / report / work_order |
| `triggered` | action → recalc / reminder / work_order |
| `caused` | decision → downstream effect |
| `supersedes` | new decision/document → prior record |
| `correlates_with` | compliance node ↔ operational_event |
| `evaluated_under` | decision → rule version at evaluation time |
| `snapshot_of` | decision_snapshot → point-in-time evidence state |

Every edge carries **full provenance** (see `GRAPH_DATA_MODEL.md`). Unknown edges remain **absent** — never fabricated.

---

## Graph Service Layer (sole public interface)

**Package:** `services/compliance_graph_service/`  
**Documentation:** `GRAPH_SERVICE_LAYER.md`

| Method | Purpose |
|--------|---------|
| `explain_decision()` | Why was this exact decision made? |
| `replay_decision()` | Chronological replay to decision |
| `compare_decision()` | Structured diff between two decisions |
| `compare_decision_snapshots()` | Historical vs current knowledge diff |
| `find_historical_decision()` | Decision effective at `as_of` |
| `trace_evidence()` | Evidence lineage traversal |
| `trace_requirement()` | Requirement graph + decisions |
| `find_decision_dependencies()` | Upstream rules, evidence, prior decisions |
| `find_affected_properties()` | Portfolio impact |
| `find_affected_requirements()` | Requirement impact |
| `find_missing_evidence()` | Evidence gaps |
| `find_superseded_evidence()` | Supersession chain |
| `trace_operational_impact()` | OE correlation follow-through |

**Consumers:** Compliance Engine, OE Timeline, Reporting, Inspector, Auditor, Customer Portal, Knowledge Centre, Regulatory Framework, Portfolio Analytics, Scenario Simulation, Compliance Intelligence, AI Assistants, future external APIs.

**No consumer may query graph storage directly.**

---

## Internal storage services

**Package:** `services/compliance_evidence_graph/` (private)

| Module | Responsibility |
|--------|----------------|
| `emit_service.py` | Atomic emit: decision + snapshot + nodes + provenanced edges |
| `storage/` | Internal Mongo queries — not imported outside graph service |
| `producers.py` | Mutation-boundary hooks (Phase 2) |
| `backfill_service.py` | Historical graph from authoritative sources |
| `bridge_operational.py` | `operational_correlation_id` join to OE |

---

## HTTP API surface

**Public prefix:** `/api/compliance/graph/` — Graph Service methods only.  
**Admin prefix:** `/api/admin/compliance/graph/` — same + admin guard.

See `GRAPH_SERVICE_LAYER.md` for full route mapping.

**Not exposed in production:** raw `GET /nodes`, `GET /subgraph` — debug-only behind `COMPLIANCE_EVIDENCE_GRAPH_DEBUG=true`.

All routes enforce tenant + role guards.

---

## AI Intelligence Layer (Phase 5+ only)

**Package:** `services/compliance_intelligence/`  
**Documentation:** `AI_INTELLIGENCE_LAYER_ARCHITECTURE.md`

**Critical rule:** AI services call `compliance_graph_service` methods only. They receive structured envelopes with `authoritative_references`, `evidence_lineage`, `decision_lineage`, `confidence_metadata`, `applicable_legislation`, `applicable_rules`, `historical_references`, and `operational_references`.

**Phase 1–4: No AI implementation.** Graph Service responses are AI-ready by design.

---

## Integration map (mutation producers — Phase 2)

Each mutation emits **decision + snapshot atomically**, then graph nodes/edges:

| Mutation authority | Decision type | Downstream `decision_id` citation |
|--------------------|---------------|-----------------------------------|
| `requirement_evidence_authority.sync_*` | `compliance_assessment` | requirement projection |
| `compliance_scoring_service.recalculate_*` | `compliance_score_change` | `score_ledger_events` |
| `score_ledger_service.log_score_change` | (references parent decision) | ledger row |
| `evidence_review_events` | `evidence_acceptance` / `evidence_rejection` | document state |
| `compliance_evidence_record_service` | `evidence_acceptance` | CER row |
| `applicability_resolution_audit` | `requirement_applicability` | requirement applicability |
| `reminder_*` services | `reminder_generation` | reminder records |
| `work_orders` lifecycle | `work_order_creation` | work order row |
| Report generation | `report_generation` | report job |

Each emit sets `operational_correlation_id` and calls `bridge_operational.link_correlation()`.

---

## Frontend surfaces

| Surface | Phase | Location |
|---------|-------|----------|
| Explain This panel (reusable) | 4 | `components/compliance/ExplainThisPanel.js` |
| Compliance Replay drawer | 4 | embedded in requirement/property/score views |
| Evidence Graph explorer (admin) | 3 | `/admin/compliance/evidence-graph` |
| Inspector journey view | 7 | `/inspector/properties/{id}/journey` |
| Customer evidence timeline (filtered) | 7 | extend client property timeline |
| AI investigation sidebar | 5 | admin graph page |

---

## Performance strategy

- **Incremental emit** at mutation time (not batch recompute).
- **Bounded subgraph queries** (`max_depth`, `max_nodes`, cursor pagination).
- **Lazy edge loading** — node list first, edges on expand.
- **Background backfill** job (mirrors OE maintenance pattern).
- **Indexes** on `client_id`, `property_id`, `requirement_id`, `node_type`, `occurred_at`, `correlation_id`, `dedupe_key` (unique).
- **Explanation cache** keyed by `(object_type, object_id, graph_watermark)` where watermark = latest node `recorded_at` for scope.

Target: subgraph first page < 500ms at 10k nodes/property (staging acceptance mirrors OE).

---

## Security model

| Control | Implementation |
|---------|----------------|
| Tenant isolation | `client_id` required on all client routes; server-side filter |
| Role-based views | landlord / agent / contractor / inspector / admin scopes |
| ABAC | property-level assignment checks for contractors |
| Immutable evidence | graph nodes append-only; annotations separate collection |
| AI safety | citation-required schema; insufficient evidence fallback |
| Audit | all `investigate` and LLM calls logged with actor + subgraph hash |

---

## Relationship to Operational Evidence Platform

```
Compliance mutation → CEG node (compliance authority index)
                   → OE producer (ops index, existing)
                   ↔ linked by correlation_id / compliance_node_id on OE metadata
```

Admin investigation flow:

1. **Compliance question** → CEG replay + decision engine (primary).
2. **Ops/automation question** → OE timeline + story (primary).
3. **Cross-domain** → bridge edge `correlates_with` joins both subgraphs.

---

## Acceptance criteria (Refinement-01)

| Criterion | Phase |
|-----------|-------|
| Compliance Decisions are first-class immutable entities | 1 |
| Decision Snapshots preserve complete historical state | 1 |
| Historical decisions reproducible from snapshots | 1–3 |
| Graph relationships have full provenance | 1 |
| Graph Service Layer is sole supported access interface | 1 |
| Multiple platform consumers use Graph Service without duplication | 2–7 |
| Architecture supports future AI without redesign | 1 (envelope) / 5 (AI) |
| Every AI explanation from Graph Service responses only | 5 |
| Every compliance decision explainable via `explain_decision()` | 2–3 |
| Decision comparison via `compare_decision()` | 3 |
| Ops + compliance connected via `trace_operational_impact()` | 2 |
| No duplicate authority | 0–1 |
| Inspector reconstructs journey from `replay_decision()` | 7 |

---

## Out of scope (this programme)

- Replacing Compliance Engine or Rules Engine logic
- Mutating compliance scores from AI recommendations
- New microservice deployment (monolith modules, same as OE)
- Cold archive implementation (defer to Phase 8+)
- Full business event catalogue wiring (incremental per producer)

---

## References

- `ARCHITECTURE_REFINEMENT_01.md` — refinement summary and Phase 1 scope
- `COMPLIANCE_DECISION_MODEL.md` — decision + snapshot schemas
- `GRAPH_SERVICE_LAYER.md` — service methods and consumer registry
- `backend/docs/audit/operational_evidence_timeline_implementation_02/`
- `backend/docs/audit/compliance_event_domain_model_audit_01.json`
- `backend/docs/STREAM_F_FORENSICS_JOIN_RECIPE.md`
