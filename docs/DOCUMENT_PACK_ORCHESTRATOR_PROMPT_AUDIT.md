# Document Pack Orchestrator Prompt – Codebase Audit

**Scope:** Compare the task's "DOCUMENT PACK ORCHESTRATOR PROMPT" (system role, input sources, hard access control, document generation logic, output structure, tone, legal disclaimer, strict prohibitions, success criteria) to the current implementation. Identify what is implemented, what is missing, and any conflicts. Propose the safest option without implementing blindly.

---

## Implementation status (recommendation applied)

- **Legal disclaimer footer:** Implemented in `backend/services/template_renderer.py`. Constant `PACK_LEGAL_DISCLAIMER_FOOTER` holds the exact required text. For pack documents, `_add_docx_footer` (with `is_pack_document=True`) and the PDF footer add the disclaimer; when pack docs are rendered from a server-side template, `_append_pack_legal_footer_docx` appends it after render. `render_pack_item` passes `is_pack_document=True` to `_render_docx` and `_render_pdf`.
- **Pack-document system prompt context:** Implemented in `backend/services/gpt_prompt_registry.py` (`DOCUMENT_PACK_ORCHESTRATOR_CONTEXT`, `PACK_SERVICE_CODES`) and `backend/services/prompt_manager_bridge.py`. For managed prompts whose `service_code` is in `PACK_SERVICE_CODES` (DOC_PACK_ESSENTIAL, DOC_PACK_PLUS, DOC_PACK_TENANCY, DOC_PACK_PRO), the bridge prepends `DOCUMENT_PACK_ORCHESTRATOR_CONTEXT` then `AUTHORITATIVE_FRAMEWORK_V2` to the stored system prompt so every pack document generation receives the same orchestrator role, input sources, access control, tone, prohibitions, and success criteria.

---

## 1. Task requirements (summary)

| Area | Key requirements |
|------|------------------|
| **System role** | Document Generation Orchestrator for Pleerity Enterprise Ltd; generate UK landlord document templates from user-selected documents and intake data only. Not a solicitor or legal advisor; no legal advice. Outputs = informational templates, administrative documents, general landlord-use documents only. |
| **Input sources** | (1) Service code: DOC_PACK_ESSENTIAL / DOC_PACK_PLUS / DOC_PACK_PRO; (2) Selected documents list; (3) Intake form fields (only visible/completed for selection); (4) Predefined GPT sub-variables only when mapped to a document: GPT_ARREARS_REASON_PARAGRAPH, GPT_DEPOSIT_EXPLANATION, GPT_NOTICE_REASON, GPT_CUSTOM_CLAUSE_SUMMARY, GPT_INVENTORY_SUMMARY, GPT_ACCESS_REASON_PARAGRAPH. |
| **Hard access control** | Pack hierarchy: ESSENTIAL → ESSENTIAL only; PLUS → PLUS + ESSENTIAL; PRO → PRO + PLUS + ESSENTIAL. No cross-pack leakage; never generate or reference higher-tier or unselected documents. Selection-driven: only generate explicitly selected documents; no defaults, no assumptions, no auto-inclusion. |
| **Document generation logic** | For each selected document: identify correct base template (task lists 15 template names); inject only GPT sub-variables mapped to that document; ignore unrelated intake fields. |
| **Output structure** | Canonical order: (1) Administrative/Informational, (2) Notices, (3) Agreements, (4) Records/Inventories, (5) Supporting packs. Each document self-contained; must not reference other generated documents. |
| **Tone & language** | Neutral, professional, UK landlord-appropriate; clear administrative wording; no legal advice phrasing. Avoid: "You are legally required to…", "This guarantees compliance…", "Under the law you must…". Use instead: "This document is commonly used to…", "This template is intended to support…", "Landlords often include…". |
| **Legal safety disclaimer** | **Required on all documents** – exact footer: "This document is provided as a general template for administrative and informational purposes only. It does not constitute legal advice. Users may wish to seek independent legal guidance where appropriate." No variations, no embellishment. |
| **Strict prohibitions** | Must NOT: invent clauses; assume jurisdiction beyond UK; reference legislation by section number; interpret council decisions; suggest enforcement actions; provide eviction guidance; recommend legal strategies. |
| **Success criteria** | Every generated document was explicitly selected; no unselected document; no higher-tier leak; neutral, non-advisory language; professional, enterprise-grade; no regulatory risk to Pleerity. |

---

## 2. What is implemented

### 2.1 Pack hierarchy and access control

- **Location:** `backend/services/document_pack_orchestrator.py`
- **Implemented:** `PackTier` (ESSENTIAL, PLUS, PRO); `SERVICE_CODE_TO_PACK_TIER` maps DOC_PACK_ESSENTIAL/PLUS/PRO (and DOC_PACK_TENANCY → PLUS); `get_allowed_docs(pack_tier)` returns `CANONICAL_ORDER[pack_tier]` so PRO includes PLUS + ESSENTIAL, PLUS includes ESSENTIAL. `filter_and_order_docs(service_code, selected_docs)` restricts to `doc_key in allowed_docs and doc_key in DOCUMENT_REGISTRY` and to `selected_docs`. So:
  - Pack hierarchy and inheritance are enforced.
  - No cross-pack leakage: only docs in the user’s tier and in `selected_docs` are generated.
  - Selection-driven: only explicitly selected docs; no default or auto-inclusion of unselected docs.

### 2.2 Canonical order

- **Location:** `document_pack_orchestrator.py` – `CANONICAL_ORDER` per tier.
- **Implemented:** Fixed order per tier (Essential 5 → Plus 5 → Pro 4). `filter_and_order_docs` sorts by `canonical_index`. Order is server-side and stable.
- **Difference from task:** Task defines order by **category**: (1) Administrative/Informational, (2) Notices, (3) Agreements, (4) Records/Inventories, (5) Supporting packs. Current order is by **tier** then a fixed list (e.g. arrears, deposit refund, reference, receipt, GDPR then AST, guarantor, renewal, rent increase, notice to quit then inventory, deposit info, access notice, additional notice). So ordering is enforced but the **semantic grouping** (Admin → Notices → Agreements → Records → Packs) is not the same as the task’s.

### 2.3 Document registry and base templates

- **Location:** `document_pack_orchestrator.py` – `DOCUMENT_REGISTRY` (doc_key → DocumentDefinition with doc_type, pack_tier, output_keys, display_name).
- **Implemented:** 14 doc_keys covering Essential (5), Plus (5), Pro (4). Per-document generation uses `get_prompt_for_service(service_code, doc_type)` and generates one document per item; each output is self-contained.
- **Naming vs task:** Task lists e.g. `doc_arrears_letter_template`, `doc_inventory_condition_template`, `doc_deposit_info_pack_template`, `doc_additional_notice_template`. Codebase uses `doc_rent_arrears_letter_template`, `doc_inventory_condition_report`, `doc_deposit_information_pack`, `doc_additional_landlord_notice`. Task also lists `doc_tenancy_agreement_prt_template`; `service_definitions_v2` has it, but **DOCUMENT_REGISTRY does not** (Plus tier has AST, guarantor, renewal, rent increase, notice to quit only). So PRT is present in service definitions but not in the pack orchestrator registry.

### 2.4 GPT sub-variables

- **Location:** `backend/services/service_definitions_v2.py` – `gpt_sections` per document template (e.g. GPT_ARREARS_REASON_PARAGRAPH, GPT_DEPOSIT_EXPLANATION, GPT_NOTICE_REASON, GPT_CUSTOM_CLAUSE_SUMMARY, GPT_INVENTORY_SUMMARY, GPT_ACCESS_REASON_PARAGRAPH).
- **Implemented:** Mapping of which GPT sub-variables apply to which document exists in service definitions. Document pack orchestrator uses `output_keys` on `DocumentDefinition` (e.g. GPT_RENT_ARREARS_LETTER) for LLM output validation; template rendering and docx assembly use structured output and intake. Exact injection of task-named placeholders into server-side templates (docxtpl) depends on `_build_template_context` and template files; variable names in templates may differ from task list but the concept (per-doc mapped variables) is present.

### 2.5 Tone and non-legal framing

- **Location:** `backend/services/gpt_prompt_registry.py` – `AUTHORITATIVE_FRAMEWORK` (and DOC_PACK_ORCHESTRATOR prompt) and `prompt_manager_bridge` prepending framework for managed prompts.
- **Implemented:** Global rules include “Never provide legal or financial advice”, “Explanatory only, not advisory”, “No legal conclusions or guarantees of compliance”, “Controlled template language”. DOC_PACK_ORCHESTRATOR prompt adds “Explanatory only, not advisory” and “GPT sections enhance but don’t replace template content”. The task’s specific avoid/use-instead phrases (“You are legally required to…” vs “This document is commonly used to…”) are **not** explicitly in the prompt text.

### 2.6 Where the “orchestrator” prompt is used

- **Current architecture:** Generation is **per-document**: for each selected doc, `document_pack_orchestrator.generate_document_item` calls `prompt_manager_bridge.get_prompt_for_service(service_code, doc_type)` and runs one LLM call per document. There is **no** single LLM call that receives “pack type + selected list + intake” and returns all document contents. The `DOC_PACK_ORCHESTRATOR` prompt in `gpt_prompt_registry` is a legacy/orchestrator-style definition; the **actual** prompts used for pack docs are the per–doc_type prompts (from Prompt Manager or legacy) for e.g. RENT_ARREARS_LETTER, DEPOSIT_REFUND_EXPLANATION_LETTER, etc.
- **Implication:** The task’s “DOCUMENT PACK ORCHESTRATOR PROMPT” text is a **single** system prompt for one orchestrator. The codebase does not use one orchestrator LLM; it uses per-document prompts. So the task’s full wording is not currently applied as the system prompt for pack generation unless we add it as shared context for every pack doc generation.

---

## 3. What is missing or different

| Item | Status | Notes |
|------|--------|--------|
| **Required legal disclaimer footer** | **Missing** | Task requires **every** document to include the exact footer: “This document is provided as a general template for administrative and informational purposes only. It does not constitute legal advice. Users may wish to seek independent legal guidance where appropriate.” Current `_add_docx_footer` in `template_renderer.py` adds “Generated by Pleerity Enterprise Ltd \| date \| Document vX” and “CONFIDENTIAL - This document contains proprietary information.” The task’s disclaimer text is not present. |
| **Full orchestrator prompt as system context for pack docs** | **Missing** | The task’s SYSTEM ROLE, INPUT SOURCES, HARD ACCESS CONTROL, DOCUMENT GENERATION LOGIC, TONE & LANGUAGE CONSTRAINTS, STRICT PROHIBITIONS, and SUCCESS CRITERIA are not fully reflected in the prompt text used for each pack document. AUTHORITATIVE_FRAMEWORK and DOC_PACK_ORCHESTRATOR add high-level rules but not the full task wording (e.g. “You may ONLY use the following inputs”, “No Cross-Pack Leakage”, “Inject ONLY the GPT sub-variables mapped to that document”, avoid/use-instead phrases, prohibitions list). |
| **Canonical order by category** | **Different** | Task order: Administrative/Informational → Notices → Agreements → Records/Inventories → Supporting packs. Current order: by tier then fixed list. Both enforce a stable order; the **grouping logic** is not the same. |
| **PRT in pack registry** | **Gap** | Task lists `doc_tenancy_agreement_prt_template`. It exists in `service_definitions_v2` but not in `document_pack_orchestrator.DOCUMENT_REGISTRY`. So PRT is not part of the pack orchestrator’s document set in code. |
| **Explicit “ignore unrelated intake fields”** | **Partial** | Per-doc generation receives intake snapshot; prompts do not explicitly state “use only intake fields relevant to this document type; ignore unrelated fields”. Could be added to pack-doc system prompt. |

---

## 4. Conflicts and options

| Topic | Conflict | Recommendation |
|-------|----------|-----------------|
| **Single orchestrator prompt vs per-document prompts** | Task describes one orchestrator system prompt; codebase uses one LLM call per document with per–doc_type prompts. | **Keep per-document generation.** Add a **pack-document framework** constant (or extend AUTHORITATIVE_FRAMEWORK when the document is a pack doc) that contains the task’s SYSTEM ROLE, INPUT SOURCES, HARD ACCESS CONTROL (as “you are generating one selected document; only use inputs relevant to this document”), TONE & LANGUAGE (including avoid/use-instead), STRICT PROHIBITIONS, and SUCCESS CRITERIA. Prepend this when building the system prompt for any pack doc_type (e.g. in `prompt_manager_bridge` when service is DOC_PACK_* or when doc_type is in the pack set). Do not change to a single-call pack orchestrator without a separate design decision. |
| **Legal disclaimer footer** | Task requires exact disclaimer on every document; current footer is different. | **Add the task’s disclaimer** to pack document output. Safest: in `template_renderer`, when rendering a **pack** document (e.g. when `use_generic_content=True` and order/service is pack, or when a dedicated “is_pack_document” flag is set), append the task’s footer text to the DOCX (and PDF) footer in addition to or instead of the current “CONFIDENTIAL” line. Use the exact wording; no variations. |
| **Canonical order** | Task wants category-based order; code uses tier-based order. | **Option A:** Keep current order (no change). **Option B:** Define a category-based canonical order (Admin → Notices → Agreements → Records → Packs), map each doc_key to a category, and sort by category then within category. Option B aligns with task but may reorder documents; confirm with product before changing. |
| **PRT in registry** | PRT in service definitions but not in DOCUMENT_REGISTRY. | If PRT is intended to be a selectable pack document (e.g. for Scotland), add `doc_tenancy_agreement_prt_template` to `DOCUMENT_REGISTRY` under PLUS (or appropriate tier) and to `CANONICAL_ORDER`. If PRT is intentionally out of scope for the main pack flow, document that and leave registry as-is. |

---

## 5. Recommended approach (safest)

1. **Legal disclaimer footer (high priority)**  
   - In `template_renderer.py`, for document pack items (e.g. in `_add_docx_footer` when the document is a pack doc, or in a new `_add_pack_legal_footer` called from pack render path), add the required disclaimer paragraph exactly as specified. Ensure it appears on pack DOCX and, if the PDF is built from the same content path, on pack PDF. Do not alter the task’s wording.

2. **Pack-document system prompt (shared context)**  
   - Introduce a constant (e.g. `DOCUMENT_PACK_ORCHESTRATOR_CONTEXT` or a “pack document framework”) in `gpt_prompt_registry.py` (or a dedicated module) containing the task’s SYSTEM ROLE, INPUT SOURCES (restricted to “for this single document”), HARD ACCESS CONTROL (selection-driven, no cross-pack leakage), DOCUMENT GENERATION LOGIC (inject only mapped GPT sub-variables; ignore unrelated intake fields), TONE & LANGUAGE CONSTRAINTS (with avoid/use-instead), STRICT PROHIBITIONS, and SUCCESS CRITERIA.  
   - When building the prompt for a pack document (e.g. in `prompt_manager_bridge` when the prompt is for a doc_type that belongs to a document pack service), prepend this constant to the system prompt so every pack doc generation gets the same rules. Do not replace the existing per-document prompt; prepend so both the shared pack rules and the doc-specific prompt apply.

3. **Canonical order**  
   - Leave as-is (tier-based) unless product explicitly requests category-based order; then implement Option B above with a clear mapping from doc_key to category.

4. **PRT**  
   - Decide whether PRT is in scope for the pack orchestrator. If yes, add it to `DOCUMENT_REGISTRY` and `CANONICAL_ORDER`; if no, document the out-of-scope decision.

5. **No architectural change**  
   - Do not switch to a single LLM call that generates the entire pack; keep per-document generation and align behaviour via shared prompt context and footer.

---

## 6. Files to touch (when implementing)

| Change | File(s) |
|--------|---------|
| Add required legal disclaimer to pack documents | `backend/services/template_renderer.py` (footer for pack DOCX/PDF). |
| Add pack orchestrator context and prepend for pack docs | `backend/services/gpt_prompt_registry.py` (new constant) and `backend/services/prompt_manager_bridge.py` (prepend when doc is pack). |
| Optional: category-based canonical order | `backend/services/document_pack_orchestrator.py`. |
| Optional: add PRT to registry | `backend/services/document_pack_orchestrator.py`. |

---

## 7. Summary table

| Task requirement | Implemented | Action |
|------------------|------------|--------|
| Pack hierarchy (ESSENTIAL/PLUS/PRO) | Yes | None |
| No cross-pack leakage; selection-driven | Yes | None |
| Canonical order enforced | Yes (tier-based) | Optional: align to category-based order |
| Document registry / base templates | Yes (naming differs; PRT missing in registry) | Optional: add PRT if in scope |
| GPT sub-variables mapped per doc | Yes (service_definitions_v2) | Ensure template context uses them |
| System role / not legal advisor | Partial (in AUTHORITATIVE_FRAMEWORK) | Add full task wording as pack-doc context |
| Tone & avoid/use-instead phrases | Partial | Add to pack-doc context |
| **Required legal disclaimer footer** | **No** | **Add to pack DOCX/PDF footer** |
| Strict prohibitions list | Partial | Add to pack-doc context |
| Success criteria in prompt | No | Add to pack-doc context |
| Single orchestrator LLM | N/A (per-doc used) | Keep per-doc; add shared context |
