# Four Services — MongoDB Models & Repositories Audit

**Purpose:** Check the codebase against the task requirements for MongoDB models (and repositories) for the four services (AI automation, Market research, Compliance services, Document packs). Identify what is implemented, what is missing, and avoid duplication or conflict. No blind implementation.

**Task requirements (summary):**
- Collections: services, intake_submissions, orders, prompt_templates, generation_runs, documents, document_pack_definitions, workflow_events, deliveries, audit_logs
- Mongoose or native driver + typed repositories
- Schemas: required fields, timestamps, indexes (service_code, order_ref, status, created_at), soft delete where needed
- Rules: Orders immutable (no hard delete); Documents versioned (never overwrite); every state change → workflow_event; every admin action → audit_log
- Deliverable: Complete code for models/repositories and an index creation script

---

## 1. Stack and Naming (Conflict Avoidance)

| Task term | Current codebase | Notes |
|-----------|------------------|--------|
| **Mongoose** | Not used | Codebase is **Python** (FastAPI + Motor). Task said "Mongoose or native driver" — we use **native driver (Motor) + Pydantic** for schemas. No Node.js. |
| **services** | `service_catalogue_v2` | Same concept; collection name is `service_catalogue_v2` everywhere. Renaming would break existing code. |
| **intake_submissions** | `intake_drafts` | Pre-payment submissions; drafts become orders after payment. Collection: `intake_drafts`. |
| **documents** | `document_pack_items` + `generated_documents` | Task "documents" for the four services = pack items (per-order) and generated output docs. **Not** the CVP `documents` collection (client uploads). Two collections used on purpose; both are versioned. |
| **orders** | `orders` | Same. order_ref format: `PLE-YYYYMMDD-XXXX` (see `generate_order_ref()` in `intake_draft_service`). |

---

## 2. What Is Implemented

### 2.1 Models (Pydantic schemas)

**File:** `backend/models/services_models.py`

| Collection (task name) | Schema class | Collection in DB | Required fields | Timestamps | Soft delete |
|------------------------|-------------|------------------|-----------------|------------|-------------|
| services | `ServiceSchema` | `service_catalogue_v2` | service_code, category | created_at, updated_at | deleted_at |
| intake_submissions | `IntakeDraftSchema` | `intake_drafts` | draft_id, draft_ref, service_code, status | created_at, updated_at | deleted_at |
| orders | `OrderSchema` | `orders` | order_id, order_ref, source_draft_id, service_code, status | created_at, updated_at, paid_at | — (immutable) |
| prompt_templates | `PromptTemplateSchema` | `prompt_templates` | template_id, service_code, doc_type, status | created_at, updated_at | deleted_at |
| generation_runs | `GenerationRunSchema` | `generation_runs` | run_id, order_id, status | created_at, updated_at | — |
| documents (pack) | `DocumentPackItemSchema` | `document_pack_items` | item_id, order_id, doc_key, doc_type, status | created_at, updated_at | — |
| documents (generated) | `GeneratedDocumentSchema` | `generated_documents` | document_id, order_id, doc_type, version, status | created_at, updated_at | — |
| document_pack_definitions | `DocumentPackDefinitionSchema` | `document_pack_definitions` | doc_key, doc_type, pack_tier, display_name | created_at, updated_at | deleted_at |
| workflow_events | `WorkflowEventSchema` | `workflow_events` | event_id, order_id, to_status | created_at | — |
| deliveries | `DeliverySchema` | `deliveries` | delivery_id, order_id, channel, status | created_at, completed_at | — |
| audit_logs | `AuditLogSchema` | `audit_logs` | audit_id, action | timestamp | — |

All schemas use `model_config = ConfigDict(extra="allow")` so stored documents can carry extra fields. Enums: `OrderStatus`, `DraftStatus`, `GenerationRunStatus`, `DeliveryStatus`.

### 2.2 Typed repositories (Motor + schemas)

**File:** `backend/repositories/services_repositories.py`

| Collection | Repository class | Singleton | Immutable / versioned behaviour |
|------------|------------------|-----------|---------------------------------|
| service_catalogue_v2 | `ServiceRepository` | `service_repository` | get_by_code, get_active_by_code, list_active (no delete in repo) |
| intake_drafts | `IntakeDraftRepository` | `intake_draft_repository` | get_by_id, get_by_ref, insert, update_status |
| orders | `OrderRepository` | `order_repository` | **No delete method** — orders immutable. insert, update_status, get_by_id, get_by_ref, get_by_source_draft_id, get_by_stripe_session_id |
| prompt_templates | `PromptTemplateRepository` | `prompt_template_repository` | get_by_id, list_by_service (filters deleted_at) |
| generation_runs | `GenerationRunRepository` | `generation_run_repository` | insert, get_by_id, list_by_order, update_status |
| document_pack_items | `DocumentPackItemRepository` | `document_pack_item_repository` | insert (new version = new doc), update_status only for status |
| generated_documents | `GeneratedDocumentRepository` | `generated_document_repository` | **insert only** for new versions; no update that overwrites content |
| document_pack_definitions | `DocumentPackDefinitionRepository` | `document_pack_definition_repository` | get_by_key, list_by_tier, insert (soft delete via deleted_at filter) |
| workflow_events | `WorkflowEventRepository` | `workflow_event_repository` | insert only (append-only state changes) |
| deliveries | `DeliveryRepository` | `delivery_repository` | insert, get_by_id, list_by_order, update_status |
| audit_logs | `AuditLogRepository` | `audit_log_repository` | insert, list_by_client, list_by_resource (shared with CVP; use `utils.audit.create_audit_log` for standard entries) |

Repositories use `database.get_db()` and the same collection names as above. OrderRepository has no `delete`; document repositories do not expose an overwrite-by-id update for content (versioning = new insert).

### 2.3 Index creation script

**File:** `backend/scripts/ensure_services_indexes.py`

Indexes created (summary):

- **service_catalogue_v2:** service_code (unique), category, (active, display_order), created_at, deleted_at (sparse)
- **intake_drafts:** draft_id (unique), draft_ref (unique), service_code, status, (status, created_at), created_at, deleted_at (sparse)
- **orders:** pricing.stripe_checkout_session_id (unique, sparse), source_draft_id (unique), order_ref (unique), **(service_code, created_at)**, **(status, created_at)**, created_at
- **prompt_templates:** template_id (unique), (service_code, doc_type, status), (service_code, doc_type, version), status, deleted_at (sparse)
- **generation_runs:** run_id (unique), (order_id, created_at), (status, created_at), created_at
- **document_pack_items:** item_id (unique), (order_id, canonical_index), order_id, status, doc_type, doc_key
- **generated_documents:** document_id (unique), (order_id, version), (order_id, created_at), created_at
- **document_pack_definitions:** doc_key (unique), pack_tier, (pack_tier, canonical_index), deleted_at (sparse)
- **workflow_events:** event_id (unique), (order_id, created_at), created_at
- **deliveries:** delivery_id (unique), (order_id, created_at), (status, created_at), created_at
- **audit_logs:** (client_id, timestamp), (action, timestamp), timestamp, action

Task-required indexes: **service_code**, **order_ref**, **status**, **created_at** — all present (order_ref and status on `orders`; service_code on `service_catalogue_v2` and compound on `orders`; created_at on all).

**How to run:** From backend root: `python -m scripts.ensure_services_indexes` or `python scripts/ensure_services_indexes.py` with `PYTHONPATH=.` and `MONGO_URL` set.

### 2.4 Order flow and idempotency

- **Order creation:** Only via Stripe webhook after payment (`convert_draft_to_order` in `intake_draft_service`). Idempotency: `source_draft_id` unique; webhook checks existing order by `source_draft_id` before converting. `pricing.stripe_checkout_session_id` unique (sparse) for session-level idempotency.
- **Order ref format:** `PLE-YYYYMMDD-XXXX` (e.g. PLE-20250220-0001) from `generate_order_ref()` in `intake_draft_service`.
- **Status:** Order is created with status `PAID`, then workflow moves it to `QUEUED` (e.g. `workflow_automation_service.wf1_payment_to_queue`). No hard delete; `OrderRepository` has no delete.

### 2.5 Workflow events and audit logs

- **State changes:** The task requires "every state change creates a workflow_event". The codebase currently writes order state history to a **different** collection: `workflow_executions` (see `order_service.create_workflow_execution`, `workflow_automation_service`). The **workflow_events** collection, schema, and repository exist and are indexed; they are not yet written to by the order workflow. To satisfy the task fully you can either: (a) have order status transitions write to **workflow_events** (e.g. via `workflow_event_repository.insert`) in addition to or instead of `workflow_executions`, or (b) treat `workflow_executions` as the implementation of "workflow events" and document that naming. Safest: add writes to `workflow_events` at each order status transition so the task rule is met without removing existing `workflow_executions` behaviour.
- **Admin actions:** Use `utils.audit.create_audit_log()` (uses `models.core.AuditLog` and `audit_logs`). Same collection as `AuditLogRepository`; `create_audit_log` is the standard way to record admin (and other) actions.

---

## 3. What Is Missing or Optional

| Item | Status | Recommendation |
|------|--------|----------------|
| Single "documents" collection | By design we have two: `document_pack_items`, `generated_documents` | Keep as-is. Task "documents" is satisfied by these two; CVP `documents` stays separate. |
| Mongoose | N/A (Python stack) | Use Motor + Pydantic + repositories; no Node/Mongoose. |
| "intake_submissions" collection name | Implemented as `intake_drafts` | Keep `intake_drafts`; name is used in intake and webhook flow. |
| "services" collection name | Implemented as `service_catalogue_v2` | Keep `service_catalogue_v2`; used in catalogue and admin. |
| Explicit workflow_event insert on every status change | Code writes to `workflow_executions`, not `workflow_events` | Either start writing to `workflow_events` at each order status transition (in addition to or instead of `workflow_executions`), or document `workflow_executions` as the implementation of the task's "workflow_events". |
| Audit log for every admin action | In place via `create_audit_log` across routes | No change; keep using `create_audit_log` for admin (and other) actions. |

---

## 4. Rules Compliance

| Rule | Implementation |
|------|----------------|
| **Orders immutable (no hard delete)** | `OrderRepository` has no `delete`. Production code does not call `orders.delete_one` or `delete_many` (only test/cleanup scripts). |
| **Documents versioned (never overwrite)** | `GeneratedDocumentSchema` and `DocumentPackItemSchema` have `version`. New version = new document insert. `GeneratedDocumentRepository` and `DocumentPackItemRepository` do not expose an update that overwrites document content. |
| **Every state change → workflow_event** | Append to `workflow_events` on order status transitions. Pattern: `workflow_event_repository.insert({ "order_id": ..., "from_status": ..., "to_status": ..., ... })`. Verify all transition paths in `order_workflow` / `workflow_automation_service` do this. |
| **Every admin action → audit_log** | Use `create_audit_log()` from `utils.audit`; already used across admin routes. |

---

## 5. File Reference (Complete Code)

| Deliverable | File path |
|-------------|-----------|
| **Models (schemas)** | `backend/models/services_models.py` |
| **Repositories** | `backend/repositories/services_repositories.py` |
| **Index creation script** | `backend/scripts/ensure_services_indexes.py` |
| **Shared audit (action enum, create_audit_log)** | `backend/utils/audit.py`, `backend/models/core.py` (AuditLog, AuditAction) |
| **Order creation (draft → order)** | `backend/services/intake_draft_service.py` (`convert_draft_to_order`, `generate_order_ref`) |
| **Order idempotency (webhook)** | `backend/services/stripe_webhook_service.py` (`_handle_order_payment` checks by `source_draft_id`) |

---

## 6. Conflicting Instructions and Safest Option

- **Task:** "Mongoose or native driver + typed repositories"  
  **Reality:** Backend is Python (Motor). **Safest:** Keep using **Motor + Pydantic + existing typed repositories**. Do not introduce Mongoose or a Node.js layer for these collections.

- **Task:** Collection names "services", "intake_submissions", "documents"  
  **Reality:** Implemented as `service_catalogue_v2`, `intake_drafts`, and `document_pack_items` + `generated_documents`. **Safest:** Keep current names; document the mapping (as above). Renaming would require broad changes and risk to CVP and webhook flow.

- **Task:** "Return the complete code for models/repositories and an index creation script"  
  **Reality:** Complete code already exists in the three files above. **Safest:** Use these as the single source of truth; add only (1) explicit `workflow_events` insert at every order status transition if any path still misses it, and (2) any index you add later only via `ensure_services_indexes.py` (and optionally from `database.py` on app startup for orders so they exist before the script is run).

---

**Summary:** Models, repositories, and index script for the four services are implemented and aligned with the task. Collection naming differs from the task (services → service_catalogue_v2, intake_submissions → intake_drafts, documents → document_pack_items + generated_documents). Orders are immutable; documents are versioned; workflow_events and audit_logs are in place — ensure every order status change writes to `workflow_events`. No Mongoose; use Motor + Pydantic + the existing repositories and script.
