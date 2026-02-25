# Audit: Pleerity Assistant system prompt task vs codebase

**Purpose:** Identify what is implemented vs missing against the provided task requirements (full “Pleerity Assistant” system prompt). No implementation in this doc; recommend safest path and call out conflicts.

---

## 1. Current implementation (how it was implemented)

### 1.1 System prompt
- **Location:** `backend/services/assistant_prompt.py` — `ASSISTANT_SYSTEM_PROMPT`
- **Content:** Shorter prompt; core rules: no legal advice, no verdicts, use only portal_facts + kb_snippets, use only portal_urls, no fabricated URLs, cite sources, set safety_flags for legal requests.
- **Output:** **Strict JSON only** — `{ "answer", "citations", "safety_flags" }`. The chat service parses this and the frontend displays `answer`, `citations`, and `safety_flags` (e.g. legal_advice_request).

### 1.2 Portal URLs
- **Location:** `assistant_prompt.get_portal_urls()`
- **Keys:** base, dashboard, properties, documents, upload, calendar, reports, notifications, preferences, support, property_detail_template.
- **Used in:** `assistant_chat_service` builds context with `portal_urls` and passes it to the LLM.

### 1.3 Context passed to the LLM
- **Location:** `assistant_chat_service.py` — one big context string containing:
  - Full `portal_facts` (JSON) from `get_portal_facts()` — includes client_summary, user, account_state, portfolio_summary, properties, requirements_by_property, documents, property_id_filter.
  - Separate `portal_urls` (JSON).
  - KB snippets (title, source_id, content).
  - User message.
- **Retrieval:** `assistant_retrieval_service.get_portal_facts()` returns: client_summary, user, account_state, portfolio_summary, properties, requirements_by_property, documents, property_id_filter. **No** `notification_prefs` in retrieval.

### 1.4 Data shapes (retrieval)
- **user:** name, email, role, crn — **implemented**
- **account_state:** payment_state, provisioning_status, portal_user_exists, activation_email_status, password_set — **implemented**
- **portfolio_summary:** property_count, requirement_count, document_count, overdue_requirements_count — **implemented**  
  Task also asks: expiring_soon_count, compliant_count, score_portfolio, scores_by_property — **not present**
- **notification_prefs:** task asks email_enabled, sms_enabled, reminder_timing_days, recipients — **not in get_portal_facts** (only in support context API).

### 1.5 Escalation / handover
- **Keywords:** `ESCALATION_KEYWORDS` in chat service; `_should_suggest_handover(message)`; response includes `handover_suggested`.
- **Escalation endpoint:** POST `/api/assistant/escalate`; creates ticket, marks conversation escalated. Task’s escalation rules (when to escalate, what to say, summary for human) are **not** in the system prompt text; behaviour is partial (keyword-based suggestion only).

---

## 2. Task requirements vs implementation

| Requirement | Implemented | Notes |
|-------------|------------|--------|
| **Identity:** “Pleerity Assistant”, CVP, no legal advice | Partial | Name and intent in current prompt; task wording is more explicit and structured |
| **Strict safety rules (1–5)** | Partial | No legal advice, no inventing data, only portal + KB, no secrets, read-only — all present in spirit. Task adds exact “Is this legally required?” script and “NEVER DO” list |
| **Tone** (professional, short paragraphs, next steps) | Partial | Not explicitly in prompt |
| **Context structure:** user, portal_urls, account_state, portfolio_summary, notification_prefs, kb_snippets | Partial | user, portal_urls, account_state, portfolio_summary, kb_snippets are in context (inside portal_facts + separate portal_urls). **notification_prefs** not fetched or passed |
| **portfolio_summary:** expiring_soon_count, compliant_count, score_portfolio, scores_by_property | No | Only property_count, requirement_count, document_count, overdue_requirements_count exist |
| **Linking rules** (only portal_urls, property_detail_template, no localhost) | Yes | get_portal_urls() provides these; prompt says use only these URLs |
| **Core behaviour** (What I can see, Next steps with links, “where do I do X?”, why something flagged) | Partial | Prompt does not prescribe this structure; no explicit “What I can see” / “Next steps” format |
| **Escalation rules** (when to escalate, what to say, summary for human) | Partial | Keyword-based handover suggestion only; no prompt text for “I’m going to hand this to…” or handover summary format |
| **Output format** | **Conflict** | Task: prose sections (“What I can see”, “What this means”, “Next steps”, “If you still need help”). **Current:** JSON only: answer, citations, safety_flags. Frontend and `_parse_chat_response()` depend on JSON |

---

## 3. Conflicts and safest approach

### 3.1 Output format (main conflict)
- **Task:** Prose output with named sections; no JSON specified.
- **Current:** JSON-only response; pipeline and UI rely on `answer`, `citations`, `safety_flags`.
- **Risk:** Replacing the system prompt with the task text as-is would make the model return prose; `_parse_chat_response()` would fail and the UI would not get citations or safety_flags.
- **Recommendation:** **Do not switch to prose-only.** Keep the **JSON response contract** (answer, citations, safety_flags). Merge the task’s **content** (safety rules, tone, behaviour, linking, escalation wording) into the system prompt while **explicitly requiring** the same JSON shape. Add instructions such as: “Put your reply in the ‘answer’ field; use the sections (What I can see, Next steps, etc.) **inside** the answer text so the structure is visible to the user, but always respond with valid JSON.”

### 3.2 Duplication
- There is no second system prompt elsewhere; single source of truth is `assistant_prompt.ASSISTANT_SYSTEM_PROMPT`. No duplication to remove.

### 3.3 notification_prefs
- Task says context includes `notification_prefs`. Currently not in `get_portal_facts()`. Support context API reads `notification_preferences` by client_id. **Recommendation:** Add optional fetch of `notification_preferences` in `get_portal_facts()` and include a minimal `notification_prefs` object (e.g. email_enabled, sms_enabled, reminder_timing_days, recipients) in the returned dict so the prompt can reference it once the prompt text is updated.

### 3.4 portfolio_summary enrichment
- Task wants: expiring_soon_count, compliant_count, score_portfolio, scores_by_property. Codebase has compliance_score and expiring_soon logic elsewhere (e.g. compliance_score service, portfolio/calendar routes). **Recommendation:** Add to `get_portal_facts()` only what is already available without heavy new logic: e.g. expiring_soon_count (from requirement status or due_date), compliant_count (from requirement status). Add score_portfolio / scores_by_property only if we can read from existing property/compliance stores without new scoring runs.

---

## 4. What’s implemented vs missing (summary)

**Implemented**
- Single system prompt in `assistant_prompt.py`; portal_urls from app base URL; no fabricated URLs.
- Context includes: user, account_state, portfolio_summary (basic counts), portal_urls, kb_snippets, full portal_facts.
- Safety: no legal advice, no verdicts, post-process verdict rewriting, legal_advice_request flag and audit.
- Escalation: keyword-based handover_suggested; POST /escalate creates ticket and marks conversation.

**Missing / partial**
- **Prompt text:** Task’s full “Pleerity Assistant” wording (identity, strict rules, tone, identity+context list, core behaviour, linking rules, escalation rules, output sections, safe language examples, NEVER DO) is not in the codebase; current prompt is shorter and does not describe the context structure.
- **notification_prefs** in assistant context (not fetched in get_portal_facts).
- **portfolio_summary:** expiring_soon_count, compliant_count, score_portfolio, scores_by_property.
- **Output:** Task describes prose sections; implementation requires JSON — must keep JSON and embed sectioned prose inside `answer`.

---

## 5. Recommended next steps (no implementation here)

1. **Prompt:** Replace/extend `ASSISTANT_SYSTEM_PROMPT` with the task’s content but **append** (or clearly restate) the requirement to respond with **only** the JSON object `{ "answer", "citations", "safety_flags" }`, with sectioned text inside `answer` (e.g. “What I can see”, “Next steps”, etc.).
2. **Context structure:** In the prompt, explicitly list “You will receive: user, portal_urls, account_state, portfolio_summary, notification_prefs, kb_snippets” so it matches the data we pass (after adding notification_prefs).
3. **Data:** Add `notification_prefs` to `get_portal_facts()`; optionally add expiring_soon_count and compliant_count (and scores if available from existing stores) to `portfolio_summary`.
4. **Escalation:** Add the task’s escalation wording and “summary for human” instructions into the system prompt while keeping existing escalation API and handover_suggested behaviour.
5. **Tests:** After changes, run assistant chat and retrieval tests; confirm frontend still receives answer, citations, safety_flags.

This keeps the existing pipeline and UI intact, avoids duplication, and aligns behaviour with the task in the safest way.
