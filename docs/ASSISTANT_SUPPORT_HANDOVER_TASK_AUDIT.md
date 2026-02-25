# Enterprise Pleerity Assistant + Support Dashboard Handover — Task Audit

**Purpose:** Map the task requirements to the current codebase, identify what is implemented, what is missing, and any conflicts. No implementation in this audit; recommendations only.

---

## Executive summary

| Area | Status | Conflict? |
|------|--------|-----------|
| **Part A — Assistant system prompt** | Partial | Task wants single file + `portal_urls`; current prompt is inline; no `portal_urls`; context shape differs |
| **Part A — Portal links / portal_urls** | Missing | No server-built `portal_urls`; assistant can fabricate URLs |
| **Part A — Chat context (user, account_state, portfolio, kb)** | Partial | `get_portal_facts` + kb exist; no `account_state` (payment_state, provisioning, portal_user_exists, activation_email, password_set); no `notification_prefs` |
| **Part A — Escalation** | Done | POST /api/assistant/escalate, transcript, ticket, escalate flags (already implemented) |
| **Part B — Support Dashboard UI** | Partial | Route /admin/support exists; queue + transcript exist; **no** unified queue design, **no** context panel, **no** Handover Summary, **no** system events in transcript |
| **Part B — Data model & API** | Conflict | Task: `assistant_sessions` + GET /api/support/queue, /session/:id; current: `assistant_conversations` + `support_conversations` + `/api/admin/support/*` |
| **Resend-activation rate limit** | Missing | Task: max 3/hour; current: no rate limit on POST /api/portal/resend-activation |

---

## PART A — Assistant system prompt and context

### 1) Single source-of-truth system prompt (task)

- **Task:** File `backend/services/assistant/prompt.py` (or similar), export `ASSISTANT_SYSTEM_PROMPT` as exact text from ChatGPT.
- **Current:** `CHAT_SYSTEM_PROMPT` is defined inline in `backend/services/assistant_chat_service.py` (no legal advice, cite sources, JSON output).
- **Conflict:** Task asks for a separate prompt file and “exact text provided by ChatGPT” — that text is not in the repo. Current prompt is hand-written and already enforces no legal advice.
- **Recommendation:** Add `backend/services/assistant/prompt.py` (or `backend/services/assistant_prompt.py`) that exports `ASSISTANT_SYSTEM_PROMPT`. Either (a) paste the ChatGPT-provided text into that constant when provided, or (b) move the existing `CHAT_SYSTEM_PROMPT` there and import it in `assistant_chat_service.py`. Do **not** keep two competing prompts; one source of truth.

### 2) Portal URLs — assistant must only use backend-provided links (task)

- **Task:** Create `portal_urls` on server using env `APP_BASE_URL` (never localhost). Provide: `base`, `dashboard`, `properties`, `documents`, `upload`, `calendar`, `reports`, `notifications`, `preferences`, `support`, and `property_detail_template: ${APP_BASE_URL}/properties/{property_id}`. Assistant must never fabricate portal URLs.
- **Current:** No `portal_urls` in the assistant flow. No `APP_BASE_URL`; elsewhere the app uses `get_public_app_url()` / `get_frontend_base_url()` from `utils/public_app_url.py` (reads `FRONTEND_PUBLIC_URL`, `PUBLIC_APP_URL`, `FRONTEND_URL`, etc.). Assistant context does not include a structured URL object; the model could invent links.
- **Conflict:** Task says `APP_BASE_URL`; codebase uses `FRONTEND_PUBLIC_URL` / `PUBLIC_APP_URL` / `FRONTEND_URL`. Using the same single source as email links avoids drift.
- **Recommendation:** Introduce a small module (e.g. next to prompt or in `utils`) that builds `portal_urls` from `get_public_app_url(for_email_links=False)` (or a dedicated read for portal links). In production, reject or never use localhost. Provide the keys above; add `property_detail_template` with `{property_id}` placeholder. Pass `portal_urls` into the chat context and state in the system prompt: “You may only use these URLs; do not invent or alter them.”

### 3) /api/assistant/chat must pass (task)

- **Task:** user (name/email/role/CRN), account_state (payment_state, provisioning_status, portal_user_exists, activation_email_status, password_set), portfolio_summary + notification_prefs (if available), kb_snippets.
- **Current:** Chat uses `get_portal_facts(client_id, role, property_id)` which returns: `client_summary` (client_id, customer_reference, plan, subscription_status, client_type), `properties`, `requirements_by_property`, `documents`, `property_id_filter`. No `user` object (name/email/role/CRN). No `account_state`. No `notification_prefs`. KB: `get_kb_snippets(message)` is used and included in context.
- **Gap:** `user` and `account_state` are missing. `portfolio_summary` is partially covered by properties/requirements/documents but not named or shaped as “portfolio_summary”. Notification preferences and last deliveries are not fetched or passed.
- **Recommendation:** Extend retrieval (or add a small “account state” loader) to include: `user` (from portal_users + clients: name, email, role, CRN), `account_state` (payment_state from subscription, provisioning_status from onboarding_status, portal_user_exists, activation_email_status, password_set from portal/password status). Optionally add `portfolio_summary` (counts, scores) and `notification_prefs` + last deliveries if available. Pass these into the same context blob the LLM receives; keep PII minimal and server-side only.

### 4) Escalation triggers + endpoint (task)

- **Task:** /api/assistant/escalate; save session + transcript; create ticket; mark escalated; return ticket_id.
- **Current:** Implemented. POST /api/assistant/escalate; `escalate_assistant_conversation()` updates `assistant_conversations` (escalated, escalation_reason, escalated_at), builds transcript from `assistant_messages`, creates support ticket with transcript, sends internal notification, returns ticket_id. Keyword-based `handover_suggested` in chat response.
- **Recommendation:** No change for this part. Optionally add “AI Handover Packet” (see Part B).

---

## PART B — Support Dashboard UI

### 1) Route and layout (task)

- **Task:** Support Dashboard at `/admin/support`; left queue (30%) + right transcript + context panel (70%); mobile: tabs Queue | Conversation | Context | Actions.
- **Current:** Route exists: `/admin/support` (AdminSupportPage). Layout: left panel (Tickets / Chats tabs, filters, list) ~5 cols, right panel (detail + transcript) ~7 cols. No dedicated “context panel” drawer; CRN Lookup is below the detail. Mobile is not explicitly tabs-based.
- **Gap:** No 30/70 split with a distinct “context panel”; no mobile tabs for Queue | Conversation | Context | Actions.
- **Recommendation:** Evolve current layout: add a third column or drawer for “Context” (account snapshot, portfolio, notifications, audit, documents). On small screens, use tabs (Queue | Conversation | Context | Actions) as specified.

### 2) Queue requirements (task)

- **Task:** Filters: status, priority, channel, assigned_to, search by CRN/email. Row: status, priority, timestamp, user, CRN, last message preview, tags. SLA: “Oldest unassigned”, “Avg first response today”.
- **Current:** Left panel has Tickets and Conversations tabs. Filters: status, priority (tickets), service_area. Conversation row: conversation_id, status, channel, message_count, last_message_at, service_area. Ticket row: ticket_id, status, priority, subject, description, email, created_at. No CRN/email search, no “assigned_to” filter, no last message preview in row, no tags, no SLA indicators.
- **Gap:** Search by CRN/email, assigned_to, last message preview, tags, SLA.
- **Recommendation:** Add query params and backend support for search (CRN/email), assigned_to; return last_message_preview and tags in list payloads; add optional SLA fields (oldest unassigned, avg first response) if desired.

### 3) Conversation view (task)

- **Task:** Header: Assign/Resolve/Create ticket; transcript timeline with system events; quick reply + canned responses; “Handover Summary” when session.escalated == true.
- **Current:** Detail header shows status/priority and ticket dropdown (Mark Open/Pending/Resolved/Closed). Transcript shows user/bot/human bubbles from `support_messages`; no system events (e.g. “AI escalated at …”, “Support joined at …”). Reply is a single textarea + Send. Canned responses exist at /admin/support/responses but are not integrated into this reply bar. No “Handover Summary” when escalated.
- **Gap:** Assign to me, Resolve, Create ticket in header; system events in transcript; canned responses in reply bar; Handover Summary for escalated sessions.
- **Recommendation:** Add Assign/Resolve/Create ticket to the conversation header (wire to existing or new support APIs). Store and show system events (escalation time, support joined, email sent, etc.) in the transcript. Add a “Saved responses” dropdown or selector next to the reply box. When the conversation (or linked ticket) is from an escalated assistant session, show a “Handover Summary” section (see “AI Handover Packet” below).

### 4) Context panel (task)

- **Task:** Account snapshot (CRN, payment state, provisioning, portal user exists, activation email, password set, last login, env); Portfolio snapshot (properties, scores, overdue/expiring, top 5 missing); Notifications & preferences (email/SMS on, reminder timing, recipients, last reminder); Recent system activity (last 20 audit, webhook status, last 10 email delivery events); Evidence & documents (recent uploads, extraction status, expiry dates).
- **Current:** No context panel. CRN Lookup returns client name, email, subscription_status, recent_orders, properties_count — not the full snapshot above.
- **Gap:** Full context panel is missing.
- **Recommendation:** Add a dedicated context API (e.g. GET /api/admin/support/context/:client_id or by conversation/session) that returns account snapshot, portfolio snapshot, notification prefs + last deliveries, recent audit log, recent email delivery events, recent documents with extraction status. Build the Support Dashboard context panel from this API. Respect RBAC (Support can see only what they are allowed to).

### 5) Data model & API (task vs current — conflict)

- **Task:** `assistant_sessions`, `assistant_messages`, `support_tickets` (minimal). Endpoints: GET /api/support/queue, GET /api/support/session/:session_id, POST …/assign, …/resolve, …/message.
- **Current:** Two systems. (1) **Portal assistant:** `assistant_conversations` (conversation_id, client_id, escalated, etc.), `assistant_messages`; POST /api/assistant/chat, POST /api/assistant/escalate; GET /api/assistant/conversation/:id/status; GET /api/admin/assistant/conversations and …/conversations/:id (Support can read). (2) **Support (widget):** `support_conversations`, `support_messages`, `support_tickets`; GET /api/admin/support/conversations, …/tickets, …/conversation/:id, …/ticket/:id; POST …/conversation/:id/reply; PUT …/ticket/:id/status. No GET /api/support/queue or /api/support/session/:id; admin routes are under `/api/admin/support`.
- **Conflict:** Task names “assistant_sessions” and “/api/support/queue”, “/api/support/session/:id”. Existing design uses `assistant_conversations` and `/api/admin/support/*` for admin. Adding a second “sessions” model and a second API shape would duplicate and confuse.
- **Recommendation (safest):** Do **not** introduce a new `assistant_sessions` collection. Keep `assistant_conversations` and `assistant_messages`. Optionally add an alias or view: “queue” = list that can merge support_conversations + support_tickets + escalated assistant_conversations (or show assistant escalations as tickets with a flag). Expose under existing admin support routes (e.g. GET /api/admin/support/queue that returns unified queue) or keep separate lists (Tickets / Chats / Portal assistant escalations) and link from ticket to assistant transcript when the ticket was created from escalation. Do **not** add a separate `/api/support/queue` that duplicates `/api/admin/support/conversations` and `/tickets`; extend existing admin support APIs and frontend.

### 6) Logging / audit (task)

- **Task:** Every support action writes to audit log (who, what, before/after if applicable).
- **Current:** Support uses `SupportAuditService.log_action` for ticket creation and some flows; admin reply and other actions may log. General audit log (e.g. `create_audit_log` with AuditAction) is used for assistant. Not every support action may be audited in a single consistent way.
- **Recommendation:** Ensure every support action (assign, resolve, reply, create ticket, status change, resend activation from dashboard) writes to the audit log with actor, action, resource, and optional before/after. Prefer one audit model (e.g. existing audit_logs + SupportAuditService) so all actions are queryable.

---

## “AI Handover Packet” (task)

- **Task:** When AI escalates, generate a short “Handover Summary”: user intent, where they got stuck, what AI already tried, required action, attachments (last error, screenshot flag). Show at top of conversation when session.escalated == true.
- **Current:** On escalate we attach the full transcript to the ticket description and send internal notification; we do not generate a structured summary.
- **Recommendation:** Optional enhancement: when creating the ticket from escalation, optionally call an LLM or template to produce a one-paragraph handover summary and store it (e.g. in ticket description or a `handover_summary` field). Dashboard can show this in the “Handover Summary” block when viewing that ticket or the linked conversation.

---

## Safety and constraints (task)

- **No secrets in frontend:** Current design keeps secrets server-side; continue.
- **No legal advice in assistant:** Already enforced in prompt and guardrails.
- **Assistant never fabricates portal URLs:** Not yet enforced; implement via `portal_urls` (see above).
- **Rate limit resend-activation:** Task: max 3 per hour. Current: POST /api/portal/resend-activation has no rate limit.
- **Recommendation:** Add rate limit (e.g. per client_id or per portal_user_id) of 3 per hour for resend-activation; return 429 when exceeded and log.

---

## Conflicting instructions — summary

| Task says | Codebase has | Recommended approach |
|-----------|----------------|----------------------|
| `assistant_sessions` collection | `assistant_conversations` | Keep `assistant_conversations`; treat as “session” in product wording only. |
| GET /api/support/queue, /session/:id | GET /api/admin/support/conversations, /conversation/:id, /tickets | Keep admin routes; add “queue” view or merged list if needed; do not add duplicate public `/api/support/queue` for the same data. |
| APP_BASE_URL | FRONTEND_PUBLIC_URL / PUBLIC_APP_URL / FRONTEND_URL | Build `portal_urls` from existing `get_public_app_url()` (or same envs); document “APP_BASE_URL” as that base URL. |
| New prompt file with “exact ChatGPT text” | CHAT_SYSTEM_PROMPT inline in assistant_chat_service | Single prompt file; use ChatGPT text when provided, else move existing prompt and keep one source of truth. |

---

## Implementation order (suggested)

1. **Prompt + portal_urls (Part A)**  
   - Add `backend/services/assistant/prompt.py` (or `assistant_prompt.py`) with `ASSISTANT_SYSTEM_PROMPT`.  
   - Add `portal_urls` built from `get_public_app_url()`; pass into chat context; instruct model to use only these URLs.

2. **Chat context (Part A)**  
   - Extend context with `user`, `account_state`, and optionally `portfolio_summary` / `notification_prefs`; keep kb_snippets.

3. **Resend-activation rate limit**  
   - Rate limit POST /api/portal/resend-activation (e.g. 3/hour per client or user); 429 + audit when exceeded.

4. **Support Dashboard — context panel (Part B)**  
   - New endpoint for “context” by client (or by conversation/ticket); build Account + Portfolio + Notifications + Audit + Documents.  
   - Add Context panel (drawer or column) to AdminSupportPage and load from that endpoint.

5. **Support Dashboard — queue and conversation (Part B)**  
   - Add search (CRN/email), assigned_to, last message preview, tags, SLA if needed.  
   - Add Assign/Resolve/Create ticket to conversation header; system events in transcript; canned responses in reply bar; Handover Summary when escalated (and optionally generate handover packet on escalate).

6. **Audit**  
   - Ensure every support action is audited (who, what, before/after where applicable).

---

## What not to do

- Do **not** add a new `assistant_sessions` collection; keep using `assistant_conversations`.  
- Do **not** add a separate `/api/support/queue` that duplicates existing admin support list endpoints; extend existing admin APIs and UI.  
- Do **not** put portal URLs in the frontend or let the assistant invent links; provide them only from the backend via `portal_urls`.  
- Do **not** implement a second, conflicting system prompt; use one constant and one file.

---

*Audit complete. Use this document to plan implementation; clarify product choices (e.g. unified queue vs tabs, exact prompt text, SLA metrics) before coding.*
