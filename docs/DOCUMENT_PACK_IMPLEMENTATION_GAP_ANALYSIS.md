# Document Pack Implementation — Gap Analysis

**Goal (from task):** Enterprise-grade document generation for Document Packs: deterministic pack definitions, per-document micro-prompts, DOCX/PDF renderer, ZIP bundle delivery, full audit trail.

**Scope:** Backend only (FastAPI, MongoDB). Frontend and Phase F not assessed here.

---

## 1. Phase A — Data Models

| Spec Requirement | Current State | Gap / Conflict |
|------------------|---------------|----------------|
| **document_pack_definitions** with `pack_code`, `inherits`, `canonical_documents[]`, `delivery_mode`, `bundle_format`, `active` | **document_pack_definitions** exists with **per-document** shape: `doc_key`, `doc_type`, `pack_tier`, `canonical_index`. Pack-level (pack_code, inherits, canonical_documents) is **in code** in `document_pack_orchestrator.py`: `DOCUMENT_REGISTRY`, `CANONICAL_ORDER`, `SERVICE_CODE_TO_PACK_TIER` | **Partial.** Pack-level definition is not in DB; it is hard-coded. Per-doc definitions could be seeded from registry. |
| **doc_templates** with `doc_type`, `template_docx_file_id`/path, `template_version`, `active` | **document_templates** collection exists (`document_template_service.py`): `service_code`, `doc_type`, `gridfs_id` (in bucket `docx_templates`). Used by `template_renderer` via `get_template_bytes(service_code, doc_type)`. | **Implemented** (name: `document_templates`; template stored in GridFS). |
| **generated_documents** with full audit: `prompt_version_used`, `intake_snapshot`, `intake_hash`, `structured_output`, `render_artifacts` (docx_file_id, pdf_file_id, filenames), status, versioning | **document_pack_items** is the main store for pack docs: `generated_output`, `prompt_version_used`, `input_snapshot_hash`, `docx_gridfs_id`, `pdf_gridfs_id`, `filename_docx`, `filename_pdf`, `status`, `version`. **generated_documents** exists but is minimal (`document_id`, `order_id`, `doc_type`, `version`, `status`) and appears used for non-pack flows. | **Split.** Pack flow uses **document_pack_items** with rich audit; **intake_snapshot** is not stored on the item (only hash). Spec’s “generated_documents” is satisfied by document_pack_items for packs; no need to duplicate. |
| **pack_bundles** with `order_id`, `pack_code`, `bundle_version`, `zip_file_id`, `filenames`, `created_at` | **No pack_bundles collection.** Delivery bundle is built on-the-fly in `GET /order/{order_id}/bundle` (returns list of approved items with file refs); no ZIP file is created or stored. | **Missing.** ZIP bundle generation and storage not implemented. |

**Recommendation (Phase A):**

- Keep **document_pack_items** as the single source of truth for pack document audit; do not duplicate into generated_documents for pack flow.
- Add **pack_bundles** collection and model when implementing ZIP delivery (Phase E).
- Optionally: add **pack-level** documents to **document_pack_definitions** (pack_code, inherits, canonical_documents, delivery_mode, bundle_format) via seed for reporting/UI; orchestrator can continue to use in-code registry to avoid breaking changes.

---

## 2. Phase B — Pack Orchestrator (No LLM)

| Spec Requirement | Current State | Gap / Conflict |
|------------------|---------------|----------------|
| **pack_orchestrator.py** with `build_document_plan(order_id) -> plan` | **document_pack_orchestrator.py** exists. Plan is **implicit**: `create_document_items(order_id, service_code, selected_docs, input_data)` + `filter_and_order_docs(service_code, selected_docs)` create and order items; no function returns a `document_plan` JSON. | **Different shape.** No explicit `build_document_plan(order_id)` returning `{ pack_code, document_plan[], delivery_mode, bundle_format }`. |
| Plan contains `document_plan[]` with `doc_type`, `prompt_service_code`, `prompt_doc_type`, `template_id` | `filter_and_order_docs` returns `List[Tuple[doc_key, canonical_index, DocumentDefinition]]`; `DocumentDefinition` has `doc_type`, `output_keys`. `_get_service_code_for_doc_type(doc_type)` gives prompt_service_code. No `template_id` in plan (template resolved at render time via `get_template_bytes(service_code, doc_type)`). | **Partial.** Logic exists; plan structure and template_id in plan are missing. |
| Deterministic; if template missing → fail clearly | Templates are optional in `render_pack_item` (fallback to code-built DOCX). Missing template does not fail the order. | **Conflict.** Spec says “if template missing → fail order clearly”. Current behaviour: render still proceeds with fallback. |

**Recommendation (Phase B):**

- Add **build_document_plan(order_id)** that:
  - Loads order (service_code, selected_docs or default to full pack).
  - Uses existing `filter_and_order_docs` / registry to build ordered list.
  - Returns `{ pack_code, document_plan: [{ doc_key, doc_type, prompt_service_code, prompt_doc_type, template_id or null }], delivery_mode, bundle_format }`.
- Resolve `template_id` in plan from existing `document_templates` (by service_code, doc_type) if you need it in the plan; otherwise leave as “template resolved at render” and omit from plan.
- Make “template required” configurable (e.g. per doc_type or per pack) so “fail if template missing” can be enforced where needed without breaking current behaviour everywhere.

---

## 3. Phase C — Micro-Prompt Execution

| Spec Requirement | Current State | Gap / Conflict |
|------------------|---------------|----------------|
| **document_generation_service.py** with `generate_pack(order_id, regen=..., regen_payload=...)` | **document_pack_orchestrator** has `generate_all_documents(order_id, input_data, generated_by)` and `generate_document(item_id, input_data, generated_by)`. Webhook/workflow passes `input_data` from order/intake. | **Implemented** (different name: generate_all_documents; no separate “document_generation_service” module). |
| INPUT_DATA_JSON scoped per doc_type (strict mapping table) | Same `input_data` passed to every doc; `build_user_prompt_with_json(template, intake_data)` injects full JSON. No per-doc_type field filtering. | **Partial.** Spec asks for “only relevant intake fields for the doc_type”. Current: all intake sent to every prompt. Acceptable if prompts are instructed to “use only provided fields”; stricter scoping would require a mapping table. |
| get_active_prompt(service_code, doc_type), validate output against output_schema | **prompt_manager_bridge.get_prompt_for_service(service_code, doc_type)**; **prompt_service._parse_llm_output**; output_keys checked against definition. | **Implemented.** |
| Persist with version, prompt_version_used, intake_snapshot, intake_hash | document_pack_items: `prompt_version_used`, `input_snapshot_hash`, `generated_output`. **intake_snapshot** not stored on item (order may hold intake). | **Partial.** For strict audit, consider storing intake_snapshot on item or a single per-order snapshot referenced by hash. |
| render_docx → PDF, GridFS, filename scheme | **template_renderer.render_pack_item**: `_render_docx`, `_render_pdf`, upload to GridFS (`order_files`), update item with `docx_gridfs_id`, `pdf_gridfs_id`, `filename_docx`, `filename_pdf`. `generate_deterministic_filename(...)` used. | **Implemented.** |
| Create ZIP bundle, store in pack_bundles | Not implemented. | **Missing.** |
| Move to INTERNAL_REVIEW, notify admin | **workflow_automation_service**: DRAFT_READY → INTERNAL_REVIEW; **order_notification_service** for admin. | **Implemented.** |

---

## 4. Phase D — Review Actions

| Spec Requirement | Current State | Gap / Conflict |
|------------------|---------------|----------------|
| POST `.../approve` | **POST /api/admin/orders/{order_id}/approve** (admin_orders) + **document_pack_orchestrator.approve_document(item_id)**. Order approval locks version and moves to FINALISING. | **Implemented.** |
| POST `.../request-regeneration` | Regeneration flow in admin_orders and workflow_automation_service; regen_reason/regen_notes. | **Implemented.** |
| POST `.../request-more-info` | **request_more_info** in admin_orders; CLIENT_INPUT_REQUIRED; notify client. | **Implemented.** |

---

## 5. Phase E — Delivery

| Spec Requirement | Current State | Gap / Conflict |
|------------------|---------------|----------------|
| EMAIL with ZIP download link | Order delivery service exists; bundle endpoint returns list of document items with file refs. **No single ZIP file** created or stored; no “signed URL for ZIP download”. | **Missing:** ZIP creation, storage, and ZIP download endpoint. |
| POSTAL / Fast Track add-ons | Not verified in this pass. | Out of scope for this gap list. |

---

## 6. Conflicts and Safest Options

1. **Pack definitions in DB vs in-code**  
   - **Conflict:** Spec wants pack-level definition in DB; current design uses in-code registry.  
   - **Safest:** Keep in-code registry as source of truth for orchestration. Optionally seed pack-level rows into **document_pack_definitions** for reporting/UI only; do not change orchestrator to read pack structure from DB in this phase to avoid regressions.

2. **generated_documents vs document_pack_items**  
   - **Conflict:** Spec describes “generated_documents” with full audit; implementation uses “document_pack_items” for that.  
   - **Safest:** Treat **document_pack_items** as the pack document record. Do not duplicate into **generated_documents** for pack flow. If a single “generated_documents” view is needed, add a read-only view or sync job later.

3. **build_document_plan()**  
   - **Gap:** Spec requires a function that returns plan JSON; current code only creates items.  
   - **Safest:** Add **build_document_plan(order_id)** that builds and returns the plan (and optionally validates templates) **without** creating items. Use it for validation and for any client that needs the plan before generation. Keep **create_document_items** as the path that writes to DB (called after payment/webhook).

4. **ZIP bundle and pack_bundles**  
   - **Gap:** No ZIP, no pack_bundles.  
   - **Safest:** Implement as **Phase E.1**: after all items are approved (or on “approve order”), build one ZIP from GridFS files in canonical order, upload ZIP to GridFS, insert **pack_bundles** row. Add endpoint to download ZIP (e.g. by order_id or bundle_id). Do not change existing per-document download behaviour.

5. **Template missing → fail order**  
   - **Conflict:** Spec says fail clearly if template missing; current code falls back to code-built DOCX.  
   - **Safest:** Introduce a config (e.g. per doc_type or global) “require_template”: if True, fail generation when `get_template_bytes` returns None. Default False to preserve current behaviour; enable for specific packs when templates are mandatory.

6. **Intake snapshot on each document**  
   - **Gap:** Spec wants intake_snapshot on each generated document; items only store `input_snapshot_hash`.  
   - **Safest:** If audit requires full snapshot per doc, add **intake_snapshot** to document_pack_items at generation time (same payload for all items of an order). Alternatively store once per order and reference by hash; document_pack_items already has the hash.

---

## 7. Proposed Next Steps (No Blind Implementation)

1. **Phase B — Add build_document_plan (deterministic plan API)**  
   - In **document_pack_orchestrator.py** (or a thin **pack_plan_service.py**), add `build_document_plan(order_id) -> dict`.  
   - Load order; get service_code and selected_docs; use existing filter_and_order_docs and registry; return `{ pack_code, document_plan[], delivery_mode, bundle_format }`.  
   - Optionally include template_id per doc from document_templates lookup.  
   - Add a test that asserts plan structure and ordering for a known order.

2. **Phase A — Optional pack-level seed**  
   - Add seed data for **document_pack_definitions** pack-level documents (DOC_PACK_ESSENTIAL, DOC_PACK_TENANCY, DOC_PACK_PRO) with inherits, canonical_documents, delivery_mode, bundle_format if the collection schema is extended; or document that pack-level is in-code and only per-doc definitions are in DB.

3. **Phase E.1 — ZIP bundle and pack_bundles**  
   - Define **pack_bundles** collection and model.  
   - After “approve order” (or when all items are approved), build ZIP from document_pack_items (canonical order), upload to GridFS, insert pack_bundles.  
   - Add **GET /api/.../order/{order_id}/bundle/zip** (or similar) that returns the ZIP (or signed URL).  
   - Keep existing GET bundle (list of items) for backward compatibility.

4. **Do not**  
   - Replace or duplicate the existing document_pack_orchestrator with a new “document_generation_service” unless you consolidate in one place and migrate callers.  
   - Switch pack structure to DB-driven without a clear migration and feature flag.  
   - Add “generated_documents” rows for pack docs without deprecating or clarifying the role of document_pack_items.

---

## 8. File / Module Map (Current)

| Spec / Concept | Current Location |
|----------------|------------------|
| Pack definitions (canonical order, tiers) | `document_pack_orchestrator.py`: DOCUMENT_REGISTRY, CANONICAL_ORDER, SERVICE_CODE_TO_PACK_TIER |
| Document plan / item creation | `document_pack_orchestrator.py`: filter_and_order_docs, create_document_items |
| Per-doc generation | `document_pack_orchestrator.py`: generate_document, generate_all_documents |
| Prompt resolution | `prompt_manager_bridge.py`: get_prompt_for_service; build_user_prompt_with_json |
| DOCX/PDF render | `template_renderer.py`: render_pack_item |
| Template storage | `document_template_service.py`: document_templates + GridFS docx_templates |
| Pack item storage | `document_pack_items` (MongoDB) |
| Review actions | `routes/admin_orders.py` (approve, request-regeneration, request-more-info); `document_pack_orchestrator.approve_document` |
| Bundle (list) | `routes/document_packs.py`: GET /order/{order_id}/bundle |

---

*Document generated from codebase review. Use this to decide what to implement next without duplicating or conflicting with existing behaviour.*
