# Comparison Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02

---

## Purpose

Define **Intelligence Comparison** — deterministic structural diff between two Compliance Intelligence Artefacts (or their provenance records) without AI.

Answers: *Why is the new recommendation different from the old one?*

---

## Comparison inputs

| Input | Description |
|-------|-------------|
| `left_id` | Artefact ID (typically older / superseded) |
| `right_id` | Artefact ID (typically newer / current) |
| `compare_mode` | `artefact` \| `provenance` \| `full` (default: `full`) |

Both artefacts must be tenant-accessible to the actor.

---

## Comparison pipeline

```
left artefact (cia_A)          right artefact (cia_B)
        │                              │
        ▼                              ▼
left provenance (cip_A)        right provenance (cip_B)
        │                              │
        └──────────┬───────────────────┘
                   ▼
        Provenance Diff Engine (deterministic)
                   ▼
        Comparison Report Envelope
```

**No LLM.** Diff is structural field comparison + registry version diff + trace stage diff.

---

## Diff dimensions

| Dimension | Source | Example output |
|-----------|--------|----------------|
| Artefact payload | CIA `payload` | `priority_score: 72 → 91` |
| Lifecycle | CIA `lifecycle_state` | `published → superseded` |
| Inputs | Provenance `inputs_hash` | `changed: true` |
| Rules | `rule_versions_used` | `rule_eicr: 2026-01-01 → 2026-03-01` |
| Legislation | `legislation_versions_used` | Added `housing_act_amendment_2026` |
| Evidence | `evidence_ids_used` | `+doc_new_cert`, `-doc_expired_cert` |
| Snapshots | `snapshot_ids_used` | Snapshot set changed |
| Weights | `weight_set_version` | `weights_v1.1.0 → weights_v1.2.0` |
| Strategies | `*_strategy_version` | `rec_strategy_v1.0.0 → rec_strategy_v1.1.0` |
| Constraints | `constraint_set_version` | Constraint set unchanged |
| Engine | `engine_version` | `cie-1.2.0 → cie-2.0.0` |
| Trace stages | `calculation_trace` | `weight_calculation` output hash changed |
| Graph refs | `graph_node_references` | New dependency edge cited |
| Dependencies | Trace `dependency_resolution` | `blocked_by` removed |

---

## Comparison report schema

```json
{
  "service": "compare_intelligence",
  "enabled": true,
  "insufficient_evidence": false,
  "left_artefact_id": "cia_A",
  "right_artefact_id": "cia_B",
  "left_provenance_id": "cip_A",
  "right_provenance_id": "cip_B",
  "supersession_relationship": "cia_B supersedes cia_A",
  "summary": {
    "primary_change_drivers": [
      "weight_set_version",
      "evidence_ids_used"
    ],
    "inputs_hash_changed": true,
    "response_hash_changed": true
  },
  "diff": {
    "registry_versions": [
      {
        "field": "weight_set_version",
        "left": "weights_v1.1.0",
        "right": "weights_v1.2.0",
        "impact": "priority_score_recalculated"
      }
    ],
    "rule_versions": [
      {
        "rule_id": "rule_eicr_renewal",
        "left": "2026-01-01",
        "right": "2026-03-01"
      }
    ],
    "evidence": {
      "added": ["doc_new_cert"],
      "removed": ["doc_expired_cert"]
    },
    "trace_stages": [
      {
        "stage": "weight_calculation",
        "output_hash_changed": true
      }
    ],
    "payload_fields": [
      {
        "path": "payload.priority_score",
        "left": 72,
        "right": 91
      }
    ]
  },
  "response_hash": "sha256:…"
}
```

---

## Supersession-aware comparison

When `right.supersedes_artefact_id == left.artefact_id`:

- Comparison report includes `supersession_relationship`
- `primary_change_drivers` ranked by provenance diff engine heuristics (deterministic ordering)
- `explain_intelligence(right_id)` may embed comparison summary by reference

---

## Weight / strategy change attribution

```
IF weight_set_version changed
  → attribute priority_score delta to weight_set_version
ELSE IF evidence_ids_used changed
  → attribute to evidence change
ELSE IF rule_versions_used changed
  → attribute to rule change
…
```

Attribution rules are **deterministic precedence** — documented in comparison engine, versioned as `comparison_strategy_version` in provenance when comparison is itself persisted (optional).

---

## ISL integration

Extends existing `compare_intelligence(left_id, right_id)`:

```python
async def compare_intelligence(
    *,
    left_id: str,
    right_id: str,
    actor: ActorContext,
    compare_mode: str = "full",
) -> IntelligenceEnvelope:
    """Deterministic provenance-aware diff."""
```

`explain_intelligence` may call comparison internally when artefact has `supersedes_artefact_id`.

---

## AI consumer boundary

Phase 5 AI may **narrate** comparison envelopes — it must not **generate** comparison conclusions. Tier 2 narration cites `diff` fields only.

---

## Validation scenarios (future)

| ID | Assertion |
|----|-----------|
| C1 | Compare superseded recommendation pair → `weight_set_version` in diff when weights changed |
| C2 | Compare identical regeneration → empty diff, `response_hash_changed: false` |
| C3 | Compare after rule version change → `rule_versions` section populated |
| C4 | No AI imports in comparison module |

See `RUNTIME_VALIDATION_PLAN.md` (updated).

---

## Non-goals

- Comparison does not recommend which artefact is "better"
- Comparison does not alter either artefact
- Comparison does not determine compliance outcomes
