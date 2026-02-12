# Document Generation Workflow — End-to-End Audit

**Scope:** Trace document generation from trigger → prompt selection/rendering → model call → validation → template render → storage → delivery. File paths and function names are referenced for precision. **No code changes** — audit only.

---

## 1. Trigger Points

| Trigger | Entry | File:Function / Route | Notes |
|--------|--------|------------------------|-------|
| **Stripe webhook (order payment)** | Checkout completed for order intake | `stripe_webhook_service.py` → `_handle_order_payment`; then `document_pack_webhook_handler.handle_checkout_completed` when `service_code` in `VALID_PACK_CODES` | Document pack only: creates `document_pack_items`, sets order to QUEUED. Does **not** call GPT/render. |
| **Workflow WF1 (payment → queue)** | After payment verified | `workflow_automation_service.py` → `wf1_payment_to_queue` | Transitions order PAID → QUEUED. Does not generate documents. |
| **Workflow WF2 (queue → generation)** | Worker picks QUEUED order | `workflow_automation_service.py` → `wf2_queue_to_generation` | Calls `document_orchestrator.execute_generation(order_id, intake_data=order.get("parameters", {}))`. **Primary GPT + render path.** |
| **Workflow WF4 (regeneration)** | Admin requests regen from review | `workflow_automation_service.py` → `wf4_regeneration` | Calls `orchestrator.execute_generation(..., regeneration=True, regeneration_notes=...)`. |
| **Admin orchestration API** | Manual generate/regenerate | `routes/orchestration.py`: `POST /api/orchestration/generate`, `POST /api/orchestration/regenerate` | `document_orchestrator.execute_full_pipeline(order_id, intake_data=request.intake_data, ...)`. |
| **Admin orders “generate documents”** | Manual trigger per order | `routes/admin_orders.py` → `POST /{order_id}/generate-documents` | Uses `document_generator.generate_documents(order_id, ...)` → **RealDocumentGenerator** (no GPT; builds DOCX/PDF from order params only). |
| **Document pack admin** | Generate one or all pack items | `routes/document_packs.py`: `POST .../orders/{order_id}/items/{item_id}/generate`, `POST .../orders/{order_id}/generate-all` | `document_pack_orchestrator.generate_document(item_id, input_data, ...)` or `generate_all_documents`. GPT path; stores **generated_output** on `document_pack_items` (no DOCX/PDF file in this path). |

**Summary:** The path that produces **stored DOCX/PDF “generated documents”** is: **document_orchestrator** → **template_renderer** (used by WF2, WF4, and orchestration API). Document pack path produces JSON `generated_output` on items; RealDocumentGenerator produces DOCX/PDF from order data without LLM.

---

## 2. Job/State Model (Collections, Statuses, Transitions)

### Orders (order workflow)

- **Collection:** `orders`
- **Status field:** `status` (and `order_status` in some reads). Values from `OrderStatus` enum in `services/order_workflow.py` (e.g. CREATED, PAID, QUEUED, IN_PROGRESS, DRAFT_READY, INTERNAL_REVIEW, REGEN_REQUESTED, REGENERATING, CLIENT_INPUT_REQUIRED, FINALISING, DELIVERING, COMPLETED, DELIVERY_FAILED, FAILED, CANCELLED).
- **Relevant transitions for doc gen:** PAID → QUEUED (WF1); QUEUED → IN_PROGRESS → DRAFT_READY (WF2) or FAILED; INTERNAL_REVIEW → REGEN_REQUESTED → REGENERATING → INTERNAL_REVIEW (WF4).
- **Order doc state:** `document_versions` (array on order), `document_status`, `review_status`, `orchestration_status`, `current_version`, `prompt_version_used`, `version_locked`, `approved_document_version`.

### Orchestration executions

- **Collection:** `orchestration_executions` (see `document_orchestrator.py`, `COLLECTION = "orchestration_executions"`).
- **Purpose:** One record per run of the full pipeline (intake snapshot, structured_output, rendered doc metadata, prompt_version_used, hashes). Inserted in Step 8 of `execute_full_pipeline` (around line 474).
- **Fields (key):** `order_id`, `service_code`, `prompt_id`, `version`, `status` (e.g. REVIEW_PENDING), `prompt_version_used`, `intake_snapshot`, `intake_snapshot_hash`, `structured_output`, `json_output_hash`, `rendered_documents` (docx/pdf filename, sha256, size), `validation_issues`, `data_gaps`, `is_regeneration`, `regeneration_notes`, token counts, `created_at`.

### Document versions (rendered files)

- **Collection:** `document_versions_v2` (see `template_renderer.py`, `VERSIONS_COLLECTION = "document_versions_v2"`).
- **Purpose:** One record per rendered version; stores metadata and GridFS references for DOCX/PDF.
- **Fields (key):** `order_id`, `order_ref`, `service_code`, `version`, `status`, `prompt_version_used`, `docx`/`pdf` (filename, sha256_hash, size_bytes, later `gridfs_id`), `intake_snapshot_hash`, `json_output_hash`, `intake_snapshot`, `structured_output`, `created_at`, `created_by`.

### Document pack items

- **Collection:** `document_pack_items` (see `document_pack_orchestrator.py`, `COLLECTION = "document_pack_items"`).
- **Status:** PENDING → GENERATING → COMPLETED (or FAILED). No DOCX/PDF storage in codebase; only `generated_output` (JSON) and `prompt_version_used` on the item.

### Order status vs orchestration status

- **Orchestration status** (on order): Set during pipeline in `document_orchestrator` (e.g. INTAKE_LOCKED, GENERATING, RENDERING, REVIEW_PENDING). Defined in `OrchestrationStatus` in `document_orchestrator.py`.

---

## 3. Prompt Selection Path (per service_code / doc_type)

- **Orchestrator path** (`document_orchestrator.execute_full_pipeline`):
  - **Service code:** From `order["service_code"]`.
  - **Doc type:** Canonical rule `doc_type = service_code` (line ~268).
  - **Lookup:** `prompt_manager_bridge.get_prompt_for_service(service_code=service_code, doc_type=doc_type)` in `services/prompt_manager_bridge.py`. If no match and service is DOC_PACK_*, retry with `service_code="DOC_PACK_ORCHESTRATOR"`.
  - **Fallback:** Legacy `get_prompt_for_service(service_code)` from `gpt_prompt_registry` (in bridge).
  - **Result:** `PromptDefinition` (system_prompt, user_prompt_template, output_schema, etc.) and `ManagedPromptInfo` (template_id, version, source). If no prompt_def, pipeline returns failure: `"No prompt defined for service: {service_code}"`.

- **Document pack item path** (`document_pack_orchestrator.generate_document`):
  - **Doc type:** From item’s `doc_key` → `DOCUMENT_REGISTRY.get(item["doc_key"])` → `definition.doc_type`.
  - **Service code:** `_get_service_code_for_doc_type(definition.doc_type)` (e.g. RENT_ARREARS_LETTER → DOC_PACK_ESSENTIAL).
  - **Lookup:** `bridge.get_prompt_for_service(service_code=..., doc_type=definition.doc_type)`.
  - **Failure:** If no prompt_def/prompt_info, raises `ValueError("No active prompt found for ...")`.

---

## 4. Render Step: Intake + Computed Fields → Final Prompt String

- **Managed prompts (Prompt Manager):** Single injection pattern.
  - **Function:** `prompt_manager_bridge.build_user_prompt_with_json` in `services/prompt_manager_bridge.py` (lines ~276–299).
  - **Logic:** `input_json = json.dumps(intake_data, indent=2, default=str)`; `user_prompt = template.replace("{{INPUT_DATA_JSON}}", input_json)`. If regeneration, appends REGENERATION REQUEST text with `regeneration_notes`.
  - **Critical:** The **only** substitution is `{{INPUT_DATA_JSON}}`. If the template does not contain `{{INPUT_DATA_JSON}}`, intake is not injected (or only partially). If the template is empty or wrong, the prompt may be effectively empty or not data-bound.

- **Legacy prompts (orchestrator):** Format-string substitution.
  - **Function:** `document_orchestrator._build_user_prompt` in `services/document_orchestrator.py` (lines ~596–628).
  - **Logic:** Copy intake with empty string for missing keys; add `regeneration_context` if regen; `user_prompt = prompt_def.user_prompt_template.format(**data)`; on `KeyError`, fallback to per-key `.replace("{{{key}}}", ...)`.
  - **Risk:** If template uses `{variable}` and intake has no such key, format can throw or leave placeholders; fallback replaces with "Not provided".

---

## 5. Model Call and Response Parsing/Validation

- **Orchestrator:** `document_orchestrator._execute_gpt` (lines ~630–706).
  - **System prompt:** `prompt_def.system_prompt` + appended JSON schema and “Return ONLY the JSON object…”.
  - **Client:** `LlmChat` from `emergentintegrations.llm.chat` with `system_message`, then `with_model("gemini", "gemini-2.0-flash")`; `response = await client.send_message(UserMessage(text=user_prompt))`.
  - **Response handling:** `response_text` = string from response; strip ```json/``` wrappers; `structured_output = json.loads(response_text)`.
  - **On JSONDecodeError:** Does **not** return failure. Sets:
    - `structured_output = {"raw_response": response_text, "parse_error": str(e), "data_gaps_flagged": ["Response could not be parsed as JSON"]}`.
  - **Empty check (Step 6b):** Only `if not structured_output or len(structured_output) == 0` → return failure. The parse-error wrapper has length 3, so **pipeline continues** and this dict is passed to the template renderer.

- **Document pack:** `document_pack_orchestrator.generate_document` uses `prompt_service._parse_llm_output(raw_output)` (`prompt_service.py` ~1133–1152). On parse failure returns `None`; code then raises `ValueError("Failed to parse LLM output as JSON")`, so **no** storage of raw response on the item.

- **Validation:** Orchestrator uses `validate_intake_data(prompt_def.service_code, intake_data)` (legacy) and logs missing fields but does not block. No schema validation of **structured_output** in the orchestrator before render. Document pack path checks `definition.output_keys` vs `parsed_output.keys()` and only logs missing keys.

---

## 6. DOCX/PDF Production (Template Renderer)

- **Entry:** `template_renderer.render_from_orchestration` in `services/template_renderer.py` (lines ~176–398). Called from orchestrator Step 7 with `order_id`, `structured_output`, `intake_snapshot`, `is_regeneration`, `regeneration_notes`, `prompt_version_used`.
- **Versioning:** New version = `existing_versions + 1`; previous versions marked SUPERSEDED via `_mark_previous_superseded`.
- **DOCX:** `_render_docx(order, structured_output, intake_snapshot, version, status, regeneration_notes)` → `_add_docx_content(doc, structured_output, service_code)` (line ~496). Content routing:
  - `service_code.startswith("AI_")` → `_render_ai_service_content`
  - `startswith("MR_")` → `_render_market_research_content`
  - `startswith("COMP_")` → `_render_compliance_content`
  - `startswith("DOC_PACK_")` → `_render_document_pack_content`
  - else → `_render_generic_content`
- **Generic content** (`_render_generic_content`, lines ~968–988): Iterates `for key, value in output.items()`, **skips only `data_gaps_flagged`**. Adds a section for every other key, including **`raw_response`** and **`parse_error`**, with value as paragraph text. So if the orchestrator passed the parse-error wrapper, **raw_response (and parse_error) are rendered into the DOCX** as section content.
- **PDF** (`_add_pdf_content`, lines ~1149–1195): Explicitly **skips** keys in `["data_gaps_flagged", "raw_response", "parse_error"]`. So PDF does not show raw_response/parse_error; DOCX generic path does.

---

## 7. Storage and Linking

- **Rendered files:** GridFS bucket `order_files` (see `template_renderer.py` ~343–382). DOCX and PDF uploaded with metadata: `order_id`, `version`, `format`, `sha256_hash`, `content_type`. GridFS IDs stored on `document_versions_v2` as `docx.gridfs_id`, `pdf.gridfs_id`.
- **Order link:** `document_versions_v2` holds `order_id`, `version`; order’s `document_versions` array is updated by orchestrator (Step 9) with `filename_docx`, `filename_pdf`, hashes, `prompt_version_used`, etc. Order also gets `document_status`, `review_status`, `orchestration_status`, `current_version`, `prompt_version_used`, `last_generation_at`.
- **Execution record:** `orchestration_executions` stores full audit record (intake_snapshot, structured_output, rendered_documents, prompt_version_used, hashes, token counts).
- **Document pack:** Only `document_pack_items` updated with `generated_output`, `prompt_version_used`, `input_snapshot_hash`, `generated_at`; no GridFS or document_versions_v2 in this path.

---

## 8. Idempotency (Duplicate Trigger Handling)

- **Orchestrator:** No idempotency key per “generate” request. Each call creates a new version (version increment in template_renderer). Duplicate triggers (e.g. double WF2 run) can create multiple versions unless prevented at workflow layer (e.g. status check: only QUEUED → IN_PROGRESS).
- **WF2:** Checks `order["status"] != OrderStatus.QUEUED.value` and returns error if not QUEUED; then transitions to IN_PROGRESS. So a second WF2 run for the same order would see IN_PROGRESS and fail the check. No idempotency by idempotency_key or event_id.
- **Document pack:** `generate_document` updates an existing item by `item_id`; status moves PENDING → GENERATING → COMPLETED. No duplicate item creation for same (order_id, item_id). Creating items is done once in webhook (`create_document_items`).

---

## 9. Logging / Audit Coverage

- **Orchestrator:** Logs “Intake snapshot created … hash=…”, “Selected prompt for … template_id …”, “Pipeline complete for … DOCX=… PDF=… Prompt=…”. Execution record in `orchestration_executions` includes prompt_version_used, hashes, token counts, validation_issues, data_gaps. No explicit “prompt hash” of the final user prompt string; intake_snapshot_hash and json_output_hash are stored.
- **Template renderer:** Logs “Stored files in GridFS: DOCX=…, PDF=…”, “Rendered documents for …”.
- **Document pack:** Logs “Generated document {item_id} ({doc_type})”; on failure logs and sets `error_message` on item.
- **Gaps:** No centralized log line that always records (doc_type, model, job_id/order_id, prompt_hash, success/error) in one place for every generation attempt.

---

## 10. Failure Modes That Can Explain “Raw Intake Saved as Generated Document”

1. **Parse failure treated as success (orchestrator)**  
   **File:** `document_orchestrator.py`, `_execute_gpt`.  
   When `json.loads(response_text)` fails, the code sets `structured_output = {"raw_response": response_text, "parse_error": ..., "data_gaps_flagged": [...]}`. The empty-output check only requires `len(structured_output) == 0`, so this wrapper passes. The pipeline continues to render. If the LLM had returned raw intake (e.g. echoed JSON or plain text), that text is in `raw_response` and can be rendered into the document.

2. **Generic DOCX renderer includes `raw_response` and `parse_error`**  
   **File:** `template_renderer.py`, `_render_generic_content`.  
   Only `data_gaps_flagged` is skipped. So for any service that hits the generic branch (non-AI_, non-MR_, non-COMP_, non-DOC_PACK_), the parse-error wrapper produces sections “Raw Response” and “Parse Error” with the raw text in the DOCX. That is the exact “raw intake (or raw model output) saved as generated document” path.

3. **Missing or wrong prompt template**  
   If no prompt is found, orchestrator returns early with “No prompt defined for service”. If the template is wrong (e.g. no `{{INPUT_DATA_JSON}}` or wrong placeholders), the **user prompt** sent to the model may be empty or contain literal placeholders; the model might then echo request data or produce non-JSON. That can feed into (1) and (2).

4. **Wrong field used as document body**  
   If the schema or renderer expected a specific key (e.g. `sections` or `document_contents`) but the model returns something else (e.g. `raw_response` from the error wrapper), the generic renderer still renders all keys. So “wrong field” here is partly “error wrapper keys rendered as content” (see 1 and 2).

5. **Model call passing intake JSON as prompt**  
   The intended path is: intake → `build_user_prompt_with_json` → single replacement of `{{INPUT_DATA_JSON}}` with `json.dumps(intake_data)`. So the **prompt** correctly contains intake as JSON inside a template. If a bug elsewhere passed **only** intake JSON with no template (e.g. user_prompt = intake_data), that would be a different bug; not found in the traced code. The observed risk is (1)–(2): **response** (or echoed intake) in `raw_response` being rendered.

6. **Validation bypass**  
   Orchestrator does not validate `structured_output` against a schema before render. So an invalid or parse-error wrapper structure is not rejected; it is sent to the template renderer. Document pack path validates only that `parsed_output` is non-null and checks output_keys; it does not validate structure or content.

---

## 11. Prioritized Fix Plan (Do Not Implement)

### Tier 1 — Minimal guardrails / validation

1. **Treat parse-error wrapper as failure in orchestrator**  
   **File:** `document_orchestrator.py`, after `_execute_gpt` (or inside it). If `structured_output` contains `"parse_error"` or `"raw_response"`, return `OrchestrationResult(success=False, ...)` and do not call the template renderer.  
   **Effect:** Prevents any parse-failure path from producing a stored document.

2. **Skip `raw_response` and `parse_error` in generic DOCX content**  
   **File:** `template_renderer.py`, `_render_generic_content`. Add the same skip as in PDF: `if key in ["data_gaps_flagged", "raw_response", "parse_error"]: continue`.  
   **Effect:** Even if the error wrapper ever reaches the renderer, it will not appear as document body.

3. **Optional: schema validation of structured_output before render**  
   **File:** `document_orchestrator.py`, between Step 6b and Step 7. Validate `structured_output` against the prompt’s expected schema (or a minimal required shape). On failure, return with error and do not render.  
   **Effect:** Rejects malformed or non-conforming output before any file is written.

### Tier 2 — Reliability (job queue, retries)

4. **Idempotency for orchestration runs**  
   **File:** `document_orchestrator.py` and/or `workflow_automation_service.py`. For a given (order_id, regeneration=False), consider storing an idempotency key (e.g. from request or event_id) and skipping if a successful execution already exists for that key. Or enforce at workflow layer (e.g. only one IN_PROGRESS per order).  
   **Effect:** Reduces duplicate versions and double charges from duplicate triggers.

5. **Retry policy for transient failures**  
   **File:** `workflow_automation_service.py` (WF2) and/or job runner. On GPT or render failure (transient), retry with backoff instead of immediately marking FAILED; cap attempts and then fail.  
   **Effect:** Fewer orders stuck in FAILED due to transient errors.

6. **Structured logging for every generation**  
   **File:** Single place (e.g. at start of `execute_full_pipeline` and at end, or in a small wrapper). Log at least: order_id, service_code, doc_type, prompt_template_id (or hash), model, success/failure, error_message, and if available job_id/execution_id.  
   **Effect:** Easier to trace and debug “raw intake as document” and other issues.

---

**End of audit.**
