# Producer Architecture — Phase 2 Authority Integration

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIGENCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-PHASE-2-ARCHITECTURE-REFINEMENT-02  
**Status:** Authorised for implementation (2A onward)

---

## Principles

1. **Observer only** — producers run after authoritative writes succeed; never before or instead of.
2. **Centralised registry** — no scattered `emit_compliance_decision` calls outside `producers/`.
3. **Idempotent** — deterministic `dedupe_key` per logical mutation.
4. **Append-only** — no graph mutations on retry; duplicates return existing `decision_id`.
5. **Non-blocking** — failures logged; never raise to authority callers.
6. **Tenant-scoped** — `client_id` from authoritative document only.
7. **Quality metadata** — every emit includes computed `decision_quality` (descriptive only).

Gated by `graph_producers_enabled()` (`COMPLIANCE_EVIDENCE_GRAPH_MODE=shadow|enabled`).

---

## Package layout

```
backend/services/compliance_evidence_graph/
  producers/
    __init__.py
    registry.py              # dispatch + coverage metadata
    _base.py                 # dedupe builders, provenance templates, quality computer
    authority_sync.py        # 2B — P0
    score.py                 # 2B — P0
    review.py                # 2B — P0
    outcome.py               # 2B — P0
    applicability.py         # 2C — P1
    risk.py                  # 2C — P1
    document.py              # 2C — P1
    evidence.py              # 2C — P1
    reminder.py              # 2D — P2
    notification.py          # 2D — P2
    work_order.py            # 2D — P2
    knowledge.py             # 2D — P2
    operational_bridge.py    # 2A — correlation enrichment helper
  bridge_operational.py
  backfill_service.py        # 2D
  validation/
    integrity_validator.py   # 2A
```

---

## Registry API

```python
# producers/registry.py

MUTATION_KINDS = frozenset({...})  # aligned with MUTATION_COVERAGE_MATRIX.md

async def emit_for_mutation(
    *,
    mutation_kind: str,
    context: ProducerContext,
) -> Optional[str]:
    """
    Dispatch to registered producer. Returns decision_id or None.
    No-op when graph_producers_enabled() is False.
    """
```

`ProducerContext` carries post-write authoritative state:

- `db`, `client_id`, `property_id`, `requirement_id`
- `source_collection`, `source_id`
- `correlation_id`, `operational_context`
- `authoritative_payload` (read-only snapshot of mutation result)
- `mutation_timestamp` (business time — preserves causal ordering)

---

## Hook points (instrumentation boundaries)

| Priority | Authoritative writer | Producer module | Stage |
|----------|---------------------|-----------------|-------|
| P0 | `sync_requirement_evidence_authority` | `authority_sync.py` | 2B |
| P0 | `recalculate_and_persist` | `score.py` | 2B |
| P0 | `append_evidence_review_event` | `review.py` | 2B |
| P0 | `apply_action_outcome` | `outcome.py` | 2B |
| P1 | `execute_applicability_operator_command` | `applicability.py` | 2C |
| P1 | `materialize_requirements_for_property` | `applicability.py` | 2C |
| P1 | `generate_risk_signals_for_property` | `risk.py` | 2C |
| P1 | Document extraction confirm/reject | `document.py` | 2C |
| P1 | CER / supporting linkage writes | `evidence.py` | 2C |
| P2 | `send_daily_reminders` / digest jobs | `reminder.py` | 2D |
| P2 | `notification_orchestrator` | `notification.py` | 2D |
| P2 | `create_work_order` / `update_work_order` | `work_order.py` | 2D |
| P2 | Report generation jobs | `score.py` / `outcome.py` | 2D |
| P2 | Knowledge reference attach | `knowledge.py` | 2D |

Instrumentation pattern at hook site (after successful authoritative write):

```python
if graph_producers_enabled():
    await emit_for_mutation(
        mutation_kind="evidence_authority_sync",
        context=ProducerContext(...),
    )
```

---

## Dedupe key contract

Format: `{mutation_kind}:{client_id}:{entity_id}:{fact_signature}`

Examples:

| Mutation | Dedupe key pattern |
|----------|-------------------|
| Authority sync | `authority_sync:{client_id}:{requirement_id}:{authority_hash}` |
| Score change | `score_change:{client_id}:{property_id}:{correlation_id}:{score_after}` |
| Evidence review | `evidence_review:{client_id}:{review_event_id}` |
| Outcome | `outcome:{client_id}:{dedupe_key_from_activity_log}` |
| Applicability | `applicability:{client_id}:{requirement_id}:{applicability_hash}` |

`fact_signature` must change when authoritative outcome changes; must be stable on retry.

---

## Decision emit sequence (every producer)

1. Compute `decision_quality` from authoritative payload (`_base.compute_decision_quality`)
2. Build `snapshot_payload` including quality mirror + rule lineage refs
3. Call `emit_compliance_decision()` with evidence nodes/edges as applicable
4. Return `decision_id` to caller for downstream artefact stamping

Downstream writers (same transaction or immediate follow-up):

- `score_ledger_events.decision_id`
- `compliance_activity_log.decision_id`
- `evidence_review_events.decision_id`
- etc.

---

## Decision Quality computation (`_base.py`)

Computed at emit time; **never feeds back into authority logic**.

| Field | Source |
|-------|--------|
| `evidence_completeness` | evidence authority blob / required docs matrix |
| `evidence_confidence` | verification status, CER state |
| `ai_extraction_confidence` | extraction record if present |
| `human_verification_status` | review events |
| `missing_required_evidence` | gap engine / authority missing list |
| `conflicting_evidence` | authority conflict flags |
| `rule_certainty` | rules evaluation trace completeness |
| `jurisdiction_certainty` | jurisdiction attribution confidence |
| `decision_stability` | supersession depth, recent churn |
| `outstanding_review_requirements` | pending review tiers |

Labels: `confirmed`, `partial`, `inferred`, `insufficient`, `unknown`.

---

## Operational bridge

`bridge_operational.py` + `producers/operational_bridge.py`:

- Resolve `OperationalContext` (contextvars on worker paths)
- Stamp `operational_correlation_id` on decision
- Populate snapshot `operational_context` and `timeline_references`
- Emit `correlates_with` edges to OE nodes when resolvable

Join recipe: existing `correlation_id` spine + explicit graph edges.

---

## Ordering

- `decision_timestamp` = authoritative write business time (not emit wall time)
- `previous_decision_id` for supersession when producer detects state replacement
- Causal sequence preserved via timestamps + supersession chain (not global sequence numbers)

---

## Failure behaviour

| Scenario | Expected behaviour |
|----------|---------------------|
| Duplicate execution | Same `dedupe_key` → same `decision_id`, zero new nodes |
| Worker restart | Re-emit safe via dedupe |
| Queue replay | Idempotent per correlation + fact signature |
| Emit exception | Logged; authority path unaffected |
| Flag disabled | Registry returns immediately |

---

## Testing requirements

| Test file | Coverage |
|-----------|----------|
| `test_ceg_producers_registry.py` | Dispatch, gating, dedupe |
| `test_ceg_producers_p0.py` | P0 hook integration (mocked authority) |
| `test_ceg_decision_quality.py` | Quality computation; no outcome influence |
| `test_graph_integrity_validator.py` | Post-emit validation |
| `test_ceg_producer_idempotency.py` | Duplicate/replay scenarios |

---

## Coverage tracking

Each producer registers its `mutation_kind` entries in `registry.py` with:

- `priority`: P0 | P1 | P2
- `status`: planned | implemented | validated
- `stream_e_row`: cross-ref to `MUTATION_COVERAGE_MATRIX.md`

CI check (2E): matrix coverage thresholds enforced.
