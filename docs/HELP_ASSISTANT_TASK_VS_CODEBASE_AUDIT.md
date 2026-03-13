# Role-Aware AI Help Assistant – Task vs Codebase Audit

**Purpose:** Check the codebase against the task requirements for a **documentation-grounded** Help Assistant. Identify what is implemented, what is missing, and any conflicts. No code changes in this audit.

**Task summary:** Implement an in-product Help Assistant that answers only from **published Knowledge Centre content**, with role-aware visibility, citations, strict fallback when no answer is found, and no action execution.

---

## 1. Executive Summary

| Area | Implemented | Missing / Partial | Conflict / Decision |
|------|-------------|-------------------|----------------------|
| **Knowledge sources** | Knowledge Centre (`kb_articles`) exists with status (draft/published/archived), audience (USER/STAFF/ADMIN). Client Help Centre serves USER + published only. | Assistant does **not** use `kb_articles`. It uses **file-based** `backend/docs/assistant_kb/*.md`. No retrieval from published articles. | **Conflict:** Task requires "only published knowledge articles". Current assistant uses a separate markdown KB and can answer from portal data + LLM. **Recommendation:** Implement a **separate** doc-grounded Help Assistant (or add a "Help" mode) that uses only `kb_articles`; keep or later deprecate existing assistant for data Q&A. |
| **Role-aware access** | Client Help API (`/api/client/help`) returns USER + published only. Admin KB sees all audiences. | No STAFF-specific API (USER+STAFF). No role-based **retrieval** for an assistant (USER vs STAFF vs ADMIN). | Implement role-aware filter in any new help-assistant retrieval (USER → USER only; STAFF → USER+STAFF; ADMIN → USER+STAFF+ADMIN). |
| **Search / retrieval** | None over `kb_articles` for assistant. Admin list search: title, excerpt, summary, content, tags. | No `knowledge_chunks` collection. No chunking of articles. No retrieval pipeline for help-assistant queries. | Task prefers chunked index; if no vector DB, use strong text search (e.g. regex/text search on title, excerpt, content) with schema extensible for embeddings later. |
| **Assistant response rules** | Existing assistant returns answer + citations (from assistant_kb files) + safety_flags. | No structured "Direct Answer / Steps / Related Articles / Fallback". No strict "I couldn't find a confirmed answer" when no docs match. LLM can still generate from portal data. | New help-assistant must: (A) answer only from retrieved content, (B) cite article titles, (C) explicit fallback when no content. |
| **UI placement** | User: `/assistant` (chat), `/help` (browse articles). Admin: `/admin/assistant` (client-scoped chat), `/admin/knowledge-base` (CRUD). | No "ask a question" on Help Centre page. No help-assistant widget on dashboard. No Admin KC "Ask" entry. No Helpful/Not Helpful on answers. | Add entry points per task: user help widget or Help Centre "Ask"; Admin → Knowledge Centre help assistant. |
| **API** | `/api/assistant/chat`, `/api/assistant/ask`, `/api/assistant/snapshot`, `/api/assistant/escalate`. Admin: `/api/admin/assistant/ask`, `/api/admin/assistant/chat`, history, conversations. | No `POST /api/help-assistant/query` with `{ answer, steps, sources, grounded }`. Current endpoints are chat/ask with different contract and non–doc-only grounding. | Add dedicated help-assistant endpoint(s) with role-aware retrieval and response shape per task. |
| **Context-aware help** | Chat accepts optional `property_id`; portal_facts include property. | No "context" (e.g. page/module) passed to retrieval to boost relevant articles. | Optional: add `context` to query and use to prefer articles by `product_module` or category. |
| **Article linking** | Help Centre: `/help`, `/help?article=<slug>`. Product links (e.g. Documents, Property Detail) deep-link to `/help?article=uploading-evidence`. | Assistant citations reference `assistant_kb/filename.md`, not `article_id`/`slug`; user cannot click to open KB article from assistant answer. | New help-assistant must return `sources` with `articleId`, `title`, `slug`, `updatedAt` and UI must link to `/help?article=<slug>` (user) or admin article view (admin). |
| **Feedback** | `insights_feedback` exists for a different feature (admin modules). | No `assistant_feedback` collection. No Helpful/Not Helpful on assistant or help-assistant answers. | Add `assistant_feedback` (or equivalent) and UI for Helpful/Not Helpful per task. |
| **Security / safety** | Assistant has guardrails (no legal verdicts, no inventing data from thin air); client help only USER articles. | Assistant is not doc-only: it uses portal data + LLM, so it can "answer" without any KB. Admin/STAFF articles must never be exposed to USER in any new flow. | Enforce: help-assistant returns answers only from retrieved docs; server-side role filter on articles; no drafts/archived in retrieval. |

---

## 2. What Exists Today (Evidence)

### 2.1 Current “Assistant” (Not Doc-Grounded)

- **Backend**
  - **Routes:** `backend/routes/assistant.py` — `GET /api/assistant/snapshot`, `POST /api/assistant/ask`, `POST /api/assistant/chat`, `POST /api/assistant/escalate`, `GET /api/assistant/conversation/{id}/status`.
  - **Retrieval:** `backend/services/assistant_retrieval_service.py` — `get_kb_snippets(query)` loads from **`backend/docs/assistant_kb/*.md`** (files on disk), ranks by keyword overlap, returns top N snippets. **No** MongoDB `kb_articles` usage.
  - **Chat:** `backend/services/assistant_chat_service.py` — Uses `get_portal_facts()` + `get_kb_snippets(message)` then LLM (OpenAI) to produce answer + citations + safety_flags. Citations use `source_id` like `assistant_kb/filename.md` (not article slug/ID). No “grounded only in docs” guarantee; LLM can use portal_facts with or without KB.
  - **Prompt:** `backend/services/assistant_prompt.py` — System prompt tells LLM to use portal data + “curated KB snippets”; no constraint that answer must come only from KB.
- **Admin assistant:** `backend/routes/admin.py` — `POST /api/admin/assistant/ask`, `POST /api/admin/assistant/chat` (with CRN), history, conversations. Same chat service; same file-based KB; no role-based article visibility.
- **Collections:** `assistant_conversations`, `assistant_messages`, `admin_assistant_queries`. **No** `knowledge_chunks`, **no** `assistant_feedback` in `database.py` or code.

### 2.2 Knowledge Centre (KB) and Help Centre

- **Collections:** `kb_articles`, `kb_categories`, `kb_search_analytics` (see `backend/routes/knowledge_base.py`).
- **Client Help API:** `/api/client/help/articles`, `/api/client/help/articles/{slug}`, `/api/client/help/categories`. Filters: `status=published`, `is_active=True`, `audience=USER` (or missing). **No** STAFF or ADMIN articles for client.
- **Admin KB API:** Full CRUD; list supports status, category, audience, search (title, excerpt, summary, content, tags). No chunking or retrieval API for “query → relevant articles”.
- **UI:** `HelpPage.js` at `/help` — browse categories and articles, open by slug; supports `?article=<slug>`. No “Ask a question” input that calls an assistant. `AssistantPage.js` at `/assistant` — chat UI; citations show title/source_id but do not link to `/help?article=...` (source_id is file path).

### 2.3 Role Model

- **Auth:** `client_route_guard` (client portal); `admin_route_guard` and role checks (OWNER, ADMIN, SUPPORT, CONTENT) for admin. STAFF = OWNER, ADMIN, SUPPORT, CONTENT (see `auth.py`, `middleware.py`).
- **KB visibility:** Only USER (and no-audience) articles are exposed to client help. Admin sees all. There is **no** dedicated “staff help” API that returns USER+STAFF articles.

---

## 3. Gap List (Task vs Codebase)

| # | Task requirement | Current state | Gap |
|---|------------------|---------------|-----|
| 1 | Use only **published** knowledge articles / help / SOPs / release notes | Assistant uses `assistant_kb/*.md` files; no use of `kb_articles` in assistant | Retrieval for help-assistant must query `kb_articles` with `status=published`, exclude draft/archived |
| 2 | Ignore drafts, archived, raw code, hidden admin data for user roles | Client help already filters published + USER. Assistant does not use KB. | Apply same status + audience filters in any new help-assistant retrieval |
| 3 | USER: USER articles (+ public release notes if flagged) | Client help: USER (or no audience) only | Optional: “public release notes” flag; currently not in model |
| 4 | STAFF: USER + STAFF articles | No API returns USER+STAFF for staff role | Add role-aware filter: staff → audience in [USER, STAFF] |
| 5 | ADMIN: USER + STAFF + ADMIN articles | Admin KB list shows all; no “help query” that returns only visible-by-role | Help-assistant retrieval must filter by role (USER / STAFF / ADMIN) |
| 6 | Chunk articles; `knowledge_chunks` with id, article_id, title, audience, category, chunk_text, chunk_order, updated_at | No such collection or chunking | Add collection and indexing (or phase 1: search articles by title/excerpt/content without chunking, schema extensible) |
| 7 | Search/retrieval pipeline over knowledge articles | None for assistant | Implement retrieval over `kb_articles` (or over `knowledge_chunks` when added): text search, top-k, role filter |
| 8 | Answer structure: Direct Answer, Steps, Related Articles, Fallback | Chat returns free-form answer + citations; no structured steps or “Related Articles” list; no strict fallback text | New endpoint should return answer, steps[], sources[] (with articleId, title, slug, updatedAt), grounded: bool; when grounded=false use task fallback message |
| 9 | Fallback: “I couldn’t find a confirmed answer in the current help documentation.” | No such strict fallback; LLM can always answer from portal data | Help-assistant must **not** call general LLM when no docs match; return fallback and grounded=false |
| 10 | No action execution; no settings changes | Current assistant is read-only (explain only) | Same for new help-assistant; document clearly |
| 11 | No answers from unpublished drafts | N/A (assistant doesn’t use KB) | Retrieval must exclude draft/archived |
| 12 | Never expose ADMIN/STAFF docs to USER | Client help already USER-only | Enforce in help-assistant: filter by role server-side |
| 13 | Two entry points: (A) User: dashboard help widget or Help Centre, (B) Admin: Admin → Knowledge Centre | User has `/assistant` (chat) and `/help` (browse). No “Ask” on Help page. Admin has `/admin/assistant` and `/admin/knowledge-base` but no “Ask” in KC. | Add: e.g. “Ask” on Help page and/or dashboard widget; Admin KC “Help Assistant” or “Ask” that uses KB only |
| 14 | UI: ask question, view answer, click cited articles, Helpful / Not Helpful | Chat has ask + answer + citations (not clickable to KB). No feedback buttons | Add: sources as links to `/help?article=<slug>` (user) or admin article; Helpful/Not Helpful + store in feedback collection |
| 15 | `POST /api/help-assistant/query` with query, optional context; response answer, steps, sources, grounded | No such endpoint | Add endpoint; implement role-aware retrieval and response shape |
| 16 | Optional context (page/module) to boost retrieval | Chat has property_id only; no “module” or “page” | Optional: add context to request and use to boost by product_module/category |
| 17 | Article linking from answers: open cited article | Citations are file-based; no slug/articleId | Return slug (and articleId) in sources; UI links to Help or admin article |
| 18 | Feedback: Helpful / Not Helpful; store in `assistant_feedback` (id, user_id, query, answer, helpful, source_article_ids, created_at) | No such collection or UI | Add collection and endpoint; add buttons in UI |
| 19 | Security: no admin/staff docs to user; no legal advice claims; informational language | Assistant has safety rules; client help is USER-only | Same for help-assistant; add “not legal advice” where relevant |
| 20 | Design: calm, compact, product assistant; mobile responsive; fast | Current assistant/help UIs are standard | Apply to any new widget/panel |

---

## 4. Conflicts and Safest Options

### 4.1 Two Different “Assistants”

- **Task:** A **documentation-grounded** Help Assistant that answers **only** from approved Knowledge Centre content, cites articles, and refuses to guess.
- **Current:** A **general** assistant that uses portal data + file-based KB + LLM, can answer from portal data even with no KB, and does not use `kb_articles`.

**Options:**

- **A) New “Help Assistant” alongside existing:** Implement a **separate** flow: e.g. `POST /api/help-assistant/query` and a “Ask help” UI (on Help page or widget) that uses **only** `kb_articles` (published, role-filtered). Keep existing `/api/assistant/chat` for “explain my data” use cases. Clear separation: “Help” = docs only; “Assistant” = data + docs. **Recommended.**
- **B) Replace current assistant with doc-only:** Switch retrieval to `kb_articles` only and remove portal data from answers. Would break “explain my compliance” and “what’s missing” use cases unless those are also written as KB articles. **Risky** without product decision.
- **C) Two modes in one assistant:** Single chat but “Help mode” vs “Data mode” (or detect intent). Higher complexity and risk of leaking non-doc content in Help mode. **Not recommended** unless product explicitly wants one surface.

**Recommendation:** **Option A** — implement a dedicated role-aware Help Assistant (API + UI) that is strictly grounded in Knowledge Centre; keep existing assistant as-is for now.

### 4.2 Knowledge Chunks vs Simple Search

- Task suggests `knowledge_chunks` and chunked retrieval. Codebase has no chunks and no vector/embedding infra in use for KB.
- **Option 1:** Add `knowledge_chunks` and a job to chunk published articles (e.g. by section/paragraph); search by text (regex or $text if MongoDB text index). Schema extensible for embedding vector later.
- **Option 2 (simpler):** No chunking initially. Retrieve full articles (title, excerpt, content) with `status=published` and role-based audience filter; run text search (e.g. regex on title + excerpt + content), rank by match count or simple relevance, return top N articles and use their content for answer generation or extract snippets. Add `knowledge_chunks` later if needed.

**Recommendation:** Start with **Option 2** (article-level search, no new collection) to ship faster; add chunking and optional embeddings in a second phase if needed.

### 4.3 STAFF Visibility

- Task: STAFF can access USER + STAFF articles. Current client help API is used by “client” (portal users); admin KB is admin-only. There is no “staff help” or “staff assistant” API.
- **Option:** For help-assistant, determine role from auth (USER vs STAFF vs ADMIN). If the same `/api/help-assistant/query` is used from both portal and admin, pass role (or derive from JWT) and filter articles by audience: USER → [USER]; STAFF → [USER, STAFF]; ADMIN → [USER, STAFF, ADMIN]. Client portal users are USER; admin routes can pass admin/staff role. **Recommendation:** Implement this role-based filter in the new endpoint.

### 4.4 Response Shape: With or Without LLM

- Task: “Answer based only on retrieved content” and “Never fabricate.” If no grounded answer, say so.
- **Option 1 (no LLM):** Pure retrieval: return top articles + snippets; UI shows “Answer” as concatenation or first snippet + “Read more: [articles]”. No fabrication; no “steps” unless parsed from content. Simple and safe.
- **Option 2 (LLM with strict grounding):** Retrieve top articles, send only their content to LLM with strict prompt: “Answer only from the following documentation; if nothing is relevant say [fallback]. Do not add information not in the docs.” Return answer + steps (if any) + sources. Risk: LLM may still drift; need clear fallback when retrieval is empty or low-confidence.

**Recommendation:** Prefer **Option 1** for v1 (no LLM for help-assistant) to guarantee no fabrication; optional **Option 2** later with tight prompting and validation. If Option 2 is used, when retrieval returns no or very low-relevance results, **do not** call LLM; return `grounded: false` and fallback message.

---

## 5. Implementation Outline (No Code – Plan Only)

1. **Backend**
   - Add **role-aware retrieval** over `kb_articles`: filter `status=published`, `is_active=True`, and `audience` by caller role (USER / STAFF / ADMIN). Text search on title, excerpt, content (and optionally tags); return list of articles (or snippets) with article_id, title, slug, updated_at, category.
   - Add **`POST /api/help-assistant/query`** (or under `/api/client/help/query` and admin equivalent): body `{ query, context? }`; response `{ answer, steps, sources: [{ articleId, title, slug, updatedAt }], grounded }`. If no/sufficient results, return fallback message and `grounded: false`. Enforce role from auth.
   - Optional: Add **`knowledge_chunks`** and indexing job; use chunks for retrieval in a later phase.
   - Add **`assistant_feedback`** collection and **POST** endpoint to record helpful / not helpful (user_id, query, answer, helpful, source_article_ids, created_at). Optionally same for existing assistant chat.

2. **Frontend**
   - **User:** On Help page (`HelpPage.js`) and/or dashboard: add “Ask a question” that calls help-assistant API; show answer, steps, and sources as links to `/help?article=<slug>`. Add Helpful/Not Helpful.
   - **Admin:** In Knowledge Centre (e.g. tab or sidebar): add “Help Assistant” or “Ask” that calls admin help-assistant (role=ADMIN so USER+STAFF+ADMIN articles); show answer and links to article edit/view.

3. **Safety**
   - Never return draft/archived in retrieval. Never expose ADMIN/STAFF articles to USER. In response, do not claim legal advice; use “based on current help documentation” / “review your records” where relevant.

---

## 6. Acceptance Criteria (Task Section 12) – Status

| Criterion | Status |
|-----------|--------|
| Users can ask help questions and get grounded answers from published docs | **Not met** — current assistant is not doc-grounded; no help-assistant endpoint |
| Staff/admin can access internal docs based on permissions | **Partial** — admin sees all in KB UI; no staff-scoped help or role-based retrieval |
| Assistant cites source articles | **Partial** — current assistant cites file-based “sources”; not KB articles with slug |
| Assistant refuses to guess if no grounded answer exists | **Not met** — current assistant can answer from portal data; no strict fallback |
| Feedback buttons work | **Not met** — no assistant_feedback or Helpful/Not Helpful |
| No restricted docs leak across roles | **Met** for client help (USER only); **N/A** for assistant (doesn’t use KB) |

---

## 7. Files and Components Referenced (Current)

| Component | Path / Location |
|-----------|------------------|
| Assistant routes (client) | `backend/routes/assistant.py` |
| Assistant chat service | `backend/services/assistant_chat_service.py` |
| Assistant retrieval (file-based KB) | `backend/services/assistant_retrieval_service.py` |
| Assistant prompt | `backend/services/assistant_prompt.py` |
| Admin assistant (ask, chat, history) | `backend/routes/admin.py` (e.g. `/admin/assistant/ask`, `/admin/assistant/chat`) |
| Knowledge Base routes | `backend/routes/knowledge_base.py` (public_router, admin_router, client_help_router) |
| Help Centre UI | `frontend/src/pages/HelpPage.js` |
| Assistant chat UI (client) | `frontend/src/pages/AssistantPage.js` |
| Admin assistant UI | `frontend/src/pages/AdminAssistantPage.js` |
| DB indexes | `backend/database.py` (no knowledge_chunks or assistant_feedback) |

---

**End of audit.** Implement per Section 5 outline; prefer dedicated Help Assistant (Option A) and article-level search first (Option 2) unless product decides otherwise.
