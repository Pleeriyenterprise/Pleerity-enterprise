# Document Orchestrator – Codebase Audit vs Task Requirements

**Scope:** Four services (AI automation, Market research, Compliance services, Document packs).  
**Audit date:** 2025-02 (codebase state at audit).  
**Do not implement blindly:** This document compares task requirements to the existing implementation and calls out gaps and the safest options.

---

## 1. Task summary (requirements)

- **Input:** `order_id`
- **Steps:**
  1. Load order, service, intake_snapshot
  2. Determine document plan:
     - If service category ≠ document_pack: generate 1 doc_type
     - If document_pack: load pack definition and generate all docs in canonical order (PRO: ESSENTIAL + TENANCY + PRO)
  3. For each doc: select ACTIVE prompt, build INPUT_DATA_JSON, call LLM, validate output schema, store generation_runs, render (docx + pdf), save document version records with strict naming
- **File naming:** `{order_ref}{service_code}{doc_type}v{version}{status}_{YYYYMMDD-HHMM}.{ext}`
- **Output:** Order moves to INTERNAL_REVIEW after all docs generated successfully

---

## 2. Current architecture (two orchestrators)

| Component | Role | Used by |
|-----------|------|--------|
| **document_orchestrator.py** | Single-document pipeline: load order → one prompt → one LLM call → one render → store execution | WF2 (all orders), WF4 (regen) |
| **document_pack_orchestrator.py** | Pack items: create items per doc, generate per item (one prompt per doc_type), canonical order, inheritance | Webhook (create items), Admin API (generate one/all), **not** queue worker |

**Workflow (WF2):** `workflow_automation_service.wf2_queue_to_generation` always calls `document_orchestrator.execute_generation(order_id, intake_data=order.get("parameters", {}))`. There is no branch for document_pack to call the pack orchestrator or to generate multiple docs.

---

## 3. Requirement-by-requirement

### 3.1 Input: order_id

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Input is `order_id` | ✅ | `execute_full_pipeline(order_id, ...)` and `execute_generation(order_id, ...)` take `order_id`. WF2 passes it through. |

### 3.2 Step 1: Load order, service, intake_snapshot

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Load order | ✅ | `validate_order_for_generation(order_id)` loads order from DB; order used for `service_code`, `order_ref`. |
| Load service | ✅ | `service_code = order.get("service_code")`; service/category used for prompt selection and rendering. |
| Load intake_snapshot | ⚠️ Partial | Task says “load intake_snapshot”. Code **creates** an intake snapshot from `intake_data` passed in (`create_intake_snapshot(intake_data)`). WF2 passes `order.get("parameters", {})`. Order may also have `intake_snapshot` from draft/checkout; that is not used. So: snapshot is built from `parameters`, not loaded from a stored `intake_snapshot` field. Functionally equivalent if parameters are the source of truth; if order stores a locked `intake_snapshot` at payment, consider using that when present. |

### 3.3 Step 2: Determine document plan

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| If service category ≠ document_pack: generate 1 doc_type | ✅ | Single-doc path: `doc_type = service_code`, one prompt, one generation, one render. |
| If document_pack: load pack definition and generate all docs in canonical order | ❌ In queue path | Pack **definition** (canonical order, inheritance) exists in **document_pack_orchestrator** (in-code `DOCUMENT_REGISTRY`, `CANONICAL_ORDER`, PRO/PLUS/ESSENTIAL). Pack **generation** in canonical order is implemented as `generate_all_documents(order_id, input_data, generated_by)` in document_pack_orchestrator. **But** the queue (WF2) does **not** call the pack orchestrator. For DOC_PACK_* orders, WF2 still calls document_orchestrator once (with DOC_PACK_ORCHESTRATOR prompt fallback), producing **one** output, not “all docs in canonical order”. So: pack definition and multi-doc generation exist; they are **not** used in the automated queue flow. |
| Enforce inheritance PRO: ESSENTIAL + TENANCY + PRO | ✅ In pack orchestrator | `CANONICAL_ORDER` and `filter_and_order_docs` implement ESSENTIAL / PLUS (tenancy) / PRO inheritance. Not used by WF2. |

### 3.4 Step 3: For each doc (per-document steps)

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Select ACTIVE prompt template | ✅ | Single-doc: `prompt_manager_bridge.get_prompt_for_service(service_code, doc_type)`. Pack: document_pack_orchestrator uses same bridge per doc_type. |
| Build INPUT_DATA_JSON from order + intake + doc-specific fields | ✅ | Single-doc: `build_user_prompt_with_json(template, intake_snapshot, ...)` or `_build_user_prompt`; snapshot is the locked intake. Pack: `build_user_prompt_with_json` with input_data per item. |
| Call LLM provider | ✅ | Single-doc: `_execute_gpt`. Pack: `prompt_service._get_llm_provider()` then `llm.generate(...)`. |
| Validate output schema | ✅ Single-doc; ⚠️ Pack | Single-doc: schema key check and non-empty dict; optional output_schema keys. Pack: checks `definition.output_keys` present in parsed output; no formal JSON Schema validate. |
| Store generation_runs | ⚠️ Different store | Task: “store generation_runs”. Code: single-doc path stores to **orchestration_executions** (with execution_id, order_id, prompt_version_used, intake_snapshot, structured_output, rendered_documents, tokens, etc.). **generation_runs** collection exists (indexes in ensure_services_indexes) but is **not** written by either orchestrator. So: “run” data is stored, but in `orchestration_executions`, not `generation_runs`. |
| Render documents (docx + pdf) | ✅ Single-doc; ❌ Pack | Single-doc: `template_renderer.render_from_orchestration` → DOCX + PDF, versioned. Pack: `document_pack_orchestrator.generate_document` only stores `generated_output` (JSON) on the item; **no** call to template_renderer, **no** docx/pdf files or document version records for pack items. |
| Save document version records with strict naming | ✅ Single-doc; ❌ Pack | Single-doc: `document_versions_v2` and order’s `document_versions` updated; filenames from `generate_deterministic_filename`. Pack: no document version records or file naming; only item status and JSON. |

### 3.5 File naming

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| `{order_ref}{service_code}{doc_type}v{version}{status}_{YYYYMMDD-HHMM}.{ext}` | ⚠️ Different shape | Current: `generate_deterministic_filename(order_ref, service_code, version, status, extension)` → `{order_ref}_{service_code}_v{version}_{status}_{YYYYMMDD-HHMM}.{ext}`. So: underscores, no `doc_type` in name (single-doc uses service_code as doc_type). Task includes `doc_type` (relevant for packs with multiple docs). |

### 3.6 Output: Order moves to INTERNAL_REVIEW

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Order moves to INTERNAL_REVIEW after all docs generated successfully | ✅ Single-doc | WF2 on success: order → DRAFT_READY. WF3 (separate step, same pipeline): DRAFT_READY → INTERNAL_REVIEW. So “after all docs” for single-doc is “after the one doc”. For packs, queue does not run “all docs”, so there is no “after all docs” transition to INTERNAL_REVIEW in the pack path. |

---

## 4. Gaps summary

| # | Gap | Where | Risk / note |
|---|-----|--------|-------------|
| 1 | **Document-pack queue path** | WF2 | For DOC_PACK_* orders, WF2 runs a single document_orchestrator run (one doc), not “load pack definition and generate all docs in canonical order”. Pack multi-doc generation exists in document_pack_orchestrator but is only used from Admin API, not from the queue. |
| 2 | **Pack: no render / no version records** | document_pack_orchestrator | Pack flow generates JSON per item but does not call template_renderer, so no DOCX/PDF and no document version records or file naming for pack items. |
| 3 | **generation_runs not written** | Both | Task says “store generation_runs”. Runs are stored in `orchestration_executions` (single-doc). `generation_runs` is never written. Either treat orchestration_executions as the run store, or dual-write/alias to generation_runs. |
| 4 | **File naming: doc_type and exact format** | template_renderer | Current format has underscores and no `doc_type` segment. Task format includes `doc_type`. Only matters for multi-doc (pack) or if you want one convention for all. |
| 5 | **Intake snapshot source** | document_orchestrator | Snapshot is built from passed-in `intake_data` (parameters). If order stores a locked `intake_snapshot` at payment, it is not used. Optional: prefer order’s `intake_snapshot` when present. |

---

## 5. Conflicts and safe options

- **Two orchestrators:** No conflict. Single-doc (document_orchestrator) and pack (document_pack_orchestrator) are complementary. Safe approach: keep both; have the **queue** (WF2) branch on category/document_pack and call pack orchestrator when appropriate, then move to INTERNAL_REVIEW when all pack docs succeed.
- **generation_runs vs orchestration_executions:** Task says “generation_runs”; code uses orchestration_executions. Safest: keep orchestration_executions as source of truth; optionally dual-write a minimal record to generation_runs (run_id, order_id, template_id, doc_type, status, timestamps) for reporting, or rename in docs to “execution store” and leave generation_runs for future use.
- **Pack: in-code vs DB definitions:** Pack definitions are in-code (DOCUMENT_REGISTRY, CANONICAL_ORDER). Task says “load pack definition”. Safest: keep in-code as default; if you later need admin-editable packs, add a load from `document_pack_definitions` with fallback to in-code.

---

## 6. Recommended direction (no implementation here)

1. **Queue path for document_pack (main gap)**  
   In WF2 (or in a dedicated “run document plan” helper), if order is document_pack (e.g. `service_code` in DOC_PACK_* or category from service catalogue):
   - Load order, service, intake (parameters or order’s intake_snapshot if present).
   - Call document_pack_orchestrator to generate all docs in canonical order (e.g. `generate_all_documents` or a new method that also performs render and version records).
   - Only after all docs succeed, transition order to DRAFT_READY then WF3 to INTERNAL_REVIEW.
   - On any doc failure, treat as generation failure (e.g. FAILED state, no move to INTERNAL_REVIEW).

2. **Pack: render and version records**  
   Extend document_pack_orchestrator (or a shared helper) so that after each successful LLM generation for an item it:
   - Calls template_renderer (or a pack-specific render that uses the same naming rules) to produce DOCX + PDF.
   - Writes document version records and uses the agreed naming convention (including doc_type if required).

3. **File naming**  
   If you need to align with task exactly, add an optional `doc_type` argument to `generate_deterministic_filename` and use format `{order_ref}_{service_code}_{doc_type}_v{version}_{status}_{YYYYMMDD-HHMM}.{ext}` (or drop underscores to match task literally). Use for pack items; keep current format for single-doc if desired.

4. **generation_runs**  
   Either document that “run” data lives in orchestration_executions and generation_runs is reserved for future use, or add a small dual-write from document_orchestrator (and from pack path when added) into generation_runs with run_id, order_id, template_id, doc_type, status, timestamps.

5. **Intake snapshot**  
   In `execute_full_pipeline`, if order has `intake_snapshot` (e.g. from checkout), use that as the source for `create_intake_snapshot` when present; otherwise keep using `intake_data` (parameters).

---

## 7. Files reference

- **Single-doc pipeline:** `backend/services/document_orchestrator.py` (execute_full_pipeline, execute_generation, create_intake_snapshot, orchestration_executions).
- **Pack pipeline:** `backend/services/document_pack_orchestrator.py` (create_document_items, filter_and_order_docs, generate_document, generate_all_documents); `backend/services/document_pack_webhook_handler.py` (post-payment create items, order → QUEUED).
- **Workflow:** `backend/services/workflow_automation_service.py` (WF2, WF3; only calls document_orchestrator).
- **Rendering:** `backend/services/template_renderer.py` (render_from_orchestration, generate_deterministic_filename, document_versions_v2).
- **Prompt selection:** `backend/services/prompt_manager_bridge.py` (get_prompt_for_service, build_user_prompt_with_json).
- **Collections:** orchestration_executions (written); generation_runs (indexed, not written); document_pack_items (written by pack orchestrator); document_versions_v2 (written by template_renderer).

This audit is accurate as of the current codebase and is intended to guide implementation so that the document orchestrator behaviour matches the task without duplicating or conflicting with existing behaviour.
