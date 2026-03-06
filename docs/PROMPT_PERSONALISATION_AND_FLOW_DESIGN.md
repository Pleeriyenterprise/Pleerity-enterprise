# Prompt Personalisation & Flow: Intake → LLM (Design Only)

**Scope:** How to ensure each service’s prompt (e.g. AI Workflow Blueprint) receives the **intake data** so generation is **personalised and coherent**. Correct flow, safest approach, per-service prompt selection, and whether to save prompts in the database. **Do not implement yet.**

---

## 0. Mapping the AI Workflow Blueprint master prompt (example)

You provided the **AI WORKFLOW BLUEPRINT — MASTER PROMPT** with:

- **System role:** Senior enterprise automation architect; concrete workflows, no speculation; label assumptions if info missing.
- **Input data (from intake):** Business Description, Current Process Overview, Goals & Objectives, Priority Goal, Team Size, Processes to Focus On, Current Tools Used, Main Challenges, Additional Notes. Synthesise holistically; do not echo form fields verbatim.
- **Output structure (must match writer template):** Four sections in order: `{{GPT_EXECUTIVE_SUMMARY}}`, `{{GPT_WORKFLOW_OVERVIEW}}`, `{{GPT_PROCESS_FLOW}}`, `{{GPT_RECOMMENDATIONS}}`.
- **Hard constraints / quality bar:** No prompt leakage, no hype, consistent tone, client-ready.

To make this **personalised and coherent**:

1. **Intake fields** for `AI_WF_BLUEPRINT` must match the prompt's INPUT DATA list (e.g. business_description, current_process_overview, goals_objectives, priority_goal, team_size, processes_to_focus, current_tools, main_challenges, additional_notes). Stored in `order.intake_snapshot.intake_payload`.
2. **Prefill before LLM:** Backend takes intake_data from the order (§2) and injects it once into the user prompt via `{{INPUT_DATA_JSON}}`. The LLM sees one JSON block and synthesises; no need to list each field again in the user template.
3. **Per-service prompt:** One prompt for `(service_code=AI_WF_BLUEPRINT, doc_type=AI_WORKFLOW_BLUEPRINT_REPORT)`. Orchestrator already selects by service_code + doc_type.
4. **Save in DB:** Store in Prompt Manager: **system_prompt** = full master text; **user_prompt_template** = instruction + `{{INPUT_DATA_JSON}}` + "Generate the full response now."; **output_schema** = keys matching writer template (GPT_EXECUTIVE_SUMMARY, GPT_WORKFLOW_OVERVIEW, GPT_PROCESS_FLOW, GPT_RECOMMENDATIONS).

The same pattern applies to the remaining prompts (Business Process Mapping, AI Tool Recommendation, MR Basic, MR Advanced, Full Compliance Audit, HMO Audit, Move-In/Out Checklist): one prompt per (service_code, doc_type), each with `{{INPUT_DATA_JSON}}`, intake prefilled from the order.

---

## 1. Current flow (as implemented)

1. **Order creation (after payment)**  
   Order is created with an **intake_snapshot** (immutable):
   - `client_identity` (name, email, phone, role, company)
   - `intake_payload` (service-specific fields: e.g. business_description, current_process_overview, goals_objectives, team_size, etc.)
   - `delivery_consent`

2. **Triggering generation**  
   An admin (or job) calls `POST /api/orchestration/generate` with:
   - `order_id`
   - **`intake_data`** (sent in the request body)

3. **Orchestrator pipeline**  
   - Validates order (payment, etc.).  
   - Resolves **prompt** by `service_code` (and `doc_type`): Prompt Manager first, then legacy registry.  
   - **Intake validation** (optional): `validate_intake_data(service_code, intake_data)` checks required fields.  
   - **Intake snapshot**: `create_intake_snapshot(intake_data)` → immutable copy + hash.  
   - **Build user prompt**:  
     - **Managed prompts:** `prompt_manager_bridge.build_user_prompt_with_json(template, intake_snapshot)`  
       - Replaces **`{{INPUT_DATA_JSON}}`** in the template with `json.dumps(intake_snapshot, indent=2, default=str)`.  
     - Legacy prompts use a different pattern (named placeholders).  
   - LLM is called with **system_prompt** (framework + service context) and **user_prompt** (containing the JSON).  
   - Output is validated, rendered (DOCX/PDF), versioned, and stored.

So **personalisation is already wired**: whatever is in `intake_data` (and then `intake_snapshot`) is injected as the single JSON block into the user prompt. The open points are **where `intake_data` comes from** when generation is triggered and **how it’s shaped** so the prompt “sees” the right fields.

---

## 2. Where intake_data should come from (recommended)

**Risk today:** If the **caller** (e.g. frontend or job) does **not** send `intake_data`, the pipeline would get an empty or wrong payload unless the API defaults it.

**Safest approach:**

- **Source of truth = order’s stored intake.**  
  When generation is triggered for an order, the backend should **derive** `intake_data` from the order if the request does not (or only partially) supply it.
- **Concrete behaviour:**
  - If the request includes `intake_data` (e.g. after “request more info” or an admin edit), use it (and optionally merge with or replace order’s snapshot for that run).
  - If the request does **not** include `intake_data`, **prefill from the order**:  
    `intake_data = order["intake_snapshot"]["intake_payload"]` (plus, if needed, `client_identity` / `order_ref` / `service_code` for context).
- So: **intake is “prefilled” from the order before sending to the LLM** — not by the client re-sending the form at trigger time, but by the backend loading the order and passing its intake into the pipeline.

This keeps a single source of truth (the order), avoids duplicate or stale form submissions, and ensures the LLM always gets the same data that was captured at checkout (unless explicitly overridden for that run).

---

## 3. Correct end-to-end flow (recommended)

1. **Intake capture**  
   User fills the intake form (unified wizard) for the chosen service. Fields are **service-specific** (e.g. AI Workflow Blueprint: business_description, current_process_overview, goals_objectives, priority_goal, team_size, processes_to_focus, current_tools, main_challenges, additional_notes).

2. **Checkout & order creation**  
   On payment success, an order is created with `intake_snapshot` = { client_identity, intake_payload, delivery_consent }. `intake_payload` must contain exactly the fields the service’s prompt expects (and the writer template uses).

3. **Trigger generation**  
   Admin (or automated job) calls “Generate” for that order.  
   - Backend loads the order.  
   - **Prefill:** `intake_data = order["intake_snapshot"]["intake_payload"]` (and optionally merge in client_identity / order_ref / service_code for context).  
   - If the API allows “updated intake” (e.g. after “request more info”), request body can override or merge with this.

4. **Pipeline**  
   - Select prompt by `service_code` (and `doc_type`).  
   - Create immutable snapshot: `intake_snapshot, hash = create_intake_snapshot(intake_data)`.  
   - Build user prompt: replace `{{INPUT_DATA_JSON}}` with `json.dumps(intake_snapshot, indent=2, default=str)`.  
   - Call LLM with system + user prompt.  
   - Validate, render, version, store.

5. **Result**  
   The model receives one coherent JSON blob of intake (and any added context) and produces the sections required by the prompt. No need to “prefill” inside the prompt text itself; the **whole** intake is the prefill, injected once into `{{INPUT_DATA_JSON}}`.

So: **intake is prefilled from the order before sending to the LLM**; the “prefill” is the backend populating `intake_data` from the order, not the client re-sending the form.

---

## 4. Ensuring each service uses the right prompt

**Current behaviour:**  
Prompt selection is already **per service** (and per doc type):

- `get_prompt_for_service(service_code, doc_type)`  
  - For single-document services, `doc_type = service_code` (canonical rule).  
  - So e.g. `AI_WF_BLUEPRINT` → prompt for `AI_WF_BLUEPRINT` (or `AI_WORKFLOW_BLUEPRINT_REPORT` if that’s the doc_type in the DB).  
- Priority: (1) Prompt Manager (ACTIVE), (2) legacy `gpt_prompt_registry`.

To **ensure each service uses the particular prompt meant for it:**

- Keep **one prompt per (service_code, doc_type)** in Prompt Manager (or registry).  
- **Service_code** is set from the order; **doc_type** is set from the orchestrator (e.g. `doc_type = service_code` for single-doc services).  
- So: AI Workflow Blueprint order → `service_code = AI_WF_BLUEPRINT` → lookup prompt for `(AI_WF_BLUEPRINT, AI_WORKFLOW_BLUEPRINT_REPORT)` or `(AI_WF_BLUEPRINT, AI_WF_BLUEPRINT)` (depending on your convention).  
- No code change needed for “which prompt”; ensure **seeded or admin-created prompts** in the DB (or registry) map 1:1 to each service/doc_type you care about (AI Workflow Blueprint, Business Process Mapping, AI Tool Recommendation, MR Basic, MR Advanced, Full Compliance Audit, HMO Audit, Move-In/Out Checklist, etc.).

---

## 5. Should we save this prompt in the database?

**Yes — recommended.**

- **Prompt Manager** already has `prompt_templates`: `template_id`, `service_code`, `doc_type`, `system_prompt`, `user_prompt_template`, `output_schema`, version, status (DRAFT/TESTED/ACTIVE), etc.
- Benefits of storing the AI Workflow Blueprint prompt (and the others) in the DB:
  - **Editable** without code deploys (admin or script).  
  - **Versioned** (DRAFT → TESTED → ACTIVE), with audit trail.  
  - **Same injection pattern**: store `user_prompt_template` with a single `{{INPUT_DATA_JSON}}`; the bridge already replaces it with the intake JSON.  
  - **Deterministic selection**: one ACTIVE prompt per (service_code, doc_type).

**How it fits your AI Workflow Blueprint master prompt:**

- **system_prompt:**  
  The full “SYSTEM ROLE”, “INPUT DATA”, “OUTPUT STRUCTURE”, “HARD CONSTRAINTS”, “QUALITY BAR”, “FINAL INSTRUCTION” text (and any global framework you prepend, e.g. AUTHORITATIVE_FRAMEWORK_V2).
- **user_prompt_template:**  
  Either:
  - Minimal:  
    `"Use the following intake data as the source of truth for your response.\n\n{{INPUT_DATA_JSON}}\n\nGenerate the full response now."`  
  - Or a short instruction that references the sections and then:  
    `"\n\n{{INPUT_DATA_JSON}}\n\nGenerate the full response now."`  
  So the **intake is always** the JSON injected by the backend; no need to list fields again in the user template if they’re already in the system prompt.
- **output_schema:**  
  Match the writer template: e.g. `GPT_EXECUTIVE_SUMMARY`, `GPT_WORKFLOW_OVERVIEW`, `GPT_PROCESS_FLOW`, `GPT_RECOMMENDATIONS` (or whatever keys your DOCX/PDF builder expects).

Storing in the DB does **not** require a second “prefill” step: the backend still builds `intake_data` from the order, creates the snapshot, and injects it into `{{INPUT_DATA_JSON}}`. The prompt in the DB only needs to contain that single placeholder.

---

## 6. Intake shape vs prompt expectations

For the output to be **personalised and coherent**, the **intake_payload** (and thus the JSON in `{{INPUT_DATA_JSON}}`) must contain the fields the prompt describes, e.g.:

- Business Description  
- Current Process Overview  
- Goals & Objectives  
- Priority Goal  
- Team Size  
- Processes to Focus On  
- Current Tools Used  
- Main Challenges  
- Additional Notes  

So:

- **Unified intake wizard** and **service definitions** must define these fields for `AI_WF_BLUEPRINT` and store them in `intake_payload` (and hence in `order.intake_snapshot.intake_payload`).  
- When building `intake_data` for the orchestrator, use that payload (plus any extra context like order_ref, client name) so the LLM sees one consistent, complete JSON.  
- Same idea for every other service: intake schema per service → same fields in `intake_payload` → same fields in `{{INPUT_DATA_JSON}}` for that service’s prompt.

---

## 7. Summary (no implementation)

| Question | Answer |
|----------|--------|
| How to ensure the prompt has the inputted data? | Backend injects **order-derived intake** into `{{INPUT_DATA_JSON}}`; ensure intake_payload holds all fields the prompt expects. |
| Prefill before sending to LLM? | **Yes:** prefill = backend loads `intake_data` from the order (and optionally request body) **before** building the user prompt and calling the LLM. |
| Correct flow? | Order created with intake_snapshot → on “Generate”, backend uses order’s intake_snapshot as source of truth → create snapshot → inject into prompt → LLM → render. |
| Safest approach? | Use **order-stored intake** as default; allow override only when explicitly provided (e.g. after “request more info”); one prompt per (service_code, doc_type). |
| Each service uses its prompt? | Already: selection by `service_code` (+ `doc_type`). Keep one prompt per service/doc_type in DB or registry. |
| Save prompt in DB? | **Yes.** Store full system + user prompt (with `{{INPUT_DATA_JSON}}`) in Prompt Manager; use ACTIVE version per (service_code, doc_type). |

Once this flow and storage model are agreed, the same pattern applies to the other prompts (Business Process Mapping, AI Tool Recommendation, MR Basic, MR Advanced, Full Compliance Audit, HMO Audit, Move-In/Out Checklist, etc.): each gets one prompt record keyed by service_code/doc_type, and each receives the same intake-injection mechanism from the order.

---

## 8. When you provide the remaining prompts

For each document type (Business Process Mapping, AI Tool Recommendation, Market Research – Basic, Market Research – Advanced, Full Compliance Audit, HMO Compliance Audit, Move-In/Out Checklist, etc.), provide:

1. **Service code** (e.g. `AI_PROC_MAP`, `AI_TOOL_RECOMMENDATION`, `MR_BASIC`, `MR_ADV`, `FULL_COMPLIANCE_AUDIT`, `HMO_COMPLIANCE_AUDIT`, `MOVE_IN_OUT_CHECKLIST`).
2. **Doc type** (e.g. `BUSINESS_PROCESS_MAPPING_REPORT`, `AI_TOOL_RECOMMENDATION_REPORT`, …) — must match what the orchestrator and writer template expect.
3. **Full system prompt text** (role, input data list, output structure with section placeholders, hard constraints, quality bar).
4. **Intake field names** the prompt expects (so intake_payload and unified wizard can align).
5. **Output schema keys** (section names that will appear in the JSON and in the writer template, e.g. GPT_EXECUTIVE_SUMMARY, GPT_WORKFLOW_OVERVIEW, …).

Each will be stored as one row in `prompt_templates` with `{{INPUT_DATA_JSON}}` in the user template; the pipeline will prefill intake from the order and inject it once. No implementation until you confirm this design.
