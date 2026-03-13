# Chat Assistant – Onboarding & Qualification (Task vs Codebase Audit)

## Goal (task)

Turn the chat widget into a **support + lead qualification** assistant with:

1. On-open welcome + quick options that set intent  
2. Qualification step (e.g. “Are you a: Landlord / Property manager / Letting agency / Just exploring”) → store `user_type`  
3. Recommendation step (intent + user_type → recommend service + next actions)  
4. Conversion options (See pricing, Create account, Check your compliance risk, Ask a question)  
5. Lead capture (“Would you like us to send you more information by email?” + email input)  
6. Conversation reset (Start new chat)  
7. Preserve existing chat UI; extend logic only  

---

## 1. What’s Already Implemented

| Task item | Current implementation | Notes |
|-----------|-------------------------|------|
| **Conversation context** | `conversationContext`: `{ intent, topic, last_action }` in widget; sent/returned by `/support/chat` and quick-action. | No `user_type` or onboarding `step` yet. |
| **Intent detection** | `INTENTS` map + `detect_intent()` in `support_chatbot.py`; context updated when message or quick action matches. | Intents: compliance_vault_pro, document_packs, automation, market_research, account_support, pricing. |
| **Quick options** | Quick actions panel: CVP, Document Packs, Pricing, Reset Password, Talk to Support, Check Order, Billing, Start New Chat. Selecting calls backend and sets `conversation_context.intent`. | Wording differs from task (“Manage property compliance” vs “Compliance Vault Pro”). No “Automate workflows” / “Get market research” as primary labels. |
| **Recommendation step** | `build_guided_response(intent)` returns intro + features + pricing + “What would you like to do?” with actions (See pricing, Create account, Ask a question). | Not tailored by `user_type`. No “Check your compliance risk” link yet. |
| **Conversion-style actions** | Guided actions include “See pricing”, “Create account”, “Ask a question” with `FRONTEND_BASE` URLs. | “Check your compliance risk” not in actions; site has `/risk-check`. |
| **Conversation reset** | “Start new chat” in header + “Start New Chat” in quick actions; `resetConversation()` clears messages, `conversationId`, and `conversationContext`. | Matches task. |
| **Lead capture backend** | `POST /api/leads/capture/chatbot` accepts email, name, phone, service_interest, conversation_id, marketing_consent, UTM. Creates lead and can send acknowledgement. | Ready for widget to call when user accepts “send more info by email”. |
| **Welcome message** | Single bot message on open/reset: “Hello! I'm the Pleerity assistant. I can help you with: * Compliance Vault Pro * … What would you like help with today?” | Different from task (“Hello, welcome to Pleerity. What are you trying to do today?” + 5 options). |

---

## 2. Gaps (Not Implemented)

| # | Gap | Required change |
|---|-----|------------------|
| 1 | **On-open welcome and options** | Use task wording: “Hello, welcome to Pleerity. What are you trying to do today?” and show exactly 5 options: **Manage property compliance**, **Get landlord documents**, **Automate workflows**, **Get market research**, **Contact support**. Selecting one should set `conversation_context.intent` (and optionally move to qualification). |
| 2 | **Qualification step** | After first selection (when relevant, e.g. compliance): ask “Are you a: Landlord / Property manager / Letting agency / Just exploring”. Store choice in `conversation_context.user_type`. Backend must support `user_type` in context and return a “qualification_question” or next step when `intent` set and `user_type` missing. |
| 3 | **Recommendation by intent + user_type** | Recommendation text should be driven by intent and, when present, `user_type` (e.g. “As a landlord, we recommend Compliance Vault Pro”). Backend: extend `build_guided_response` or add a small recommendation layer that uses intent + user_type. |
| 4 | **“Check your compliance risk”** | Add to conversion actions for compliance intent: link to `/risk-check` (or `FRONTEND_BASE/risk-check`). |
| 5 | **Lead capture in widget** | When to show: e.g. after recommendation and user has not converted (e.g. 1–2 exchanges without “See pricing” / “Create account” / “Check your compliance risk”). Bot message: “Would you like us to send you more information by email?” If yes, show email input; on submit call `POST /api/leads/capture/chatbot` with email, `service_interest` from intent, `conversation_id`, and optional marketing_consent. Then confirm in chat. |
| 6 | **`user_type` and onboarding step in context** | Backend and frontend: add `user_type` (and optionally `onboarding_step`: `welcome` | `qualification` | `recommendation` | `conversion` | `lead_capture`) to `conversation_context` so the flow can branch correctly. |

---

## 3. Conflicts and Choices

- **Two welcome texts**  
  - **Current:** “Hello! I'm the Pleerity assistant. I can help you with: * Compliance Vault Pro * Document Packs * …”  
  - **Task:** “Hello, welcome to Pleerity. What are you trying to do today?” + 5 options.  
  - **Choice:** Use the task wording and the 5 options for the **onboarding** path. Keep existing quick actions available after the first reply (or in a “More options” area) so support (Reset Password, Billing, etc.) is still there.

- **When to ask qualification**  
  - Task: “After the first selection, ask a follow-up when relevant” (e.g. for compliance: “Are you a: Landlord / …”).  
  - **Choice:** Only for intents where we have a clear recommendation (e.g. compliance → CVP; document_packs → Document Packs). For “Contact support” or “Just exploring”, skip qualification and go to recommendation or handoff.

- **Lead capture trigger**  
  - Task: “If the user asks for more information but does not sign up, offer to capture email.”  
  - **Choice:** Define “does not sign up” as: after we’ve shown the recommendation and conversion options, and the user has sent 1–2 messages without clicking a conversion link (we can’t detect clicks; so “after recommendation + N user messages without a conversion intent” or after a generic “tell me more” style message). Keep it simple: e.g. after showing recommendation, if the next user message is not “pricing” / “create account” / “risk check”, optionally show the email capture prompt once.

---

## 4. Proposed Implementation (Safest – Extend Only)

- **Backend (`support_chatbot.py` + `support.py`)**  
  - Extend `conversation_context` with `user_type` and optionally `onboarding_step`.  
  - Add qualification question texts and choices per intent (e.g. compliance: Landlord, Property manager, Letting agency, Just exploring).  
  - In `handle_chat_message`: if context has `intent` and no `user_type` and intent is “compliance” (and optionally others), return a response that asks the qualification question and set a step so the next user message is treated as `user_type` (or map it from keywords).  
  - Add “Check your compliance risk” to the compliance (and optionally pricing) guided actions with `FRONTEND_BASE/risk-check`.  
  - Add a small recommendation helper that, given intent + user_type, returns a one-line recommendation (e.g. “As a landlord, we recommend Compliance Vault Pro”) and reuse existing `build_guided_response` for the rest.  
  - Do not remove existing behaviour: keep intent detection, guided responses, escalation, and handoff as they are.

- **Frontend (`SupportChatWidget.js`)**  
  - Change the welcome message to the task text and, when `messages.length === 0`, show the 5 options as buttons that set intent (same as current quick actions but with the 5 labels; can reuse `handleQuickAction` with mapping: Manage property compliance → cvp_info, Get landlord documents → document_packs_info, Automate workflows → new or existing automation action, Get market research → new or existing market_research action, Contact support → speak_to_human).  
  - When the bot response includes a “qualification_question” (or a known “ask user type” step), show 4 buttons: Landlord, Property manager, Letting agency, Just exploring; on click send a message or trigger an action that sets `user_type` and request the next response (recommendation).  
  - Add lead-capture state: show “Would you like us to send you more information by email?” when backend sends a flag or after a simple heuristic (e.g. after recommendation and one more user reply). If user accepts, show email input; on submit call `POST /api/leads/capture/chatbot` with email, service_interest from context, conversation_id; then show a confirmation message.  
  - Keep “Start new chat” and `resetConversation()` as they are.  
  - Do not redesign the UI: same layout, same message bubble and input; only add the new welcome, qualification buttons, and email capture block when needed.

- **Lead capture API**  
  - Use existing `POST /api/leads/capture/chatbot`; ensure `service_interest` is sent from `conversation_context.intent` (map to existing enum: cvp, document packs, automation, market research). No backend change required if mapping is done in the frontend.

---

## 5. Files to Touch (When Implementing)

| File | Changes |
|------|--------|
| `backend/services/support_chatbot.py` | Add `user_type` (and optionally `onboarding_step`) to context; add qualification questions and choices per intent; handle “user type” message and return recommendation; add “Check your compliance risk” to compliance actions; optional small recommendation-by-user_type helper. |
| `backend/routes/support.py` | Ensure `conversation_context` in request/response can carry `user_type` (and optional `onboarding_step`); no schema change if we keep context as a free-form dict. |
| `frontend/src/components/SupportChatWidget.js` | New welcome text and 5 onboarding options; handle qualification step (show 4 buttons, send selection, set `user_type`); add lead-capture prompt + email input + call to `POST /api/leads/capture/chatbot`; keep reset and existing quick actions. |

---

## 6. New Conversation Flow (Summary)

1. **Open / reset** → Show: “Hello, welcome to Pleerity. What are you trying to do today?” and 5 options.  
2. **User picks an option** → Set `intent`; for compliance (and optionally others), go to step 3; else go to step 4.  
3. **Qualification** → Bot: “Are you a: Landlord / Property manager / Letting agency / Just exploring?” User picks → set `user_type`; go to step 4.  
4. **Recommendation** → Bot recommends service (intro + features + conversion options including “Check your compliance risk” for compliance).  
5. **Conversion options** → User can click/link to See pricing, Create account, Check your compliance risk, or Ask a question (existing handoff).  
6. **Lead capture** → If user doesn’t convert and we decide to offer (e.g. after one more message): “Would you like us to send you more information by email?” → If yes, show email input → submit to `/api/leads/capture/chatbot` → confirm.  
7. **Start new chat** → Clears history and context; show welcome again (step 1).  

Existing support behaviour (free-text chat, FAQ, handoff, escalation) remains; the onboarding flow is an extension that runs when the user is in the “welcome” or “qualification” or “recommendation” path.

---

## 7. Status

- **Audit:** Done.  
- **Implementation:** Done. Backend: `user_type`, `onboarding_step`, `lead_capture_offered` in context; qualification question for compliance intent; recommendation intro by user_type; "Check your compliance risk" in CVP and pricing actions; lead capture offer after recommendation. Frontend: onboarding welcome + 5 options; qualification 4 buttons; lead capture block with email submit to `/api/leads/capture/chatbot`.
