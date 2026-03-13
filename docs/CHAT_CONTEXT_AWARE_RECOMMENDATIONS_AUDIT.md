# Chat Assistant – Context-Aware Recommendations (Task vs Codebase Audit)

## Goal (task)

Upgrade the website chat assistant so it **recommends the most relevant Pleerity service** based on what the visitor has already said.

---

## 1. Task Requirements Summary

1. **Extend conversation state** with: intent, user_type, portfolio_size, primary_goal, secondary_need.
2. **Lightweight recommendation logic** – e.g. landlord + compliance + 1_2_properties → CVP; landlord + documents → Document Packs; agency + automation → AI Automation; exploring → overview/demo/pricing.
3. **Follow-up questions** when needed before recommending.
4. **Response format**: short recommendation + reason for recommendation + clickable next actions (label + url, no raw URLs in text).
5. **No raw URLs in chat text** – render actions as clickable links/buttons (label + url).
6. **Keep** current onboarding flow and knowledge retrieval; add recommendation logic on top.
7. **Deliverables**: files modified, new context fields, recommendation logic, example paths.

---

## 2. Current Implementation

### Conversation state (context)

| Field | Backend | Frontend | Notes |
|-------|---------|----------|--------|
| **intent** | ✅ `ctx["intent"]` set from detect_intent / quick action | ✅ `conversationContext.intent` sent and updated from API | Present. |
| **user_type** | ✅ `ctx["user_type"]` set after qualification (Landlord / Property manager / Letting agency / Just exploring) | ✅ `conversationContext.user_type` in state and sent to API | Present. |
| **portfolio_size** | ❌ Not stored | ❌ Not in state | **Missing.** |
| **primary_goal** | ❌ Not stored | ❌ Not in state | **Missing.** |
| **secondary_need** | ❌ Not stored | ❌ Not in state | **Missing.** |
| **topic** | ✅ `ctx["topic"]` (mirrors intent) | ✅ in context | Present. |
| **last_action** | ✅ e.g. intent_set, guided, recommendation, qualification | ✅ in context | Present. |
| **onboarding_step** | ✅ welcome / qualification / recommendation | ✅ in context | Present. |
| **lead_capture_offered** | ✅ boolean | ✅ in context | Present. |

### Recommendation logic

| Task example | Current behaviour | Gap |
|--------------|-------------------|-----|
| **landlord + compliance + 1_2_properties → CVP** | We have: intent compliance_vault_pro + user_type landlord → we show `recommendation_intro_by_user_type` ("As a landlord, we recommend **Compliance Vault Pro**.") + guided response. We do **not** ask or use portfolio_size. | No **portfolio_size**; no rule that explicitly maps (user_type, intent, portfolio_size) → service. Recommendation is effectively intent + user_type only for CVP. |
| **landlord + documents → Document Packs** | Intent document_packs → we return `build_guided_response("document_packs")` with no user_type-based intro or “recommendation” framing. We do not ask user_type for document_packs. | No recommendation layer for document_packs (no “As a landlord, Document Packs are a good fit because…”). |
| **agency + automation → AI Automation consultation** | Intent automation → we return guided response. No user_type asked or used for automation. | No agency-specific recommendation or “consultation” framing. |
| **exploring → overview, demo, or pricing** | user_type "exploring" is set from qualification (only for compliance flow). We don’t have a dedicated “exploring” path that recommends overview/demo/pricing. | No explicit “exploring” branch that recommends overview/demo/pricing. |

**Current recommendation surface:** `recommendation_intro_by_user_type(intent, user_type)` exists **only for intent == "compliance_vault_pro"** and returns a one-line intro. No central “recommendation engine” that takes (intent, user_type, portfolio_size, primary_goal, secondary_need) and returns (recommended_service, reason, actions).

### Follow-up questions

| Task | Current | Gap |
|------|---------|-----|
| Ask follow-ups when needed before recommending | We have **one** follow-up: for compliance_vault_pro we ask “Are you a: Landlord / Property manager / Letting agency / Just exploring?” and then recommend. | We do **not** ask “How many properties?” (portfolio_size) or “What’s your main goal?” (primary_goal) or secondary need. No second/third follow-up step. |

### Response format

| Task | Current | Gap |
|------|---------|-----|
| Short recommendation | ✅ For CVP we prepend a one-line intro (e.g. “As a landlord, we recommend **Compliance Vault Pro**.”). | For other intents we don’t use a “recommendation” sentence; we go straight to description/features. |
| Reason for recommendation | Partially: we show “Key features:” and list. Not phrased as “because…” (e.g. “because it helps track certificates, reminders, and compliance records in one place”). | **Missing** explicit “reason” line in the task’s format. |
| Clickable next actions (label + url) | ✅ Implemented: backend returns `actions: [{ label, url }]`; frontend renders as button-style links; no raw URLs in action block. | Satisfied. |
| No raw URLs in text | ✅ When `actions` is present we trim the “What would you like to do?” and numbered URL lines from the response text. | Satisfied. |

### Onboarding and knowledge retrieval

- **Onboarding**: Welcome + 5 options, qualification (user type) for compliance, recommendation, lead capture, reset. ✅ Kept.
- **Knowledge retrieval**: Structured KB retrieval with threshold, clarifying, fallback. ✅ Kept.
- **Conflict**: None; task says add recommendation logic **on top** of these. ✅

---

## 3. Gaps Summary

| # | Gap | Required change |
|---|-----|------------------|
| 1 | **Context fields** | Add to conversation_context (backend + frontend): **portfolio_size** (e.g. 1_2_properties, 3_10, 10_plus, unknown), **primary_goal** (e.g. compliance, documents, automate, research, support), **secondary_need** (optional). |
| 2 | **Recommendation logic** | Add a small recommendation layer: input (intent, user_type, portfolio_size, primary_goal, secondary_need) → output (recommended_service_key, short_reason). Use it when building the response so we return “short recommendation + reason + actions” instead of only guided description. Extend to document_packs, automation, market_research, exploring (not only CVP). |
| 3 | **Follow-up questions** | When context is missing fields needed for a better recommendation (e.g. portfolio_size for compliance), ask one follow-up (e.g. “How many properties do you manage?” with options 1–2, 3–10, 10+) and store the answer before recommending. Optional: primary_goal / secondary_need if we want to ask “What’s your main goal?”. |
| 4 | **Reason in response** | Ensure recommendation response includes an explicit “because…” line (e.g. “For a landlord managing 1–2 properties, Compliance Vault Pro is likely the best fit because it helps track certificates, reminders, and compliance records in one place.”) then features/actions. |
| 5 | **Exploring path** | When user_type is “exploring” (or no clear intent), recommend overview/demo/pricing and return actions for those (e.g. See pricing, Learn more, Book a demo). |

---

## 4. Conflicts and Safest Options

| Topic | Task / codebase | Recommendation |
|-------|------------------|----------------|
| **Portfolio size values** | Task suggests “1_2_properties” etc. | Use a small fixed set: e.g. `1_2`, `3_10`, `10_plus`, `unknown`. Store in context; use in recommendation rules only when present. If we don’t ask, leave `unknown` or omit. |
| **When to ask follow-ups** | Task: “when needed before making a recommendation”. | Ask portfolio_size only for **compliance_vault_pro** (and optionally document_packs) to avoid long flows. For automation/market_research, current “no extra follow-up” is acceptable unless we add optional “primary_goal” later. |
| **Recommendation vs guided** | We already have guided responses and CVP recommendation intro. | **Add** a single recommendation step: (1) If we have enough context (intent + user_type and optionally portfolio_size), call a `get_recommendation(context)` that returns (service_key, reason). (2) Build response as: recommendation sentence + reason + existing guided content (description/features) + actions. Do **not** remove onboarding or retrieval; recommendation is an extra layer before/around guided response. |
| **primary_goal / secondary_need** | Task suggests these fields. | **Option A:** Add fields to context and set them only when we have a clear signal (e.g. primary_goal = intent when intent is set). **Option B:** Add fields and optionally ask “What’s your main goal?” as a follow-up for exploring or when intent is ambiguous. Safest: add fields to context, derive primary_goal from intent when possible; add follow-up only for 1–2 high-value paths (e.g. compliance portfolio_size). |

---

## 5. Proposed Implementation (Safe, Additive)

### Backend

1. **Context**
   - In `handle_chat_message`, extend `ctx` with:
     - `portfolio_size`: None | "1_2" | "3_10" | "10_plus" | "unknown"
     - `primary_goal`: None or same as intent when intent is set
     - `secondary_need`: None or optional string
   - Detect portfolio_size from message when possible (e.g. “1 or 2”, “couple of properties” → 1_2); otherwise set when user selects from a follow-up (e.g. buttons).

2. **Follow-up**
   - For **compliance_vault_pro** only (after user_type is set): if portfolio_size is missing, return a follow-up question: “How many properties do you manage?” with options (e.g. 1–2, 3–10, 10+) and set `metadata.follow_up = "portfolio_size"` and `metadata.portfolio_size_options = [...]`. On next message, if we’re in this follow-up, parse or match option → set ctx["portfolio_size"], then proceed to recommendation.

3. **Recommendation layer**
   - New helper: `get_recommendation(ctx) -> (service_key, reason)`:
     - landlord + compliance_vault_pro + (1_2 or 3_10 or unknown) → ("compliance_vault_pro", "it helps track certificates, reminders, and compliance records in one place")
     - landlord + document_packs → ("document_packs", "professional document packs for tenancies and compliance")
     - property_manager / letting_agency + compliance_vault_pro → ("compliance_vault_pro", "ideal for portfolio compliance")
     - letting_agency + automation → ("automation", "AI workflow automation for agency processes")
     - exploring (or no intent) → ("pricing" or "overview", "see our plans and book a demo")
     - Fallback: (intent or "pricing", generic reason)
   - When building the response after qualification (or when we have intent + user_type and no pending follow-up), call `get_recommendation(ctx)` and prepend “For [context], [Service] is likely the best fit because [reason].” (or similar). Then append existing guided content and actions.

4. **Response format**
   - Recommendation block: one short sentence + one “because” sentence. Then “Key features:” and actions as today (already clickable via actions array). No raw URLs in text.

5. **Files**
   - `support_chatbot.py`: extend ctx defaults; add portfolio_size follow-up branch; add `get_recommendation(ctx)`; use it in the recommendation/guided return paths. Optionally a small `support_chatbot_recommendation.py` for rules only.

### Frontend

1. **Context**
   - Add to `conversationContext` state: `portfolio_size`, `primary_goal`, `secondary_need` (null by default). Send and receive them in conversation_context from the API (backend already sends full context object).

2. **Follow-up**
   - When backend returns `metadata.follow_up === "portfolio_size"` and `metadata.portfolio_size_options`, show buttons (e.g. “1–2”, “3–10”, “10+”). On click, send that as the next message (or a dedicated payload) so backend sets portfolio_size and returns recommendation.

3. **No change** to action rendering (already clickable); no change to onboarding or retrieval.

### Deliverables (when implemented)

- Files modified: `backend/services/support_chatbot.py`, optionally `support_chatbot_recommendation.py`; `frontend/.../SupportChatWidget.js` (context fields + portfolio_size follow-up UI).
- New context fields: portfolio_size, primary_goal, secondary_need.
- Recommendation logic: `get_recommendation(ctx)` with rules for landlord/agency/exploring + intent + portfolio_size.
- Example paths: (1) Landlord → compliance → 1–2 properties → CVP recommendation + reason + actions. (2) Landlord → documents → Document Packs recommendation + reason + actions. (3) Agency → automation → AI Automation recommendation. (4) Exploring → overview/pricing recommendation.

---

## 6. Status

- **Audit:** Complete.
- **Implementation:** Done. Context extended with portfolio_size, primary_goal, secondary_need. get_recommendation(ctx) and build_recommendation_response(service_key, reason, ctx) added. Portfolio size follow-up for compliance (ask "How many properties?" after user type) with PortfolioSizeButtons in frontend. Recommendation + reason used in qualification, portfolio_size, explicit intent, and pricing follow-up paths. Frontend context state and reset updated; portfolio_size options rendered when metadata.follow_up === "portfolio_size".

### Example recommendation paths (after implementation)

1. **Landlord + compliance + 1–2 properties:** User picks "Manage property compliance" → "Landlord" → "1–2 properties" → Bot: "For a landlord, **Compliance Vault Pro** is likely the best fit because it helps you track certificates, reminders, and compliance records in one place—ideal for 1–2 properties." + Key features + Pricing + actions (See pricing, Create account, Check your compliance risk, Ask a question).
2. **Landlord + documents:** User picks "Get landlord documents" → Bot (if user_type already set): "For a landlord, **Document Packs** is likely the best fit because professional document packs for tenancies and compliance are a good fit for landlords." + features + actions.
3. **Agency + automation:** User picks "Automate workflows" and had previously said they're a letting agency (or we add qualification for automation) → "For a letting agency, **AI workflow automation** is likely the best fit because AI workflow automation can streamline agency processes and reporting." + features + actions.
4. **Exploring:** User picks "Just exploring" → Bot recommends pricing/overview: "For exploring, **our Pricing page** is likely the best fit because you can see our plans and book a demo to find the right fit." + actions.
