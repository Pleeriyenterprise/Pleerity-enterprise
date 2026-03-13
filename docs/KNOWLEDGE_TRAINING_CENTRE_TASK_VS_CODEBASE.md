# Knowledge & Training Centre – Task vs Codebase Audit (Current)

**Purpose:** Check the codebase against the full task (Sections 1–16) to see what is implemented, what is missing, and any conflicts. No code changes in this audit.

**Task source:** Implement a Knowledge & Training Centre: two portals (Admin Knowledge Centre + User Help Centre), `knowledge_articles`-style model, categories, CRUD, versioning, PDF export, search, release notes, product linking, permissions, status, future AI support.

---

## 1. Executive Summary

| Area | Implemented | Missing / Partial | Conflict / Decision |
|------|-------------|-------------------|----------------------|
| **Two portals** | Admin KC at `/admin/knowledge-base`; User Help at `/help` using `/api/client/help/*` | — | Naming: UI uses "Knowledge Centre" / "Help Centre"; API uses `kb_articles`, `/api/kb`, `/api/admin/kb`. No conflict. |
| **Database model** | `kb_articles` collection with id, title, slug, audience, category, tags, content, summary (excerpt), status, version, created_by, updated_by, created_at, updated_at, product_module, related_feature_flags, article_type, release_* fields | `downloadable_pdf_url` (optional); `related_articles` derived at read time | Collection name in code is `kb_articles` (constant `ARTICLES_COLLECTION`); task said `knowledge_articles`. **Recommendation:** Keep `kb_articles`; no rename. |
| **Categories** | ADMIN + USER default sets (Staff Training, Operations Playbooks, …, Release Notes; Getting Started, Adding Properties, …, Billing, Troubleshooting) | — | Matches task Section 3. |
| **Admin UI** | Article list with Title, Category, Audience, Status, Last Updated, Version; Create, Edit, Publish, Unpublish, Archive, Delete, Export PDF | — | Complete for Section 4. |
| **Article editor** | Markdown textarea; category, audience, version, tags | Rich editor (headings, lists, images, code blocks, internal links, screenshots); structured tagging (product_module, feature flags, roles) in UI | Task Section 5: rich editor and tagging are **optional / later phase** per prior audit. |
| **Version control** | `version` field stored and displayed; "Last Updated" in list and PDF | Optional version history (e.g. append-only) | Section 6 satisfied. |
| **PDF export** | `GET /api/admin/kb/articles/{id}/export-pdf`; "Download Training Guide"; title, version, last updated, content, page numbers, Pleerity branding | — | Section 7 done. |
| **User Help Centre** | `/help` (client portal); categories, search, article list/detail from `/api/client/help/articles` and `/api/client/help/categories` (USER audience only) | — | Section 8 done. |
| **Visibility rules** | audience ADMIN | STAFF | USER; public and client APIs return only USER (or no audience for backward compat); admin sees all | — | Section 9 done. |
| **Search** | Public and client: title, excerpt, content, tags (regex). Admin: title, excerpt only | Task: include "summary"; "most relevant first". Admin search does not use content, tags, or summary | **Gap:** Extend admin search to content, tags, summary. Optional: add simple relevance (e.g. title match first) when query present. |
| **Release notes** | Backend: `article_type`, `release_version`, `release_date`, `changes`, `affected_modules` stored on create/update | Admin UI has no release-notes type selector or fields (version, date, changes, affected modules); no dedicated "Release Notes" view in admin or user | **Gap:** Section 11 – add release-notes form (or article type + conditional fields) and optionally a Release Notes list/section. |
| **Product linking** | "Need help? See: Uploading Evidence guide" on Documents and PropertyDetail pages → `/help` | Deep link to specific article (e.g. `/help?article=slug`) not wired; no central config (e.g. product_module → slug) | **Optional:** Add query `?article=<slug>` so Help opens that article; or config for "Evidence Upload" → slug. |
| **Permissions** | Admin-only create/edit/publish/archive/delete (admin_route_guard); client help read requires client_route_guard, USER articles only | Staff read of ADMIN/STAFF articles not implemented (task: "Staff may read internal articles but not edit") | **Optional / Phase 2:** Staff role and read access to ADMIN/STAFF in admin KC. |
| **Status** | draft, published, archived; draft and archived never returned to public/client | — | Section 14 done. |
| **Future AI** | — | Optional fields (e.g. last_reviewed_at, ai_suggested_changes) not added | Section 15: add when needed; schema allows extra optional fields. |

---

## 2. What Is Implemented (Evidence)

### 2.1 Backend (`backend/routes/knowledge_base.py`)

- **Collections:** `kb_articles`, `kb_categories`, `kb_search_analytics` (constant `ARTICLES_COLLECTION = "kb_articles"`).
- **Article document:** article_id, title, slug, category_id, excerpt, content, tags, status (draft/published/archived), audience (ADMIN/STAFF/USER), version, summary, meta_title, meta_description, product_module, related_feature_flags, article_type, release_version, release_date, changes, affected_modules, created_by, updated_by, created_at, updated_at, view_count, is_active, published_at, etc.
- **Default categories:** `DEFAULT_CATEGORIES_ADMIN` (Staff Training, Operations Playbooks, Admin Console, Provisioning, Compliance Engine, Job Monitoring, Feature Flags, Support Procedures, Release Notes) and `DEFAULT_CATEGORIES_USER` (Getting Started, Adding Properties, Uploading Evidence, Compliance Score, Dashboard Guide, Reminders, Compliance Packs, Billing, Troubleshooting).
- **Public API (`/api/kb`):** List/get articles and categories with `status=published`, `audience=USER` (or no audience). Search on title, excerpt, content, tags. Analytics for search.
- **Client Help API (`/api/client/help`):** Same filters; requires `client_route_guard`. List articles, get by slug, list categories with counts.
- **Admin API (`/api/admin/kb`):** Full CRUD, list (with status/category/audience/search), get, create, update, publish, unpublish, **archive**, **export-pdf**. Categories CRUD. Analytics (top viewed, top searches, no-result searches).
- **PDF:** `_build_article_pdf(article)` (reportlab): title, version, last updated, content, footer with company name and page numbers.
- **Visibility:** Public and client list/get use `status=published` and `audience=USER` (or missing); admin list returns all (filterable). Draft and archived never exposed to non-admin.

### 2.2 Frontend

- **Admin:** `AdminKnowledgeBasePage.js` at `/admin/knowledge-base`. Menu label "Knowledge Centre" in `UnifiedAdminLayout.js`. Articles tab: filters (search, status, category, audience), table/cards with Title, Category, Audience, Status, Version, Last updated; actions Create, Edit, Publish/Unpublish, Archive, Delete, **Export PDF**. Categories and Analytics tabs. Article form: title, category, status, audience, version, excerpt, content (textarea), tags.
- **User Help:** `HelpPage.js` at `/help` (client portal). Fetches `/client/help/categories` and `/client/help/articles` (with search and category). Article detail shows version and updated_at; related articles; "Email support" link.
- **Product links:** `DocumentsPage.js` and `PropertyDetailPage.js` show "Need help? See: Uploading Evidence guide" with `Link to="/help"`.
- **Public KB:** `PublicKnowledgeBasePage.js` at `/support/knowledge-base` (unauthenticated); uses `/api/kb` (USER-only in backend).

### 2.3 Routes and Guards

- `server.py`: `knowledge_base.public_router`, `knowledge_base.admin_router`, `knowledge_base.client_help_router` included.
- Admin KB protected by `admin_route_guard`; client help by `client_route_guard`.

---

## 3. Gaps and Optional Work

| # | Task section | Gap | Status |
|---|----------------|-----|--------|
| 1 | Section 5 (Article editor) | Rich editor (images, code blocks, etc.) and structured tagging in UI | Optional phase; keep markdown textarea for now. |
| 2 | Section 10 (Search) | Admin search only title + excerpt; task wants title, summary, tags, content. | **Done:** Admin list search extended to content, tags, summary (regex); tags use $elemMatch for array. |
| 3 | Section 11 (Release notes) | Backend has release_* fields; admin form had no article_type or release fields. | **Done:** Admin article form has Article type (Standard / Release Notes) and conditional fields: release_version, release_date, changes (one per line), affected_modules (comma-separated). |
| 4 | Section 12 (Linking) | Links went to `/help` only. | **Done:** HelpPage already supports `?article=<slug>`. Product links on Documents and Property Detail now use `/help?article=uploading-evidence`. |
| 5 | Section 13 (Staff read) | Only admins see admin KC; no staff role for read-only internal articles. | Phase 2: role check and allow staff to read ADMIN/STAFF articles in admin KC. |
| 6 | Section 15 (Future AI) | No optional AI fields. | Add when needed (e.g. last_reviewed_at, ai_suggested_changes); do not require in validation. |
| 7 | Task output "Example seeded articles" | No seed script for `kb_articles`. | **Done:** `backend/scripts/seed_kb_articles.py` idempotently creates 4 example USER articles (uploading-evidence, adding-a-property, compliance-score-explained, reminders-and-alerts) if slug does not exist. |

---

## 4. Conflicts and Safest Options

- **Collection name:** Task said `knowledge_articles`; codebase uses `kb_articles`. **Option:** Keep `kb_articles`; no migration.
- **Archive vs delete:** Task: Archive = status archived, visible in admin only. Code: Archive endpoint sets status to archived; delete is soft (is_active). **Option:** Keep both; no conflict.
- **Public KB vs User Help:** Task: User Help = in-app, USER-only. Code: `/support/knowledge-base` is public (USER-only in API); `/help` is in-app and uses client help API (USER-only). **Option:** No change; both paths are valid (public marketing vs logged-in help).

---

## 5. Acceptance Criteria (Section 16) – Status

| Criterion | Status |
|----------|--------|
| Creating documentation articles | Done (admin CRUD) |
| Categorising them | Done (category_id + default ADMIN/USER categories) |
| Restricting visibility | Done (audience + status; public/client see USER published only) |
| Exporting manuals as PDF | Done (export-pdf endpoint + Download Training Guide) |
| Searching documentation | Done (public/client: title, excerpt, content, tags; admin: title, excerpt only – extend to content, tags, summary for parity) |
| Linking help articles from product UI | Done (links to /help); optional: deep link to article slug |
| Version tracking | Done (version field + Last Updated in UI and PDF) |
| Updating manuals when system changes | Done (edit + version in form) |

---

## 6. Files Referenced

| Layer | File(s) |
|-------|--------|
| Backend routes | `backend/routes/knowledge_base.py` |
| Frontend admin | `frontend/src/pages/AdminKnowledgeBasePage.js` |
| Frontend user help | `frontend/src/pages/HelpPage.js` |
| Frontend public KB | `frontend/src/pages/public/PublicKnowledgeBasePage.js` |
| Routing | `frontend/src/App.js` |
| Admin menu | `frontend/src/components/admin/UnifiedAdminLayout.js` |
| Client menu (help) | `frontend/src/components/ClientPortalLayout.jsx` |
| Product help links | `frontend/src/pages/DocumentsPage.js`, `frontend/src/pages/PropertyDetailPage.js` |
| Prior audit | `docs/KNOWLEDGE_TRAINING_CENTRE_TASK_AUDIT.md` |

---

## 7. Recommended Implementation Order (If Implementing Gaps)

1. **Admin search:** Extend admin list search to content, tags, summary (and optionally relevance when query present).
2. **Release notes in admin UI:** Article type "Release Notes" + fields (release_version, release_date, changes, affected_modules); optionally Release Notes filter/section.
3. **Help deep link:** Support `?article=<slug>` on `/help` so product pages can link to a specific article.
4. **Example seeded articles:** Optional seed script for USER articles with example titles.
5. **Rich editor / tagging:** Optional later phase.
6. **Staff read access:** Phase 2 when staff role exists.
7. **Future AI fields:** Add optional fields when needed.

---

*Audit only; no code or assets were changed. Proceed with implementation of gaps only after approval; follow existing patterns and safest options above.*
