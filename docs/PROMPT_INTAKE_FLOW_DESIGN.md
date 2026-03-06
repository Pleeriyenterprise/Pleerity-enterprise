# Prompt + Intake Flow for Personalised Document Generation (Design)

**Scope:** How to ensure prompts receive intake data so generation is personalised and coherent; correct flow; prefill vs other options; per-service prompt selection; whether to store prompts in the database. **Do not implement yet.**

---

## 1. Current flow (already correct — keep it)

High-level sequence today:

1. **Order + intake** – Order is paid; backend loads order and `intake_data` (from order or intake_submissions).
2. **Prompt selection** – Resolve `(service_code, doc_type)`. For single-doc services, `doc_type = service_code`. Look up prompt: **Prompt Manager first** (ACTIVE prompt in `prompt_templates`), then **legacy** `gpt_prompt_registry`.
3. **Intake snapshot (before any LLM call)** – `create_intake_snapshot(intake_data)` returns an immutable copy and a hash. Order status set to INTAKE_LOCKED. This is the **source of truth** for “what the client submitted.”
4. **Build user prompt** – Two paths:
   - **Managed prompt:** Template must contain `{{INPUT_DATA_JSON}}`. `build_user_prompt_with_json(template, intake_snapshot)` replaces it with `json.dumps(intake_snapshot, indent=2)`.
   - **Legacy prompt:** Template uses named placeholders (`{business_description}`, `{current_process_overview}`, etc.). `_build_user_prompt(prompt_def, intake_snapshot)` does `template.format(**data)` (with missing fields as `""` or `"Not provided"`).
5. **LLM call** – `system_prompt` (framework + service context) + `user_prompt` (with intake either as JSON or as prefilled text) → one generation per document.
6. **Parse + validate + render** – Response parsed as JSON, validated against schema, then DOCX/PDF rendered and stored.

So: **intake is fixed in a snapshot before any prompt is built or sent to the LLM.** The only design choice is **how** the snapshot is put into the prompt: one JSON blob vs named prefill.

---

## 2. Should intake be “prefilled” before sending to the LLM?

**Yes — and you already do it in one of two ways.**

- **Legacy (prefill):** The user prompt template has placeholders like `{business_description}`, `{current_process_overview}`. The orchestrator **prefills** them from `intake_snapshot` before calling the LLM. The model sees natural text (e.g. “Business Description: Acme Ltd …”), so generation is clearly grounded in that data.
- **Managed (single blob):** The user prompt has one placeholder `{{INPUT_DATA_JSON}}`, replaced by the full intake as JSON. The model is instructed to use that JSON. So the intake is still “in the prompt” before the LLM runs, but as a structured blob rather than inline narrative.

So:

- **“Prefill” in the narrow sense** = named placeholders filled from intake before the LLM runs. That’s the **safest for personalised, coherent** output: the model sees explicit “Business Description: …”, “Current Process Overview: …”, etc., and is less likely to ignore or misparse fields.
- **“Prefill” in the broad sense** = intake is fixed (snapshot) and then injected into the prompt in some form before the LLM runs. You already do that; the only question is format (named prefill vs JSON).

Recommendation: **prefer named prefill** for reports like AI Workflow Blueprint, Business Process Mapping, Market Research, Compliance, etc., so the prompt the LLM sees is clearly personalised and sectioned. Keep the existing **intake snapshot → then build prompt → then LLM** order; no “send to LLM first and fill later.”

---

## 3. Safest approach (without changing architecture)

1. **Keep the flow** – Snapshot intake once, then build the prompt, then call the LLM. No second “fill in” step after the LLM.
2. **For each service prompt, choose one injection style:**
   - **Option A — Named prefill:** User template contains placeholders like `{business_description}`, `{current_process_overview}`, `{goals_objectives}`, etc. At runtime, replace them from `intake_snapshot` (with a safe default for missing keys, e.g. `"Not provided"` or `""`). The string sent to the LLM then has the actual values in place. Best for “reads like we wrote it for this client.”
   - **Option B — Single JSON:** User template contains `{{INPUT_DATA_JSON}}` and instructions that “the following JSON is the intake form; use all relevant fields.” Replace with `json.dumps(intake_snapshot, indent=2)`. Simpler and flexible for any intake shape; slightly more room for the model to underuse or misread a field.
3. **Support both in code** – When building the user prompt for a **managed** prompt:
   - If the template contains `{{INPUT_DATA_JSON}}` → keep current behaviour (replace with JSON).
   - Else if the template contains `{field_name}`-style placeholders → do named prefill from `intake_snapshot` (same logic as legacy `_build_user_prompt`), so stored prompts can use either style without changing the overall flow.
4. **Intake keys = placeholder keys** – For named prefill to work, the keys in the intake form (and thus in `intake_snapshot`) must match the placeholders in the template (e.g. `business_description`, `current_process_overview`). Your intake schema / unified wizard should define these field IDs once and use them in both the form and the prompt templates.

That way: intake is always locked first; the prompt the LLM sees always contains the intake in some form; and you can still store prompts in the DB and choose per prompt whether to use JSON or named prefill.

---

## 4. Making sure each service uses its own prompt

This is **already** how it works:

- **Single-doc services (e.g. AI_WF_BLUEPRINT, MR_BASIC, FULL_COMPLIANCE_AUDIT):** Prompt is selected by `(service_code, doc_type)` with `doc_type = service_code`. So AI_WF_BLUEPRINT → prompt for AI_WF_BLUEPRINT; MR_BASIC → prompt for MR_BASIC; etc.
- **Document packs:** Each pack doc type (e.g. RENT_ARREARS_LETTER) is resolved by pack service code + doc_type; each has its own prompt in Prompt Manager or registry.

To keep that clean:

- **Canonical rule:** One prompt per `(service_code, doc_type)`. For “AI Workflow Blueprint”, that’s `service_code = AI_WF_BLUEPRINT` and a single `doc_type` (e.g. `AI_WORKFLOW_BLUEPRINT_REPORT` or again `AI_WF_BLUEPRINT`).
- **No sharing:** AI Workflow Blueprint prompt is not used for Business Process Mapping or Market Research; each service has its own prompt record (in DB or registry) keyed by that service’s `(service_code, doc_type)`.

So: **each service uses the prompt meant for it** as long as you store (or register) one prompt per service/doc_type and resolve by the same `(service_code, doc_type)` you use for orders and intake.

---

## 5. Should we save the prompt in the database?

**Yes.** Store these prompts in the **Prompt Manager** (`prompt_templates`):

- **Edits without deploy** – Change wording, sections, or constraints in the admin UI or via API; no code change.
- **Versioning and audit** – Keep versions, activation history, and who changed what.
- **Testing** – Use the existing “test prompt” endpoint with sample intake before activating.
- **One place for all services** – AI Workflow Blueprint, Business Process Mapping, AI Tool Recommendation, MR Basic/Advanced, Full Compliance Audit, HMO Audit, Move-in/out Checklist, etc., can all live in `prompt_templates` with the right `service_code` and `doc_type`.

Concretely for “AI Workflow Blueprint — Master Prompt”:

- **service_code:** `AI_WF_BLUEPRINT`
- **doc_type:** e.g. `AI_WORKFLOW_BLUEPRINT_REPORT` (or same as service_code if you prefer)
- **system_prompt:** Your full SYSTEM ROLE, INPUT DATA instructions, OUTPUT STRUCTURE (with section names like {{GPT_EXECUTIVE_SUMMARY}}, {{GPT_WORKFLOW_OVERVIEW}}, etc.), HARD CONSTRAINTS, QUALITY BAR, FINAL INSTRUCTION. Optionally prepend the global AUTHORITATIVE_FRAMEWORK (or rely on the bridge to prepend it).
- **user_prompt_template:** Either:
  - **Named prefill:** A block that lists each intake field and a placeholder, e.g. “Business Description: {business_description}\nCurrent Process Overview: {current_process_overview}\n…” so the bridge/orchestrator can prefill from `intake_snapshot`, or
  - **JSON:** “Use the following intake form data when generating the document.\n\n{{INPUT_DATA_JSON}}”
- **output_schema:** Define keys that match what the writer/template expects. For your prompt, that would include at least: `GPT_EXECUTIVE_SUMMARY`, `GPT_WORKFLOW_OVERVIEW`, `GPT_PROCESS_FLOW`, `GPT_RECOMMENDATIONS` (and any others you use in the template). The LLM is then instructed (e.g. in system prompt or schema description) to return JSON with those keys so the downstream template can plug them into {{GPT_EXECUTIVE_SUMMARY}}, etc.

Storing in the DB also makes it easy to add the other services you mentioned (Business Process Mapping, AI Tool Recommendation, MR Basic/Advanced, Full Compliance, HMO, Move-in/out Checklist) as separate rows with their own `service_code` / `doc_type` and their own system/user prompts and schemas.

---

## 6. Mapping your “AI Workflow Blueprint” prompt into the flow

- **System role and rules** – Stored in `system_prompt` (or in a shared “framework” that gets prepended). No need to duplicate the global AUTHORITATIVE_FRAMEWORK if the bridge already prepends it; just store the service-specific part.
- **“INPUT DATA (FROM INTAKE FORM)”** – Implement by either:
  - **Named prefill:** In `user_prompt_template`, include placeholders for every intake field you list (Business Description, Current Process Overview, Goals & Objectives, Priority Goal, Team Size, Processes to Focus On, Current Tools Used, Main Challenges, Additional Notes). At runtime, replace them from `intake_snapshot` so the text the LLM sees is “Business Description: …”, “Current Process Overview: …”, etc.
  - **JSON:** Keep a single “Use the following intake data:\n\n{{INPUT_DATA_JSON}}” and pass the snapshot as JSON; instruct in system prompt to “use all relevant intake fields provided and synthesize holistically; do not list or echo form fields verbatim.”
- **“OUTPUT STRUCTURE (MUST MATCH WRITER TEMPLATE)”** – The sections {{GPT_EXECUTIVE_SUMMARY}}, {{GPT_WORKFLOW_OVERVIEW}}, {{GPT_PROCESS_FLOW}}, {{GPT_RECOMMENDATIONS}} are **output** keys. The LLM should return JSON like `{ "GPT_EXECUTIVE_SUMMARY": "...", "GPT_WORKFLOW_OVERVIEW": "...", ... }`. The `output_schema` for this prompt should require those keys so validation and the template renderer/writer can use them.

So: **intake is prefilled (or injected as JSON) before the LLM runs; the same snapshot is used for the whole run; each service uses its own prompt from the DB; and the prompt is stored in the database with a clear split between system prompt, user template (with placeholders or {{INPUT_DATA_JSON}}), and output schema.** Once this pattern is agreed, the same approach applies to the other document types you plan to add.

---

## 7. Summary (no implementation)

| Question | Answer |
|----------|--------|
| How to ensure the prompt has the inputted data? | Intake is locked in a snapshot, then injected into the user prompt (either as named prefill or as {{INPUT_DATA_JSON}}) **before** calling the LLM. |
| Correct flow? | Snapshot intake → select prompt by (service_code, doc_type) → build user prompt from snapshot → call LLM → parse/validate/render. Already in place. |
| Prefill before sending to LLM? | Yes. Prefill (or JSON injection) happens when building the user prompt, so the prompt string the LLM sees already contains the intake. Prefer **named prefill** for reports for best personalisation and coherence. |
| Safest approach? | Keep snapshot-first flow; support both named prefill and {{INPUT_DATA_JSON}} for managed prompts; align intake field IDs with placeholder names; store prompts in DB. |
| Each service uses its particular prompt? | Yes — resolve by (service_code, doc_type); one prompt per service/doc_type in DB or registry. |
| Save prompt in database? | Yes — use `prompt_templates` (Prompt Manager) for versioning, editing, testing, and to hold all services (AI Workflow Blueprint, Business Process Mapping, MR Basic/Advanced, Compliance, HMO, Move-in/out, etc.) in one place. |

No code changes have been made; this is design only.
