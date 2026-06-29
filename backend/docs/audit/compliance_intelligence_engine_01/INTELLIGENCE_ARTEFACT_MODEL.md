# Compliance Intelligence Artefact Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01

---

## Purpose

Define **Compliance Intelligence Artefact (CIA)** — the immutable parent entity for every deterministic output of the Compliance Intelligence Engine.

All domain engines (priority, recommendation, impact, dependency, portfolio, regulatory, commercial) **emit artefacts**. None emit standalone records outside this model.

---

## Parent entity

**Collection:** `compliance_intelligence_artefacts`  
**ID prefix:** `cia_`  
**Mutability:** Append-only. Updates → new artefact with `supersedes_artefact_id`.

### Base schema (all types)

```json
{
  "artefact_id": "cia_<uuid>",
  "artefact_type": "recommendation",
  "artefact_version": 1,
  "generated_at": "2026-06-02T12:00:00+00:00",
  "client_id": "uuid",
  "scope": {
    "property_id": "uuid | null",
    "requirement_id": "uuid | null",
    "portfolio_root": true
  },
  "engine_version": "cie-1.0.0",
  "template_version": "recommendation_templates_v1",
  "deterministic_version": "cie-deterministic-1.0.0",
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…",
  "source_decision_ids": ["dec_…"],
  "source_snapshot_ids": ["snap_…"],
  "source_graph_references": {
    "node_ids": ["ceg_…"],
    "edge_ids": ["cee_…"]
  },
  "confidence": {
    "score": 92,
    "label": "high",
    "factors": []
  },
  "operational_correlation_ids": ["corr_…"],
  "generation_decision_id": "dec_<uuid>",
  "lifecycle_state": "generated",
  "supersedes_artefact_id": null,
  "superseded_by_artefact_id": null,
  "insufficient_evidence": false,
  "insufficient_reason": null,
  "payload": { },
  "commercial": { },
  "explainability": {
    "why_exists": "Template-matched gap: evidence_expiring",
    "assumptions": [
      { "assumption_id": "assess_valid_if_renewed", "template_ref": "impact_rules_v1" }
    ]
  },
  "dedupe_key": "recommendation:renew_eicr:req_abc:2026-06-02",
  "environment": "staging",
  "build_sha": "f8da4fe5…"
}
```

### Required fields (acceptance)

| Field | Rule |
|-------|------|
| `artefact_id` | Server-generated; immutable |
| `artefact_type` | Registered enum (see § Types) |
| `engine_version` | CIE package version |
| `template_version` | Domain template registry version |
| `deterministic_version` | Cross-engine calculation contract version |
| `inputs_hash` | Canonical hash of all upstream inputs |
| `response_hash` | Canonical hash of full artefact (excl. `artefact_id`, `generated_at`) |
| `source_decision_ids` | ≥1 for non-insufficient artefacts |
| `generation_decision_id` | CEG decision for artefact creation |
| `lifecycle_state` | Current state pointer (denormalised; history authoritative) |
| `payload` | Type-specific body |

---

## Artefact type registry

Initial types (v1). New types register in `artefact_type_registry` without changing base schema.

| `artefact_type` | Produced by | Payload document |
|-----------------|-------------|------------------|
| `recommendation` | Recommendation Engine | `RECOMMENDATION_MODEL.md` |
| `priority_assessment` | Priority Engine | `PRIORITY_MODEL.md` |
| `decision_impact_assessment` | Decision Impact Engine | `DECISION_IMPACT_MODEL.md` |
| `dependency_chain` | Dependency Engine | `DEPENDENCY_MODEL.md` |
| `portfolio_insight` | Portfolio Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| `portfolio_risk_assessment` | Portfolio Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| `portfolio_readiness_assessment` | Portfolio Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| `regulatory_impact_assessment` | Regulatory Impact Engine | `REGULATORY_IMPACT_MODEL.md` |
| `forecast` | Forecast Engine (future slice) | Reserved |
| `workload_forecast` | Portfolio Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| `audit_readiness_assessment` | Readiness Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| `insurance_readiness_assessment` | Readiness Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| `compliance_trend` | Portfolio Engine | `PORTFOLIO_INTELLIGENCE_MODEL.md` |
| `operational_insight` | Dependency / OE bridge | `DEPENDENCY_MODEL.md` |
| `remediation_strategy` | Orchestrator composite | Multi-artefact bundle ref |

### Extension protocol

1. Add enum value + payload schema doc
2. Bump `deterministic_version` minor if calculation rules affected
3. Register Graph node subtype mapping
4. Add ISL method alias if needed (optional — `generate_intelligence(artefact_type=…)` may suffice)
5. No change to `compliance_intelligence_artefacts` base fields

---

## Subtype payload pattern

```json
{
  "artefact_type": "recommendation",
  "payload": {
    "subtype_schema_version": "1",
    "…": "type-specific fields"
  }
}
```

Legacy CIE-0 per-type collections (`compliance_intelligence_recommendations`, etc.) may exist as **materialised views** or **deprecated** in favour of unified storage — implementation choice in CIE-2; architecture mandates **CIA as canonical**.

---

## Relationship to compliance decisions

| Concept | Relationship |
|---------|--------------|
| Compliance assessment decision | **Upstream authority** — cited in `source_decision_ids` |
| Intelligence generation decision | **Emit event** — `generation_decision_id`; `decision_type=intelligence_artefact` |
| Lifecycle transition decision | **Emit event** — `decision_type=intelligence_lifecycle` |

CIE never creates `decision_type=compliance_assessment`.

---

## Supersession

When intelligence is regenerated:

1. New `cia_B` with `supersedes_artefact_id=cia_A`
2. Transition on `cia_A` → `superseded`
3. Graph edge `supersedes` between artefact nodes
4. Consumers use `list_intelligence(active_only=true)` or latest by `dedupe_key`

---

## Insufficient evidence artefact

Allowed artefact with `insufficient_evidence: true`, empty `payload`, and `source_decision_ids` explaining what was missing. Prevents silent empty responses.

---

## Hashing

```
inputs_hash = SHA256(canonical_json({
  artefact_type, scope, as_of, source_decision_ids, source_snapshot_ids,
  template_version, deterministic_version, engine_version, upstream_envelope_hashes
}))

response_hash = SHA256(canonical_json(artefact excluding artefact_id, generated_at))
```

Same inputs → same hashes across runs.
