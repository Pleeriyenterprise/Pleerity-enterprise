# Intelligence Consumers

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-01

---

## Access rule

> Every consumer retrieves intelligence **only** through the **Intelligence Service Layer**. No direct queries to `compliance_intelligence_artefacts`.

---

## Consumer catalogue

| Consumer | Artefact types typically used | ISL methods |
|----------|--------------------------------|-------------|
| **Decision Explorer** | All | `explain_intelligence`, `get_intelligence_lifecycle` |
| **Compliance Reports** | `recommendation`, `portfolio_insight`, `compliance_trend` | `list_intelligence`, `explain_intelligence` |
| **Monthly Digest** | `priority_assessment`, `recommendation` | `list_intelligence(published)`, `generate_portfolio_insights` |
| **Operational Dashboards** | `priority_assessment`, `operational_insight`, `workload_forecast` | `list_intelligence`, `generate_readiness` |
| **Portfolio Dashboard** | `portfolio_insight`, `portfolio_risk_assessment`, `compliance_trend` | `generate_portfolio_insights` |
| **Inspector View** | `recommendation`, `dependency_chain`, `audit_readiness_assessment` | `list_intelligence`, `explain_intelligence` |
| **Auditor View** | `audit_readiness_assessment`, `compliance_trend`, decision impact | `explain_intelligence`, Graph `explain_decision` |
| **Knowledge Centre** | `recommendation`, regulatory | `explain_intelligence` (future customer) |
| **Operational Evidence Platform** | `operational_insight`, correlation refs | `get_intelligence` + OE correlation |
| **Compliance Evidence Graph** | All (indexed nodes) | Producer emit — not ISL read |
| **Work Orders / Reminders** | `recommendation` (lifecycle) | `transition_intelligence`, `get_intelligence` |
| **Future Customer Portal** | Published artefacts only | `list_intelligence(published)` |
| **Future Public APIs** | Scoped published artefacts | ISL with API gateway |
| **AI Intelligence Layer** | All | `explain_intelligence` + optional Graph envelope for narration |

---

## Future advisors (consumers, not engines)

| Advisor name | Consumes | Does not calculate |
|--------------|----------|-------------------|
| Compliance Advisor | `recommendation`, `priority_assessment` | ✓ |
| Portfolio Advisor | `portfolio_insight`, `portfolio_risk_assessment` | ✓ |
| Operational Advisor | `operational_insight`, `dependency_chain` | ✓ |
| Regulatory Advisor | `regulatory_impact_assessment` | ✓ |
| Audit Advisor | `audit_readiness_assessment` | ✓ |
| Insurance Advisor | `insurance_readiness_assessment` | ✓ |
| Budget Advisor | `commercial` block on artefacts | ✓ |
| Maintenance Optimiser | `recommendation`, `remediation_strategy` | ✓ |
| Scenario Simulation | `compare_intelligence`, impact assessments | Deterministic diff only |
| Predictive Planning | **Not CIE** — ML programme if ever authorised | — |
| Portfolio Forecasting | `forecast`, `workload_forecast` artefacts | CIE deterministic |
| Decision Diff | `compare_intelligence` | ✓ |
| Natural Language Intelligence | AI narration of ISL envelopes | ✓ |

---

## Consumer registration (future)

```json
{
  "consumer_id": "monthly_digest",
  "allowed_artefact_types": ["recommendation", "priority_assessment"],
  "min_lifecycle_state": "published",
  "rate_limit": "1_per_client_per_day"
}
```

Enables `consumed` lifecycle transitions with audit.

---

## AI layer consumption path

```
ISL.explain_intelligence(artefact_id)
        → Intelligence Service Envelope (tier1)
        → Optional: Graph Service.explain_decision(source_decision_ids[0])
        → Phase 5 investigate/narrate (tier2, optional)
```

AI **never** calls `generate_*` methods to invent intelligence — only `explain_*` on existing artefacts unless user explicitly triggers regeneration via ISL (admin action, audited).

---

## Dual-hash lineage for narration

`compliance_ai_narrations` should store:

- `intelligence_response_hash` (ISL envelope)
- `graph_service_response_hash` (when Graph enrichment used)

Enables full replay audit.
