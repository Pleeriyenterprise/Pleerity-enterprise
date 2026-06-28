# AI Intelligence Layer Architecture (Refined)

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-ARCHITECTURE-REFINEMENT-01

---

## Core rule

> The AI consumes Graph Service responses. It never queries graph storage. It never becomes the source of truth.

```
Authoritative Facts
        ↓
Compliance Decision + Snapshot
        ↓
Graph Service Layer  ←── AI calls ONLY this layer
        ↓
AI Intelligence Layer (Phase 5+)
```

If Graph Service returns `insufficient_evidence: true`, the AI layer **must not** fill gaps.

**Phase 1–4: No AI implementation.** Graph Service envelopes are AI-ready by design.

---

## Access boundary (enforced)

| Allowed | Forbidden |
|---------|-----------|
| `from services.compliance_graph_service import …` | `from services.compliance_evidence_graph.storage import …` |
| Graph Service response envelopes | Direct Mongo collection queries |
| Governed rule text fetch by ID from envelope refs | LLM parametric "knowledge" of regulations |

`test_graph_service_access_boundary.py` validates intelligence package imports.

---

## Two-tier explanation model

| Tier | Engine | When used | LLM |
|------|--------|-----------|-----|
| **Tier 1 — Deterministic** | Graph Service (`explain_decision`, `replay_decision`, `compare_decision`, `trace_*`) | Always; audits; regulators; customers (default) | Never |
| **Tier 2 — Narration** | `compliance_intelligence/*` | Optional readable narrative | Optional; grounded |

Tier 2 receives Tier 1 Graph Service envelope as **immutable input**. LLM may rephrase but not add claims absent from envelope `decision_reasoning` / `authoritative_references`.

---

## Graph Service envelope fields (AI input contract)

Every AI service receives a Graph Service response containing:

| Field | AI usage |
|-------|----------|
| `authoritative_references` | Mandatory citation source |
| `evidence_lineage` | Evidence chain narration |
| `decision_lineage` | Supersession / history narration |
| `confidence_metadata` | Uncertainty communication |
| `applicable_legislation` | Regulatory narration |
| `applicable_rules` | Rule explanation |
| `historical_references` | Past-tense questions (snapshot-bound) |
| `operational_references` | Ops impact narration (via OE bridge) |
| `insufficient_evidence` | Hard stop — no speculation |

---

## Service catalogue (Phase 5+)

All services dispatch to Graph Service methods first:

| Service | Graph Service calls | Output |
|---------|---------------------|--------|
| `evidence_ai` | `trace_evidence()` | Evidence quality narrative |
| `compliance_advisor` | `find_missing_evidence()`, `explain_decision()` | Prioritised actions |
| `regulation_interpreter` | `explain_decision()` + rule refs from snapshot | Applicability explanation |
| `operations_ai` | `trace_operational_impact()` | Ops narrative |
| `portfolio_intelligence` | `find_affected_properties()`, `find_historical_decision()` | Portfolio summary |
| `predictive_intelligence` | Historical decision chains | Forecasts labelled `prediction: true` |
| `scenario_intelligence` | `compare_decision()` on dry-run branch | What-if diff; `scenario: true` |
| `conversation_intelligence` | Intent → Graph Service method dispatch | NL answer |

---

## Conversation intelligence pipeline

1. Parse intent → Graph Service method + parameters
2. Call Graph Service (never storage)
3. If `insufficient_evidence` → return explicit message
4. If narration requested → LLM receives Graph Service JSON only
5. Post-validate: every paragraph maps to `authoritative_references`
6. Store `compliance_ai_narrations` with `graph_service_response_hash`

---

## LLM prompt contract

```
SYSTEM: You are an evidence interpreter. Only state facts present in GRAPH_SERVICE_RESPONSE.
Every claim must map to authoritative_references. If uncertain, say "Insufficient evidence available."

GRAPH_SERVICE_RESPONSE: { ... full envelope ... }
USER_QUESTION: { ... }
```

**Response schema:**

```json
{
  "paragraphs": [
    {
      "text": "…",
      "authoritative_references": { "decision_id": "…", "node_ids": [], "snapshot_fields": [] },
      "confidence": 90
    }
  ],
  "insufficient_evidence": false,
  "graph_service_response_hash": "sha256:…"
}
```

---

## Anti-fabrication controls

| Control | Implementation |
|---------|----------------|
| No direct storage access | Import lint + CI test |
| Citation required | Schema validation on `authoritative_references` |
| No invent legislation | Legislation from snapshot only |
| No invent timelines | `timeline[]` from Graph Service replay only |
| No invent customer actions | `user_action` refs from envelope only |
| No score override | AI output cannot include `new_score` |
| Historical integrity | `historical_references.snapshot_id` required for past-tense |
| Audit reproducibility | `graph_service_response_hash` + `prompt_version` + `model_id` |

---

## Customer-facing AI policy

| Role | Default tier |
|------|--------------|
| Landlord / agent | Tier 1 only (deterministic Graph Service) |
| Inspector / auditor | Tier 1; optional Tier 2 with flag |
| Admin | Tier 1 + optional Tier 2 narration |
| API external | Tier 1 only unless contract enables Tier 2 |

---

## Future capabilities (no AI redesign required)

| Capability | Graph Service foundation | AI role (optional) |
|------------|-------------------------|-------------------|
| Explain This | `explain_decision()` | Narrate envelope |
| Compliance Replay | `replay_decision()` | Narrate timeline |
| Decision Diff | `compare_decision()` | Summarise diff |
| Root Cause Analysis | `find_decision_dependencies()` + `trace_operational_impact()` | Narrate traversal |
| Regulatory Change Impact | `compare_decision_snapshots()` across rule versions | Summarise impact |
| NL Search | Intent → Graph Service dispatch | Format results |

---

## Acceptance tests (Phase 5)

1. Intelligence module import scan — no storage imports
2. Empty Graph Service response → "Insufficient evidence available."
3. LLM adds uncited claim → post-validator strips
4. Same Graph Service response hash → Tier 1 identical; Tier 2 may vary
5. Tenant A envelope never in Tenant B session
6. Historical question without snapshot → insufficient evidence (no current-state fallback)
