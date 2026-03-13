# Chat Assistant Upgrade – Task vs Codebase Audit

## Goal

Check the codebase against the task requirements for upgrading the Pleerity marketing website chat from a "simple FAQ bot" to a "guided support, onboarding, and recommendation assistant." Identify what is implemented, what is missing, and any conflicts. Propose the safest, most professional options without implementing blindly.

---

## Architecture (Relevant to Conflicts)

| Layer | Task assumption | Actual codebase |
|-------|-----------------|-----------------|
| **AI / logic** | Task suggests frontend files (`frontend/src/chat/knowledgeBase.ts`, `intentResolver.ts`, etc.) | **Backend-only**: LLM, intent, KB, retrieval, and recommendations live in `backend/services/support_chatbot.py`, `support_chatbot_knowledge.py`, `support_chatbot_retrieval.py`. Frontend only POSTs to `/api/support/chat` and `/support/quick-action/{id}`. |
| **Context** | Session-level `conversationContext` | **Implemented**: Frontend state in `SupportChatWidget.js`; sent in request body; backend merges and returns updated context. |
| **Knowledge** | "Create a structured knowledge base file, e.g. frontend/src/chat/knowledgeBase.ts" | **Backend**: `support_chatbot_knowledge.get_structured_qa()` returns id, title, category, keywords, answer, actions, audience. No `frontend/src/chat` folder. |

**Implication:** The task’s suggested file layout (frontend `knowledgeBase.ts`, `intentResolver.ts`, etc.) does not match the current architecture. Implementing those as new frontend modules would duplicate or conflict with backend logic. The safest approach is to treat the backend as the source of truth and extend it where needed; do not add parallel frontend logic for intent/KB/recommendations.

---

## 1. Conversation context memory

**Task:** Session-level `conversationContext` with intent, topic, user_type, portfolio_size, primary_goal, secondary_need, last_action. Use for follow-up answers (e.g. "CVP" → topic = compliance_vault_pro; "pricing" → CVP pricing in context).

**Status: IMPLEMENTED**

- **Backend** (`support_chatbot.handle_chat_message`): `ctx` includes intent, topic, last_action, user_type, portfolio_size, primary_goal, secondary_need, onboarding_step, lead_capture_offered, problem_intent. Received as `conversation_context` in `ChatRequest`, returned in `ChatResponse`.
- **Frontend** (`SupportChatWidget.js`): `conversationContext` state with the same fields; sent on every `/support/chat` request; updated from `response.data.conversation_context`.
- **Pricing-in-context:** Backend uses `ctx.get("intent")` so that after "CVP", a follow-up "pricing" uses CVP pricing (short follow-up block around lines 1078–1100).

**Gap:** None.

---

## 2. Intent detection

**Task:** Lightweight intent resolver. Intents: compliance_vault_pro, document_packs, automation, market_research, account_support, pricing, human_support. Keyword mapping as specified.

**Status: IMPLEMENTED (backend); NAMING DIFFERENCE**

- **Backend** (`support_chatbot.py`): `INTENTS` dict with compliance_vault_pro, document_packs, automation, market_research, account_support, pricing. Keywords align with task (e.g. "cvp", "compliance vault", "document pack", "automation", "research", "login", "reset password", "pricing", "cost").
- **human_support:** **Done.** `"human_support"` added to `INTENTS` with keywords "talk to support", "human", "help", "speak to human", "contact support", "real person". When this intent is detected, `handle_chat_message` returns the same handoff response and sets `ctx["intent"] = "human_support"` in conversation_context.

---

## 3. Guided onboarding flow

**Task:** On first open show: "Hello, welcome to Pleerity. What are you trying to do today?" and 5 options. After first selection, one follow-up when useful (e.g. compliance: "Are you a: Landlord / Property manager / Letting agency / Just exploring"). Store answers in conversationContext.

**Status: IMPLEMENTED; ONE WORDING GAP**

- **Welcome:** Frontend shows a single welcome message when messages are empty; current text is: `Tell me what you're trying to solve, and I'll point you to the right option.` Task text: **"Hello, welcome to Pleerity. What are you trying to do today?"**
- **5 options:** Present: Manage property compliance, Get landlord documents, Automate workflows, Get market research, Contact support (ids: compliance, documents, automation, research, support). Shown when `messages.length === 1` and the only message is the bot welcome.
- **Follow-up:** For compliance, backend returns QUALIFICATION_QUESTION ("Are you a: Landlord / Property manager / Letting agency / Just exploring") and `user_type_options`; frontend renders `QualificationButtons`. For compliance + landlord, backend then asks PORTFOLIO_SIZE_QUESTION with `portfolio_size_options`. Answers stored in `ctx` (user_type, portfolio_size) and returned in conversation_context.

**Gap:** ~~Welcome message text only.~~ **Done:** `WELCOME_MESSAGE` in `SupportChatWidget.js` set to: `Hello, welcome to Pleerity. What are you trying to do today?`

---

## 4. Structured knowledge base

**Task:** Create a structured KB file (e.g. frontend/src/chat/knowledgeBase.ts). Entries: id, title, category, keywords, answer, optional actions, optional audience. Use starter entries for CVP, document packs, pricing, compliance score, evidence upload, reminder system, property management, password reset, account support, AI automation, market research, notification channels, human support.

**Status: IMPLEMENTED (BACKEND); LOCATION CONFLICT**

- **Backend** (`support_chatbot_knowledge.get_structured_qa()`): Entries have id, title, category, keywords, answer, actions (label + url), audience. Topics covered: CVP overview, CVP features, CVP pricing, document packs, document pack pricing, compliance score, evidence upload, reminder system, property management, password reset, account support (login), AI automation, market research, billing, order status, CRN. Human support is handled by handoff flow; notification channels are mentioned in reminder-system answer.
- **Conflict:** Task suggests a **frontend** file; the only KB in the codebase is **backend**. Adding `frontend/src/chat/knowledgeBase.ts` would duplicate data and create two sources of truth.

**Recommendation:** Do **not** add a frontend knowledge base file. Keep the single backend KB in `support_chatbot_knowledge.py`. If a frontend-facing list is ever needed (e.g. for type hints or static checks), it can be a thin re-export or generated from an API, not a second full copy of content.

---

## 5. Knowledge retrieval

**Task:** On direct questions: search structured KB, use conversation context to improve match, return best answer, avoid hallucination when confidence is low. If no strong match: clarifying question or offer human support.

**Status: IMPLEMENTED**

- **Backend** (`support_chatbot_retrieval.py`): `retrieve(message, ctx)` scores query + context against `get_structured_qa()`; context boosts (e.g. topic CVP boosts cvp category). `RETRIEVAL_CONFIDENCE_THRESHOLD` (0.35) and `CLARIFYING_THRESHOLD` (0.18). Above threshold → `build_response_from_entry` + `get_actions_from_entry`. Between thresholds → `get_clarifying_message`. Below → fallback to AI or escalation.
- **Integration** (`handle_chat_message`): Retrieval runs before LLM; on match returns response + actions and sets `last_action: "retrieval"`. On clarifying, returns clarifying message. No strong match eventually leads to escalation after 2 fallbacks.

**Gap:** None.

---

## 6. Context-aware recommendations

**Task:** Lightweight recommendation from context (e.g. landlord + compliance + 1_2 → CVP; landlord + documents → Document Packs; agency + automation → AI Automation; exploring → overview/pricing/demo). Include short recommendation, reason, clickable next actions.

**Status: IMPLEMENTED**

- **Backend:** `get_recommendation(ctx)` uses intent, user_type, portfolio_size (and primary_goal). Returns (service_key, reason). `build_recommendation_response(service_key, reason, ctx)` builds intro ("For [user_type], [Service] is likely the best fit because [reason]") + key features + pricing. `_get_guided_actions(service_key)` returns `[{ label, url }]` for the UI.
- **Flow:** After qualification (and optionally portfolio size), backend returns recommendation response and actions; frontend shows message + clickable action buttons from `response.data.actions`.

**Gap:** None.

---

## 7. Response format

**Task:** Short intro, short bullets if needed, next actions. No long raw text or tables unless necessary.

**Status: IMPLEMENTED**

- Guided responses and recommendations are built as intro + bullet list + (in backend text, trimmed) action lines; actions are passed separately as `actions` array. Frontend renders actions as buttons/links. Canned responses use short bullets. Tables exist only where needed (e.g. document pack pricing in one canned response).

**Gap:** None.

---

## 8. Clickable actions instead of raw links

**Task:** All actions as clickable hyperlinks or buttons, not raw URLs. Use an actions array like `[{ label, url }, ...]`. Support for KB answers, onboarding recommendations, support escalation.

**Status: IMPLEMENTED**

- **Backend:** Responses return `actions: [{ label, url }]` (url optional for in-chat actions). Used for guided responses, recommendations, retrieval answers, canned quick-action responses.
- **Frontend:** `MessageBubble` renders `message.actions` as links (with `target="_blank"` where url present). Bot text is also linkified for any remaining URLs (`linkifyText`). Handoff shows HandoffOptions (Live Chat, Email, WhatsApp) as buttons.

**Gap:** None.

---

## 9. Reset / start new chat

**Task:** Visible control in header "Start new chat"; `resetConversation()`: clear history, clear conversationContext, restore welcome. Also detect "reset", "start over", "new chat" in text and trigger same reset.

**Status: PARTIALLY IMPLEMENTED**

- **Header:** "Start new chat" button in chat header calls `resetConversation()` (clears conversationId, messages, conversationContext, handoff/ticket UI, resets quick actions). Next open shows welcome again via existing `useEffect` that adds the single welcome message when `messages.length === 0`.
- **Done:** Text commands "reset", "start over", "new chat" now trigger reset. In `sendMessage`, if trimmed input matches `/^(reset|start over|new chat)$/i`, `resetConversation()` is called and the message is not sent to the backend.

---

## 10. Quick actions

**Task:** Assistant can surface and handle: Compliance Vault Pro, Document Packs, Pricing, Reset Password, Talk to Support, Start New Chat; each maps to correct intent or flow.

**Status: IMPLEMENTED**

- **Backend** `get_all_quick_actions()` and canned responses: cvp_info, document_packs_info, pricing, reset_password, speak_to_human, check_order_status, billing_help. Quick-action endpoint sets conversation_context intent/topic from action (e.g. cvp_info → compliance_vault_pro).
- **Frontend:** QuickActionsPanel shows these plus "Start New Chat" (calls `resetConversation`). All map to the right intent or handoff/reset flow.

**Gap:** None. Task list is a minimum; codebase includes extra (Check Order Status, Billing Help), which is acceptable.

---

## 11. Human escalation

**Task:** If the assistant cannot answer after two attempts, respond with something like "I may need a human team member to help with that. Would you like to contact support?" and show a clickable support action.

**Status: IMPLEMENTED**

- **Backend:** `ESCALATION_AFTER_UNANSWERED = 2`. `_count_recent_fallback_responses(conversation_history)` counts consecutive bot messages that were AI fallback. When count ≥ 2, returns `ESCALATION_MESSAGE` and `action: "handoff"` with handoff_data. ESCALATION_MESSAGE text matches the task idea.
- **Frontend:** When `response.data.action === "handoff"`, shows HandoffOptions (Live Chat, Email Ticket, WhatsApp) as clickable options.

**Gap:** None.

---

## 12. File structure

**Task suggests:**  
`frontend/src/chat/knowledgeBase.ts`, `intentResolver.ts`, `contextManager.ts`, `recommendationEngine.ts`, `responseBuilder.ts`, and to follow existing project structure if it suggests better placement.

**Actual:**  
- No `frontend/src/chat` directory.  
- Intent: `support_chatbot.detect_intent` (and problem layer).  
- Context: frontend state + backend merge in `handle_chat_message`.  
- Recommendations: `support_chatbot.get_recommendation` + `build_recommendation_response`.  
- KB: `support_chatbot_knowledge.get_structured_qa`; retrieval in `support_chatbot_retrieval`.  
- Response building: `build_guided_response`, `build_recommendation_response`, retrieval `build_response_from_entry` in backend.

**Conflict:** Task assumes frontend modules for intent, KB, context, recommendation, response. The app is backend-driven; adding the suggested frontend files would duplicate logic and risk inconsistency.

**Recommendation:** Do **not** add `frontend/src/chat/` with intentResolver, knowledgeBase, contextManager, recommendationEngine, responseBuilder. Keep the current backend-based structure. If desired, document the backend modules as the canonical implementation (see Deliverables below).

---

## 13. Deliverables (where things are)

| Deliverable | Location |
|-------------|----------|
| **Files created/modified (for this upgrade)** | Largely already present. Remaining: (1) optional welcome text change in `SupportChatWidget.js`, (2) optional reset-by-text in `SupportChatWidget.js`, (3) optional `human_support` intent in `support_chatbot.py` for task wording. |
| **Knowledge base** | Backend: `backend/services/support_chatbot_knowledge.py` (`get_structured_qa()`). Used by `support_chatbot_retrieval.py` and by guided/canned flows. Not in frontend. |
| **Intent detection** | Backend: `support_chatbot.py` – `INTENTS` dict and `detect_intent(message)`. Problem layer: `PROBLEM_INTENTS`, `detect_problem_intent`, `PROBLEM_TO_SOLUTION`. Request flow: `handle_chat_message` uses context + message to set/update intent. |
| **Conversation context** | Frontend: `SupportChatWidget.js` state `conversationContext`. Sent in `POST /support/chat` as `conversation_context`. Backend: merged and returned in `ChatResponse.conversation_context`. |
| **Recommendation logic** | Backend: `support_chatbot.get_recommendation(ctx)` and `build_recommendation_response(service_key, reason, ctx)`. Triggered after qualification (and portfolio_size for CVP). Actions from `_get_guided_actions(service_key)`. |
| **Reset conversation** | Frontend: `resetConversation()` clears state and restores welcome. Header button "Start new chat" calls it. Backend: no dedicated reset endpoint; new conversation is created when frontend sends no `conversation_id`. Text triggers for "reset"/"start over"/"new chat" not yet implemented. |
| **Clickable actions** | Backend returns `actions: [{ label, url }]` on relevant responses. Frontend `MessageBubble` renders them as links/buttons; `linkifyText` turns URLs in text into links. |
| **Onboarding flow** | Frontend: welcome + OnboardingOptionsPanel (5 options). Backend: qualification question + user_type_options; for CVP, portfolio_size question + options; then recommendation + actions. |
| **Direct knowledge answer** | User asks e.g. "How much is CVP?" → retrieval scores message + context → high-confidence match → `build_response_from_entry` + `get_actions_from_entry` → response + actions returned; frontend shows message + action buttons. |
| **Recommendation response** | User picks "Manage property compliance" → backend sets intent, asks "Are you a: Landlord / ...?" → user picks "Landlord" → backend asks portfolio size → user picks "1–2" → `get_recommendation` returns (compliance_vault_pro, reason) → `build_recommendation_response` + actions → frontend shows recommendation text + "See pricing", "Create account", etc. |
| **Reset behaviour** | User clicks "Start new chat" → `resetConversation()` → messages and context cleared, welcome message shown again. Typing "reset" currently does not trigger reset (gap above). |

---

## Summary: what’s implemented vs missing

| # | Feature | Status | Notes |
|---|---------|--------|--------|
| 1 | Conversation context memory | Done | Backend + frontend; pricing-in-context works. |
| 2 | Intent detection | Done | Backend; human_support intent added and routes to handoff. |
| 3 | Guided onboarding | Done | Welcome text updated to task wording. |
| 4 | Structured knowledge base | Done (backend) | Do not add frontend KB file. |
| 5 | Knowledge retrieval | Done | Thresholds, context boost, clarifying, escalation. |
| 6 | Context-aware recommendations | Done | By user_type, portfolio_size, intent. |
| 7 | Response format | Done | Intro, bullets, actions. |
| 8 | Clickable actions | Done | actions array + MessageBubble. |
| 9 | Reset / start new chat | Done | Button + text commands "reset"/"start over"/"new chat" trigger reset (frontend). |
| 10 | Quick actions | Done | All task actions + extras. |
| 11 | Human escalation | Done | After 2 fallbacks, handoff + clickable options. |
| 12 | File structure | Conflict | Keep backend-only; do not add frontend/src/chat/*. |

---

## Conflicting instructions and recommended approach

1. **Knowledge base in frontend vs backend**  
   - Task: frontend file (e.g. `knowledgeBase.ts`).  
   - Codebase: single backend KB.  
   - **Recommendation:** Keep backend as the only KB. Do not add a frontend knowledge file.

2. **Intent "human_support"**  
   - Task: list human_support as an intent.  
   - Codebase: handoff via `needs_human_handoff()` and HANDOFF_TRIGGERS.  
   - **Recommendation:** Either leave as-is (handoff path only) or add `human_support` to `INTENTS` and route it into the same handoff path for consistency with task wording.

3. **Welcome message**  
   - Task: "Hello, welcome to Pleerity. What are you trying to do today?"  
   - Current: "Tell me what you're trying to solve..."  
   - **Recommendation:** Update to task wording in `SupportChatWidget.js` only.

4. **Reset by text**  
   - Task: "reset", "start over", "new chat" trigger reset.  
   - Current: only header button.  
   - **Recommendation:** In frontend, before send, if trimmed message matches these phrases, call `resetConversation()` and do not send to backend.

5. **File structure (frontend chat modules)**  
   - Task: suggests several frontend TS files for chat logic.  
   - Codebase: backend-driven; no frontend chat folder.  
   - **Recommendation:** Do not add frontend intent/KB/context/recommendation/response modules; keep and extend the existing backend structure.

---

## Safe, minimal changes (if you choose to implement)

- **Welcome text:** Done. `WELCOME_MESSAGE` in `SupportChatWidget.js` set to `Hello, welcome to Pleerity. What are you trying to do today?`
- **Reset by text:** Done. In `sendMessage`, if trimmed input matches `/^(reset|start over|new chat)$/i`, `resetConversation()` is called and the message is not sent.
- **human_support intent:** Done. `human_support` added to `INTENTS`; when detected, handoff response is returned and `ctx["intent"] = "human_support"` is set.

No further changes were required; the rest was already implemented.
