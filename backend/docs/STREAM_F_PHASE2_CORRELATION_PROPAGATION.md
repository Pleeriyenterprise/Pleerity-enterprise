# Stream F Phase 2 — Correlation propagation audit & minimal rules (read-only design)

**Purpose:** Improve **forensic traceability** and **cross-system reconstruction consistency** by documenting where `correlation_id` (and related context) **lives**, where it **breaks**, and what **narrow code slices** may extend propagation — **without** a new event bus, queue redesign, remediation engine, broad schema migration, or new SSOT collection.

**Companion:** `STREAM_F_FORENSICS_JOIN_RECIPE.md`, `STREAM_F_RECONSTRUCTION_CONSISTENCY.md`, `STREAM_E_MUTATION_FANOUT_MATRIX.md`, `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md`, `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` (Stream F).

**Authority:** This document is **governance + gap analysis**; runtime remains defined by named modules (`compliance_recalc_queue`, `job_runner`, `compliance_scoring_service.recalculate_and_persist`, `create_audit_log`, `score_ledger_service.log_score_change`, gap sync, outcome engine).

---

## 1. Correlation propagation matrix

Legend: **Y** = field present / survives next hop in normal path; **P** = partial (some paths only); **N** = not stored on that artefact; **~** = async / time-lagged; **var** = caller-supplied string conventions vary.

| System / artefact | `correlation_id` or equivalent | Survives enqueue → worker? | Survives `recalculate_and_persist`? | Join to `audit_logs` `COMPLIANCE_SCORE_UPDATED` | Join to `score_ledger_events` | `score_change_log` / `property_compliance_score_history` | Notes |
|-------------------|------------------------------|----------------------------|--------------------------------------|--------------------------------------------------|-------------------------------|------------------------------------------------------------|-------|
| **`audit_logs`** (general) | `metadata.correlation_id` when callers set it | N/A | N/A | Self; merge `metadata` with `**(context or {})` on score update | Via ledger/audit time window | **P** — strong to score rows when same id on `score_change_log` / history (**F2-A**); else weak (`property_id` + time + `reason`) | Many actions have **no** correlation_id (by design today). |
| **`score_change_log`** | **P** — optional `correlation_id` on insert when `recalculate_and_persist` context supplies it (**F2-A**, 2026-04-30); omitted when absent | N/A | **P** — same as context | Strong when id present on row + audit/ledger | Strong when id present | Self | Legacy rows and callers without id: join via time + `reason` + score pair. |
| **`property_compliance_score_history`** | **P** — optional `correlation_id` when context supplies (**F2-A**); else absent | N/A | **P** | Strong when id present | Strong when id present | Self | Same partial model as `score_change_log`. |
| **`score_ledger_events`** | **Y** when `log_score_change(..., correlation_id=...)` | N/A | **Y** from `context["correlation_id"]` | Strong when audit metadata also had same id | Self | Weak | Idempotent skip when same `(client_id, property_id, correlation_id)` re-logged. |
| **`compliance_gaps` lifecycle** (`COMPLIANCE_GAP_*`) | **N** in gap open/resolve metadata today | N/A | N/A | Per-event metadata has `gap_key` / `requirement_id` / `property_id` | N/A | N/A | Stable join is **`gap_key`** / `requirement_id`, not correlation_id. |
| **`work_orders`** | **var** in some maintenance → score paths (e.g. `work_order_completed:{id}` on evidence upload) | P | P | P | P if passed into recalc context | **P** if recalc context forwarded (**F2-A**) | WO row itself may carry ids; correlation is **path-specific**; not all WO→score paths enqueue with id. |
| **`maintenance_issues`** | Bridge / outcome paths vary | P | P | P | P | **P** when outcome/recalc supplies id (**F2-A** + **F2-B**) | Operational joins per `STREAM_C` runbook (`operational_root_key`). |
| **Tenant delivery flows** | **`TENANT_DELIVERY:{delivery_id}`** on enqueue after gap batch | **Y** — stored on `compliance_recalc_queue` doc | **Y** — `job_runner` passes `context={"correlation_id": job["correlation_id"], ...}` | **Y** — metadata spread includes `correlation_id` | **Y** when context passed | **Y** when same context reaches inserts (**F2-A**) | Strong enqueue → score **audit/ledger/history/change_log** when worker forwards id. |
| **`compliance_recalc_queue` jobs** | **Y** — `correlation_id` on job document | **Y** — worker reads job | **Y** — into `recalculate_and_persist` context | **Y** | **Y** | **Y** when context forwarded (**F2-A**) | Dedupe key `(property_id, correlation_id)` per `enqueue_compliance_recalc`. |
| **Outcome engine** (`compliance_outcome_engine` → `recalculate_and_persist`) | **Y (2026-05-01 F2-B)** — `context["correlation_id"]` from caller / `metadata.correlation_id` / ecosystem heuristics / `ACTION_OUTCOME:{dedupe_key}`; persisted on **`compliance_activity_log`** insert | N/A (sync path) | **Y** → ledger + `COMPLIANCE_SCORE_UPDATED` metadata | **Y** when id present | **Y** | **Y** on history/change_log when F2-B-resolved id in context (**F2-A**) | WO/doc/issue/risk strings align with maintenance/evidence logs where ids known. |
| **Workflow API** (mark-not-applicable / reopen) | **`MARK_NOT_APPLICABLE:{rid}`** / **`REOPEN_REQUIREMENT:{rid}`** on enqueue | **Y** | **Y** through queue worker | **Y** | **Y** | **Y** when queue context forwarded (**F2-A**) | Same model as tenant delivery row. |
| **`patch_requirement`** | **`REQUIREMENT_UPDATED:{requirement_id}`** | **Y** | **Y** | **Y** | **Y** | **Y** when context forwarded (**F2-A**) | Covered by matrix row 10 + HTTP tests. |
| **Admin repair** | **`ADMIN_VALIDATOR_REPAIR:{property_id}:{uuid}`** | Sync `recalculate_and_persist` | **Y** | **Y** (mismatch + repaired + updated share) | **Y** | **Y** — repair correlation on inserts (**F2-A**) | Enterprise tests assert propagation into recalc context + audits. |

---

## 2. Broken or weak reconstruction chains

### 2.1 Enqueue → worker → score update

- **Strong:** `compliance_recalc_queue.correlation_id` → `job_runner` context → `recalculate_and_persist` → **`COMPLIANCE_SCORE_UPDATED.metadata`** (full `context` merge) and **`score_ledger_events.correlation_id`**.
- **Partial (F2-A, 2026-04-30):** when `context["correlation_id"]` is non-empty, the same value is written on **`property_compliance_score_history`** and **`score_change_log`** inserts (new rows only; no backfill). When callers omit id or pass blank/whitespace-only, those collections behave as before (no field).
- **Weak (legacy / no id):** rows without `correlation_id` still bridge via ledger/audit or `reason` + timestamp.

### 2.2 Gap sync → recalc

- Gap lifecycle audits use **`gap_key` / `requirement_id`** — no shared correlation_id with score.
- Recalc enqueue from gap-adjacent mutations often uses **trigger-specific** correlation (`REQUIREMENT_UPDATED:…`, `TENANT_DELIVERY:…`) or **timestamp fallback** when caller omits id (`enqueue_compliance_recalc` default).
- **Risk:** two different “stories” (gap open vs score move) tied only by **time + property**, not one id.

### 2.3 Outcome engine flows

- **F2-B shipped (2026-05-01):** `apply_action_outcome` sets **`correlation_id`** on `recalculate_and_persist` context (precedence: top-level → `metadata.correlation_id` → type-specific `work_order_completed:` / `certificate_verified:` / … → `ACTION_OUTCOME:{dedupe_key}`). **`compliance_activity_log`** rows now include **`correlation_id`** for the same application id.
- **F2-A shipped (2026-04-30):** optional **`correlation_id`** on **`score_change_log`** and **`property_compliance_score_history`** inserts when context supplies a non-empty string; no minting inside scoring.

### 2.4 Admin repair flows

- **Strong** across mismatch → repair → `COMPLIANCE_SCORE_UPDATED` when using shared repair correlation (see `routes/admin.py`); **F2-A** persists the same id on history/change_log when present in `recalculate_and_persist` context.

### 2.5 Tenant delivery recalc

- **Strong** for enqueue + worker + audit/ledger; **strong** on history/change_log when job `correlation_id` is forwarded into recalc context (**F2-A**).

### 2.6 Workflow reopen / mark-not-applicable

- Correlation id on **enqueue** is stable per requirement action; **F2-A** persists it on `score_change_log` / history when the worker passes it through context (same as queue paths).

---

## 3. Minimal propagation rules (design)

1. **Create `correlation_id` when** a user-visible or support-critical **mutation span** crosses **async** boundary (`enqueue_compliance_recalc`) **and** product wants idempotent dedupe or audit pairing — use **existing string conventions** (`SCOPE:entity`) per `STREAM_C` / matrix docs.
2. **Preserve `correlation_id` when** handing work to **`job_runner`** — always pass through `context` unchanged (already true for queue jobs).
3. **Do not mint a second “root” id** for the same user action — prefer **propagating** the enqueue id into `recalculate_and_persist` rather than generating a fresh UUID inside the worker (admin repair is explicit exception: single repair session id is intentional).
4. **Async expectations:** audits/ledger may trail mutation audits by **queue latency**; `COMPLIANCE_SCORE_UPDATED` is authoritative for “score persisted”, not ordering vs document audit timestamp alone.
5. **Retry / idempotency:** `compliance_recalc_queue` dedupes on `(property_id, correlation_id)`; ledger skips duplicate `correlation_id` per property/client — **re-using** the same correlation on unrelated mutations is a product bug, not infra retry noise.

---

## 4. Narrow implementation slices (proposals — not implemented in this doc PR)

Allowed (small, targeted):

| Slice | Change | Touches |
|-------|--------|---------|
| **F2-A** | ~~Add optional `correlation_id` to `score_change_log` + `property_compliance_score_history` **only when** `context` provides it~~ — **Done (2026-04-30):** `recalculate_and_persist`; tests in `test_stream_f_correlation_propagation_contract.py`. | `compliance_scoring_service.py` |
| **F2-B** | ~~Outcome engine: `context["correlation_id"]` + activity log field~~ — **Done (2026-05-01):** `compliance_outcome_engine._resolve_outcome_correlation_id`; tests in `test_compliance_outcome_engine.py`. | `compliance_outcome_engine.py` |
| **F2-C** | Gap lifecycle audits: optional `metadata["correlation_id"]` propagated from caller when sync invoked as part of a known parent operation (operator batch id) — **default unset**. | `compliance_gap_sync.py` call sites |
| **F2-D** | Pass through `document_id` / `requirement_id` on outcome recalc context (already partially supported) **and** document in matrix. | `compliance_outcome_engine.py` |

Forbidden (see programme constraints):

- New event bus, global orchestration framework, distributed tracing platform, central remediation timeline collection, queue schema redesign, score formula changes.

---

## 5. Contract tests

- **`tests/test_stream_f_correlation_propagation_contract.py`** — asserts `recalculate_and_persist` forwards `context["correlation_id"]` into **`log_score_change`**, **`create_audit_log`** metadata, **`property_compliance_score_history.insert_one`**, and **`score_change_log.insert_one`** when non-empty; asserts **no** `correlation_id` key on those inserts when absent or whitespace-only (**F2-A**).
- **`tests/test_compliance_outcome_engine.py`** — F2-B: `apply_action_outcome` passes resolved **`correlation_id`** into `recalculate_and_persist` **context** (caller override, metadata, heuristics, `ACTION_OUTCOME:` fallback).
- Existing: `test_patch_requirement_audit_http.py`, `test_tenant_delivery_and_audit_pack.py`, `test_compliance_scoring_enterprise.py` (admin repair).

---

## Document control

**Owner:** Platform / compliance engineering. **Updates:** When adding slices F2-A / F2-C / F2-D, update this matrix, `STREAM_F_RECONSTRUCTION_CONSISTENCY.md`, `STREAM_F_FORENSICS_JOIN_RECIPE.md` §5/§8, and `STREAM_E_MUTATION_FANOUT_MATRIX.md` cross-cutting notes if fan-out metadata changes.
