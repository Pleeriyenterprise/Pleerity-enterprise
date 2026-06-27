# Customer Impact Model

## Classifications

| Classification | Meaning |
|---|---|
| `no_impact` | Purely internal; no customer visibility |
| `operational_only` | Admin/ops surfaces only |
| `delayed` | Customer-facing output delayed |
| `temporarily_stale` | Data briefly stale but self-healing |
| `read_only_degradation` | Read paths degraded; writes OK |
| `partial_customer_impact` | Subset of customers affected |
| `property_affected` | Single property impact |
| `portfolio_affected` | Landlord portfolio impact |
| `multiple_tenants_affected` | Cross-tenant |
| `incorrect_output` | Wrong data shown (requires remediation) |
| `recovered_automatically` | Impact occurred but auto-recovered |
| `recovered_manually` | Required admin intervention to recover |
| `manual_intervention_required` | Ongoing; needs human action |

## Structure

```json
{
  "classification": "property_affected",
  "scope": "property",
  "affected_count": 1,
  "summary": "Compliance score recalculation queued for property X"
}
```

## Searchability

Indexed: `(customer_impact.classification, occurred_at)`

Intelligence shortcut: `GET /intelligence/shortcuts` aggregates non-no_impact events over 24h.

## Story aggregation

Operational Story uses **worst classification** across chain steps for summary banner.
