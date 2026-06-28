# Rule Lineage Model

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIGENCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-PHASE-2-ARCHITECTURE-REFINEMENT-02  
**Phase:** 2C (primary emit); 2D (backfill)

---

## Purpose

Preserve **why every rule exists and where it originated**. Lineage extends beyond individual rule version refs on decisions to a traversable graph from primary legislation through policy registry to the compliance rule that governed a specific decision.

The graph answers:

- Which legislation ultimately required this evidence?
- Which guidance document informed this jurisdiction rule?
- Which Knowledge Centre article was authoritative at decision time?
- How did a local authority rule derive from national policy?

---

## Lineage hierarchy

```
Legislation
    ↓ derived_from
Statutory Instrument
    ↓ derived_from
Government Guidance
    ↓ derived_from
Knowledge Centre Article
    ↓ derived_from
Policy Registry Entry
    ↓ derived_from
Jurisdiction Rule
    ↓ derived_from
Local Authority Rule
    ↓ governed_by / decided_under
Compliance Rule (governed rule version)
    ↓ decided_under
Compliance Decision
    ↓ based_on_evidence
Evidence
    ↓ produced
Outcome (score, status, risk, artefact)
```

Not every decision requires every level. Producers emit nodes and edges **when authoritative sources provide refs**. Incomplete lineage is explicit via `lineage_incomplete: true` on the rule node — never silent gaps.

---

## Node types (Phase 2 additions)

Extend `compliance_evidence_graph/constants.py`:

| `node_type` | Source collection | Description |
|-------------|-------------------|-------------|
| `legislation` | `legislation_registry` / gov refs | Primary legislation |
| `statutory_instrument` | legislation refs | SI / regulations |
| `government_guidance` | guidance registry | HSE, gov.uk guidance |
| `knowledge_article` | knowledge centre | Platform KC articles |
| `policy_registry_entry` | `compliance_policy_registry` | Internal policy snapshots |
| `jurisdiction_rule` | jurisdiction engine output | National jurisdiction rules |
| `local_authority_rule` | LA-specific rules | Council requirements |
| `rule` | `governed_rules` / requirement rules | Compliance rule (existing) |

Existing types (`compliance_decision`, `document`, `requirement`, etc.) connect at the decision and evidence layers.

---

## Edge types (Phase 2 additions)

| `edge_type` | Direction | Meaning |
|-------------|-----------|---------|
| `derived_from` | child → parent | Lower layer derived from higher authority |
| `governed_by` | decision/rule → rule | Decision assessed under this rule |
| `decided_under` | decision → rule | Same as governed_by for decision nodes (existing) |
| `interpreted_by` | rule → guidance/article | Rule interpretation source |
| `based_on_evidence` | decision → evidence | Existing |
| `produced` | decision → outcome node | Score, reminder, report artefact |

All lineage edges require full provenance (Refinement-01).

---

## Node document (example: `legislation`)

```json
{
  "node_id": "ceg_leg_gas_safety_1998",
  "node_type": "legislation",
  "dedupe_key": "legislation:gas_safety_regs_1998:1998-amendment-2018",
  "occurred_at": "1998-10-31T00:00:00+00:00",
  "recorded_at": "2026-06-02T10:00:00+00:00",
  "source": {
    "collection": "legislation_registry",
    "id": "gas_safety_regs_1998",
    "version": "1998-amendment-2018"
  },
  "summary": "Gas Safety (Installation and Use) Regulations 1998",
  "metadata": {
    "title": "Gas Safety (Installation and Use) Regulations 1998",
    "jurisdiction": "england_wales",
    "effective_from": "1998-10-31",
    "lineage_incomplete": false
  }
}
```

---

## Snapshot integration

Decision snapshots carry **`applicable_legislation`** and **`rules_version`** (existing). Phase 2 adds:

```json
{
  "rule_lineage": {
    "compliance_rule_id": "rule_gas_safety",
    "governed_rule_version_id": "gov_v12",
    "lineage_node_ids": [
      "ceg_leg_gas_safety_1998",
      "ceg_si_installation_use",
      "ceg_guidance_hse_l56",
      "ceg_rule_gas_safety_v12"
    ],
    "lineage_complete": true,
    "lineage_hash": "sha256:…"
  }
}
```

`lineage_hash` covers canonical lineage refs for audit comparison.

---

## Producer responsibilities

| Producer | Lineage emit |
|----------|--------------|
| `authority_sync.py` | Rule + requirement refs from authority blob |
| `score.py` | Governed rule version from scoring context |
| `applicability.py` | Jurisdiction + policy registry refs |
| `backfill_service.py` | Reconstruct from historical registry snapshots; `confidence: indirect` |

Producers read authoritative registries at emit time. They never infer legislation not present in source data.

---

## Validator integration

`validate_rule_lineage(decision_id)` checks:

1. `decided_under` edge from decision node to compliance rule node
2. `derived_from` chain present or `lineage_incomplete` explicitly set
3. All lineage node `source` pointers resolve
4. Snapshot `rule_lineage.lineage_node_ids` consistent with graph edges

P0/P1 decisions: lineage completeness required at 2E acceptance (warnings → failures if below threshold).

---

## Graph Service consumption

| Method | Lineage usage |
|--------|---------------|
| `explain_decision` | Includes `applicable_legislation` + lineage chain in envelope |
| `replay_decision` | Phase `requirements_determined` expands lineage nodes |
| `find_decision_dependencies` | Returns lineage node IDs + version refs |
| `compare_decision` | Diff `legislation` and `rules_version` sections |

No AI required — structured traversal only.

---

## Future capabilities enabled

- Regulatory Impact Analysis — blast radius from legislation version change
- Audit Preparation — export lineage bundle with decision
- Compliance Advisor — cite authoritative chain
- Scenario Simulation — compare lineage at two points in time

No redesign required beyond populating lineage during Phase 2 producers and backfill.
