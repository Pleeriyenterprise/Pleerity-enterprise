# Compliance Intelligence Engine — API Design

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01

---

## Principles

1. **Intelligence Service Layer is canonical** — HTTP routes wrap ISL only
2. **Deterministic envelopes** — every method returns artefact envelope + `response_hash`
3. **Graph Service read boundary** — CIE/ISL use Graph Service for decision lineage; consumers never touch graph storage
4. **No direct intelligence storage access** — same rule as CEG
5. **Tenant scoped** — `client_id` enforced server-side
6. **AI-ready** — envelopes include `authoritative_references` + optional `graph_service_response_hash`

See `INTELLIGENCE_SERVICE_LAYER.md` for architecture.

---

## Intelligence Service Layer API (canonical)

**Package:** `services/compliance_intelligence_service/` (future)

### Generation

```python
async def generate_intelligence(
    *,
    artefact_type: str,
    scope: IntelligenceScope,
    actor: ActorContext,
    params: dict | None = None,
) -> IntelligenceEnvelope:
    """Generic dispatcher to CIE orchestrator."""


async def generate_recommendations(
    *, scope: IntelligenceScope, actor: ActorContext
) -> IntelligenceEnvelope:
    """artefact_type=recommendation pipeline."""


async def generate_portfolio_insights(
    *, client_id: str, actor: ActorContext, as_of: str | None = None
) -> IntelligenceEnvelope:
    """portfolio_insight + related types."""


async def generate_decision_impact(
    *, artefact_id: str | None, scope: IntelligenceScope, actor: ActorContext
) -> IntelligenceEnvelope:
    """decision_impact_assessment."""


async def generate_regulatory_impact(
    *, rule_change_event: dict, actor: ActorContext
) -> IntelligenceEnvelope:
    """regulatory_impact_assessment."""


async def generate_forecast(
    *, client_id: str, window_days: int, actor: ActorContext
) -> IntelligenceEnvelope:
    """forecast | workload_forecast (deterministic)."""


async def generate_readiness(
    *, scope: IntelligenceScope, kind: str, actor: ActorContext
) -> IntelligenceEnvelope:
    """audit_readiness_assessment | insurance_readiness_assessment."""


async def generate_dependency_chain(
    *, anchor_type: str, anchor_id: str, client_id: str, actor: ActorContext
) -> IntelligenceEnvelope:
    """dependency_chain."""


async def generate_remediation_strategy(
    *, scope: IntelligenceScope, actor: ActorContext
) -> IntelligenceEnvelope:
    """remediation_strategy composite."""
```

### Query and explain

```python
async def list_intelligence(
    *,
    scope: IntelligenceScope,
    actor: ActorContext,
    artefact_type: str | None = None,
    lifecycle_state: str | None = None,
    active_only: bool = True,
) -> IntelligenceEnvelope:
    """Filtered artefact list."""


async def get_intelligence(
    *, artefact_id: str, actor: ActorContext
) -> IntelligenceEnvelope:
    """Single artefact."""


async def compare_intelligence(
    *, left_id: str, right_id: str, actor: ActorContext
) -> IntelligenceEnvelope:
    """Structural diff."""


async def explain_intelligence(
    *, artefact_id: str, actor: ActorContext
) -> IntelligenceEnvelope:
    """Deterministic explanation — any artefact type."""


async def get_intelligence_lifecycle(
    *, artefact_id: str, actor: ActorContext
) -> IntelligenceEnvelope:
    """Transition history."""


async def transition_intelligence(
    *,
    artefact_id: str,
    to_state: str,
    actor: ActorContext,
    reason_code: str,
    reason_summary: str | None = None,
) -> IntelligenceEnvelope:
    """Immutable lifecycle transition."""
```

### Backward-compatible aliases (CIE-0 names)

| CIE-0 name | ISL equivalent |
|------------|----------------|
| `prioritise_actions()` | `generate_intelligence(artefact_type=priority_assessment)` or `list` + sort |
| `calculate_decision_impact()` | `generate_decision_impact()` |
| `find_dependency_chain()` | `generate_dependency_chain()` |
| `explain_recommendation()` | `explain_intelligence(artefact_id)` |
| `compare_recommendations()` | `compare_intelligence()` |
| `forecast_workload()` | `generate_forecast()` |
| `calculate_readiness()` | `generate_readiness()` |
| `calculate_portfolio_intelligence()` | `generate_portfolio_insights()` |

---

## HTTP API (admin — future)

**Router:** `routes/compliance_intelligence_engine.py`  
**Prefix:** `/api/admin/compliance/intelligence-engine/` (distinct from Phase 5 `/intelligence/investigate`)

| Method | Path | ISL method |
|--------|------|------------|
| POST | `/generate` | `generate_intelligence` |
| POST | `/recommendations/generate` | `generate_recommendations` |
| GET | `/artefacts` | `list_intelligence` |
| GET | `/artefacts/{id}` | `get_intelligence` |
| GET | `/artefacts/{id}/explain` | `explain_intelligence` |
| GET | `/artefacts/{id}/lifecycle` | `get_intelligence_lifecycle` |
| POST | `/artefacts/{id}/transition` | `transition_intelligence` |
| POST | `/compare` | `compare_intelligence` |
| GET | `/portfolio/insights` | `generate_portfolio_insights` |
| GET | `/portfolio/workload` | `generate_forecast` |
| GET | `/readiness` | `generate_readiness` |

---

## Response envelope

```json
{
  "service": "explain_intelligence",
  "enabled": true,
  "insufficient_evidence": false,
  "artefact_id": "cia_…",
  "artefact_type": "recommendation",
  "response_hash": "sha256:…",
  "inputs_hash": "sha256:…",
  "artefacts": [],
  "tier1": { },
  "authoritative_references": {
    "artefact_ids": ["cia_…"],
    "decision_ids": ["dec_…"],
    "snapshot_ids": ["snap_…"]
  },
  "graph_service_response_hash": null,
  "tier2": null
}
```

---

## Feature flag

```text
COMPLIANCE_INTELLIGENCE_ENGINE_MODE=disabled|shadow|enabled
```

---

## AI consumer mapping

AI calls **ISL** `explain_intelligence` / `list_intelligence` — never `generate_*` except via explicit audited admin regeneration.

See `INTELLIGENCE_CONSUMERS.md` for advisor mapping.

---

## CIE internal package

`services/compliance_intelligence_engine/` — domain engines, orchestrator, storage write, graph_emit. **Not imported by routes or AI.**
