# Document Pack Implementation Audit

**Purpose:** Compare the codebase to the task requirements (enterprise document generation for Document Packs) to identify what is implemented, what is missing, and any conflicts. No blind implementation.

**Scope:** Four services (AI automation, Market research, Compliance, Document packs). Focus: Document Packs.

---

## 1. GOAL vs CURRENT STATE

| Requirement | Status | Notes |
|-------------|--------|------|
| Deterministic pack definitions (no LLM decides content) | **Done** | `document_pack_orchestrator`: `DOCUMENT_REGISTRY`, `CANONICAL_ORDER`, `filter_and_order_docs`; server-side only. |
| Per-document micro-prompts (LLM generates content only) | **Done** | Prompt Manager: one prompt per `(service_code, doc_type)`; seed has micro-prompts for all ESSENTIAL/PLUS/PRO doc types. |
| Renderer enforces formatting with DOCX templates per doc_type | **Done** | `template_renderer.render_pack_item()` + `document_template_service.get_template_bytes(service_code, doc_type)`; fallback to code-built DOCX. |
| Output delivered as ZIP bundle (DOCX + PDF per document) | **Partial** | DOCX + PDF per item stored in GridFS; `document_pack_items` has `filename_docx`, `filename_pdf`, `docx_gridfs_id`, `pdf_gridfs_id`. **No `pack_bundles` collection; no ZIP build step.** Bundle endpoint returns metadata only, not a ZIP file. |
| Full audit trail: intake snapshot hash, prompt_version_used, document versioning | **Done** | `document_pack_items`: `input_snapshot_hash`, `prompt_version_used`, `version`; `generation_runs` dual-write; never overwrite. |

---

## 2. NON-NEGOTIABLES CHECK

| Rule | Status | Notes |
|------|--------|------|
| Packs deterministic; pack definitions in DB | **Partial** | Definitions are **in code** (`CANONICAL_ORDER`, `DOCUMENT_REGISTRY`). Collection `document_pack_definitions` exists but holds **per-document** rows (doc_key, pack_tier, canonical_index), not **per-pack** rows (pack_code, inherits, canonical_documents). |
| Orchestrator outputs "document_plan" list | **Partial** | No explicit `build_document_plan(order_id) -> plan` returning `{ pack_code, document_plan: [{ doc_type, prompt_service_code, prompt_doc_type, template_id }], delivery_mode, bundle_format }`. Plan is implicit in `filter_and_order_docs` + `create_document_items`. |
| Each doc generated via micro-prompt one-by-one | **Done** | `generate_document(item_id, ...)` per item; `generate_all_documents` loops PENDING items. |
| LLM outputs structured JSON only, never DOCX | **Done** | Prompts require JSON; `prompt_service._parse_llm_output`; output keys validated. |
| Renderer uses DOCX template per doc_type, placeholders from JSON | **Done** | `get_template_bytes(service_code, doc_type)`; renderer fills from `structured_output` + intake. |
| Never hard-delete; statuses + versioning | **Done** | New versions; statuses PENDING/GENERATING/COMPLETED/FAILED/APPROVED/REJECTED; regenerated_from_version. |
| prompt_version_used on every generated document version | **Done** | Stored on `document_pack_items` and in `generation_runs`. |

---

## 3. PHASE A — DATA MODELS

### 3.1 document_pack_definitions (task: per-pack)

**Task spec:** One document per **pack** (not per doc type):

- `pack_code` (string, unique) e.g. DOC_PACK_ESSENTIAL / DOC_PACK_TENANCY / DOC_PACK_PRO  
- `inherits` (array of pack_codes)  
- `canonical_documents` (array of { doc_type, order })  
- `delivery_mode` (array) e.g. ["DOCX","PDF"]  
- `bundle_format` (string) e.g. "ZIP"  
- `active` (bool), `created_at`, `updated_at`

**Current:** Collection exists. **Schema is per-document:** `doc_key`, `doc_type`, `pack_tier`, `display_name`, `canonical_index`, timestamps, `deleted_at`. Used by `DocumentPackDefinitionRepository.list_by_tier(pack_tier)`.

**Conflict:** Task wants **pack-level** definitions (one row per pack). Code has **document-level** definitions (one row per doc type). Canonical order and inheritance live in Python (`CANONICAL_ORDER`, `DOCUMENT_REGISTRY`).

**Recommendation:**  
- **Option A (safest):** Introduce a **new** collection `pack_definitions` for pack-level records (pack_code, inherits, canonical_documents, delivery_mode, bundle_format). Keep `document_pack_definitions` for optional per-doc metadata (e.g. display_name, canonical_index override). Orchestrator can read from `pack_definitions` when present and fall back to code.  
- **Option B:** Replace content of `document_pack_definitions` with pack-level docs and derive doc list from `canonical_documents` + inheritance. This would require a data migration and changing all usages of `document_pack_definitions` (e.g. list_by_tier).  

**Preferred:** Option A — add `pack_definitions`; seed DOC_PACK_ESSENTIAL, DOC_PACK_TENANCY, DOC_PACK_PRO with inheritance and canonical_documents; orchestrator uses pack_definitions when available.

### 3.2 doc_templates (task)

**Task spec:** `doc_type` (unique), `template_docx_file_id` or `template_path`, `template_version`, `active`.

**Current:** `document_templates` collection (see `document_template_service`): `service_code`, `doc_type`, `template_id`, `gridfs_id`, `name`, `content_hash`, timestamps, `uploaded_by`. Template bytes in GridFS bucket `docx_templates`. Key is (service_code, doc_type), not doc_type alone.

**Gap:** Task says doc_type unique; current key is (service_code, doc_type). For packs this is correct (same doc_type can appear in different packs but template is per service_code/doc_type).

**Recommendation:** No change to collection name or key. Add `template_version` and `active` if missing. Align naming in docs with `document_templates` (already used everywhere).

### 3.3 generated_documents (task)

**Task spec:** order_id, pack_code, doc_type, version, status (DRAFT|FINAL|SUPERSEDED|VOID|REGENERATED), prompt_service_code, prompt_doc_type, prompt_template_id, prompt_version_used, intake_snapshot, intake_hash, structured_output, render_artifacts (docx_file_id, pdf_file_id, filenames), regenerated_from_version, regen_reason, regen_notes, created_at, created_by.

**Current (pack flow):** Data lives in **document_pack_items**: item_id, order_id, doc_key, doc_type, canonical_index, version, status (PENDING|GENERATING|COMPLETED|FAILED|APPROVED|REJECTED), prompt_version_used, input_snapshot_hash, generated_output, filename_docx, filename_pdf, docx_gridfs_id, pdf_gridfs_id, regenerated_from_version, regen_reason, regen_notes, etc. No separate `generated_documents` row per pack doc.

**Current (single-doc / non-pack):** `generated_documents` and `document_versions` (in orders or separate collection) used by `document_orchestrator` / `document_generator` for non-pack services.

**Conflict:** Task assumes one "generated_documents" collection for pack outputs. Code uses **document_pack_items** for pack outputs and **generated_documents** for non-pack.

**Recommendation:** Keep **document_pack_items** as the source of truth for pack-generated docs. Ensure it has all audit fields (intake_snapshot optional for size; intake_hash present). Optionally dual-write a summary row into `generated_documents` for cross-service reporting (order_id, pack_code, doc_type, version, status, prompt_version_used, intake_hash, structured_output keys, render artifact refs). Do not replace document_pack_items with generated_documents for packs.

### 3.4 pack_bundles (task)

**Task spec:** order_id, pack_code, bundle_version, zip_file_id, filenames (array), created_at.

**Current:** **No** `pack_bundles` collection. Bundle is described on the fly in `GET /order/{order_id}/bundle` (list of approved items with file refs). No ZIP assembly or stored zip_file_id.

**Gap:** ZIP bundle not built or stored. Delivery likely uses individual file links or ad-hoc ZIP generation.

**Recommendation:** Add `pack_bundles` collection. After all pack docs for an order are approved (or on approve), build ZIP from GridFS files in canonical order, upload ZIP to GridFS, insert `pack_bundles` row. Delivery endpoint can return signed URL to ZIP or stream ZIP from GridFS.

---

## 4. PHASE B — PACK ORCHESTRATOR (NO LLM)

**Task spec:** Service `pack_orchestrator.py` with `build_document_plan(order_id) -> plan` returning:

- pack_code  
- document_plan: [ { doc_type, prompt_service_code, prompt_doc_type, template_id } ]  
- delivery_mode, bundle_format  

Logic: read order (service_code, selected docs), load pack definition, resolve inheritance, sort by order, apply selection, produce plan. If template missing → fail clearly.

**Current:** `document_pack_orchestrator.py` already has:

- `get_pack_tier(service_code)`, `get_allowed_docs(pack_tier)`, `get_canonical_order(pack_tier)`  
- `filter_and_order_docs(service_code, selected_docs)` → list of (doc_key, canonical_index, DocumentDefinition)  
- `create_document_items(order_id, service_code, selected_docs, input_data)` → creates rows in document_pack_items  

No explicit `build_document_plan(order_id)` that returns the JSON structure above. Prompt lookup is by (service_code, doc_type) where service_code = `_get_service_code_for_doc_type(doc_type)`; template lookup is inside `template_renderer` via `get_template_bytes(service_code, doc_type)` (no template_id in plan).

**Gaps:**

1. No single function `build_document_plan(order_id)` returning the specified plan JSON.  
2. Plan does not include `template_id` (active template for doc_type). Template service could return template_id when loading bytes; or plan could include it from document_templates lookup.  
3. Pack definitions are in code, not DB (see Phase A).

**Recommendation:**

- Add `build_document_plan(order_id) -> dict` either:
  - **In** `document_pack_orchestrator` (e.g. `DocumentPackOrchestrator.build_document_plan`), or  
  - In a separate thin `pack_plan_service` that uses the same registry and DB.  
- Plan format: `{ "pack_code", "document_plan": [ { "doc_key", "doc_type", "prompt_service_code", "prompt_doc_type", "template_id" (optional) } ], "delivery_mode": ["DOCX","PDF"], "bundle_format": "ZIP" }`.  
- If template_id is required in plan: add a read from document_templates by (prompt_service_code, doc_type) to get active template_id; if missing and task says "fail order clearly", raise or return error in plan build.  
- Keep deterministic behaviour: use existing registry + order selection; no LLM.

---

## 5. PHASE C — MICRO-PROMPT EXECUTION

**Current:** `document_pack_orchestrator.generate_document(item_id, input_data, generated_by)` and `generate_all_documents(order_id, input_data, generated_by)` already:

1. Get item and definition, get prompt by (prompt_service_code, prompt_doc_type).  
2. Build user prompt with `build_user_prompt_with_json(template, intake_data)`.  
3. Call LLM, parse JSON, validate output keys.  
4. Persist to document_pack_items (status, generated_output, prompt_version_used, input_snapshot_hash).  
5. Call `template_renderer.render_pack_item(...)` → DOCX + PDF, store in GridFS, update item with filename_*, *_gridfs_id.  
6. Dual-write generation_runs.

**Gaps:**

- No step that builds a **scoped** INPUT_DATA_JSON per doc_type from a "strict mapping table" (task: "include only relevant intake fields for the doc_type"). Currently the same `input_data` is passed to every doc.  
- Order state transition to INTERNAL_REVIEW and admin notification: handled elsewhere (e.g. workflow_automation_service after generate_all_documents). Confirm once after generation completes.  
- ZIP bundle creation and pack_bundles insert: not implemented (see Phase A.4).

**Recommendation:**

- Optional: add a mapping (doc_type → list of intake field names) and filter input_data to those keys (plus universal fields) before calling the prompt. If not present, keep current behaviour (full intake).  
- Add ZIP build + pack_bundles insert when all items are COMPLETED/APPROVED (or on approve).  
- Keep rest of Phase C as-is.

---

## 6. PHASE D — REVIEW ACTIONS

**Current:**

- `POST /api/admin/orders/{order_id}/approve` exists (admin_orders): approves order, locks version, moves to FINALISING.  
- Regeneration: `POST .../request-regeneration` (admin) and pack-specific regenerate endpoint in document_packs.  
- Request more info: `POST .../request-more-info` (admin), stores request, sets CLIENT_INPUT_REQUIRED, notifies client.

**Alignment:** Phase D is largely implemented. Ensure pack orders use the same approve/regenerate/request-more-info flows and that "approve" for packs marks all doc versions FINAL and triggers bundle build + delivery.

---

## 7. PHASE E — DELIVERY

**Current:** order_delivery_service finds FINALISING orders with approved_document_version; sends email (Postmark) with links. Pack delivery may not assemble ZIP; need to confirm link is to ZIP or to per-doc downloads.

**Gap:** No ZIP; no pack_bundles; POSTAL/Fast Track add-ons may be partial.

**Recommendation:** Implement ZIP bundle and pack_bundles; then add signed URL endpoint for ZIP download and use it in delivery email for pack orders.

---

## 8. PHASE F — FRONTEND

Not audited in this pass. Backend must expose: document_plan (if needed by UI), bundle status, per-doc viewer (PDF URL), version history, regen/request-more-info/approve actions.

---

## 9. CONFLICTS SUMMARY AND SAFEST OPTIONS

| Conflict | Safer option |
|----------|----------------|
| document_pack_definitions = per-pack vs per-doc | Add new `pack_definitions` for pack-level config; keep `document_pack_definitions` for per-doc metadata or leave as-is and keep pack logic in code. |
| generated_documents vs document_pack_items for pack docs | Keep document_pack_items as source of truth for pack; optionally dual-write to generated_documents for reporting. |
| No pack_bundles / ZIP | Add pack_bundles collection and a ZIP build step after approve (or when all COMPLETED); store ZIP in GridFS. |
| No explicit build_document_plan | Add build_document_plan(order_id) returning the specified plan structure; implement inside document_pack_orchestrator or a small pack_plan_service. |

---

## 10. PROPOSED FOLDER/FILE CHANGES (FOR PHASE A + B)

- **New:** `backend/models/pack_models.py` (optional) — Pydantic models for pack_definitions and plan output.  
- **New collection / seed:** `pack_definitions` — seed DOC_PACK_ESSENTIAL, DOC_PACK_TENANCY, DOC_PACK_PRO with inherits and canonical_documents.  
- **New:** `backend/repositories/pack_definitions_repository.py` (or add to services_repositories) — get_by_pack_code, list_active.  
- **Modify:** `backend/services/document_pack_orchestrator.py` — add `build_document_plan(order_id) -> dict`; optionally read from pack_definitions when present.  
- **Modify:** `backend/scripts/ensure_services_indexes.py` — add indexes for pack_definitions (pack_code unique), and for pack_bundles if added.  
- **New (Phase A.4):** `pack_bundles` collection + schema in services_models; repository method to insert bundle record.  
- **Tests:** Extend or add tests in `backend/tests/` for build_document_plan (deterministic order, selection, missing template behaviour) and for pack_definitions read path.

No new top-level service file `pack_orchestrator.py` is strictly necessary if we extend `document_pack_orchestrator` with `build_document_plan` and keep a single orchestrator; the task’s "pack_orchestrator" can be the same module. If you prefer a clear separation, a thin `pack_plan_service.py` could call into the existing registry and DB and return the plan only.

---

## 11. IMPLEMENTATION ORDER (PHASE A + B ONLY)

1. **Phase A.1 (pack_definitions):** Add `pack_definitions` collection and schema; seed DOC_PACK_ESSENTIAL, DOC_PACK_TENANCY, DOC_PACK_PRO with inherits and canonical_documents; add repository and indexes.  
2. **Phase A.2 (doc_templates):** Confirm document_templates has template_version and active; add if missing.  
3. **Phase A.3 (generated_documents / document_pack_items):** Ensure document_pack_items has all audit fields; no structural change to use generated_documents for pack docs unless dual-write is desired.  
4. **Phase A.4 (pack_bundles):** Add pack_bundles collection, schema, repository, indexes.  
5. **Phase B:** Implement `build_document_plan(order_id)` in document_pack_orchestrator (or pack_plan_service), returning pack_code, document_plan (with doc_key, doc_type, prompt_service_code, prompt_doc_type, template_id when available), delivery_mode, bundle_format; deterministic; fail clearly if template required but missing.  
6. **Tests:** Unit tests for build_document_plan (selection, inheritance, order); integration test with in-memory DB or mocks for plan content.

This audit should be used to avoid duplication and to align new code with the existing document_pack_orchestrator and template_renderer behaviour. Do not implement blindly; prefer extending the current orchestrator and adding only the missing pieces (pack_definitions, pack_bundles, build_document_plan, and optional doc-type-scoped intake).
