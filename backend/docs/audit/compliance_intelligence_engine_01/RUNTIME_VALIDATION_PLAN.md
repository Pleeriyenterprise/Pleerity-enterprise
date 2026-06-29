# Runtime Validation Plan

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

---

## Purpose

Define staging validation for CIE without AI — proving deterministic, reproducible intelligence on live `pleerity_staging` data.

**Prerequisite:** `COMPLIANCE_EVIDENCE_GRAPH_MODE=enabled`, `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=shadow|enabled`, `AI_ENABLED=false`.

Validate **Compliance Intelligence Artefacts** (CIA) via Intelligence Service Layer — not legacy per-type collections.

---

## Validation harness (future)

**Script:** `backend/tmp_compliance_intelligence_engine_staging_validation.py`  
**Artefacts:**

- `CIE_STAGING_VALIDATION.json`
- `CIE_STAGING_VALIDATION_REPORT.md`

Pattern mirrors `tmp_compliance_evidence_graph_phase5_staging_smoke.py`.

---

## Validation scenarios

### V1 — Recommendations generated deterministically

| Step | Assertion |
|------|-----------|
| Select staging client with known gaps (e.g. `ceg-2e-20260629T000018Z`) | Sample decision exists |
| Call `generate_recommendations(scope)` twice | Identical `response_hash` |
| Inspect recommendations[] | Each has `evidence[]`, `applicable_rules`, `generation_decision_id` |
| Graph query via `explain_decision(generation_decision_id)` | 200 |

### V2 — Priorities reproducible

| Step | Assertion |
|------|-----------|
| `prioritise_actions(client_id)` × 2 | Same ordering + ranks |
| Top item | `priority_score_breakdown` sums to score ± epsilon |
| `explain` top item | `why_now` cites decision_ids |

### V3 — Decision impact reproducible

| Step | Assertion |
|------|-----------|
| Pick recommendation from V1 | |
| `calculate_decision_impact(rec_id)` × 2 | Identical projection `response_hash` |
| `projected_deltas.compliance_score` | Present with disclaimer field |
| No score_ledger writes | Count before/after unchanged |

### V4 — Dependency chains reproducible

| Step | Assertion |
|------|-----------|
| `find_dependency_chain(anchor=recommendation)` × 2 | Identical chain hash |
| Blocked recommendations | `blocked_by` cites requirement_id |
| Root cause | Single node with highest regulatory_exposure |

### V5 — Portfolio intelligence reproducible

| Step | Assertion |
|------|-----------|
| `calculate_portfolio_intelligence(client_id)` × 2 | Identical snapshot hash |
| Health + workload fields | Non-null for active portfolio |
| Trend fields | `unknown` acceptable if insufficient history |

### V6 — Regulatory impact reproducible

| Step | Assertion |
|------|-----------|
| Inject fixture rule change event (staging test rule) | Governance test hook |
| `calculate_regulatory_impact(event)` × 2 | Identical report hash |
| `affected_properties` | ⊆ portfolio properties |
| `scoring_recalc_recommended` | Boolean only — no auto recalc |

### V7 — Intelligence explanations reproducible

| Step | Assertion |
|------|-----------|
| `explain_intelligence(cia_id)` × 2 | Identical envelope |
| All explainability fields populated or `insufficient_evidence` | |
| `compliance_ai_narrations` count delta | 0 |

### V8 — Lifecycle transitions

| Step | Assertion |
|------|-----------|
| `transition_recommendation(generated → accepted)` | New transition record |
| Graph emit | `decision_type=recommendation_lifecycle` decision exists |
| Invalid transition (completed → generated) | 422 |

### V9 — Insufficient evidence safety

| Step | Assertion |
|------|-----------|
| `explain_recommendation(nonexistent)` | 404 |
| Scope with no assessment decisions | `insufficient_evidence: true` |
| No speculative recommendations in response | `recommendations[]` empty |

### V10 — Regression guard

| Surface | Expected |
|---------|----------|
| Graph Health | 200 |
| Decision list | 200 |
| OE Timeline | 200 |
| System Health | 200 |
| Control Centre | 200 |
| Phase 5 investigate (Tier 1) | Still 200 with `enabled: true` |
| Scoring / rules / reminders / notifications / WO / reports / dashboard | No semantic regression |
| Local pytest CEG + Phase 5 suite | Pass |

---

## Shadow vs enabled validation

| Mode | Validate |
|------|----------|
| `shadow` | V1–V10 + no operational side-effects (no WO/reminder creation) |
| `enabled` | Above + controlled lifecycle → WO link on staging test client only |

---

## Reproducibility protocol

```python
def assert_reproducible(coro_factory):
    a = await coro_factory()
    b = await coro_factory()
    assert a["response_hash"] == b["response_hash"]
    assert a["inputs_hash"] == b["inputs_hash"]
```

Run at fixed `as_of` timestamp passed explicitly to eliminate clock drift in factors using dates.

---

## Acceptance verdicts

| Verdict | Meaning |
|---------|---------|
| `CIE_STAGING_VALIDATION_ACCEPTED` | All V1–V10 pass in `shadow` |
| `CIE_STAGING_ENABLED_ACCEPTED` | Operational integration slice pass in `enabled` |
| `CIE_STAGING_NOT_ACCEPTED` | Any critical failure |

---

## Production

**No production validation** until explicit promotion authorisation. Production remains `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=disabled`.

---

## AI exclusion proof

Validation runs with:

```text
AI_ENABLED=false
COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED=false
```

Assert `compliance_ai_narrations` count delta = 0 across full validation run.
