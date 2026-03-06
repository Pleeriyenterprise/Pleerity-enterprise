# Prompt Manager + Seeded Templates + Deterministic Selection + Schema Validation – Audit

**Scope:** Four services (AI automation, Market research, Compliance services, Document packs).  
**Audit date:** 2025-02.  
**Do not implement blindly:** This document compares the task (which assumes a Node/Next.js monorepo) to the **existing Python FastAPI + React** codebase and calls out what is implemented, what is missing, and the safest approach.

---

## 1. Critical conflict: stack and repo structure

The task explicitly states:

- **Monorepo:** `/apps/api` (Node TS), `/apps/web` (Next.js), `/packages/shared`
- **Seed file:** `/apps/api/seed/seed_data_v1.json`
- **Seed script:** `/apps/api/scripts/seed_services_and_prompts.ts`
- **Shared:** `/packages/shared` (Zod, serviceCodes.ts, docTypes.ts, outputSchemas.ts, validators)
- **Validation:** ajv (Node JSON Schema)
- **Provider:** LLMClient with `generate({ system, user, provider, model })`

The **actual codebase** is:

- **Backend:** Python FastAPI under `backend/` (no `/apps/api`)
- **Frontend:** React (not Next.js) under `frontend/`
- **No** `/packages/shared`; no TypeScript/Zod in this repo
- **Validation:** Custom Python `SchemaValidator` and Pydantic; no ajv
- **Provider:** Python `LLMProviderInterface` + `GeminiProvider` in `prompt_service.py`

**Recommendation:** Implement all **functional** requirements in the **existing Python/React stack**. Do not introduce a Node/Next monorepo or duplicate prompt logic in TypeScript. Use a **Python seed script** and a **JSON seed file** in the backend (e.g. `backend/seed/seed_data_v1.json` and `backend/scripts/seed_services_and_prompts.py`) that mirror the task’s intent. If a separate Node/Next services repo exists or is planned, treat the task’s paths and types as a **spec** for that repo and keep this codebase as the single source of truth for the current product.

---

## 2. Non-negotiables vs current implementation

| Requirement | Implemented | Notes |
|-------------|------------|--------|
| **1) user_prompt_template MUST contain {{INPUT_DATA_JSON}} exactly once; no scattered placeholders** | ✅ Yes | `models/prompts.py`: `PromptTemplateCreate` and `PromptTemplateUpdate` validators require `{{INPUT_DATA_JSON}}` and reject other `{...}` placeholders. `document_orchestrator` checks before use and fails with clear error if missing. |
| **2) ACTIVE prompts immutable; new edits create new version** | ✅ Yes | `prompt_service.update_template`: non-DRAFT templates create a **new version** (new template_id, version N+1, DRAFT). ACTIVE is never updated in place. |
| **3) Activation requires (a) playground test pass and (b) JSON schema validation pass** | ✅ Yes | `mark_as_tested` requires a passing test result. `activate` checks template is TESTED. Test execution runs schema validation via `SchemaValidator.validate()`. |
| **4) Deterministic selection: service_code + doc_type + status=ACTIVE; if doc_type missing, count ACTIVE for service_code → if exactly 1 use it, if >1 fail** | ✅ Yes | `prompt_manager_bridge.get_prompt_for_service(service_code, doc_type=None)`: queries ACTIVE; if no doc_type, counts ACTIVE for service_code; if count > 1 returns None (explicit fail); if count == 1 uses that prompt. Never “random first”. |
| **5) Every generation stores prompt_template_id, prompt_version, provider, model, token usage, sha256 of input snapshot** | ⚠️ Partial | `prompt_version_used` (template_id, version) is stored on orders and document_versions_v2. Provider/model and token usage are in `prompt_execution_metrics` and test results; not always persisted on the **generation** record. Input snapshot hash is stored (e.g. `intake_snapshot_hash`, `json_output_hash`). **Gap:** Ensure every generation path writes provider, model, token_usage, and input_snapshot hash in one place (e.g. generation_runs or orchestration_executions). |
| **6) Runtime never uses raw intake as deliverable content; raw intake only for audit/input snapshot** | ✅ Yes | Document content is built from **structured_output** (LLM output validated against schema). Intake is used for context and stored as snapshot for audit, not injected as-is into deliverable. |

---

## 3. Deliverables vs current state

### A) Mongo collection: prompt_templates

| Field (task) | Exists | Notes |
|--------------|--------|--------|
| template_id (PTMPL-...) | ⚠️ Different format | Codebase uses `_generate_id("PT")` → **PT-...** not PTMPL-. Can align by changing prefix to "PTMPL" if desired. |
| service_code, doc_type, version, status | ✅ | status: DRAFT, TESTED, ACTIVE, DEPRECATED, ARCHIVED (task has ARCHIVED; we have DEPRECATED too). |
| system_prompt, user_prompt_template, output_schema | ✅ | output_schema stored as dict (from Pydantic OutputSchema). |
| required_output_keys (string[]) | ❌ | Not a separate field. Required keys are implied by output_schema.fields (required=True). Can add as optional denormalization. |
| created_by, created_at, activated_by, activated_at | ✅ | Implemented. |
| last_test_result { passed, provider, model, output_preview, errors[] } | ⚠️ Different shape | We have `last_test_status`, `last_test_at`, and a separate **prompt_test_results** collection with full result (schema_validation_passed, prompt_tokens, etc.). No single `last_test_result` object on the template. **Gap:** Add or map a `last_test_result` (or keep using test_results and document as “last test” in API response). |
| Audit trail in separate collection | ✅ | `prompt_audit_log`; logged on create, update, activate, deprecate, archive. |

### B) API routes (admin)

| Task route | Current | Notes |
|------------|---------|--------|
| GET /api/admin/prompts?service_code= | ✅ | GET /api/admin/prompts with service_code, doc_type, status, tags, search, pagination. |
| POST /api/admin/prompts (create draft) | ✅ | Creates DRAFT. |
| POST /api/admin/prompts/:template_id/version (clone → new version) | ⚠️ Semantics | No dedicated “clone version” endpoint. **PUT /api/admin/prompts/:template_id** with body creates a **new version** when template is not DRAFT (new template_id, version+1, DRAFT). Task’s “clone->new version” is the same outcome. **Gap:** Optional **POST /:template_id/version** that clones current version to new DRAFT without requiring other field changes. |
| POST /api/admin/prompts/:template_id/test | ⚠️ Different | We have **POST /api/admin/prompts/test** with body `{ template_id, test_input_data, ... }`. Task expects path param. Functionally equivalent. |
| POST /api/admin/prompts/:template_id/activate | ✅ | POST /api/admin/prompts/:template_id/activate (with activation_reason). |
| POST /api/admin/prompts/:template_id/archive | ⚠️ Method | We have **DELETE /api/admin/prompts/:template_id** (soft archive). Task says POST .../archive. Semantically same; can add POST .../archive that calls same logic. |
| GET /api/admin/prompts/:template_id/audit | ⚠️ Path | We have **GET /api/admin/prompts/audit/log?template_id=**. Same data; task wants path-style. Optional: add GET /api/admin/prompts/:template_id/audit that returns same entries. |

### C) Runtime bridge

| Task | Current | Notes |
|------|---------|--------|
| getActivePrompt(service_code, doc_type?) with alias resolution | ✅ | `prompt_manager_bridge.get_prompt_for_service(service_code, doc_type=None)`; SERVICE_CODE_ALIASES map; deterministic single-ACTIVE when doc_type omitted. |
| validateSingleInjection(user_prompt_template) | ✅ | Pydantic validators on create/update; runtime check in document_orchestrator before use. |
| validateOutputAgainstSchema(output, schema) | ✅ | `SchemaValidator.validate(output, schema)` in prompt_service; used in test and can be used in generation. |

### D) Seed scripts and data

| Task | Current | Notes |
|------|---------|--------|
| Seed file at /apps/api/seed/seed_data_v1.json | ❌ | No such path. Existing **POST /api/admin/prompts/seed** creates one default CLEARFORM prompt if collection empty. |
| Script: load JSON, upsert services by service_code, insert prompts as v1 DRAFT (or TESTED), never ACTIVE unless SEED_ACTIVATE=true | ❌ | No script that reads a JSON file and seeds the full list of service_code + doc_type combos. |
| Seed data: service_code + doc_type combos (AI_WF_BLUEPRINT, AI_PROC_MAP, MR_*, HMO_*, FULL_*, MOVE_*, DOC_PACK_*, etc.) | ❌ | Not in one seed file. SERVICE_DOC_TYPE_MAP in routes/prompts.py and DOCUMENT_REGISTRY in document_pack_orchestrator define doc types; no single seed_data_v1.json. |
| Document pack micro-doc doc_types in pack mapping table | ⚠️ In code | Pack doc keys (doc_rent_arrears_letter_template, etc.) live in **DOCUMENT_REGISTRY** in `document_pack_orchestrator.py` and in service_definitions_v2; **document_pack_definitions** collection exists but seed from JSON is not implemented. |

**Recommendation:** Add `backend/seed/seed_data_v1.json` (structure mirroring task) and `backend/scripts/seed_services_and_prompts.py` that: (1) load JSON, (2) upsert service_catalogue_v2 entries by service_code, (3) insert prompt_templates as version 1 DRAFT (or TESTED) with template_id PTMPL-… or keep PT-…, (4) set ACTIVE only if env SEED_ACTIVATE=true. No Node/TS script in this repo.

### E) Shared types + Zod (Node)

Task asks for:

- `/packages/shared/src/serviceCodes.ts` (canonical service_code enums)
- `/packages/shared/src/docTypes.ts` (canonical doc_type enums)
- `/packages/shared/src/schemas/outputSchemas.ts` (JSON schema objects)
- `/packages/shared/src/validators/promptTemplate.ts` (injection rule)

**Current:** No `/packages/shared` in this repo. Canonical service codes and doc types are in Python (SERVICE_CODE_ALIASES, SERVICE_DOC_TYPE_MAP, DOCUMENT_REGISTRY, service_catalogue_v2). Output schema is Pydantic `OutputSchema` with `to_json_schema()`.

**Recommendation:** Do **not** add a Node shared package in this repo. If a separate Node/Next app is introduced later, those types can be generated or hand-written there from the same canonical list. In this codebase, add a single **Python** module (e.g. `backend/models/prompt_canonical.py`) that defines SERVICE_CODES and DOC_TYPES as constants and documents the canonical list for seed and API.

### F) Optional: SERVICE_CODE_ALIASES, doc_type fallbacks

| Task | Current | Notes |
|------|---------|--------|
| SERVICE_CODE_ALIASES map | ✅ | In `prompt_manager_bridge.py`; maps legacy codes to canonical. |
| doc_type fallbacks disallowed unless deterministic | ✅ | Bridge fails explicitly when multiple ACTIVE exist and doc_type is missing or not matched. |

---

## 4. JSON Schema validation (ajv) and LLM abstraction

| Task | Current | Notes |
|------|---------|--------|
| JSON Schema validation using ajv | N/A (Python) | Python uses custom `SchemaValidator` and Pydantic; no ajv. For stricter JSON Schema compliance, consider **jsonschema** (Python) and validate with the same schema shape. |
| LLMClient with generate({ system, user, provider, model }) | ⚠️ Partial | `LLMProviderInterface` + `GeminiProvider` exist. No **OpenAI** provider in prompt_service; no request-level **provider/model** choice. |
| Playground can run on OpenAI or Gemini per request | ❌ | Test execution uses a single provider (default Gemini). No provider/model in `PromptTestRequest`. |

**Recommendation:** (1) Add an **OpenAI** provider implementing `LLMProviderInterface`. (2) Extend test request (and optional env) with `provider` and `model`; in `execute_test` select provider and call `generate(...)`. (3) Optionally add **jsonschema** and validate test/generation output with the same JSON Schema used by the frontend or external tools.

---

## 5. Seed data requirements (task list) vs codebase

Task asks for these **service_code + doc_type** pairs and pack doc_types:

- AI_WF_BLUEPRINT / AI_WORKFLOW_BLUEPRINT_REPORT  
- AI_PROC_MAP / BUSINESS_PROCESS_MAPPING_REPORT  
- AI_TOOL_RECOMMENDATION / AI_TOOL_RECOMMENDATION_REPORT  
- MR_BASIC / MARKET_RESEARCH_BASIC_REPORT  
- MR_ADV / MARKET_RESEARCH_ADVANCED_REPORT  
- HMO_COMPLIANCE_AUDIT / HMO_COMPLIANCE_AUDIT_REPORT  
- FULL_COMPLIANCE_AUDIT / FULL_COMPLIANCE_AUDIT_REPORT  
- MOVE_IN_OUT_CHECKLIST / MOVE_IN_OUT_CHECKLIST_DOC  
- DOC_PACK_ESSENTIAL / DOC_PACK_ORCHESTRATOR, DOC_PACK_TENANCY / DOC_PACK_ORCHESTRATOR, DOC_PACK_PRO / DOC_PACK_ORCHESTRATOR  
- Pack micro-doc doc_types: doc_rent_arrears_letter_template, doc_deposit_refund_letter_template, … (full list in task)

**Current:** SERVICE_DOC_TYPE_MAP in `routes/prompts.py` and DOCUMENT_REGISTRY in `document_pack_orchestrator.py` define allowed doc types and pack docs. **No single seed file** that creates prompt_templates for all of these. Orchestrator uses doc_key (e.g. doc_rent_arrears_letter_template) and doc_type (e.g. RENT_ARREARS_LETTER); task uses doc_type strings like doc_rent_arrears_letter_template. Mapping between task doc_type and existing doc_key/doc_type is straightforward.

**Recommendation:** Add `backend/seed/seed_data_v1.json` with an array of prompt template seeds (service_code, doc_type, name, system_prompt, user_prompt_template, output_schema) for each task pair. Seed script creates/updates service_catalogue_v2 and inserts prompt_templates (DRAFT, or ACTIVE only if SEED_ACTIVATE=true). Document pack doc_types can be seeded in document_pack_definitions from the same JSON or a separate section.

---

## 6. Gaps summary

| # | Gap | Severity | Recommendation |
|---|-----|----------|----------------|
| 1 | **Seed file + seed script** | High | Add `backend/seed/seed_data_v1.json` and `backend/scripts/seed_services_and_prompts.py`; load JSON, upsert services, insert prompts as v1 DRAFT; optional SEED_ACTIVATE for ACTIVE. |
| 2 | **template_id prefix PTMPL-** | Low | Optional: change `_generate_id("PT")` to `_generate_id("PTMPL")` for alignment with task. |
| 3 | **required_output_keys** | Low | Optional: add field to prompt_templates (or derive from output_schema) for API/consumers. |
| 4 | **last_test_result on template** | Low | Optional: add or compute from latest prompt_test_results entry (passed, provider, model, output_preview, errors). |
| 5 | **POST /:template_id/version (clone)** | Low | Optional: add endpoint that clones current version to new DRAFT without other edits. |
| 6 | **POST /:template_id/archive and GET /:template_id/audit** | Low | Optional: add path-style routes that delegate to existing archive and audit/log logic. |
| 7 | **Provider/model in playground** | Medium | Add provider (and optionally model) to test request; implement OpenAI provider; select in execute_test. |
| 8 | **Generation record: provider, model, token_usage, input hash** | Medium | Ensure every generation path (orchestrator, pack orchestrator) writes these to one place (e.g. generation_runs or orchestration_executions). |

---

## 7. Conflicts and safest approach

| Topic | Conflict | Safest option |
|-------|----------|----------------|
| **Stack (Node/Next vs Python/React)** | Task assumes Node/Next monorepo and Zod/ajv. | Keep single codebase in Python/React. Implement seed, deterministic selection, and validation in Python. Do not add /apps/api or /packages/shared in this repo. |
| **Seed file path** | Task: /apps/api/seed/seed_data_v1.json. | Use **backend/seed/seed_data_v1.json** and **backend/scripts/seed_services_and_prompts.py**. |
| **Archive endpoint** | Task: POST .../archive. We have DELETE. | Keep DELETE; optionally add POST .../archive that calls same archive logic. |
| **Test endpoint** | Task: POST .../:template_id/test. We have POST /test with template_id in body. | Keep current; optionally add POST /:template_id/test that forwards to same handler. |

---

## 8. What is already in place (no change needed)

- prompt_templates collection with template_id, service_code, doc_type, version, status (DRAFT/TESTED/ACTIVE/DEPRECATED/ARCHIVED), system_prompt, user_prompt_template, output_schema, created_by, created_at, activated_by, activated_at, prompt_audit_log.
- {{INPUT_DATA_JSON}} enforced; no scattered placeholders.
- ACTIVE immutable; updates create new version.
- Activation requires TESTED and schema validation in test.
- Deterministic selection in prompt_manager_bridge (service_code + doc_type; when doc_type missing, exactly one ACTIVE required).
- SERVICE_CODE_ALIASES.
- Admin API: list, create, get, update, delete (archive), mark-tested, activate, test, version history, audit/log (with template_id filter).
- Runtime: get_prompt_for_service, validation before use, schema validation in tests.
- Document pack DOCUMENT_REGISTRY with doc_key and doc_type for all task-listed pack docs.

---

## 9. Files reference (current)

- **Backend:**  
  - `backend/models/prompts.py` (Pydantic models, {{INPUT_DATA_JSON}} validation)  
  - `backend/services/prompt_service.py` (CRUD, test, activate, SchemaValidator, LLMProviderInterface, GeminiProvider)  
  - `backend/services/prompt_manager_bridge.py` (get_prompt_for_service, SERVICE_CODE_ALIASES, deterministic selection)  
  - `backend/routes/prompts.py` (admin prompt API, seed, audit/log)  
  - `backend/services/document_orchestrator.py` (uses bridge, stores prompt_version_used)  
  - `backend/services/document_pack_orchestrator.py` (DOCUMENT_REGISTRY, pack doc_types)  
- **Frontend:**  
  - `frontend/src/pages/AdminPromptManagerPage.js` (list, create, edit, test, activate, token usage, sample order)  
- **DB:**  
  - prompt_templates, prompt_audit_log, prompt_test_results, prompt_execution_metrics; document_pack_definitions.

---

## 10. Recommended implementation order (if implementing in this codebase)

1. **Seed data and script (Python)**  
   - Add `backend/seed/seed_data_v1.json` with services and prompt template definitions for all task-listed service_code + doc_type pairs.  
   - Add `backend/scripts/seed_services_and_prompts.py`: load JSON, upsert service_catalogue_v2, insert prompt_templates as v1 DRAFT; support SEED_ACTIVATE for ACTIVE.  
   - Optionally seed document_pack_definitions from same or related structure.

2. **Playground provider/model**  
   - Add OpenAI provider implementing `LLMProviderInterface`.  
   - Add optional `provider` and `model` to test request; in `execute_test`, choose provider and call generate; persist provider/model in test result.

3. **Generation audit fields**  
   - Ensure orchestration and pack orchestration write provider, model, token_usage, and input_snapshot hash to the chosen generation record (e.g. orchestration_executions or generation_runs).

4. **Optional API alignments**  
   - POST /api/admin/prompts/:template_id/version (clone to new version).  
   - POST /api/admin/prompts/:template_id/archive.  
   - GET /api/admin/prompts/:template_id/audit.  
   - template_id prefix PTMPL if desired; required_output_keys and last_test_result if needed.

This audit reflects the current codebase. Implement only what adds value; avoid duplicating logic or introducing a second stack in this repo.

---

## 11. Implementation status (safest approach completed)

- **Seed data:** `backend/seed/seed_data_v1.json` created with services and prompts for all task-listed service_code + doc_type pairs; `pack_doc_types` list included.
- **Seed script:** `backend/scripts/seed_services_and_prompts.py` loads JSON, upserts services (insert new only; existing untouched except updated_at), inserts prompt templates as v1 DRAFT (or ACTIVE if `SEED_ACTIVATE=true`). Idempotent on prompts (skips if pair exists). Template ID prefix: PTMPL.
- **Playground provider/model:** Backend already had OpenAI + Gemini providers and `provider`/`model` on test request/result. Frontend updated: test form includes Provider (Gemini/OpenAI) and optional Model override; result shows provider/model and token usage.
- **Generation records:** `orchestration_executions` and `generation_runs` already store provider, model, prompt_tokens, completion_tokens, intake_snapshot_hash.
- **Optional API/prefix:** Path-style `GET /:template_id/audit`, `POST /:template_id/version` (clone), `POST /:template_id/archive` and PTMPL prefix were already present in codebase.
