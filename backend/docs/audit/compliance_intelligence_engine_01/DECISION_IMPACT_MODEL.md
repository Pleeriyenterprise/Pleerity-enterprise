# Decision Impact Model

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01

**Output artefact type:** `decision_impact_assessment` — see `INTELLIGENCE_ARTEFACT_MODEL.md`.

## Purpose

Calculate **deterministic expected impact** of completing or ignoring a recommended action — before the action is performed.

This is **not prediction**. It is **structured projection** from known compliance models, decision snapshots, and registered impact rules.

---

## Impact projection entity

**Collection:** `compliance_intelligence_impact_projections`

```json
{
  "projection_id": "imp_<uuid>",
  "projection_type": "if_completed | if_ignored | if_deferred",
  "recommendation_id": "rec_<uuid>",
  "generated_at": "2026-06-02T12:00:00+00:00",
  "baseline_decision_id": "dec_assessment_…",
  "baseline_snapshot_id": "snap_…",
  "projected_deltas": {
    "compliance_score": { "current": 78, "projected": 82, "delta": 4 },
    "portfolio_risk_score": { "current": 45, "projected": 33, "delta": -12 },
    "outstanding_actions_count": { "current": 7, "projected": 6, "delta": -1 },
    "open_recommendations_count": { "current": 5, "projected": 4, "delta": -1 },
    "reminders_eligible": { "added": [], "removed": ["rent_reminder_block_gas"] },
    "evidence_readiness": { "from": "partial", "to": "complete" },
    "insurance_readiness": { "from": "at_risk", "to": "acceptable" },
    "audit_readiness": { "from": "gaps_present", "to": "audit_ready" },
    "reports_affected": [
      { "report_type": "compliance_summary_executive", "section": "recommendations", "change": "item_removed" }
    ]
  },
  "requirement_states": [
    {
      "requirement_id": "req_gas",
      "current_state": "INVALID",
      "projected_state": "VALID",
      "decision_basis": "template:evidence_renewal_satisfied"
    }
  ],
  "dependency_effects": {
    "unblocks_recommendation_ids": ["rec_…"],
    "unblocks_requirement_ids": ["req_…"]
  },
  "confidence": {
    "score": 88,
    "label": "high",
    "limitation": "Score delta is estimate from score model rules v3 — not a recalculation"
  },
  "disclaimer": "Projection only. Authoritative score change requires Compliance Engine recalc.",
  "inputs_hash": "sha256:…",
  "response_hash": "sha256:…",
  "engine_version": "cie-impact-1.0.0",
  "impact_rules_version": "impact_rules_v1"
}
```

---

## Projection methodology

### Step 1 — Baseline capture

Load from Graph Service `explain_decision(baseline_decision_id)`:

- Current requirement semantic state
- Current score contribution (from snapshot fields — **not** live recalc)
- Evidence completeness from `decision_quality`

### Step 2 — Apply impact template

Registered templates per `recommendation_type`:

| Template | Assumes on completion |
|----------|----------------------|
| `evidence_renewal_satisfied` | Requirement → VALID if document type matches rule |
| `missing_document_uploaded` | Gap closed per `find_missing_evidence` inverse |
| `licence_obtained` | Applicability satisfied + evidence complete |

Templates are **deterministic state machines** — not ML.

### Step 3 — Propagate portfolio effects

- Sum requirement-level deltas → portfolio risk aggregation formula (versioned)
- Count outstanding actions from open recommendations + open gaps
- Reminder eligibility from existing reminder rule tables (read-only)

### Step 4 — Hash and emit

- `inputs_hash` = hash(baseline_decision_id, recommendation_id, template_id, impact_rules_version)
- Emit projection linked to recommendation

---

## Impact chain (user-facing model)

```
If EPC renewed
  → Requirement state: INVALID → VALID
  → Compliance score: +N (estimated)
  → Portfolio risk: -M
  → Outstanding actions: -1
  → Reminders: eligibility restored
  → Evidence readiness: partial → complete
  → Insurance readiness: at_risk → acceptable
  → Audit readiness: gaps → ready
  → Reports: executive summary recommendation section updated
```

Each arrow is a **typed delta** in `projected_deltas` with `derivation` field citing rule ID.

---

## calculate_decision_impact()

```text
Input:  recommendation_id OR (hypothetical_action_template, requirement_id)
Output: ImpactProjection envelope (if_completed + if_ignored)
```

**Hypothetical mode** (future): simulate without persisting recommendation — still deterministic, labelled `hypothetical: true`.

---

## Safety constraints

1. **Never write score_ledger** — projections are not facts
2. **Label estimates** — `confidence.limitation` mandatory when score delta is model-based
3. **Insufficient baseline** → `insufficient_evidence: true`; no projection
4. **Conflicting assessments** → require latest superseding decision or abort

---

## Comparison

`compare_impact(projection_a, projection_b)` → field-level delta diff on `projected_deltas` — supports recommendation comparison UI without AI.
