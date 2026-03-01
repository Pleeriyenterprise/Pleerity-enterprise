# Pleerity 24/7 Support Assistant — Task vs Codebase Audit

**Purpose:** Map the task requirements to the current implementation. Identify what is implemented, what is missing, and any conflicts. **No implementation** in this audit; recommendations only.

---

## 0) Non-Negotiables

| Requirement | Status | Notes |
|-------------|--------|------|
| No legal advice | **Done** | `support_chatbot.is_legal_advice_request()`, `LEGAL_REFUSAL_RESPONSE`, enforced in `handle_chat_message()`; tests in `test_support_system.test_chat_refuses_legal_advice`. |
| Assistant never queries DB directly; retrieval via backend API with RBAC | **Done** | All data via support/assistant routes; client snapshot via `get_client_snapshot(client_id)`; admin via `require_support_or_above`. |
| Read-only assistant; no side effects except support tickets/conversations | **Done** | Chat only creates/updates conversations and messages; ticket creation is the intended side effect. |
| Full transcript retention; human sees whole conversation on handoff | **Done** | Every message in `support_messages`; `MessageService.get_transcript()`; ticket creation attaches transcript; admin conversation view shows full messages + system_events. |
| Multi-service capable (CVP, Document, Automation, Market Research) | **Done** | `support_chatbot`: KNOWLEDGE_BASE services, `ServiceArea` enum, `detect_service_area()`; routing in chat. |
| RBAC server-side for account lookup | **Partial** | Public lookup: no auth (by design). Portal: `get_current_user`. Admin lookup: **see conflict below** — task says ROLE_ADMIN only; code uses `require_support_or_above` (Owner, Admin, Support). |
| All sensitive actions audit-logged | **Done** | `SupportAuditService.log_action()` for chat, lookup attempts, ticket creation, admin reply, ticket status, CRN lookup. |

---

## 1) Assistant Naming + Positioning

| Requirement | Status | Notes |
|-------------|--------|------|
| Name in UI: "Pleerity Support" (not restricted to CVP) | **Done** | `SupportChatWidget.js`: header "Pleerity Support", "AI Assistant • 24/7"; footer "Powered by Pleerity AI • No legal advice". |
| Service routing: CVP, Document Services, Automation, Market Research, billing/account | **Done** | `support_chatbot`: KNOWLEDGE_BASE, ServiceArea enum, detect_service_area; quick actions and KB cover all. |

---

## 2) Channels

| Requirement | Status | Notes |
|-------------|--------|------|
| **A) Website Assistant (anonymous)** | **Done** | POST /api/support/chat (channel=web), quick-actions, lookup, ticket; handoff: live chat, email ticket, WhatsApp. |
| KB answers + routing + ticket creation | **Done** | handle_chat_message uses KB/Gemini; ConversationService + MessageService; POST /api/support/ticket. |
| CRN+email verification lookup (sanitized) | **Done** | POST /api/support/lookup; `lookup_account_by_crn()`; returns verified + account_status, member_since only. |
| Human handoff: live chat + email ticket + WhatsApp | **Done** | handoff_options in chat response; TawkToAPI.openWithContext(); EmailTicketForm; generate_whatsapp_link(). |
| **B) Portal Assistant (authenticated)** | **Done** | GET /api/support/account-snapshot (client-scoped); SupportChatWidget with isAuthenticated/clientContext; chat uses channel=portal and client_context when logged in. |

---

## 3) Transcript System (MANDATORY)

| Task model | Current implementation | Match? |
|------------|------------------------|--------|
| **Conversation** { id, channel, started_at, ended_at, user_identity_type, client_id?, email?, crn?, status } | **support_conversations**: conversation_id, channel (web/portal/whatsapp), started_at (started_at), ended_at, user_identity_type, client_id, email, crn, status (open/escalated/closed), last_message_at, message_count, service_area, category, urgency | **Yes** (field names slightly differ; semantics match). |
| **ConversationMessage** { conversation_id, sender, message_text, timestamp, metadata, redaction_flags } | **support_messages**: message_id, conversation_id, sender (user/bot/human), message_text, timestamp, metadata, redaction_flags | **Yes**. |
| **SupportTicket** { ticket_id, conversation_id, category, priority, contact_method, status, assigned_to?, created_at } | **support_tickets**: ticket_id, conversation_id, category, priority, contact_method, subject, description, service_area, email, crn, status, assigned_to, created_at, updated_at, resolved_at, notes | **Yes** (task "minimal" vs current has subject, description, notes — acceptable). |
| Every message → ConversationMessage | **Done** | MessageService.add_message() on every user/bot message; quick actions also add messages. |
| On escalation link SupportTicket to Conversation | **Done** | TicketService.create_ticket(..., conversation_id=...); conversation escalated. |
| Human must view transcript in admin or live chat | **Done** | GET /api/admin/support/conversation/{id} returns messages + transcript; AdminSupportPage shows full transcript; Tawk gets attributes (conversation_id, transcript_available). |

---

## 4) Live Chat Integration

| Requirement | Status | Notes |
|-------------|--------|------|
| Integrate with live chat provider; preferred Tawk | **Done** | TawkToWidget.js loads Tawk script; TawkToAPI (show, hide, setAttributes, addTags, openWithContext). |
| On human request: create ticket + attach Conversation ID, transcript, metadata (category, urgency, service area, CRN) | **Partial** | **Ticket creation** is separate (user picks "Email Ticket" and submits form, or admin creates from conversation). When user clicks "Live Chat", Tawk is opened with **attributes** (conversation_id, crn, service_area, category, transcript_available) — but **no automatic ticket creation** and **no automatic injection of transcript into Tawk** (Tawk does not accept transcript in API; agent sees attributes only). So: "create live chat conversation/ticket and attach transcript" — **current**: we open Tawk with context attributes; we do **not** create a support ticket automatically when user chooses Live Chat. Task says "create live chat conversation/ticket and attach... transcript". |
| Human replies visible to user in same channel | **N/A** | Tawk handles its own channel; our "reply" is admin reply in our system (POST /admin/support/conversation/{id}/reply) which is for **Escalation Inbox** flow. So: **Live chat** = Tawk (replies in Tawk). **Fallback** = our reply box in Admin Support (replies stored in support_messages as HUMAN). Task requires "human replies visible in same channel" — for Tawk that's Tawk's UI; for fallback that would require real-time or refresh in widget. **Gap:** Widget does not poll or subscribe for admin replies; if admin replies via dashboard, the widget would need to refetch or use WS to show it. |
| If full provider API not feasible: Escalation Inbox with transcript + reply box | **Done** | Admin Support has conversation detail + transcript + reply (POST conversation/:id/reply); tickets list; create ticket from conversation. |

**Recommendation:** Document that "Live Chat" = Tawk with context (no server-side ticket created for Tawk path unless product wants it). Optionally: when user clicks Live Chat, also create a support ticket with status "live_chat" and link conversation_id so admin has a ticket record; and ensure widget can show admin replies (e.g. poll conversation when tab focused).

---

## 5) WhatsApp Handoff

| Requirement | Status | Notes |
|-------------|--------|------|
| Tier 1: "Continue on WhatsApp" with prefilled message: "Hi Pleerity, my reference is {ConversationID} {CRN if known}. Summary: {short summary}" | **Done** | `generate_whatsapp_link(conversation_id, crn, summary)` builds exactly that (message_parts: reference + CRN + Summary); used in chat handoff_options and quick-action handoff. |
| Tier 2 (feature-flagged): Twilio WhatsApp API automation | **Not implemented** | No Twilio WhatsApp in codebase. Task says feature-flagged; safe to leave as Tier 1 only until required. |

---

## 6) Support Ticket Email

| Requirement | Status | Notes |
|-------------|--------|------|
| POST /api/support/ticket creates SupportTicket + transcript | **Done** | TicketService.create_ticket(..., conversation_id=body.conversation_id); transcript from MessageService.get_transcript(body.conversation_id). |
| Postmark customer confirmation with reference | **Done** | send_ticket_confirmation_email() via NotificationOrchestrator (SUPPORT_TICKET_CONFIRMATION). |
| Internal email to support inbox with transcript summary + link to admin ticket page | **Done** | send_internal_ticket_notification() with transcript (first 2000 chars), link to FRONTEND_URL/admin/support. |

---

## 7) Secure Account Lookup

| Requirement | Status | Notes |
|-------------|--------|------|
| Public: POST /api/support/lookup { crn, email } → sanitized status if match | **Done** | public_router.post("/lookup"); lookup_account_by_crn(); returns verified, account_status, member_since or generic "Unable to verify". |
| Portal: GET /api/support/account-snapshot → client-scoped | **Done** | client_router.get("/account-snapshot"); get_client_snapshot(client_id). |
| Admin: POST /api/admin/support/lookup-by-crn **restricted to ROLE_ADMIN** | **Conflict** | **Task:** "restricted to ROLE_ADMIN". **Current:** `require_support_or_above` = Owner, Admin, **Support**. So Support role can do CRN lookup. **Recommendation (safest):** If task is strict "admin only", change lookup-by-crn to use `admin_route_guard` (ROLE_ADMIN only). If product intends Support to look up clients, keep current and document the variance. |
| All lookup attempts audit-logged and **rate-limited** | **Partial** | **Audit:** Public lookup logs via SupportAuditService (public_lookup_attempt); admin lookup logs (admin_crn_lookup). **Rate limiting:** Comment in code says "Rate limiting would go here" on public lookup — **not implemented**. Task: "rate-limited". **Recommendation:** Add rate limit (e.g. per IP or per crn) on POST /api/support/lookup; 429 when exceeded; log. |

---

## 8) Structured + Free-text Intake (HYBRID)

| Requirement | Status | Notes |
|-------------|--------|------|
| Free text: user message | **Done** | message in ChatRequest; stored in support_messages. |
| Structured metadata: service_area, category, urgency, preferred_contact, identifiers (CRN/email) | **Partial** | **Conversation:** service_area, category, urgency updated from chat metadata. **Ticket:** category, priority, contact_method, service_area, email, crn. **Missing on Conversation:** preferred_contact (email/livechat/whatsapp) not stored explicitly; identifiers only if user provides (crn/email on conversation when provided). Task wants "Store metadata on Conversation and SupportTicket" — conversation has service_area, category, urgency; ticket has category, priority, contact_method, service_area, email, crn. **Gap:** preferred_contact not captured on conversation (only on ticket when they submit email form). |
| Stored on Conversation and SupportTicket | **Done** for existing fields | Conversation: service_area, category, urgency, crn, email. Ticket: category, priority, contact_method, service_area, subject, description, email, crn. |

---

## 9) Admin UI (MANDATORY)

| Requirement | Status | Notes |
|-------------|--------|------|
| /admin/support | **Done** | Route in App.js; AdminSupportPage. |
| List tickets | **Done** | GET /admin/support/tickets; Tickets tab. |
| Filter by status, category, service_area | **Done** | list_tickets(status, category, service_area, priority, assigned_to, search). |
| Open ticket → full transcript + metadata | **Done** | GET /admin/support/ticket/{id}; shows ticket, conversation, messages; handover_summary when from Portal Assistant. |
| Reply capability (fallback) | **Done** | POST /admin/support/conversation/{id}/reply; reply box in UI. |
| Attach client record (if CRN match and admin authorised) | **Partial** | CRN Lookup (lookup-by-crn) returns client + orders + properties_count; UI shows in "Context" or detail. GET /admin/support/context/{client_id} returns full context (account, portfolio, notifications, audit, documents). So "attach" is implicit (view context by client_id); no explicit "attach to ticket" button. |
| Audit log viewer for support actions | **Done** | GET /admin/support/audit-log; filters by resource_type, resource_id, action. **UI:** Need to confirm AdminSupportPage has Audit tab or section — from code, endpoint exists; UI may have a tab or link. |

---

## 10) Testing (MANDATORY)

| Task test | Status | Notes |
|-----------|--------|------|
| Website Assistant KB flow | **Done** | test_support_system: chat creates/continues, handoff, legal refusal, services; test_new_features_iter50: quick actions, FAQ, chat. |
| Portal assistant snapshot flow | **Done** | GET /api/support/account-snapshot (client); widget with isAuthenticated. |
| CRN lookup success + failure | **Done** | test_support_system: lookup invalid CRN (not verified); admin lookup 404/200. |
| Legal advice refusal | **Done** | test_chat_refuses_legal_advice. |
| Live chat escalation test (transcript visible) | **Partial** | Handoff to Tawk tested (openWithContext); transcript is in our DB and in ticket — not "in" Tawk (Tawk gets attributes only). So "transcript visible" for human = visible in Admin Support when they open the conversation/ticket. |
| WhatsApp handoff test (prefilled message includes reference) | **Done** | test_new_features_iter50: POST /api/support/audit/whatsapp-handoff; widget opens link with conversation_id. |
| Ticket email test (customer + internal) | **Done** | test_support_system: ticket creation with conversation_id; support_email_service used in route. |
| Deliver pass/fail report + evidence logs | **Manual** | Tests exist; formal "report" and evidence logs are process, not in repo. |

---

## Conflicts and Safest Options

| Topic | Task says | Codebase has | Safest option |
|-------|-----------|--------------|---------------|
| **Admin CRN lookup role** | Restricted to **ROLE_ADMIN** | require_support_or_above (Owner, Admin, **Support**) | If compliance requires admin-only: change to `admin_route_guard` for POST /api/admin/support/lookup-by-crn. Otherwise keep Support access and document. |
| **Data model names** | Conversation, ConversationMessage, SupportTicket | support_conversations, support_messages, support_tickets | No change; names are implementation detail; semantics match. |
| **Queue/session API** | GET /api/support/queue, /session/:id | GET /api/admin/support/conversations, /conversation/:id, /tickets | Keep existing admin routes; do not add duplicate /api/support/queue (see ASSISTANT_SUPPORT_HANDOVER_TASK_AUDIT). |

---

## Summary: What's Implemented vs Missing

**Fully or largely implemented:**  
0) Non-negotiables (legal refusal, no DB access, read-only, transcript, multi-service, audit); 1) Naming "Pleerity Support" and service routing; 2) Website + Portal channels, lookup, handoff options; 3) Transcript system (collections and every message stored, ticket linked); 4) Tawk integration + Escalation Inbox reply; 5) WhatsApp Tier 1 prefilled message; 6) POST /api/support/ticket + customer + internal emails; 7) Public and portal lookup; 8) Structured metadata on conversation/ticket (partial preferred_contact); 9) Admin /admin/support with list, filter, transcript, reply (with canned responses dropdown), context, CRN lookup, audit endpoint; 10) Tests for KB, portal snapshot, CRN, legal refusal, WhatsApp, ticket.

**Gaps / to add:**  
- **Rate limiting** on POST /api/support/lookup (task: "rate-limited").  
- **Admin lookup role:** Align with task (ROLE_ADMIN only) or document Support access.  
- **Live Chat path:** Optionally create a ticket when user chooses Live Chat and ensure transcript is visible (e.g. in admin when they open by conversation_id); Tawk cannot receive full transcript via API.  
- **preferred_contact** on Conversation when user selects handoff method (email vs livechat vs whatsapp).  
- **Tier 2 WhatsApp** (Twilio) only if feature-flagged and required.  

**Conflicts resolved by recommendation:**  
- Use existing support_conversations / support_messages / support_tickets; do not introduce new Conversation/ConversationMessage names as new collections.  
- Keep admin routes under /api/admin/support; do not add duplicate /api/support/queue.  
- Admin CRN lookup: restrict to ROLE_ADMIN if task is strict; else keep Support and document.

---

*Audit complete. Use this document to plan implementation; do not implement blindly. Clarify product choices (e.g. admin-only vs Support CRN lookup, rate limit limits) before coding.*
