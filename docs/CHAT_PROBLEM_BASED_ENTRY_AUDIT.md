# Chat Assistant – Problem-Based Entry Detection (Task vs Codebase Audit)

## Goal (task)

Make the assistant feel more intelligent by **detecting the user’s underlying problem** within the first message or two, then recommending the right Pleerity service.

---

## 1. Task Requirements Summary

1. **Problem-intent detection layer** before product recommendation: compliance_risk, missing_documents, workflow_overload, account_access_issue, pricing_interest, exploration, support_need.
2. **Lightweight keyword/phrase mappings** for each problem intent (e.g. "forgetting certificates", "expiry", "compliance" → compliance_risk).
3. **Store** detected problem intent in conversation context (e.g. `conversationContext.problem_intent = "compliance_risk"`).
4. **Map** problem intents to recommended solutions: compliance_risk → CVP, missing_documents → Document Packs, workflow_overload → AI Automation, account_access_issue → Account support, exploration → onboarding/overview.
5. **Update first assistant message**: "Tell me what you're trying to solve, and I'll point you to the right option." with free type or guided quick option.
6. **Recommendation responses** must include: short diagnosis of the user’s likely need, recommended service, short reason, clickable next actions.
7. **Do not remove** existing intent detection, knowledge base, or onboarding flow; layer problem-intent detection on top.
8. **Deliverables**: files modified, problem intent definitions, context fields, problem→solution mapping, example conversations.

---

## 2. Current Implementation

### Intent layer (product-level)

| Item | Implementation |
|------|----------------|
| **Intent detection** | `INTENTS` in `support_chatbot.py`: product-oriented keys (compliance_vault_pro, document_packs, automation, market_research, account_support, pricing). Keywords map **directly to product** (e.g. "expiry", "compliance", "certificate" → compliance_vault_pro). |
| **Flow** | User message → `detect_intent(message)` → set `ctx["intent"]` → qualification (for CVP) or guided response / recommendation. No separate "problem" step. |
| **Context** | `ctx` has: intent, topic, last_action, user_type, onboarding_step, lead_capture_offered, portfolio_size, primary_goal, secondary_need. **No `problem_intent`.** |

### Opening and quick options

| Item | Implementation |
|------|----------------|
| **Welcome** | "Hello, welcome to Pleerity. What are you trying to do today?" (frontend `WELCOME_MESSAGE`). |
| **Quick options** | 5 onboarding options: Manage property compliance, Get landlord documents, Automate workflows, Get market research, Contact support. Clicking sends a message that triggers product intent (or quick action for Contact support). |

### Recommendation format

| Item | Implementation |
|------|----------------|
| **Content** | "For [user_type], **[Service]** is likely the best fit because [reason]." + Key features + Pricing + clickable actions (via `actions` array). |
| **Diagnosis** | **No** explicit "diagnosis" line (e.g. "It sounds like you're concerned about compliance and renewals."). Reason is product-focused, not problem-focused. |

### Knowledge base and onboarding

- **Structured KB retrieval**: Present; used when no strong product intent match.
- **Onboarding**: Welcome + 5 options, qualification (user type), portfolio size (compliance), recommendation, lead capture. Present and unchanged by this task.

---

## 3. Gaps vs Task

| Requirement | Current | Gap |
|-------------|---------|-----|
| **1. Problem-intent layer** | Only **product** intents exist; no compliance_risk, missing_documents, workflow_overload, etc. | Add a **problem-intent** layer with its own keywords and `detect_problem_intent(message)` that runs **before** or alongside product intent. |
| **2. Keyword mappings for problems** | Product keywords (e.g. "expiry", "compliance") map to compliance_vault_pro. | Add **problem** keywords/phrases (e.g. "forgetting certificates", "renewal", "compliance" → compliance_risk; "tenancy agreement", "documents" → missing_documents) in a separate structure. |
| **3. problem_intent in context** | Not stored. | Add `ctx["problem_intent"]` and set it when problem detection fires; frontend to include in `conversationContext` and send/receive with API. |
| **4. Map problem → solution** | No mapping. Recommendation uses `intent` (product) only. | Add **PROBLEM_TO_SOLUTION** (e.g. compliance_risk → compliance_vault_pro, missing_documents → document_packs). When problem_intent is set, derive or set `intent` from this map so existing recommendation/qualification flow runs unchanged. |
| **5. Opening message** | "What are you trying to do today?" | Task suggests: "Tell me what you're trying to solve, and I'll point you to the right option." Keep free type + guided quick options. |
| **6. Diagnosis in response** | We have reason + service + actions; no "diagnosis" line. | Add a short **diagnosis** line when `problem_intent` is set (e.g. "It sounds like you're dealing with compliance and renewal concerns.") before the existing recommendation sentence. |
| **7. Don’t remove existing** | N/A | No conflict; task says layer on top. Keep `detect_intent`, KB retrieval, onboarding as-is. |

---

## 4. Conflict and Recommended Approach

| Topic | Task / codebase | Recommendation |
|-------|------------------|----------------|
| **Two intent layers** | Task adds problem intents; codebase has product intents. | **Layer, don’t replace.** Run **problem detection first** on the user message. If `detect_problem_intent(message)` returns a value, set `ctx["problem_intent"]` and set `ctx["intent"] = PROBLEM_TO_SOLUTION[problem_intent]`. If problem detection returns nothing, keep current behaviour: run `detect_intent(message)` and set `ctx["intent"]` from that. So product intent can come from either (1) problem → solution map or (2) direct product keywords. Existing qualification, recommendation, and KB flows continue to use `intent`. |
| **Overlap in keywords** | "compliance", "expiry" could match both compliance_risk and compliance_vault_pro. | Use **separate** problem keywords (e.g. PROBLEM_INTENTS) and run problem detection first; only if no problem match do we run product detect_intent. That way "I keep forgetting certificate renewals" → compliance_risk → CVP, and "I need CVP" → no problem match → product intent compliance_vault_pro. |
| **Opening message** | Current: "What are you trying to do today?" Task: "Tell me what you're trying to solve, and I'll point you to the right option." | **Update** the first bot message to the task wording. Keep the same 5 quick options (they remain guided entry points; backend can still map their messages to product or problem as needed). |

---

## 5. Proposed Implementation (Safe, Additive)

### Backend

1. **Problem intents**
   - Define `PROBLEM_INTENTS`: dict mapping problem_key → list of keywords/phrases.
     - compliance_risk: e.g. "forgetting certificates", "expiry", "compliance", "renewal", "certificate expired", "track certificates", "compliance risk"
     - missing_documents: e.g. "tenancy agreement", "documents", "forms", "need documents", "missing documents", "ast", "landlord documents"
     - workflow_overload: e.g. "too much admin", "automation", "workflow", "repetitive", "streamline", "admin burden"
     - account_access_issue: e.g. "login", "reset password", "can't access", "forgot password", "locked out", "sign in"
     - pricing_interest: e.g. "pricing", "how much", "cost", "plans", "price"
     - exploration: e.g. "exploring", "just looking", "not sure", "options", "what do you offer"
     - support_need: e.g. "speak to someone", "human", "support", "help", "contact"
   - Add `detect_problem_intent(message) -> Optional[str]` (same style as detect_intent: keyword match, return first match or None).

2. **Problem → solution**
   - Define `PROBLEM_TO_SOLUTION`: compliance_risk → compliance_vault_pro, missing_documents → document_packs, workflow_overload → automation, account_access_issue → account_support, pricing_interest → pricing, exploration → pricing (or keep as onboarding), support_need → account_support (or handoff). Use keys that match `get_guided_knowledge()` so existing flows work.

3. **Context**
   - In `handle_chat_message`, set `ctx.setdefault("problem_intent", None)`. When processing the message, run `detect_problem_intent(message)` first. If result is non-None, set `ctx["problem_intent"] = result` and, if we don’t already have an intent (or for first message), set `ctx["intent"] = PROBLEM_TO_SOLUTION.get(result)` so downstream qualification/recommendation runs unchanged.

4. **Diagnosis line**
   - Add a small map `PROBLEM_DIAGNOSIS`: problem_intent → short diagnosis sentence (e.g. compliance_risk → "It sounds like you're concerned about compliance and certificate renewals."). When building the recommendation response, if `ctx.get("problem_intent")` is set, prepend the diagnosis line (and a blank line) before the existing "For [user_type], **[Service]** is likely the best fit because …".

5. **Order of operations**
   - Early in the handler (after legal/handoff): run problem detection. If problem_intent found and intent not set (or message is one of the first), set problem_intent and intent from map. Then continue with existing logic (qualification, pricing follow-up, intent detection). If problem detection found something we can still run product detect_intent and allow it to override when the user is more product-specific (optional; or keep problem-only when problem_intent is set to avoid overwriting). Safest: when problem_intent is set, set intent from map and **do not** overwrite intent with product detect_intent on the same turn; on later turns product intent can still update (e.g. user says "pricing" later).

### Frontend

1. **Context**
   - Add `problem_intent` to `conversationContext` state and to reset. Send and receive it in the existing `conversation_context` API payload (no schema change if context is a free-form object).

2. **Opening**
   - Change `WELCOME_MESSAGE` to: "Tell me what you're trying to solve, and I'll point you to the right option." Keep the same 5 onboarding options below.

### Files to Touch (when implementing)

| File | Changes |
|------|--------|
| `backend/services/support_chatbot.py` | Add PROBLEM_INTENTS, detect_problem_intent(), PROBLEM_TO_SOLUTION, PROBLEM_DIAGNOSIS. In handle_chat_message: set ctx.problem_intent and ctx.intent from problem when applicable; prepend diagnosis line in recommendation when problem_intent set. |
| `frontend/src/components/SupportChatWidget.js` | Add problem_intent to conversationContext; change WELCOME_MESSAGE to task wording. |

### Example conversations (after implementation)

1. **compliance_risk** – User: "I keep forgetting when my certificates expire." → problem_intent = compliance_risk, intent = compliance_vault_pro → qualification (user type, portfolio size) → "It sounds like you're concerned about compliance and certificate renewals. For a landlord, **Compliance Vault Pro** is likely the best fit because …" + actions.
2. **missing_documents** – User: "I need a tenancy agreement and some forms." → problem_intent = missing_documents, intent = document_packs → "It sounds like you need landlord documents. **Document Packs** is likely the best fit because …" + actions.
3. **workflow_overload** – User: "Too much admin, need to automate." → problem_intent = workflow_overload, intent = automation → recommendation + actions.
4. **account_access_issue** – User: "I can't log in." → problem_intent = account_access_issue, intent = account_support → account support flow + actions.
5. **pricing_interest** – User: "How much does it cost?" → problem_intent = pricing_interest, intent = pricing → pricing response + actions.
6. **exploration** – User: "Just exploring options." → problem_intent = exploration → intent = pricing → overview/pricing + actions.
7. **support_need** – User: "I want to speak to someone." → problem_intent = support_need → handoff or account_support flow.

---

## 6. Status

- **Audit:** Complete.
- **Implementation:** Done. Backend: PROBLEM_INTENTS, detect_problem_intent(), PROBLEM_TO_SOLUTION, PROBLEM_DIAGNOSIS; problem detection runs first and sets ctx.problem_intent and ctx.intent from map; product detect_intent only updates intent when problem_intent not set; diagnosis line prepended to recommendation responses when problem_intent set. Frontend: problem_intent in conversationContext and reset; WELCOME_MESSAGE updated to "Tell me what you're trying to solve, and I'll point you to the right option."
