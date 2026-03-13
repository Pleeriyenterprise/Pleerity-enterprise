# Support Assistant Upgrade – Audit and Deliverables

## 1. Files Modified

| File | Changes |
|------|--------|
| `backend/services/support_chatbot.py` | Added INTENTS, detect_intent(), get_guided_knowledge(), build_guided_response(), ESCALATION_*; extended handle_chat_message with conversation_context, intent-based guided responses, and escalation after 2 fallbacks; added "pricing" canned response; reordered get_all_quick_actions(). |
| `backend/routes/support.py` | ChatRequest/ChatResponse extended with conversation_context; chat endpoint passes conversation_context to handle_chat_message and returns updated context; quick-action endpoint returns conversation_context and maps action_id → intent. |
| `frontend/src/components/SupportChatWidget.js` | Added conversationContext state and resetConversation(); send/receive conversation_context in /support/chat and quick-action responses; "Start new chat" in header and "Start New Chat" in quick actions; updated welcome message; quick actions reordered (CVP, Document Packs, Pricing, Reset Password, Talk to Support, Check Order, Billing, Start New Chat). |

## 2. Intent Detection Module

**Location:** `backend/services/support_chatbot.py`

- **INTENTS** – Mapping of intent keys to keyword lists:
  - `compliance_vault_pro`, `document_packs`, `automation`, `market_research`, `account_support`, `pricing`
- **detect_intent(message)** – Returns the first matching intent key or `None`. Used to set `conversation_context.intent` and to choose guided responses.

## 3. Knowledge Base Structure

**Location:** `backend/services/support_chatbot.py` – **get_guided_knowledge()**

Structure (per intent):

- **description** – One-line intro.
- **features** – List of bullet points.
- **actions** – List of (label, url) for “What would you like to do?” (url `None` = ask in chat).
- **pricing** – Optional; used for CVP/pricing intents (from plan_registry + FRONTEND_BASE).

Intents with guided entries: `compliance_vault_pro`, `document_packs`, `automation`, `market_research`, `account_support`, `pricing`.

## 4. Conversation State Logic

- **Client:** `conversationContext` = `{ intent, topic, last_action }`. Sent with every `POST /support/chat`; updated from response `conversation_context`.
- **Server:** Receives optional `conversation_context`; runs intent detection on the current message; updates context (e.g. sets `intent` when keywords match); uses context for short follow-ups (e.g. “pricing” when `intent` is already set); returns updated `conversation_context` in the response.
- **Reset:** “Start new chat” (header) or “Start New Chat” (quick action) clears messages, sets `conversationId` to `null`, and resets `conversationContext` to `{ intent: null, topic: null, last_action: null }`. Next message creates a new conversation; welcome message is shown again.

## 5. Reset Conversation Implementation

- **Header:** “Start new chat” button (visible when not minimized) calls `resetConversation()`.
- **Quick actions:** “Start New Chat” button (when `onReset` is passed) calls `resetConversation()`.
- **resetConversation():** Sets `conversationId` to `null`, `messages` to `[]`, `conversationContext` to `{ intent: null, topic: null, last_action: null }`, and clears handoff/ticket UI; existing `useEffect` then repopulates the single welcome message.

## 6. Updated Assistant Response Logic

- **Legal / handoff:** Unchanged; responses include `conversation_context` in the return payload.
- **Intent + guided:** If the message matches an intent in INTENTS and that intent exists in get_guided_knowledge(), the reply is **build_guided_response(intent)** (intro + features + pricing if present + next actions). Context is updated (`intent`, `topic`, `last_action`).
- **Follow-up “pricing”:** If the message is pricing-like (“pricing”, “price”, “how much”, etc.) and `conversation_context.intent` is set and in get_guided_knowledge(), reply is guided for that intent (so e.g. “CVP” then “pricing” returns CVP pricing).
- **Escalation:** If the last N bot messages in history are fallback (unmatched, not guided/FAQ/legal), next reply is **ESCALATION_MESSAGE** and `action: "handoff"` so the client shows live chat / email / WhatsApp.
- **Otherwise:** Existing AI/fallback path; context is still updated and returned.

## 7. Quick Actions

- **Compliance Vault Pro** → `cvp_info`  
- **Document Packs** → `document_packs_info`  
- **Pricing** → `pricing` (guided pricing response)  
- **Reset Password** → `reset_password`  
- **Talk to Support** → `speak_to_human` (handoff)  
- **Check Order Status** → `check_order_status`  
- **Billing Help** → `billing_help`  
- **Start New Chat** → client-only; calls `resetConversation()`.

## 8. Welcome Message

Shown on first load and after reset:

```
Hello! I'm the Pleerity assistant.

I can help you with:
* Compliance Vault Pro
* Document Packs
* AI Automation
* Market Research
* Account support

What would you like help with today?
```

## 9. Escalation

After **2** consecutive bot replies that are fallback (no intent match, not FAQ, not legal), the next reply is:

“I may need a human team member to help with that. Would you like to contact support? …” with options for Live Chat, Email, WhatsApp. The response has `action: "handoff"` so the widget shows the existing handoff UI.

## 10. Conflicts / Design Choices

- **No UI redesign** – Only extended state, header button, welcome text, and quick action list; no layout or visual redesign.
- **Context on client** – Context is kept in the widget and sent each turn; not stored in the DB, so reset is instant and no schema change.
- **Guided vs AI** – If intent matches, we use the guided response first; otherwise we keep using the existing AI/fallback path so behaviour is backward compatible.
