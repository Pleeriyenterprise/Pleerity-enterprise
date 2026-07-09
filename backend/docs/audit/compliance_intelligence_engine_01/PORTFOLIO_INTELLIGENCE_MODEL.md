# Portfolio Intelligence Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

**Output artefact types:** `portfolio_insight`, `portfolio_risk_assessment`, `portfolio_readiness_assessment`, `compliance_trend`, `workload_forecast` — see `INTELLIGENCE_ARTEFACT_MODEL.md`.

## Purpose

Calculate deterministic portfolio-level compliance operations metrics — health, trends, workload, readiness, risk concentration, velocity — without AI.

---

## Portfolio snapshot

**Collection:** `compliance_intelligence_portfolio_snapshots`

```json
{
  "snapshot_id": "port_snap_<uuid>",
  "client_id": "uuid",
  "generated_at": "2026-06-02T12:00:00+00:00",
  "portfolio_health": {
    "score": 72,
    "band": "moderate",
    "properties_total": 24,
    "properties_compliant": 18,
    "properties_at_risk": 4,
    "properties_non_compliant": 2,
    "trend_30d": { "direction": "improving", "delta": 3 }
  },
  "portfolio_risk": {
    "concentration_score": 0.42,
    "top_risk_properties": [
      { "property_id": "prop_…", "risk_score": 85, "primary_driver": "expired_gas_safety" }
    ],
    "regulatory_exposure_summary": {
      "critical": 2,
      "high": 5,
      "medium": 8
    }
  },
  "portfolio_workload": {
    "open_recommendations": 12,
    "critical_priority": 2,
    "scheduled_actions": 4,
    "in_progress_actions": 3,
    "forecast_30d_completions": 6
  },
  "portfolio_readiness": {
    "evidence_readiness_pct": 85,
    "insurance_readiness_pct": 78,
    "audit_readiness_pct": 71,
    "report_readiness_pct": 90
  },
  "compliance_velocity": {
    "requirements_satisfied_30d": 8,
    "requirements_regressed_30d": 1,
    "net_velocity": 7,
    "avg_days_to_remediate": 14.2
  },
  "remediation_velocity": {
    "recommendations_completed_30d": 5,
    "recommendations_generated_30d": 9,
    "completion_rate": 0.56,
    "avg_lifecycle_days": 11.5
  },
  "upcoming_workload": {
    "expirations_30d": 6,
    "expirations_90d": 14,
    "inspections_due_30d": 3,
    "regulatory_deadlines": []
  },
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…",
  "engine_version": "cie-portfolio-1.0.0"
}
```

---

## Metric definitions

### Portfolio health

Aggregated from latest assessment decisions per property-requirement pair:

```
health_score = weighted_mean(property_compliance_scores)
band = thresholds(health_score)
trend_30d = compare snapshot at as_of vs as_of-30d (historical decisions)
```

### Risk concentration

```
concentration_score = Herfindahl index on property risk scores
top_risk_properties = sort by risk_score desc, take 5
```

### Workload

Counts from open recommendations by lifecycle status + open gaps from `find_missing_evidence` portfolio scan.

### Readiness percentages

| Readiness | Numerator | Denominator |
|-----------|-----------|-------------|
| Evidence | Requirements with complete evidence_set | Total applicable requirements |
| Insurance | Properties meeting insurance evidence template | Total properties |
| Audit | Properties with no critical gaps | Total properties |
| Report | Properties with report prerequisites met | Total properties |

Templates are versioned — aligned with report service prerequisites.

### Velocity metrics

Derived from **decision history** (not mutable requirement rows):

- `requirements_satisfied_30d` = count of assessment decisions VALID where previous was not VALID
- `recommendations_completed_30d` = lifecycle transitions to `completed`
- `avg_days_to_remediate` = mean(completed_at - generated_at) for recommendations

---

## calculate_portfolio_impact()

Portfolio-level variant of Decision Impact Engine:

```json
{
  "if_all_critical_completed": {
    "portfolio_health_delta": 8,
    "risk_concentration_delta": -0.15,
    "open_recommendations_delta": -2
  }
}
```

Sum of individual recommendation `impact_if_completed` projections — deterministic arithmetic, labelled aggregate.

---

## forecast_workload(window_days)

```json
{
  "window_days": 30,
  "projected_new_recommendations": 4,
  "projected_completions": 5,
  "projected_expirations": 6,
  "congestion_band": "moderate",
  "inputs_hash": "sha256:…"
}
```

Based on:

- Known expiry dates from evidence
- Historical generation rate (lifecycle decisions count / 30d)
- No stochastic forecasting

---

## calculate_readiness(scope)

Property or portfolio readiness bundle — subset of snapshot fields for targeted APIs.

---

## Trend calculation

Trends use `find_historical_decision` at two `as_of` timestamps. If historical insufficient → `trend: unknown`, not interpolated.

---

## Non-goals

- Not a BI dashboard replacement — supplies data contracts
- Not predictive ML ("likely to fail")
- Does not modify portfolio structure
