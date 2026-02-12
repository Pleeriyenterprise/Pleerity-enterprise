# Document Generation Failure Handling — Code Verification

Verification performed by tracing code paths. References are to **file path** and **function / line** where applicable.

---

## 1) Order + orchestration status on failure

### 1.1 Orchestrator: does it update the order on failure?

**`backend/services/document_orchestrator.py` — `execute_full_pipeline`**

- On every early return (`success=False`), the orchestrator **only returns** `OrchestrationResult(...)`. It does **not** call `db.orders.update_one` to set `orchestration_status` or `status`.
- Order updates in the orchestrator occur only on the success path:
  - Line 327–330: `orchestration_status` → `INTAKE_LOCKED`
  - Line 371–374: `orchestration_status` → `GENERATING`
  - Line 443–446: `orchestration_status` → `RENDERING`
  - Lines 562–578: Step 9 — `orchestration_status` → `REVIEW_PENDING`, `document_versions`, etc.

So when the pipeline fails (invalid JSON, schema mismatch, managed prompt misconfiguration, render failure, etc.), the order is left with the **last** `orchestration_status` set (e.g. `GENERATING` or `INTAKE_LOCKED`).

**Gap:** The orchestrator **never** sets `orders.orchestration_status` to `FAILED` (or any terminal failure state) on any failure path.

---

### 1.2 WF2 — `wf2_queue_to_generation`

**`backend/services/workflow_automation_service.py` — `wf2_queue_to_generation` (lines 355–432)**

- Before calling the orchestrator: line 365–370 — `transition_order_state(..., OrderStatus.IN_PROGRESS, ...)`.
- On `result.success` False (lines 399–419):
  - `transition_order_state(order_id, OrderStatus.FAILED, reason=f"WF2: Document generation failed: {result_error}")` is called.
- **`backend/services/order_service.py` — `transition_order_state` (lines 169–199):**
  - Sets `update_fields["status"] = new_status.value` → **orders.status = FAILED**.
  - When `new_status == OrderStatus.FAILED` and `reason`: sets `failure_reason` and `failed_at` on the order (lines 191–194).

**Verified:**

- **orders.status** is set to **FAILED** (order is not left in IN_PROGRESS).
- **Failure reason** is persisted on the order as **orders.failure_reason** (and **orders.failed_at**).

**Gap:**

- **orders.orchestration_status** is **not** updated by `transition_order_state`. That function only sets `status`, `updated_at`, and (for FAILED) `failure_reason` and `failed_at`. So after a WF2 failure, **orchestration_status** remains **GENERATING** (or INTAKE_LOCKED if failure was very early).

---

### 1.3 Admin orchestration endpoints

**`backend/routes/orchestration.py`**

- **POST /generate** (lines 55–105): calls `execute_full_pipeline`; on `not result.success` (lines 83–87) only **raises HTTPException(400, detail=result.error_message)**. No order update.
- **POST /regenerate** (lines 108–154): same — on `not result.success` (lines 135–139) only raises HTTPException. No order update.

So when admin triggers generate/regenerate and the pipeline fails:

- The order is **not** transitioned to FAILED.
- **orchestration_status** stays **GENERATING** (or INTAKE_LOCKED / RENDERING) because the orchestrator had already set it and never sets FAILED.
- **No** failure reason is written to the order (no `failure_reason`, no dedicated error field).

**Gap:** Admin orchestration path does **not** set `orders.status` to FAILED, does **not** set `orders.orchestration_status` to FAILED, and does **not** persist the failure reason on the order.

---

### 1.4 Regeneration flow (WF4)

**`backend/services/workflow_automation_service.py` — `wf4_regeneration` (lines 488–576)**

- Before orchestrator: line 503–508 — `transition_order_state(..., OrderStatus.REGENERATING, ...)`.
- On `result.success` False (lines 554–563):
  - `transition_order_state(order_id, OrderStatus.INTERNAL_REVIEW, reason=f"WF4: Regeneration failed: {result_error}")`.
- So the order is moved back to **INTERNAL_REVIEW**, not to FAILED.

**Verified:**

- Order is **not** left in REGENERATING; it is explicitly set back to INTERNAL_REVIEW.
- The failure reason is passed as `reason` into `transition_order_state`, which stores it in **workflow_executions** (audit record) and in the transition audit; it is **not** stored as **orders.failure_reason** because that is only set when `new_status == OrderStatus.FAILED` (order_service.py lines 191–194).

**Gap:**

- **orders.orchestration_status** is never set to FAILED; it remains **REGENERATING** (or whatever the orchestrator last set).
- **orders.failure_reason** is not set (status is INTERNAL_REVIEW, not FAILED).

---

### 1.5 Summary: paths where success=False but order can be misleading

| Path              | orders.status after failure | orders.orchestration_status after failure | failure reason on order? |
|-------------------|----------------------------|------------------------------------------|---------------------------|
| WF2               | FAILED ✓                   | Left as GENERATING (or earlier) ✗        | Yes (failure_reason) ✓    |
| Admin /generate   | Unchanged ✗                | Left as GENERATING (or earlier) ✗        | No ✗                      |
| Admin /regenerate | Unchanged ✗                | Left as GENERATING / RENDERING ✗         | No ✗                      |
| WF4               | INTERNAL_REVIEW ✓          | Left as REGENERATING ✗                    | No (only in audit) ✗       |

So:

- There **are** paths where orchestration returns `success=False` but the order remains in a misleading state: **Admin** (status and orchestration_status not terminal, no error on order) and **all paths** leave **orchestration_status** other than FAILED (often GENERATING/REGENERATING).

---

## 2) Minimal error metadata logging (debug + support)

### 2.1 Where error metadata is persisted today

- **WF2 failure**
  - **orders**: `failure_reason` (string, includes error message), `failed_at` (timestamp). **Not** stored: service_code, doc_type, prompt_version_used.
  - **workflow_executions** (order_service.py `create_workflow_execution`, lines 251–269): `order_id`, `previous_state`, `new_state`, `reason` (same string as failure_reason), `created_at`. **Not** stored: service_code, doc_type, prompt_version_used.

- **Admin generate/regenerate failure**
  - **Nothing** is persisted to orders or to any dedicated error/audit record. The error is only returned in the HTTP response.

- **WF4 regeneration failure**
  - **workflow_executions**: transition to INTERNAL_REVIEW with `reason` (failure message), `order_id`, `created_at`. **Not** on order; **not** in orchestration_executions.

- **orchestration_executions**
  - **Only written on success** (document_orchestrator.py Step 8, line 522: `await db[self.COLLECTION].insert_one(execution_record)`). So **no** failed run is recorded there (no order_id, service_code, doc_type, prompt_version_used, error_message, timestamp for failures).

**Gap:** The requested minimal set (order_id, service_code, doc_type, prompt_version_used, error_message, timestamp) is **not** consistently persisted for failures. Only WF2 gives order_id + human-readable message + timestamp (on order and in workflow_executions); service_code, doc_type, and prompt_version_used are not stored for any failure path.

### 2.2 Raw intake / raw LLM output

- **document_orchestrator.py**: On failure it only returns `OrchestrationResult`; it does **not** write to DB. No intake or raw LLM output is written to orders, orchestration_executions, or any other collection on failure.
- **Logger**: Failure branches use e.g. `logger.error(f"GPT response was not valid JSON for {order_id}")` / `logger.error(f"GPT returned parse-error wrapper for {order_id} - rejecting")` — no intake data and no raw LLM response in the log message.

**Verified:** Raw intake and raw LLM output are **not** logged/persisted on failure.

### 2.3 Traceability per order without reading logs

- **WF2**: Possible by querying **orders** (`failure_reason`, `failed_at`) and **workflow_executions** by `order_id` (reason, created_at). No structured service_code/doc_type/prompt_version_used.
- **Admin**: No persisted record of the failure; not traceable without logs.
- **WF4**: Traceable via **workflow_executions** (order_id, reason, created_at) but not via a single “last error” on the order.

---

## 3) Tier 2 explicitly deferred

Checked in code (no Tier 2 work started):

- **Idempotency**
  - **document_orchestrator.py**: No idempotency key, no idempotency check. Grep for `idempotency`: no matches.
  - **workflow_automation_service.py**: No idempotency for document generation. ✓

- **Retry / backoff**
  - **document_orchestrator.py**: No retry or backoff. Grep for `retry`/`backoff`: no matches.
  - **workflow_automation_service.py**: Retry/backoff only for **delivery** (WF8, `delivery_retry_count`, `MAX_DELIVERY_RETRIES`), not for document generation. ✓

- **Job queue refactor**
  - Document generation is still triggered by the same call paths (WF2, WF4, admin endpoints); no new job queue or worker refactor for document generation. ✓

**Confirmed:** Tier 2 (idempotency keys, retry/backoff for generation, job queue refactor) has **not** been started.

---

## 4) Structured summary (as requested)

| Check | Result |
|-------|--------|
| **Failure sets order + orchestration status correctly** | ✗ **Gap.** Orchestrator never sets `orchestration_status` to FAILED. No caller sets `orchestration_status` to FAILED. WF2 sets **orders.status** to FAILED and **failure_reason**; admin and WF4 do not set status to FAILED; WF4 returns to INTERNAL_REVIEW. |
| **No path leaves orders stuck in IN_PROGRESS** | ✓ **WF2:** transition to FAILED (workflow_automation_service.py 401–406). ✗ **Admin:** order never moved to IN_PROGRESS by the route, but if it were, it would stay; and **orchestration_status** can stay GENERATING. |
| **Error metadata persisted** | **Partial.** WF2: order_id + error message + timestamp on **orders** (failure_reason, failed_at) and in **workflow_executions** (reason, created_at). **Not** persisted: service_code, doc_type, prompt_version_used for any failure; admin path persists nothing. |
| **Raw intake / raw LLM not logged** | ✓ Verified: no DB write on failure; log messages do not include intake or raw LLM output. |
| **Errors traceable per order without logs** | **Partial:** WF2 and WF4 via workflow_executions + (WF2 only) orders.failure_reason; admin path not traceable without logs. |
| **Tier 2 not started** | ✓ Confirmed: no idempotency keys, no retry/backoff for doc gen, no job queue refactor. |

---

## 5) Recommended next steps (for implementation later)

1. **Orchestrator:** On every failure path before returning `OrchestrationResult(success=False, ...)`, add a single `db.orders.update_one` to set `orchestration_status: "FAILED"` and a single error field (e.g. `orchestration_error` or `last_orchestration_error`) with `error_message` and optionally `updated_at`.
2. **Admin endpoints:** On `not result.success`, before raising HTTPException, update the order (e.g. set `orchestration_status` to FAILED and persist `result.error_message` on the order and/or in a failure record).
3. **WF4:** Consider either (a) setting `orchestration_status` to FAILED on regeneration failure and optionally keeping status as INTERNAL_REVIEW, or (b) persisting the regeneration failure reason on the order (e.g. `last_orchestration_error`) so it’s visible without querying workflow_executions.
4. **Failure audit record:** Consider inserting a minimal failure record (e.g. into `orchestration_executions` with a `status: "FAILED"` and fields: order_id, service_code, doc_type, prompt_version_used, error_message, timestamp) so support can trace errors per order without scanning logs.
