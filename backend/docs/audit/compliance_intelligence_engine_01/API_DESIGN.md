# Compliance Intelligence Engine — API Design

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Principles

1. **Service-first** — Python service API is canonical; HTTP is admin wrapper
2. **Deterministic envelopes** — every method returns `IntelligenceEnvelope` + `response_hash`
3. **Graph Service read boundary** — no direct graph storage access
4. **Tenant scoped** — `client_id` enforced server-side; portal actors cannot cross-tenant
5. **Admin vs portal** — portfolio methods available to both; cross-portfolio admin only for admin actors
6. **AI-ready** — envelopes include `authoritative_references` for future narration consumers

---

## Package API (canonical)

**Package:** `services/compliance_intelligence_engine/` (future)

### Core methods

```python
async def generate_recommendations(
    *,
    scope: IntelligenceScope,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Pipeline A: recommendations + dependencies + impact + priority."""


async def prioritise_actions(
    *,
    scope: IntelligenceScope,
    actor: ActorContext,
    recommendation_ids: list[str] | None = None,
) -> IntelligenceEnvelope:
    """Rank recommendations and/or open gaps."""


async def calculate_decision_impact(
    *,
    recommendation_id: str,
    actor: ActorContext,
    projection_types: list[str] = ("if_completed", "if_ignored"),
) -> IntelligenceEnvelope:
    """Impact projections for a recommendation."""


async def calculate_portfolio_impact(
    *,
    client_id: str,
    recommendation_ids: list[str],
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Aggregate impact if recommendation set completed."""


async def find_dependency_chain(
    *,
    anchor_type: str,
    anchor_id: str,
    client_id: str,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Dependency chain + root cause + critical path."""


async def calculate_regulatory_impact(
    *,
    rule_change_event: dict,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Blast radius report for rule version change."""


async def explain_recommendation(
    *,
    recommendation_id: str,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Deterministic explanation — no LLM."""


async def compare_recommendations(
    *,
    left_id: str,
    right_id: str,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Structural diff between recommendations."""


async def forecast_workload(
    *,
    client_id: str,
    window_days: int,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Deterministic workload forecast."""


async def calculate_readiness(
    *,
    scope: IntelligenceScope,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Evidence / insurance / audit readiness bundle."""


async def calculate_portfolio_intelligence(
    *,
    client_id: str,
    actor: ActorContext,
    as_of: str | None = None,
) -> IntelligenceEnvelope:
    """Full portfolio snapshot."""
```

### Lifecycle methods

```python
async def transition_recommendation(
    *,
    recommendation_id: str,
    to_status: str,
    actor: ActorContext,
    reason_code: str,
    reason_summary: str | None = None,
    linked_artefacts: dict | None = None,
) -> IntelligenceEnvelope:
    """Immutable lifecycle transition."""


async def get_recommendation_lifecycle(
    *,
    recommendation_id: str,
    actor: ActorContext,
) -> IntelligenceEnvelope:
    """Ordered transition history."""
```

---

## HTTP API (admin — future)

**Router:** `routes/compliance_intelligence_engine.py`  
**Prefix:** `/api/admin/compliance/intelligence-engine/`

| Method | Path | Maps to |
|--------|------|---------|
| POST | `/recommendations/generate` | `generate_recommendations` |
| POST | `/actions/prioritise` | `prioritise_actions` |
| GET | `/recommendations/{id}` | load + `explain_recommendation` |
| GET | `/recommendations/{id}/lifecycle` | `get_recommendation_lifecycle` |
| POST | `/recommendations/{id}/transition` | `transition_recommendation` |
| POST | `/impact/decision` | `calculate_decision_impact` |
| POST | `/impact/portfolio` | `calculate_portfolio_impact` |
| POST | `/dependencies/chain` | `find_dependency_chain` |
| POST | `/regulatory/impact` | `calculate_regulatory_impact` |
| POST | `/recommendations/compare` | `compare_recommendations` |
| GET | `/portfolio/snapshot` | `calculate_portfolio_intelligence` |
| GET | `/portfolio/workload` | `forecast_workload` |
| GET | `/readiness` | `calculate_readiness` |
| GET | `/health` | engine version, flag mode, last run metadata |

All routes: `admin_route_guard` + tenant enforcement.

**No customer-facing routes in initial slices.**

---

## Request / response envelope

### Example: generate_recommendations

**Request:**

```json
{
  "client_id": "uuid",
  "property_id": "uuid | null",
  "as_of": "2026-06-02T12:00:00+00:00 | null"
}
```

**Response:**

```json
{
  "enabled": true,
  "service": "generate_recommendations",
  "engine_version": "cie-1.0.0",
  "insufficient_evidence": false,
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…",
  "tier1": {
    "recommendations": [ ],
    "priority_snapshot_id": "pri_snap_…",
    "generation_decision_ids": ["dec_…"]
  },
  "authoritative_references": {
    "decision_ids": [],
    "recommendation_ids": []
  }
}
```

Note: `tier1` key aligns with Phase 5 AI envelope convention — CIE output is always Tier-1 deterministic; AI narration is separate consumer.

---

## Error model

| Code | When |
|------|------|
| 403 | Tenant access denied |
| 404 | Recommendation / anchor not found |
| 422 | Invalid lifecycle transition |
| 503 | Engine disabled or graph unavailable |
| 200 + `insufficient_evidence: true` | Valid request but cannot compute |

Never 500 for insufficient evidence — structured response preferred.

---

## Feature flag behaviour

```python
def intelligence_engine_enabled() -> bool:
    return mode in ("shadow", "enabled")

def intelligence_engine_operational_effects() -> bool:
    return mode == "enabled"
```

---

## AI consumer mapping (future)

| AI service (Phase 5+) | CIE method to call first |
|-----------------------|--------------------------|
| `compliance_advisor` | `prioritise_actions` + `explain_recommendation` |
| `portfolio_intelligence` | `calculate_portfolio_intelligence` |
| `regulation_interpreter` | `explain_recommendation` + rule refs |
| `operations_ai` | `find_dependency_chain` + OE bridge |
| `predictive_intelligence` | **Not CIE** — requires separate labelled programme |
| `scenario_intelligence` | `compare_recommendations` + impact diffs (deterministic scenario) |

AI receives CIE `response_hash` + optional Graph `graph_service_response_hash` — dual hash lineage in `compliance_ai_narrations`.

---

## Caching

Optional deterministic cache keyed by `inputs_hash`:

- TTL configurable
- Invalidated on new assessment decision for scoped requirements
- Cache hits must return identical `response_hash`

---

## Versioning

| Version field | Bumps when |
|---------------|------------|
| `engine_version` | Any calculation logic change |
| `priority_weights_version` | Weight matrix change |
| `recommendation_templates_version` | New recommendation type |
| `impact_rules_version` | Impact template change |
| `regulatory_impact_rules_version` | Regulatory scan logic change |

Runtime validation asserts version pins in test fixtures.
