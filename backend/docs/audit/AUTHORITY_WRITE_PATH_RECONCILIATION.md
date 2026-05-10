# Authority write-path reconciliation (Stream B / evidence)

**Scope:** Launch-stabilization audit — admin repair, score repair, validation, and recalculation routes vs canonical writers.

## Canonical writers (must remain single sources of truth)

| Concern | Authority | Notes |
|--------|-----------|--------|
| Persisted property headline `compliance_score` | `compliance_scoring_service.recalculate_and_persist` (and queue worker draining into it) | Only path that clears `compliance_score_pending` and persists breakdown consistently. |
| Requirement evidence/client runtime projection | `requirement_evidence_authority.sync_requirement_evidence_authority` via `authority_mutation_fanout.authority_sync_with_transition_observability` | Document/admin paths must not leave client surfaces believing authority synced when backbone gate blocked — observability attached to fanout. |
| Client-facing requirement rows | `requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces` + `project_requirement_row_client_runtime` | See `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`. |

## Evidence Review V2 — document verify (2026-05-10)

- **`services/evidence_review_verify.execute_verify_document_v2`** now calls **`authority_sync_with_transition_observability`** (RST core backbone gate + `sync_requirement_evidence_authority`) and **`enqueue_compliance_recalc_with_fanout`** instead of direct `sync_requirement_evidence_authority` + raw `enqueue_compliance_recalc`.
- **Rationale:** Same propagation contract as `routes.documents.verify_document` (v1): enqueue respects backbone-block semantics and attaches structured downstream observations to one fanout dict; reduces multi-path mutation and hidden async divergence.

## Audited paths (2026-05)

- **`POST /api/admin/properties/{property_id}/validate-compliance-score`** (`routes/admin.py`): With `fix=true`, persists **only** through `recalculate_and_persist(..., REASON_ADMIN_VALIDATOR_REPAIR)`; mismatch audits use shared `correlation_id`. No parallel `$set` on `compliance_score` outside the scoring service was found.
- **Compliance recalc queue worker** (`job_runner.py`): Delegates to `recalculate_and_persist`; audit on drift uses before/after read from properties collection (does not invent scores).
- **`provisioning_service._update_property_compliance`**: Updates **`compliance_status`** (RED/AMBER/GREEN) only — **not** `compliance_score`. Operational lamp; headline remains persisted scoring path.
- **Legacy verify v1** (`routes/documents.py` `verify_document` when Evidence Review V2 is off): Applies an optimistic requirement `$set` before calling `authority_sync_with_transition_observability`. **V2 verify** (`execute_verify_document_v2`) uses the same authority + `enqueue_compliance_recalc_with_fanout` contract after optional optimistic promotion. Final client-visible requirement state must match authority after sync.
- **2026-05-08 — observability / audit (no behaviour change):** When that optimistic promotion runs, transition fanout traces and `DOCUMENT_VERIFIED` audit metadata may include **`pre_authority_optimistic_requirement_promotion`** (via `requirement_transition_observability.merge_pre_authority_optimistic_requirement_promotion_marker`) so support and replay forensics can see **reconciliation is expected in the same request** and must not be confused with a second authority writer.

## Drift prevention stance

- No additional duplicate scoring writers were introduced in this pass.
- Any future admin “hot patch” that writes `compliance_score` directly must be rejected or fenced behind `recalculate_and_persist` with explicit audit reason codes.

## Operator support — tracing score change and recalc (non-client)

These paths are **not** end-user API responses; they exist for support, audit exports, and structured logs.

| Question | Where to look first | Notes |
|----------|---------------------|--------|
| Why did this headline score change after verify? | `compliance_recalc_queue` row for `property_id` + `correlation_id`; worker run in `job_runner.run_compliance_recalc_worker` | `correlation_id` is normalized by `compliance_recalc_correlation.ensure_correlation_id` from trigger + property |
| Why was recalc skipped as duplicate? | Same collection: `suppressed_duplicate_enqueue_count`, `last_duplicate_suppression_reason` | Safe to retry same correlation — insert is idempotent |
| What did the requirement transition fanout record? | Persisted transition / audit payloads carrying `downstream_trigger_targets` | Rows for `compliance_recalc_queue.enqueue_compliance_recalc` from **`enqueue_compliance_recalc_with_fanout`** include flat replay/idempotency fields: `idempotency_boundary`, `enqueue_property_id`, `resolved_queue_correlation_id`, `replay_duplicate_enqueue_safe` |
| Why is `compliance_score_pending` still true? | Pending `PENDING`/`FAILED` (retry) jobs for that `property_id` | `stuck_running` counts are observability-only in `compliance_recalc_operational_snapshot` — ops reclaim is manual today |
| Permanent recalc failure? | `status=DEAD` on queue row + `COMPLIANCE_RECALC_FAILED` audit | `dead_state_reason` truncated on row |

## Related tests

- `tests/test_portfolio_pending_score_recalc_snapshot.py` — honesty fields when recalc is queued.
