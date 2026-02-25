# Pleerity Assistant Hardening — Codebase Audit vs Task Requirements

**Purpose:** Identify what is implemented, what is missing, and any conflicts before implementing the “Harden Pleerity Assistant for safe, contextual portal guidance” task. No implementation is done in this audit; recommendations are for the safest, non-duplicative path.

---

## 1. Summary Table

| Requirement | Status | Notes |
|-------------|--------|--------|
| **Backend: assistant_session model** | **Conflict / Partial** | Task: `session_id, user_id, role, started_at, escalated, escalation_reason`. Current: `assistant_conversations` with `conversation_id, client_id, created_by_user_id, created_at, last_activity_at` — **no `escalated` or `escalation_reason`**. |
| **Backend: assistant_messages model** | **Partial** | Task: `session_id, sender: 'user'\|'assistant'\|'system', message, created_at`. Current: `assistant_messages` with `conversation_id, client_id, user_id, role, message, citations, safety_flags, model, prompt_version, created_at`. Same idea; different field names (`conversation_id` vs `session_id`, `role` vs `sender`). No `system` messages stored. |
| **POST /api/assistant/chat** | **Done** | Exists. Fetches portal context via `get_portal_facts` + KB via `get_kb_snippets`, LLM with strict system prompt, logs all messages. |
| **POST /api/assistant/escalate** | **Missing** | Not present. Task: mark session escalated, create support ticket, attach transcript, notify support dashboard. |
| **GET /api/assistant/context** | **Partial** | Task implies a context endpoint. Current: `GET /api/assistant/snapshot` returns client snapshot; chat flow uses `get_portal_facts` + `get_kb_snippets` inside `assistant_chat_service`. No standalone `/api/assistant/context`. |
| **Auto-escalation triggers** | **Missing** | Task: keywords (human, complaint, refund, legal, cancel), AI confidence &lt; threshold, billing topic. Not implemented in portal assistant flow. |
| **Frontend: “Escalated to human” / “Support joined”** | **Missing** | Portal AssistantPage has no escalation state UI. Support Chat Widget (separate) has handoff options but is not the portal assistant. |
| **Frontend: support online → live; offline → ticket + email** | **Partial** | Exists only in **Support Chat Widget** (Tawk, email ticket, WhatsApp). Portal Assistant does not offer handover or connect to this. |
| **RBAC: Support reads transcripts** | **Partial** | Admin uses `admin_route_guard` (all staff) and `require_owner_or_admin` on some routes. `/api/admin/assistant/history` uses `admin_route_guard` and reads **admin_assistant_queries** (old /ask), not **assistant_conversations/assistant_messages**. No dedicated “Support can read assistant chat transcripts” with role check. |
| **RBAC: Admin/Owner audit** | **Done** | Audit log: ASSISTANT_CHAT_REQUESTED, ASSISTANT_CHAT_RESPONDED, ASSISTANT_CHAT_REFUSED_LEGAL, ASSISTANT_CHAT_ERROR. Admin can access admin dashboard. |
| **No legal advice / strict system prompt** | **Done** | ASSISTANT_SPEC + assistant_chat_service: strict prompt, VERDICT_BLOCK_PATTERNS, safety_flags.legal_advice_request, audit on refusal. |
| **Assistant cannot modify records** | **Done** | Read-only: get_portal_facts, KB; no write to properties/documents/requirements from assistant. |
| **Chat transcript preserved and visible** | **Partial** | Messages stored in assistant_messages; no API for Support to list/read **chat** transcripts (only old admin_assistant_queries). |

---

## 2. Two Systems (Avoid Confusion)

| System | Where | Backend | Purpose |
|--------|--------|---------|--------|
| **Portal Assistant** | Authenticated portal (`/app/assistant` or similar), AssistantPage.js | `POST /api/assistant/chat`, assistant_conversations, assistant_messages, assistant_chat_service, assistant_retrieval_service | Context-aware portal guidance (score, requirements, documents). No human handover today. |
| **Support Chat Widget** | Public/marketing site, SupportChatWidget.js | support_conversations, support_tickets, support_chatbot.py, Tawk, POST /api/support/* | Pre-login support: FAQ, quick actions, human handoff (live chat, email ticket, WhatsApp). Has HANDOFF_TRIGGERS in support_chatbot. |

The task mixes “Portal Guidance” (inside portal) with “Chat widget shows Escalated / Support joined” and “support online/offline”. **Safest reading:** harden the **portal** assistant and add **escalation from portal assistant into the support system** (ticket + transcript), and show “Escalated to human” / “Support joined” in the **portal** assistant UI (not only in the public widget).

---

## 3. Schema / Naming Conflicts

- **Session vs conversation**  
  - Task: `assistant_session` with `session_id`.  
  - Current: `assistant_conversations` with `conversation_id`.  
  - **Recommendation:** Do **not** introduce a new `assistant_sessions` collection. Add `escalated: boolean` and `escalation_reason: optional string` to **assistant_conversations** (and optional `escalated_at`). Treat conversation_id as session_id for the task.

- **Messages: sender vs role**  
  - Task: `sender: 'user' | 'assistant' | 'system'`.  
  - Current: `role: "user" | "assistant"`.  
  - **Recommendation:** Keep `role`; add `system` only if you need to store system messages (e.g. “Conversation escalated to support”). No need to rename to `sender`.

- **Transcript for support**  
  - Task: “Attach full transcript” on escalate.  
  - Current: All messages in `assistant_messages` keyed by `conversation_id`.  
  - **Recommendation:** On escalate, build transcript from existing `assistant_messages` for that `conversation_id` and attach to the support ticket (reuse support ticket + transcript pattern from support_service).

---

## 4. Conflicting Instructions (Task vs Codebase)

- **Task:** “Create assistant_session model” with specific fields.  
  **Codebase:** assistant_conversations already exists and is used everywhere.  
  **Recommendation:** Extend assistant_conversations (escalated, escalation_reason, optionally escalated_at). Do not create a second session store.

- **Task:** “Create assistant_messages model” with session_id, sender, message, created_at.  
  **Codebase:** assistant_messages has more fields (citations, safety_flags, model, etc.) and uses conversation_id.  
  **Recommendation:** Keep current assistant_messages schema; ensure all messages are logged (already done). Add system messages only if needed for escalation.

- **Task:** “/api/assistant/context”.  
  **Codebase:** Context is fetched inside chat (get_portal_facts + get_kb_snippets). GET /api/assistant/snapshot exists but returns a different shape.  
  **Recommendation:** Either (a) document that “context” is embedded in /chat and snapshot is for optional UI use, or (b) add GET /api/assistant/context that returns the same payload the chat uses (portal_facts + kb_snippets for current user). Prefer (a) unless frontend needs context without sending a message.

- **Task:** “Chat widget shows Escalated / Support joined” and “If support online connect live; if offline create ticket + email”.  
  **Codebase:** Support **widget** (public) already has handoff; **portal** assistant has no escalation.  
  **Recommendation:** Implement escalation **in the portal assistant**: button or auto-trigger → POST /api/assistant/escalate → create support ticket with transcript, then in **AssistantPage** show “Escalated to human” and optionally “Support joined” (e.g. when ticket is acknowledged). “Support online” can mean: check support availability (e.g. Tawk or a simple flag) and in UI offer “Live chat” vs “Create ticket + email” from the same portal assistant screen.

---

## 5. What’s Implemented (No Duplication Needed)

- **Portal context in chat:** get_portal_facts (CRN, plan, subscription, properties, requirements, documents), get_kb_snippets (assistant_kb/*.md). Used in assistant_chat_service.
- **Strict system prompt:** CHAT_SYSTEM_PROMPT, no legal advice, cite sources, safety_flags.legal_advice_request.
- **Post-process guardrails:** VERDICT_BLOCK_PATTERNS, _rewrite_compliance_verdict_language.
- **Message persistence:** Every user and assistant message stored in assistant_messages with conversation_id, client_id, user_id, role, citations, safety_flags.
- **Audit:** ASSISTANT_CHAT_REQUESTED, ASSISTANT_CHAT_RESPONDED, ASSISTANT_CHAT_REFUSED_LEGAL, ASSISTANT_CHAT_ERROR.
- **Rate limiting:** Per user 20/10min, per client 100/day on /api/assistant/chat.
- **Frontend:** AssistantPage uses /api/assistant/chat, conversation_id, property_id, citations, safety_flags.legal_advice_request banner, disclaimer.
- **Admin chat:** POST /api/admin/assistant/chat with optional CRN; same chat_turn flow.

---

## 6. What’s Missing (Implement Here)

1. **Escalation on assistant_conversations**  
   - Add fields: `escalated: boolean` (default false), `escalation_reason: optional string`, optionally `escalated_at` (ISO).  
   - When escalate is called: set these, create support ticket, attach transcript from assistant_messages, notify support dashboard (reuse existing support ticket + internal notification pattern).

2. **POST /api/assistant/escalate**  
   - Body: `conversation_id` (required), optional `reason` (user-facing or internal).  
   - Auth: client_route_guard (portal user); ensure conversation belongs to user’s client_id.  
   - Actions: mark conversation escalated, build transcript from assistant_messages, create support ticket (link to client_id/CRN), attach transcript to ticket, send internal notification.  
   - Return: e.g. `{ escalated: true, ticket_id?: string, message?: "Support has been notified" }`.

3. **Auto-escalation triggers (in chat flow)**  
   - After receiving user message (and optionally after generating assistant reply):  
     - Keyword check: e.g. “human”, “complaint”, “refund”, “legal”, “cancel” (align with task; can reuse/extend support_chatbot HANDOFF_TRIGGERS for portal).  
     - Optional: AI confidence &lt; threshold (if you add confidence to LLM output).  
     - Optional: billing topic detection (keyword or classifier).  
   - If trigger fires: either (a) set escalated + create ticket automatically, or (b) force next assistant reply to say “I’m transferring you to a support specialist” and return a flag so frontend shows “Request human” / calls escalate. Recommendation: (b) so user confirms handover.

4. **Frontend (Portal Assistant)**  
   - Show “Escalated to human” when conversation has been escalated (e.g. from conversation metadata or a dedicated small endpoint).  
   - Show “Support joined” when ticket is in a “support_joined” or “in_progress” state (optional; requires support ticket status in API).  
   - If support online: show “Connect to live chat” (e.g. open Tawk or same widget with context).  
   - If offline: show “Create ticket” that calls POST /api/assistant/escalate and then “Ticket created; we’ll email you.”

5. **RBAC: Support can read transcripts**  
   - Add endpoint(s) for staff to list/read **assistant** conversations/messages (e.g. GET /api/admin/assistant/conversations, GET /api/admin/assistant/conversations/:id with messages).  
   - Protect with `require_support_or_above` (or require_owner_or_admin if you want only Admin/Owner). Task says “Support role can read transcripts; Admin/Owner can audit” — so use require_support_or_above for transcript read, keep audit logs for Admin/Owner as today.

6. **Optional: GET /api/assistant/context**  
   - Only if product needs it: return portal_facts + kb_snippets for current user (same as chat uses) without sending a message.

---

## 7. Recommended Implementation Order (Safe, No Duplication)

1. **Schema only:** Add `escalated`, `escalation_reason`, (optional) `escalated_at` to assistant_conversations. Migration or one-time backfill for existing docs (escalated: false).
2. **POST /api/assistant/escalate:** Implement as above; reuse TicketService.create_ticket (or equivalent) and attach transcript; reuse internal notification for support dashboard.
3. **Auto-escalation triggers:** In assistant_chat_service, after storing user message (and optionally after assistant reply), run keyword/billing checks; if trigger, set a flag or store “system” message and include in response so frontend can show “Request human” and call escalate (or auto-call escalate with reason).
4. **Frontend:** In AssistantPage, add “Talk to a human” / “Escalated to human” / “Support joined” states and wire to /api/assistant/escalate and support availability (and ticket status if available).
5. **RBAC:** Add GET /api/admin/assistant/conversations (and detail by conversation_id) with require_support_or_above; return list/detail of assistant_conversations + assistant_messages for audit/Support.
6. **Docs:** Update ASSISTANT_SPEC.md to describe escalation, transcript visibility, and RBAC. Keep ASSISTANT_TASK_GAP.md or replace with this audit for “hardening” work.

---

## 8. Files to Touch (Reference Only)

| Area | Files |
|------|--------|
| Schema / DB | database.py (indexes if needed for escalated), no new collections. |
| Escalation + triggers | assistant_chat_service.py (optional trigger check; or new assistant_escalation_service.py), routes/assistant.py (POST /escalate). |
| Support ticket + transcript | support_service.py / routes/support.py (create ticket with transcript; may already support transcript in create_ticket). |
| Admin transcript read | routes/admin.py (new GET /assistant/conversations, GET /assistant/conversations/:id) with require_support_or_above. |
| Frontend | AssistantPage.js (escalation state, “Request human”, “Escalated”, “Support joined”, call /escalate). |
| Docs | ASSISTANT_SPEC.md, ASSISTANT_HARDENING_AUDIT.md (this file). |

---

## 9. What Not to Do

- Do **not** add a new `assistant_sessions` collection; extend `assistant_conversations`.
- Do **not** duplicate the Support Chat Widget’s handoff logic; **reuse** support ticket creation and transcript attachment from the portal assistant.
- Do **not** change the existing assistant_messages schema for task field names (`sender` vs `role`); keep `role` and add `system` only if needed.
- Do **not** implement “Level 3 — Full Agent” (assistant modifying records); current read-only boundary is correct.
- Do **not** add legal-advice or compliance-verdict claims in marketing or in-app copy; current positioning and ASSISTANT_SPEC already forbid this.

---

*Audit complete. Implement in the order above; clarify product decisions (e.g. auto vs manual escalate, “Support joined” definition) before coding.*
