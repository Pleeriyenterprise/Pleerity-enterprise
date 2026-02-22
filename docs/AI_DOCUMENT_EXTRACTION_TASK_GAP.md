# AI Document Extraction for Compliance Vault Pro – Gap Analysis

## Task summary (non-negotiables)

- AI used **only** to extract/normalize fields and suggest mappings; **no legal advice or compliance verdicts**.
- AI output is **suggested** with confidence; **never overwrite** user-entered values without confirmation.
- If confidence &lt; threshold or key fields missing → **NEEDS_REVIEW**; require user/admin confirmation.
- **Deterministic and auditable**: store raw model output + prompt version + model name + timestamp.
- **Do not break** existing upload flows, scoring, notifications, or provisioning.

---

## Current state

### A) Data model

| Task requirement | Current implementation | Gap |
|-----------------|------------------------|-----|
| **extracted_documents collection** (or embed as `documents.extraction`) | **Embedded only**: `documents.ai_extraction` with `status` ("completed" \| "failed"), `data`, `extraction_quality`, `review_status` ("pending" \| "approved" \| "rejected"), `reviewed_at`, `reviewed_by`, `applied_data`, `rejection_reason`. No separate collection. | Task asks for either a **new collection** `extracted_documents` or embed with a **different schema**: doc_type enum (GAS_SAFETY, EICR, EPC, …), certificate_number, issue_date, expiry_date, inspector_company, inspector_id, address_line_1, postcode, property_match_confidence, overall_confidence, notes, **mapping_suggestion** (requirement_key, suggested_property_id), **status** (PENDING \| EXTRACTED \| NEEDS_REVIEW \| CONFIRMED \| REJECTED \| FAILED), **errors**, **audit** (model, prompt_version, tokens_in/out, **raw_response_json**, created_at, updated_at). Current has no prompt_version, no model name, no full raw_response (only truncated on parse failure). |
| **documents.extraction_id / extraction_status** | Documents do not have `extraction_id` or `extraction_status`; extraction lives under `ai_extraction` with different status semantics. | Task: link document to extraction record via `extraction_id` and surface `extraction_status` for list/badge. |

### B) Backend extraction pipeline

| Task requirement | Current implementation | Gap |
|-----------------|------------------------|-----|
| **document_extraction_service.py** with `enqueue_extraction`, `run_extraction_job` | **None.** No dedicated extraction service or queue. | Task: **Create** `backend/services/document_extraction_service.py` with enqueue + run job. |
| **Read file bytes from storage** | `document_analysis_service.analyze_document(file_path, ...)` receives **file path**; `chat_with_file` in `utils/llm_chat.py` passes file to Gemini (binary/upload). | Task: read file bytes securely; **extract text first** (PDF text or OCR), cap 30k chars; **call AI only on text**, not raw binary. |
| **Validate AI output, set status by confidence** | `document_analysis` parses JSON, normalizes, computes `extraction_quality` (high/medium/low); **always** sets `requires_review: True` and `review_status: "pending"`. No EXTRACTED vs NEEDS_REVIEW by threshold. | Task: if `overall_confidence >= 0.85` AND `expiry_date` present → **EXTRACTED**; else → **NEEDS_REVIEW**. Never auto **CONFIRMED**. |
| **Store extraction record + link to document** | Writes only to `documents.ai_extraction` (embedded). No separate record; no `documents.extraction_id`. | Task: store in extraction record (new collection or structured embed); set `documents.extraction_id` and `documents.extraction_status`. |
| **Audit events** | Only **DOCUMENT_AI_ANALYZED** (and AI_EXTRACTION_APPLIED on apply). | Task: **DOC_EXTRACT_REQUESTED**, **DOC_EXTRACT_SUCCEEDED**, **DOC_EXTRACT_NEEDS_REVIEW**, **DOC_EXTRACT_FAILED**. |

### C) AI provider

| Task requirement | Current implementation | Gap |
|-----------------|------------------------|-----|
| **ai_provider.py** with `extract_compliance_fields(text, file_name, hints) -> dict` | **No ai_provider.py.** Uses **document_analysis.py** + **utils/llm_chat.py**: `chat_with_file(system_prompt, user_text, file_path, mime_type, model="gemini-2.5-flash")` – sends **file** to Gemini. Uses **LLM_API_KEY** (Gemini). | Task: **Create** `backend/services/ai_provider.py`; **text-only** input; env **AI_PROVIDER=openai**, **OPENAI_API_KEY**, **AI_MODEL_EXTRACTION**, **AI_EXTRACTION_PROMPT_VERSION**, **AI_EXTRACTION_ENABLED**. Strict JSON schema (doc_type, certificate_number, issue_date, expiry_date, inspector_company, inspector_id, address_line_1, postcode, requirement_key, confidence.{overall, dates, address, doc_type}, notes). |
| **Hard rules in prompt** | Current prompt says only extract visible info, use null if unsure, no inference. | Task: explicit "No legal advice", "Do not infer facts not present", "If uncertain return nulls and lower confidence", "Output JSON only." |
| **AI disabled / missing keys** | If no LLM_API_KEY or import error, returns `success=False`, "AI extraction unavailable"; stores `ai_extraction.status = "failed"` with error. | Task: mark status=**FAILED** with **error_code="AI_NOT_CONFIGURED"**; do not crash upload. Compatible with current behavior if we map to same. |

### D) Trigger points

| Task requirement | Current implementation | Gap |
|-----------------|------------------------|-----|
| **After vault upload** | **POST /documents/upload** and **POST /documents/admin/upload**: create document, update requirement, compliance recalc, audit **DOCUMENT_UPLOADED**. **No** call to any extraction. | Task: after upload succeeds, **enqueue_extraction(document_id, client_id, source="vault_upload", property_id=...)**. Async, non-blocking. |
| **After intake migration** | **intake_upload_migration.migrate_intake_uploads_to_vault**: creates document, updates intake_uploads; **no** extraction call. | Task: after creating each vault document, **enqueue_extraction(..., source="intake_upload", intake_session_id=...)**. Do not block migration. |

**Existing triggers (unchanged by task):**

- **POST /documents/analyze/{document_id}**: on-demand analyze (current); can remain and call new pipeline or be adapted.
- **Bulk/ZIP upload**: currently calls `document_analysis_service.analyze_document` inline per file; task says do not change existing behavior – so either keep as-is (sync analyze) or optionally enqueue per file for consistency.

### E) Review UI

| Task requirement | Current implementation | Gap |
|-----------------|------------------------|-----|
| **Document list: extraction status badge** | DocumentsPage shows **ai_extraction.status** (completed/failed), **confidence**, **extraction_quality**, **review_status** (pending/approved/rejected). Wording differs from task. | Task: badge **Pending / Needs review / Extracted / Confirmed / Failed**. Map current "completed" + review_status to task statuses or add new status field. |
| **“Review extraction” drawer/modal** | Exists: shows extracted fields, confidence; **Confirm & apply** (apply-extraction), **Edit then confirm**, **Reject** (reject-extraction). | Align labels and behavior with task: "Confirm & apply to property requirement fields", "Edit fields then confirm", "Reject extraction". Apply = write to requirement + set extraction **CONFIRMED**; Reject = **REJECTED**, do not apply. |
| **Apply = explicit** | apply-extraction updates requirement (due_date, status) and sets `ai_extraction.review_status = "approved"`, `applied_data`. | Task: same idea; ensure extraction record (if new) is set to **CONFIRMED** and requirement/evidence updated. |
| **Admin: Extraction Review Queue** | **None.** No admin page filtering NEEDS_REVIEW/FAILED. | Task: **Add** admin queue page "Extraction Review Queue" with filter NEEDS_REVIEW, FAILED; admin can confirm/reject. |

### F) Safety and auditability

| Task requirement | Current implementation | Gap |
|-----------------|------------------------|-----|
| **Store text snippet (capped) or hash in audit** | Not stored. | Task: optional in extraction record audit. |
| **Store raw_response_json always** | Only on parse failure, truncated to 1000 chars in `ai_extraction.raw_response`. | Task: **always** store full raw response in audit. |
| **Rate limiting** | None for extraction. | Task: **max extractions per minute globally**, and **per client/day**. |
| **AI disabled → FAILED, no crash** | Already fails gracefully; no error_code. | Task: **error_code="AI_NOT_CONFIGURED"**. |

### G) Tests

| Task requirement | Current implementation | Gap |
|-----------------|------------------------|-----|
| **AI disabled → enqueue but extraction FAILED, AI_NOT_CONFIGURED** | Tests exist for analyze endpoint and apply/reject; no test for “upload triggers enqueue, extraction marks FAILED when AI disabled”. | **Add** backend test. |
| **Valid extraction JSON → EXTRACTED, expiry_date parsed** | No test that asserts status EXTRACTED and date parsing. | **Add** backend test. |
| **Low confidence or missing expiry_date → NEEDS_REVIEW** | No test. | **Add** backend test. |
| **Confirm endpoint → applies to requirement, sets CONFIRMED** | test_iteration19_apply_save_history, test_apply_extraction_*; apply-extraction tested. | Ensure test asserts extraction record (or doc field) **CONFIRMED** and requirement updated. |
| **Reject endpoint → REJECTED, applies nothing** | test_reject_extraction exists. | Ensure **REJECTED** and no change to requirement. |
| **Frontend: extraction badge per status** | DocumentsPage has badges for completed/failed and review_status. | **Add** test that badge reflects status (Pending/Needs review/Extracted/Confirmed/Failed). |
| **Frontend: confirm flow calls API and updates UI** | Manual flow exists. | **Add** test that confirm calls apply API and UI updates. |

---

## Conflicts and recommended approach

### 1. New collection vs embed

- **Task:** “Create collection extracted_documents (or embed under documents as `extraction`).”
- **Current:** All extraction state in `documents.ai_extraction`; no extraction_id.
- **Recommendation:** **Add a new collection `extracted_documents`** with the full task schema (including audit.raw_response_json, model, prompt_version, status lifecycle). Link document via `documents.extraction_id` and `documents.extraction_status` (denormalized for list/badge). This keeps audit and lifecycle clear, avoids overloading the document document, and allows admin queue to query by status without scanning all documents. **Migration:** Existing docs with `ai_extraction` can remain as-is; new extractions write to `extracted_documents` and set extraction_id. Optionally backfill or treat “no extraction_id” as legacy (read from ai_extraction for backward compatibility in GET extraction/apply/reject).

### 2. ai_provider.py vs document_analysis + llm_chat

- **Task:** New **ai_provider.py** with `extract_compliance_fields(text, file_name, hints)`, OpenAI env vars, strict JSON schema.
- **Current:** **document_analysis.py** uses **llm_chat.chat_with_file** (Gemini, file-based).
- **Recommendation:** **Introduce ai_provider.py** as the **single** place that calls the LLM for extraction: input **text only**, output strict JSON per task schema. Use **AI_PROVIDER**, **OPENAI_API_KEY**, **AI_MODEL_EXTRACTION**, **AI_EXTRACTION_ENABLED**. **document_extraction_service** (new) should: (1) read file → extract text (PDF/OCR), cap 30k chars; (2) call **ai_provider.extract_compliance_fields(text, file_name, hints)**; (3) validate and map to extracted_documents schema; (4) set status EXTRACTED/NEEDS_REVIEW/FAILED. **Keep document_analysis.py** for backward compatibility: either have it delegate to the new pipeline (so on-demand analyze uses same path) or leave it as-is for Gemini/file path and only new “enqueue” flow uses ai_provider + text. **Safest:** New pipeline only uses ai_provider (text); existing POST /analyze can stay on document_analysis + Gemini until a later cutover, to avoid breaking current behavior.

### 3. Status lifecycle (EXTRACTED vs NEEDS_REVIEW vs CONFIRMED)

- **Current:** status "completed" or "failed"; review_status "pending" | "approved" | "rejected".
- **Task:** PENDING → EXTRACTED | NEEDS_REVIEW | FAILED; user action → CONFIRMED | REJECTED.
- **Recommendation:** In **extracted_documents** (and optionally in documents.extraction_status for list): use task statuses **PENDING, EXTRACTED, NEEDS_REVIEW, CONFIRMED, REJECTED, FAILED**. Map: after AI run, set EXTRACTED if confidence ≥ 0.85 and expiry_date present, else NEEDS_REVIEW; FAILED on error or AI_NOT_CONFIGURED. On apply → CONFIRMED; on reject → REJECTED. Frontend badge: map these 1:1 (Pending / Needs review / Extracted / Confirmed / Failed). Keep existing ai_extraction.review_status for legacy or mirror CONFIRMED/REJECTED there when applying/rejecting.

### 4. Audit actions

- **Current:** DOCUMENT_AI_ANALYZED, AI_EXTRACTION_APPLIED.
- **Task:** DOC_EXTRACT_REQUESTED, DOC_EXTRACT_SUCCEEDED, DOC_EXTRACT_NEEDS_REVIEW, DOC_EXTRACT_FAILED.
- **Recommendation:** **Add** the four DOC_EXTRACT_* actions to **AuditAction** and use them in the new extraction pipeline. Keep DOCUMENT_AI_ANALYZED for existing on-demand analyze if that path remains; or use DOC_EXTRACT_* for all extraction events once everything goes through the new pipeline.

### 5. Trigger: enqueue after upload / after intake migration

- **Recommendation:** **Do not block** upload or migration. After **documents.insert_one** in upload_document and admin_upload_document, call **enqueue_extraction(document_id, client_id, source="vault_upload", property_id=...)** (fire-and-forget or background job). After each **documents.insert_one** in **migrate_intake_uploads_to_vault**, call **enqueue_extraction(..., source="intake_upload", intake_session_id=...)**. Enqueue can write a minimal `extracted_documents` row with status PENDING and a job id, then a worker or async task runs **run_extraction_job**. If no worker exists, run_extraction_job can be invoked in-process (e.g. asyncio.create_task) so upload returns immediately and extraction runs in background.

### 6. Rate limiting

- **Recommendation:** In **document_extraction_service** (or before calling AI), check: (1) global extractions in last 1 minute (e.g. in-memory or Redis); (2) per client_id extractions in last 24 hours (e.g. from extracted_documents count or a small rate_limit collection). If over limit, set status FAILED with error_code RATE_LIMITED and do not call AI.

### 7. Backward compatibility

- **Apply/Reject:** Current apply-extraction and reject-extraction read from **document.ai_extraction**. When extraction lives in **extracted_documents**, these endpoints should: resolve document → extraction_id → load from extracted_documents; apply updates requirement and sets extracted_documents.status = CONFIRMED (and optionally documents.extraction_status); reject sets REJECTED. For documents with no extraction_id but existing ai_extraction, keep supporting apply/reject from ai_extraction so existing flows do not break.
- **GET /documents/:id/extraction:** Return extraction from extracted_documents when extraction_id is set; else fall back to document.ai_extraction for legacy.

---

## Deliverables checklist (for implementation)

- [ ] **docs/DOCUMENT_EXTRACTION_SPEC.md** – Flow, status meanings, “no legal advice” rule, data model.
- [ ] **Data model:** Collection **extracted_documents** (or equivalent) with task fields; **documents.extraction_id**, **documents.extraction_status**.
- [ ] **backend/services/ai_provider.py** – `extract_compliance_fields(text, file_name, hints)`; env AI_PROVIDER, OPENAI_API_KEY, AI_MODEL_EXTRACTION, AI_EXTRACTION_PROMPT_VERSION, AI_EXTRACTION_ENABLED; strict JSON; no legal advice in prompt.
- [ ] **backend/services/document_extraction_service.py** – enqueue_extraction, run_extraction_job; read file → text (PDF/OCR, cap 30k); call ai_provider; validate; set EXTRACTED/NEEDS_REVIEW/FAILED; store full audit (model, prompt_version, raw_response_json); rate limiting; DOC_EXTRACT_* audit events; AI disabled → FAILED, AI_NOT_CONFIGURED.
- [ ] **Trigger:** After vault upload (client + admin), enqueue_extraction (async). After each intake migration document create, enqueue_extraction (async).
- [ ] **Apply/Reject:** Confirm applies to requirement and sets CONFIRMED; Reject sets REJECTED; support both extracted_documents and legacy ai_extraction.
- [ ] **Frontend:** Status badge (Pending / Needs review / Extracted / Confirmed / Failed); Review extraction drawer (confirm / edit then confirm / reject); Admin “Extraction Review Queue” (filter NEEDS_REVIEW, FAILED; confirm/reject).
- [ ] **Tests:** AI disabled → FAILED + AI_NOT_CONFIGURED; valid JSON → EXTRACTED + expiry parsed; low confidence/missing expiry → NEEDS_REVIEW; confirm → requirement updated + CONFIRMED; reject → REJECTED, no apply; frontend badge and confirm flow.

---

## File reference (existing, for context)

| Area | File | Relevant parts |
|------|------|----------------|
| Document analysis | backend/services/document_analysis.py | analyze_document, stores ai_extraction, uses llm_chat.chat_with_file (Gemini) |
| LLM | backend/utils/llm_chat.py | chat_with_file(file_path, mime_type) – file to Gemini |
| Document routes | backend/routes/documents.py | POST /analyze/:id, GET /:id/extraction, POST /:id/apply-extraction, POST /:id/reject-extraction; upload_document, admin_upload_document |
| Intake migration | backend/services/intake_upload_migration.py | migrate_intake_uploads_to_vault – creates documents, no extraction |
| Audit | backend/models/core.py | AuditAction: DOCUMENT_AI_ANALYZED, AI_EXTRACTION_APPLIED |
| Frontend | frontend/src/pages/DocumentsPage.js | analyzeDocument, apply/reject, ai_extraction badges and review modal |
| Plan gating | backend/services/plan_registry.py | ai_extraction_basic, ai_extraction_advanced; frontend ai_review_interface, extraction_review_ui |

No refactoring of unrelated code; keep changes scoped to extraction + review only.
