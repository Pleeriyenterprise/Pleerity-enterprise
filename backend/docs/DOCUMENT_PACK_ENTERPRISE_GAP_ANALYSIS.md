# Document Pack Enterprise Implementation — Gap Analysis

**Goal:** Enterprise-grade document generation for Document Packs (deterministic packs, per-document micro-prompts, DOCX/PDF renderer, ZIP bundle, full audit trail).

**Stack:** FastAPI, MongoDB, React, Postmark, OpenAI/Gemini. Prompt Manager supports `service_code` + `doc_type`, `{{INPUT_DATA_JSON}}`, versions + schema validation.

---

## Phase A — Data Models

| Spec | Current State | Gap / Recommendation |
|------|---------------|----------------------|
| **document_pack_definitions** (pack_code, inherits, canonical_documents, delivery_mode, bundle_format, active) | Pack-level config is **in-code**: `DOCUMENT_REGISTRY`, `CANONICAL_ORDER`, `SERVICE_CODE_TO_PACK_TIER` in `document_pack_orchestrator.py`. Collection `document_pack_definitions` exists with **per-doc** shape (doc_key, doc_type, pack_tier, canonical_index). | **Partial.** Pack-level (pack_code, inherits, delivery_mode, bundle_format) is not in DB. **Recommendation:** Keep in-code registry as source of truth for now; optionally seed pack-level rows for reporting/UI only. |
| **doc_templates** (doc_type, template_docx_file_id/path, template_version, active) | **document_templates** collection exists (`document_template_service.py`): service_code, doc_type, gridfs_id, template_id, content_hash. GridFS bucket `docx_templates`. | **Implemented.** Align spec naming to `document_templates`; no new collection. |
| **generated_documents** (order_id, doc_type, version, status, prompt_version_used, intake_snapshot, intake_hash, structured_output, render_artifacts) | **document_pack_items** holds per-doc audit: item_id, order_id, doc_key, doc_type, generated_output, prompt_version_used, input_snapshot_hash, docx_gridfs_id, pdf_gridfs_id, filename_docx, filename_pdf. **generated_documents** collection exists but is minimal (document_id, order_id, doc_type, version, status) — used for non-pack flows. | **Split.** Pack flow uses `document_pack_items`; no duplicate into `generated_documents`. **Recommendation:** Treat document_pack_items as canonical pack-doc record; add intake_snapshot to item if audit requires it (or reference order snapshot). |
| **pack_bundles** (order_id, pack_code, bundle_version, zip_file_id, filenames, created_at) | No collection. Bundle assembled on-the-fly in `GET /order/{order_id}/bundle` (returns list of approved items with file refs); no ZIP stored in GridFS. | **Missing.** Add Phase E.1: build ZIP from GridFS DOCX/PDF in canonical order on approve (or on demand), store in GridFS, insert pack_bundles row; add download endpoint. |

---

## Phase B — Pack Orchestrator (No LLM)

| Spec | Current State | Gap / Recommendation |
|------|---------------|----------------------|
| **pack_orchestrator.build_document_plan(order_id) -> plan** | **Implemented** in `document_pack_orchestrator.py`: `build_document_plan(order_id)` returns `{ pack_code, document_plan[], delivery_mode, bundle_format }`. Uses order.service_code, document_pack_info.selected_docs or selected_documents, filter_and_order_docs(), and optional template_id from document_templates. | **Done.** No separate pack_orchestrator.py; logic lives in document_pack_orchestrator. |
| Plan shape: document_plan[].doc_type, prompt_service_code, prompt_doc_type, template_id | document_plan entries include doc_key, doc_type, canonical_index, prompt_service_code, prompt_doc_type, template_id (optional). | **Aligned.** |
| Deterministic; if template missing -> fail clearly | template_id can be None; renderer falls back to code-built DOCX. Spec said "fail order clearly" — current behaviour is graceful fallback. | **Optional:** Explicitly fail generation if template required and missing (configurable per doc_type). |

---

## Phase C — Micro-Prompt Execution

| Spec | Current State | Gap / Recommendation |
|------|---------------|----------------------|
| **generate_pack(order_id, regen=...)** | `generate_all_documents(order_id, input_data, generated_by)` + `generate_document(item_id, input_data, generated_by)` per item. | **Implemented** (different naming). |
| INPUT_DATA_JSON scoped per doc_type | `build_user_prompt_with_json(template, intake_data)` — same intake for all docs. | **Partial.** No strict per-doc_type field mapping table; all docs receive same intake. Add mapping later if needed for compliance. |
| get_active_prompt(service_code, doc_type), validate output_schema | `prompt_manager_bridge.get_prompt_for_service(service_code, doc_type)`; output parsed and checked against definition.output_keys. | **Implemented.** |
| Persist generated_documents with version, prompt_version_used, intake_snapshot, hash | document_pack_items updated with generated_output, prompt_version_used, input_snapshot_hash. intake_snapshot not stored on item (only on order). | **Partial.** Add intake_snapshot to item if audit requires; else keep hash + order reference. |
| render_docx, convert to PDF, GridFS, filename scheme | `template_renderer.render_pack_item()`: _render_docx, _render_pdf, upload to GridFS (docx_gridfs_id, pdf_gridfs_id), generate_deterministic_filename. | **Implemented.** |
| Create ZIP bundle, store in pack_bundles | Not implemented. | **Missing.** See Phase E.1. |
| Move to INTERNAL_REVIEW, notify admin | workflow_automation_service transitions DRAFT_READY → INTERNAL_REVIEW; order_notification_service. | **Implemented.** |

---

## Phase D — Review Actions

| Spec | Current State | Gap / Recommendation |
|------|---------------|----------------------|
| POST .../approve | `POST /api/admin/orders/{order_id}/approve` (admin_orders) + `document_pack_orchestrator.approve_document(item_id)`. | **Implemented.** |
| POST .../request-regeneration | Regeneration flow in admin_orders + workflow_automation_service (REGEN_REQUESTED → REGENERATING → INTERNAL_REVIEW). | **Implemented.** |
| POST .../request-more-info | admin_orders request_more_info (CLIENT_INPUT_REQUIRED); client responds → back to INTERNAL_REVIEW. | **Implemented.** |

---

## Phase E — Delivery

| Spec | Current State | Gap / Recommendation |
|------|---------------|----------------------|
| EMAIL default: Postmark with ZIP download link | Order delivery service exists; bundle endpoint returns list of files — no single ZIP. | **Partial.** Add ZIP build + pack_bundles + signed download URL. |
| POSTAL add-on / Fast Track add-on | May exist in order/addon logic. | Not verified in this pass. |

---

## Phase F — Frontend

Not audited in this pass. Assumed: intake wizard, checkout (Stripe after intake), admin dashboard with pipeline stages, INTERNAL_REVIEW view (document viewer, version history, regen/request-more-info/approve modals).

---

## Conflicts and Safest Options

1. **Pack definitions in DB vs in-code**  
   **Option:** Keep in-code registry as source of truth. Do not migrate to DB-only without a clear migration path and backfill. Optional: seed pack-level document_pack_definitions for reporting only.

2. **generated_documents vs document_pack_items**  
   **Option:** Do not duplicate. Treat document_pack_items as the pack-doc record. Use generated_documents only for non-pack (single-doc) flows if needed.

3. **build_document_plan()**  
   **Done.** Already implemented in document_pack_orchestrator; returns plan JSON. Add test coverage.

4. **ZIP bundle and pack_bundles**  
   **Option:** Implement as next step: on approve (or on first download), build ZIP from GridFS DOCX/PDF in canonical order, upload ZIP to GridFS, insert pack_bundles; add GET /api/.../order/{order_id}/bundle/zip (signed or auth) returning ZIP.

5. **Intake snapshot on item**  
   **Option:** If audit requires full snapshot per doc, add intake_snapshot (or intake_snapshot_ref) to document_pack_items at generation time; else keep hash + order reference.

---

## Summary

- **Phase A:** document_templates implemented; pack-level defs in-code; generated_documents minimal; pack_bundles missing.
- **Phase B:** build_document_plan implemented; add test.
- **Phase C:** Generation, prompts, render, audit (hash) implemented; ZIP + pack_bundles missing; optional per-doc intake snapshot.
- **Phase D–E:** Review actions implemented; delivery needs ZIP + pack_bundles + download endpoint.
- **Phase F:** Not verified.

**Recommended next steps (no blind implementation):**  
1. Add test for `build_document_plan`.  
2. Implement ZIP bundle creation + pack_bundles collection + download endpoint.  
3. Optionally add intake_snapshot to document_pack_items if audit requires.
