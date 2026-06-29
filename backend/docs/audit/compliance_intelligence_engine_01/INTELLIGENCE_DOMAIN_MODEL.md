# Intelligence Domain Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Purpose

Define shared vocabulary, bounded contexts, and cross-domain contracts for the seven deterministic intelligence engines.

---

## Bounded contexts

```
┌─────────────────────────────────────────────────────────────────┐
│                    CIE ORCHESTRATOR                              │
│  resolve scope · load graph context · dispatch · emit · hash      │
└────┬────────┬────────┬────────┬────────┬────────┬──────────────┘
     │        │        │        │        │        │
     ▼        ▼        ▼        ▼        ▼        ▼
 Priority  Recommend  Impact  Depend   Portfolio  Regulatory
 Engine    Engine     Engine  Engine   Engine     Engine
     │        │        │        │        │        │
     └────────┴────────┴────┬───┴────────┴────────┘
                            ▼
                   Lifecycle Engine
                            │
                            ▼
                   Graph Emit Adapter
```

Each engine:

- Accepts a **scoped context** (`client_id`, optional `property_id`, `requirement_id`, `as_of`)
- Returns a **deterministic envelope** with `response_hash`
- Never calls another engine mutably — orchestrator composes pipelines
- Declares `insufficient_evidence` when upstream data cannot support output

---

## Shared types

### IntelligenceScope

```json
{
  "client_id": "uuid",
  "property_id": "uuid | null",
  "requirement_id": "uuid | null",
  "portfolio_root": true,
  "as_of": "2026-06-02T12:00:00+00:00 | null",
  "correlation_id": "uuid | null"
}
```

`as_of` null → current intelligence run timestamp (recorded, not mutable state reads for compliance facts).

### IntelligenceEnvelope (base)

```json
{
  "service": "generate_recommendations",
  "engine_version": "cie-1.0.0",
  "insufficient_evidence": false,
  "insufficient_reason": null,
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…",
  "generated_at": "2026-06-02T12:00:00+00:00",
  "scope": { },
  "authoritative_references": {
    "decision_ids": [],
    "snapshot_ids": [],
    "requirement_ids": [],
    "document_ids": [],
    "rule_version_ids": []
  },
  "confidence_metadata": {
    "label": "high | medium | low | insufficient",
    "score": 0,
    "factors": []
  },
  "payload": { }
}
```

### EvidenceReference

Aligned with CEG decision `evidence_set`:

```json
{
  "evidence_type": "document | cer | review | decision | operational_event",
  "source_collection": "documents",
  "source_id": "doc_abc",
  "decision_id": "dec_… | null",
  "summary": "Gas Safety certificate expires 2026-07-01",
  "occurred_at": "2026-01-15T00:00:00+00:00",
  "expiry_at": "2026-07-01T00:00:00+00:00 | null"
}
```

### RuleLegislationRef

Always from decision snapshots — never re-parsed by CIE:

```json
{
  "governed_rule_version_id": "gov_v12",
  "requirement_rule_id": "rule_gas_safety",
  "legislation_refs": [
    { "legislation_id": "gas_safety_regs_1998", "version": "1998-amendment-2018" }
  ]
}
```

### PriorityFactor

```json
{
  "factor_id": "expiry_proximity",
  "weight": 0.35,
  "raw_score": 85,
  "weighted_score": 29.75,
  "reason": "Certificate expires in 28 days",
  "evidence_refs": [],
  "decision_ids": ["dec_…"]
}
```

---

## Domain responsibilities

| Domain | Owns | Does not own |
|--------|------|--------------|
| **Priority** | Ranking formulas, urgency weights, portfolio/property ordering | Compliance status determination |
| **Recommendation** | Action templates, generation rules, recommendation records | Work order execution |
| **Decision Impact** | Deterministic delta projections on known models | Score recalculation |
| **Dependency** | Prerequisite graphs, blocked detection, critical path | Requirement applicability rules |
| **Portfolio** | Aggregated health, velocity, workload metrics | Portfolio mutation |
| **Regulatory Impact** | Blast-radius analysis on rule version change events | Rule authoring |
| **Lifecycle** | State transition records, supersession | Recommendation content edits |

---

## Orchestration pipelines

### Pipeline A — Generate and prioritise recommendations

```
1. Graph Service: find_missing_evidence(scope)
2. Graph Service: find_historical_decision(scope) — recent assessments
3. Recommendation Engine: generate_recommendations(context)
4. Dependency Engine: attach prerequisites per recommendation
5. Decision Impact Engine: project impact_if_completed / impact_if_ignored
6. Priority Engine: prioritise_actions(recommendations)
7. Graph Emit: index recommendations + generation decision
```

### Pipeline B — Explain existing recommendation

```
1. Load recommendation record by recommendation_id
2. Graph Service: explain_decision(generation_decision_id)
3. Lifecycle Engine: transition history
4. explain_recommendation() composes static fields + graph envelope
```

### Pipeline C — Regulatory change

```
1. Input: rule_version_change_event (from Rules Engine emit — not CIE authority)
2. Regulatory Impact Engine: calculate_regulatory_impact(change)
3. Recommendation Engine: generate_remediation_recommendations (deterministic templates)
4. Portfolio Engine: forecast_workload(impact)
5. Graph Emit: regulatory impact report + recommendations
```

---

## Determinism contract

1. **Version pinning** — `engine_version` + `priority_weights_version` + `recommendation_templates_version` in every envelope
2. **Canonical serialization** — `inputs_hash` from sorted JSON of all upstream refs (decision IDs, snapshot fields used, template IDs)
3. **No randomness** — no UUID generation inside calculation paths (IDs assigned at emit time only)
4. **No clock dependency in scoring** — `as_of` passed explicitly; wall clock only for `generated_at` metadata
5. **Shadow mode** — identical calculation in shadow and enabled; shadow skips operational side-effects

---

## Insufficient evidence policy

CIE returns `insufficient_evidence: true` when:

- Graph Service returns insufficient for a required method
- No applicable decision snapshot for the scoped requirement
- Conflicting evidence flagged in `decision_quality` without resolution decision
- Dependency chain cannot be resolved to authoritative nodes

Never interpolate, assume, or use LLM to fill gaps.

---

## AI consumption contract (future)

AI services receive **CIE envelopes** plus optional Graph Service `explain_decision` payloads. Allowed AI actions:

- Rephrase `generation_reason`, `priority_score_breakdown` labels
- Summarise portfolio snapshot numbers
- Translate to natural language

Forbidden:

- Adding recommendations not in `payload.recommendations[]`
- Changing priority order
- Inventing impact numbers

Every AI paragraph maps to `authoritative_references.recommendation_ids[]` or `decision_ids[]`.

---

## Mapping to existing platform concepts

| Existing concept | CIE mapping |
|------------------|-------------|
| `maintenance_service.recommendation_id` | Foreign key to `compliance_intelligence_recommendations` |
| `monthly_digest_operational_intelligence` | Consumes `prioritise_actions()` snapshot |
| `report_compliance_summary_executive` | Consumes grouped recommendations by priority band |
| `DECISION_RECOMMENDATION` (CEG constant) | Generation decision type for new recommendations |
| Phase 5 `investigate()` | Dispatches to Graph Service; **does not** replace CIE |
