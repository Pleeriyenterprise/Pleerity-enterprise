# Enterprise Prompt Manager – Codebase Audit vs Task Requirements

**Scope:** Four services (AI automation, Market research, Compliance services, Document packs).  
**Audit date:** 2025-02 (codebase state at audit).  
**Do not implement blindly:** This document compares task requirements to the existing implementation and calls out gaps and safe options.

---

## 1. Collection and schema

| Requirement | Implemented | Location / notes |
|-------------|-------------|------------------|
| **Collection:** `prompt_templates` | ✅ Yes | `backend/server.py` (indexes), `backend/services/prompt_service.py` (`COLLECTION = "prompt_templates"`) |
| **template_id** | ✅ Yes | Generated in `prompt_service.create_template` (e.g. `PT-...`), unique index in DB |
| **service_code** | ✅ Yes | Required in create/update, indexed |
| **doc_type** | ✅ Yes | Required, indexed (service_code + doc_type + status/version) |
| **version** | ✅ Yes | Integer, incremented for new versions |
| **status: DRAFT \| TESTED \| ACTIVE \| ARCHIVED** | ✅ Yes (plus DEPRECATED) | `models/prompts.py` `PromptStatus`: DRAFT, TESTED, ACTIVE, DEPRECATED, ARCHIVED. DEPRECATED is used when a new version is activated; task did not mention it but it fits the lifecycle. |
| **system_prompt** | ✅ Yes | Stored and used in tests/activation |
| **user_prompt_template** (must contain `{{INPUT_DATA_JSON}}`) | ✅ Yes | Validated in `PromptTemplateCreate` / `PromptTemplateUpdate` via `field_validator`; create/update reject if placeholder missing |
| **output_schema** (JSON Schema) | ✅ Yes | Stored as dict (from `OutputSchema`), used for validation in tests and activation |
| **created_by, created_at** | ✅ Yes | Set on create |
| **activated_by, activated_at** | ✅ Yes | Set on activation in `activate_template` |
| **last_test_result** | ⚠️ Partial | Task: single “last_test_result”. Implemented as: `last_test_status`, `last_test_at`, `test_count` on template, and full results in `prompt_test_results`. Functionally equivalent; no separate `last_test_result` object on the template. |

**Conclusion:** Collection and fields are implemented. Only naming difference: “last test” is expressed as status + timestamp (and count) rather than one `last_test_result` object.

---

## 2. Rules

| Requirement | Implemented | Location / notes |
|-------------|-------------|------------------|
| **ACTIVE prompts immutable** | ✅ Yes | `prompt_service.update_template`: DRAFT updated in place; TESTED/ACTIVE trigger creation of a *new version* (new template_id, version+1). Original ACTIVE is never overwritten; it is set to DEPRECATED when a new version is activated. |
| **Activation requires schema validation test pass** | ✅ Yes | `activate_template` checks `template["status"] == TESTED` and `template["last_test_status"] == PASSED`. Otherwise raises `ValueError`. `mark_as_tested` also requires a passing test. |
| **Deterministic selection: service_code + doc_type match exactly** | ✅ Yes | `get_active_template(service_code, doc_type)` queries `{ service_code, doc_type, status: ACTIVE }`. Exact match only. |
| **If doc_type missing and multiple ACTIVE exist, fail explicitly** | ✅ Yes | In `prompt_manager_bridge.get_prompt_for_service`: when `doc_type` is not provided, it counts ACTIVE prompts for that service_code; if count > 1 it returns `(None, None)` and logs that selection is ambiguous. When doc_type is provided but no template matches and count > 1, it also returns `(None, None)` instead of picking one. |

**Conclusion:** All stated rules are enforced. No conflicts.

---

## 3. Admin API (prompts)

| Requirement | Implemented | Location / notes |
|-------------|-------------|------------------|
| **List prompts (per service)** | ✅ Yes | `GET /api/admin/prompts` with optional `service_code`, `doc_type`, `status`, `tags`, `search`; used by Admin UI with service filter. |
| **Create new version** | ✅ Yes | New template: `POST /api/admin/prompts`. New version from existing: `PUT /api/admin/prompts/{template_id}` with update payload; for non-DRAFT this creates a new template (new template_id, version+1). |
| **Test playground (execute test)** | ✅ Yes | `POST /api/admin/prompts/test/execute` with `PromptTestRequest` (template_id, test_input_data dict, optional temperature/max_tokens overrides). Runs LLM, validates against output_schema, stores result in `prompt_test_results`, returns `PromptTestResult` (includes schema pass/fail, tokens, output). |
| **Get test results for template** | ✅ Yes | `GET /api/admin/prompts/test/{template_id}/results` for history. |

**Conclusion:** Backend supports list per service, create/new version, and test playground with schema validation and token metrics.

---

## 4. Admin UI

| Requirement | Implemented | Location / notes |
|-------------|-------------|------------------|
| **List prompts per service** | ✅ Yes | `AdminPromptManagerPage.js`: filters by `service_code` (and status/search); table shows service_code, doc_type, status, version, last test status, actions. |
| **Create new version** | ✅ Yes | “Create template” dialog; edit of non-DRAFT template triggers backend “new version” flow. Version history available. |
| **Test playground: pick sample order OR paste sample INPUT_DATA_JSON** | ⚠️ Paste only | Playground has a textarea for **paste JSON** only. There is **no “pick sample order”** (e.g. dropdown to choose an order and use its payload as `test_input_data`). |
| **Show output + schema pass/fail + token usage** | ⚠️ Output and schema only | Playground result shows: status badge, execution_time_ms, schema_validation_passed / schema_validation_errors, parsed_output/raw_output. **Token usage (prompt_tokens, completion_tokens) is not displayed.** The API already returns these in `PromptTestResult`; the UI simply does not render them. |

**Conclusion:**  
- **Gap 1:** Playground has no “pick sample order”; only paste JSON.  
- **Gap 2:** Playground does not show token usage (prompt_tokens, completion_tokens) even though the API provides them.

---

## 5. Where prompts are used (four services)

- **Runtime selection:** `prompt_manager_bridge.get_prompt_for_service(service_code, doc_type)` is used by the document/orchestration path. It uses `prompt_templates` with ACTIVE status and enforces deterministic selection (and explicit failure when doc_type is missing and multiple ACTIVE exist).
- **Service catalogue alignment:** `prompt_service` validates `service_code` and `doc_type` against the service catalogue in create and activate flows (`_validate_service_catalogue_alignment`).
- **Indexes:** `server.py` and `ensure_services_indexes.py` create indexes on `template_id` (unique), (service_code, doc_type, status), (service_code, doc_type, version), status, and (in script) deleted_at.

No duplication or conflict with another “prompt manager” implementation was found; a single path uses `prompt_templates` and the same lifecycle.

---

## 6. Conflicts and safe choices

- **Status values:** Task: DRAFT | TESTED | ACTIVE | ARCHIVED. Code also has DEPRECATED. Keeping DEPRECATED is the right design (previous ACTIVE when a new one is activated); no conflict. No change needed.
- **“last_test_result”:** Task asks for a single field; code uses `last_test_status` + `last_test_at` (+ optional full results in another collection). Functionally equivalent. Safest option: keep current schema; no migration. If a single JSON object is desired later, it can be added as an optional denormalized field populated from the latest test run.
- **Test input:** Task says “pick sample order OR paste sample INPUT_DATA_JSON”. Today only paste exists. Adding “pick sample order” is an enhancement: new API (e.g. list orders or get one order’s payload) + UI dropdown. No conflict with existing paste flow.

---

## 7. Summary: implemented vs missing

| Area | Implemented | Missing / optional |
|------|-------------|---------------------|
| Collection & fields | ✅ All required fields and rules | Optional: explicit `last_test_result` object (current design sufficient) |
| ACTIVE immutable | ✅ | — |
| Activation only after schema test pass | ✅ | — |
| Deterministic selection & fail when ambiguous | ✅ | — |
| Admin API: list, create, new version, test, test results | ✅ | — |
| Admin UI: list per service, create/new version | ✅ | — |
| Playground: paste INPUT_DATA_JSON | ✅ | — |
| Playground: pick sample order | — | ⚠️ Not implemented |
| Playground: show output + schema pass/fail | ✅ | — |
| Playground: show token usage | — | ⚠️ API returns it; UI does not show it |

---

## 8. Recommended next steps (if implementing)

1. **Token usage in Playground (low risk)**  
   In `AdminPromptManagerPage.js`, in the Test Result section, after execution time (or next to it), display `testResult.prompt_tokens` and `testResult.completion_tokens` (and optionally total). Data is already in the response; no API change.

2. **“Pick sample order” (optional enhancement)**  
   - Backend: e.g. `GET /api/admin/prompts/test/sample-orders` (or `GET /api/admin/orders` with minimal fields) and `GET /api/admin/orders/{order_id}/intake-payload` (or equivalent) to return the JSON that would be used as `INPUT_DATA_JSON` for that order.  
   - Frontend: In the test dialog, add a control (e.g. dropdown) “Use payload from order” and call the new endpoint(s), then set `test_input_data` from the selected order’s payload.  
   This does not conflict with the existing paste JSON flow; it only adds another way to fill the same field.

3. **No change recommended**  
   - Do not remove or rename DEPRECATED status.  
   - Do not add a mandatory `last_test_result` object unless product explicitly requires it; current fields are enough for “last test” semantics.

---

## 9. Files reference

- **Models:** `backend/models/prompts.py` (PromptStatus, create/update/response, test request/result, output schema).
- **Service:** `backend/services/prompt_service.py` (CRUD, versioning, test execution, activation, audit).
- **Routes:** `backend/routes/prompts.py` (prefix `/api/admin/prompts`).
- **Bridge (runtime):** `backend/services/prompt_manager_bridge.py` (get ACTIVE prompt for service/doc_type, deterministic and explicit fail when ambiguous).
- **UI:** `frontend/src/pages/AdminPromptManagerPage.js` (list, filters, create/edit, test dialog, activate, analytics).
- **Indexes:** `backend/server.py`, `backend/scripts/ensure_services_indexes.py`.

This audit is accurate as of the current codebase and can be used to implement the two small gaps (token display, optional “pick sample order”) without duplicating or conflicting with the existing Enterprise Prompt Manager.
