# Compliance Intelligence Engine — Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02 (provenance)  
**Status:** Architecture refined — CIE-1 implemented; provenance refinement documented  
**Prerequisite:** CIE-0 committed (`f8da4fe5`); CEG Phase 5 Tier 1 accepted

---

## Executive summary

The **Compliance Intelligence Engine (CIE)** transforms authoritative compliance history into **prioritised, evidence-backed, deterministic operational intelligence**, represented as immutable **Compliance Intelligence Artefacts (CIA)**.

This is **not an AI programme**. It is a **Compliance Operations Intelligence Platform** programme. Recommendations are one artefact subtype among many (portfolio insights, impact assessments, forecasts, readiness, regulatory blast radius). The **Intelligence Service Layer** is the sole consumer interface. The **AI Intelligence Layer** explains artefact envelopes — never creating them.

CIE answers **"What should happen next?"** while remaining:

- **Deterministic** — same inputs + engine version → same outputs (hashable)
- **Explainable** — every output cites decisions, evidence, rules, legislation
- **Auditable** — immutable records + graph lineage
- **Reproducible** — replay from snapshots, registries, and provenance — not mutable state
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
- Emit **immutable Compliance Intelligence Artefacts** indexed in CEG
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
│ COMPLIANCE INTELLIGENCE ENGINE (CIE) — calculation                  │
│ Domain engines → Compliance Intelligence Artefacts                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ internal storage
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ INTELLIGENCE SERVICE LAYER — sole consumer API                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ OPERATIONAL INTEGRATION · Dashboards · Reports · Digest · AI       │
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
| Outputs | `compliance_ai_narrations` audit trail | **Compliance Intelligence Artefacts** via ISL |
| Authority | Never authoritative | Never authoritative — operational suggestions only |

Phase 5 `compliance_advisor` / `portfolio_intelligence` names in `AI_INTELLIGENCE_LAYER_ARCHITECTURE.md` are **renamed at consumption time**: those capabilities move to **CIE**; AI services **explain** their outputs.

---

## Core intelligence domains

Seven deterministic engines plus commercial extension. Each emits **typed Compliance Intelligence Artefacts**.

| # | Domain | Document | Artefact type(s) |
|---|--------|----------|------------------|
| 1 | Priority Engine | `PRIORITY_MODEL.md` | `priority_assessment` |
| 2 | Recommendation Engine | `RECOMMENDATION_MODEL.md` | `recommendation` |
| 3 | Decision Impact Engine | `DECISION_IMPACT_MODEL.md` | `decision_impact_assessment` |
| 4 | Dependency Engine | `DEPENDENCY_MODEL.md` | `dependency_chain`, `operational_insight` |
| 5 | Portfolio Intelligence Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` | `portfolio_insight`, `portfolio_risk_assessment`, `portfolio_readiness_assessment`, `compliance_trend`, `workload_forecast` |
| 6 | Regulatory Impact Engine | `REGULATORY_IMPACT_MODEL.md` | `regulatory_impact_assessment` |
| 7 | Lifecycle | `INTELLIGENCE_LIFECYCLE_MODEL.md` | transitions on all types |
| — | Commercial | `COMMERCIAL_INTELLIGENCE_MODEL.md` | `commercial` block on artefacts |

**Parent entity:** `INTELLIGENCE_ARTEFACT_MODEL.md`  
**Consumer API:** `INTELLIGENCE_SERVICE_LAYER.md`  
**Consumers:** `INTELLIGENCE_CONSUMERS.md`

Cross-cutting: `INTELLIGENCE_DOMAIN_MODEL.md`, `GRAPH_INTEGRATION_MODEL.md`, `API_DESIGN.md`.

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

## Outputs (Compliance Intelligence Artefacts)

**Canonical collection:** `compliance_intelligence_artefacts`  
See `INTELLIGENCE_ARTEFACT_MODEL.md` for base schema and type registry.

| Artefact type | Domain |
|---------------|--------|
| `recommendation` | Recommendation Engine |
| `priority_assessment` | Priority Engine |
| `decision_impact_assessment` | Decision Impact Engine |
| `dependency_chain` | Dependency Engine |
| `portfolio_insight`, `portfolio_risk_assessment`, `portfolio_readiness_assessment`, `compliance_trend`, `workload_forecast` | Portfolio Engine |
| `regulatory_impact_assessment` | Regulatory Impact Engine |
| `audit_readiness_assessment`, `insurance_readiness_assessment` | Readiness |
| `forecast`, `operational_insight`, `remediation_strategy` | Composite / future slices |

Every artefact includes: `provenance_id`, `engine_version`, `template_version`, `deterministic_version`, `inputs_hash`, `response_hash`, `source_decision_ids`, `source_snapshot_ids`, `source_graph_references`, `confidence`, `lifecycle_state`, `operational_correlation_ids`.

**Provenance (Refinement-02):** Every artefact references exactly one immutable `compliance_intelligence_provenance` record (`cip_*`) — see `INTELLIGENCE_PROVENANCE_ARCHITECTURE.md`.

Lifecycle transitions emit `decision_type=intelligence_lifecycle` (see `INTELLIGENCE_LIFECYCLE_MODEL.md`).

---

## Explainability (no AI required)

`explain_intelligence(artefact_id)` answers for **any artefact type**:

| Question | Mechanism |
|----------|-----------|
| Why does it exist? | `explainability.why_exists` + `source_decision_ids` |
| Which decisions generated it? | `source_decision_ids`, `generation_decision_id` |
| What evidence supports it? | `payload.evidence` or linked refs |
| Which legislation / rules apply? | `applicable_legislation`, `applicable_rules` in payload |
| What dependencies exist? | Linked `dependency_chain` artefact refs |
| What outcomes are calculated? | Linked `decision_impact_assessment` refs |
| What assumptions are deterministic? | `explainability.assumptions[]` |
| How was it calculated? | `provenance_id` → full calculation trace (Refinement-02) |
| Why did it change vs predecessor? | `compare_intelligence()` provenance diff |

Subtype shortcuts: `explain_recommendation()` → `explain_intelligence` filter.

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
services/compliance_intelligence_engine/   # calculation + storage write
services/compliance_intelligence_service/  # Intelligence Service Layer (consumer API)
  artefact_registry.py
  service.py              # generate_*, list_*, explain_*, compare_*
  envelopes.py
  access.py               # tenant boundary

routes/compliance_intelligence_engine.py   # admin HTTP (future; ISL wrapper)
```

**Not implemented in this programme slice.**

---

## Document index

| Document | Path |
|----------|------|
| Architecture (this document) | `COMPLIANCE_INTELLIGENCE_ENGINE_ARCHITECTURE.md` |
| Refinement summary | `ARCHITECTURE_REFINEMENT_01.md` |
| Intelligence artefact model | `INTELLIGENCE_ARTEFACT_MODEL.md` |
| Intelligence Service Layer | `INTELLIGENCE_SERVICE_LAYER.md` |
| Intelligence lifecycle | `INTELLIGENCE_LIFECYCLE_MODEL.md` |
| Intelligence consumers | `INTELLIGENCE_CONSUMERS.md` |
| Commercial intelligence | `COMMERCIAL_INTELLIGENCE_MODEL.md` |
| Intelligence domain model | `INTELLIGENCE_DOMAIN_MODEL.md` |
| Recommendation model (subtype) | `RECOMMENDATION_MODEL.md` |
| Recommendation lifecycle (extension) | `RECOMMENDATION_LIFECYCLE.md` |
| Dependency / Priority / Impact / Portfolio / Regulatory | respective `*_MODEL.md` |
| Graph integration | `GRAPH_INTEGRATION_MODEL.md` |
| API design | `API_DESIGN.md` |
| Runtime validation | `RUNTIME_VALIDATION_PLAN.md` |
| Implementation roadmap | `PHASED_IMPLEMENTATION_ROADMAP.md` |

---

## Acceptance criteria (programme gate)

| Criterion | Validation |
|-----------|------------|
| Compliance Intelligence Artefacts are primary entity | `INTELLIGENCE_ARTEFACT_MODEL.md` |
| Recommendations are one subtype | `RECOMMENDATION_MODEL.md` |
| Future types addable without redesign | Artefact type registry |
| Intelligence is deterministic | Same `inputs_hash` → same `response_hash` |
| Intelligence reproducible | Replay from snapshot refs |
| Evidence-backed | `source_decision_ids` + insufficient gate |
| Explainable without AI | `explain_intelligence()` |
| CEG integration | `GRAPH_INTEGRATION_MODEL.md` |
| AI is consumer not producer | `INTELLIGENCE_CONSUMERS.md` |
| Future operational/commercial intel without redesign | ISL + artefact extension protocol |

---

## Explicitly out of scope (this programme)

- LLM integration, narration, conversation intelligence
- Customer-facing intelligence UI
- Predictive / scenario AI labelled services (deterministic scenario simulation may be a **future CIE extension** — not Phase 1)
- Production flag changes until staging acceptance per slice
- Modifying Compliance Engine, Rules Engine, or scoring formulas
