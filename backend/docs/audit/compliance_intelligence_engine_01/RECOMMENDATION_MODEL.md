# Recommendation Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Purpose

Define the **Recommendation** subtype of **Compliance Intelligence Artefact** — deterministic, evidence-backed operational actions derived from authoritative compliance history.

Recommendations are **not** compliance decisions. They are `artefact_type=recommendation` records extending the base CIA schema in `INTELLIGENCE_ARTEFACT_MODEL.md`.

---

## Recommendation as artefact subtype

**Canonical storage:** `compliance_intelligence_artefacts` where `artefact_type=recommendation`  
**Legacy alias:** `recommendation_id` = `artefact_id` for backward-compatible integrations  
**Mutability:** Append-only. Content changes → new artefact with `supersedes_artefact_id`.

### Base fields (inherited)

All fields from `INTELLIGENCE_ARTEFACT_MODEL.md` base schema apply, including `artefact_id`, `inputs_hash`, `response_hash`, `source_decision_ids`, `lifecycle_state`, `commercial`, `explainability`.

### Payload schema (`payload` when `artefact_type=recommendation`)

```json
{
  "recommendation_id": "cia_<uuid>",
  "recommendation_type": "renew_eicr",
  "recommendation_version": 1,
  "status": "generated",
  "generated_at": "2026-06-02T12:00:00+00:00",
  "client_id": "uuid",
  "property_id": "uuid",
  "requirement_id": "uuid | null",
  "priority_band": "critical | high | medium | low",
  "priority_score": 87.5,
  "priority_rank": 1,
  "generation_decision_id": "dec_<uuid>",
  "supersedes_recommendation_id": null,
  "superseded_by_recommendation_id": null,
  "title": "Renew EICR before expiry",
  "action_summary": "Book qualified electrician to renew Electrical Installation Condition Report",
  "generation_reason": {
    "code": "evidence_expiring",
    "narrative": "EICR expires within statutory renewal window based on assessment decision snap_…",
    "decision_ids": ["dec_assessment_…"],
    "snapshot_ids": ["snap_…"]
  },
  "evidence": [
    {
      "evidence_type": "document",
      "source_collection": "documents",
      "source_id": "doc_eicr_…",
      "summary": "EICR valid until 2026-07-15",
      "expiry_at": "2026-07-15T00:00:00+00:00"
    }
  ],
  "applicable_legislation": [
    {
      "legislation_id": "electrical_safety_standards_2020",
      "version": "2020-04",
      "citation_label": "Electrical Safety Standards in the Private Rented Sector (England) Regulations 2020"
    }
  ],
  "applicable_rules": [
    {
      "requirement_rule_id": "rule_eicr",
      "governed_rule_version_id": "gov_v8",
      "effective_at": "2020-04-01T00:00:00+00:00"
    }
  ],
  "dependencies": {
    "prerequisite_recommendation_ids": [],
    "prerequisite_requirement_ids": [],
    "blocked_by": [],
    "blocks": ["rec_book_inspection_…"]
  },
  "expected_outcome": {
    "compliance_state": "requirement_satisfied",
    "score_delta_estimate": 4,
    "risk_delta_estimate": -12,
    "outstanding_actions_delta": -1,
    "reminders_affected": ["rent_reminder_eligibility_restored"],
    "evidence_readiness": "complete",
    "insurance_readiness": "improved",
    "audit_readiness": "improved",
    "reports_affected": ["compliance_summary_executive"]
  },
  "impact_if_ignored": {
    "projection_id": "imp_ignore_rec_…",
    "score_delta_estimate": -6,
    "risk_delta_estimate": 18,
    "regulatory_exposure": "medium",
    "deadline_at": "2026-07-15T00:00:00+00:00"
  },
  "impact_if_completed": {
    "projection_id": "imp_complete_rec_…",
    "score_delta_estimate": 4,
    "risk_delta_estimate": -12
  },
  "implementation_complexity": "low | medium | high",
  "business_impact": { "score": 75, "band": "high" },
  "regulatory_impact": { "exposure": "statutory", "severity": "high" },
  "customer_impact": { "tenant_disruption": "low", "visibility": "high" },
  "operational_correlation_id": "corr_uuid | null",
  "work_order_id": null,
  "reminder_id": null,
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…"
}
```

`confidence` lives on base artefact. `estimated_cost`, `estimated_duration` denormalised from `commercial` block — see `COMMERCIAL_INTELLIGENCE_MODEL.md`.

---

## Recommendation-specific attributes (summary)

| Attribute | Location |
|-----------|----------|
| Recommendation Type | `payload.recommendation_type` |
| Priority | `payload.priority_band`, `priority_score`, `priority_rank` |
| Expected Outcome | `payload.expected_outcome` |
| Expected Improvement | impact assessment artefact ref + score deltas |
| Estimated Cost / Duration | `commercial` + payload denormalised fields |
| Dependencies | `payload.dependencies` |
| Implementation Complexity | `payload.implementation_complexity` |
| Business / Regulatory / Customer Impact | `payload.business_impact`, etc. |

Lifecycle: `RECOMMENDATION_LIFECYCLE.md` extends `INTELLIGENCE_LIFECYCLE_MODEL.md`.

---

## Recommendation types (initial catalogue)

Deterministic templates — not LLM-generated.

| Type | Trigger signals (from graph / snapshots) |
|------|------------------------------------------|
| `renew_eicr` | EICR expiry within window; requirement not satisfied post-expiry |
| `book_gas_safety_inspection` | Gas Safety due / overdue; missing valid CER |
| `apply_hmo_licence` | HMO applicability decision + missing licence evidence |
| `review_evidence` | `decision_quality.human_verification_status` pending |
| `replace_expired_document` | Document `expiry_at` passed; authority sync INVALID |
| `schedule_contractor` | Maintenance gap + dependency resolved |
| `update_tenancy_record` | Tenancy metadata blocks compliance assessment |
| `upload_missing_document` | `find_missing_evidence` positive |
| `resolve_evidence_conflict` | `decision_quality.conflicting_evidence` non-empty |
| `remediate_regulatory_change` | Regulatory Impact Engine output |

New types require template registration + version bump — no runtime string invention.

---

## Required fields (acceptance)

Every recommendation **must** include:

| Field | Requirement |
|-------|-------------|
| `recommendation_id` | Stable immutable ID |
| `recommendation_type` | Registered enum |
| `priority_band` + `priority_score` | From Priority Engine |
| `evidence[]` | ≥1 ref or `insufficient_evidence` abort |
| `applicable_legislation` | From snapshot refs |
| `applicable_rules` | From snapshot refs |
| `dependencies` | From Dependency Engine |
| `expected_outcome` | From Decision Impact Engine |
| `confidence` | Computed from decision_quality factors |
| `generation_decision_id` | CEG decision citing generation event |

---

## Generation algorithm (deterministic)

```
FOR each candidate in scope (requirements with gap signals):
  1. CALL Graph Service find_missing_evidence(requirement_id)
  2. IF insufficient → SKIP candidate
  3. MATCH recommendation_type from template registry (rule_id + gap_type)
  4. IF no template match → SKIP (no speculative rec)
  5. LOAD latest assessment decision + snapshot
  6. BUILD evidence[] from snapshot.evidence_set
  7. COMPUTE dependencies via Dependency Engine
  8. COMPUTE expected_outcome via Decision Impact Engine
  9. ASSIGN priority via Priority Engine
  10. EMIT artefact (`artefact_type=recommendation`) + generation decision to CEG
  11. HASH inputs → inputs_hash; HASH output → response_hash
```

**Dedupe:** `dedupe_key` prevents duplicate recommendations for same logical gap within generation window.

---

## Comparison

`compare_recommendations(left_id, right_id)` returns structural diff:

- Priority score delta + factor breakdown diff
- Evidence set diff (added/removed refs)
- Dependency diff
- Expected outcome diff
- Supersession chain overlap

No semantic "better/worse" LLM judgement — numeric and set diffs only.

---

## Integration points

| Consumer | Usage |
|----------|-------|
| Work Orders | `work_order_id` set on lifecycle `scheduled` transition |
| Reminders | Reminder service reads `priority_band` + `deadline_at` from impact_if_ignored |
| Monthly Digest | Top N by `priority_rank` |
| Reports | Group by `recommendation_type` + property |
| Decision Explorer | Navigate via `generation_decision_id` |
| AI Layer | `explain_recommendation()` envelope — narration only |

---

## What recommendations are not

- Not compliance assessments (`decision_type=compliance_assessment`)
- Not score mutations
- Not rule evaluations
- Not predictions (`prediction: true` reserved for future labelled scenario engine — separate from core recommendations)
