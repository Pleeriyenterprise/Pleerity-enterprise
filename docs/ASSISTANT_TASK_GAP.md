# Compliance Vault Assistant — Task Gap Analysis

This document maps the task requirements to the current codebase and lists what is implemented, what is missing, and any conflicts with recommended resolution.

## Summary

| Area | Status | Notes |
|------|--------|--------|
| A) Backend routes | Partial | Existing `/ask`; task requires `/chat` with conversation_id, property_id, new response shape |
| B) Retrieval | Partial | Snapshot exists; no KB, no `assistant_retrieval_service`, no property_id filter, PII not minimized |
| C) AI generation | Partial | JSON output exists; no citations array, no safety_flags, no strict fallback template |
| D) CRN lookup | Done | Admin CRN required and resolved; client uses client_id only |
| E) Storage + audit | Partial | Admin has `admin_assistant_queries`; no assistant_conversations/messages; audit uses ADMIN_ACTION / ADMIN_ASSISTANT_QUERY |
| F) Frontend | Partial | Chat UI and disclaimer exist; no property scope, no Sources/citations, no legal banner |
| G) Guardrails | Partial | Prompt says no legal advice; no post-process block, no PII minimization, different rate limits |
| H) Tests | Partial | Some iteration tests; missing 401, CRN isolation, citations, message storage, frontend tests |

---

## A) Backend routes

### Existing

- **Client**: `backend/routes/assistant.py`
  - `GET /api/assistant/snapshot` — returns full client snapshot (client_route_guard).
  - `POST /api/assistant/ask` — body `{ question }`; returns `AssistantResponse`: answer, what_this_is_based_on, next_actions, refused, refusal_reason, correlation_id.
- **Admin**: `backend/routes/admin.py`
  - `POST /api/admin/assistant/ask` — body `{ crn, question }` (CRN required); returns answer, compliance_summary, query_id, etc.
  - `GET /api/admin/assistant/history`, `GET /api/admin/assistant/history/{query_id}`.

### Task requires

- **Client**: `POST /api/assistant/chat` — body `{ message, conversation_id?, property_id? }`; return `{ conversation_id, answer, citations[], safety_flags{} }`.
- **Admin**: `POST /api/admin/assistant/chat` — body `{ message, conversation_id?, crn? }`; same return shape; CRN optional for lookup.

### Gap

- Different path: `/chat` vs `/ask`.
- Request: conversation_id, property_id (client); conversation_id, crn optional (admin).
- Response: citations (source_type, source_id, title), safety_flags (legal_advice_request, missing_data).

### Conflict and recommendation

- **Conflict**: Task specifies `/chat` and new payload/response; existing frontend and tests use `/ask` and current shape.
- **Recommendation**: Add new `POST /api/assistant/chat` and `POST /api/admin/assistant/chat` that implement the spec. Keep existing `/ask` endpoints for backward compatibility; optionally have `/ask` call the same service with conversation_id=null and map to old response shape, or leave as-is and migrate frontend to `/chat` and then deprecate `/ask`. Do not remove `/ask` until frontend and any external callers are updated.

---

## B) Retrieval

### Existing

- **Service**: `backend/services/assistant_service.py`
  - `get_client_snapshot(client_id)` — returns client (full_name, email, company_name, etc.), properties (full docs), requirements, documents, compliance_summary. No property_id filter. No knowledge base.

### Task requires

- **New module**: `backend/services/assistant_retrieval_service.py`
  - `get_portal_facts(client_id, user_role, property_id=None)` — minimal fields: client summary (CRN, plan, subscription), property list (id, nickname, postcode), requirements status per property with expiry, latest documents (type, filename, uploaded_at, linked_property_id, extracted expiry if confirmed). PII minimized.
  - `get_kb_snippets(query) -> list[Snippet]` — from `backend/docs/assistant_kb/*.md` (e.g. certificates_overview.md, how_to_upload.md, how_scoring_works.md, glossary.md). No web scraping; external refs via curated URLs.

### Gap

- No `assistant_retrieval_service`; no `property_id` filter; no KB; snapshot includes more PII than spec (e.g. full address in properties). No `backend/docs/assistant_kb/` directory.

### Recommendation

- Add `assistant_retrieval_service.py` with `get_portal_facts` and `get_kb_snippets`. Create `backend/docs/assistant_kb/` and add the listed markdown files (content can be minimal placeholders initially). In the new `/chat` flow, use portal_facts + kb_snippets as context. Optionally refactor existing `get_client_snapshot` to call `get_portal_facts` with PII rules (nickname + postcode by default) to avoid duplication.

---

## C) AI generation

### Existing

- `backend/services/assistant_service.py`: system prompt with no legal advice; JSON output with answer, what_this_is_based_on, next_actions; fallback on parse error uses raw text.

### Task requires

- System prompt: no legal advice, cite sources, if missing data ask user to upload/confirm, if user asks for legal verdict refuse politely.
- Context: portal_facts JSON + kb_snippets text.
- Output JSON: `answer`, `citations: [{ source_type, source_id, title }]`, `safety_flags: { legal_advice_request, missing_data }`.
- Validation: strict parse; on invalid JSON use safe template ("I can help, but I need you to rephrase…" + what data is available).

### Gap

- No citations array (source_type, source_id, title); no safety_flags; no structured fallback template.

### Recommendation

- Extend (or add) assistant generation in a way that: (1) accepts portal_facts + kb_snippets, (2) instructs the model to return the new JSON shape with citations and safety_flags, (3) parses strictly and uses the safe fallback on failure. This can live in the existing `assistant_service.py` or a dedicated function used by the new `/chat` route.

---

## D) CRN lookup

### Existing

- Client: uses authenticated user's client_id only; no CRN in request.
- Admin: CRN required in body; resolved via `clients.customer_reference`; snapshot built for that client.

### Task

- Client: ignore CRN in message; use authenticated client_id only.
- Admin: allow CRN to be provided; resolve to client_id; never expose other clients to non-admins.

### Status

- **Done.** No change required; admin can be extended to optional CRN (for "new question without CRN" if needed) while keeping current behaviour when CRN is provided.

---

## E) Storage + audit

### Existing

- **Collections**: Only `admin_assistant_queries` (admin): query_id, admin_id, client_id, crn, question, answer, model, snapshot_summary, created_at. No client-side conversation or message storage.
- **Audit**: Client assistant uses `AuditAction.ADMIN_ACTION` with metadata `"action": "CLIENT_ASSISTANT_QUERY"`. Admin uses `AuditAction.ADMIN_ASSISTANT_QUERY`.

### Task requires

- **Collections**:  
  - `assistant_conversations`: client_id, created_by_user_id, created_at, last_activity_at.  
  - `assistant_messages`: conversation_id, client_id, user_id, role, message, citations, safety_flags, model, prompt_version, created_at.
- **Audit actions**: ASSISTANT_CHAT_REQUESTED, ASSISTANT_CHAT_RESPONDED, ASSISTANT_CHAT_REFUSED_LEGAL, ASSISTANT_CHAT_ERROR.

### Gap

- No assistant_conversations or assistant_messages; no per-turn storage for client; audit action names and semantics differ.

### Recommendation

- Add new AuditAction enum values (ASSISTANT_CHAT_REQUESTED, ASSISTANT_CHAT_RESPONDED, ASSISTANT_CHAT_REFUSED_LEGAL, ASSISTANT_CHAT_ERROR). Add assistant_conversations and assistant_messages and write to them in the new `/chat` flow. Keep existing admin_assistant_queries and ADMIN_ASSISTANT_QUERY for current admin `/ask` until admin is migrated to `/chat` if desired.

---

## F) Frontend

### Existing

- **Client**: `frontend/src/pages/AssistantPage.js` — chat panel, disclaimer ("This assistant explains your compliance data only. It does not provide legal advice."), what_this_is_based_on + next_actions (expandable "Show details"), no property scope, no conversation_id.
- **Admin**: `frontend/src/pages/AdminAssistantPage.js` — CRN input, load client, then ask; history panel; no conversation_id in API.

### Task requires

- Assistant tab (or floating help); chat with message history; **scope selector**: All properties or selected property (property_id); **Sources** under each response (portal + KB); disclaimer "Information only. Not legal advice." If safety_flags.legal_advice_request === true, show banner: "I can't provide legal advice. I can show what your portal currently has and what you can do next."

### Gap

- No property scope selector; no Sources as citations (source_type, source_id, title); no legal_advice_request banner; disclaimer text slightly different.

### Recommendation

- Add property scope selector (All / property dropdown) and send property_id in `/chat`. Display citations as "Sources" (list with source_type, source_id, title). Add the legal-advice banner when safety_flags.legal_advice_request is true. Align disclaimer with spec. Use conversation_id when returned to maintain history in UI (and optionally for backend continuity).

---

## G) Hard guardrails

### Existing

- Prompt: no legal advice, explain product only. No post-processing. Snapshot includes full client and property data (e.g. address). Rate limit: 10 requests / 10 minutes per client (key `assistant_{client_id}`).

### Task requires

- Post-process: block/rewrite "you are compliant", "you are legally required to", "this guarantees compliance".
- PII: nickname + postcode by default; address_line_1 only when user explicitly asks and authorized.
- Rate limit: 20 / 10 min per user; 100 / day per client (env configurable).

### Gap

- No post-process checker; no PII minimization in snapshot; rate limits differ (per user vs per client, and daily cap).

### Recommendation

- Add a post-process step that scans assistant output for forbidden phrases and rewrites or replaces with safe text. In `get_portal_facts` (and any snapshot used for chat), return only nickname + postcode unless address is explicitly requested. Extend rate limiter: per-user key (e.g. portal_user_id) 20/10min; per-client key 100/day (configurable via env), and enforce both in `/chat`.

---

## H) Tests

### Existing

- `tests/test_iteration17_admin_assistant.py`: admin ask, CRN validation, history, audit ADMIN_ASSISTANT_QUERY.
- `tests/test_iteration18_drilldowns.py`: client assistant ask, refuses action requests, empty question rejected.
- `backend/test_assistant.py`: snapshot, ask endpoint (URL-based).

### Task requires

- Backend: non-auth 401; client cannot query other CRN; admin CRN lookup works; response includes citations when portal facts referenced; legal advice request refused or safety-flagged with safe wording; messages saved with conversation_id.
- Frontend: chat renders; property scope passed; sources list renders.

### Gap

- No 401 test for unauthenticated /chat; no test that client cannot query by CRN; no citation/safety_flags assertions; no check that messages are stored; no frontend tests for scope or sources.

### Recommendation

- Add backend tests for: 401 on unauthenticated POST /api/assistant/chat; client request with no CRN in body (and ensure server uses only client_id); admin CRN lookup returns that client's data; at least one test where response has citations; one where legal request is refused or safety_flags.legal_advice_request true; one that checks assistant_messages after a chat. Add frontend tests (or extend existing): chat panel renders; selecting property sends property_id; response shows Sources list when citations present.

---

## Implementation order (recommended)

1. **docs/ASSISTANT_SPEC.md** — Done.
2. **AuditAction** — Add ASSISTANT_CHAT_REQUESTED, ASSISTANT_CHAT_RESPONDED, ASSISTANT_CHAT_REFUSED_LEGAL, ASSISTANT_CHAT_ERROR in `backend/models/core.py`.
3. **assistant_retrieval_service.py** — get_portal_facts (with property_id, PII minimization), get_kb_snippets; create `backend/docs/assistant_kb/` + placeholder markdown files.
4. **assistant_service.py (or new orchestration)** — New chat flow: load/create conversation, get portal_facts + kb_snippets, call LLM with new prompt and output schema (answer, citations, safety_flags), post-process verdict phrases, store in assistant_messages + assistant_conversations, audit, return new shape.
5. **Routes** — POST /api/assistant/chat (client_route_guard), POST /api/admin/assistant/chat (require_owner_or_admin); rate limits 20/10min per user, 100/day per client.
6. **Guardrails** — Post-process block/rewrite; PII in get_portal_facts as above.
7. **Frontend** — Property scope selector, call /chat with conversation_id and property_id; display citations as Sources; legal banner when safety_flags.legal_advice_request; disclaimer text.
8. **Tests** — Backend and frontend as in task.

---

## File reference (existing)

| File | Relevance |
|------|-----------|
| backend/routes/assistant.py | Client /ask, /snapshot; add /chat here or keep /ask and add /chat |
| backend/routes/admin.py | Admin /assistant/ask, /assistant/history; add /assistant/chat |
| backend/services/assistant_service.py | get_client_snapshot, ask_question; extend or add chat flow + new response shape |
| backend/models/core.py | AuditAction; add ASSISTANT_CHAT_* |
| backend/utils/rate_limiter.py | Extend for per-user and per-client/day |
| frontend/src/pages/AssistantPage.js | Add scope, citations/Sources, legal banner, call /chat |
| frontend/src/pages/AdminAssistantPage.js | Optional: add /admin/assistant/chat with conversation_id, or keep current ask |

No duplication: new behaviour lives in new endpoints (/chat), new retrieval module, and extended assistant service; existing /ask and admin_assistant_queries remain until explicitly deprecated/migrated.
