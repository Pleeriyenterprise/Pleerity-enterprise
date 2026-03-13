# Chat Assistant Knowledge Upgrade – Task vs Codebase Audit

## Goal (task)

Upgrade the **Pleerity website chat assistant** so it can answer real user questions from a **structured knowledge base**, not just scripted flows, by combining:

1. Guided onboarding flows  
2. Intent detection  
3. **Structured knowledge retrieval**  
4. Action-oriented responses  

---

## 1. Scope: Which Chat Is This?

| System | Location | Purpose |
|--------|----------|---------|
| **Website support chat** | `backend/services/support_chatbot.py`, `backend/routes/support.py`, `frontend/.../SupportChatWidget.js` | Public site chatbot (FAQ, CVP, documents, handoff). **This is the target of the task.** |
| Portal assistant | `backend/services/assistant_*.py`, `backend/routes/assistant.py` | Client portal assistant (uses `assistant_retrieval_service.py` + markdown KB). **Not in scope.** |
| Help centre KB | `backend/routes/knowledge_base.py` (kb_articles) | Published articles for help centre + help assistant search. **Could be reused or kept separate.** |

The task refers to the **website chat assistant**; all findings below apply to `support_chatbot.py` and its callers.

---

## 2. Requirements vs Current State

### Req 1: Structured knowledge base (id, title, category, keywords, answer, optional actions, optional audience)

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| Format: JSON or TS objects | Python dict in `get_chatbot_knowledge_base()`: `company`, `frontend_links`, `services`, `faqs` | FAQs have `question`, `answer`, `category` only. No `id`, no `keywords` array, no per-entry `actions` or `audience`. |
| Suggested topics (CVP overview, CVP pricing, document packs, property management, compliance score, evidence upload, reminder system, password reset, billing, AI automation, market research) | Partially covered: services (CVP, document_packs, ai_automation, market_research), and 8 FAQs (password reset, order status, CRN, cancel, documents, delivery, payment, refunds). | No dedicated entries for: property management, compliance score, evidence upload, reminder system as first-class KB entries. Some are inside CVP “features” text only. |
| Each entry: id, title, category, keywords, answer, optional actions, optional audience | `get_guided_knowledge()` has intent-keyed entries with description, features, **actions** (no id/keywords/audience). FAQs have question, answer, category only. | **Missing:** unified entry shape with `id`, `title`, `keywords`, `actions`, `audience`. |

**Conclusion:** Add a **structured Q&A knowledge base** (e.g. list of entries with id, title, category, keywords, answer, optional actions, optional audience) that can be searched. This can extend or sit alongside the existing `services` + `faqs` structure.

---

### Req 2: Retrieval logic (search by keywords/topic, return best match, avoid hallucination when no strong match)

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| Search KB by keywords / topic | **None.** No dedicated retrieval step. | All “unknown” queries go to `generate_ai_response()` which sends the full `get_chatbot_knowledge_base()` JSON to the LLM. The LLM may still hallucinate or ignore the KB. |
| Return best matching answer | Intent match returns `build_guided_response(intent)`. Fallback uses a weak FAQ check: “any of first 3 words of FAQ question in message” → return that FAQ answer. | No proper keyword/topic scoring or “best match” selection. |
| Avoid hallucinating if no strong match | Not enforced. LLM is free-form. | **Missing:** “only answer from KB when confidence above threshold; otherwise clarifying question or human support.” |

**Conclusion:** Add **explicit retrieval**: e.g. score user message against structured KB (keywords/title/category), pick best match above a threshold, and **return that answer without calling the LLM**. If no match above threshold, do not answer from KB (go to fallback/clarify/human).

---

### Req 3: Fallback logic (clarifying question or offer human support)

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| If no strong answer: clarifying question **or** offer human support | • After 2 consecutive “fallback” replies, we show `ESCALATION_MESSAGE` (offer human). • `generate_fallback_response()`: weak FAQ match or generic “What would you like help with?” + offer human. | No explicit **clarifying question** path (e.g. “Are you asking about X or Y?”). Fallback is either one FAQ match or one generic message; then escalation only after 2 fallbacks. |

**Conclusion:** Add an optional **clarifying** response when retrieval finds weak or ambiguous matches (e.g. “Did you mean compliance for CVP or document packs?”) and keep the existing “offer human” after 2 fallbacks.

---

### Req 4: Keep guided onboarding flow

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| Do not remove onboarding / intent-driven flow; combine with knowledge retrieval | Full onboarding in place: welcome + 5 options, qualification (user type), recommendation, conversion actions, lead capture. Intent detection and `build_guided_response()` for CVP, document_packs, automation, market_research, pricing, etc. | **None.** Must only **add** retrieval before or after intent handling, not replace it. |

**Conclusion:** Keep current flow. Insert **knowledge retrieval** in the pipeline where appropriate (e.g. when no intent match, or after intent for follow-up questions).

---

### Req 5: Response format (short intro, optional bullets, next action choices)

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| Short intro, optional bullets, next action choices | `build_guided_response()` does exactly this (description, “Key features” bullets, pricing, “What would you like to do?” with action links). Canned and fallback responses are plain text. | Guided responses are compliant. **Retrieval-derived answers** should follow the same format (intro + bullets + actions) when we add them; currently we have no retrieval answers. |

**Conclusion:** When adding retrieval, format the chosen KB entry as: short intro (or title), optional bullets (if entry has structure), plus next action choices (from entry or default).

---

### Req 6: Conversation context (e.g. “pricing” in CVP context → CVP pricing)

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| If current topic is CVP and user says “pricing”, answer CVP pricing | Implemented: `pricing_like` + `ctx.get("intent")` in `handle_chat_message()` → `build_guided_response(ctx["intent"])`. | **None.** Extend retrieval to use `conversation_context.intent` / `topic` when scoring or selecting KB entries (e.g. prefer CVP-related entries when context is CVP). |

**Conclusion:** Use existing `conversation_context` in any new retrieval/scoring (topic-aware retrieval).

---

### Req 7: File structure (suggested: src/chat/knowledgeBase.ts, intentResolver.ts, responseBuilder.ts, contextManager.ts)

| Task requirement | Current implementation | Conflict / note |
|------------------|------------------------|------------------|
| Suggested: `src/chat/knowledgeBase.ts`, `intentResolver.ts`, `responseBuilder.ts`, `contextManager.ts` | **Backend is Python;** chat logic lives in `backend/services/support_chatbot.py` (single module). No `src/chat/` on frontend; widget is `SupportChatWidget.js` and does not do intent/KB logic. | **Conflict:** Task suggests TypeScript under `src/chat/`. The codebase implements the assistant on the **backend**; the frontend only sends messages and displays replies. |

**Recommendation:** Implement in **backend** to avoid duplication and keep a single source of truth:

- **Do not** add a parallel `src/chat/` with TS resolver/KB on the frontend.
- Add structure **under backend** instead, e.g.:
  - `backend/services/support_chatbot_knowledge.py` – structured KB (data + loaders).
  - `backend/services/support_chatbot_retrieval.py` – retrieval (keyword/topic scoring, threshold, context-aware).
  - Keep intent and context in `support_chatbot.py` or extract to `support_chatbot_intent.py` if desired.
  - Response formatting can stay in `support_chatbot.py` or a small `support_chatbot_response.py` (intro + bullets + actions from KB entry).

So: **same logical structure (knowledge base, retrieval, response building, context), but in Python under `backend/services/`, not TypeScript under `src/chat/`.**

---

### Req 8: Do not redesign current UI

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| Extend assistant logic only; no UI redesign | All behaviour is in backend + existing `SupportChatWidget.js` (messages, quick actions, handoff, etc.). | **None.** No UI changes required for this task. |

---

### Req 9: Return files created/modified, KB structure, retrieval logic, fallback logic, examples

| Task requirement | Current implementation | Gap |
|------------------|------------------------|-----|
| Deliverables: files created/modified, KB structure, retrieval, fallback, example questions | N/A until implementation. | To be produced when implementing. |

---

## 3. Conflicting Instructions and Safest Options

| Conflict | Task says | Codebase reality | Safest option |
|----------|-----------|------------------|---------------|
| **File structure** | `src/chat/*.ts` (TypeScript) | Chat is backend Python; frontend only renders. | Implement in **backend** (e.g. `backend/services/support_chatbot_knowledge.py`, `support_chatbot_retrieval.py`). Do **not** add `src/chat/` with duplicate logic. |
| **“Structured knowledge base”** | New format with id, title, keywords, answer, actions, audience. | Existing `get_chatbot_knowledge_base()` has services + faqs (different shape). | **Extend** with a dedicated **Q&A list** (e.g. `structured_qa` or separate module) that has the new shape. Keep existing services/faqs for backward compatibility and for LLM/fallback; use the new list for **retrieval-first** answers. |
| **Avoid hallucination** | Only answer when there is a strong match. | Today all non-intent queries go to LLM with KB in prompt. | Add a **retrieval step before LLM**: if retrieval returns a match above a confidence threshold, return that answer (formatted) and **do not** call the LLM. If below threshold, go to clarifying question or existing fallback/escalation. |
| **Fallback** | Clarifying question **or** offer human. | We have generic fallback + escalation after 2 fallbacks. | **Add** an explicit “clarifying” path when retrieval has weak/ambiguous matches (e.g. “I’m not sure – are you asking about X or Y?”). Keep current “offer human” after 2 fallbacks. |

---

## 4. What Is Already Implemented (No Duplication)

- **Guided onboarding:** Welcome, 5 options, qualification (user type), recommendation, conversion actions, lead capture.
- **Intent detection:** `INTENTS`, `detect_intent()`, used in `handle_chat_message()`.
- **Context:** `conversation_context` (intent, topic, last_action, user_type, onboarding_step, lead_capture_offered); pricing follow-up uses context.
- **Action-oriented responses:** `build_guided_response()` (intro, features, pricing, action links); “Check your compliance risk” and other links.
- **Legal guardrails:** `is_legal_advice_request()` → refusal message.
- **Human handoff:** `needs_human_handoff()`, handoff options, escalation after 2 fallbacks.
- **Fallback when LLM fails:** `generate_fallback_response()` (weak FAQ match + generic reply).
- **Canned responses:** Quick actions (CVP, document packs, pricing, reset password, speak to human, etc.).
- **KB data:** `get_chatbot_knowledge_base()` (company, links, services, faqs) and `get_guided_knowledge()` (intent → description, features, actions).

---

## 5. What Is Missing (To Implement)

1. **Structured Q&A knowledge base**  
   - Entries with: id, title, category, keywords, answer, optional actions, optional audience.  
   - Cover suggested topics (CVP overview/pricing, document packs, property management, compliance score, evidence upload, reminder system, password reset, billing, AI automation, market research).  
   - Maintainable format (e.g. JSON or Python dict/list in a dedicated module or file).

2. **Retrieval logic**  
   - Score user message (and optionally `conversation_context.topic`) against KB (keywords, title, category).  
   - Return best match and a confidence score.  
   - Use a threshold: above threshold → return that answer (no LLM); below → go to clarifying or fallback.

3. **Integration in pipeline**  
   - In `handle_chat_message()`, after intent/qualification/pricing-follow-up but **before** `generate_ai_response()`: run retrieval.  
   - If strong match: format as short intro + bullets + action choices; return; set context if needed.  
   - If weak/ambiguous: optionally return a clarifying question.  
   - If no match: keep current behaviour (call LLM or existing fallback).

4. **Fallback behaviour**  
   - Add clarifying-question response when retrieval is weak/ambiguous.  
   - Keep existing “offer human” after 2 fallbacks.

5. **Response format for retrieval**  
   - Ensure retrieval-derived answers use the same style: short intro, optional bullets, next action choices (from KB entry or defaults).

6. **Context-aware retrieval**  
   - Use `conversation_context.intent` / `topic` to prefer topic-relevant entries (e.g. CVP when context is CVP).

7. **File structure (backend)**  
   - e.g. `support_chatbot_knowledge.py` (KB definition/load), `support_chatbot_retrieval.py` (scoring, threshold, context-aware selection).  
   - Keep or refactor intent/response in `support_chatbot.py` as agreed.

---

## 6. Suggested Implementation Order (When Approved)

1. **Define the structured KB** (e.g. in `support_chatbot_knowledge.py` or a JSON file loaded by it) with the new entry shape and suggested topics.  
2. **Implement retrieval** (keyword/topic scoring, threshold, context-aware) in `support_chatbot_retrieval.py`.  
3. **Add response builder** for retrieval results (intro + bullets + actions) reusing the same style as `build_guided_response()`.  
4. **Wire into `handle_chat_message()`**: after existing intent/onboarding/pricing logic, call retrieval; if above threshold return built response; if weak offer clarifying or fallback.  
5. **Add clarifying-question** path when retrieval is below threshold but not empty.  
6. **Document**: files created/modified, KB structure, retrieval and fallback behaviour, and example questions the assistant can now answer.

---

## 7. Example Questions the Assistant Could Answer (After Implementation)

- “What is Compliance Vault Pro?”  
- “How much does CVP cost?” / “CVP pricing?”  
- “What’s in the document packs?”  
- “How do I reset my password?”  
- “What is the compliance score?”  
- “How do I upload evidence?”  
- “How do reminders work?”  
- “How do I cancel my subscription?”  
- “What AI automation do you offer?”  
- “Tell me about market research.”  

With **context**: after user has been talking about CVP, “What about pricing?” → CVP pricing (already supported); retrieval can reinforce and format the same answer from KB.

---

## 8. Status

- **Audit:** Complete.  
- **Implementation:** Done (safe order). See section 9 below.

---

## 9. Implementation Deliverables (Done)

### Files created

| File | Purpose |
|------|---------|
| `backend/services/support_chatbot_knowledge.py` | Structured Q&A list: `get_structured_qa()` returns entries with id, title, category, keywords, answer, actions, audience. CVP pricing loaded from plan_registry; frontend base from env. |
| `backend/services/support_chatbot_retrieval.py` | `retrieve(message, conversation_context)` scores message + context against KB (keywords, title, category), returns best entry + confidence and top-5 for clarifying. `build_response_from_entry(entry)` formats answer + action links. `get_clarifying_message(scored)` builds "Are you asking about X or Y?" when score is weak. Constants: `RETRIEVAL_CONFIDENCE_THRESHOLD = 0.35`, `CLARIFYING_THRESHOLD = 0.18`. |

### Files modified

| File | Changes |
|------|---------|
| `backend/services/support_chatbot.py` | After lead-capture block and before escalation: call retrieval; if `best_score >= RETRIEVAL_CONFIDENCE_THRESHOLD` return `build_response_from_entry(best_entry)` with `metadata.retrieval_matched`, `kb_id`, `category`; if `best_score >= CLARIFYING_THRESHOLD` return `get_clarifying_message(all_scored)` when non-None with `metadata.clarifying`. Exceptions from retrieval fall through to existing AI/fallback. `_count_recent_fallback_responses` treats `retrieval_matched` and `clarifying` as successful (no escalation). |

### Knowledge base structure

Each entry in `get_structured_qa()`:

- **id**: string (e.g. `cvp-overview`, `password-reset`)
- **title**: string (e.g. "Compliance Vault Pro overview")
- **category**: string (e.g. `cvp`, `document_packs`, `billing`, `login`, `automation`, `market_research`, `property_management`)
- **keywords**: list of strings (lowercase phrases for matching)
- **answer**: string (plain text; used as intro in response)
- **actions**: list of `(label, url)` with `url` None for in-chat actions (e.g. "Ask a question")
- **audience**: optional (currently None for all)

Topics included: Compliance Vault Pro overview, CVP pricing, Document packs, Property management, Compliance score, Evidence upload, Reminder system, Password reset, Billing support, Order status, AI automation services, Market research, CRN.

### Retrieval logic

- **Scoring**: Normalize message to words; for each KB entry compute keyword overlap (query words in keywords/title/category) with weights (keywords 1.0, title 0.8, category 0.6), normalized by query length.
- **Context boost**: If `conversation_context.intent` or `topic` aligns with entry category (e.g. `compliance_vault_pro` → cvp), multiply score by 1.2–1.25.
- **Threshold**: If best score ≥ 0.35, return that entry’s answer (no LLM). If best score ≥ 0.18 but < 0.35, return clarifying question (top 2 topics) when applicable. Otherwise continue to escalation check and then `generate_ai_response()`.

### Fallback logic

- **Strong match**: Answer from KB only; no LLM.
- **Weak match**: Clarifying message "I'm not sure which of these you mean. Are you asking about: • **Title1** • **Title2**" (or similar).
- **No match**: Existing behaviour unchanged: escalation after 2 consecutive fallbacks (offer human); else LLM with full KB in prompt; if LLM fails, `generate_fallback_response()` (FAQ match or generic).

### Example questions the assistant can now answer (from structured KB)

- "What is Compliance Vault Pro?" / "What is CVP?"
- "How much does CVP cost?" / "CVP pricing?"
- "What's in the document packs?" / "Document pack prices?"
- "How do I reset my password?"
- "What is the compliance score?" / "How does the compliance score work?"
- "How do I upload evidence?" / "Upload documents?"
- "How do reminders work?" / "Expiry alerts?"
- "How do I cancel my subscription?" / "Refunds?"
- "What AI automation do you offer?"
- "Tell me about market research." / "Market reports?"
- "What is a CRN?" / "Customer reference number?"
- "Order status?" / "Where is my order?"
- "Property management?" / "Manage multiple properties?"

With **context**: e.g. after the user has been talking about CVP, "What about pricing?" continues to be handled by existing intent/pricing follow-up (CVP pricing). Retrieval can also return the CVP pricing entry when the message matches and context is CVP (context boost).
