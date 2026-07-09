# Commercial Intelligence Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01

---

## Purpose

Extend deterministic intelligence with **commercial and operational economics** — cost, effort, time, budget, and capacity — without AI reasoning.

Commercial fields attach to the **`commercial` block** on any Compliance Intelligence Artefact (especially `recommendation` and `remediation_strategy`).

---

## Design principles

1. **Deterministic templates** — cost/effort from registered lookup tables + property metadata
2. **Estimates labelled** — never presented as invoices or authoritative spend
3. **Versioned** — `commercial_rules_version` in artefact metadata
4. **Evidence-linked** — assumptions cite property type, region, requirement rule
5. **No ML pricing** — optional external rate tables ingested as versioned config

---

## Commercial block schema

```json
{
  "commercial": {
    "commercial_rules_version": "commercial_v1",
    "estimated_remediation_cost": {
      "amount_gbp": 185.0,
      "currency": "GBP",
      "basis": "template:gas_safety_inspection_median",
      "range_low_gbp": 150.0,
      "range_high_gbp": 250.0,
      "confidence": "medium"
    },
    "estimated_contractor_effort": {
      "hours": 2.0,
      "visits": 1,
      "basis": "template:gas_safety_single_visit"
    },
    "estimated_completion_time": {
      "days": 14,
      "basis": "median_lifecycle_days:book_gas_safety_inspection"
    },
    "budget_impact": {
      "portfolio_monthly_budget_pct": 0.8,
      "basis": "client_budget_setting | default_band"
    },
    "portfolio_cost_exposure": {
      "total_open_remediation_gbp": 4200.0,
      "critical_share_pct": 35.0
    },
    "cost_per_compliance_gain": {
      "gbp_per_score_point": 46.25,
      "basis": "estimated_remediation_cost / impact.score_delta_estimate"
    },
    "expected_risk_reduction": {
      "portfolio_risk_delta": -12,
      "basis": "decision_impact_assessment ref cia_…"
    },
    "insurance_readiness": {
      "from": "at_risk",
      "to": "acceptable",
      "basis": "insurance_readiness_assessment ref cia_…"
    },
    "tenant_disruption_impact": {
      "level": "low | medium | high",
      "basis": "template:inspection_access_required"
    },
    "operational_capacity": {
      "concurrent_remediations_open": 3,
      "capacity_band": "moderate",
      "basis": "workload_forecast ref cia_…"
    },
    "maintenance_efficiency": {
      "bundling_opportunity": true,
      "bundle_with_recommendation_ids": ["cia_…"],
      "basis": "same_property_same_contractor_window"
    },
    "disclaimer": "Commercial figures are deterministic estimates for planning only."
  }
}
```

---

## Calculation sources

| Field | Deterministic source |
|-------|---------------------|
| Remediation cost | `commercial_rate_table` keyed by `recommendation_type` + region |
| Contractor effort | Template hours × property complexity factor |
| Completion time | Historical `remediation_velocity` from portfolio artefact |
| Budget impact | Client budget config ÷ sum open remediation costs |
| Portfolio cost exposure | Sum `estimated_remediation_cost` for open recommendations |
| Cost per compliance gain | `cost / score_delta` from linked impact assessment |
| Risk reduction | Linked `decision_impact_assessment` artefact |
| Insurance readiness | Linked `insurance_readiness_assessment` artefact |
| Tenant disruption | Rule template by recommendation type |
| Operational capacity | `workload_forecast` artefact |
| Maintenance efficiency | Same-property recommendation clustering algorithm |

---

## Recommendation subtype fields (commercial-related)

In addition to `commercial` block, recommendation `payload` includes:

| Field | Description |
|-------|-------------|
| `estimated_cost` | Denormalised pointer to `commercial.estimated_remediation_cost` |
| `estimated_duration` | Denormalised days |
| `implementation_complexity` | `low \| medium \| high` from dependency depth + contractor effort |
| `business_impact` | Structured score from priority factors |
| `regulatory_impact` | From applicable legislation severity enum |
| `customer_impact` | Tenant disruption + compliance visibility band |

---

## Artefact types with commercial focus

| Type | Commercial emphasis |
|------|---------------------|
| `recommendation` | Full commercial block |
| `remediation_strategy` | Aggregated portfolio cost exposure + bundling |
| `portfolio_insight` | `portfolio_cost_exposure`, capacity |
| `workload_forecast` | Capacity planning |
| `forecast` | Cost/time projection bands (deterministic) |

---

## Non-goals

- Not accounting system integration in CIE-1–4
- Not dynamic market pricing
- Not AI-generated cost estimates

---

## Explainability

`explain_intelligence()` includes `commercial` assumptions array — each assumption cites `basis` template ID and input artefact refs.
