# Priority Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

**Output artefact type:** `priority_assessment` — see `INTELLIGENCE_ARTEFACT_MODEL.md`.

## Purpose

Deterministically rank properties, requirements, and recommendations by operational urgency and compliance impact — without AI.

---

## Outputs

### PriorityItem

```json
{
  "object_type": "recommendation | requirement | property",
  "object_id": "rec_… | req_… | prop_…",
  "priority_score": 87.5,
  "priority_band": "critical",
  "priority_rank": 1,
  "reason_summary": "Gas Safety certificate expired 14 days; statutory obligation",
  "factors": [
    {
      "factor_id": "regulatory_exposure",
      "weight": 0.30,
      "raw_score": 95,
      "weighted_score": 28.5,
      "evidence_refs": ["doc_…"],
      "decision_ids": ["dec_…"]
    },
    {
      "factor_id": "expiry_proximity",
      "weight": 0.25,
      "raw_score": 90,
      "weighted_score": 22.5,
      "evidence_refs": [],
      "decision_ids": ["dec_…"]
    },
    {
      "factor_id": "portfolio_impact",
      "weight": 0.20,
      "raw_score": 70,
      "weighted_score": 14.0,
      "evidence_refs": [],
      "decision_ids": []
    },
    {
      "factor_id": "dependency_criticality",
      "weight": 0.15,
      "raw_score": 80,
      "weighted_score": 12.0,
      "evidence_refs": [],
      "decision_ids": []
    },
    {
      "factor_id": "remediation_cost_efficiency",
      "weight": 0.10,
      "raw_score": 60,
      "weighted_score": 6.0,
      "evidence_refs": [],
      "decision_ids": []
    }
  ],
  "affected_decisions": ["dec_…"],
  "expected_impact_summary": {
    "score_delta_if_completed": 8,
    "risk_delta_if_completed": -20,
    "properties_unblocked": 2
  }
}
```

### PrioritySnapshot

Versioned ranked list for a scope:

```json
{
  "snapshot_id": "pri_snap_<uuid>",
  "client_id": "uuid",
  "scope": "portfolio | property",
  "generated_at": "2026-06-02T12:00:00+00:00",
  "items": [ ],
  "weights_version": "priority_weights_v1",
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…"
}
```

---

## Priority bands

| Band | Score range | Typical signals |
|------|-------------|-----------------|
| `critical` | ≥ 80 | Expired statutory evidence, active regulatory exposure |
| `high` | 60–79 | Imminent expiry, blocking dependencies |
| `medium` | 40–59 | Missing non-blocking evidence, review pending |
| `low` | < 40 | Informational improvements, optional remediation |

Thresholds are **versioned constants** — not tuned per request.

---

## Factor catalogue (v1)

| Factor ID | Source | Calculation |
|-----------|--------|-------------|
| `regulatory_exposure` | Assessment decision + rule severity | Enum map: statutory=95, contractual=70, advisory=40 |
| `expiry_proximity` | Document/CER expiry from evidence_set | Days until expiry → piecewise score |
| `compliance_impact` | Decision Impact Engine `score_delta_estimate` | Normalised 0–100 |
| `portfolio_impact` | Count of blocked requirements downstream | log-scale normalised |
| `dependency_criticality` | Dependency Engine critical path position | On-path=90, off-path=30 |
| `remediation_velocity` | Historical lifecycle completion rate | Portfolio metric — optional v2 |
| `workload_urgency` | `forecast_workload()` congestion | Portfolio Engine input |

---

## Ranking algorithm

```
1. COLLECT candidate items (recommendations + open requirement gaps)
2. FOR each item:
     a. COMPUTE factor scores from authoritative refs only
     b. APPLY weights_version matrix → priority_score
     c. ASSIGN priority_band from thresholds
3. SORT descending by priority_score, tie-break:
     a. regulatory_exposure weighted_score
     b. expiry_proximity (earlier expiry wins)
     c. object_id lexicographic (deterministic tie-break)
4. ASSIGN priority_rank 1..N
5. EMIT PrioritySnapshot + generation decision
```

**Reproducibility:** Same candidates + same `weights_version` + same `inputs_hash` → identical ordering.

---

## Scope variants

| Method | Scope | Use case |
|--------|-------|----------|
| `prioritise_actions(client_id)` | Portfolio | Dashboard, digest, control centre |
| `prioritise_property(property_id)` | Single property | Property detail |
| `prioritise_requirements(property_id)` | Requirements on property | Requirement list ordering |

---

## Explainability

`explain_priority(item)` returns:

- Full `factors[]` breakdown
- `why_now`: max contributing factor narrative (template string + refs)
- `what_if_deferred`: link to `impact_if_ignored` projection
- Graph `explain_decision` for top contributing assessment decision

No LLM required.

---

## Non-goals

- Does not change requirement sort in compliance engine authority paths
- Does not auto-send reminders (feeds reminder eligibility only)
- Does not use ML ranking
