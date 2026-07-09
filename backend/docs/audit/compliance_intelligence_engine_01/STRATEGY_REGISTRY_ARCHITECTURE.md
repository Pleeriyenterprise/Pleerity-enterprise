# Strategy Registry Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02

---

## Purpose

Define the **Strategy Registry** — the versioned catalogue of immutable deterministic algorithms used by CIE domain engines.

Strategies are **never embedded opaquely** inside engine code paths. Every calculation pins explicit strategy versions in provenance.

---

## Design principles

| Principle | Rule |
|-----------|------|
| Immutability | Published strategy versions are never modified |
| Independent versioning | Each strategy family versions independently |
| Registration | New engines register through the same registry contract |
| Traceability | Provenance records `*_strategy_version` for each family used |
| Substitution | Changing strategy version → new provenance → new artefact |

---

## Registry structure

```
Strategy Registry
├── recommendation_strategies/
│   └── rec_strategy_v1.0.0
├── priority_strategies/
│   └── priority_strategy_v1.0.0
├── dependency_strategies/
├── impact_strategies/
├── portfolio_strategies/
├── regulatory_strategies/
├── forecast_strategies/
└── commercial_strategies/
```

**Collection (implementation):** `compliance_intelligence_strategy_registry`  
**ID pattern:** `{family}_{semantic_version}` e.g. `rec_strategy_v1.0.0`

---

## Strategy document schema

```json
{
  "strategy_id": "rec_strategy_v1.0.0",
  "strategy_family": "recommendation",
  "semantic_version": "1.0.0",
  "published_at": "2026-06-01T00:00:00+00:00",
  "status": "active",
  "supersedes_strategy_id": null,
  "engine_version_min": "cie-2.0.0",
  "engine_version_max": null,
  "description": "Template-matched gap recommendations v1",
  "algorithm_ref": "services/compliance_intelligence_engine/engines/recommendation/strategy_v1.py",
  "template_version_binding": "recommendation_templates_v1",
  "constraint_set_binding": "constraints_v1.0.0",
  "weight_set_binding": "weights_v1.2.0",
  "parameters_schema": {},
  "default_parameters": {},
  "content_hash": "sha256:…"
}
```

---

## Strategy families

| Family | Key | Used by |
|--------|-----|---------|
| Recommendation | `recommendation_strategy_version` | Recommendation Engine |
| Priority | `priority_strategy_version` | Priority Engine |
| Dependency | `dependency_strategy_version` | Dependency Engine |
| Impact | `impact_strategy_version` | Decision Impact Engine |
| Portfolio | `portfolio_strategy_version` | Portfolio Engine |
| Regulatory | `regulatory_strategy_version` | Regulatory Impact Engine |
| Forecast | `forecast_strategy_version` | Forecast Engine |
| Commercial | `commercial_strategy_version` | Commercial Intelligence |

Future optimisation engines (ML-assisted deterministic scoring, A/B experiments) register as new strategy versions within existing or new families.

---

## Resolution at runtime

```
1. Orchestrator receives generate request (artefact_type, scope, as_of)
2. Strategy resolver selects active strategy version for:
   - artefact_type
   - client scope (optional client override — see § Scoped strategies)
   - jurisdiction (optional)
   - as_of timestamp (latest published ≤ as_of)
3. Resolved strategy_id pinned in provenance before calculation begins
4. Calculation trace records strategy_id per stage
```

**No silent upgrades:** If a newer strategy is published mid-day, artefacts generated before publication retain their original strategy version via provenance.

---

## Scoped strategies

Support without schema redesign:

| Scope | Example |
|-------|---------|
| Global default | `rec_strategy_v1.0.0` |
| Jurisdiction override | `rec_strategy_v1.1.0-england` |
| Portfolio override | `priority_strategy_v2.0.0-portfolio_abc` |
| Customer override | `commercial_strategy_v1.0.0-client_xyz` |

Scoped strategies are separate immutable registry entries — not runtime parameter mutation.

---

## Experimental and A/B strategies

| Pattern | Architecture |
|---------|--------------|
| A/B validation | Parallel generation under two strategy versions; separate provenance per artefact; comparison via `compare_intelligence` |
| Experimental flag | `status: experimental` in registry; gated by `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=shadow` |
| Promotion | New strategy version published; old version `status: deprecated` — historical provenance unchanged |

---

## Relationship to templates

`template_version` on CIA and `template_version_binding` on strategy are related but distinct:

| Concept | Role |
|---------|------|
| Template registry | Data templates (gap types, impact rules, message patterns) |
| Strategy registry | Algorithm that applies templates |

A strategy version binds to a template version range. Provenance records both.

---

## Governance

| Action | Authority |
|--------|-----------|
| Publish new strategy version | Admin governance (future); staging test required |
| Deprecate strategy | Registry status change only — no deletion |
| Emergency rollback | Publish previous version as new entry; do not mutate history |

---

## CIE-2 implication

Priority and Recommendation engines in CIE-2 **must** resolve strategies from registry before emitting artefacts. Hard-coded algorithm selection without registry pin is **non-compliant** with Refinement-02.
