# Workflow Engine Audit – Four Services (AI Automation, Market Research, Compliance, Document Packs)

**Purpose:** Check the codebase against the task requirements for the workflow engine. Identify what is implemented, what is missing, and any conflicts. Do not implement blindly; propose the safest option where there are gaps or conflicting instructions.

---

## 1. Task Requirements (Summary)

| Requirement | Detail |
|-------------|--------|
| State machine | Allowed transitions defined and enforced |
| Background job runner | BullMQ + Redis **OR** simple Render cron + queue collection (pick one) |
| Transition audit | Each transition writes a **workflow_events** record |
| Failures | Create **FAILED** state with **reason** |
| Jobs | payment_to_queue, queue_to_generate, generate_to_review, review_to_deliver, deliver_to_complete |
| Admin fallback | Endpoints to **retry job**; endpoints to **force transition** (reason required, audit logged) |
| Frontend | Admin pipeline **Kanban** with **counts per stage**; stages **clickable** to list orders; **real-time updates** via polling (websocket optional later) |

---

## 2. What Is Implemented

### 2.1 State machine with allowed transitions

- **Location:** `backend/services/order_workflow.py`
- **Content:** `OrderStatus` enum (14 states), `ALLOWED_TRANSITIONS` dict (whitelist), `is_valid_transition()`, `get_allowed_transitions()`, `requires_admin_action()`, `ADMIN_ONLY_TRANSITIONS`, `TERMINAL_STATES`, `SLA_PAUSED_STATES`, `PIPELINE_COLUMNS`.
- **Enforcement:** `order_service.transition_order_state()` is the single place that updates order status; it validates via `is_valid_transition()` and `requires_admin_action()` before updating.
- **Verdict:** Implemented.

### 2.2 Background job runner (cron + queue, no BullMQ/Redis)

- **Location:** `backend/job_runner.py`, `backend/server.py`
- **Mechanism:** **APScheduler** (AsyncIOScheduler) with CronTrigger/IntervalTrigger. No BullMQ, no Redis. Jobs are registered in `JOB_RUNNERS` and run via `make_instrumented(job_id, "schedule")`. Execution is recorded in `job_runs` (job_run_service) for observability.
- **Queue semantics:** The “queue” is the **orders** collection: orders in status `QUEUED`, `DRAFT_READY`, or `REGEN_REQUESTED` are processed by the **queued_order_processing** job (every 10 min). No separate queue collection; orders are the source of work.
- **Verdict:** Implements the “simple Render cron + queue collection” option. No conflict with BullMQ/Redis; the codebase already chose the second option.

### 2.3 Jobs vs task names

| Task job name | Implementation | Notes |
|---------------|----------------|--------|
| payment_to_queue | `wf1_payment_to_queue` | Called from `intake_draft_service.convert_draft_to_order()` after order create. PAID → QUEUED, SLA init, notifications. |
| queue_to_generate | `wf2_queue_to_generation` (+ `wf3_draft_to_review`) | Invoked by **queued_order_processing** cron (and batch `process_queued_orders`). QUEUED → IN_PROGRESS → DRAFT_READY → INTERNAL_REVIEW. |
| generate_to_review | `wf3_draft_to_review` | DRAFT_READY → INTERNAL_REVIEW; also run after WF2 in same batch. |
| review_to_deliver | Admin approve → `transition_order_state(..., FINALISING)`; then **order_delivery_processing** cron | INTERNAL_REVIEW → FINALISING (admin) → DELIVERING (cron) → COMPLETED. |
| deliver_to_complete | `order_delivery_processing` (job_runner) + `order_delivery_service` | FINALISING → DELIVERING → COMPLETED (or DELIVERY_FAILED). |

- **Verdict:** All five job concepts are implemented; naming differs (wf1–wf3, process_queued_orders, order_delivery_processing) but behaviour matches.

### 2.4 Failures → FAILED state with reason

- **Location:** `backend/services/order_service.py` in `transition_order_state()`.
- **Behaviour:** When `new_status == OrderStatus.FAILED` and `reason` is provided, the order is updated with `failure_reason` and `failed_at`. WF2 and other workflow steps call `transition_order_state(..., OrderStatus.FAILED, reason="...")` on failure.
- **Verdict:** Implemented.

### 2.5 Transition audit (workflow_executions vs workflow_events)

- **Current behaviour:** Every transition goes through `transition_order_state()` → `create_workflow_execution()`, which writes to the **workflow_executions** collection (execution_id, order_id, previous_state, new_state, transition_type, triggered_by_*, reason, notes, metadata, timestamp).
- **Task requirement:** “Each transition writes **workflow_events** record.”
- **Gap:** The **workflow_events** collection exists (indexes in `ensure_services_indexes.py`, schema in `services_models.WorkflowEventSchema`, `WorkflowEventRepository` in `repositories/services_repositories.py`), but **no code writes to it**. All transition audit today is in **workflow_executions**.
- **Verdict:** Partially implemented. Audit is done via `workflow_executions`; `workflow_events` is defined but unused.

### 2.6 Admin manual fallback

| Requirement | Implementation |
|-------------|----------------|
| Force transition (with reason, audit) | `POST /api/admin/orders/{order_id}/transition` with body `{ new_status, reason, notes? }`. Enforces allowed transitions and admin-only where required; calls `transition_order_state(..., triggered_by_type="admin", reason=...)` and `create_workflow_execution`. |
| Retry job | **Delivery:** `POST /api/admin/orders/{order_id}/retry-delivery` (calls `order_delivery_service.retry_delivery()`). **Generation:** No dedicated “retry generation” endpoint; admin can move order **FAILED → QUEUED** via the same transition endpoint. Next run of **queued_order_processing** will pick it up. |

- **Verdict:** Force transition is implemented. “Retry job” is satisfied for delivery explicitly and for generation via transition to QUEUED; an explicit “retry generation” endpoint would be optional clarity.

### 2.7 Frontend: Admin pipeline Kanban

- **Location:** `frontend/src/pages/AdminOrdersPage.js`, `frontend/src/components/admin/orders/OrderPipelineView.jsx`, `frontend/src/components/admin/orders/OrderList.jsx`.
- **API:** `GET /api/admin/orders/pipeline` (optional `status`, `limit`, `skip`) returns `{ orders, total, counts }`. `GET /api/admin/orders/pipeline/counts` returns `{ counts, columns }`.
- **Behaviour:** Pipeline view shows columns (Paid, Queued, In Progress, Draft Ready, Review, Awaiting Client, Finalising, Delivering, Completed, Failed) with **counts per stage**. Columns are **clickable** to filter/list orders for that status. **Polling:** `AdminOrdersPage` has `autoRefresh` and `AUTO_REFRESH_INTERVAL` (e.g. 30s) to refetch pipeline data.
- **Verdict:** Implemented (Kanban-style pipeline, counts, clickable stages, polling). Websocket is optional later as per task.

---

## 3. Gaps and Conflicts

### 3.1 workflow_events not written (task: “each transition writes workflow_events record”)

- **Conflict:** Task specifies **workflow_events**; codebase only writes **workflow_executions**.
- **Options:**
  - **A (recommended):** Keep writing **workflow_executions** as today and **additionally** write one record per transition into **workflow_events** (same logical event: order_id, from_status, to_status, transition_type, actor, reason, created_at). Use `WorkflowEventRepository` or a small helper so both collections stay in sync and the task requirement is met without breaking existing consumers of `workflow_executions`.
  - **B:** Treat **workflow_executions** as the canonical “workflow event” store and document in the codebase that “workflow_events” in the task is implemented as **workflow_executions**. Do not introduce a second write. Simpler but does not satisfy the literal “workflow_events” requirement.
- **Safest:** **A** – add a single write to **workflow_events** alongside `create_workflow_execution()` (e.g. inside `create_workflow_execution` or immediately after it in `transition_order_state`), with the same transition data and an `event_id` (e.g. reuse execution_id or generate new). This keeps existing behaviour and adds the required workflow_events record.

### 3.2 Explicit “retry job” endpoint for generation

- **Gap:** Task asks for “endpoints to retry job”. Delivery retry exists; for “retry generation” the flow is: admin moves FAILED → QUEUED via transition, then cron runs. There is no dedicated “retry generation” or “retry job” for orders.
- **Options:**
  - **A:** Add `POST /api/admin/orders/{order_id}/retry-generation` that: (1) ensures order is in FAILED (or DELIVERY_FAILED if you want), (2) transitions to QUEUED with reason “Admin retry generation”, (3) optionally triggers processing for that order (e.g. call `process_queued_orders(limit=1)` with a filter for that order_id, or a new “process_one” helper). This makes “retry job” explicit and auditable.
  - **B:** Rely on existing transition endpoint and document that “retry generation” = transition to QUEUED; no new endpoint.
- **Safest:** **B** is enough for “retry job” (admin can retry via transition). **A** is a small, low-risk improvement if you want a dedicated retry-generation action in the UI.

### 3.3 BullMQ + Redis vs cron + queue

- **No conflict.** Task allows either “BullMQ + Redis” or “simple Render cron + queue collection”. The codebase uses the second (APScheduler + orders as queue). No change needed.

---

## 4. Summary Table

| Requirement | Status | Notes |
|-------------|--------|--------|
| State machine with allowed transitions | Done | `order_workflow.py`, `transition_order_state()` |
| Background job runner (cron + queue) | Done | APScheduler, `queued_order_processing`, `order_delivery_processing`, etc. |
| Each transition writes workflow_events | Gap | Only **workflow_executions** written; **workflow_events** defined but unused |
| Failures → FAILED with reason | Done | `failure_reason` + `failed_at` in `transition_order_state` |
| Jobs: payment_to_queue, queue_to_generate, … | Done | wf1–wf3, process_queued_orders, order_delivery_processing |
| Admin: force transition (reason + audit) | Done | POST `.../transition` with reason |
| Admin: retry job | Partial | retry-delivery exists; “retry generation” = transition FAILED→QUEUED |
| Frontend: Kanban, counts, clickable stages | Done | OrderPipelineView, getPipeline, getPipelineCounts |
| Frontend: real-time via polling | Done | autoRefresh + AUTO_REFRESH_INTERVAL |

---

## 5. Recommended Next Steps (Safest)

1. **workflow_events:** In the same place where `create_workflow_execution()` is called (or inside it), add one insert into **workflow_events** per transition with: event_id, order_id, from_status, to_status, transition_type, actor_id, reason, metadata, created_at. Use existing schema/indexes and avoid breaking any reader of **workflow_executions**.
2. **Retry generation (optional):** Either document that “retry job” for generation is “transition to QUEUED”, or add `POST /api/admin/orders/{order_id}/retry-generation` that performs that transition with a fixed reason and optionally kicks processing for that order.
3. **No change** to state machine, job runner choice, FAILED handling, or frontend pipeline; they already meet the task.

---

## 6. Key File References

| Area | File(s) |
|------|--------|
| State machine | `backend/services/order_workflow.py` |
| Transition + audit | `backend/services/order_service.py` (`transition_order_state`, `create_workflow_execution`) |
| WF1–WF4, batch | `backend/services/workflow_automation_service.py` |
| Delivery | `backend/services/order_delivery_service.py` |
| Jobs | `backend/job_runner.py` (JOB_RUNNERS, run_queued_order_processing, run_order_delivery_processing) |
| Scheduler | `backend/server.py` (queued_order_processing, order_delivery_processing, sla_monitoring) |
| Admin pipeline API | `backend/routes/admin_orders.py` (GET /pipeline, GET /pipeline/counts), `backend/services/order_service.py` (get_orders_for_pipeline, get_pipeline_counts) |
| Admin transition/retry | `backend/routes/admin_orders.py` (POST /{order_id}/transition, POST /{order_id}/retry-delivery) |
| workflow_events (unused) | `backend/models/services_models.py` (WorkflowEventSchema), `backend/repositories/services_repositories.py` (WorkflowEventRepository), `backend/scripts/ensure_services_indexes.py` (indexes) |
| Frontend pipeline | `frontend/src/pages/AdminOrdersPage.js`, `frontend/src/components/admin/orders/OrderPipelineView.jsx`, `frontend/src/api/ordersApi.js` |

---

*Audit only; no code changes. Implement only after approval.*
