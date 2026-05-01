# Stream E — Mutation fan-out matrix (read-only)

**Purpose:** Single inventory of compliance-changing mutations: whether gap persistence, score persistence, audits, and notifications are wired today, plus stale-state and missing-wiring risks. **No runtime behaviour** — code references are for traceability only.

**Companion:** `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` (Stream E), `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md`.

**Last updated:** 2026-04-30 (row 10: `patch_requirement` audit; rows 13–14: tenant delivery `Enq`; appendix: outcome engine coverage).

**Authority:** `sync_compliance_gaps_for_requirement` (`compliance_gap_sync.py`) — optional `audit_lifecycle` and `run_operational_bridge`; `sync_requirement_evidence_authority` (`requirement_evidence_authority.py`) — rewrites evidence authority then calls gap sync with defaults (**lifecycle + bridge on** unless caller replaces merged row logic). Property score persistence: `compliance_scoring_service.recalculate_and_persist`; async fan-out: `enqueue_compliance_recalc` → worker `recalculate_and_persist`.

**Legend**

| Token | Meaning |
|-------|---------|
| **Y** | Yes / wired for typical success path |
| **N** | Not required for minimal product contract *or* intentionally absent |
| **—** | Not applicable |
| **Enq** | `enqueue_compliance_recalc` (score updates when worker runs) |
| **Sync** | `recalculate_and_persist` in-request (immediate persisted score) |
| **Quiet** | Gap sync runs with `audit_lifecycle=False` and `run_operational_bridge=False` |
| **Partial** | Some sub-paths or downstream jobs differ; see notes |
| **Var** | Varies by flags / payload (documented in notes) |

---

## Matrix (minimum required paths)

Rows reflect **main** success paths as of the matrix authoring pass. Sub-routes (e.g. ZIP vs single upload) share the same fan-out pattern unless noted.

| # | Mutation path | Primary surface | Mutation type | Gap sync required? | Gap sync today? | Recalc required? | Recalc today? | Audit required? | Audit today? | Notification / reminder impact | Stale-state risk | Missing-wiring risk |
|---|----------------|-----------------|-----------------|---------------------|-----------------|------------------|---------------|-------------------|----------------|----------------------------------|------------------|---------------------|
| 1 | Document upload (linked requirement) | `routes/documents.py` (client upload) | INSERT `documents` + evidence upsert | Y (authority drives inference) | Y via `sync_requirement_evidence_authority` after link | Y | Y `Enq` + `provisioning_service._update_property_compliance` | Y | Y `DOCUMENT_UPLOADED` + score event (best-effort) | Async analysis task; digest/score lag until queue | Score/gap until worker; expected | Unlinked upload skips authority (see row 2) |
| 2 | Document upload (no `requirement_id`) | `routes/documents.py` | INSERT `documents` | N for requirement gaps | N (no authority sync) | Y property-level | Y `Enq` + provisioning touch | Y | Y `DOCUMENT_UPLOADED` | Same | Property score may refresh before requirement gaps reconcile | Later link/match must trigger authority |
| 3 | Document bulk / ZIP upload (matched requirement) | `routes/documents.py` | INSERT + match | Y | Y per matched `sync_requirement_evidence_authority` | Y | Y `Enq` per uploaded doc + bulk audit | Y | Y bulk + per-file score events (best-effort) | High volume → queue backlog | Same as row 1 |
| 4 | Admin document upload | `routes/documents.py` (admin upload) | INSERT + evidence upsert | Y | Y `sync_requirement_evidence_authority` | Y | Y `Enq` `TRIGGER_ADMIN_UPLOAD` | Y | Y `ADMIN_ACTION` metadata | Same | Same |
| 5 | Document delete (client / admin) | `routes/documents.py` `delete_document` / `admin_delete_document` | DELETE `documents` | Y | Y via `_revert_requirement_if_no_verified_docs` → `sync_requirement_evidence_authority` when `requirement_id` | Y | Y `Enq` | Y | Y `DOCUMENT_DELETED_*` | Reminder/due logic may shift on revert | Delete **without** `requirement_id`: no authority sync; property `Enq` only |
| 6 | Document verify (admin route) | `routes/documents.py` verify handler | UPDATE `documents` + requirement fields | Y | Y `sync_requirement_evidence_authority` | Y | Y `Enq` + provisioning + `apply_action_outcome` → **Sync** score | Y | Y `DOCUMENT_VERIFIED` + enablement (best-effort) | **Double** score path: enqueue + outcome `Sync` — eventual consistency window still possible between calls | Order-dependent UX messaging |
| 7 | Document verify (evidence review v2 helper) | `services/evidence_review_verify.py` | UPDATE doc + optional requirement promote | Y | Y `sync_requirement_evidence_authority` | Y | Y `Enq` + provisioning + outcome **Sync** | Y | Y `DOCUMENT_VERIFIED` | Same as row 6 | Same |
| 8 | Document reject (admin) | `routes/documents.py` `reject_document` | UPDATE status REJECTED | Y | Y via `_revert_requirement_if_no_verified_docs` when linked | Y | Y `Enq` | Y | Y `DOCUMENT_REJECTED` | Depends on reminder rules on status | If `requirement_id` missing: no authority path |
| 9 | Evidence authority sync (standalone) | `requirement_evidence_authority.sync_requirement_evidence_authority`; call sites: `routes/admin.py`, `routes/client_compliance_evidence.py`, scripts | Recompute `evidence_authority` blob | Y | Y (includes gap sync) | Partial | **N** unless caller also `Enq` / `Sync` | Partial | Partial (not all callers audit authority itself) | None by default | Gap/score vs authority until separate recalc | Admin bulk doc ops: easy to forget `Enq` after batch sync |
|10 | Requirement update (client PATCH) | `routes/properties.py` `patch_requirement` | UPDATE `requirements` | Y | Y `sync_requirement_evidence_authority` after patch | Y | Y `Enq` | Partial | **Y** `REQUIREMENT_ACTION_TRIGGERED` (`event=client_patch_requirement`, `correlation_id=REQUIREMENT_UPDATED:{requirement_id}`) after sync, before enqueue (**Stream E micro-PR 2**) | Score event best-effort | Low until next read | — |
|11 | Property jurisdiction / metadata / applicability PATCH | `routes/properties.py` `patch_property` | UPDATE `properties` + optional materialization | Y (inferred gaps should match new obligations) | **Y** when materialisation succeeds: `_sync_compliance_gaps_for_property_requirements_after_materialization` runs `sync_compliance_gaps_for_requirement` per requirement (default lifecycle/bridge) (**Stream E2.3**). Skipped if materialisation throws. | Y | Y `Sync` on jurisdiction change; `Enq` on applicability-only change | Partial | Partial (not every field change audited) | Materialization may change obligations → reminders | Low once sweep runs | Very large properties capped at 500 requirements per sweep |
|12 | Applicability operator command | `services/applicability_operator_actions.py` | UPDATE applicability / provenance fields | Y | Y **Quiet** (`audit_lifecycle=False`, `run_operational_bridge=False`) | Partial | **N** on path (separate queue/policy may recalc) | Y | Y `applicability_resolution_audit` append | No gap-open noise (by design) | **Operational bridge off** — issues not auto-created/closed from this sync | Operators must not assume gap-issue parity here |
|13 | Tenant delivery proof (initiate → send success) | `services/tenant_delivery_proof_service.py` | INSERT/UPDATE proof + UPDATE `requirements` flags | Y | Y direct `sync_compliance_gaps_for_requirement` per covered `requirement_id` | Y | Y **`Enq`** after **≥1** successful gap sync (`enqueue_property_recalc_after_tenant_delivery_gap_batch` → `TENANT_DELIVERY:{delivery_id}`) | Y | Y `TENANT_DELIVERY_*` audits | Governed email + message_logs | Residual until worker drains queue (same as other `Enq` paths) | If **all** gap syncs fail: **no** `Enq`; send fail path unchanged |
|14 | Tenant delivery proof (provider / reconciliation) | `services/tenant_delivery_reconciliation.py` | UPDATE proof + requirement mirror | Y | Y `sync_compliance_gaps_for_requirement` | Y | Y **`Enq`** when `_sync_requirements_for_proof` runs **≥1** successful sync (same helper; webhook/ack: `ACTOR_SYSTEM` vs tenant ack: `ACTOR_CLIENT`) | Partial | Partial (`create_audit_log` on some transitions) | Webhook-driven | Same as row 13 | Open-only log path: **no** `_sync` → **no** `Enq`; empty `requirement_ids_covered`: no sync |
|15 | Gap reconciliation / backfill (batch) | `services/compliance_gap_backfill.py`; `scripts/backfill_compliance_gaps.py` | Upsert/resolve `compliance_gaps` | Y | Y (configurable `audit_lifecycle`; summary audit when quiet) | Partial | **N** unless paired job | Partial | Y batch summary when configured | Ops noise if `audit_lifecycle=True` at scale | Dry-run vs live mismatch |
|16 | Policy gap reconciliation (tenant job) | `services/compliance_policy_backfill_service.py` `run_tenant_gap_policy_reconciliation` | UPDATE open gap policy snapshots | Partial | **Different** — not full `sync_compliance_gaps_for_requirement`; inference patch on rows | N | **N** | N | Dead-letter / checkpoint metadata | Batch job | Open gaps without inferred match → dead-letter | Does not replace runtime gap sync |
|17 | Work order completion (compliance-aware) | `services/maintenance_service.py` → `compliance_outcome_engine.apply_action_outcome` | WO state + outcome log | Y | **Partial** — authority+gap refresh when `_set_requirement_compliant` runs (**Stream E2.1**); other `apply_action_outcome` branches unchanged | Y | Y **Sync** `recalculate_and_persist` + risk regen hook | Partial | **N** dedicated WO→compliance audit in engine | Client proof emails on evidence append | WO path without compliant-set: unchanged | Other outcome event types still omit authority refresh |
|18 | Maintenance issue resolved / closed | `services/maintenance_issues_service.py` → `apply_action_outcome` | UPDATE issue + outcome | Partial | Same as row 17 | Y | Y **Sync** | Y | Y issue status audit | Depends on linked WO/compliance | Same as row 17 | — |
|19 | Score repair / admin validate compliance score | `routes/admin.py` `validate_compliance_score` | Diagnostic / `fix=true` repair | Partial | **N** direct (recalc reads DB truth) | Y | Y `Sync` when `fix=true` | Y | Y mismatch + repaired + score updated audits (Stream B) | None | Compare + recalc **double** scoring cost |
|20 | Admin “recalculate compliance” for all properties | `routes/admin.py` `admin_action_recalculate_compliance` | Fan-out `Enq` | N | N | Y | Y `Enq` per property | Y | Y `ADMIN_ACTION` | Queue flood | Depends on worker capacity |
|21 | Mark requirement not applicable (workflow API) | `routes/api_compliance_workflow.py` | UPDATE `requirements` | Y | **Y** — `sync_requirement_evidence_authority` after successful update, before audit + `enqueue_compliance_recalc` (**Stream E2.2**) | Y | Y `Enq` | Y | Y `REQUIREMENT_ACTION_TRIGGERED` | WO cancel side-effects in same flow | Residual until worker processes `Enq` | — |
|22 | Reopen requirement (workflow API) | `routes/api_compliance_workflow.py` `reopen_requirement` | UPDATE `requirements` | Y | **Y** — same as row 21 (**Stream E2.2**) | Y | Y `Enq` | Y | Y `REQUIREMENT_ACTION_TRIGGERED` | Reminders may resume | Residual until worker | — |

---

## Cross-cutting notes

1. **Quiet operator gap sync** — Documented intentional pattern: `applicability_operator_actions` calls `sync_compliance_gaps_for_requirement(..., audit_lifecycle=False, run_operational_bridge=False)` so gap rows refresh without `COMPLIANCE_GAP_*` lifecycle noise and without idempotent issue bridge writes. Forensics: applicability audit + requirement row diffs (`CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md`).

2. **Outcome engine** — `compliance_outcome_engine.apply_action_outcome` runs `recalculate_and_persist` and risk heuristics. For **`EVENT_CERTIFICATE_VERIFIED`** and **`EVENT_REQUIREMENT_COMPLETED`**, after `_set_requirement_compliant` it calls **`sync_requirement_evidence_authority`** per affected requirement (authority + default gap sync) **before** scoring (**Stream E2.1**). Other event types (e.g. **`EVENT_WORK_ORDER_COMPLETED`** without compliant-set) still do **not** run that authority refresh on the outcome path — persisted gaps vs score can diverge until another mutation runs gap sync.

3. **Enqueue vs synchronous recalc** — Most routes use `enqueue_compliance_recalc`; property jurisdiction patch and outcome engine use synchronous `recalculate_and_persist` (or both). Dashboards may show queue lag for **Enq-only** paths.

4. **Evidence authority as hub** — For document-centric paths, `sync_requirement_evidence_authority` is the **normal** way to get gap sync + authority alignment together. Paths that update `requirements` without it should be flagged in Stream E phase 2 (includes workflow API rows 21–22 vs `patch_requirement` row 10).

5. **Tenant delivery score convergence** — After tenant-delivery-driven gap sync, **`enqueue_property_recalc_after_tenant_delivery_gap_batch`** enqueues **one** recalc per property per batch with **`correlation_id`** `TENANT_DELIVERY:{delivery_id}` and **`TRIGGER_PROPERTY_UPDATED`** (no synchronous `recalculate_and_persist` on the delivery path). Skipped when no requirement row sync succeeds.

---

## Appendix — Outcome engine (`compliance_outcome_engine.apply_action_outcome`) event coverage

**Purpose:** Freeze **current** branching as of Stream E2.1+ for support and code review. **Source of truth:** `services/compliance_outcome_engine.py` (`ALL_EVENTS`). This appendix is **not** a mutation matrix row substitute; it documents the **outcome** subsystem only.

**Scope notes**

- **Idempotency:** If `compliance_activity_log` already has the `dedupe_key`, the handler returns early — no requirement mutation, no sync, no recalc (not shown in the table).
- **`requirement_type`:** For `certificate_verified` and `requirement_completed`, `_set_requirement_compliant` and `_sync_requirement_evidence_authority_after_compliant_set` **no-op** (no DB writes / no sync calls) when `requirement_type` is empty; **`_mark_related_risk_resolved` still runs** for those event types when `requirement_type` is empty.
- **Post-score hook:** `_sync_regenerate_risks_and_operational` is **always awaited** after `recalculate_and_persist` on the non-idempotent path; it **returns immediately** when predictive-maintenance flags are off (no risk regen).

| `event_type` | Mutates `requirements` (inside engine) | Syncs evidence authority → gap sync (inside engine) | Touches `risk_signals` before score | `recalculate_and_persist` | Post-score risk regen hook | Known persisted gap vs score skew (engine-only narrative) |
|--------------|----------------------------------------|-----------------------------------------------------|-------------------------------------|---------------------------|----------------------------|----------------------------------------------------------------|
| `certificate_uploaded` | No | No | No | Yes | Yes (may no-op) | **Low–medium** — relies on other mutations (e.g. document routes) for gap refresh; engine only recalculates. |
| `certificate_verified` | **Yes** if non-empty `requirement_type` (`COMPLIANT` set); else **no** | **Yes** — one `sync_requirement_evidence_authority` per matched requirement row (cap 500) if `requirement_type` set; else **no** | **Yes** — `_mark_related_risk_resolved` always in this branch | Yes | Yes (may no-op) | **Medium** when `requirement_type` empty: score recalc **without** engine-driven gap refresh. |
| `requirement_completed` | Same as `certificate_verified` | Same | Same | Yes | Yes (may no-op) | Same as `certificate_verified`. |
| `issue_created` | No | No | No | Yes | Yes (may no-op) | **Medium** — no engine authority sync; gaps update only via other paths. |
| `issue_resolved` | No | No | **Yes** — `_mark_related_risk_acknowledged` | Yes | Yes (may no-op) | **Medium** — same pattern as non-compliant-set outcomes. |
| `work_order_completed` | No | No | **Yes** only if `metadata.resolve_linked_compliance_risks`; else **no** | Yes | Yes (may no-op) | **High** when WO implies obligation/evidence change but **no** engine authority sync (Stream E cross-cutting note §2). |
| `risk_signal_acknowledged` | No | No | **Yes** — `_mark_related_risk_acknowledged` | Yes | Yes (may no-op) | **Low–medium** — risk layer only; compliance gaps unchanged by this branch. |
| `risk_signal_resolved` | No | No | **Yes** — `_mark_related_risk_resolved` | Yes | Yes (may no-op) | **Low–medium** — same. |

**Contract tests:** `tests/test_compliance_outcome_engine_event_coverage.py` asserts `ALL_EVENTS` matches a frozen set and that **call counts** for requirement updates, authority sync, pre-recalc risk updates, and `recalculate_and_persist` match this table for canonical payloads. Changing behaviour requires updating **both** this appendix and that test.

---

## Change control

New mutation paths that can change obligation posture, gaps, or scores **must** add a row here (or extend one with explicit sub-rows) in the same PR as the code change, per tracker Stream E acceptance criteria.
