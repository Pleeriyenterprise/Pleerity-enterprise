# Compliance Decision Model & Decision Snapshots

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-ARCHITECTURE-REFINEMENT-01, REFINEMENT-02 (Decision Quality)

---

## Purpose

Compliance Decisions are **first-class, immutable graph entities** — not attributes buried inside requirement rows or assessment blobs.

Every score change, risk change, reminder, recommendation, work order, and report **must reference the `decision_id` that produced it**.

The platform must answer **"Why was this exact decision made?"** from a single decision record + its snapshot — without reconstructing from unrelated collections.

---

## Compliance Decision (first-class entity)

**Collection:** `compliance_decisions`  
**Role:** Immutable decision authority index. Append-only. Never updated in place.

### Schema

```json
{
  "decision_id": "dec_<uuid>",
  "decision_type": "compliance_assessment",
  "decision_version": 1,
  "decision_timestamp": "2026-06-28T10:00:00.123456+00:00",
  "recorded_at": "2026-06-28T10:00:00.234567+00:00",
  "decision_outcome": "VALID",
  "previous_decision_id": "dec_<uuid>",
  "superseding_decision_id": null,
  "decision_authority": {
    "service": "compliance_scoring_service",
    "component": "recalculate_and_persist",
    "actor_type": "system",
    "actor_id": "compliance_recalc_worker"
  },
  "decision_confidence": {
    "score": 100,
    "label": "runtime_confirmed",
    "reason": "Authority sync + verified document"
  },
  "rules_version": {
    "governed_rule_version_id": "gov_v12",
    "requirement_rule_id": "rule_gas_safety",
    "effective_at": "2026-01-01T00:00:00+00:00"
  },
  "jurisdiction_version": {
    "jurisdiction": "england",
    "local_authority": "Westminster",
    "attribution_version": "jur_v3"
  },
  "legislation_version": {
    "refs": [
      {
        "legislation_id": "gas_safety_regs_1998",
        "version": "1998-amendment-2018",
        "effective_from": "1998-10-31"
      }
    ]
  },
  "evidence_set": {
    "snapshot_id": "snap_<uuid>",
    "evidence_node_ids": ["ceg_doc_1", "ceg_cer_2", "ceg_review_3"],
    "document_ids": ["doc_abc"],
    "cer_ids": ["cer_xyz"]
  },
  "operational_correlation_id": "corr_uuid",
  "client_id": "uuid",
  "property_id": "uuid",
  "requirement_id": "uuid",
  "scope": {
    "object_type": "requirement",
    "object_id": "req_abc"
  },
  "summary": "Requirement assessed VALID based on verified Gas Safety certificate",
  "reasoning_inputs_hash": "sha256:…",
  "snapshot_id": "snap_<uuid>",
  "graph_node_id": "ceg_decision_<uuid>",
  "dedupe_key": "compliance_assessment:req_abc:2026-06-28T10:00:00Z:VALID",
  "environment": "staging",
  "build_sha": "49eb7978…",
  "metadata": {
    "trigger": "authority_sync",
    "correlation_id": "corr_uuid"
  },
  "decision_quality": {
    "evidence_completeness": "complete",
    "evidence_confidence": { "score": 100, "label": "verified" },
    "ai_extraction_confidence": { "score": 85, "label": "high" },
    "human_verification_status": "approved",
    "missing_required_evidence": [],
    "conflicting_evidence": [],
    "rule_certainty": { "score": 100, "label": "confirmed" },
    "jurisdiction_certainty": { "score": 100, "label": "confirmed" },
    "decision_stability": "stable",
    "outstanding_review_requirements": [],
    "overall_label": "confirmed",
    "computed_at": "2026-06-28T10:00:00.123456+00:00",
    "computed_by": "compliance_evidence_graph.producers._base"
  }
}
```

### Decision Quality (Refinement-02)

**Required on every runtime decision.** Descriptive metadata only — **must never modify compliance outcomes**.

Future Compliance Intelligence services may use this block when explaining confidence or recommending follow-up actions.

| Field | Type | Description |
|-------|------|-------------|
| `evidence_completeness` | enum | `complete` \| `partial` \| `insufficient` \| `unknown` |
| `evidence_confidence` | object | `{ score, label }` from verification / authority state |
| `ai_extraction_confidence` | object \| null | From extraction record when applicable |
| `human_verification_status` | enum | `approved` \| `rejected` \| `pending` \| `not_required` \| `unknown` |
| `missing_required_evidence` | array | Requirement IDs or doc types still missing |
| `conflicting_evidence` | array | Conflicts detected by authority (refs only) |
| `rule_certainty` | object | Completeness of rules evaluation trace |
| `jurisdiction_certainty` | object | Jurisdiction attribution confidence |
| `decision_stability` | enum | `stable` \| `recently_superseded` \| `volatile` \| `unknown` |
| `outstanding_review_requirements` | array | Pending human review tiers / scopes |
| `overall_label` | enum | `confirmed` \| `partial` \| `inferred` \| `insufficient` \| `unknown` |
| `computed_at` | ISO8601 | When quality was assessed |
| `computed_by` | string | Producer component (audit) |

**Rules:**

1. Producers compute quality from **authoritative post-write state only**.
2. Missing data → explicit `unknown` / `insufficient` — never upgrade confidence.
3. Backfill decisions: `overall_label: inferred`, `metadata.backfill: true`.
4. Quality is mirrored in snapshot as `decision_quality` for historical reproducibility.
5. Graph Service `explain_decision` includes quality in `confidence_metadata` envelope section.

### Decision types (enum)

| `decision_type` | Produced by | Downstream artefacts must cite `decision_id` |
|-----------------|-------------|-----------------------------------------------|
| `compliance_assessment` | Authority sync / scoring | requirement status projection |
| `compliance_score_change` | Score recalc | `score_ledger_events`, dashboards |
| `risk_assessment` | Risk signal service | risk signals, portfolio views |
| `requirement_applicability` | Applicability resolution | requirement NOT_REQUIRED / applicable |
| `evidence_acceptance` | Human review / validation | document verification state |
| `evidence_rejection` | Human review | rejection reason |
| `reminder_generation` | Reminder evaluator | reminder sends |
| `recommendation` | Advisor / gap engine | recommendations |
| `work_order_creation` | Workflow / maintenance | work orders |
| `report_generation` | Report jobs | audit packs, PDFs |
| `regulatory_interpretation` | Rules evaluation | applicability audit |

### Immutability rules

1. **No in-place updates** — corrections create a new decision with `previous_decision_id` link.
2. **Supersession chain** — when decision B replaces A: `A.superseding_decision_id = B`, `B.previous_decision_id = A`.
3. **Independent queryability** — indexed by `decision_id`, `decision_type`, `property_id`, `requirement_id`, `decision_timestamp`, `operational_correlation_id`.
4. **Single-question answer** — `GraphService.explain_decision(decision_id)` returns complete answer without cross-collection inference.

### Mandatory downstream references

| Artefact | Required field |
|----------|----------------|
| `score_ledger_events` | `decision_id` (new field, Phase 2) |
| `risk_signals` | `decision_id` |
| Reminder evaluation records | `decision_id` |
| Work orders (compliance-triggered) | `decision_id` |
| Report generation jobs | `decision_id` |
| Graph nodes (`score_change`, `reminder`, etc.) | `decision_id` |
| OE events (bridge) | `metadata.compliance_decision_id` |

---

## Decision Snapshot (immutable knowledge freeze)

**Collection:** `compliance_decision_snapshots`  
**Role:** Complete state of knowledge **at decision time**. Never modified after creation.

### Schema

```json
{
  "snapshot_id": "snap_<uuid>",
  "decision_id": "dec_<uuid>",
  "snapshot_timestamp": "2026-06-28T10:00:00.123456+00:00",
  "recorded_at": "2026-06-28T10:00:00.234567+00:00",
  "snapshot_hash": "sha256:…",
  "applicable_legislation": [
    {
      "legislation_id": "gas_safety_regs_1998",
      "version": "1998-amendment-2018",
      "title": "Gas Safety (Installation and Use) Regulations 1998",
      "effective_from": "1998-10-31",
      "source_ref": "gov_rule_v12"
    }
  ],
  "applicable_jurisdiction": {
    "jurisdiction": "england",
    "local_authority": "Westminster",
    "council_requirements": [],
    "attribution_snapshot": { }
  },
  "rules_version": {
    "governed_rule_version_id": "gov_v12",
    "rule_definitions_hash": "sha256:…",
    "applicability_rules_executed": ["rule_a", "rule_b"]
  },
  "evidence_version": {
    "evidence_node_ids": ["ceg_doc_1", "ceg_cer_2"],
    "document_versions": [
      { "document_id": "doc_abc", "version": 3, "uploaded_at": "…", "verification_status": "verified" }
    ],
    "cer_versions": [
      { "cer_id": "cer_xyz", "version": 1, "verification_status": "approved" }
    ]
  },
  "ai_extraction_results": [
    {
      "document_id": "doc_abc",
      "extraction_id": "ext_1",
      "extracted_fields": { "expiry_date": "2027-06-28" },
      "confidence": 85,
      "model_version": "extraction_v2"
    }
  ],
  "human_approvals": [
    {
      "review_event_id": "rev_1",
      "actor_id": "admin_uuid",
      "outcome": "approved",
      "timestamp": "2026-06-28T09:55:00+00:00"
    }
  ],
  "compliance_score": {
    "property_id": "uuid",
    "score_before": 72,
    "score_after": 78,
    "headline_status": "partially_compliant"
  },
  "risk_score": {
    "property_id": "uuid",
    "risk_level_before": "medium",
    "risk_level_after": "low"
  },
  "operational_context": {
    "correlation_id": "corr_uuid",
    "job_run_id": "run_abc",
    "recalc_queue_item_id": "queue_xyz",
    "operational_event_ids": ["ev_1", "ev_2"]
  },
  "timeline_references": [
    { "node_id": "ceg_…", "occurred_at": "…", "summary": "…" }
  ],
  "decision_reasoning_inputs": {
    "authority_sync_outcome": { "semantic_state": "VALID", "effective_expiry": "2027-06-28" },
    "rules_evaluation_trace": [ ],
    "assumptions": [ ],
    "exclusions_evaluated": [ ],
    "exemptions_evaluated": [ ]
  },
  "client_id": "uuid",
  "property_id": "uuid",
  "requirement_id": "uuid"
}
```

### Snapshot rules

1. **Created atomically with decision** — every `compliance_decision` has exactly one `snapshot_id` at emit time.
2. **Never updated** — legislation changes do not retroactively alter snapshots.
3. **Historical explainability** — all historical questions resolve against `snapshot_id`, not current `requirements` / `documents` state.
4. **Content-addressed integrity** — `snapshot_hash` covers canonical JSON for audit verification.

---

## Historical explainability

| Question | Resolution path |
|----------|-----------------|
| Why was property compliant six months ago? | `find_historical_decision(property_id, as_of=t)` → `snapshot_id` → `explain_decision` |
| Why did score decrease last week? | `decision_type=compliance_score_change` + timestamp filter → snapshot `compliance_score` |
| Which regulation version applied when report generated? | Report's `decision_id` → snapshot `applicable_legislation` |
| Which evidence existed when reminder cancelled? | Reminder's `decision_id` → snapshot `evidence_version` |
| Which documents when recommendation produced? | Recommendation `decision_id` → snapshot |

**Rule:** Historical APIs accept `as_of` or `decision_id`. They **never** read current mutable state for past-tense questions.

---

## Decision comparison

**Service:** `GraphService.compare_decision(left_decision_id, right_decision_id)`  
**Alternative:** `compare_decision_snapshots(left_snapshot_id, right_snapshot_id)`

### Structured diff output

```json
{
  "left_decision_id": "dec_a",
  "right_decision_id": "dec_b",
  "left_snapshot_id": "snap_a",
  "right_snapshot_id": "snap_b",
  "outcome_changed": true,
  "diff": {
    "decision_outcome": { "before": "PENDING", "after": "VALID" },
    "compliance_score": { "before": 72, "after": 78 },
    "risk_score": { "before": "medium", "after": "low" },
    "legislation": { "added": [], "removed": [], "version_changed": [] },
    "rules_version": { "before": "gov_v11", "after": "gov_v12" },
    "evidence": {
      "documents_added": ["doc_new"],
      "documents_removed": [],
      "documents_superseded": [{ "from": "doc_old", "to": "doc_new" }],
      "extractions_changed": []
    },
    "human_approvals_added": ["rev_2"],
    "operational_context_changed": false
  },
  "decision_chain": ["dec_a", "dec_b"],
  "insufficient_evidence": false
}
```

Comparison is **deterministic** — same decision pair → same diff JSON.

---

## Graph integration

Each `compliance_decision` also emits:

1. A `compliance_decision` node in `compliance_evidence_nodes` (for traversal).
2. Edges with full provenance:
   - `decided_under` → `rules` node
   - `based_on_evidence` → evidence nodes
   - `supersedes` → previous decision node
   - `produced` → downstream artefact nodes (score_change, reminder, …)
   - `correlates_with` → operational events

The **authoritative decision record** is `compliance_decisions`; the graph node is the traversable index.

---

## Indexes (`compliance_decisions`)

- `decision_id` unique
- `dedupe_key` unique
- `(client_id, decision_timestamp DESC)`
- `(property_id, decision_timestamp DESC)`
- `(requirement_id, decision_timestamp DESC)`
- `(decision_type, decision_timestamp DESC)`
- `previous_decision_id`
- `superseding_decision_id`
- `operational_correlation_id`
- `snapshot_id` unique

## Indexes (`compliance_decision_snapshots`)

- `snapshot_id` unique
- `decision_id` unique (1:1 at creation)
- `(property_id, snapshot_timestamp DESC)`
- `snapshot_hash`
