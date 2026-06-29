# Compliance Intelligence Engine — Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Status:** Architecture approved for planning — **no implementation in this slice**  
**Date:** 2026-06-02  
**Prerequisite:** Compliance Evidence Graph Phases 1–5 Tier 1 accepted on staging (`PHASE_5_TIER1_STAGING_ACCEPTED`)

---

## Executive summary

The **Compliance Intelligence Engine (CIE)** transforms authoritative compliance history into **prioritised, evidence-backed, deterministic operational intelligence**.

This is **not an AI programme**. It is a **business intelligence and decision-support** programme. The existing **AI Intelligence Layer** (`services/compliance_intelligence/`, Phase 5) becomes a **consumer** of CIE outputs — explaining deterministic intelligence, never creating it.

CIE answers **"What should happen next?"** while remaining:

- **Deterministic** — same inputs + engine version → same outputs (hashable)
- **Explainable** — every output cites decisions, evidence, rules, legislation
- **Auditable** — immutable records + graph lineage
- **Reproducible** — replay from snapshots, not mutable state
- **Independent of any language model**

---

## Mission

Build the deterministic engine that converts authoritative compliance evidence into prioritised operational intelligence for landlords, operators, and internal teams — without becoming a compliance authority.

---

## Non-authority contract (non-negotiable)

CIE **must never**:

| Forbidden action | Rationale |
|------------------|-----------|
| Determine compliance outcomes | Compliance Engine + Rules Engine remain authoritative |
| Change compliance scores | Score ledger is append-only authority |
| Override rules or legislation | Rules/Jurisdiction engines own interpretation logic |
| Modify evidence or requirements | Fact stores are upstream |
| Create compliance *assessment* decisions | CIE creates *intelligence* artefacts only |
| Speculate when evidence is insufficient | Return `insufficient_evidence: true` |

CIE **may**:

- Read authoritative projections via **Graph Service** and governed read adapters
- Emit **immutable intelligence artefacts** (recommendations, priorities, impact projections) as graph-indexed entities
- Propose operational follow-ups (work orders, reminders) **only through existing operational integration contracts** — never bypassing authority

---

## Position in the authority stack

```
┌─────────────────────────────────────────────────────────────────────┐
│ AUTHORITATIVE ENGINES (existing — unchanged)                        │
│ Compliance Engine · Rules Engine · Jurisdiction Engine              │
│ Requirements · Documents · CERs · Score Ledger · Outcome Engine     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ mutations emit decisions
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ COMPLIANCE EVIDENCE GRAPH (CEG) — accepted foundation               │
│ compliance_decisions · snapshots · nodes · edges                      │
│ Graph Service Layer — sole graph access interface                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ read-only consumption
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ COMPLIANCE INTELLIGENCE ENGINE (CIE) — THIS PROGRAMME               │
│ Priority · Recommendation · Decision Impact · Dependency              │
│ Portfolio · Regulatory Impact · Lifecycle                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ intelligence artefacts indexed in CEG
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ OPERATIONAL INTEGRATION (existing contracts)                        │
│ Work Orders · Reminders · Notifications · Digest · Reports        │
│ Operational Evidence Timeline · Decision Explorer                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ optional narration
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ AI INTELLIGENCE LAYER (Phase 5+) — consumer only                    │
│ Explains CIE + Graph Service envelopes · never calculates intel     │
└─────────────────────────────────────────────────────────────────────┘
```

**Operational Evidence Platform** runs parallel as the ops investigation layer. CIE links via `operational_correlation_id` and `trace_operational_impact()` — it does not duplicate ops authority.

---

## Relationship to Phase 5 AI layer

| Concern | Phase 5 `compliance_intelligence` | CIE (this programme) |
|---------|-----------------------------------|----------------------|
| Purpose | Grounded narration of Graph Service envelopes | Deterministic intelligence calculation |
| LLM | Optional Tier 2 when explicitly enabled | **Never** |
| Inputs | Graph Service methods | Graph Service + governed read projections |
| Outputs | `compliance_ai_narrations` audit trail | Recommendations, priorities, impact, dependencies |
| Authority | Never authoritative | Never authoritative — operational suggestions only |

Phase 5 `compliance_advisor` / `portfolio_intelligence` names in `AI_INTELLIGENCE_LAYER_ARCHITECTURE.md` are **renamed at consumption time**: those capabilities move to **CIE**; AI services **explain** their outputs.

---

## Core intelligence domains

Seven independent deterministic engines. Each is a bounded context with its own model document.

| # | Domain | Document | Primary question |
|---|--------|----------|------------------|
| 1 | Priority Engine | `PRIORITY_MODEL.md` | What matters most, and why? |
| 2 | Recommendation Engine | `RECOMMENDATION_MODEL.md` | What action should be taken? |
| 3 | Decision Impact Engine | `DECISION_IMPACT_MODEL.md` | What changes if this action completes? |
| 4 | Dependency Engine | `DEPENDENCY_MODEL.md` | What blocks this, and what is the critical path? |
| 5 | Portfolio Intelligence Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` | How healthy is the portfolio overall? |
| 6 | Regulatory Impact Engine | `REGULATORY_IMPACT_MODEL.md` | What breaks when rules change? |
| 7 | Recommendation Lifecycle | `RECOMMENDATION_LIFECYCLE.md` | How do recommendations progress immutably? |

Cross-cutting: `INTELLIGENCE_DOMAIN_MODEL.md` (shared vocabulary), `GRAPH_INTEGRATION_MODEL.md` (CEG indexing), `API_DESIGN.md` (public service surface).

---

## Inputs (read-only)

CIE consumes **only** from:

| Source | Access pattern |
|--------|----------------|
| Graph Service | `explain_decision`, `replay_decision`, `find_missing_evidence`, `trace_evidence`, `find_decision_dependencies`, `find_affected_*`, `trace_operational_impact`, `find_historical_decision` |
| Governed read adapters | Requirement rows, document metadata, CER status — **never** ad-hoc Mongo from consumers |
| Rules / jurisdiction version refs | From decision snapshots — not re-evaluated inside CIE |
| Operational Evidence | Correlation IDs and timeline summaries via OE bridge |

CIE **does not** import `services/compliance_evidence_graph.storage` directly (same boundary as AI layer).

---

## Outputs (immutable intelligence artefacts)

| Artefact | Nature | Graph role |
|----------|--------|------------|
| `compliance_intelligence_recommendations` | Immutable recommendation records | First-class graph entity |
| `compliance_intelligence_priorities` | Ranked action sets (versioned) | Derived view / snapshot |
| `compliance_intelligence_impact_projections` | Deterministic what-if deltas | Linked to recommendation |
| `compliance_intelligence_dependency_chains` | Materialised or computed chains | Traversal index |
| `compliance_intelligence_portfolio_snapshots` | Portfolio KPI bundles | Point-in-time intelligence |
| `compliance_intelligence_regulatory_impact_reports` | Rule-change blast radius | Event-triggered |

Every output record includes:

- `intelligence_engine_version`
- `inputs_hash` (canonical hash of upstream references)
- `response_hash` (deterministic output fingerprint)
- `source_decision_ids[]`
- `insufficient_evidence` when applicable

Lifecycle transitions emit **new** `compliance_decisions` with `decision_type=recommendation_lifecycle` (see `RECOMMENDATION_LIFECYCLE.md`).

---

## Explainability (no AI required)

Every recommendation and priority must answer deterministically:

| Question | Mechanism |
|----------|-----------|
| Why generated? | `generation_reason` + `source_decision_ids` + Graph `explain_decision` |
| Why highest priority? | `priority_score_breakdown` (weighted factors, all cited) |
| Why now? | `urgency_factors` (expiry proximity, risk delta, regulatory deadline) |
| What evidence supports it? | `evidence_set` pointers — same schema as decisions |
| Which regulation applies? | `applicable_legislation` from snapshot refs |
| If ignored? | `impact_if_ignored` projection (Decision Impact Engine) |
| If completed? | `impact_if_completed` projection |

`explain_recommendation()` composes these fields — no LLM.

---

## Operational integration (no duplication)

| System | Integration contract |
|--------|---------------------|
| Work Orders | Optional `work_order_id` on lifecycle transition; CIE never creates WO authority |
| Reminders | Reminder eligibility from priority + urgency; existing reminder service owns send |
| Notifications | Notification templates consume recommendation summary fields |
| Monthly Digest | `monthly_digest_operational_intelligence` reads CIE priority snapshot |
| Compliance Reports | Executive recommendations section cites `recommendation_id` + `decision_id` |
| OE Timeline | `operational_correlation_id` on recommendation generation decision |
| Decision Explorer | Graph Service `explain_decision` on recommendation's generation decision |
| Graph Service | CIE registers as **consumer**; intelligence emit as **producer** |

---

## Feature flag

```text
COMPLIANCE_INTELLIGENCE_ENGINE_MODE=disabled|shadow|enabled
```

| Mode | Behaviour |
|------|-----------|
| `disabled` (default) | No CIE execution; no intelligence emit |
| `shadow` | Compute + log + graph emit; **no** operational side-effects (WO/reminder creation) |
| `enabled` | Full intelligence + permitted operational integrations per sub-flag |

Independent of:

- `COMPLIANCE_EVIDENCE_GRAPH_MODE` — CIE requires graph `shadow|enabled`
- `COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED` — AI only; unrelated to CIE calculation

---

## Package layout (future implementation)

```text
services/compliance_intelligence_engine/
  config.py                 # feature flags, version
  orchestrator.py           # dispatch to domain engines
  priority/
  recommendation/
  decision_impact/
  dependency/
  portfolio/
  regulatory_impact/
  lifecycle/
  hashing.py                # inputs_hash, response_hash
  explain.py                # explain_recommendation composition
  graph_emit.py             # CEG producer adapter (intelligence artefacts)
  read_adapter.py           # governed reads + Graph Service client

routes/compliance_intelligence_engine.py   # admin HTTP (future)
```

**Not implemented in this programme slice.**

---

## Document index

| # | Deliverable | Path |
|---|-------------|------|
| 1 | Architecture (this document) | `COMPLIANCE_INTELLIGENCE_ENGINE_ARCHITECTURE.md` |
| 2 | Intelligence domain model | `INTELLIGENCE_DOMAIN_MODEL.md` |
| 3 | Recommendation model | `RECOMMENDATION_MODEL.md` |
| 4 | Recommendation lifecycle | `RECOMMENDATION_LIFECYCLE.md` |
| 5 | Dependency model | `DEPENDENCY_MODEL.md` |
| 6 | Priority model | `PRIORITY_MODEL.md` |
| 7 | Decision impact model | `DECISION_IMPACT_MODEL.md` |
| 8 | Portfolio intelligence model | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| 9 | Regulatory impact model | `REGULATORY_IMPACT_MODEL.md` |
| 10 | Graph integration model | `GRAPH_INTEGRATION_MODEL.md` |
| 11 | API design | `API_DESIGN.md` |
| 12 | Runtime validation plan | `RUNTIME_VALIDATION_PLAN.md` |
| 13 | Phased implementation roadmap | `PHASED_IMPLEMENTATION_ROADMAP.md` |

---

## Acceptance criteria (programme gate)

| Criterion | Validation |
|-----------|------------|
| Intelligence is deterministic | Same `inputs_hash` → same `response_hash` |
| Recommendations reproducible | Replay from snapshot refs |
| Every recommendation evidence-backed | `evidence_set` + `insufficient_evidence` gate |
| Every recommendation explainable | `explain_recommendation()` without LLM |
| Recommendations are immutable graph entities | CEG emit + `decision_type=recommendation` |
| Decision impact deterministic | Impact projection hash stable |
| Portfolio intelligence deterministic | Portfolio snapshot hash stable |
| Regulatory impact deterministic | Regulatory report hash stable |
| AI not required for any calculation | All runtime validation passes with `AI_ENABLED=false` |
| AI layer can consume without redesign | CIE envelopes match AI input contract in `AI_INTELLIGENCE_LAYER_ARCHITECTURE.md` |

---

## Explicitly out of scope (this programme)

- LLM integration, narration, conversation intelligence
- Customer-facing intelligence UI
- Predictive / scenario AI labelled services (deterministic scenario simulation may be a **future CIE extension** — not Phase 1)
- Production flag changes until staging acceptance per slice
- Modifying Compliance Engine, Rules Engine, or scoring formulas
