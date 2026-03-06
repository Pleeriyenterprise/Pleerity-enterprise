# Orchestrator Plan + Canonical Order + Seed Data Audit

**Scope:** Orchestrator decides the plan and canonical order; per-document micro-prompts generate each document independently; seed data file `seed_data_v1.json` (task structure vs current).  
**Do not implement blindly.** This document compares task requirements to the codebase and identifies gaps and safe options.

---

## 1. Task requirements (summary)

- **Orchestrator** decides the **plan** and **canonical order**.
- **Per-document micro-prompts** generate each document **independently**.
- **Seed data:** `seed_data_v1.json` with **services** (and optionally prompts) in the task-defined shape:
  - Services: `service_code`, `name`, `category` (e.g. "Automation Services"), `description_preview`, `base_price_gbp`, `currency`, `requires_review`, `document_types[]`, `is_active`, `seo_slug`.

---

## 2. What is already implemented

### 2.1 Orchestrator decides plan + canonical order

**Document pack (multi-doc) flow**

- **File:** `backend/services/document_pack_orchestrator.py`
- **Plan:** Pack tier (ESSENTIAL / PLUS / PRO) and client-selected doc_keys determine which documents are in scope. Allowed docs come from `get_allowed_docs(pack_tier)` (inheritance: PRO ⊇ PLUS ⊇ ESSENTIAL).
- **Canonical order:** `CANONICAL_ORDER` per tier (ordered list of `doc_key`). `filter_and_order_docs(service_code, selected_docs)` returns `(doc_key, canonical_index, DocumentDefinition)` **sorted by canonical order**.
- **Creation:** `create_document_items(order_id, service_code, selected_docs, input_data)` uses `filter_and_order_docs` and creates one `DocumentItem` per doc in that order and persists them.

So for packs: **plan = filtered + ordered list of doc_keys; canonical order is enforced server-side.**

**Single-document (non-pack) flow**

- **File:** `backend/services/document_orchestrator.py`
- **Plan:** One document per order. `doc_type` is derived from `service_code` (canonical rule: `doc_type = service_code` for single-doc services) or from service/prompt configuration.
- There is no “list of documents” to order; the plan is implicitly “one doc.”

So for single-doc: **plan = single doc; no canonical ordering (N/A).**

### 2.2 Per-document micro-prompts generate each document independently

**Pack flow**

- **File:** `backend/services/document_pack_orchestrator.py`
- For each document item, `generate_document_item(item_id)` (and the internal path that generates one doc):
  - Resolves `DocumentDefinition` from `DOCUMENT_REGISTRY` by `doc_key`.
  - Looks up prompt via `prompt_manager_bridge.get_prompt_for_service(service_code, doc_type)` (service_code derived from doc_type for pack docs).
  - Builds user prompt with `build_user_prompt_with_json(...)` (single `{{INPUT_DATA_JSON}}` injection).
  - Calls LLM once per document; parses and validates output; renders DOCX/PDF; stores version and metadata.
- Each document is generated in a separate LLM call with its own prompt (micro-prompt per doc). Items are processed in canonical order (when the pipeline runs them in sequence).

**Single-doc flow**

- **File:** `backend/services/document_orchestrator.py`
- One prompt per order; one LLM call; one document. “Per-document” applies only to packs.

So: **per-document micro-prompts are implemented for packs; single-doc is single prompt per order (as intended).**

### 2.3 Seed data file and script

- **File:** `backend/seed/seed_data_v1.json`
- **Script:** `backend/scripts/seed_services_and_prompts.py`
- **Current behaviour:** Reads `services` and `prompts` from JSON. For each service, builds a minimal `service_catalogue_v2` document (upsert by `service_code`). For each prompt, inserts into `prompt_templates` if `(service_code, doc_type)` does not exist.
- **Current service shape in seed JSON:** `service_code`, `service_name`, `category` (e.g. `ai_automation`), `description`, `workflow_name`, `display_order` (and optional `base_price`, etc. in `_minimal_service_doc`).

---

## 3. Seed data: task shape vs current shape

Task expects a **service** object like:

```json
{
  "service_code": "AI_WF_BLUEPRINT",
  "name": "Workflow Automation Blueprint",
  "category": "Automation Services",
  "description_preview": "Structured automation plan...",
  "base_price_gbp": 79,
  "currency": "GBP",
  "requires_review": true,
  "document_types": ["AI_WORKFLOW_BLUEPRINT_REPORT"],
  "is_active": true,
  "seo_slug": "workflow-automation-blueprint"
}
```

Current seed **service** shape:

- `service_name` (task: `name`)
- `category` (task: display string like `"Automation Services"`; we use enum-like `ai_automation`, `market_research`, etc.)
- `description` (task: `description_preview`)
- No `base_price_gbp` / `currency` (we have `base_price` in pence in the built doc)
- No `requires_review` (we have `review_required` in catalogue)
- No `document_types[]` (we have `documents_generated` with `DocumentTemplate` objects)
- No `seo_slug` (we have `learn_more_slug` in catalogue)

So the **seed JSON schema** in the repo does not match the **task’s schema**. The **public API** already exposes a task-like shape: `services_public.py` maps catalogue entries to `name`, `description_preview`, `requires_review`, `document_types`, `seo_slug` (see `_service_to_public`). So the **runtime** is aligned with the task’s *output*; the **seed file** is the part that differs.

---

## 4. Gaps and options

| Area | Status | Notes |
|------|--------|--------|
| Orchestrator plan + canonical order | **Done** | Pack: `filter_and_order_docs` + `CANONICAL_ORDER` + `create_document_items`. Single-doc: one doc per order. |
| Per-document micro-prompts | **Done** | Pack: one prompt per doc via `get_prompt_for_service(service_code, doc_type)` and one LLM call per item. |
| Seed JSON schema (task shape) | **Mismatch** | Task uses `name`, `description_preview`, `base_price_gbp`, `currency`, `requires_review`, `document_types[]`, `seo_slug`. Current seed uses `service_name`, `description`, `workflow_name`, `display_order`, and does not set pricing/seo_slug/document_types in seed. |

**Conflict / choice**

- If you **replace** the current `seed_data_v1.json` with the **exact** task structure, the existing seed script will break unless it is updated to read both shapes or only the new shape.
- **Safest:** Keep existing seed structure working; **extend** the seed script so it **also** accepts the task’s field names and maps them into the existing `service_catalogue_v2` and prompt model. That way:
  - Existing seed files and flows keep working.
  - A seed file in the task’s format can be used by mapping: `name` → `service_name`, `description_preview` → `description`, `base_price_gbp` → `base_price` (e.g. GBP → pence), `requires_review` → `review_required`, `document_types` → `documents_generated` (e.g. list of `{ template_code: doc_type, template_name: doc_type }` for single-doc; for packs, task has `["DOC_PACK_ORCHESTRATOR"]` and real doc list is in DOCUMENT_REGISTRY), `seo_slug` → `learn_more_slug`, `category` string → existing `ServiceCategory` enum (e.g. "Automation Services" → `ai_automation`, "Market Research" → `market_research`, "Compliance Services" → `compliance`, "Document Packs" → `document_pack`).

---

## 5. Mapping task category string → catalogue enum

For seed script compatibility with task’s `category` string:

- `"Automation Services"` → `ai_automation`
- `"Market Research"` → `market_research`
- `"Compliance Services"` → `compliance`
- `"Document Packs"` → `document_pack`

(Exact strings may need adjusting if the task uses different labels.)

---

## 6. Summary

- **Orchestrator plan + canonical order:** Implemented (pack: explicit plan and canonical order; single-doc: one doc).
- **Per-document micro-prompts:** Implemented for packs (one prompt per doc, independent generation); single-doc uses one prompt per order.
- **Seed data:** Current `seed_data_v1.json` and seed script use a different schema than the task’s. No duplication or conflict in **orchestration logic**; the only gap is **seed file shape and script mapping**. Recommended approach: extend the seed script to accept the task’s service shape and map it into the existing catalogue and prompt model, without removing support for the current shape, so both existing and task-style seed files work and nothing is implemented blindly.
