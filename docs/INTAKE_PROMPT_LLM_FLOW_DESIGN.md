# Intake → Prompt → LLM Flow: Design (No Implementation)

**Purpose:** Clarify how intake data reaches the LLM so generation is personalised and coherent, and how each service gets its correct prompt. Based on your AI Workflow Blueprint master prompt and the existing codebase.

---

## 1. Your questions (short answers)

| Question | Answer |
|----------|--------|
| How ensure the prompt has the inputted data so generation is personalised and coherent? | **Inject intake at request time** into the user prompt via a single placeholder `{{INPUT_DATA_JSON}}`. The intake is the **locked snapshot** taken immediately before LLM call. |
| What is the correct flow? | Intake form → saved to order/draft → at **generation time** create immutable snapshot → build user prompt by replacing `{{INPUT_DATA_JSON}}` with that snapshot (as JSON) → send system + user prompt to LLM. |
| Should intake data be prefilled before sending to the LLM? | **No.** Do **not** prefill the prompt template with customer data and store it. **Inject at request time** so the prompt template stays generic and versioned, and the data is always the snapshot used for that run. |
| Safest approach? | Keep current pattern: (1) one prompt template per service (with `{{INPUT_DATA_JSON}}`), (2) intake snapshot created once per run before GPT, (3) build user prompt = template + snapshot JSON at execution time only. |
| How make sure each service uses the particular prompt meant for it? | Already in place: prompt is selected by **service_code** (+ **doc_type** for packs). Store each master prompt (e.g. AI Workflow Blueprint, Business Process Mapping, …) under the right service_code/doc_type in the **database** so one service = one prompt (versioned). |
| Should we save this prompt in the database? | **Yes.** Save the full AI Workflow Blueprint prompt (and all other service prompts) in the **prompt_templates** collection so you get versioning, audit, and a single place that drives generation. |

---

## 2. Correct end-to-end flow (no prefill)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. INTAKE (before payment)                                                   │
│    User fills form → fields saved to draft / order (e.g. business_description,│
│    current_process_overview, goals_objectives, priority_goal, team_size,     │
│    processes_to_focus, current_tools, main_challenges, additional_notes).    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. PAYMENT & ORDER                                                           │
│    Order created/confirmed. Intake payload lives on order (or linked draft). │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. GENERATION TRIGGER                                                        │
│    Job or API loads order, reads intake from order/draft, calls orchestrator │
│    with (order_id, intake_data).                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. ORCHESTRATOR (document_orchestrator or document_pack_orchestrator)        │
│    a) Resolve service_code (and doc_type for packs).                         │
│    b) Get prompt for this service: get_prompt_for_service(service_code,      │
│       doc_type) → from DB (prompt_templates) or legacy registry.             │
│    c) Validate intake (optional; do not fail hard; flag gaps).                │
│    d) Create INTAKE SNAPSHOT (immutable copy + hash). Do this once,           │
│       immediately before building the prompt. No edits after this.           │
│    e) Build user prompt: template.replace("{{INPUT_DATA_JSON}}",             │
│       json.dumps(intake_snapshot, indent=2)).                                │
│    f) Send to LLM: system_prompt (from DB/registry) + user_prompt.          │
│    g) Parse response, validate, render DOCX/PDF, store with snapshot hash.  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Important:** The prompt **template** (with `{{INPUT_DATA_JSON}}`) is stored once per service. The **actual intake** is never stored inside the prompt; it is injected only when building the user message for that run. So:

- Personalisation = the JSON in the **user** message (the snapshot).
- Coherence = same snapshot used for the whole run and for audit.

---

## 3. Prefill vs inject at request time

| Approach | Pros | Cons |
|----------|------|------|
| **Prefill** (bake intake into the prompt and save) | — | Different “prompt” per order; no single versioned template; hard to audit; if intake is updated you have inconsistency. |
| **Inject at request time** (template + snapshot at run time) | Single template per service; versioned in DB; snapshot is clearly the input for that run; audit trail (snapshot hash on order/run). | None for correctness; this is the safe pattern. |

**Recommendation:** Do **not** prefill. Keep storing only the **template** (with `{{INPUT_DATA_JSON}}`) and inject the **intake snapshot** when you build the user prompt for each run.

---

## 4. How each service gets its prompt

- **Selection key:** `(service_code, doc_type)`.
  - Single-doc services: e.g. `AI_WF_BLUEPRINT` + `AI_WORKFLOW_BLUEPRINT_REPORT`.
  - Packs: e.g. `DOC_PACK_ESSENTIAL` + `RENT_ARREARS_LETTER` (per doc).
- **Source:** Prompt Manager first (DB `prompt_templates`), then legacy `gpt_prompt_registry` if no ACTIVE prompt.
- So: one prompt row per (service_code, doc_type). AI Workflow Blueprint = one row for `AI_WF_BLUEPRINT` / `AI_WORKFLOW_BLUEPRINT_REPORT`; Business Process Mapping = one for `AI_PROC_MAP` / `BUSINESS_PROCESS_MAPPING_REPORT`; etc. No cross-use between services.

---

## 5. Saving the AI Workflow Blueprint prompt in the database

**Yes, save it in the database** in `prompt_templates`:

- **service_code:** `AI_WF_BLUEPRINT`
- **doc_type:** `AI_WORKFLOW_BLUEPRINT_REPORT` (or whatever your schema uses)
- **system_prompt:** The full master prompt (SYSTEM ROLE, INPUT DATA description, OUTPUT STRUCTURE with the four sections, HARD CONSTRAINTS, QUALITY BAR). This is the “instructions” the LLM always gets for this service.
- **user_prompt_template:** A short wrapper that injects intake and tells the model to generate, e.g.:

  ```
  Below is the intake data for this order. Use it as the SOURCE OF TRUTH for all fields (Business Description, Current Process Overview, Goals & Objectives, Priority Goal, Team Size, Processes to Focus On, Current Tools, Main Challenges, Additional Notes). Synthesise holistically; do not list or echo form fields verbatim.

  {{INPUT_DATA_JSON}}

  Generate the full response now, matching the output structure defined in your instructions (Executive Summary, Workflow Overview, Process Flow, Recommendations). Output valid JSON with keys aligned to the required schema.
  ```

- **output_schema:** Whatever your writer/template expects (e.g. `executive_summary`, `workflow_overview`, `process_flow`, `recommendations` or the `{{GPT_*}}` names if you map them later).

Then the **existing** flow already does the right thing:

1. Orchestrator gets prompt from DB for `AI_WF_BLUEPRINT` / `AI_WORKFLOW_BLUEPRINT_REPORT`.
2. Creates intake snapshot from the order’s intake.
3. Replaces `{{INPUT_DATA_JSON}}` with `json.dumps(intake_snapshot)` in the user template.
4. Sends system_prompt + built user_prompt to the LLM.

No prefill; each run is personalised by the snapshot you inject.

---

## 6. Intake field alignment

For the output to be personalised and coherent, the **intake form** for AI Workflow Blueprint must collect and persist the same fields the prompt expects, under **stable keys** that end up in the snapshot, e.g.:

- business_description  
- current_process_overview  
- goals_objectives  
- priority_goal  
- team_size  
- processes_to_focus  
- current_tools (or current_tools_used)  
- main_challenges  
- additional_notes  

Those keys should be:

- Defined in the intake schema for that service, and  
- Saved on the order/draft so when the orchestrator reads “intake_data” it gets this object.  

Then the snapshot is a copy of that object (plus maybe `_snapshot_created_at`); the LLM sees it as the JSON in the user message. No need to “prefill” the prompt; the prompt tells the model “use the following intake” and the JSON is that intake.

---

## 7. Applying the same pattern to other services

For Business Process Mapping, AI Tool Recommendation, MR Basic, MR Advanced, Full Compliance Audit, HMO Compliance Audit, Move-In/Out Checklist, etc.:

1. **One prompt per service** in `prompt_templates`: the right `service_code` and `doc_type` for that document.
2. **system_prompt:** That service’s full master prompt (role, input description, output structure, constraints, quality bar).
3. **user_prompt_template:** Short wrapper that says “use the intake below as source of truth” + `{{INPUT_DATA_JSON}}` + “generate the full response / valid JSON”.
4. **Intake form** for that service collects the fields the prompt expects; those fields are stored on the order/draft and passed into the orchestrator as `intake_data`.
5. **At generation time:** snapshot → inject into `{{INPUT_DATA_JSON}}` → send to LLM. No prefill.

Same flow for every service; only the stored prompt and the intake schema change per service.

---

## 8. Summary

- **Flow:** Intake form → order/draft → at generation time: snapshot → inject snapshot into prompt template (`{{INPUT_DATA_JSON}}`) → LLM. Do **not** prefill the prompt with customer data.
- **Safest:** One versioned prompt template per service in the DB; intake injected at request time; snapshot immutable and hashed for audit.
- **Per-service prompt:** Use `(service_code, doc_type)` to load the right row from `prompt_templates` (or legacy registry); each service has exactly one prompt (version) used for that run.
- **Save in DB:** Yes. Store the AI Workflow Blueprint master prompt (and all others) in `prompt_templates` with the correct service_code/doc_type and a user template that contains `{{INPUT_DATA_JSON}}`.
- **Personalisation and coherence:** Ensure intake form fields match the prompt’s expected inputs and are persisted to the order; the snapshot is then the single source of truth for that run and is what the LLM sees in the user message.

Once this is agreed, you can provide the remaining prompts (Business Process Mapping, AI Tool Recommendation, MR Basic, MR Advanced, Full Compliance Audit, HMO, Move-In/Out Checklist, etc.) and they can be stored the same way and used with the same flow.
