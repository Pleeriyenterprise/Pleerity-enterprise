# Regulatory Impact Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

**Output artefact type:** `regulatory_impact_assessment` — see `INTELLIGENCE_ARTEFACT_MODEL.md`.

## Purpose

When governed rules or legislation versions change, deterministically determine blast radius across properties, decisions, reports, evidence, recommendations, and operational workload.

CIE does **not** author rules — it consumes **rule change events** emitted by the Rules Engine / governance pipeline.

---

## Trigger input

```json
{
  "event_type": "rule_version_change",
  "governed_rule_version_id": "gov_v13",
  "previous_version_id": "gov_v12",
  "requirement_rule_id": "rule_eicr",
  "effective_at": "2026-09-01T00:00:00+00:00",
  "change_summary": "EICR renewal interval amended",
  "emitted_by": "rules_governance_service",
  "correlation_id": "uuid"
}
```

---

## Regulatory impact report

**Collection:** `compliance_intelligence_regulatory_impact_reports`

```json
{
  "report_id": "reg_imp_<uuid>",
  "rule_change_event": { },
  "generated_at": "2026-06-02T12:00:00+00:00",
  "affected_properties": [
    {
      "property_id": "prop_…",
      "impact_level": "high",
      "current_assessment_decision_id": "dec_…",
      "projected_reassessment_required": true,
      "reason": "Rule interval change affects expiry calculation"
    }
  ],
  "affected_decisions": [
    {
      "decision_id": "dec_…",
      "decision_type": "compliance_assessment",
      "supersession_required": true,
      "reason": "rules_version mismatch post effective_at"
    }
  ],
  "affected_reports": [
    { "report_type": "compliance_summary_executive", "regeneration_recommended": true }
  ],
  "affected_evidence": [
    { "document_id": "doc_…", "validity_reassessment_required": true }
  ],
  "affected_recommendations": [
    { "recommendation_id": "rec_…", "supersession_required": true }
  ],
  "required_reevaluations": {
    "assessment_count": 12,
    "applicability_count": 3,
    "scoring_recalc_recommended": true
  },
  "estimated_workload": {
    "new_recommendations": 8,
    "remediation_hours_estimate": 16,
    "forecast_completion_days": 21
  },
  "estimated_customer_impact": {
    "properties_requiring_action": 12,
    "critical_priority_count": 2,
    "notification_recommended": true
  },
  "remediation_recommendations": ["rec_…"],
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…",
  "engine_version": "cie-regulatory-1.0.0",
  "impact_rules_version": "regulatory_impact_v1"
}
```

---

## Calculation methodology

### Step 1 — Scope affected rules

Load diff between `gov_v12` and `gov_v13` from governed rules store (read-only). Extract changed fields: intervals, applicability predicates, severity.

### Step 2 — Property scan

For each property with applicability decision citing `requirement_rule_id`:

1. Graph `find_historical_decision` at `effective_at`
2. Compare assessment outcome under old vs new rule template (deterministic re-evaluation template — **not** live Compliance Engine)
3. If outcome differs → `affected_properties` + `required_reevaluations`

### Step 3 — Decision blast radius

Decisions with `rules_version.governed_rule_version_id = gov_v12` and `decision_timestamp < effective_at` flagged for supersession review.

### Step 4 — Downstream artefacts

| Artefact | Rule |
|----------|------|
| Reports | Regenerate if any affected property in report scope |
| Evidence | Reassess if validity rules changed |
| Recommendations | Supersede if `applicable_rules` version stale |
| Work orders | Flag linked WOs for review |

### Step 5 — Workload estimate

```
new_recommendations = count(affected_properties where gap template matches)
forecast_completion_days = avg_lifecycle_days * new_recommendations / throughput_factor
```

Throughput factor from portfolio `remediation_velocity` — deterministic.

---

## calculate_regulatory_impact(change_event)

Returns full report envelope. In `shadow` mode: compute + graph emit only.

---

## Integration with Compliance Engine

CIE recommends `scoring_recalc_recommended: true` — actual recalc remains Compliance Engine queue authority. **No bypass.**

---

## Explainability

Each affected row includes:

- `reason` (template + changed field ref)
- `decision_id` / `document_id` pointers
- `rule_diff_ref` pointing to governed diff record

`explain_regulatory_impact(report_id)` composes without LLM.

---

## Insufficient evidence

If rule diff unavailable or applicability decisions missing → `insufficient_evidence: true` for affected property subset; partial report allowed with `completeness: partial` flag.
