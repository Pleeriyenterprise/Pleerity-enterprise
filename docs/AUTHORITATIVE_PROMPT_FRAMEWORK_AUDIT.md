# Authoritative Prompt Framework – Codebase Audit

**Scope:** Compare the task’s “AUTHORITATIVE PROMPT FRAMEWORK” (sections 1–11) to the current implementation. Identify what is implemented, what is missing, and any conflicts. Propose the safest way to align without breaking existing behaviour.

**Do not implement blindly.** This is an audit only; changes should follow the plan below.

---

## Implementation status (recommendation applied)

The following has been implemented in the codebase:

- **`AUTHORITATIVE_FRAMEWORK_V2`** in `backend/services/gpt_prompt_registry.py`: Single constant containing core principle (deterministic document generator), role, hard guardrails, hallucination prevention (including required pattern sentence), prompt leakage prevention, global tone & language (hard lock, allowed/disallowed examples), cover page & pack summary rules, section coherence, regeneration one-liner, output structure, and tone & style.
- **Legacy prompts:** `AUTHORITATIVE_FRAMEWORK = AUTHORITATIVE_FRAMEWORK_V2` so all registry prompts prepend the full framework.
- **Managed prompts:** In `backend/services/prompt_manager_bridge.py`, `_managed_to_prompt_definition` prepends `AUTHORITATIVE_FRAMEWORK_V2` to the stored `system_prompt` so Prompt Manager prompts get the same guardrails.
- **Service-specific addenda** in each legacy prompt system_prompt: AI services (implementation-oriented, no tool hype), MR_BASIC (narrative only, no tables/charts), MR_ADV (tables permitted, charts only if deterministic), Compliance and Document Packs (explanatory not advisory, no legal conclusions).

Optional Phase 2 (post-generation leakage/tone checks) is not implemented and remains backlog.

---

## 1. Task framework (summary)

| # | Area | Key requirements |
|---|------|-------------------|
| 1 | Core principle | GPT = deterministic document generator; strict input boundaries, fixed structure, controlled tone, explicit failure conditions. Not a creative writer or decision-maker. |
| 2 | Prompt architecture | Multi-stage, **section-based** prompts. Each section generated independently with full document context, section position, target audience, output constraints. No single “generate everything” prompt. Sections must assume continuity and not restate earlier content. |
| 3 | Global tone & language | Professional, neutral, advisory. No marketing, hype, first-person (“we”, “I”), casual language, AI self-reference. Allowed: “Based on the information provided…”, “This analysis indicates…”. Disallowed: “This will guarantee…”, “You should definitely…”, “As an AI…”. Any violation = hard fail. |
| 4 | Hallucination prevention | Never invent facts, guess missing data, pull external statistics, or cite sources not provided. If missing → state limitation; if assumptions → label them; if low confidence → express uncertainty. Example: “This section is based solely on the information provided. Where data is incomplete, conclusions are indicative rather than definitive.” |
| 5 | Prompt leakage prevention | Outputs must never reference prompts, system instructions, or how the document was generated. Leakage = automatic rejection. |
| 6 | Cover page & pack summary | Cover: structured placeholders only; no branding language or disclaimers from GPT. Pack summary: what’s included, how to use, scope limitations; no legal advice/promises/marketing; clear disclaimers. |
| 7 | Section coherence | Each section prompt must include “This section follows X”, “Do not repeat previous content”, “Maintain continuity with earlier sections”. Document is partially written, not blank slate. |
| 8 | Regeneration rules | Only from Internal Review; each regeneration = new immutable version; previous preserved; final status locks further regeneration. GPT must never edit final docs or self-correct without explicit trigger. |
| 9 | Service-specific | MR_BASIC: narrative only, no tables/charts. MR_ADV: tables allowed; charts only if deterministic; no speculative data. AI services: implementation-oriented, no vague recommendations. Compliance/packs: explanatory not advisory, no legal conclusions. |
| 10 | Acceptance criteria | Structure matches templates; tone rules; no hallucinations; no leakage; coherent flow; MR_BASIC no tables/charts; MR_ADV tables correct; cover/summary where required; regeneration = clean new version; enterprise documentation standards. |
| 11 | Guarantees | Consistency, predictable quality, safe regeneration, auditability, no “AI smell”. |

---

## 2. What is implemented

### 2.1 Core principle (partial)

- **Location:** `backend/services/gpt_prompt_registry.py` – `AUTHORITATIVE_FRAMEWORK` (lines 50–75).
- **Present:** “Never fabricate or estimate numerical figures”, “Never provide legal or financial advice”, “Never recommend specific contractors…”, “Never speculate on outcomes”, “Never generate content outside scope”, “If input data missing or ambiguous, flag explicitly”, “Cite UK-specific compliance where applicable”.
- **Missing in text:** Explicit “GPT is a deterministic document generator, not a creative writer or decision-maker” and “explicit failure conditions = invalid output”.

### 2.2 Prompt architecture – section-based (not implemented as execution model)

- **Current behaviour:** One **single** LLM call per document. System prompt lists “DOCUMENT SECTIONS” (e.g. 1. Executive Summary, 2. Current State…) but the model is asked to “Generate the complete blueprint/report” in one go.
- **Task requirement:** “All documents are generated using **multi-stage, section-based** prompts”; “Each section is generated **independently**”; “❌ No single ‘generate everything’ prompt”.
- **Gap:** Execution is single-shot per document. There is no loop that generates section 1, then section 2 with “this section follows section 1”, etc. Template renderer has section headings and content placement but does **not** drive separate LLM calls per section.

### 2.3 Global tone & language (partial)

- **Present:** “Professional, clear, and concise”; “Avoid jargon unless necessary”; “Avoid filler phrases”.
- **Missing:** Hard lock list: no first-person, no “we”/“I”, no marketing/hype, no “As an AI”; explicit allowed/disallowed phrase list; “Any violation = hard fail”.

### 2.4 Hallucination prevention (partial)

- **Present:** “Never fabricate…”, “If input data missing or ambiguous, flag explicitly”, “data_gaps_flagged” in schemas.
- **Missing:** Explicit “label assumptions”, “express uncertainty”, and the required pattern sentence (“This section is based solely on the information provided…”).

### 2.5 Prompt leakage prevention (missing)

- **Present:** None in prompt text.
- **Missing:** Instruction that outputs must never reference prompts, system instructions, or generation process; “Any leakage = automatic rejection”. No post-generation check for leakage.

### 2.6 Cover page & pack summary (partial)

- **Present:** Template renderer has structure for sections/headings; pack orchestrator has document list and ordering.
- **Missing:** Explicit rule that cover is “structured placeholders only”, “GPT must NOT create branding language”; mandatory pack summary with “what’s included, how to use, scope limitations” and static + variable disclaimers in prompt/text.

### 2.7 Section coherence (missing)

- **Present:** Sections listed in system prompt; single call produces structured JSON with section keys.
- **Missing:** Per-section instructions “This section follows X”, “Do not repeat previous content”, “Maintain continuity with earlier sections”. Not applicable in current single-call model unless we move to multi-stage.

### 2.8 Regeneration rules (implemented in workflow, not in prompt)

- **Location:** `admin_orders.py` (request_regeneration from INTERNAL_REVIEW), `document_pack_orchestrator.py` (regenerate_document, versioning), order status flow.
- **Present:** Regeneration only from Internal Review; new version created; previous versions preserved; structured regen reason/notes; version locking after approval.
- **Missing in prompts:** No instruction that “GPT must never edit final documents or self-correct without explicit trigger” (workflow already enforces this; adding to prompt is reinforcement only).

### 2.9 Service-specific rules (partial)

- **MR_BASIC:** Schema and prompt say “directional insights”, “Focus on directional insights rather than specific numerical data”, “Do NOT fabricate specific market size numbers”. **Missing:** Explicit “No tables; no charts; narrative analysis only.”
- **MR_ADV:** “Provide ranges rather than fabricated specific numbers”, “SWOT… balanced”, “pricing… tier-based”. **Missing:** Explicit “Tables allowed and expected”; “Charts only if technically deterministic”; “No speculative data”.
- **AI services:** “implementation-oriented” and “no vague recommendations” are partially reflected in section lists and schema. **Missing:** Explicit “Every suggestion must map to a real workflow step”; “No tool hype”.
- **Compliance/packs:** “Do NOT confirm compliance”, “assessment only”, “professional verification”. **Missing:** Explicit “Explanatory, not advisory”; “No legal conclusions”; “No guarantees of compliance”.

### 2.10 Acceptance criteria & guarantees (missing)

- No checklist in code that validates: structure, tone, no hallucinations, no leakage, MR_BASIC no tables/charts, MR_ADV tables, cover/summary, regeneration behaviour. No automated “hard fail” on tone/leakage.

### 2.11 Prompt Manager vs legacy registry

- **Prompt Manager** (DB): Stored prompts use short system text (e.g. “You are a precise document assistant. Produce structured output as valid JSON only.”). They do **not** currently include the full AUTHORITATIVE_FRAMEWORK.
- **Legacy registry:** Each prompt uses `AUTHORITATIVE_FRAMEWORK + """..."""` so the framework is always prepended when legacy is used.
- **Bridge:** When returning a managed prompt, `_managed_to_prompt_definition` uses `managed_prompt["system_prompt"]` as-is; it does **not** prepend the framework. So **managed prompts today do not get the full guardrails** unless the framework is stored in the DB or the bridge prepends it.

---

## 3. Conflicts and choices

| Topic | Conflict | Recommendation |
|-------|----------|----------------|
| Section-based execution | Task requires per-section generation; current design is one call per document. | **Phase 1:** Do not change execution model. Add the full framework text (tone, hallucination, leakage, coherence wording) to system prompts so that single-call output is constrained. **Phase 2 (optional):** Introduce true multi-stage section generation later (separate design/backlog). |
| Managed vs legacy prompts | Legacy gets AUTHORITATIVE_FRAMEWORK; managed prompts do not. | **Safest:** Bridge prepends a single “AUTHORITATIVE_FRAMEWORK” constant (updated to match task) when building `PromptDefinition` from a managed prompt, so all generation paths get the same guardrails. Prompt Manager continues to store service-specific addenda only. |
| MR_BASIC tables/charts | Task: “No tables; no charts.” Schema/JSON can still contain structured objects (e.g. competitor_overview array). | Interpret as: no **markdown/rendered** tables or charts in MR_BASIC output; narrative only. Add explicit line in MR_BASIC system prompt: “Do not produce tables or charts; narrative analysis only.” Renderer already can render narrative from JSON. |
| Hard fail on tone/leakage | Task: “Any violation = hard fail” / “automatic rejection”. | **Phase 1:** Add to framework text that such outputs are invalid. **Phase 2:** Optional post-processing (keyword/heuristic check for “we”, “I”, “As an AI”, “prompt”, “system instruction”) and mark run as failed or flag for review; do not block delivery without product agreement. |

---

## 4. Recommended approach (safest)

1. **Single source of framework text**
   - Define one constant (e.g. `AUTHORITATIVE_FRAMEWORK_V2`) in `gpt_prompt_registry.py` (or a dedicated `authoritative_framework.py`) that reflects sections 1, 3, 4, 5, 7 (as instructions), 8 (reinforcement), and 9 (service-specific bullets). Keep it additive to existing guardrails where they already match.

2. **Use framework for all paths**
   - **Legacy:** Keep prepending this framework to legacy prompts (replace or extend current `AUTHORITATIVE_FRAMEWORK`).
   - **Managed:** In `prompt_manager_bridge._managed_to_prompt_definition`, set  
     `system_prompt = AUTHORITATIVE_FRAMEWORK_V2 + "\n\n" + (managed_prompt["system_prompt"] or "")`  
     so every managed prompt gets the same base rules. No DB migration of existing prompts required.

3. **Service-specific addenda**
   - In registry (and/or in Prompt Manager per service/doc_type), add:
     - **MR_BASIC:** “Output must be narrative only. Do not produce tables or charts. No comparative matrices.”
     - **MR_ADV:** “Structured analytical tables are permitted. Charts only if technically deterministic; otherwise use tables and narrative. No speculative or fabricated data.”
     - **AI services:** “Output must be implementation-oriented. Every suggestion must map to a real workflow step. No vague recommendations or tool hype.”
     - **Compliance/packs:** “Explanatory only, not advisory. No legal conclusions or guarantees of compliance.”

4. **Cover page and pack summary**
   - Add to framework (or pack-specific prompt): cover page = structured placeholders only (client name, service name, order ref, date); no branding language from GPT. Pack summary: one structured summary stating what’s included, how to use, scope limitations; no legal advice/promises; include disclaimers (static + variables).

5. **Regeneration**
   - No change to workflow. Optionally add one line to framework: “Do not edit or regenerate content unless explicitly requested by the user; you are generating a single response.”

6. **Validation (optional, Phase 2)**
   - Lightweight post-generation check for leakage (e.g. “prompt”, “system instruction”, “As an AI”) and first-person (“ we ”, “ I ”) in concatenated output; log and optionally set a “quality_flag” for review. Do not auto-reject without product/legal agreement.

7. **Do not do (without explicit decision)**
   - Change to multi-stage section-by-section generation in this change set.
   - Migrate or overwrite existing Prompt Manager content; keep bridge prepend only.

---

## 5. Summary table

| Framework section | Implemented | Action |
|-------------------|------------|--------|
| 1. Core principle | Partial | Add deterministic-generator wording and explicit failure conditions to framework text. |
| 2. Section-based execution | No (single-shot) | Document as gap; optionally Phase 2. Do not change execution in Phase 1. |
| 3. Global tone | Partial | Add hard lock list (no we/I, no marketing, no “As an AI”), allowed/disallowed examples. |
| 4. Hallucination | Partial | Add “label assumptions”, “express uncertainty”, required pattern sentence. |
| 5. Leakage | No | Add leakage rule to framework; optional Phase 2 post-check. |
| 6. Cover & pack summary | Partial | Add explicit cover/summary rules and disclaimer wording. |
| 7. Section coherence | No | Add to framework for future section-based use; single-call can still “assume continuity”. |
| 8. Regeneration | Yes (workflow) | Optional one-line reinforcement in framework. |
| 9. Service-specific | Partial | Add MR_BASIC/MR_ADV/AI/Compliance bullets to framework or service addenda. |
| 10. Acceptance criteria | No | Document; optional Phase 2 automated checks. |
| 11. Guarantees | Partial | Reflected by above; no code change. |
| Managed prompt framework | No | Bridge prepends framework to managed prompts. |

---

## 6. Files to touch (when implementing)

- **Framework constant:** `backend/services/gpt_prompt_registry.py` (new or updated `AUTHORITATIVE_FRAMEWORK` / `AUTHORITATIVE_FRAMEWORK_V2`).
- **Bridge:** `backend/services/prompt_manager_bridge.py` – prepend framework in `_managed_to_prompt_definition`.
- **Optional:** New `backend/services/authoritative_framework.py` if the block becomes large.
- **Seed / Prompt Manager:** Optionally add service-specific snippets to seed prompts or admin-editable fields; not required if addenda are in code per service_code/doc_type.

No changes to orchestrator execution flow, regeneration API, or document storage schema are required for Phase 1.
